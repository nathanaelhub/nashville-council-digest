"""council-digest fetch | locate | summarize | build"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from . import geo, legistar, summarize
from .records import meetings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="council-digest", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download council meetings from Legistar")
    f.add_argument("--since", default="2026-07-01")
    f.add_argument("--until", default=time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400)))
    f.add_argument("--refresh", action="store_true", help="re-download matters already saved")
    sub.add_parser("locate", help="find council districts for each item")
    s = sub.add_parser("summarize", help="write and check plain-language summaries with Claude")
    s.add_argument("--model", default="sonnet")
    s.add_argument("--concurrency", type=int, default=2)
    s.add_argument("--limit", type=int)
    b = sub.add_parser("build", help="build the static site into _site/")
    b.add_argument("--out", default="_site")
    a = p.parse_args(argv)

    if a.cmd == "fetch":
        for m in legistar.council_meetings(a.since, a.until):
            path = legistar.fetch_meeting(m, refresh=a.refresh)
            print(m["EventDate"][:10], path.name, flush=True)
    elif a.cmd == "locate":
        geo.locate_all([i for m in meetings() for i in m.items if summarize.needs_summary(i)])
    elif a.cmd == "summarize":
        items = [i for m in meetings() for i in m.items]
        done = asyncio.run(summarize.summarize_all(items, a.model, a.concurrency, a.limit,
                                                   log=lambda s: print(s, flush=True)))
        print(f"{len(done)} summarized, {sum(not d['verified'] for d in done)} unverified")
    elif a.cmd == "build":
        from .site import build
        print(build(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
