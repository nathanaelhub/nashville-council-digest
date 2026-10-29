import json

from council_digest.records import districts, load, outcome


def test_last_recorded_action_decides():
    assert outcome(["substituted", "passed on third reading"])[0] == "passed"
    assert outcome(["passed on first reading"]) == ("advanced", "Passed first reading; two more votes to go")
    assert outcome(["deferred"])[0] == "deferred"
    assert outcome([])[0] == "none"


def test_unknown_action_is_shown_not_guessed():
    assert outcome(["tabled"]) == ("none", "Tabled")


def test_districts_in_text_stay_in_range():
    assert districts("in Council District 19 and District 5") == [5, 19]
    assert districts("District 40") == []


def write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_load_ignores_the_passed_flag(tmp_path):
    """RS2026-2330 on 2026-10-20: Legistar's flag says Fail, the action says adopted."""
    (tmp_path / "matters").mkdir()
    write(tmp_path / "event.json", {"EventId": 1, "EventDate": "2026-10-20T00:00:00",
                                    "EventInSiteURL": "u", "EventAgendaFile": "a", "EventMinutesFile": None})
    write(tmp_path / "items.json", [
        {"EventItemAgendaSequence": 1, "EventItemTitle": "Resolutions", "EventItemMatterId": None},
        {"EventItemAgendaSequence": 2, "EventItemMatterId": 7, "EventItemActionName": "adopted",
         "EventItemPassedFlagName": "Fail"},
    ])
    write(tmp_path / "matters" / "7.json", {
        "matter": {"MatterFile": "RS2026-2330", "MatterTypeName": "Resolution", "MatterGuid": "G",
                   "MatterTitle": "A resolution approving a power purchase agreement."},
        "text": "..title\nA resolution\n..body\nWHEREAS", "histories": [],
        "sponsors": [{"MatterSponsorName": "B", "MatterSponsorSequence": 2},
                     {"MatterSponsorName": "A", "MatterSponsorSequence": 1}],
        "attachments": []})
    m = load(tmp_path)
    (item,) = m.items
    assert (item.outcome, item.section, item.sponsors) == ("passed", "Resolutions", ["A", "B"])
    assert item.url.endswith("ID=7&GUID=G")
