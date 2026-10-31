from collectors.cricdata_source import _extract_match_ref

def test_extract_current_espn_series_match_link():
    ref = _extract_match_ref(
        "/series/india-in-south-africa-2023-24-1387592/south-africa-vs-india-1st-odi-1387599/full-scorecard"
    )
    assert ref["match_id"] == "1387599"
    assert ref["series_slug"] == "india-in-south-africa-2023-24-1387592"
    assert ref["match_slug"] == "south-africa-vs-india-1st-odi-1387599"

def test_extract_legacy_match_link():
    ref = _extract_match_ref("/ci/engine/match/123456.html")
    assert ref["match_id"] == "123456"

def test_ignore_non_match_links():
    assert _extract_match_ref("/cricketers/some-player-123") is None
