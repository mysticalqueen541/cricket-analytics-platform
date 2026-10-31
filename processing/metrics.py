import pandas as pd

def batting_summary(batting: pd.DataFrame):
    if batting.empty: return pd.DataFrame()
    df=batting.copy()
    for c in ["runs","balls","fours","sixes","batting_position"]:
        if c in df: df[c]=pd.to_numeric(df[c],errors="coerce")
    if "runs" in df and "balls" in df:
        df["strike_rate"]=(df["runs"]/df["balls"].replace(0,pd.NA))*100
    return df

def coverage_summary(matches: pd.DataFrame):
    if matches.empty: return {"matches":0,"scorecards":0,"deliveries":0,"failed":0}
    return {
      "matches":len(matches),
      "scorecards":int(matches.get("scorecard_status",pd.Series(dtype=str)).isin(["complete","partial"]).sum()),
      "deliveries":int(matches.get("delivery_status",pd.Series(dtype=str)).eq("complete").sum()),
      "failed":int(matches.get("delivery_status",pd.Series(dtype=str)).eq("failed").sum())
    }

def odi_phase(over_number):
    if pd.isna(over_number): return "Unknown"
    o=int(over_number)+1
    return "1–10" if o<=10 else ("11–40" if o<=40 else "41–50")
