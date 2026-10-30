"""Which council district(s) an agenda item is about.

Legistar doesn't record districts, and bill texts rarely name one, but
zoning bills cite official parcels ("Property Parcel No. 086 as designated
on Map 069-16") and other items give street addresses ("at 501 Houston
Street"). Both are looked up in Metro's public parcels layer, which has a
Council district field. Only the parcel id, address and district are
requested: no owner data.

Results are cached in data/districts.json with how each was found, so the
site can say "District 1 (parcel 069-16-086)".
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .records import Item

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "districts.json"
PARCELS = ("https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
           "Parcels_view/FeatureServer/0/query")
UA = "nashville-council-digest (+https://github.com/nathanaelhub/nashville-council-digest)"

# "Property Parcel Nos. 094-097 and 120 as designated on Map 082-08"
PARCEL_REF = re.compile(
    r"Parcels?\s+(?:Nos?\.?\s*)?([\d\s,\-&and]+?)\s+as\s+designated\s+on\s+Map\s+(\d{3})(?:-(\d{2}))?(?![-\d])", re.I)
SUFFIX = {
    "street": "ST", "st": "ST", "avenue": "AVE", "ave": "AVE", "road": "RD", "rd": "RD", "drive": "DR",
    "dr": "DR", "pike": "PIKE", "lane": "LN", "ln": "LN", "boulevard": "BLVD", "blvd": "BLVD",
    "court": "CT", "ct": "CT", "place": "PL", "pl": "PL", "way": "WAY", "circle": "CIR", "cir": "CIR",
    "parkway": "PKWY", "pkwy": "PKWY", "trail": "TRL", "bend": "BND", "highway": "HWY", "hwy": "HWY",
    "alley": "ALY", "terrace": "TER", "row": "ROW", "loop": "LOOP",
}
DIRECTION = {"north": "N", "south": "S", "east": "E", "west": "W"}
ADDRESS = re.compile(
    r"\b(?:at|located at)\s+(\d{1,5}[A-Z]?(?:\s*(?:,|and|&|,\s*and)\s*\d{1,5}[A-Z]?)*)\s+"
    r"((?:[A-Z0-9][\w.'’]*\s+){0,4}?)(" + "|".join(SUFFIX) + r")\b\.?"
    r"(\s+(?:North|South|East|West))?", re.I)
# "9320, 9323, 9315 Highway 100": numbered state highways, spelled HIGHWAY in the parcel layer
HIGHWAY = re.compile(r"\b(?:at|located at)\s+(\d{1,5}(?:\s*(?:,|and|&|,\s*and)\s*\d{1,5})*)\s+(?:Highway|Hwy\.?)\s+(\d{1,3})\b", re.I)


def parcel_ids(text: str) -> list[str]:
    """Metro STANPAR ids (map, group, 4-digit parcel, 00) for the parcels a text cites."""
    out = []
    for nums, map_no, group in PARCEL_REF.findall(text or ""):
        for a, b in re.findall(r"(\d{1,4})(?:\s*-\s*(\d{1,4}))?", nums):
            lo, hi = int(a), int(b or a)
            if hi - lo > 50:
                continue
            out += [f"{map_no}{group or '00'}{p:04d}00" for p in range(lo, hi + 1)]
    return sorted(set(out))


def addresses(text: str) -> list[tuple[str, str]]:
    """(house number, LIKE pattern for PropStreet) for street addresses in a text."""
    out = []
    for houses, name, suffix, direction in ADDRESS.findall(text or ""):
        words = [w for w in re.sub(r"[^\w\s]", " ", name).upper().split() if w]
        if not words or words[0] in ("THE", "OF", "AND"):
            continue
        pattern = "%".join(words) + "%" + SUFFIX[suffix.lower()]
        if direction.strip():
            pattern += "%" + DIRECTION[direction.strip().lower()]
        out += [(re.sub(r"\D", "", h), pattern) for h in re.findall(r"\d{1,5}", houses)]
    for houses, road in HIGHWAY.findall(text or ""):
        out += [(h, f"HIGHWAY%{road}") for h in re.findall(r"\d{1,5}", houses)]
    return sorted(set(out))


def query(where: str) -> list[dict]:
    params = {"where": where, "outFields": "STANPAR,PropAddr,PropHouse,Council", "returnGeometry": "false", "f": "json"}
    url = PARCELS + "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            if "error" in d:
                raise RuntimeError(d["error"])
            return [f["attributes"] for f in d.get("features", [])]
        except OSError:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)


def council(attrs: list[dict]) -> list[int]:
    return sorted({int(a["Council"]) for a in attrs if (a.get("Council") or "").strip().isdigit()})


def nearest(house: str, pattern: str) -> dict | None:
    """The parcel with the closest house number on the same street, for addresses
    newer than the parcels layer. Only used within 200 numbers of the target."""
    rows = query(f"PropStreet LIKE '{pattern}' AND PropHouse <> ''")
    numbered = [(abs(int(r["PropHouse"]) - int(house)), r) for r in rows if (r.get("PropHouse") or "").isdigit()]
    numbered = [x for x in numbered if x[0] <= 200]
    return min(numbered, key=lambda x: x[0])[1] if numbered else None


FILE_REF = re.compile(r"\b(BL\d{4}-\d{1,5})\b")


def locate(item: Item) -> dict:
    text = f"{item.title}\n{item.text}"
    ids = parcel_ids(text)
    if ids:
        rows = []
        for i in range(0, len(ids), 50):
            rows += query("STANPAR IN (" + ",".join(f"'{p}'" for p in ids[i:i + 50]) + ")")
        if council(rows):
            return {"districts": council(rows), "via": "parcel", "refs": sorted({r["STANPAR"] for r in rows})[:20]}
    found, refs, via = [], [], "address"
    for house, pattern in addresses(text)[:10]:
        rows = query(f"PropHouse = '{house}' AND PropStreet LIKE '{pattern}'")
        if not rows:
            near = nearest(house, pattern)
            rows, via = ([near], "nearby address") if near else ([], via)
        if rows:
            found += council(rows)
            refs.append(rows[0]["PropAddr"])
    if found:
        return {"districts": sorted(set(found)), "via": via, "refs": refs}
    return {"districts": [], "via": None, "refs": []}


def locate_all(items: list[Item], log=print) -> dict[str, dict]:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [it for it in {it.file: it for it in items}.values() if it.file not in cache]
    for n, it in enumerate(todo, 1):
        cache[it.file] = locate(it)
        if n % 25 == 0 or n == len(todo):
            CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            log(f"located {n}/{len(todo)}")
    # Companion bills ("...in the Specific Plan district (BL2026-1403)") take their partner's districts.
    for it in items:
        r = cache.get(it.file)
        if r and not r["districts"]:
            for ref in FILE_REF.findall(f"{it.title} {it.text}"):
                partner = cache.get(ref)
                if ref != it.file and partner and partner["districts"]:
                    cache[it.file] = {"districts": partner["districts"], "via": f"same site as {ref}", "refs": [ref]}
                    break
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return cache
