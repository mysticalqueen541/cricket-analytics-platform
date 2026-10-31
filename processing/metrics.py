"""Analysis helpers for Statsguru rows and normalized delivery records."""
import pandas as pd

def numeric_column(df, candidates):
    for name in candidates:
        if name in df.columns:
            return pd.to_numeric(df[name].astype(str).str.replace(",", "", regex=False), errors="coerce")
    return pd.Series([pd.NA] * len(df), index=df.index, dtype="Float64")

def batting_metrics(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    runs = numeric_column(df, ["Runs", "R", "runs"])
    balls = numeric_column(df, ["BF", "Balls", "B", "balls"])
    df["runs_numeric"] = runs
    df["balls_numeric"] = balls
    df["strike_rate_calculated"] = (runs / balls.where(balls.ne(0))) * 100
    return df

def coverage_metrics(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return {"matches": 0, "scorecards": 0, "deliveries": 0, "failed": 0, "unresolved": 0}
    return {
        "matches": len(df),
        "scorecards": int(df["scorecard_status"].isin(["complete", "partial"]).sum()),
        "deliveries": int(df["delivery_status"].eq("complete").sum()),
        "failed": int(df["delivery_status"].eq("failed").sum()),
        "unresolved": int(df["match_id"].isna().sum()) if "match_id" in df else 0,
    }

def odi_phase(over_number):
    try:
        over = int(over_number) + 1
    except (TypeError, ValueError):
        return "Unknown"
    if over <= 10:
        return "1–10"
    if over <= 40:
        return "11–40"
    return "41–50"
