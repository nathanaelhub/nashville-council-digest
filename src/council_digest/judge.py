"""A second check: Claude reads each summary against its text and says whether it's faithful.

The fact checker (verify.check) proves every amount, number and name is in
the text, but not that they're attached to the right thing: "A gives B" and
"B gives A" pass it equally (see evals/). The judge reads for meaning. It can
only hold a summary back, never put one up: a flagged summary is replaced on
the site by the official title, the same as one that fails the checker.

Verdicts are stored in the summary's own file under "judge", keyed by a hash
of the text and the summary, so a rewritten summary is judged again.
"""

from __future__ import annotations

import asyncio
import hashlib
import json

from . import summarize
from .records import Item

BATCH = 8
SYSTEM = """You check plain-language summaries of Nashville Metro Council legislation against the official text.

For each pair, decide whether the summary is faithful: everything it says is supported by the text,
nothing is reversed or attached to the wrong party, place or amount. Leaving details out is fine;
saying something the text doesn't support, or the opposite of what it says, is not.

Reply with only JSON: {"verdicts": [{"id": "...", "faithful": true|false, "problem": "... or empty"}]}"""


def judge_key(source: str, summary: str) -> str:
    return hashlib.sha256(f"{source}\n--\n{summary}".encode("utf-8")).hexdigest()[:16]


async def judge(pairs: list[dict], model: str) -> dict[str, dict]:
    """Verdicts for [{id, source, summary}], several pairs per call."""
    prompt = "Check each pair.\n\n" + "\n\n".join(
        f"=== id {p['id']}\nOFFICIAL TEXT:\n{p['source']}\n\nSUMMARY:\n{p['summary']}" for p in pairs)
    reply, cost = await summarize.claude(prompt, model, timeout=600, system=SYSTEM)
    start = reply.find("{")
    obj, _ = json.JSONDecoder().raw_decode(reply[start:])
    return {str(v["id"]): v | {"cost": cost / len(pairs)} for v in obj["verdicts"]}


def verdict(item: Item, s: dict | None) -> dict | None:
    """The stored verdict for this summary, if it was judged as it stands now."""
    if not s or not s.get("summary"):
        return None
    v = s.get("judge")
    if v and v.get("key") == judge_key(summarize.source(item), s["summary"]):
        return v
    return None


async def judge_all(items: list[Item], model: str = "sonnet", concurrency: int = 2,
                    limit: int | None = None, log=print) -> list[dict]:
    todo, seen = [], set()
    for it in items:
        if it.file in seen or not summarize.needs_summary(it):
            continue
        s = summarize.cached(it)
        if s and s["verified"] and s["summary"] and not verdict(it, s):
            seen.add(it.file)
            todo.append(it)
    todo = todo[:limit] if limit else todo
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    sem = asyncio.Semaphore(concurrency)
    done = []

    async def run(b):
        async with sem:
            pairs = {it.file: {"id": it.file, "source": summarize.source(it),
                               "summary": summarize.cached(it)["summary"]} for it in b}
            try:
                got = await judge(list(pairs.values()), model)
            except Exception as e:  # noqa: BLE001 - one bad batch shouldn't stop the run
                log(f"batch {b[0].file}..: {e}")
                return
            for it in b:
                v = got.get(it.file)
                if v is None:
                    continue
                p = summarize.CACHE / f"{it.file}.json"
                d = json.loads(p.read_text(encoding="utf-8"))
                d["judge"] = {"key": judge_key(pairs[it.file]["source"], pairs[it.file]["summary"]),
                              "model": model, "faithful": bool(v["faithful"]),
                              "problem": v.get("problem") or "", "cost_usd": round(v["cost"], 4)}
                tmp = p.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
                tmp.replace(p)
                done.append(d)
            log(f"{len(done)}/{len(todo)} judged ({sum(not d['judge']['faithful'] for d in done)} flagged so far)")

    await asyncio.gather(*(run(b) for b in batches))
    return done
