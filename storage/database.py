import sqlite3
import json
from datetime import datetime, timezone
import pandas as pd
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
 player_id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT, profile_url TEXT,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS matches (
 match_id TEXT PRIMARY KEY, player_id TEXT, format TEXT, date TEXT, opposition TEXT,
 team TEXT, venue TEXT, series TEXT, match_url TEXT, discovery_source TEXT,
 scorecard_status TEXT DEFAULT 'pending', delivery_status TEXT DEFAULT 'pending',
 last_error TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS batting (
 match_id TEXT, innings INTEGER, player_id TEXT, player_name TEXT, batting_position INTEGER,
 runs INTEGER, balls INTEGER, fours INTEGER, sixes INTEGER, dismissal TEXT,
 PRIMARY KEY(match_id, innings, player_id)
);
CREATE TABLE IF NOT EXISTS bowling (
 match_id TEXT, innings INTEGER, player_id TEXT, player_name TEXT, overs REAL,
 maidens INTEGER, runs INTEGER, wickets INTEGER, wides INTEGER, no_balls INTEGER,
 PRIMARY KEY(match_id, innings, player_id)
);
CREATE TABLE IF NOT EXISTS deliveries (
 match_id TEXT, innings INTEGER, over_number INTEGER, ball_number INTEGER,
 batter TEXT, non_striker TEXT, bowler TEXT, runs_batter INTEGER, runs_extras INTEGER,
 total_runs INTEGER, extras_type TEXT, wicket_type TEXT, dismissed_batter TEXT,
 source TEXT, PRIMARY KEY(match_id, innings, over_number, ball_number)
);
"""

def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con

def save_player(player):
    with connect() as con:
        con.execute("""INSERT INTO players VALUES(?,?,?,?,?)
        ON CONFLICT(player_id) DO UPDATE SET name=excluded.name,country=excluded.country,
        profile_url=excluded.profile_url,updated_at=excluded.updated_at""",
        (str(player["player_id"]), player["name"], player.get("country"),
         player.get("profile_url"), datetime.now(timezone.utc).isoformat()))

def save_matches(rows):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        for r in rows:
            con.execute("""INSERT INTO matches
            (match_id,player_id,format,date,opposition,team,venue,series,match_url,
             discovery_source,scorecard_status,delivery_status,last_error,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(match_id) DO UPDATE SET
            player_id=excluded.player_id,format=excluded.format,date=excluded.date,
            opposition=excluded.opposition,team=excluded.team,venue=excluded.venue,
            series=excluded.series,match_url=excluded.match_url,
            discovery_source=excluded.discovery_source,updated_at=excluded.updated_at""",
            (str(r["match_id"]),str(r.get("player_id","")),r.get("format"),r.get("date"),
             r.get("opposition"),r.get("team"),r.get("venue"),r.get("series"),
             r.get("match_url"),r.get("discovery_source","unknown"),
             r.get("scorecard_status","pending"),r.get("delivery_status","pending"),
             r.get("last_error"),now))

def update_match_status(match_id, **fields):
    allowed={"scorecard_status","delivery_status","last_error"}
    fields={k:v for k,v in fields.items() if k in allowed}
    if not fields: return
    fields["updated_at"]=datetime.now(timezone.utc).isoformat()
    sql=", ".join(f"{k}=?" for k in fields)
    with connect() as con:
        con.execute(f"UPDATE matches SET {sql} WHERE match_id=?",
                    (*fields.values(),str(match_id)))

def read_table(table):
    allowed={"players","matches","batting","bowling","deliveries"}
    if table not in allowed: raise ValueError("Unknown table")
    with connect() as con:
        return pd.read_sql_query(f"SELECT * FROM {table}",con)

def save_deliveries(match_id, innings, rows, source):
    with connect() as con:
        for d in rows:
            con.execute("""INSERT OR REPLACE INTO deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(match_id),int(innings),int(d.get("over_number",0)),int(d.get("ball_number",0)),
             d.get("batter"),d.get("non_striker"),d.get("bowler"),
             int(d.get("runs_batter",0)),int(d.get("runs_extras",0)),
             int(d.get("total_runs",0)),d.get("extras_type"),d.get("wicket_type"),
             d.get("dismissed_batter"),source))
