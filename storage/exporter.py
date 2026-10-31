"""CSV and ZIP export helpers."""
from io import BytesIO
import zipfile
import pandas as pd
from storage.database import load_dataset, load_coverage

DATASETS = [
    "career_batting", "career_bowling", "career_fielding", "career_allround",
    "match_list_batting", "match_list_bowling", "match_list_fielding", "match_list_allround",
    "match_history", "innings_batting", "innings_bowling", "innings_fielding", "innings_allround",
    "series_batting", "series_bowling", "grounds_batting", "grounds_bowling",
    "series_details", "series_match_lists", "team_career", "team_matches",
    "deliveries", "scorecards",
]

def export_player_zip(player_id, formats):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fmt in formats:
            for dataset in DATASETS:
                rows = load_dataset(player_id, fmt, dataset)
                if rows:
                    zf.writestr(f"{fmt}/{dataset}.csv", pd.DataFrame(rows).to_csv(index=False))
            coverage = load_coverage(player_id, fmt)
            if coverage:
                zf.writestr(f"{fmt}/coverage.csv", pd.DataFrame(coverage).to_csv(index=False))
        team_profile = load_dataset(player_id, "team", "team_profile")
        if team_profile:
            zf.writestr("team/team_profile.csv", pd.DataFrame(team_profile).to_csv(index=False))
    buffer.seek(0)
    return buffer.getvalue()
