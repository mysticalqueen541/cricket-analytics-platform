"""KL Rahul ODI analytics dashboard — fixed-player edition."""
from datetime import datetime
import re
import pandas as pd
import plotly.express as px
import streamlit as st

from collectors.cricdata_source import make_client, collect_format_career, SourceError
from storage.database import save_player, save_dataset, load_dataset, save_coverage_rows, load_coverage
from config import REQUEST_DELAY_SECONDS

PLAYER_ID = "422108"  # ESPNcricinfo Statsguru profile ID for KL Rahul
PLAYER_NAME = "KL Rahul"
FORMAT = "odi"

st.set_page_config(page_title="KL Rahul | ODI Analytics", page_icon="🏏", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1500px; padding-top: 1.3rem;}
[data-testid="stMetric"] {background: rgba(128,128,128,.08); padding: 13px; border-radius: 12px;}
h1 {letter-spacing: -.035em;}
.muted {opacity: .72; font-size: .9rem;}
</style>
""", unsafe_allow_html=True)

def frame(dataset):
    rows = load_dataset(PLAYER_ID, FORMAT, dataset)
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def first_col(df, candidates):
    return next((c for c in candidates if c in df.columns), None)

def numeric(df, candidates):
    col = first_col(df, candidates)
    if not col:
        return pd.Series(float("nan"), index=df.index)
    return pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce")

def collect():
    client = make_client()
    result = collect_format_career(client, PLAYER_ID, FORMAT)
    save_player(PLAYER_ID, PLAYER_NAME, {"source": "ESPNcricinfo Statsguru", "format": "ODI"})
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
    return result["errors"]

def load_or_refresh():
    if st.button("↻ Refresh latest ODI records", type="secondary"):
        st.session_state["force_refresh"] = True
    should_fetch = st.session_state.pop("force_refresh", False)
    existing = frame("innings_batting")
    if should_fetch or existing.empty:
        with st.spinner("Loading KL Rahul's ODI career and innings records from public ESPNcricinfo pages…"):
            try:
                errors = collect()
                st.session_state["source_errors"] = errors
                st.session_state["last_loaded"] = datetime.now().strftime("%d %b %Y, %H:%M")
            except Exception as exc:
                st.error(f"Could not load the public Statsguru records: {exc}")
                st.info("Previously saved records, if available, remain on this device.")
    else:
        st.session_state.setdefault("last_loaded", "Saved local dataset")

st.title("🏏 KL Rahul — ODI Career Analytics")
st.caption("A single-player, single-format dashboard · ODI debut to latest available match · Public ESPNcricinfo Statsguru records")
load_or_refresh()

career_rows = load_dataset(PLAYER_ID, FORMAT, "career_batting")
career = career_rows[0] if career_rows else {}
innings = frame("innings_batting")
history = frame("match_history")
series = frame("series_batting")
grounds = frame("grounds_batting")
coverage = load_coverage(PLAYER_ID, FORMAT)

if innings.empty and not career:
    st.warning("No KL Rahul ODI records have been saved yet. Check your internet connection and use Refresh latest ODI records.")
    st.stop()

runs_col = first_col(innings, ["Runs", "R", "runs"])
balls_col = first_col(innings, ["BF", "Balls", "B", "balls"])
date_col = first_col(innings, ["Start Date", "Date", "Match Date"])
opp_col = first_col(innings, ["Opposition", "Opponent"])
ground_col = first_col(innings, ["Ground", "Venue"])
pos_col = first_col(innings, ["Pos", "Batting Position", "Batting position", "position", "Bat Pos"])
dismissal_col = first_col(innings, ["Dismissal", "How Out", "Dismissal Type", "Dismissal type"])

if not innings.empty:
    innings["runs_numeric"] = numeric(innings, ["Runs", "R", "runs"])
    innings["balls_numeric"] = numeric(innings, ["BF", "Balls", "B", "balls"])
    innings["strike_rate_calc"] = innings["runs_numeric"] / innings["balls_numeric"].replace(0, pd.NA) * 100
    if date_col:
        innings["match_date"] = pd.to_datetime(innings[date_col], errors="coerce", dayfirst=True)
        innings["year"] = innings["match_date"].dt.year
    if pos_col:
        innings["batting_position"] = pd.to_numeric(innings[pos_col], errors="coerce")

matches = career.get("Mat", career.get("Matches", "—"))
runs = career.get("Runs", career.get("R", "—"))
average = career.get("Ave", career.get("Avg", "—"))
strike_rate = career.get("SR", "—")
hundreds = career.get("100", career.get("100s", "—"))
fifties = career.get("50", career.get("50s", "—"))
high_score = career.get("HS", "—")
balls_faced = career.get("BF", "—")

st.caption(f"Data last loaded: {st.session_state.get('last_loaded', 'not recorded')} · ESPNcricinfo player ID: {PLAYER_ID}")
k1,k2,k3,k4,k5,k6 = st.columns(6)
for col, label, value in [
    (k1,"ODI matches",matches),(k2,"Runs",runs),(k3,"Batting average",average),
    (k4,"Strike rate",strike_rate),(k5,"100s / 50s",f"{hundreds} / {fifties}"),(k6,"Highest score",high_score)
]:
    col.metric(label, value if value not in (None,"") else "—")

tabs = st.tabs(["Career overview","Batting position","Innings analysis","Opposition & venues","Year-by-year","Records & coverage"])

with tabs[0]:
    st.subheader("Career at a glance")
    left,right = st.columns([1.1,1])
    with left:
        st.markdown("**Career batting summary — source values**")
        summary = pd.DataFrame([career]) if career else pd.DataFrame()
        if not summary.empty:
            st.dataframe(summary, use_container_width=True, hide_index=True)
        else:
            st.info("Career summary is not currently available from the source.")
    with right:
        st.markdown("**Runs per innings**")
        if not innings.empty and runs_col:
            chart = innings.dropna(subset=["runs_numeric"])
            st.plotly_chart(px.histogram(chart, x="runs_numeric", nbins=18, labels={"runs_numeric":"Runs"}, title="Distribution of innings scores"), use_container_width=True)
        else:
            st.info("Innings score data unavailable.")
    if not history.empty:
        st.markdown("**Match history inventory**")
        st.dataframe(history, use_container_width=True, hide_index=True)
    errors = st.session_state.get("source_errors", [])
    if errors:
        with st.expander(f"Source retrieval notes ({len(errors)})"):
            for err in errors: st.write("• " + str(err))

with tabs[1]:
    st.subheader("How has his batting position affected his ODI output?")
    if pos_col and not innings.empty:
        posdf = innings.dropna(subset=["batting_position","runs_numeric"]).copy()
        if not posdf.empty:
            posdf["batting_position"] = posdf["batting_position"].astype(int)
            if dismissal_col:
                d = posdf[dismissal_col].fillna("").astype(str).str.lower().str.strip()
                posdf["is_out"] = ~d.isin(["","-","not out","retired hurt","absent","did not bat","dnb"])
            else:
                posdf["is_out"] = True
            grouped = posdf.groupby("batting_position").agg(
                Innings=("runs_numeric","count"), Runs=("runs_numeric","sum"),
                Balls=("balls_numeric","sum"), Outs=("is_out","sum"),
                Hundreds=("runs_numeric",lambda s:int((s>=100).sum())),
                Fifties=("runs_numeric",lambda s:int(((s>=50)&(s<100)).sum())),
                Highest=("runs_numeric","max")
            ).reset_index()
            fours_col = first_col(posdf, ["4s", "Fours", "4"])
            sixes_col = first_col(posdf, ["6s", "Sixes", "6"])
            if fours_col:
                posdf["_fours"] = pd.to_numeric(posdf[fours_col], errors="coerce").fillna(0)
                grouped["Fours"] = posdf.groupby("batting_position")["_fours"].sum().values
            if sixes_col:
                posdf["_sixes"] = pd.to_numeric(posdf[sixes_col], errors="coerce").fillna(0)
                grouped["Sixes"] = posdf.groupby("batting_position")["_sixes"].sum().values
            grouped["Average"] = grouped["Runs"] / grouped["Outs"].replace(0,pd.NA)
            grouped["Strike rate"] = grouped["Runs"] / grouped["Balls"].replace(0,pd.NA) * 100
            grouped = grouped.rename(columns={"batting_position":"Position"})
            a,b = st.columns([1.1,1])
            with a:
                st.dataframe(grouped.round(2), use_container_width=True, hide_index=True)
            with b:
                st.plotly_chart(px.bar(grouped, x="Position", y="Runs", text="Runs", title="Career runs by batting position"), use_container_width=True)
            st.plotly_chart(px.bar(grouped, x="Position", y="Average", text="Average", title="Batting average by position"), use_container_width=True)
            st.caption("Position aggregates are calculated from the available innings rows. Average uses dismissals inferred from the source dismissal field; if that field is absent, the displayed average is not reliable.")
        else:
            st.info("The innings table contains a position field, but usable position/run values were not returned.")
    else:
        st.warning("The retrieved ESPNcricinfo innings table does not expose a recognised batting-position column. Position analysis is deliberately not inferred from score order or match number.")

with tabs[2]:
    st.subheader("Innings-level performance")
    if not innings.empty:
        c1,c2,c3 = st.columns(3)
        c1.metric("Innings records",len(innings))
        c2.metric("Runs in innings table",int(innings["runs_numeric"].sum()) if innings["runs_numeric"].notna().any() else "—")
        c3.metric("Balls faced in innings table",int(innings["balls_numeric"].sum()) if innings["balls_numeric"].notna().any() else "—")
        if date_col and innings["match_date"].notna().any():
            trend = innings.dropna(subset=["match_date","runs_numeric"]).sort_values("match_date")
            st.plotly_chart(px.line(trend,x="match_date",y="runs_numeric",markers=True,title="Runs in each ODI innings"),use_container_width=True)
        if dismissal_col:
            dismissal_counts = innings[dismissal_col].fillna("Not recorded").astype(str).value_counts().rename_axis("Dismissal").reset_index(name="Innings")
            st.markdown("**Dismissal breakdown**")
            st.plotly_chart(px.bar(dismissal_counts, x="Dismissal", y="Innings", title="Dismissal types in recorded innings"), use_container_width=True)
        st.dataframe(innings.drop(columns=["match_date"],errors="ignore"),use_container_width=True,hide_index=True)
        st.download_button("Download ODI innings CSV",innings.to_csv(index=False).encode("utf-8-sig"),"kl_rahul_odi_innings.csv","text/csv")
    else:
        st.info("No innings-level batting rows are available.")

with tabs[3]:
    st.subheader("Opposition and venue splits")
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Against each opposition**")
        if opp_col and not innings.empty:
            opp = innings.groupby(opp_col).agg(Innings=("runs_numeric","count"),Runs=("runs_numeric","sum"),Balls=("balls_numeric","sum"),Highest=("runs_numeric","max")).reset_index()
            opp["Strike rate"] = opp["Runs"] / opp["Balls"].replace(0,pd.NA) * 100
            st.dataframe(opp.round(2),use_container_width=True,hide_index=True)
            st.plotly_chart(px.bar(opp,x=opp_col,y="Runs",title="Runs by opposition"),use_container_width=True)
        else: st.info("Opposition field unavailable in innings records.")
    with c2:
        st.markdown("**At each venue**")
        if ground_col and not innings.empty:
            venue = innings.groupby(ground_col).agg(Innings=("runs_numeric","count"),Runs=("runs_numeric","sum"),Balls=("balls_numeric","sum"),Highest=("runs_numeric","max")).reset_index()
            venue["Strike rate"] = venue["Runs"] / venue["Balls"].replace(0,pd.NA) * 100
            st.dataframe(venue.round(2),use_container_width=True,hide_index=True)
            st.plotly_chart(px.bar(venue,x=ground_col,y="Runs",title="Runs by venue"),use_container_width=True)
        elif not grounds.empty:
            st.dataframe(grounds,use_container_width=True,hide_index=True)
        else: st.info("Venue field unavailable in innings records.")
    if not series.empty:
        st.markdown("**Statsguru series batting splits**")
        st.dataframe(series,use_container_width=True,hide_index=True)

with tabs[4]:
    st.subheader("Year-by-year ODI performance")
    if not innings.empty and "year" in innings.columns and innings["year"].notna().any():
        annual = innings.dropna(subset=["year"]).groupby("year").agg(Innings=("runs_numeric","count"),Runs=("runs_numeric","sum"),Balls=("balls_numeric","sum"),Highest=("runs_numeric","max")).reset_index()
        annual["Strike rate"] = annual["Runs"] / annual["Balls"].replace(0,pd.NA) * 100
        st.plotly_chart(px.bar(annual,x="year",y="Runs",text="Runs",title="ODI runs by calendar year"),use_container_width=True)
        st.dataframe(annual.round(2),use_container_width=True,hide_index=True)
    else:
        st.info("Year trend requires a parseable match date in the source innings rows.")
    if not history.empty:
        st.markdown("**Match appearances by year / source match list**")
        st.dataframe(history,use_container_width=True,hide_index=True)

with tabs[5]:
    st.subheader("Records, source coverage and data quality")
    st.markdown("**Official public career summary returned by Statsguru**")
    if career: st.dataframe(pd.DataFrame([career]),use_container_width=True,hide_index=True)
    else: st.info("Career summary unavailable.")
    cov = pd.DataFrame(coverage)
    if not cov.empty:
        x,y,z = st.columns(3)
        x.metric("Match IDs resolved",len(cov))
        y.metric("Scorecards marked complete",int(cov.get("scorecard_status",pd.Series(dtype=str)).eq("complete").sum()))
        z.metric("Match-history rows",len(history))
        st.dataframe(cov.drop(columns=["last_error"],errors="ignore"),use_container_width=True,hide_index=True)
    st.caption("No ball-by-ball feeds are requested or stored by this dashboard. Match IDs and innings rows are shown only when resolved from source pages; missing records are not fabricated.")
    if not history.empty:
        st.download_button("Download match-history CSV",history.to_csv(index=False).encode("utf-8-sig"),"kl_rahul_odi_match_history.csv","text/csv")

st.divider()
st.caption("Independent research dashboard. Source: public ESPNcricinfo Statsguru pages via cricdata. Data availability and historical coverage depend on the source.")
