import asyncio
import json

from council_digest import judge, site, summarize
from council_digest.records import Item


def item():
    return Item(file="RS2026-1", matter_id=1, kind="Resolution", title="A resolution approving a grant.", section="",
                outcome="passed", outcome_text="Adopted", actions=[], sponsors=["Jane Doe"], districts=[],
                text="..title x ..body Grants $5 to A.", url="https://example.org")


def test_verdict_only_counts_for_the_summary_and_text_it_judged():
    it = item()
    s = {"summary": "Gives $5 to A."}
    k = judge.judge_key(summarize.source(it), s["summary"])
    assert judge.verdict(it, s | {"judge": {"key": k, "faithful": False}}) == {"key": k, "faithful": False}
    assert judge.verdict(it, {"summary": "Gives $5 to B.", "judge": {"key": k, "faithful": False}}) is None
    assert judge.verdict(it, s) is None


def test_changing_the_rule_means_judging_again(monkeypatch):
    it = item()
    s = {"summary": "Gives $5 to A."}
    k = judge.judge_key(summarize.source(it), s["summary"])
    monkeypatch.setattr(judge, "SYSTEM", judge.SYSTEM + " A new clause.")
    assert judge.verdict(it, s | {"judge": {"key": k, "faithful": True}}) is None


def test_rule_counts_meaning_changing_omissions():
    assert "a condition, limit or exception" in judge.SYSTEM


def test_batched_flag_is_replaced_by_the_verdict_judged_alone(tmp_path, monkeypatch):
    it = item()
    monkeypatch.setattr(summarize, "CACHE", tmp_path)
    src = summarize.source(it)
    flagged = {"key": judge.judge_key(src, "Gives $5 to A."), "faithful": False, "problem": "on re-check, faithful"}
    (tmp_path / "RS2026-1.json").write_text(json.dumps({"summary": "Gives $5 to A.", "source_hash": summarize.key(it), "judge": flagged}))
    calls = []

    async def fake(pairs, model):
        calls.append(len(pairs))
        return {p["id"]: {"faithful": True, "cost": 0.01} for p in pairs}

    monkeypatch.setattr(judge, "judge", fake)
    asyncio.run(judge.confirm_flagged([it], log=lambda s: None))
    d = json.loads((tmp_path / "RS2026-1.json").read_text())
    assert calls == [1] and d["judge"]["faithful"] and d["judge"]["alone"]
    asyncio.run(judge.confirm_flagged([it], log=lambda s: None))
    assert calls == [1]


def test_hand_hold_applies_only_to_the_summary_it_names(monkeypatch):
    it = item()
    monkeypatch.setattr(site, "held", lambda: {"RS2026-1": {"summary": "Gives $5 to A.", "reason": "x"}})
    assert site.shown_summary(it, {"summary": "Gives $5 to A.", "verified": True}) == (False, True)
    assert site.shown_summary(it, {"summary": "Grants $5 to A.", "verified": True}) == (True, False)
