"""The built site keeps its promises, checked against the committed data."""

import html
import re

import pytest

from council_digest import judge, summarize
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
        f = re.search(r'class="file"[^>]*>(.*?)</', c).group(1)
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
            v = judge.verdict(item, s)
            if s and s["verified"] and s["summary"] and not (v and not v["faithful"]):
                assert text == s["summary"] and not check(text, summarize.source(item))
            else:
                assert text == item.title


def test_links_are_https(site):
    for p in site.rglob("*.html"):
        for href in re.findall(r'href="([^"]+)"', p.read_text(encoding="utf-8")):
            assert href.startswith("https://") or not re.match(r"\w+:", href), (p.name, href)


def test_zoning_terms_appear_on_cards_that_use_codes(site):
    from council_digest.zoning import codes_in
    n = 0
    for p in (site / "meeting").glob("*.html"):
        for card in cards(p).values():
            text = html.unescape(re.search(r'<p class="summary">(.*?)</p>', card, re.S).group(1))
            assert ('class="terms"' in card) == bool(codes_in(text))
            n += bool(codes_in(text))
    assert n > 50
    assert "No Short-Term Rental" in (site / "zoning.html").read_text(encoding="utf-8")


def test_every_bill_page_lists_every_reading(site):
    history = {}
    for m in MEETINGS:
        for i in m.items:
            if summarize.needs_summary(i):
                history.setdefault(i.file, []).append(m.date)
    assert {p.stem for p in (site / "bill").glob("*.html")} == set(history)
    multi = [f for f, dates in history.items() if len(dates) >= 3]
    assert multi, "expected some bills with three readings"
    for f in multi[:20]:
        page = (site / "bill" / f"{f}.html").read_text(encoding="utf-8")
        rows = re.findall(r'<li><a href="../meeting/(\d{4}-\d{2}-\d{2}).html">', page)
        assert rows == history[f], f


def test_card_links_to_bill_pages_resolve(site):
    for path in list((site / "meeting").glob("*.html"))[:5] + list((site / "district").glob("*.html"))[:5]:
        for href in re.findall(r'<a class="file" href="([^"]+)"', path.read_text(encoding="utf-8")):
            assert (path.parent / href).resolve().exists(), href


def test_feeds_are_valid_atom_and_follow_the_card_rules(site):
    import xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = {i.file: i for m in MEETINGS for i in m.items}
    feeds = [site / "feed.xml"] + sorted((site / "district").glob("*.xml"))
    assert len(feeds) == 36
    total = 0
    for feed in feeds:
        root = ET.parse(feed).getroot()
        entries = root.findall("a:entry", ns)
        total += len(entries)
        dates = [e.find("a:updated", ns).text for e in entries]
        assert dates == sorted(dates, reverse=True), feed.name
        for entry in entries:
            href = entry.find("a:link", ns).get("href")
            f = href.rsplit("/", 1)[1].removesuffix(".html")
            assert (site / "bill" / f"{f}.html").exists()
            item = items[f]
            s = summarize.cached(item) if summarize.needs_summary(item) else None
            v = judge.verdict(item, s)
            text = entry.find("a:summary", ns).text
            if s and s["verified"] and s["summary"] and not (v and not v["faithful"]):
                assert text == s["summary"]
            else:
                assert text == item.title
    assert total > 100
