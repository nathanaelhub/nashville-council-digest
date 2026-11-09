"""The address lookup on the home page (site/lookup.js), run under Node when it's installed.

The parcel layer itself isn't called here: these check the parsing, the query
it builds, and that one address in two parts of the county stays two answers.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

LOOKUP = Path(__file__).resolve().parents[1] / "site" / "lookup.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node not installed")


def js(expr: str):
    code = f"const m = require({json.dumps(str(LOOKUP))}); console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)


def test_parse_normalizes_street_type_direction_and_zip():
    assert js('m.parse("1 Public Square, Nashville TN 37201")') == {"house": "1", "street": "PUBLIC%SQ", "zip": "37201"}
    assert js('m.parse("1600 Charlotte Avenue North")') == {"house": "1600", "street": "CHARLOTTE%AVE%N", "zip": ""}
    # "West" opening a street name is part of the name, not a direction
    assert js('m.parse("2525 West End Ave")')["street"] == "WEST%END%AVE"
    assert js('m.parse("Main Street")') is None


def test_quotes_in_street_names_cannot_break_the_query():
    p = js('m.parse("700 O\'Brien Ave")')
    assert "'" not in p["street"]
    p = json.dumps({"house": "1", "street": "A''B", "zip": ""})
    w = js(f'm.where({p}, "x")')
    assert w.count("'") % 2 == 0


def test_where_matches_the_street_exactly_or_with_a_direction_and_uses_the_zip():
    w = js('m.where({house: "5", street: "MAIN%ST", zip: "37213"}, "PropHouse = \'5\'")')
    # MAIN%ST without a trailing wildcard, so MAINSTREAM DR doesn't match
    assert "PropStreet LIKE 'MAIN%ST' OR PropStreet LIKE 'MAIN%ST %'" in w
    assert "PropZip = '37213'" in w


def test_one_address_in_two_places_stays_two_answers():
    rows = [
        {"Council": "05", "PropAddr": "100 MAIN ST", "PropCity": "NASHVILLE", "PropZip": "37206"},
        {"Council": "05", "PropAddr": "100 MAIN ST", "PropCity": "NASHVILLE", "PropZip": "37206"},
        {"Council": "11", "PropAddr": "100 MAIN ST", "PropCity": "OLD HICKORY", "PropZip": "37138"},
    ]
    got = js(f"m.places({json.dumps(rows)})")
    assert [(p["district"], p["zip"]) for p in got] == [(5, "37206"), (11, "37138")]
