"""Turn a cached Legistar meeting into plain records.

Outcomes are decided here, by code, from the action Legistar recorded,
never by the model. Legistar's "passed" flag is not used: it reads "Pass"
when a motion to *defer* passed, and on 2026-10-20 it read "Fail" for
RS2026-2330, which the council adopted and the Mayor signed the next day.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .legistar import RAW

SITE = "https://nashville.legistar.com"

# action name (lowercased) -> (outcome group, plain phrase)
ACTIONS = {
    "adopted": ("passed", "Adopted"),
    "adopted as amended": ("passed", "Adopted as amended"),
    "approved": ("passed", "Approved"),
    "confirmed": ("passed", "Confirmed"),
    "passed on third reading": ("passed", "Passed on third (final) reading"),
    "passed on third reading as amended": ("passed", "Passed on third (final) reading, as amended"),
    "passed on second reading": ("advanced", "Passed second reading; one more vote to go"),
    "passed on second reading as amended": ("advanced", "Passed second reading as amended; one more vote to go"),
    "passed on first reading": ("advanced", "Passed first reading; two more votes to go"),
    "nominated": ("advanced", "Nominated; the council votes on confirmation later"),
    "deferred": ("deferred", "Deferred to a later meeting"),
    "deferred indefinitely": ("deferred", "Deferred indefinitely"),
    "deferred by rule": ("deferred", "Deferred by rule"),
    "referred": ("deferred", "Sent to committee"),
    "re-referred": ("deferred", "Sent back to committee"),
    "withdrawn": ("withdrawn", "Withdrawn"),
    "failed": ("failed", "Failed"),
    "not adopted": ("failed", "Not adopted"),
    "substituted": ("replaced", "Replaced by a substitute version"),
    "amended": ("amended", "Amended"),
}
FINAL = ("passed", "failed", "withdrawn", "deferred", "advanced")


@dataclass
class Item:
    file: str                 # e.g. "BL2026-1234", "RS2026-2330"
    matter_id: int
    kind: str                 # Bill, Resolution, Appointment, ...
    title: str
    section: str              # agenda heading, e.g. "Bills on Third Reading"
    outcome: str              # passed / advanced / deferred / withdrawn / failed / replaced / none
    outcome_text: str
    actions: list[str]
    sponsors: list[str]
    districts: list[int]
    text: str
    url: str
    attachments: list[dict] = field(default_factory=list)


@dataclass
class Meeting:
    event_id: int
    date: str
    url: str
    agenda_pdf: str | None
    minutes_pdf: str | None
    items: list[Item]


DISTRICT = re.compile(r"\b(?:Council\s+)?District\s+(?:No\.\s*)?(\d{1,2})\b", re.I)


def districts(text: str) -> list[int]:
    """Council districts (1-35) named in the text."""
    return sorted({int(n) for n in DISTRICT.findall(text or "") if 1 <= int(n) <= 35})


def outcome(actions: list[str]) -> tuple[str, str]:
    """The meeting's last recorded action decides the outcome."""
    known = [a for a in actions if a.lower() in ACTIONS]
    if not known:
        return ("none", "No action recorded" if not actions else actions[-1].capitalize())
    return ACTIONS[known[-1].lower()]


def load(event_dir: Path) -> Meeting:
    event = json.loads((event_dir / "event.json").read_text(encoding="utf-8"))
    rows = json.loads((event_dir / "items.json").read_text(encoding="utf-8"))
    rows.sort(key=lambda r: (r.get("EventItemAgendaSequence") or 0, r.get("EventItemMinutesSequence") or 0))
    section, order, by_matter = "", [], {}
    for r in rows:
        mid = r.get("EventItemMatterId")
        if not mid:
            section = (r.get("EventItemTitle") or "").strip() or section
            continue
        if mid not in by_matter:
            by_matter[mid] = {"section": section, "actions": []}
            order.append(mid)
        if r.get("EventItemActionName"):
            by_matter[mid]["actions"].append(r["EventItemActionName"].strip())
    items = []
    for mid in order:
        path = event_dir / "matters" / f"{mid}.json"
        if not path.exists():
            continue
        m = json.loads(path.read_text(encoding="utf-8"))
        rec, text = m["matter"], m["text"] or ""
        status, phrase = outcome(by_matter[mid]["actions"])
        items.append(Item(
            file=rec["MatterFile"],
            matter_id=mid,
            kind=rec.get("MatterTypeName") or "",
            title=" ".join((rec.get("MatterTitle") or rec.get("MatterName") or "").split()),
            section=by_matter[mid]["section"],
            outcome=status,
            outcome_text=phrase,
            actions=by_matter[mid]["actions"],
            sponsors=[s["MatterSponsorName"] for s in sorted(m["sponsors"], key=lambda s: s.get("MatterSponsorSequence") or 0)],
            districts=districts(text + " " + (rec.get("MatterTitle") or "")),
            text=text,
            url=f"{SITE}/LegislationDetail.aspx?ID={mid}&GUID={rec['MatterGuid']}",
            attachments=[{"name": a["MatterAttachmentName"], "url": a["MatterAttachmentHyperlink"]} for a in m["attachments"]],
        ))
    return Meeting(
        event_id=event["EventId"],
        date=event["EventDate"][:10],
        url=event.get("EventInSiteURL") or SITE,
        agenda_pdf=event.get("EventAgendaFile"),
        minutes_pdf=event.get("EventMinutesFile"),
        items=items,
    )


def meetings(root: Path = RAW) -> list[Meeting]:
    return sorted((load(d) for d in root.iterdir() if (d / "items.json").exists()), key=lambda m: m.date)
