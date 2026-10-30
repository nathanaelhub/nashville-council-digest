from council_digest import judge, summarize
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
