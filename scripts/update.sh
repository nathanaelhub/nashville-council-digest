#!/usr/bin/env bash
# Bring the digest up to date after a council meeting, and commit the new data.
#
#   scripts/update.sh [--since YYYY-MM-DD] [--push]
#
# Re-fetches meetings since --since (default: 21 days ago), so minutes and actions
# Legistar fills in after a meeting are picked up; then locates, summarizes and
# judges anything new, runs the tests, and commits data/ if it changed. Any failing
# step stops the run, so nothing is committed unless the tests pass. Summaries and
# the judge use your Claude login (the claude CLI), so this runs on your machine,
# not in CI.
set -euo pipefail
cd "$(dirname "$0")/.."

since="" push=0
while [ $# -gt 0 ]; do
  case $1 in
    --since) since=$2; shift 2 ;;
    --push) push=1; shift ;;
    *) echo "usage: scripts/update.sh [--since YYYY-MM-DD] [--push]" >&2; exit 2 ;;
  esac
done
[ -n "$since" ] || since=$(uv run python -c "import datetime as d; print(d.date.today() - d.timedelta(days=21))")

export COUNCIL_DIGEST_USE_LOGIN=1
uv run council-digest fetch --since "$since" --refresh
uv run council-digest locate
uv run council-digest summarize
uv run council-digest judge
uv run pytest -q

git add data
if git diff --cached --quiet; then
  echo "No changes since the last update."
  exit 0
fi
latest=$(uv run python -c "from council_digest.records import meetings; print(max(m.date[:10] for m in meetings()))")
git commit -q -m "Update council data through the $latest meeting"
git log --oneline -1
if [ "$push" = 1 ]; then
  git push -q
  echo "Pushed. GitHub Pages rebuilds once the tests pass there too."
else
  echo "Committed, not pushed. Run 'git push' to publish."
fi
