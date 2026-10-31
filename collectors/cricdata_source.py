"""ESPNcricinfo public-data adapter built on the cricdata package.

The adapter keeps player search, Statsguru history, scorecards and deliveries separate.
A failed request is returned as a failure; it is never converted to an empty career.
"""
import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from cricdata import CricinfoClient
from config import FORMAT_CLASS, REQUEST_DELAY_SECONDS

BASE = "https://www.espncricinfo.com"
STATS_BASE = "https://stats.espncricinfo.com/ci/engine/player"

class SourceError(RuntimeError):
    pass

def make_client():
    return CricinfoClient(timeout=35)

def search_players(client, query, limit=10):
    if not query or not query.strip():
        raise ValueError("Enter a player name.")
    try:
        return client.search_players(query.strip(), limit=limit)
    except Exception as exc:
        raise SourceError(f"Player search failed: {exc}") from exc

def _statsguru_url(player_id, fmt, stat_type):
    cls = FORMAT_CLASS[fmt]
    return f"{STATS_BASE}/{player_id}.html?class={cls};orderby=default;template=results;type={stat_type};view=match"

def _extract_match_ref(href):
    absolute = urljoin(BASE, href)
    path = absolute.split("?", 1)[0]
    parts = [p for p in path.split("/") if p]
    match_slug = None
    series_slug = None
    match_id = None

    # Current ESPN series routes: /series/<series-slug-id>/<match-slug-id>/full-scorecard
    if "series" in parts:
        i = parts.index("series")
        if len(parts) > i + 2:
            series_slug = parts[i + 1]
            possible_match = parts[i + 2]
            m = re.search(r"-(\d+)$", possible_match)
            if m:
                match_slug = possible_match
                match_id = m.group(1)

    # Legacy route: /ci/engine/match/<id>.html
    if not match_id:
        m = re.search(r"/match/(\d+)(?:\.html)?", path)
        if m:
            match_id = m.group(1)
            match_slug = f"match-{match_id}"

    # General fallback for ESPN match links with a numeric slug suffix.
    if not match_id and any(token in path for token in ("scorecard", "live-cricket-score", "/match/")):
        numeric_segments = [re.search(r"-(\d+)$", p) for p in parts]
        numeric_segments = [m for m in numeric_segments if m]
        if numeric_segments:
            match_id = numeric_segments[-1].group(1)
            match_slug = next((p for p in reversed(parts) if p.endswith("-" + match_id)), f"match-{match_id}")

    if not match_id:
        return None
    return {
        "match_id": str(match_id),
        "match_slug": match_slug or f"match-{match_id}",
        "series_slug": series_slug,
        "match_url": absolute,
    }

def _statsguru_link_rows(client, player_id, fmt, stat_type):
    """Read the same public Statsguru HTML page to preserve match href IDs.

    cricdata's typed Statsguru rows intentionally expose text columns. This small
    companion parser preserves the match links that the text table omits.
    """
    url = _statsguru_url(player_id, fmt, stat_type)
    try:
        # Reuse cricdata's existing session so its request configuration is consistent.
        response = client._session.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        found = []
        for row in soup.select("table.engineTable tr"):
            anchors = row.find_all("a", href=True)
            ref = None
            for anchor in anchors:
                ref = _extract_match_ref(anchor["href"])
                if ref:
                    break
            if ref:
                ref["row_text"] = " ".join(row.stripped_strings)
                found.append(ref)
        return found, None
    except Exception as exc:
        return [], str(exc)

def _safe_call(fn, *args, **kwargs):
    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:
        return None, str(exc)

