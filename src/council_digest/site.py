"""Build the static site: one page per meeting, one per council district.

Everything a reader sees is either official (titles, sponsors, links,
outcomes recorded in Legistar), computed by code (counts, districts), or a
Claude summary that passed verify.check. A summary that didn't pass is not
shown; the official title is, with a note saying so.
"""

from __future__ import annotations

import html
import json
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from . import geo, summarize
from .records import Item, Meeting, meetings

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "site"
REPO = "https://github.com/nathanaelhub/nashville-council-digest"

GROUPS = [
    ("passed", "Passed", "Final votes: these are now law or adopted."),
    ("advanced", "Moving forward", "Bills pass three readings; these cleared one or two tonight."),
    ("failed", "Failed", ""),
    ("deferred", "Put off", "Deferred to a later meeting or sent to committee."),
    ("withdrawn", "Withdrawn", ""),
    ("replaced", "Replaced", "A substitute version took this one's place."),
    ("amended", "Amended", ""),
    ("none", "On the agenda, no action recorded", ""),
]
BADGE = {"passed": "Passed", "advanced": "Moving forward", "failed": "Failed", "deferred": "Put off",
         "withdrawn": "Withdrawn", "replaced": "Replaced", "amended": "Amended", "none": "No action recorded"}

e = html.escape


def long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def page(title: str, body: str, depth: int = 0, description: str = "") -> str:
    up = "../" * depth
    desc = description or "Plain-language digests of Nashville Metro Council meetings, checked against the official record."
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="stylesheet" href="{up}style.css">
</head>
<body>
<header class="top"><div class="wrap">
  <p class="eyebrow"><a href="{up}index.html">Nashville Council Digest</a></p>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">
  <p>Not affiliated with Metro Nashville. Summaries are written by Claude from the official text and
  checked by code: every amount, number, district and name in them appears in that text. Outcomes,
  sponsors and links come straight from <a href="https://nashville.legistar.com/">Legistar</a>.
  Districts come from Metro's public parcel map. Always confirm with the official record.
  <a href="{REPO}">How this works</a>.</p>
</footer>
<script src="{up}filter.js"></script>
</body>
</html>
"""


def district_chips(item: Item, loc: dict | None, depth: int) -> str:
    if not loc or not loc["districts"]:
        return ""
    how = {"parcel": "from the parcels the bill cites", "address": "from the address in the bill",
           "nearby address": "from the nearest listed address on the same street"}.get(
        loc["via"], loc["via"] or "")
    refs = ", ".join(loc["refs"][:3])
    title = f"District found {how}" + (f" ({refs})" if refs else "")
    return " ".join(f'<a class="chip" href="{"../" * depth}district/{d}.html" title="{e(title)}">District {d}</a>'
                    for d in loc["districts"])


def item_card(item: Item, s: dict | None, loc: dict | None, depth: int, show_date: str | None = None) -> str:
    verified = bool(s and s.get("verified") and s.get("summary"))
    text = e(s["summary"]) if verified else e(item.title)
    note = "" if verified else (
        '<p class="note">Showing the official title: the plain-language summary didn\'t pass the fact check.</p>'
        if s else "")
    topic = (s or {}).get("topic") or ("Appointments" if item.kind == "Appointment" else "Other")
    districts = loc["districts"] if loc else []
    sponsors = ", ".join(item.sponsors[:4]) + (f" and {len(item.sponsors) - 4} more" if len(item.sponsors) > 4 else "")
    when = f'<span class="muted">{e(long_date(show_date))} · </span>' if show_date else ""
    return f"""<article class="card item" data-topic="{e(topic)}" data-districts="{' '.join(map(str, districts))}">
  <header><span class="file">{e(item.file)}</span><span class="badge s-{item.outcome}">{e(BADGE[item.outcome])}</span></header>
  <p class="summary">{text}</p>{note}
  <p class="meta">{when}{e(item.outcome_text)}{(' · Sponsors: ' + e(sponsors)) if sponsors else ''}</p>
  <p class="links">{district_chips(item, loc, depth)} <a href="{e(item.url)}" rel="noopener">Official record</a></p>
</article>"""


def filters(topics: list[str], districts: list[int]) -> str:
    t = "".join(f'<option value="{e(x)}">{e(x)}</option>' for x in topics)
    d = "".join(f'<option value="{x}">District {x}</option>' for x in districts)
    return f"""<form class="filters" id="filters">
  <label>Topic <select name="topic"><option value="">All topics</option>{t}</select></label>
  <label>District <select name="district"><option value="">All districts</option>{d}</select></label>
  <p class="muted" id="shown" aria-live="polite"></p>
