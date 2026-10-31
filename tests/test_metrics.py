import pandas as pd
from processing.metrics import batting_metrics, coverage_metrics, odi_phase
from processing.validation import validate_deliveries

def test_batting_strike_rate():
    df = batting_metrics([{"Runs": "50", "BF": "40"}])
    assert round(float(df.iloc[0]["strike_rate_calculated"]), 2) == 125.0

def test_coverage_counts():
    rows = [
        {"scorecard_status":"complete","delivery_status":"complete","match_id":"1"},
        {"scorecard_status":"pending","delivery_status":"failed","match_id":"2"},
    ]
    result = coverage_metrics(rows)
    assert result["matches"] == 2
    assert result["deliveries"] == 1
    assert result["failed"] == 1

def test_odi_phases():
    assert odi_phase(0) == "1–10"
    assert odi_phase(10) == "11–40"
    assert odi_phase(40) == "41–50"

def test_duplicate_delivery_detection():
    rows = [{"match_id":"1","innings":1,"sequence":1,"batter":"A"},
            {"match_id":"1","innings":1,"sequence":1,"batter":"A"}]
    assert validate_deliveries(rows)["duplicate_sequences"] == 1
