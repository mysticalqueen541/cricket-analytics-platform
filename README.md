# Cricket Analytics Platform

Player-first international cricket data collection and analysis using Python, Streamlit, Pandas, Plotly, SQLite and the public-data client `cricdata`.

## What the app does

1. Search ESPNcricinfo for a player by name and select the correct identity.
2. Retrieve player career aggregates, match-by-match history and innings-by-innings records for ODI, Test and T20I.
3. Preserve the raw Statsguru rows and the source match links where those links are available.
4. Resolve match IDs from actual match links. The app does not invent IDs when link rows cannot be matched safely.
5. Attempt scorecards and delivery feeds independently for resolved matches.
6. Track each match's scorecard and delivery status, request errors and delivery-row counts.
7. Explore batting, bowling, innings and delivery records; download a ZIP of CSV datasets.

## Install on Windows

Use Python 3.11 or 3.12 if possible. The app does not require Playwright or a manually installed browser.

```powershell
cd cricket-analytics-platform
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks activation, run:
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

## Workflow

- Enter a player name (for example, KL Rahul), click **Search player**, and select the matching identity.
- Select ODI, Test and/or T20I, then click **Collect career datasets**.
- Review career summaries, match lists and innings.
- Go to **Coverage & deliveries**, set the delivery batch limit to 0 to attempt all resolved matches (or use a smaller batch first), and click **Fetch ball-by-ball**.
- Download all stored datasets from **Exports**.

## Data and coverage rules

- Career match lists, batting innings and bowling innings are different datasets; they are not interchangeable.
- A player can appear in a match without recording a batting innings. The match-list source determines the inventory; innings tables determine recorded innings.
- Match IDs are assigned only from actual ESPN match links when the parser can align the link rows with the provider's match rows. If the row counts do not match, IDs are left unresolved rather than guessed.
- Scorecards and ball-by-ball are attempted separately. A scorecard can succeed while deliveries fail, or vice versa.
- HTTP 403, 429, timeouts and parser errors are retrieval failures, not evidence that a match is absent.
- The app preserves provider fields and raw delivery JSON. It does not manufacture deliveries, extras, shot locations or wagon-wheel coordinates.
- Public source coverage varies by match and year. A successful run does not imply that every historical match has a complete delivery feed.

## Technical notes

- Uses the documented synchronous `CricinfoClient` interface; Streamlit does not call `asyncio.get_event_loop()`.
- Uses conservative sequential collection and a pause between provider requests.
- Local records are stored in `data/cricket_analytics.sqlite3` (ignored by Git).
- Data exports are CSV files packaged in a ZIP.
- Provider library: https://github.com/arnavbonigala/cricdata

## Troubleshooting

**Player search fails:** verify internet connectivity, update packages with `pip install --upgrade cricdata`, and retry later. If the provider denies access, the error is shown in the app.

**No match IDs resolved:** career text rows may still be available, but ESPN's Statsguru HTML links could not be aligned safely. The app reports unresolved IDs; it does not guess match identifiers.

**Some deliveries are missing:** check the coverage table. A 403/429, missing feed or provider error remains marked as a failure or unavailable status. Retry smaller batches after a pause.

## Disclaimer

This is an independent analytics tool and is not affiliated with ESPN or ESPNcricinfo. It uses publicly accessible source data subject to source availability and applicable terms. It does not bypass authentication, CAPTCHA or access restrictions.
