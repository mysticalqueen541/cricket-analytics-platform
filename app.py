import asyncio
import streamlit as st
import pandas as pd
import plotly.express as px
from collectors.espn_public import fetch_player_search, discover_matches_by_year, ProviderError
from storage.database import save_player, save_matches, read_table, update_match_status
from processing.metrics import batting_summary, coverage_summary

st.set_page_config(page_title="Cricket Analytics Platform",page_icon="🏏",layout="wide")
st.title("🏏 Cricket Analytics Platform")
st.caption("International cricket • ODI • Test • T20I • Player-first data collection")

def run(coro):
    try: return asyncio.run(coro)
    except RuntimeError: return asyncio.get_event_loop().run_until_complete(coro)

with st.sidebar:
    st.header("Player & format")
    player_query=st.text_input("Player name",placeholder="e.g. KL Rahul")
    fmt=st.selectbox("Format",["ODI","Test","T20I"])
    start_year=st.number_input("From year",min_value=1877,max_value=2100,value=2016,step=1)
    end_year=st.number_input("To year",min_value=int(start_year),max_value=2100,value=2026,step=1)
    search=st.button("Search player",type="primary",use_container_width=True)
    discover=st.button("Discover matches for selected player",use_container_width=True)

if search:
    if not player_query.strip(): st.warning("Enter a player name.")
    else:
        with st.spinner("Searching public player pages..."):
            try:
                candidates=run(fetch_player_search(player_query.strip()))
                st.session_state["player_candidates"]=candidates
                if not candidates: st.warning("No player candidates found. Search may be blocked or page markup may have changed.")
            except ProviderError as e: st.error(str(e))

candidates=st.session_state.get("player_candidates",[])
if candidates:
    labels=[f'{p["name"]} · ID {p["player_id"]}' for p in candidates]
    chosen=st.selectbox("Confirm the correct player identity",range(len(candidates)),format_func=lambda i:labels[i])
    if st.button("Use this player"):
        p=candidates[chosen]
        save_player(p)
        st.session_state["selected_player"]=p
        st.success(f'Selected {p["name"]}')

player=st.session_state.get("selected_player")
if player:
    st.subheader(f'Player: {player["name"]}')
    st.caption(f'Internal ESPN player ID: {player["player_id"]} · {player.get("profile_url","")}')
    if discover:
        years=range(int(start_year),int(end_year)+1)
        all_rows=[]; errors=[]
        progress=st.progress(0)
        for i,y in enumerate(years,1):
            try:
                rows=run(discover_matches_by_year(y,fmt))
                for r in rows:
                    r["player_id"]=player["player_id"]
                    # Discovery inventory is not yet proof the player appeared in the match.
                    r["discovery_source"]=f'ESPN results page {y}'
                all_rows.extend(rows)
            except ProviderError as e: errors.append(f"{y}: {e}")
            progress.progress(i/len(years))
        if all_rows:
            save_matches(all_rows)
            st.success(f"Discovered {len(all_rows)} candidate {fmt} matches across the selected years.")
            st.info("These are candidate match records from the format results pages. Player participation must be verified against scorecards before counting them as the player's career matches.")
        if errors:
            st.warning("Some years could not be checked:")
            for e in errors: st.write("• "+e)
        if not all_rows and not errors:
            st.info("No candidate matches were returned by the public page parser.")

matches=read_table("matches")
batting=batting_summary(read_table("batting"))
deliveries=read_table("deliveries")
summary=coverage_summary(matches)
st.divider()
st.subheader("Local data inventory")
c1,c2,c3,c4=st.columns(4)
c1.metric("Discovered matches",summary["matches"])
c2.metric("Scorecards stored",summary["scorecards"])
c3.metric("Complete delivery feeds",summary["deliveries"])
c4.metric("Delivery retrieval failures",summary["failed"])

if not matches.empty:
    st.subheader("Match coverage register")
    view=matches.copy()
    if player: view=view[view["player_id"].astype(str)==str(player["player_id"])]
    if fmt: view=view[view["format"]==fmt]
    st.dataframe(view, use_container_width=True,hide_index=True)
    st.download_button("Download match register (CSV)",view.to_csv(index=False).encode(),
                       "match_coverage.csv","text/csv")
else:
    st.info("Search for a player to begin. Discovery currently uses public ESPN results pages; if ESPN blocks a request, the year is explicitly reported as unavailable.")

if not batting.empty:
    st.subheader("Batting dataset")
    st.dataframe(batting,use_container_width=True,hide_index=True)
    if "runs" in batting:
        st.plotly_chart(px.histogram(batting,x="runs",nbins=20,title="Runs distribution"),use_container_width=True)
if not deliveries.empty:
    st.subheader("Delivery-level dataset")
    st.dataframe(deliveries,use_container_width=True,hide_index=True)

st.caption("No delivery data is generated or inferred. A match with a 403 remains in the discovery/coverage audit as a source failure, not a missing match.")
