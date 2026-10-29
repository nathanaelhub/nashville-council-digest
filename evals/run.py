"""How well do the fact checker and a Claude judge catch errors in summaries?

1. Sample verified summaries (seeded).
2. Plant one known error in a copy of each, of five kinds:
   money    a dollar amount changed            (checker should catch)
   number   another number changed             (checker should catch)
   name     a name swapped for one not in the text (checker should catch)
   swap     two names from the text swapped    (meaning: checker can't)
   negate   the opening verb reversed          (meaning: checker can't)
3. Run the checker on every original and mutant.
4. Ask Claude, as a judge, whether each summary is faithful to its text.
   Originals and mutants are shuffled together under opaque ids, several per
   call, so the judge can't tell which are planted.

Judge flags on *originals* are an audit of the published summaries; they're
written to results for review, not counted as judge errors.

    COUNCIL_DIGEST_USE_LOGIN=1 uv run python evals/run.py --n 80 --out evals/results/<date>
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from council_digest import summarize  # noqa: E402
from council_digest.records import meetings  # noqa: E402
from council_digest.verify import DISTRICT, MONEY, NAME, NUMBER, SENTENCE_START, check  # noqa: E402

NEGATE = {
    "Approves": "Rejects", "Accepts": "Turns down", "Allows": "Bans", "Adds": "Removes",
    "Authorizes": "Forbids", "Gives": "Takes back", "Creates": "Abolishes", "Requires": "Stops requiring",
    "Appropriates": "Cuts", "Extends": "Ends", "Increases": "Reduces", "Exempts": "Denies",
    "Sets": "Removes", "Expands": "Shrinks", "Grants": "Denies",
}
JUDGE = """You check plain-language summaries of Nashville Metro Council legislation against the official text.

For each pair, decide whether the summary is faithful: everything it says is supported by the text,
nothing is reversed or attached to the wrong party, place or amount. Leaving details out is fine;
saying something the text doesn't support, or the opposite of what it says, is not.

Reply with only JSON: {"verdicts": [{"id": "...", "faithful": true|false, "problem": "... or empty"}]}"""


def names_in(summary: str) -> list[str]:
    out = []
    for m in NAME.finditer(summary):
        words = m.group().split()
        if SENTENCE_START.search(summary[:m.start()]):
            words = words[1:]
        if len(words) >= 2:
            out.append(" ".join(words).rstrip("."))
    return out


def mutate(kind: str, s: str, src: str, rng: random.Random, other_names: list[str]) -> str | None:
    if kind == "money":
        m = MONEY.search(s)
        if not m:
            return None
        n = float(m.group(1).replace(",", ""))
        new = f"{n * 3:,.0f}" if n * 3 >= 1000 or n == int(n) else f"{n * 3:,.2f}"
        return s[:m.start(1)] + new + s[m.end(1):]
    if kind == "number":
        rest = MONEY.sub(lambda x: "#" * len(x.group()), s)
        rest = DISTRICT.sub(lambda x: "#" * len(x.group()), rest)
        for m in NUMBER.finditer(rest):
            v = m.group(1).replace(",", "")
            if v.isdigit() and not (1900 <= int(v) <= 2100):
                return s[:m.start(1)] + str(int(v) * 2 + 3) + s[m.end(1):]
        return None
    if kind == "district":
        m = re.search(r"\bDistrict (\d{1,2})\b", s)
        if not m:
            return None
        return s[:m.start(1)] + str((int(m.group(1)) + 6) % 35 + 1) + s[m.end(1):]
    if kind == "name":
        mine = [n for n in names_in(s)]
        cands = [n for n in other_names if n.lower() not in src.lower()]
        if not mine or not cands:
            return None
        return s.replace(mine[0], rng.choice(cands), 1)
    if kind == "swap":
        mine = list(dict.fromkeys(n for n in names_in(s)))
        if len(mine) < 2:
            return None
        a, b = mine[0], mine[1]
        if a in b or b in a:
            return None
        return s.replace(a, "\0").replace(b, a).replace("\0", b)
    if kind == "negate":
        first = s.split()[0] if s.split() else ""
        if first in NEGATE:
            return NEGATE[first] + s[len(first):]
        return None
    raise ValueError(kind)


KINDS = ["money", "number", "name", "swap", "negate"]


async def judge(pairs: list[dict], model: str) -> dict[str, dict]:
    prompt = "Check each pair.\n\n" + "\n\n".join(
        f"=== id {p['id']}\nOFFICIAL TEXT:\n{p['source']}\n\nSUMMARY:\n{p['summary']}" for p in pairs)
    old = summarize.SYSTEM
    summarize.SYSTEM = JUDGE
    try:
        reply, cost = await summarize.claude(prompt, model, timeout=600)
    finally:
        summarize.SYSTEM = old
    start = reply.find("{")
    obj, _ = json.JSONDecoder().raw_decode(reply[start:])
    return {str(v["id"]): v | {"cost": cost / len(pairs)} for v in obj["verdicts"]}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rng = random.Random(a.seed)

    items = {}
    for m in meetings():
        for i in m.items:
            s = summarize.cached(i) if summarize.needs_summary(i) else None
            if s and s["verified"] and s["summary"]:
                items[i.file] = (i, s)
    files = sorted(items)
    sample = rng.sample(files, min(a.n, len(files)))
    all_names = sorted({n for f in files for n in names_in(items[f][1]["summary"])})

    cases = []
    for f in sample:
        it, s = items[f]
        src = summarize.source(it)
        cases.append({"file": f, "kind": "original", "summary": s["summary"], "source": src})
        for kind in KINDS:
            mut = mutate(kind, s["summary"], src, rng, all_names)
            if mut and mut != s["summary"]:
                cases.append({"file": f, "kind": kind, "summary": mut, "source": src})
    for c in cases:
        c["id"] = hashlib.sha256(f"{c['file']}|{c['kind']}|{c['summary']}".encode()).hexdigest()[:8]
        c["checker_flags"] = [str(p) for p in check(c["summary"], c["source"])]

    order = cases[:]
    rng.shuffle(order)
    batches = [order[i:i + a.batch] for i in range(0, len(order), a.batch)]
    sem = asyncio.Semaphore(2)
    verdicts: dict[str, dict] = {}

    async def run(b):
        async with sem:
            for attempt in range(2):
                try:
                    verdicts.update(await judge(b, a.model))
                    print(f"judged {len(verdicts)}/{len(cases)}", flush=True)
                    return
                except Exception as e:  # noqa: BLE001
                    print(f"judge batch failed ({e}); {'retrying' if attempt == 0 else 'giving up'}", flush=True)

    await asyncio.gather(*(run(b) for b in batches))
    for c in cases:
        v = verdicts.get(c["id"])
        c["judge_faithful"] = None if v is None else bool(v["faithful"])
        c["judge_problem"] = None if v is None else v.get("problem", "")
        c["judge_cost"] = None if v is None else v["cost"]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {out}")


if __name__ == "__main__":
    asyncio.run(main())
