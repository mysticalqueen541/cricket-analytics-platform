from pathlib import Path

APP_NAME = "Cricket Analytics Platform"
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "cricket_analytics.sqlite3"

FORMATS = {
    "ODI": "odi",
    "Test": "test",
    "T20I": "t20i",
}
FORMAT_CLASS = {"test": 1, "odi": 2, "t20i": 3}
STAT_TYPES = ("allround", "batting", "bowling", "fielding")
REQUEST_TIMEOUT = 35
REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "Mozilla/5.0 (compatible; CricketAnalyticsPlatform/1.0; public data research)"
