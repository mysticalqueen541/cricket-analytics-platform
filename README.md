# KL Rahul ODI Analytics Dashboard

A fixed-player Streamlit dashboard for **KL Rahul's ODI career**, from his ODI debut on 11 June 2016 through the latest match available from the public source.

There is no player search, player selector, format selector, team explorer, or ball-by-ball workflow. The dashboard is dedicated to KL Rahul and ODI cricket.

## Dashboard sections

- **Career overview:** career batting summary, innings score distribution and match-history inventory.
- **Batting position:** innings, runs, average, strike rate, hundreds, fifties and highest score by batting position, when Statsguru exposes a usable position column.
- **Innings analysis:** individual ODI innings, score progression and CSV export.
- **Opposition & venues:** innings-level runs and scoring rates against opponents and at grounds, plus Statsguru series splits.
- **Year-by-year:** annual ODI runs and innings trends.
- **Records & coverage:** source career summary, resolved match-ID coverage and match-history export.

## Data source and collection

The app uses the fixed ESPNcricinfo Statsguru player ID `422108` for KL Rahul and requests only the ODI format (`class=2`). It uses the public-data Python package `cricdata` and public ESPNcricinfo Statsguru pages.

On first launch, the dashboard automatically attempts to load the career summary, match lists, innings-by-innings batting records, series splits and venue splits. Use **Refresh latest ODI records** to retrieve them again. Data is saved locally in `data/cricket_analytics.sqlite3`.

**No ball-by-ball feeds are requested.** No Cricsheet data is used. No player search, player input, format input, or manual match-ID entry is required.

## Batting-position analysis: important qualification

The position breakdown is calculated from the batting-position field in the retrieved innings records. If the public innings table does not return a position field, the dashboard will explicitly say so rather than infer a position from batting order, scorecard order, or another proxy. Averages by position require usable dismissal information; the dashboard labels this limitation where relevant.

The match list and batting innings list are separate source datasets. A match appearance does not necessarily mean Rahul batted in that match. Source gaps and unresolved match IDs are not filled with guessed records.

## Install on Windows

Python 3.10 or newer is required. Python 3.12 is a conservative choice; current `cricdata` metadata also declares Python 3.14 support.

1. Download the repository ZIP from GitHub and extract it.
2. Run `install_windows.bat`.
3. Run `run_windows.bat`.

Or install manually:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks activation:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

## Limitations

- This is an independent project, not affiliated with ESPNcricinfo.
- It relies on public pages and the behaviour of the third-party `cricdata` package.
- HTTP 403/429 responses, timeouts, parser changes or missing source fields can cause incomplete retrieval.
- A successful collection does not prove that every historical innings or match is represented.
- The dashboard does not fabricate missing scores, batting positions, match IDs, dismissal types or delivery-level metrics.
- No live end-to-end test against ESPNcricinfo has been claimed; validate the retrieved counts against the source career summary after running it locally.

## Repository

This project is separate from `irony-man/krishna-cricinfo-code`; that repository is not changed by this dashboard.
