from council_digest.verify import check, district_numbers

SOURCE = ("A resolution authorizing grants not exceeding $6,000,000 from the Barnes Fund for "
          "Affordable Housing to Urban Housing Solutions and Habitat for Humanity for 120 units "
          "in Council District 5 and Council District 19, at 1319 6th Avenue North. "
          "Sponsors: Delishia Porterfield. See RS2024-882.")


def kinds(summary):
    return [p.kind for p in check(summary, SOURCE)]


def test_faithful_summary_passes():
    assert check("Gives up to $6 million from the Barnes Fund to Habitat for Humanity and Urban "
                 "Housing Solutions for 120 homes in Districts 5 and 19.", SOURCE) == []


def test_money_compared_as_numbers():
    assert kinds("Gives $6,000,000.") == []
    assert kinds("Gives $6.0 million.") == []
    assert kinds("Gives $5 million.") == ["money"]
    assert kinds("Gives $600,000.") == ["money"]


def test_wrong_number_district_file_and_name():
    assert kinds("Pays for 210 homes.") == ["number"]
    assert kinds("Covers District 7.") == ["district"]
    assert kinds("Covers Districts 5 and 7.") == ["district"]
    assert kinds("Amends RS2024-883.") == ["file"]
    assert kinds("Sends the money to Catholic Charities.") == ["name"]


def test_names_from_the_source_and_common_words_pass():
    assert kinds("Metro Council approves money for Habitat for Humanity on 6th Avenue North.") == []
    assert kinds("Sponsored by Delishia Porterfield.") == []


def test_district_list_parsing():
    assert district_numbers("Districts 2, 5 and 19") == {2, 5, 19}
    assert district_numbers("Council District 7") == {7}
