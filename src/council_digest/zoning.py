"""Zoning codes (RS10, R6-A, RM20-A-NS, SP...) explained in Metro Planning's own words.

Each definition in data/zoning/glossary.json is a sentence copied from a Metro
Planning Commission staff report, with the report's URL. The report texts are
cached in data/zoning/sources/, and tests check every quote is in its report.

A code is explained by its base district (RM20-A-NS -> RM20-A, else RM20) plus
its suffixes (-A, -NS). Codes with no cited definition are left unexplained.
"""

from __future__ import annotations

import gzip
import json
import re
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "data" / "zoning"

CODE = re.compile(r"\b(AR2[aA]|SP|(?:RS|RM|R|OR|MU[NLGI]|CL|CS|CA|CF|IR|IWD|IG|ORI|ON|OL|OG)(?:\d+(?:\.\d+)?)?"
                  r"(?:-A)?(?:-NS)?)(?![\w-])")


@cache
def glossary() -> dict:
    return json.loads((DIR / "glossary.json").read_text(encoding="utf-8"))


def source_text(file: str) -> str:
    with gzip.open(DIR / "sources" / file, "rt", encoding="utf-8") as f:
        return f.read()


def norm(s: str) -> str:
    """Letters and digits only: PDF text breaks hyphens and dashes unpredictably."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def codes_in(text: str) -> list[str]:
    """Zoning codes mentioned in text, in order, without repeats."""
    out = []
    for m in CODE.finditer(text):
        c = m.group(1).replace("AR2A", "AR2a")
        if c not in out and explain(c):
            out.append(c)
    return out


def explain(code: str) -> list[dict]:
    """Glossary entries that explain a code: its base district, then its suffixes."""
    g = glossary()
    by_code = {d["code"]: d for d in g["districts"]}
    suffixes = {s["code"]: s for s in g["suffixes"]}
    rest, parts = code, []
    if rest.endswith("-NS"):
        rest, parts = rest[:-3], [suffixes["-NS"]]
    if rest in by_code:
        d = by_code[rest]
        if rest.endswith("-A") and "walkable" not in d["quote"]:
            parts = [suffixes["-A"]] + parts
        return [d] + parts
    if rest.endswith("-A"):
        rest, parts = rest[:-2], [suffixes["-A"]] + parts
    base = by_code.get(rest)
    return ([base] if base else []) + parts
