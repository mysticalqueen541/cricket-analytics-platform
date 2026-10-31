# Cricket Analytics Platform

A Streamlit application for discovering a player's international career and building ODI, Test and T20I analysis datasets.

## Goals

- Search for a player and resolve the correct identity.
- Discover international matches by player and format without asking users to paste match URLs or IDs.
- Collect scorecards and, where publicly available, delivery-level data.
- Keep a per-match source and completeness audit.
- Analyse batting, bowling, innings, batting position and match context.
- Export CSV/Excel datasets.

## Important data policy

A match can be discovered even when its scorecard or commentary cannot be retrieved. HTTP 403, rate limits and parser failures are recorded as retrieval failures, never interpreted as evidence that a match did not happen. The app does not fabricate deliveries or silently claim full career coverage. Some historical ESPN pages/endpoints may not expose public ball-by-ball data.

The project uses public pages/endpoints only, conservative request pacing and caching. It does not attempt CAPTCHA, login-wall or access-control circumvention. Cricsheet is not used.

## Run locally

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Project layout

- `collectors/`: player and match discovery, scorecard and delivery collection
- `processing/`: normalization, metrics and validation
- `storage/`: local SQLite persistence
- `data/`: local database/cache (ignored by Git)

## Current collector status

The app is structured so discovery, scorecard retrieval and delivery retrieval have independent status. Provider adapters are deliberately isolated: if a public ESPN endpoint returns 403, the app reports it and preserves the match inventory rather than misreporting zero matches. Provider-specific fields can change; adapters should be updated and tested against current public responses before relying on large-scale collection.

## Coverage statuses

- `complete`: validated delivery data available
- `partial`: scorecard or some innings/deliveries available
- `failed`: source request failed
- `not_available`: source has no public delivery feed for this match
- `pending`: not yet attempted

## Roadmap

1. Verify player search and career match discovery against current provider responses.
2. Add tested scorecard parsers for formats and innings edge cases.
3. Add delivery parsers only for endpoints/pages that expose full public data.
4. Expand automated tests and coverage reconciliation.
