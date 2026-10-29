"""The built site keeps its promises, checked against the committed data."""

import html
import re

import pytest

from council_digest import summarize
from council_digest.records import meetings
from council_digest.site import BADGE, build
from council_digest.verify import check

MEETINGS = meetings()
pytestmark = pytest.mark.skipif(not MEETINGS, reason="no cached meetings in data/raw")
CARD = re.compile(r'<article class="card item".*?</article>', re.S)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    return build(tmp_path_factory.mktemp("site") / "_site")


def cards(path):
    out = {}
    for c in CARD.findall(path.read_text(encoding="utf-8")):
        f = re.search(r'<span class="file">(.*?)</span>', c).group(1)
        out[html.unescape(f)] = c
    return out


def test_every_meeting_and_district_page_exists(site):
    assert {p.stem for p in (site / "meeting").glob("*.html")} == {m.date for m in MEETINGS}
    assert len(list((site / "district").glob("*.html"))) == 35


def test_shown_summaries_passed_the_check_and_badges_match_outcomes(site):
    for m in MEETINGS:
        shown = cards(site / "meeting" / f"{m.date}.html")
        for item in m.items:
            if item.kind == "Appointment":
                continue
            card = shown[item.file]
            assert f'>{BADGE[item.outcome]}</span>' in card
            text = html.unescape(re.search(r'<p class="summary">(.*?)</p>', card, re.S).group(1))
            s = summarize.cached(item) if summarize.needs_summary(item) else None
            if s and s["verified"] and s["summary"]:
                assert text == s["summary"] and not check(text, summarize.source(item))
            else:
                assert text == item.title


def test_links_are_https(site):
    for p in site.rglob("*.html"):
        for href in re.findall(r'href="([^"]+)"', p.read_text(encoding="utf-8")):
            assert href.startswith("https://") or not re.match(r"\w+:", href), (p.name, href)
