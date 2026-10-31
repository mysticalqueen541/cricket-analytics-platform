"""Local SQLite persistence for collected cricket datasets and coverage."""
import json
import sqlite3
from datetime import datetime, timezone
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    player_id TEXT NOT NULL,
    format TEXT NOT NULL,
    dataset TEXT NOT NULL,
    record_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'ESPNcricinfo',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(player_id, format, dataset, record_key)
);
CREATE TABLE IF NOT EXISTS coverage (
    player_id TEXT NOT NULL,
    format TEXT NOT NULL,
    match_id TEXT NOT NULL,
    match_slug TEXT,
    series_slug TEXT,
    match_date TEXT,
    opposition TEXT,
    ground TEXT,
    match_label TEXT,
    scorecard_status TEXT NOT NULL DEFAULT 'pending',
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    delivery_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(player_id, format, match_id)
);
CREATE TABLE IF NOT EXISTS players (
    player_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

def _now():
    return datetime.now(timezone.utc).isoformat()

def connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con

def save_player(player_id, display_name, profile):
    with connect() as con:
        con.execute(
            """INSERT INTO players VALUES(?,?,?,?)
               ON CONFLICT(player_id) DO UPDATE SET
               display_name=excluded.display_name,
               profile_json=excluded.profile_json,
               updated_at=excluded.updated_at""",
            (str(player_id), display_name, json.dumps(profile, ensure_ascii=False, default=str), _now()),
        )

def save_dataset(player_id, fmt, dataset, records, source="ESPNcricinfo"):
    """Replace one named dataset atomically; records are dictionaries."""
    with connect() as con:
        con.execute(
            "DELETE FROM datasets WHERE player_id=? AND format=? AND dataset=?",
            (str(player_id), fmt, dataset),
        )
        for i, record in enumerate(records):
            key = str(record.get("_record_key", i))
            payload = {k: v for k, v in record.items() if k != "_record_key"}
            con.execute(
                "INSERT OR REPLACE INTO datasets VALUES(?,?,?,?,?,?,?)",
                (str(player_id), fmt, dataset, key,
                 json.dumps(payload, ensure_ascii=False, default=str), source, _now()),
            )

def load_dataset(player_id, fmt, dataset):
    with connect() as con:
        rows = con.execute(
            "SELECT payload FROM datasets WHERE player_id=? AND format=? AND dataset=? ORDER BY record_key",
            (str(player_id), fmt, dataset),
        ).fetchall()
    return [json.loads(r["payload"]) for r in rows]

def save_coverage_rows(rows):
    with connect() as con:
        for r in rows:
            con.execute(
                """INSERT INTO coverage
                (player_id,format,match_id,match_slug,series_slug,match_date,opposition,
                 ground,match_label,scorecard_status,delivery_status,delivery_count,last_error,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(player_id,format,match_id) DO UPDATE SET
                match_slug=COALESCE(excluded.match_slug,coverage.match_slug),
                series_slug=COALESCE(excluded.series_slug,coverage.series_slug),
                match_date=COALESCE(excluded.match_date,coverage.match_date),
                opposition=COALESCE(excluded.opposition,coverage.opposition),
                ground=COALESCE(excluded.ground,coverage.ground),
                match_label=COALESCE(excluded.match_label,coverage.match_label),
                updated_at=excluded.updated_at""",
                (str(r["player_id"]), r["format"], str(r["match_id"]), r.get("match_slug"),
                 r.get("series_slug"), r.get("match_date"), r.get("opposition"), r.get("ground"),
                 r.get("match_label"), r.get("scorecard_status", "pending"),
                 r.get("delivery_status", "pending"), int(r.get("delivery_count", 0)),
                 r.get("last_error"), _now()),
            )

def update_coverage(player_id, fmt, match_id, **fields):
    allowed = {"scorecard_status", "delivery_status", "delivery_count", "last_error"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = _now()
    sql = ", ".join(f"{k}=?" for k in fields)
    with connect() as con:
        con.execute(
            f"UPDATE coverage SET {sql} WHERE player_id=? AND format=? AND match_id=?",
            (*fields.values(), str(player_id), fmt, str(match_id)),
        )

def load_coverage(player_id, fmt=None):
    with connect() as con:
        if fmt:
            rows = con.execute(
                "SELECT * FROM coverage WHERE player_id=? AND format=? ORDER BY match_date,match_id",
                (str(player_id), fmt),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM coverage WHERE player_id=? ORDER BY format,match_date,match_id",
                (str(player_id),),
            ).fetchall()
    return [dict(r) for r in rows]

def load_player(player_id):
    with connect() as con:
        row = con.execute("SELECT * FROM players WHERE player_id=?", (str(player_id),)).fetchone()
    return dict(row) if row else None
