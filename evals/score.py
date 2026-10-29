"""Score an eval run: who caught which planted errors, and what the judge flagged in originals.

    uv run python evals/score.py evals/results/<date>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

KINDS = ["money", "number", "name", "swap", "negate"]


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def main() -> None:
    out = Path(sys.argv[1])
    cases = json.loads((out / "cases.json").read_text(encoding="utf-8"))
    lines = ["| planted error | n | checker caught | judge caught | either caught |", "|---|---|---|---|---|"]
    for k in KINDS:
        cs = [c for c in cases if c["kind"] == k and c["judge_faithful"] is not None]
        ck = sum(bool(c["checker_flags"]) for c in cs)
        jk = sum(c["judge_faithful"] is False for c in cs)
        ek = sum(bool(c["checker_flags"]) or c["judge_faithful"] is False for c in cs)
        lines.append(f"| {k} | {len(cs)} | {pct(ck, len(cs))} | {pct(jk, len(cs))} | {pct(ek, len(cs))} |")
    orig = [c for c in cases if c["kind"] == "original" and c["judge_faithful"] is not None]
    flagged = [c for c in orig if c["judge_faithful"] is False]
    lines += ["", f"Originals: {len(orig)}; checker flags {sum(bool(c['checker_flags']) for c in orig)}, "
                  f"judge flags {len(flagged)}."]
    missing = sum(c["judge_faithful"] is None for c in cases)
    if missing:
        lines.append(f"{missing} cases have no judge verdict (failed batches).")
    cost = sum(c["judge_cost"] or 0 for c in cases)
    lines.append(f"Judge cost: ${cost:.2f} for {len(cases) - missing} verdicts.")
    report = "\n".join(lines)
    print(report)
    (out / "scores.md").write_text(report + "\n", encoding="utf-8")
    (out / "flagged_originals.json").write_text(json.dumps(
        [{"file": c["file"], "summary": c["summary"], "problem": c["judge_problem"]} for c in flagged],
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
