"""Plain-language summaries of agenda items, written by Claude and checked by code.

Claude is run through the `claude` CLI (`claude -p`), with no tools, no
settings and no MCP servers: it sees only the official text and returns
JSON. Each summary is checked with verify.check against exactly the text
Claude was shown; a failed check gets one retry with the problems listed,
and a summary that still fails is kept but marked unverified, so the site
shows the official title instead.

Summaries are cached in data/summaries/<file>.json by a hash of the source
text, so a bill that comes back for second and third reading is not
re-summarized unless its text changed.

COUNCIL_DIGEST_USE_LOGIN=1 drops ANTHROPIC_API_KEY so the CLI uses its login.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

from .records import Item
from .verify import check

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "summaries"
MAX_TEXT = 12_000
BATCH = 6
TOPICS = [
    "Housing and zoning", "Budget, grants and contracts", "Streets and transportation",
    "Public safety", "Parks, libraries and arts", "Water, power and environment",
    "Health and social services", "How Metro runs", "Honors and recognitions", "Other",
]

SYSTEM = f"""You write plain-language summaries of Nashville Metro Council legislation for residents.

For each item you are given its file number, official title, sponsors and official text. Write:
- "summary": one or two short sentences saying what the item does, in plain words a 13-year-old
  could follow. Say who gets money and how much, what changes, and where, when the text says so.
- "topic": exactly one of: {", ".join(TOPICS)}.

Rules:
- Use only facts in that item's text. Every amount, number, date, district, address and name you
  write must appear in it. If a detail isn't there, leave it out.
- Don't say whether it passed, failed or was deferred; that is added separately.
- No opinions, no "important", no guessing at motives or effects the text doesn't state.
- Prefer "$6 million" to "$6,000,000"; keep street addresses and district numbers exact.
- Don't start with "This resolution" or "This ordinance"; start with the verb ("Gives...", "Rezones...").

Reply with only a JSON object: {{"items": [{{"file": "...", "summary": "...", "topic": "..."}}]}}."""


def source(item: Item) -> str:
    """Exactly what Claude sees for an item, and what its summary is checked against."""
    body = re.sub(r"(?s)^\s*\.\.title.*?\.\.body", "", item.text or "").strip()
    sponsors = ", ".join(item.sponsors) or "none listed"
    return f"{item.file}\nTitle: {item.title}\nSponsors: {sponsors}\nText:\n{body[:MAX_TEXT]}"


def key(item: Item) -> str:
    return hashlib.sha256(source(item).encode("utf-8")).hexdigest()[:16]


def cached(item: Item) -> dict | None:
    p = CACHE / f"{item.file}.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("source_hash") == key(item):
            # The current checker decides, not the one that ran when this was written.
            if d.get("summary"):
                d["problems"] = [str(p) for p in check(d["summary"], source(item))]
                d["verified"] = not d["problems"]
            return d
    return None


def needs_summary(item: Item) -> bool:
    return item.kind in ("Bill", "Resolution", "Late Resolution", "Ordinance") and bool(item.title)


def env() -> dict:
    e = dict(os.environ)
    if os.environ.get("COUNCIL_DIGEST_USE_LOGIN"):
        e.pop("ANTHROPIC_API_KEY", None)
    return e


async def claude(prompt: str, model: str, timeout: float = 300, system: str | None = None) -> tuple[str, float]:
    argv = ["claude", "-p", "--model", model, "--output-format", "json", "--system-prompt", system or SYSTEM,
            "--tools", "", "--setting-sources", "", "--disable-slash-commands", "--strict-mcp-config",
            "--mcp-config", '{"mcpServers":{}}']
    proc = await asyncio.create_subprocess_exec(
        *argv, env=env(), cwd=str(ROOT), stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(prompt.encode("utf-8")), timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"claude timed out after {timeout:.0f}s") from None
    if proc.returncode:
        raise RuntimeError(f"claude exited {proc.returncode}: {err.decode(errors='replace')[-500:]}")
    res = json.loads(out)
    if res.get("is_error"):
        raise RuntimeError(f"claude error: {res.get('result')}")
    return res["result"], float(res.get("total_cost_usd") or 0)


def parse(reply: str) -> dict[str, dict]:
    start = reply.find("{")
    obj, _ = json.JSONDecoder().raw_decode(reply[start:])
    return {r["file"]: r for r in obj["items"]}


def prompt_for(items: list[Item], feedback: dict[str, list[str]] | None = None) -> str:
    parts = []
    for it in items:
        part = f"=== {source(it)}"
        if feedback and feedback.get(it.file):
            part += ("\n\nYour last summary of this item had facts not in its text: "
                     + "; ".join(feedback[it.file]) + ". Write it again using only the text.")
        parts.append(part)
    return "Summarize each item.\n\n" + "\n\n".join(parts)


async def summarize_batch(items: list[Item], model: str) -> list[dict]:
    reply, cost = await claude(prompt_for(items), model)
    got = parse(reply)
    results, retry = {}, {}
    for it in items:
        r = got.get(it.file)
        problems = [str(p) for p in check(r["summary"], source(it))] if r else ["no summary returned"]
        results[it.file] = {"r": r, "problems": problems, "attempts": 1}
        if problems:
            retry[it.file] = problems
    if retry:
        again = [it for it in items if it.file in retry]
        reply2, cost2 = await claude(prompt_for(again, retry), model)
        cost += cost2
        got2 = parse(reply2)
        for it in again:
            r = got2.get(it.file)
            if r:
                problems = [str(p) for p in check(r["summary"], source(it))]
                if len(problems) <= len(results[it.file]["problems"]):
                    results[it.file] = {"r": r, "problems": problems, "attempts": 2}
                else:
                    results[it.file]["attempts"] = 2
    out = []
    for it in items:
        r, problems = results[it.file]["r"] or {}, results[it.file]["problems"]
        topic = r.get("topic") if r.get("topic") in TOPICS else "Other"
        d = {"file": it.file, "source_hash": key(it), "model": model, "summary": r.get("summary"),
             "topic": topic, "verified": not problems, "problems": problems,
             "attempts": results[it.file]["attempts"], "batch_cost_usd": round(cost, 4)}
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = CACHE / f"{it.file}.json.tmp"
        tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(CACHE / f"{it.file}.json")
        out.append(d)
    return out


async def summarize_all(items: list[Item], model: str = "sonnet", concurrency: int = 2,
                        limit: int | None = None, log=print) -> list[dict]:
    todo, seen = [], set()
    for it in items:
        if needs_summary(it) and it.file not in seen and not cached(it):
            seen.add(it.file)
            todo.append(it)
    todo = todo[:limit] if limit else todo
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    sem = asyncio.Semaphore(concurrency)
    done = []

    async def run(b):
        async with sem:
            try:
                res = await summarize_batch(b, model)
            except Exception as e:  # noqa: BLE001 - one bad batch shouldn't stop the run
                log(f"batch {b[0].file}..: {e}")
                return
            done.extend(res)
            bad = sum(not r["verified"] for r in res)
            log(f"{len(done)}/{len(todo)} summarized ({bad} unverified in this batch)")

    await asyncio.gather(*(run(b) for b in batches))
    return done
