"""Download Metro Council meetings from Nashville's public Legistar API.

Everything is cached as JSON under data/raw/<event id>/ so builds and tests
run offline, and a re-fetch shows exactly what the city changed.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://webapi.legistar.com/v1/nashville"
COUNCIL_BODY_ID = 138  # "Metropolitan Council"
RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
UA = "nashville-council-digest (+https://github.com/nathanaelhub/nashville-council-digest)"


def get(path: str, **params) -> object:
    url = f"{API}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, safe="$'+:")
    for attempt in range(7):  # about two minutes in all: rides out a dropped connection or DNS blip
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except OSError:
            if attempt == 6:
                raise
            time.sleep(2 ** attempt)


def council_meetings(since: str, until: str) -> list[dict]:
    """Full-council meetings with a final agenda between two ISO dates."""
    flt = (f"EventBodyId eq {COUNCIL_BODY_ID} and EventDate ge datetime'{since}' "
           f"and EventDate lt datetime'{until}'")
    events = get("events", **{"$filter": flt, "$orderby": "EventDate"})
    return [e for e in events if e.get("EventAgendaFile")]


def fetch_meeting(event: dict, root: Path = RAW, refresh: bool = False) -> Path:
    """Save one meeting: the event, its agenda items, and every matter on it
    (record, plain text, history, sponsors, attachments). Matters already
    saved are kept unless refresh is set, so an interrupted fetch resumes."""
    out = root / str(event["EventId"])
    (out / "matters").mkdir(parents=True, exist_ok=True)
    items = get(f"events/{event['EventId']}/eventitems", AgendaNote=1, MinutesNote=1, Attachments=1)
    write(out / "event.json", event)
    write(out / "items.json", items)
    for mid in sorted({i["EventItemMatterId"] for i in items if i.get("EventItemMatterId")}):
        if not refresh and (out / "matters" / f"{mid}.json").exists():
            continue
        matter = get(f"matters/{mid}")
        versions = get(f"matters/{mid}/versions")
        text = None
        if versions:
            latest = max(versions, key=lambda v: int(v["Value"]))
            text = get(f"matters/{mid}/texts/{latest['Key']}")
        write(out / "matters" / f"{mid}.json", {
            "matter": matter,
            "text": (text or {}).get("MatterTextPlain"),
            "histories": get(f"matters/{mid}/histories"),
            "sponsors": get(f"matters/{mid}/sponsors"),
            "attachments": get(f"matters/{mid}/attachments"),
        })
    return out


def write(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
