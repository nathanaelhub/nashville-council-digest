from council_digest.geo import addresses, parcel_ids


def test_parcel_ids_match_metro_stanpar():
    t = "being Property Parcel No. 086 as designated on Map 069-16 of the Official Property Identification Maps"
    assert parcel_ids(t) == ["06916008600"]


def test_parcel_ranges_and_lists():
    t = "being Property Parcel Nos. 094-097 and 120 as designated on Map 082-08, and"
    assert parcel_ids(t) == ["08208009400", "08208009500", "08208009600", "08208009700", "08208012000"]


def test_condo_maps_are_skipped_not_misread():
    assert parcel_ids("Parcel Nos. 609, 611 as designated on Map 082-08-0-E of the") == []


def test_addresses():
    assert addresses("an aerial encroachment at 501 Houston Street. (Proposal") == [("501", "HOUSTON%ST")]
    assert addresses("located at 1319 6th Avenue North from the") == [("1319", "6TH%AVE%N")]
    assert addresses("property located at 1616 Ashton Ave, approximately") == [("1616", "ASHTON%AVE")]


def test_address_lists():
    assert addresses("properties located at 532 and 538 Bell Road, approximately") == [
        ("532", "BELL%RD"), ("538", "BELL%RD")]
    assert addresses("located at 5601, 5621 Cane Ridge Road, Cane") == [
        ("5601", "CANE%RIDGE%RD"), ("5621", "CANE%RIDGE%RD")]
