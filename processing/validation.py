"""Sanity checks; these flag discrepancies rather than altering source data."""
import pandas as pd

def validate_deliveries(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return {"row_count": 0, "duplicate_sequences": 0, "missing_batter": 0, "warnings": ["No delivery rows returned."]}
    warnings = []
    duplicate_sequences = 0
    keys = [c for c in ("match_id", "innings", "sequence") if c in df.columns]
    if len(keys) == 3:
        duplicate_sequences = int(df.duplicated(keys).sum())
        if duplicate_sequences:
            warnings.append(f"{duplicate_sequences} duplicate delivery sequence keys.")
    missing_batter = int(df["batter"].isna().sum()) if "batter" in df else len(df)
    if missing_batter:
        warnings.append(f"{missing_batter} delivery rows have no batter name.")
    return {
        "row_count": len(df),
        "duplicate_sequences": duplicate_sequences,
        "missing_batter": missing_batter,
        "warnings": warnings,
    }
