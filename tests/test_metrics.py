import pandas as pd
from processing.metrics import batting_summary, coverage_summary, odi_phase

def test_strike_rate():
    out=batting_summary(pd.DataFrame([{"runs":50,"balls":40}]))
    assert round(out.iloc[0]["strike_rate"],2)==125.00

def test_coverage():
    out=coverage_summary(pd.DataFrame([
      {"scorecard_status":"complete","delivery_status":"complete"},
      {"scorecard_status":"pending","delivery_status":"failed"}]))
    assert out["matches"]==2 and out["deliveries"]==1 and out["failed"]==1

def test_odi_phase():
    assert odi_phase(0)=="1–10"
    assert odi_phase(10)=="11–40"
    assert odi_phase(40)=="41–50"
