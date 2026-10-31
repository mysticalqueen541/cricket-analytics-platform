from pathlib import Path

APP_NAME = "Cricket Analytics Platform"
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "cricket_analytics.sqlite3"

FORMATS = {"ODI": "ODI", "Test": "Test", "T20I": "T20I"}
REQUEST_TIMEOUT = 25
REQUEST_DELAY_SECONDS = 1.5
MAX_CONCURRENT_REQUESTS = 2
USER_AGENT = "Mozilla/5.0 (compatible; CricketAnalyticsPlatform/1.0; public research)"