</form>"""


def meeting_page(m: Meeting, sums: dict, locs: dict) -> str:
    items = [i for i in m.items if i.kind != "Appointment"]
    appts = [i for i in m.items if i.kind == "Appointment"]
    by = defaultdict(list)
    for i in items:
        by[i.outcome].append(i)
    for group in by.values():  # honors and routine items after the substantive ones, agenda order otherwise
        group.sort(key=lambda i: ((sums.get(i.file) or {}).get("topic") == "Honors and recognitions"))
    counts = Counter(i.outcome for i in items)
    topics = sorted({(sums.get(i.file) or {}).get("topic") or "Other" for i in items})
    dists = sorted({d for i in items for d in (locs.get(i.file) or {}).get("districts", [])})
    stats = "".join(f'<li><strong>{counts[k]}</strong> {e(label.lower())}</li>' for k, label, _ in GROUPS if counts[k])
    sections = []
    for key, label, hint in GROUPS:
        if not by[key]:
            continue
        cards = "\n".join(item_card(i, sums.get(i.file), locs.get(i.file), 1) for i in by[key])
        sections.append(f'<section class="group"><h2>{e(label)} <span class="count">{len(by[key])}</span></h2>'
                        f'{f"<p class=hint>{e(hint)}</p>" if hint else ""}{cards}</section>')
    appt = ""
    if appts:
        rows = "".join(f'<li><a href="{e(i.url)}" rel="noopener">{e(i.title)}</a> <span class="muted">· {e(i.outcome_text)}</span></li>'
                       for i in appts)
        appt = f'<details class="card appts"><summary>Board and commission appointments ({len(appts)})</summary><ul>{rows}</ul></details>'
    links = " · ".join(x for x in [
        f'<a href="{e(m.url)}" rel="noopener">Meeting page</a>',
        f'<a href="{e(m.agenda_pdf)}" rel="noopener">Agenda (PDF)</a>' if m.agenda_pdf else "",
        f'<a href="{e(m.minutes_pdf)}" rel="noopener">Minutes (PDF)</a>' if m.minutes_pdf else "",
    ] if x)
    body = f"""<h1>Metro Council, {e(long_date(m.date))}</h1>
<p class="lede">{len(items)} bills and resolutions{f" and {len(appts)} appointments" if appts else ""}. {links}</p>
<ul class="stats">{stats}</ul>
{filters(topics, dists)}
{''.join(sections)}
{appt}"""
    return page(f"Metro Council, {long_date(m.date)}", body, depth=1,
                description=f"What the Nashville Metro Council did on {long_date(m.date)}, in plain language.")


def district_page(n: int, entries: list[tuple[Meeting, Item]], sums: dict, locs: dict) -> str:
    latest = {}
    for m, i in entries:  # meetings are in date order, so the last one wins
        latest[i.file] = (m, i)
    cards = "\n".join(item_card(i, sums.get(i.file), locs.get(i.file), 1, show_date=m.date)
                      for m, i in sorted(latest.values(), key=lambda x: x[0].date, reverse=True))
    topics = sorted({(sums.get(i.file) or {}).get("topic") or "Other" for _, i in latest.values()})
    body = f"""<h1>District {n}</h1>
<p class="lede">{len(latest)} items that name a property or address in District {n}, newest first, with each one's
latest action. Countywide legislation affects every district and is on the meeting pages.
<a href="https://www.nashville.gov/departments/council/council-members" rel="noopener">Find your council member</a>.</p>
{filters(topics, [])}
{cards}"""
    return page(f"District {n}: Metro Council items", body, depth=1)


def index_page(ms: list[Meeting], district_counts: Counter) -> str:
    rows = []
    for m in reversed(ms):
        c = Counter(i.outcome for i in m.items if i.kind != "Appointment")
        rows.append(f'<li class="card meeting"><a href="meeting/{m.date}.html"><strong>{e(long_date(m.date))}</strong></a>'
                    f'<span class="muted">{c["passed"]} passed · {c["advanced"]} moving forward · {c["deferred"]} put off</span></li>')
    ds = "".join(f'<a class="chip" href="district/{d}.html">District {d} <span class="muted">· {district_counts[d]} {"item" if district_counts[d] == 1 else "items"}</span></a>'
                 for d in range(1, 36))
    body = f"""<h1>What did the Metro Council do?</h1>
<p class="lede">Every bill and resolution from Nashville's Metro Council meetings, in plain language,
with what happened to it. Summaries are written by Claude and checked by code against the official
text; outcomes come straight from the city's records.</p>
<h2>Meetings</h2>
<ul class="meetings">{''.join(rows)}</ul>
<h2>By council district</h2>
<p class="hint">Items whose property or address is in the district.</p>
<div class="chips">{ds}</div>"""
    return page("Nashville Council Digest", body)


def build(out: str | Path = "_site") -> Path:
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ASSETS, out)
    ms = meetings()
    sums = {}
    for m in ms:
        for i in m.items:
            if summarize.needs_summary(i):
                sums[i.file] = summarize.cached(i) or sums.get(i.file)
    sums = {k: v for k, v in sums.items() if v}
    locs = json.loads(geo.CACHE.read_text(encoding="utf-8")) if geo.CACHE.exists() else {}
    (out / "meeting").mkdir()
    (out / "district").mkdir()
    by_district = defaultdict(list)
    for m in ms:
        (out / "meeting" / f"{m.date}.html").write_text(meeting_page(m, sums, locs), encoding="utf-8")
        for i in m.items:
            for d in (locs.get(i.file) or {}).get("districts", []):
                by_district[d].append((m, i))
    counts = Counter({d: len({i.file for _, i in v}) for d, v in by_district.items()})
    for d in range(1, 36):
        (out / "district" / f"{d}.html").write_text(district_page(d, by_district[d], sums, locs), encoding="utf-8")
    (out / "index.html").write_text(index_page(ms, counts), encoding="utf-8")
    return out
