# Sports Data Integration and Forecasting Pipeline

A Python pipeline that turns nested sportsbook API responses into comparable market data. I built this project to connect API ingestion, data cleaning, probability calculations, and an interactive dashboard in one workflow.

**Python · REST APIs · pandas · ETL · Streamlit · scikit-learn · pytest · GitHub Actions**

## Explore the project

| Area | Implementation |
| --- | --- |
| API integration | [Timeouts, retry policy, event-level player props, and CSV history](src/ingestion.py) |
| Data modeling | [Event, bookmaker, player, outcome, and line identities](src/processing.py) |
| Analysis | [Equivalent-contract price comparisons and theoretical arbitrage](src/analysis.py) |
| Interface | [Sample/live dashboard with cached requests and CSV export](web/app.py) |
| Reproducibility | [Offline walkthrough](notebooks/player_prop_demo.ipynb) and [regression tests](tests/test_pipeline.py) |

## Run without an API key

Use Python 3.11 or 3.12. Run commands from the repository root.

```bash
git clone https://github.com/davislaroque/Sports-Data-Integration-and-Forecasting-Pipeline.git
cd Sports-Data-Integration-and-Forecasting-Pipeline
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.demo
python -m streamlit run web/app.py
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

The CLI uses the [synthetic sample fixture](data/README.md) and writes `artifacts/cleaned_odds.csv`, `artifacts/best_odds.csv`, and a deduplicated `artifacts/odds_history.csv`. It processes two sample events and six quotes. The dashboard labels the source and lets you download the comparison.

## Fetch live data

```bash
cp .env.example .env
# Add your own ODDS_API_KEY to .env
python -m src.demo --live --market h2h
```

Player props use an individual event endpoint. Get an event ID first:

```python
from src.ingestion import fetch_events, fetch_odds

events = fetch_events()
if events:
    player_props = fetch_odds(markets="player_points", event_id=events[0]["id"])
```

Or pass a current event ID to `python -m src.demo --live --market player_points --event-id EVENT_ID`. Requests require your own key, available markets, and sufficient quota. See [The Odds API v4 documentation](https://the-odds-api.com/liveapi/guides/v4/).

## Analysis decisions

- Keep each player and line separate. An Over 20.5 quote cannot be paired with an Under 22.5 quote.
- Match spread outcomes using the same home-team handicap, including the opposite sign for the away side.
- Remove bookmaker margin within one complete contract at one bookmaker. A one-sided market has no devig estimate.
- Convert explicitly supplied American odds to decimal before comparisons. Live requests use decimal odds by default.
- Report arbitrage as equal-payout return on total stake: `(1 / sum(1 / best_odds) - 1) * 100`.

Theoretical arbitrage assumes both outcomes can be executed at the displayed prices without fees or limits. Quotes can be stale. Devigged prices are market-derived estimates, not measured forecast accuracy or independent evidence of a betting edge.

## Forecasting scope

The market-data pipeline and dashboard are runnable. `src/features.py`, `src/modeling.py`, and `src/evaluation.py` are building blocks for separate player forecasting experiments. They are not connected to a trained forecasting service in this dashboard. Backtesting requires observed outcomes and offered odds; prices alone cannot determine wins or losses.

For a reproducible regression comparison, see [NBA Player Performance Forecasting](https://github.com/davislaroque/Sports_Prediction_Model).

## Checks and further work

```bash
python -m pytest -q
```

Tests cover endpoint routing with mocked HTTP, quote identity, odds conversion, incomplete markets, probability grouping, idempotent history writes, and settlement against actual outcomes. CI runs these without credentials.

The [technical notes](docs/README.md) describe the data contract and limits. The older [V2 notebook dashboard](Sports-Pipeline-V2/README.md) remains an exploratory interface. Future work includes timestamp-aware quote freshness checks and evaluating forecasts on real held-out results.
