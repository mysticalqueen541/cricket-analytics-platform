"""Fixed-player ODI statistics adapter using public ESPNcricinfo Statsguru tables.

Collects career aggregates, innings, match lists, series and venue splits only.
It does not request scorecards or ball-by-ball data.
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
        time.sleep(REQUEST_DELAY_SECONDS)
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
    """Collect only the KL Rahul ODI batting datasets used by the dashboard.

    The match list is all-round so it inventories appearances (including DNB);
    batting innings are fetched separately so batting position and score analysis
    use only innings in which the player actually batted.
    """
    result = {
        "career": {},
        "match_lists": {},
        "innings": {},
        "series": {},
        "grounds": {},
        "coverage": [],
        "errors": [],
    }

    # Official career aggregate (contains a nested "summary" object).
    stats, err = _safe_call(
        client.player_career_stats, player_id, fmt=fmt, stat_type="batting"
    )
    if err:
        result["errors"].append(f"batting career stats: {err}")
    else:
        result["career"]["batting"] = stats

    # One all-round match list provides the complete appearance inventory.
    matches, err = _safe_call(
        client.player_match_list, player_id, fmt=fmt, stat_type="allround"
    )
    rows = []
    if err:
        result["errors"].append(f"all-round match list: {err}")
    else:
        rows = list((matches or {}).get("matches", []))
        links, link_error = _statsguru_link_rows(client, player_id, fmt, "allround")
        # IDs are joined only when the public HTML and typed table have equal row counts.
        if len(links) == len(rows):
            for row, link in zip(rows, links):
                row.update({
                    k: link.get(k)
                    for k in ("match_id", "match_slug", "series_slug", "match_url")
                })
        else:
            for row in rows:
                row.update({
                    "match_id": None, "match_slug": None,
                    "series_slug": None, "match_url": None,
                })
            if link_error:
                result["errors"].append(f"all-round match-ID links unavailable: {link_error}")
            elif rows:
                result["errors"].append(
                    f"match-ID link count ({len(links)}) did not match match-list rows "
                    f"({len(rows)}); IDs left unresolved."
                )
        result["match_lists"]["allround"] = rows

    # Batting innings contain the row-level runs, balls, dismissal and position fields.
    innings, err = _safe_call(
        client.player_innings, player_id, fmt=fmt, stat_type="batting"
    )
    if err:
        result["errors"].append(f"batting innings: {err}")
    else:
        result["innings"]["batting"] = list((innings or {}).get("innings", []))

    # These Statsguru aggregates add series and ground context without scraping
    # scorecards or requesting delivery data.
    series_rows, err = _safe_call(
        client.player_series_list, player_id, fmt=fmt, stat_type="batting"
    )
    if err:
        result["errors"].append(f"batting series splits: {err}")
    else:
        result["series"]["batting"] = list((series_rows or {}).get("series", []))

    ground_rows, err = _safe_call(
        client.player_ground_stats, player_id, fmt=fmt, stat_type="batting"
    )
    if err:
        result["errors"].append(f"batting ground splits: {err}")
    else:
        result["grounds"]["batting"] = list((ground_rows or {}).get("grounds", []))

    result["match_history"] = rows
    coverage_by_id = {}
    for row in rows:
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
        }
    result["coverage"] = list(coverage_by_id.values())
    return result
