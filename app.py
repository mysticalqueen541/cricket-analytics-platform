"""Fixed-player KL Rahul ODI career analytics dashboard.

All statistics are derived from public ESPNcricinfo Statsguru career, innings,
match-list, series and venue tables collected by collectors/cricdata_source.py.
No player/form selector, manual ID entry, scorecard scraping or ball-by-ball data.
"""
from datetime import datetime
import pandas as pd
import plotly.express as px
import streamlit as st

from collectors.cricdata_source import make_client, collect_format_career
from storage.database import (
    save_player, save_dataset, load_dataset, save_coverage_rows, load_coverage
)

PLAYER_ID = "422108"
PLAYER_NAME = "KL Rahul"
FORMAT = "odi"
SOURCE_LABEL = "Public ESPNcricinfo Statsguru"

st.set_page_config(page_title="KL Rahul | ODI Career Lab", page_icon="🏏", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1580px; padding-top: 1.15rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: rgba(128,128,128,.075); padding: 13px 15px; border-radius: 12px;}
h1 {letter-spacing: -.04em;}
.small-note {opacity: .72; font-size: .86rem;}
div[data-testid="stTabs"] button {font-weight: 600;}
</style>
""", unsafe_allow_html=True)


def load_frame(name):
    rows = load_dataset(PLAYER_ID, FORMAT, name)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def first_col(df, candidates):
    return next((c for c in candidates if c in df.columns), None)


def num(df, candidates):
    col = first_col(df, candidates)
    if not col:
        return pd.Series(float("nan"), index=df.index, dtype="float64")
    return pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce")


def safe_div(a, b):
    return a / b.replace(0, pd.NA)


def collect_all():
    client = make_client()
    result = collect_format_career(client, PLAYER_ID, FORMAT)
    save_player(PLAYER_ID, PLAYER_NAME, {"source": SOURCE_LABEL, "format": "ODI"})
    for kind, rows in result["career"].items():
        save_dataset(PLAYER_ID, FORMAT, f"career_{kind}", [rows] if rows else [])
    for kind, rows in result["match_lists"].items():
        save_dataset(PLAYER_ID, FORMAT, f"match_list_{kind}", rows)
    for kind, rows in result["innings"].items():
        save_dataset(PLAYER_ID, FORMAT, f"innings_{kind}", rows)
    for kind, rows in result["series"].items():
        save_dataset(PLAYER_ID, FORMAT, f"series_{kind}", rows)
    for kind, rows in result["grounds"].items():
        save_dataset(PLAYER_ID, FORMAT, f"grounds_{kind}", rows)
    save_dataset(PLAYER_ID, FORMAT, "match_history", result["match_history"])
    save_coverage_rows(result["coverage"])
    return result


def prepare_innings(raw):
    df = raw.copy()
    if df.empty:
        return df
    df["Runs_num"] = num(df, ["Runs", "R", "runs"])
    df["Balls_num"] = num(df, ["BF", "Balls", "B", "balls"])
    df["Fours_num"] = num(df, ["4s", "Fours", "4"])
    df["Sixes_num"] = num(df, ["6s", "Sixes", "6"])
    df["SR_calc"] = safe_div(df["Runs_num"] * 100, df["Balls_num"])
    date_col = first_col(df, ["Start Date", "Date", "Match Date"])
    if date_col:
        df["Match date"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
        df["Year"] = df["Match date"].dt.year
    else:
        df["Match date"] = pd.NaT
        df["Year"] = pd.NA
    pos_col = first_col(df, ["Pos", "Batting Position", "Batting position", "position", "Bat Pos"])
    df["Position_num"] = pd.to_numeric(df[pos_col], errors="coerce") if pos_col else pd.NA
    dismissal_col = first_col(df, ["Dismissal", "How Out", "Dismissal Type", "Dismissal type"])
    if dismissal_col:
        d = df[dismissal_col].fillna("").astype(str).str.lower().str.strip()
        df["Out_flag"] = ~d.isin(["", "-", "not out", "retired hurt", "absent", "did not bat", "dnb", ""])
    else:
        df["Out_flag"] = pd.NA
    df["50_plus"] = df["Runs_num"].ge(50)
    df["100_plus"] = df["Runs_num"].ge(100)
    df["Duck"] = df["Runs_num"].eq(0) & df["Out_flag"].eq(True)
    df["Boundary_runs"] = df["Fours_num"].fillna(0) * 4 + df["Sixes_num"].fillna(0) * 6
    df["Boundary_pct"] = safe_div(df["Boundary_runs"] * 100, df["Runs_num"])
    return df


def score_summary(df, group_col):
    out = df.groupby(group_col, dropna=False).agg(
        Innings=("Runs_num", "count"),
        Runs=("Runs_num", "sum"),
        Balls=("Balls_num", "sum"),
        Highest=("Runs_num", "max"),
        Fours=("Fours_num", "sum"),
        Sixes=("Sixes_num", "sum"),
        Fifties=("50_plus", "sum"),
        Hundreds=("100_plus", "sum"),
    ).reset_index()
    if "Out_flag" in df and df["Out_flag"].notna().any():
        outs = df.groupby(group_col)["Out_flag"].sum().reset_index(name="Dismissals")
        out = out.merge(outs, on=group_col, how="left")
        out["Average"] = safe_div(out["Runs"], out["Dismissals"])
    out["Strike rate"] = safe_div(out["Runs"] * 100, out["Balls"])
    return out


def show_download(df, filename, label):
    if not df.empty:
        st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), filename, "text/csv")


st.title("🏏 KL Rahul — ODI Career Lab")
st.caption("A fixed-player research dashboard · ODI debut to latest ODI in the public source · No player inputs or ball-by-ball data")
with st.sidebar:
    st.markdown("### KL Rahul")
    st.markdown("**ODI career only**")
    st.caption("Player ID: 422108")
    st.caption("Source: ESPNcricinfo Statsguru")
    refresh = st.button("↻ Refresh career data", type="primary", use_container_width=True)
    st.markdown("---")
    st.caption("The dashboard always loads KL Rahul's ODI records. There are no player or format selectors.")

if refresh or not load_frame("innings_batting").shape[0]:
    with st.spinner("Collecting KL Rahul's ODI career, match history, innings, series and venue statistics…"):
        try:
            result = collect_all()
            st.session_state["last_refresh"] = datetime.now().strftime("%d %b %Y, %H:%M")
            st.session_state["source_errors"] = result.get("errors", [])
            st.success("Public Statsguru collection finished. Review the coverage panel for any source gaps.")
        except Exception as exc:
            st.error(f"Could not refresh public Statsguru records: {exc}")
            st.info("Previously saved local data will still be displayed where available.")

career_rows = load_dataset(PLAYER_ID, FORMAT, "career_batting")
career = career_rows[0] if career_rows else {}
innings_raw = load_frame("innings_batting")
innings = prepare_innings(innings_raw)
history = load_frame("match_history")
series = load_frame("series_batting")
grounds = load_frame("grounds_batting")
coverage = pd.DataFrame(load_coverage(PLAYER_ID, FORMAT))
match_list = load_frame("match_list_allround")
if match_list.empty:
    match_list = load_frame("match_list_batting")

if innings.empty and not career:
    st.warning("No ODI records are saved yet. Check your internet connection and use Refresh career data.")
    st.stop()

def career_value(keys, default="—"):
    for key in keys:
        if career.get(key) not in (None, ""):
            return career[key]
    return default

matches = career_value(["Mat", "Matches"])
runs = career_value(["Runs", "R"])
average = career_value(["Ave", "Avg", "Average"])
sr = career_value(["SR", "Strike Rate"])
hs = career_value(["HS", "Highest"])
hundreds = career_value(["100", "100s"])
fifties = career_value(["50", "50s"])
not_outs = career_value(["NO", "Not Outs"])
last_loaded = st.session_state.get("last_refresh", "Saved local dataset")
st.caption(f"Last retrieved: {last_loaded} · ODI debut: 11 June 2016 · Latest source match: see match-history table")

kpis = st.columns(7)
for col, label, value in zip(kpis,
    ["Matches", "Runs", "Average", "Strike rate", "Highest score", "Hundreds", "Fifties"],
    [matches, runs, average, sr, hs, hundreds, fifties]):
    col.metric(label, value if value not in (None, "") else "—")

tabs = st.tabs([
    "Career overview", "Batting position", "Scoring & consistency",
    "Opposition", "Venues & series", "Year-by-year", "Innings records", "Data coverage"
])

# CAREER OVERVIEW
with tabs[0]:
    st.subheader("Career snapshot")
    a, b = st.columns([1.05, 1])
    with a:
        st.markdown("**Official Statsguru ODI batting summary**")
        if career:
            st.dataframe(pd.DataFrame([career]), use_container_width=True, hide_index=True)
        else:
            st.info("Career summary not returned by the source.")
    with b:
        st.markdown("**Distribution of innings scores**")
        scores = innings.dropna(subset=["Runs_num"]) if not innings.empty else pd.DataFrame()
        if not scores.empty:
            st.plotly_chart(px.histogram(scores, x="Runs_num", nbins=20,
                labels={"Runs_num":"Runs"}, title="How often each score range occurred"), use_container_width=True)
        else:
            st.info("Innings scores are not available.")
    if not innings.empty:
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Innings rows", len(innings))
        q2.metric("Runs in innings table", f"{int(innings['Runs_num'].sum()):,}")
        q3.metric("50+ scores", int(innings["50_plus"].sum()))
        q4.metric("Ducks recorded", int(innings["Duck"].sum()))
        st.markdown("**Career score timeline**")
        trend = innings.dropna(subset=["Match date", "Runs_num"]).sort_values("Match date")
        if not trend.empty:
            st.plotly_chart(px.scatter(trend, x="Match date", y="Runs_num", hover_data=[
                c for c in [first_col(trend, ["Opposition", "Opponent"]), first_col(trend, ["Ground", "Venue"]), "Position_num"] if c
            ], title="Every recorded ODI innings"), use_container_width=True)
    if not history.empty:
        st.markdown("**ODI appearance history**")
        st.dataframe(history, use_container_width=True, hide_index=True)
        show_download(history, "kl_rahul_odi_match_history.csv", "Download complete match-history table")

# BATTING POSITION
with tabs[1]:
    st.subheader("Batting-position analysis")
    st.write("Compare his output when opening, batting in the top order and playing the middle-order role.")
    if not innings.empty and innings["Position_num"].notna().any():
        pos = innings.dropna(subset=["Position_num", "Runs_num"]).copy()
        pos["Position"] = pos["Position_num"].astype(int).map(lambda x: f"No. {x}")
        grouped = score_summary(pos, "Position")
        grouped["Position_order"] = grouped["Position"].str.extract(r"(\d+)").astype(int)
        grouped = grouped.sort_values("Position_order")
        c1, c2 = st.columns([1.1, 1])
        with c1:
            st.markdown("**Position-wise scorecard**")
            st.dataframe(grouped.drop(columns=["Position_order"]).round(2), use_container_width=True, hide_index=True)
        with c2:
            st.plotly_chart(px.bar(grouped, x="Position", y="Runs", text="Runs",
                title="Total ODI runs by batting position"), use_container_width=True)
        c3, c4 = st.columns(2)
        with c3:
            metric = "Average" if "Average" in grouped else "Strike rate"
            st.plotly_chart(px.bar(grouped, x="Position", y=metric, text=metric,
                title=f"{metric} by batting position"), use_container_width=True)
        with c4:
            st.plotly_chart(px.bar(grouped, x="Position", y="Innings", text="Innings",
                title="Innings played at each position"), use_container_width=True)
        st.caption("Position analysis uses only the explicit batting-position field returned in the innings records. No batting position is guessed.")
        show_download(grouped.drop(columns=["Position_order"]), "kl_rahul_odi_batting_position.csv", "Download batting-position analysis")
    else:
        st.warning("The innings data returned by the public source does not currently contain a usable batting-position field. The dashboard will not infer positions from match order. The raw innings records remain available under Innings records.")

# SCORING & CONSISTENCY
with tabs[2]:
    st.subheader("Scoring profile and consistency")
    if not innings.empty:
        valid = innings.dropna(subset=["Runs_num"]).copy()
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.histogram(valid, x="Runs_num", nbins=25, title="Score frequency",
                labels={"Runs_num":"Runs scored"}), use_container_width=True)
        with c2:
            milestone = pd.DataFrame({"Milestone": ["0", "1–19", "20–49", "50–99", "100+"],
                "Innings": [
                    int(valid["Runs_num"].eq(0).sum()),
                    int(valid["Runs_num"].between(1,19).sum()),
                    int(valid["Runs_num"].between(20,49).sum()),
                    int(valid["Runs_num"].between(50,99).sum()),
                    int(valid["Runs_num"].ge(100).sum())
                ]})
            st.plotly_chart(px.bar(milestone, x="Milestone", y="Innings", text="Innings",
                title="Runs-band frequency"), use_container_width=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("50+ scores", int(valid["Runs_num"].ge(50).sum()))
        c2.metric("100+ scores", int(valid["Runs_num"].ge(100).sum()))
        c3.metric("Fours", int(valid["Fours_num"].sum()) if valid["Fours_num"].notna().any() else "—")
        c4.metric("Sixes", int(valid["Sixes_num"].sum()) if valid["Sixes_num"].notna().any() else "—")
        if valid["Balls_num"].notna().any():
            valid["Rolling average (last 10 innings)"] = valid["Runs_num"].rolling(10, min_periods=3).mean()
            st.plotly_chart(px.line(valid, x="Match date" if valid["Match date"].notna().any() else valid.index,
                y="Rolling average (last 10 innings)", title="Rolling 10-innings run average"), use_container_width=True)
        if valid["Boundary_runs"].notna().any():
            st.caption("Boundary runs are calculated from fours and sixes where those columns are supplied by Statsguru.")
    else:
        st.info("No innings score rows are available.")

# OPPOSITION
with tabs[3]:
    st.subheader("Performance against each opponent")
    opp_col = first_col(innings, ["Opposition", "Opponent"])
    if opp_col and not innings.empty:
        opp = score_summary(innings.dropna(subset=["Runs_num"]), opp_col).sort_values("Runs", ascending=False)
        st.dataframe(opp.round(2), use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(opp, x=opp_col, y="Runs", title="Runs against each opponent"), use_container_width=True)
        with c2:
            y = "Average" if "Average" in opp else "Strike rate"
            st.plotly_chart(px.bar(opp, x=opp_col, y=y, title=f"{y} against each opponent"), use_container_width=True)
        show_download(opp, "kl_rahul_odi_opposition_splits.csv", "Download opposition splits")
    else:
        st.info("Opposition labels are not present in the innings table.")

# VENUES & SERIES
with tabs[4]:
    st.subheader("Ground and series performance")
    venue_col = first_col(innings, ["Ground", "Venue"])
    left, right = st.columns(2)
    with left:
        st.markdown("**Venue-level batting**")
        if venue_col and not innings.empty:
            venue = score_summary(innings.dropna(subset=["Runs_num"]), venue_col).sort_values("Runs", ascending=False)
            st.dataframe(venue.round(2), use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(venue.head(20), x=venue_col, y="Runs", title="Top venues by runs"), use_container_width=True)
            show_download(venue, "kl_rahul_odi_venue_splits.csv", "Download venue splits")
        elif not grounds.empty:
            st.dataframe(grounds, use_container_width=True, hide_index=True)
        else:
            st.info("Venue split not available.")
    with right:
        st.markdown("**Statsguru series batting splits**")
        if not series.empty:
            st.dataframe(series, use_container_width=True, hide_index=True)
            show_download(series, "kl_rahul_odi_series_splits.csv", "Download series splits")
        else:
            st.info("Series split not available.")

# YEAR BY YEAR
with tabs[5]:
    st.subheader("Season-by-season ODI performance")
    if not innings.empty and innings["Year"].notna().any():
        annual = score_summary(innings.dropna(subset=["Year", "Runs_num"]), "Year").sort_values("Year")
        annual["Year"] = annual["Year"].astype(int)
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(annual, x="Year", y="Runs", text="Runs", title="Runs by calendar year"), use_container_width=True)
        with c2:
            st.plotly_chart(px.line(annual, x="Year", y="Strike rate", markers=True, title="Annual strike rate"), use_container_width=True)
        st.dataframe(annual.round(2), use_container_width=True, hide_index=True)
        show_download(annual, "kl_rahul_odi_yearly_splits.csv", "Download yearly splits")
    else:
        st.info("A usable date field is required for yearly analysis.")

# INNINGS RECORDS
with tabs[6]:
    st.subheader("Every available ODI batting innings")
    if not innings.empty:
        st.caption(f"{len(innings):,} innings rows returned by the public innings table. Rows are not silently filled or fabricated.")
        st.dataframe(innings, use_container_width=True, hide_index=True)
        show_download(innings, "kl_rahul_odi_all_innings.csv", "Download all ODI innings (CSV)")
    else:
        st.info("No innings rows are available.")

# COVERAGE / QUALITY
with tabs[7]:
    st.subheader("Source coverage and completeness")
    a, b, c = st.columns(3)
    a.metric("Innings records collected", len(innings))
    b.metric("Match-history rows", len(history))
    c.metric("Resolved match IDs", int(coverage["match_id"].notna().sum()) if not coverage.empty and "match_id" in coverage else 0)
    if not coverage.empty:
        st.markdown("**Resolved match references**")
        st.dataframe(coverage.drop(columns=["last_error"], errors="ignore"), use_container_width=True, hide_index=True)
        show_download(coverage, "kl_rahul_odi_source_coverage.csv", "Download coverage report")
    if not match_list.empty:
        st.markdown("**Statsguru match-list source rows**")
        st.dataframe(match_list, use_container_width=True, hide_index=True)
    errors = st.session_state.get("source_errors", [])
    if errors:
        with st.expander(f"Collection notes ({len(errors)} source messages)"):
            for err in errors:
                st.write("• " + str(err))
    st.info("This dashboard uses career aggregates, innings tables, match lists, series splits and venue splits only. It does not request ball-by-ball feeds or infer missing match records, scores, batting positions or dismissals.")

st.divider()
st.caption("Independent cricket research dashboard · Public ESPNcricinfo Statsguru data via cricdata · Not affiliated with ESPNcricinfo. Coverage depends on the source pages and may contain historical gaps.")