def collect_format_career(client, player_id, fmt):
    """Collect career aggregates, match lists and innings for one format."""
    result = {
        "career": {},
        "match_lists": {},
        "innings": {},
        "coverage": [],
        "errors": [],
    }
    for stat_type in ("allround", "batting", "bowling", "fielding"):
        stats, err = _safe_call(client.player_career_stats, player_id, fmt=fmt, stat_type=stat_type)
        if err:
            result["errors"].append(f"{stat_type} career stats: {err}")
        else:
            result["career"][stat_type] = stats

        matches, err = _safe_call(client.player_match_list, player_id, fmt=fmt, stat_type=stat_type)
        if err:
            result["errors"].append(f"{stat_type} match list: {err}")
        else:
            rows = list((matches or {}).get("matches", []))
            links, link_error = _statsguru_link_rows(client, player_id, fmt, stat_type)
            # Match IDs are assigned only when the provider link-row count exactly matches
            # the typed match-row count. No positional guesses on mismatched tables.
            if len(links) == len(rows):
                for row, link in zip(rows, links):
                    row.update({k: link.get(k) for k in ("match_id", "match_slug", "series_slug", "match_url")})
            else:
                for row in rows:
                    row.update({"match_id": None, "match_slug": None, "series_slug": None, "match_url": None})
                if link_error:
                    result["errors"].append(f"{stat_type} match-ID links unavailable: {link_error}")
                elif rows:
                    result["errors"].append(
                        f"{stat_type} match-ID link count ({len(links)}) did not match Statsguru rows ({len(rows)}); IDs left unresolved."
                    )
            result["match_lists"][stat_type] = rows

        innings, err = _safe_call(client.player_innings, player_id, fmt=fmt, stat_type=stat_type)
        if err:
            result["errors"].append(f"{stat_type} innings: {err}")
        else:
            result["innings"][stat_type] = list((innings or {}).get("innings", []))

    # Use allround match history first, then batting; merge other stat-type rows by
    # date/opposition/ground so the inventory includes non-batting appearances where listed.
    primary = result["match_lists"].get("allround") or result["match_lists"].get("batting") or []
    merged = {}
    for stat_type, rows in result["match_lists"].items():
        for idx, row in enumerate(rows):
            key = "|".join(str(row.get(k, "")) for k in ("Start Date", "Opposition", "Ground", "Match"))
            if not key.strip("|"):
                key = f"{stat_type}:{idx}"
            if key not in merged:
                merged[key] = dict(row)
                merged[key]["stat_types"] = [stat_type]
            else:
                merged[key]["stat_types"].append(stat_type)
                for k in ("match_id", "match_slug", "series_slug", "match_url"):
                    if not merged[key].get(k) and row.get(k):
                        merged[key][k] = row[k]

    # Deduplicate coverage strictly by real match ID.
    coverage_by_id = {}
    for row in merged.values():
        mid = row.get("match_id")
        if not mid:
            continue
        coverage_by_id[str(mid)] = {
            "player_id": str(player_id),
            "format": fmt,
            "match_id": str(mid),
            "match_slug": row.get("match_slug"),
            "series_slug": row.get("series_slug"),
            "match_date": row.get("Start Date") or row.get("Date"),
            "opposition": row.get("Opposition"),
            "ground": row.get("Ground"),
            "match_label": row.get("Match") or row.get("Opposition"),
            "scorecard_status": "pending",
            "delivery_status": "pending",
            "delivery_count": 0,
        }
    result["coverage"] = list(coverage_by_id.values())
    result["match_history"] = list(merged.values())
    return result

def collect_match_detail(client, match_ref):
    """Attempt scorecard and ball-by-ball independently for one resolved match."""
    out = {"scorecard": None, "deliveries": [], "scorecard_error": None, "delivery_error": None}
    series_slug = match_ref.get("series_slug") or "series-unresolved"
    match_slug = match_ref.get("match_slug") or f"match-{match_ref['match_id']}"

    if match_ref.get("series_slug"):
        scorecard, err = _safe_call(client.match_scorecard, series_slug, match_slug)
        out["scorecard"], out["scorecard_error"] = scorecard, err
    else:
        out["scorecard_error"] = "Series slug not present in the Statsguru match link; scorecard route unresolved."

    balls, err = _safe_call(client.match_ball_by_ball, series_slug, match_slug)
    if err:
        out["delivery_error"] = err
    else:
        out["deliveries"] = balls or []
    return out

def flatten_deliveries(match_id, fmt, innings_groups):
    rows = []
    for innings_index, balls in enumerate(innings_groups or [], start=1):
        for ball_index, ball in enumerate(balls or [], start=1):
            ball = dict(ball)
            batsman = ball.get("batsman") or {}
            bowler = ball.get("bowler") or {}
            dismissal = ball.get("dismissal") or {}
            over = ball.get("over") or {}
            innings = ball.get("innings") or {}
            batter_athlete = batsman.get("athlete") or {}
            bowler_athlete = bowler.get("athlete") or {}
            dismissed = dismissal.get("batsman") or {}
            rows.append({
                "match_id": str(match_id),
                "format": fmt,
                "innings": innings.get("number", innings_index),
                "sequence": ball.get("sequence", ball_index),
                "over_number_source": over.get("number"),
                "ball_number_source": over.get("ball"),
                "batter": batter_athlete.get("displayName") or batter_athlete.get("name"),
                "bowler": bowler_athlete.get("displayName") or bowler_athlete.get("name"),
                "batter_runs_source": batsman.get("runs"),
                "batter_total_runs_source": batsman.get("totalRuns"),
                "score_value_source": ball.get("scoreValue"),
                "play_type": (ball.get("playType") or {}).get("description"),
                "dismissal_type": dismissal.get("type"),
                "dismissed_batter": dismissed.get("displayName") or dismissed.get("name"),
                "short_text": ball.get("shortText"),
                "commentary": ball.get("text"),
                "raw_json": ball,
            })
    return rows
