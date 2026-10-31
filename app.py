import json
import time
import pandas as pd
import plotly.express as px
import streamlit as st

from collectors.cricdata_source import (
    make_client, search_players, collect_format_career,
    collect_match_detail, flatten_deliveries, SourceError,
)
from storage.database import (
    save_player, save_dataset, load_dataset, save_coverage_rows,
    load_coverage, update_coverage, load_player,
)
from storage.exporter import export_player_zip
from processing.metrics import batting_metrics, coverage_metrics
from processing.validation import validate_deliveries
from config import FORMATS, REQUEST_DELAY_SECONDS

st.set_page_config(page_title="Cricket Analytics Platform", page_icon="🏏", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1500px;}
[data-testid="stMetric"] {background: rgba(128,128,128,.08); padding: 14px; border-radius: 12px;}
.small-muted {opacity: .72; font-size: .9rem;}
</style>
""", unsafe_allow_html=True)

st.title("🏏 Cricket Analytics Platform")
st.caption("Player-first international cricket analysis · ODI · Test · T20I")

@st.cache_resource
def get_client():
    return make_client()

def as_frame(rows):
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def safe_text(value):
    if value is None:
        return ""
    return str(value)

def selected_player():
    return st.session_state.get("selected_player")

with st.sidebar:
    st.header("Player search")
    query = st.text_input("Player name", value=st.session_state.get("last_query", ""), placeholder="e.g. KL Rahul")
    if st.button("Search player", type="primary", use_container_width=True):
        if not query.strip():
            st.warning("Enter a player name first.")
        else:
            try:
                with st.spinner("Searching ESPNcricinfo player records..."):
                    candidates = search_players(get_client(), query)
                st.session_state["player_candidates"] = candidates
                st.session_state["last_query"] = query
                st.session_state.pop("selected_player", None)
                if not candidates:
                    st.info("No player candidates were returned. Try the full name or retry later.")
            except SourceError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Unexpected player-search error: {exc}")

    candidates = st.session_state.get("player_candidates", [])
    if candidates:
        def player_label(p):
            name = p.get("displayName") or p.get("fullName") or p.get("shortName") or "Unknown player"
            country = ""
            rels = p.get("teamRelationships") or []
            if rels and isinstance(rels, list):
                country = rels[0].get("displayName") or rels[0].get("name") or ""
            return f"{name}" + (f" · {country}" if country else "") + f" · ID {p.get('id','?')}"
        labels = [player_label(p) for p in candidates]
        choice = st.selectbox("Choose the correct player", range(len(candidates)), format_func=lambda i: labels[i])
        if st.button("Confirm player", use_container_width=True):
            p = candidates[choice]
            pid = str(p.get("id", ""))
            name = p.get("displayName") or p.get("fullName") or p.get("shortName") or "Unknown"
            if pid:
                try:
                    bio = get_client().player_bio(pid)
                except Exception as exc:
                    bio = {"bio_lookup_error": str(exc)}
                st.session_state["selected_player"] = {"player_id": pid, "name": name, "search_result": p, "bio": bio}
                save_player(pid, name, {"search_result": p, "bio": bio})
                st.success(f"Selected {name}")

player = selected_player()

if not player:
    st.info("Start by searching for a player. You will only need the player name; the internal ESPN player ID is resolved after you select the correct result.")
    st.markdown("""
    **What this app collects**
    - Career aggregates and match-by-match records
    - Batting, bowling and fielding innings tables
    - Resolved match IDs, scorecards and available delivery feeds
    - Match-by-match source coverage and retrieval errors
    """)
    st.stop()

pid = player["player_id"]
bio = player.get("bio", {})
name = player["name"]

headshot = (player.get("search_result", {}).get("headshot") or {}).get("href")
col1, col2 = st.columns([1, 5])
with col1:
    if headshot:
        st.image(headshot, width=105)
with col2:
    st.subheader(name)
    meta = []
    if bio.get("displayDOB"): meta.append(f"DOB: {bio['displayDOB']}")
    if bio.get("displayName") and bio.get("displayName") != name: meta.append(bio["displayName"])
    if bio.get("position", {}).get("name"): meta.append(bio["position"]["name"])
    st.caption(" · ".join(meta) if meta else f"ESPN player ID: {pid}")

with st.expander("Collection settings", expanded=True):
    formats_selected = st.multiselect("International formats", list(FORMATS.keys()), default=["ODI", "Test", "T20I"])
    st.caption("Career collection retrieves provider career tables and match-by-match/innings records for each selected format.")
    collect_button = st.button("Collect career datasets", type="primary", disabled=not formats_selected)

if collect_button:
    progress = st.progress(0)
    status = st.empty()
    all_errors = []
    for index, fmt_label in enumerate(formats_selected, start=1):
        fmt = FORMATS[fmt_label]
        status.info(f"Collecting {fmt_label}: career summaries, match lists and innings...")
        try:
            result = collect_format_career(get_client(), pid, fmt)
            for stat_type, rows in result["career"].items():
                save_dataset(pid, fmt, f"career_{stat_type}", [rows] if rows else [])
            for stat_type, rows in result["match_lists"].items():
                save_dataset(pid, fmt, f"match_list_{stat_type}", rows)
            for stat_type, rows in result["innings"].items():
                save_dataset(pid, fmt, f"innings_{stat_type}", rows)
            for stat_type, rows in result["series"].items():
                save_dataset(pid, fmt, f"series_{stat_type}", rows)
            for stat_type, rows in result["grounds"].items():
                save_dataset(pid, fmt, f"grounds_{stat_type}", rows)
            save_dataset(pid, fmt, "match_history", result["match_history"])
            save_coverage_rows(result["coverage"])
            all_errors.extend([f"{fmt_label} · {e}" for e in result["errors"]])
            st.success(
                f"{fmt_label}: {len(result['match_history'])} match-history rows, "
                f"{sum(len(v) for v in result['innings'].values())} innings rows, "
                f"{len(result['coverage'])} match IDs resolved."
            )
        except Exception as exc:
            all_errors.append(f"{fmt_label}: {exc}")
            st.error(f"{fmt_label} collection failed: {exc}")
        progress.progress(index / len(formats_selected))
    status.success("Career collection finished. Review the coverage register for unresolved match IDs.")
    if all_errors:
        with st.expander(f"Collection warnings ({len(all_errors)})"):
            for error in all_errors:
                st.write("• " + error)

# Rehydrate all formats selected for this session plus any saved career formats.
saved_formats = list(FORMATS.items())
available_formats = [label for label, code in saved_formats if load_dataset(pid, code, "match_history")]
if not available_formats:
    available_formats = formats_selected if "formats_selected" in locals() else list(FORMATS.keys())

tabs = st.tabs(["Overview", "Batting", "Bowling & fielding", "Innings", "Coverage & deliveries", "Exports", "Series & venues", "Team explorer"])

# OVERVIEW
with tabs[0]:
    st.subheader("Career overview")
    overview_rows = []
    for label, fmt in FORMATS.items():
        career = load_dataset(pid, fmt, "career_batting")
        history = load_dataset(pid, fmt, "match_history")
        batting_innings = load_dataset(pid, fmt, "innings_batting")
        if career or history or batting_innings:
            summary = (career[0] if career else {})
            overview_rows.append({
                "Format": label,
                "Matches in history": len(history),
                "Batting innings": len(batting_innings),
                "Runs (source summary)": summary.get("Runs"),
                "Average (source summary)": summary.get("Ave"),
                "Strike rate (source summary)": summary.get("SR"),
                "100s": summary.get("100"),
                "50s": summary.get("50"),
            })
    if overview_rows:
        st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Click **Collect career datasets** to populate the overview.")
    st.markdown("**Interpretation note:** match-list rows and batting innings are shown separately. A player may appear in a match without recording a batting innings.")

# BATTING
with tabs[1]:
    st.subheader("Batting analysis")
    fmt_label = st.selectbox("Format", list(FORMATS.keys()), key="bat_fmt")
    fmt = FORMATS[fmt_label]
    rows = load_dataset(pid, fmt, "innings_batting")
    df = batting_metrics(rows)
    if df.empty:
        st.info("No batting innings stored for this format yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        if "runs_numeric" in df:
            chart = df.dropna(subset=["runs_numeric"])
            if not chart.empty:
                st.plotly_chart(px.histogram(chart, x="runs_numeric", nbins=20, title=f"{fmt_label} runs per innings"), use_container_width=True)
        pos_col = next((c for c in ("Pos", "Batting Position", "position") if c in df.columns), None)
        if pos_col:
            pos = df.copy()
            pos[pos_col] = pd.to_numeric(pos[pos_col], errors="coerce")
            st.plotly_chart(px.histogram(pos.dropna(subset=[pos_col]), x=pos_col, title="Batting position frequency"), use_container_width=True)

# BOWLING & FIELDING
with tabs[2]:
    st.subheader("Bowling and fielding")
    fmt_label = st.selectbox("Format", list(FORMATS.keys()), key="bowl_fmt")
    fmt = FORMATS[fmt_label]
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Bowling innings**")
        bowling = as_frame(load_dataset(pid, fmt, "innings_bowling"))
        if bowling.empty: st.info("No bowling innings stored.")
        else: st.dataframe(bowling, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**Fielding innings**")
        fielding = as_frame(load_dataset(pid, fmt, "innings_fielding"))
        if fielding.empty: st.info("No fielding innings stored.")
        else: st.dataframe(fielding, use_container_width=True, hide_index=True)

# INNINGS
with tabs[3]:
    st.subheader("Match-by-match and innings records")
    fmt_label = st.selectbox("Format", list(FORMATS.keys()), key="innings_fmt")
    fmt = FORMATS[fmt_label]
    stat_type = st.selectbox("Dataset", ["match_history", "innings_batting", "innings_bowling", "innings_fielding", "innings_allround"])
    rows = load_dataset(pid, fmt, stat_type)
    df = as_frame(rows)
    if df.empty:
        st.info("No records saved for this selection yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(f"Download {stat_type}.csv", df.to_csv(index=False).encode("utf-8-sig"),
                           f"{fmt}_{stat_type}.csv", "text/csv")

# COVERAGE AND DELIVERIES
with tabs[4]:
    st.subheader("Match coverage register")
    fmt_label = st.selectbox("Format", list(FORMATS.keys()), key="coverage_fmt")
    fmt = FORMATS[fmt_label]
    coverage = load_coverage(pid, fmt)
    cov_df = as_frame(coverage)
    history_rows = load_dataset(pid, fmt, "match_history")
    unresolved_count = sum(1 for row in history_rows if not row.get("match_id"))
    if cov_df.empty:
        st.info("No resolved match IDs are stored for this format. Career text rows may still be available in the Innings tab.")
        st.metric("Match-history rows without a resolved ID", unresolved_count)
    else:
        stats = coverage_metrics(coverage)
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Resolved matches", stats["matches"])
        m2.metric("History rows without ID", unresolved_count)
        m3.metric("Scorecards stored", stats["scorecards"])
        m4.metric("Complete delivery feeds", stats["deliveries"])
        m5.metric("Delivery failures", stats["failed"])
        st.dataframe(cov_df, use_container_width=True, hide_index=True)

        st.markdown("**Fetch delivery data for resolved matches**")
        limit = st.number_input("Maximum matches in this batch (0 = all unresolved matches)", min_value=0, max_value=5000, value=20, step=10)
        if st.button("Fetch ball-by-ball", type="primary"):
            pending = [r for r in coverage if r.get("delivery_status") in ("pending", "failed", "not_available")]
            if limit:
                pending = pending[:int(limit)]
            if not pending:
                st.info("No unresolved delivery records in this selection.")
            else:
                progress = st.progress(0)
                message = st.empty()
                errors = []
                for idx, ref in enumerate(pending, start=1):
                    message.info(f"Fetching match {idx}/{len(pending)} · {ref['match_id']}")
                    detail = collect_match_detail(get_client(), ref)
                    if detail["scorecard"] is not None:
                        existing_cards = load_dataset(pid, fmt, "scorecards")
                        existing_cards = [
                            {**r, "_record_key": str(r.get("match_id", i))}
                            for i, r in enumerate(existing_cards)
                            if str(r.get("match_id")) != str(ref["match_id"])
                        ]
                        existing_cards.append({
                            "_record_key": ref["match_id"],
                            "match_id": ref["match_id"],
                            "scorecard_json": detail["scorecard"],
                        })
                        save_dataset(pid, fmt, "scorecards", existing_cards)
                        update_coverage(pid, fmt, ref["match_id"], scorecard_status="complete")
                    elif detail["scorecard_error"]:
                        update_coverage(pid, fmt, ref["match_id"], scorecard_status="failed")
                        errors.append(f"{ref['match_id']} scorecard: {detail['scorecard_error']}")

                    flat = flatten_deliveries(ref["match_id"], fmt, detail["deliveries"])
                    if flat:
                        # Append without replacing previously collected match deliveries.
                        existing = load_dataset(pid, fmt, "deliveries")
                        existing = [r for r in existing if str(r.get("match_id")) != str(ref["match_id"])]
                        existing.extend(flat)
                        save_dataset(pid, fmt, "deliveries", existing)
                        update_coverage(pid, fmt, ref["match_id"], delivery_status="complete", delivery_count=len(flat), last_error=None)
                    else:
                        status = "not_available" if not detail["delivery_error"] else "failed"
                        update_coverage(pid, fmt, ref["match_id"], delivery_status=status,
                                        delivery_count=0, last_error=detail["delivery_error"] or "Provider returned no delivery rows.")
                        if detail["delivery_error"]:
                            errors.append(f"{ref['match_id']} deliveries: {detail['delivery_error']}")
                    progress.progress(idx / len(pending))
                message.success(f"Delivery collection finished for {len(pending)} matches.")
                if errors:
                    with st.expander(f"Retrieval warnings ({len(errors)})"):
                        for error in errors:
                            st.write("• " + error)
                st.rerun()

    st.markdown("**Stored delivery records**")
    deliveries = as_frame(load_dataset(pid, fmt, "deliveries"))
    if deliveries.empty:
        st.info("No delivery rows stored for this format yet.")
    else:
        st.write(f"{len(deliveries):,} delivery records stored.")
        validation = validate_deliveries(deliveries.to_dict("records"))
        if validation["warnings"]:
            for warning in validation["warnings"]:
                st.warning(warning)
        st.dataframe(deliveries.drop(columns=["raw_json"], errors="ignore"), use_container_width=True, hide_index=True)
        st.download_button("Download deliveries CSV", deliveries.drop(columns=["raw_json"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
                           f"{fmt}_deliveries.csv", "text/csv")

# EXPORTS
with tabs[5]:
    st.subheader("Download collected datasets")
    chosen_labels = st.multiselect("Formats to include", list(FORMATS.keys()), default=list(FORMATS.keys()), key="export_formats")
    chosen_codes = [FORMATS[x] for x in chosen_labels]
    if st.button("Prepare ZIP export", disabled=not chosen_codes):
        payload = export_player_zip(pid, chosen_codes)
        st.download_button("Download player datasets ZIP", payload, f"{name.replace(' ','_')}_cricket_data.zip", "application/zip")
    st.caption("The ZIP contains only data currently stored on this computer. It does not download missing provider data automatically.")


# SERIES & VENUES
with tabs[6]:
    st.subheader("Series and venue analysis")
    fmt_label = st.selectbox("Format", list(FORMATS.keys()), key="series_venue_fmt")
    fmt = FORMATS[fmt_label]
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("**Series-by-series batting**")
        series_bat = as_frame(load_dataset(pid, fmt, "series_batting"))
        if series_bat.empty: st.info("No series batting split stored.")
        else: st.dataframe(series_bat, use_container_width=True, hide_index=True)
    with s2:
        st.markdown("**Venue-by-venue batting**")
        grounds_bat = as_frame(load_dataset(pid, fmt, "grounds_batting"))
        if grounds_bat.empty: st.info("No venue batting split stored.")
        else: st.dataframe(grounds_bat, use_container_width=True, hide_index=True)
    s3, s4 = st.columns(2)
    with s3:
        st.markdown("**Series-by-series bowling**")
        series_bowl = as_frame(load_dataset(pid, fmt, "series_bowling"))
        if series_bowl.empty: st.info("No series bowling split stored.")
        else: st.dataframe(series_bowl, use_container_width=True, hide_index=True)
    with s4:
        st.markdown("**Venue-by-venue bowling**")
        grounds_bowl = as_frame(load_dataset(pid, fmt, "grounds_bowling"))
        if grounds_bowl.empty: st.info("No venue bowling split stored.")
        else: st.dataframe(grounds_bowl, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Series pages and full series match lists**")
    history = load_dataset(pid, fmt, "match_history")
    series_slugs = sorted({str(r.get("series_slug")) for r in history if r.get("series_slug")})
    if not series_slugs:
        st.info("No series slugs were resolved from this player's match links. Series pages cannot be requested without a real source slug.")
    else:
        st.caption(f"{len(series_slugs)} series slug(s) available from the resolved match links.")
        if st.button("Fetch series pages and match lists", key="fetch_series_pages"):
            errors = []
            progress = st.progress(0)
            for idx, slug in enumerate(series_slugs, start=1):
                time.sleep(REQUEST_DELAY_SECONDS)
                try:
                    detail = get_client().series(slug)
                    matches = get_client().series_matches(slug)
                    old_details = load_dataset(pid, fmt, "series_details")
                    old_details = [r for r in old_details if r.get("series_slug") != slug]
                    old_details.append({"_record_key": slug, "series_slug": slug, "series_json": detail})
                    save_dataset(pid, fmt, "series_details", old_details)
                    old_matches = load_dataset(pid, fmt, "series_match_lists")
                    old_matches = [r for r in old_matches if r.get("series_slug") != slug]
                    old_matches.append({"_record_key": slug, "series_slug": slug, "matches_json": matches})
                    save_dataset(pid, fmt, "series_match_lists", old_matches)
                except Exception as exc:
                    errors.append(f"{slug}: {exc}")
                progress.progress(idx / len(series_slugs))
            if errors:
                with st.expander(f"Series retrieval warnings ({len(errors)})"):
                    for error in errors: st.write("• " + error)
            st.success("Series page collection finished.")
            st.rerun()
        series_details = load_dataset(pid, fmt, "series_details")
        st.write(f"Stored series pages: {len(series_details)}")

# TEAM EXPLORER
with tabs[7]:
    st.subheader("Team explorer")
    team = bio.get("team") if isinstance(bio, dict) else {}
    team = team if isinstance(team, dict) else {}
    team_id = team.get("id") or team.get("objectId")
    team_slug = team.get("slug")
    team_name = team.get("displayName") or team.get("name") or team.get("longName")
    if team_name:
        st.write(f"Player profile team: **{team_name}**")
    if not team_id or not team_slug:
        st.info("The selected player's bio does not expose both a team ID and team slug. Team endpoints need those real identifiers; the app will not guess them.")
    else:
        st.caption(f"Team ID: {team_id} · Team slug: {team_slug}")
        team_formats = st.multiselect("Team formats", list(FORMATS.keys()), default=list(FORMATS.keys()), key="team_formats")
        if st.button("Fetch team profile and records", disabled=not team_formats):
            errors = []
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                profile = get_client().team(team_slug)
                save_dataset(pid, "team", "team_profile", [{"_record_key": team_slug, "team_slug": team_slug, "team_json": profile}])
            except Exception as exc:
                errors.append(f"Team profile: {exc}")
            progress = st.progress(0)
            for idx, label in enumerate(team_formats, start=1):
                fmt = FORMATS[label]
                time.sleep(REQUEST_DELAY_SECONDS)
                try:
                    career = get_client().team_career_stats(team_id, fmt=fmt)
                    save_dataset(pid, fmt, "team_career", [career] if career else [])
                except Exception as exc:
                    errors.append(f"{label} team career: {exc}")
                time.sleep(REQUEST_DELAY_SECONDS)
                try:
                    matches = get_client().team_match_list(team_id, fmt=fmt)
                    save_dataset(pid, fmt, "team_matches", list((matches or {}).get("matches", [])))
                except Exception as exc:
                    errors.append(f"{label} team matches: {exc}")
                progress.progress(idx / len(team_formats))
            if errors:
                with st.expander(f"Team retrieval warnings ({len(errors)})"):
                    for error in errors: st.write("• " + error)
            st.success("Team collection finished.")
            st.rerun()

        team_fmt_label = st.selectbox("View team records", list(FORMATS.keys()), key="team_view_fmt")
        team_fmt = FORMATS[team_fmt_label]
        team_career = load_dataset(pid, team_fmt, "team_career")
        team_matches = load_dataset(pid, team_fmt, "team_matches")
        if team_career:
            st.markdown("**Team career summary**")
            st.dataframe(as_frame([team_career[0].get("summary", {})]), use_container_width=True, hide_index=True)
        if team_matches:
            st.markdown("**Team match list**")
            st.dataframe(as_frame(team_matches), use_container_width=True, hide_index=True)
