# Nashville Council Digest

**What did the Metro Council do?** Every bill and resolution from Nashville's Metro Council
meetings, in plain language, with what happened to it and which council district it's in.

**Live site:** https://nathanaelhub.github.io/nashville-council-digest/

Council agendas run to 100–170 items, written in legal language ("An ordinance to amend Title 17
of the Metropolitan Code of Laws... by changing from RS10 to R10 zoning for property located
at..."). This turns each meeting into a page a resident can read in a few minutes, and filters it
to their district, without asking them to trust a model's reading of the law.

## How it stays honest

| What you see | Where it comes from |
|---|---|
| Outcome (passed, moving forward, put off...) | The action Legistar recorded, mapped by code |
| Sponsors, links, agenda and minutes | Legistar, verbatim |
| Council district | Metro's public parcel map, from the parcels or address the bill cites |
| What a zoning code means | Quoted from Metro Planning staff reports and its zoning page, with links |
| Counts at the top of each meeting | Code |
| The plain-language summary | Claude, then a fact check by code, then a second Claude reading for meaning |

The fact check (`src/council_digest/verify.py`) requires every dollar amount, number, district,
file number and name in a summary to appear in the official text Claude was shown. Dollar amounts
are compared as numbers, so "$6 million" matches "$6,000,000". A summary that fails gets one
retry with the problems listed; if it still fails, **the site shows the official title instead**.
The checker runs again at every build, so it alone decides what gets published.

Claude never decides an outcome. There's no Claude-written "meeting overview" either, because
an overview is exactly the kind of text the checker can't verify.

## Findings

- **Legistar's "passed" flag can't be trusted.** It reads "Pass" when a motion to *defer* passed,
  and on October 20, 2026 it read "Fail" for RS2026-2330, which the council adopted and the Mayor
  signed the next day. Outcomes here come from the recorded action instead.
- **The city doesn't record which district an item is in,** and bill texts almost never name one.
  But zoning bills cite official parcels ("Parcel No. 086 as designated on Map 069-16") and other
  items give addresses, and Metro's parcel layer has a council district for each. That locates
  180 of 194 site-specific zoning bills from January–October 2026; most of the rest describe
  unnumbered land, whole corridors or areas bounded by streets. Countywide legislation has no district, by design.
- **The official record has its own errors.** Reading flagged summaries against their texts turned
  up four: a Council Office analysis naming the wrong nonprofit for a grant (RS2026-2301), a
  resolution and its analysis disagreeing on the Sheriff's pay (RS2026-2150), an analysis giving
  4400 Harding Pike for an easement the ordinance puts at 4500 (BL2025-1158), and a rezoning whose
  text says "RM20 RM9-NS" while its title says RM20 (BL2026-1552). Summaries are checked against
  the ordinance or resolution text, not the analysis.
- **Checking that a fact appears in the text isn't the same as checking it's attached to the
  right thing.** See the evaluation below: a dollar amount moved from one line of a bill to another
  passes the checker.
- **The checker refuses correct arithmetic.** One summary added 36 and 96 feet of new sewer
  pipe into "about 132 feet". That's right, but 132 isn't in the text, so it isn't published.
  That's the intended trade: the site only shows facts it can point to.

## Evaluation

Can the fact checker be trusted, and what does it miss? To find out, I took 80 published summaries
(random, seeded) and planted one known error in copies of each: a changed dollar amount, a changed
number, a name that isn't in the bill, two names from the bill swapped, or the opening verb
reversed ("Approves" became "Rejects"). Then I ran the checker on every copy, and asked Claude
(Sonnet) to judge each summary against the bill text without being told which ones were altered.
The originals and altered copies were shuffled together in batches of 8.

| Planted error | n | Checker caught | Claude judge caught | Either caught |
|---|---|---|---|---|
| Dollar amount changed | 34 | 34 (100%) | 34 (100%) | 34 (100%) |
| Other number changed | 63 | 59 (94%) | 63 (100%) | 63 (100%) |
| Name not in the bill | 78 | 77 (99%) | 78 (100%) | 78 (100%) |
| Two names swapped | 62 | 0 | 56 (90%) | 56 (90%) |
| Verb reversed | 44 | 0 | 44 (100%) | 44 (100%) |

Three of the 62 "swaps" kept the meaning ("an agreement between A and B" reversed), so the
judge caught 56 of 59 real swap errors. The misses included a grant's giver and receiver being
reversed. The 4 numbers the checker missed all changed a "0" house number to "3", with a 3
elsewhere in the bill. Full review: [`evals/results/2026-10-29/review.md`](evals/results/2026-10-29/review.md).

**What this means for the site.** The checker is good at what it's for: facts that are wrong or
made up. It can't see meaning, and a judge can. So every summary that passes the checker is also
read by the judge (`council-digest judge`, `src/council_digest/judge.py`), and a summary it flags
is replaced by the official title, the same as one that fails the checker. The judge can only hold
a summary back, never put one up, so its false alarms cost a plain-language summary, not accuracy.

On October 30, 2026 it read all 1,124 summaries that passed the checker ($7.57) and flagged 14.
Reading each against its text: **6 real errors** the checker had passed, including a CMA Fest bill
summary that made a firearms ban sound waivable; 1 copied from a garbled bill text; 3 loose
wordings; and 4 false alarms where the judge's own explanation says it found nothing wrong. All 14
now show the official title. Details: [`evals/results/2026-10-30-judge/review.md`](evals/results/2026-10-30-judge/review.md).
Verdicts are stored with each summary and keyed to its text, so a summary is judged again only if
it or its text changes.

**What the judge found in the 80 real summaries.** It flagged 3. On reading each against its
text: none was a wrong summary. One was a false alarm (its own explanation says so). Two were
**problems in the official record**: on RS2026-2301 the Council Office analysis names a different
nonprofit (Tennessee Voices for Children) from the one actually getting the grant, and on
RS2026-2150 the resolution says the Sheriff's salary will be "no less than 10 percent lower" than
the Police Chief's, while the analysis says "no less than 90 percent" of it.

This review was done by Claude in the session that built the project, not by an independent
person. The cases, verdicts and summaries are all in the repo for anyone to check.

```bash
COUNCIL_DIGEST_USE_LOGIN=1 uv run python evals/run.py --n 80 --out evals/results/<date>
uv run python evals/score.py evals/results/<date>
```

## Coverage and limits

- Full-council meetings from January 20 to October 20, 2026 (21 meetings, 2,500 agenda items,
  1,125 distinct bills and resolutions). Committees and the Planning Commission aren't included.
- Summaries describe what an item *does*, from its text. They don't explain why, who supports it,
  or what will happen; for that, follow the official record and the minutes.
- Zoning codes (RS10, SP, R6-A) are explained under each card and on a [zoning terms](https://nathanaelhub.github.io/nashville-council-digest/zoning.html)
  page, quoted from Metro Planning Commission staff reports and Metro Planning's
  [zoning classifications](https://www.nashville.gov/departments/planning/land-development/rezone-my-property/zoning-classifications)
  page (cached in `data/zoning/sources/`; a test checks every quote is in its source). Codes are
  explained part by part (RM20-A-NS is RM20-A plus -NS). Every district named in a published summary
  has a definition, and a test fails if a new one appears without one.
- District lookup can miss addresses newer than the parcel layer (it then uses the nearest house
  number on the same street, and says so) and can't place unnumbered land.
- Not affiliated with Metro Nashville. Always confirm with the official record.

## Running it

```bash
uv sync
uv run pytest                                   # offline, against the committed data
uv run council-digest fetch --since 2026-07-01  # Legistar -> data/raw (resumes if interrupted)
uv run council-digest locate                    # districts -> data/districts.json
COUNCIL_DIGEST_USE_LOGIN=1 uv run council-digest summarize   # Claude -> data/summaries
COUNCIL_DIGEST_USE_LOGIN=1 uv run council-digest judge       # second reading of new summaries
uv run council-digest build                     # -> _site/
```

`summarize` uses the `claude` CLI. `COUNCIL_DIGEST_USE_LOGIN=1` makes it use your Claude login
instead of an `ANTHROPIC_API_KEY`. Summaries are cached by a hash of the text, so a bill that
returns for its second and third readings isn't summarized again unless its text changed.

### After each council meeting

```bash
scripts/update.sh --push    # or without --push to review the commit first
```

It re-fetches the last 21 days (`--since` to change that), so the minutes and actions Legistar
fills in a few days after a meeting are picked up; then it runs `locate`, `summarize`, `judge`
and the tests, and commits `data/` only if everything passed. The site tests check every shown
summary still passes the checker and every badge matches its recorded outcome. GitHub Pages
rebuilds from the committed data once the tests pass there too. Summaries and the judge need your
Claude login, which is why this runs on your machine rather than in CI.

## Layout

```
src/council_digest/legistar.py   Legistar API client and cache
src/council_digest/records.py    meetings and items; outcomes from recorded actions
src/council_digest/geo.py        council districts from parcels and addresses
src/council_digest/summarize.py  Claude summaries with check-and-retry
src/council_digest/judge.py      second Claude reading; flagged summaries aren't shown
src/council_digest/verify.py     the fact checker
src/council_digest/zoning.py     zoning codes in Metro Planning's words
src/council_digest/site.py       static site
evals/                           planted-error evaluation of the checker and a Claude judge
data/                            cached records, summaries, districts (committed)
```

Data: [Nashville Legistar](https://nashville.legistar.com/) and Metro Nashville's
[parcel layer](https://data.nashville.gov/), both public. MIT license.
