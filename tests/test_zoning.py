import json

from council_digest import zoning
from council_digest.zoning import codes_in, explain


def test_every_definition_is_quoted_from_its_source():
    g = zoning.glossary()
    for d in g["districts"] + g["suffixes"]:
        text = zoning.norm(zoning.source_text(d["file"]))
        assert zoning.norm(d["quote"]) in text, d["code"]
        assert zoning.norm(d["name"]) in text, d["code"]
        assert d["source"].startswith("https://www.nashville.gov/")
        assert d["source"].rsplit("/", 1)[1].removesuffix(".pdf") == d["file"].removesuffix(".txt.gz"), d["code"]


def test_codes_are_explained_by_base_and_suffixes():
    assert [x["code"] for x in explain("RM20-A-NS")] == ["RM20-A", "-NS"]
    assert [x["code"] for x in explain("RS5")] == ["RS5"]
    assert [x["code"] for x in explain("R6-A")] == ["R6-A", "-A"]
    assert [x["code"] for x in explain("MUN-A-NS")] == ["MUN-A", "-NS"]
    assert [x["code"] for x in explain("RM15-A-NS")] == ["RM15", "-A", "-NS"]
    assert [x["code"] for x in explain("RM40")] == []  # no cited definition
    assert explain("DTC") == []


def test_codes_in_finds_codes_not_file_numbers():
    text = "Rezones 0.74 acres from RS5 to RM20-A-NS (BL2026-1593, RS2026-2330), and from AR2A to SP."
    assert codes_in(text) == ["RS5", "RM20-A-NS", "AR2a", "SP"]
    assert codes_in("Approves a grant of $20,000 to the R. Smith Center.") == []


def test_every_base_district_in_a_summary_is_defined():
    seen = set()
    for f in (zoning.ROOT / "data" / "summaries").glob("*.json"):
        s = json.loads(f.read_text(encoding="utf-8"))["summary"] or ""
        seen |= {m.group(1).replace("AR2A", "AR2a") for m in zoning.CODE.finditer(s)}
    seen -= {"R", "RS", "RM"}  # an initial, or a family named in prose ("RS and RM districts")
    gaps = {c for c in seen if not any(x["code"][0] != "-" for x in explain(c))}
    assert gaps == set()
