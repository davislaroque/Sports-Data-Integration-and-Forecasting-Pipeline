# Technical Notes & Deep Dive

This document supplements the project overview by focusing on implementation details, engineering trade-offs, and future enhancements.

## Data Model
The canonical odds table produced by `src.ingestion.props_to_dataframe` contains the following schema:

| Column | Description |
| --- | --- |
| `timestamp` | UTC timestamp when the ingestion ran. |
| `game_id` | Stable identifier from The Odds API. |
| `commence_time` | Scheduled start time of the matchup. |
| `home_team` / `away_team` | Participating teams. |
| `bookmaker` | Sportsbook name. |
| `last_update` | Provider timestamp for this bookmaker-market pair. |
| `player_name` | Player associated with the prop (if applicable). |
| `market` | Market key (e.g., `h2h`, `player_points`). |
| `line` | Line/handicap for the outcome. |
| `price` | Decimal odds. |

## Module Responsibilities
- **`src/ingestion.py`** – encapsulates API I/O. Functions are pure where possible, accept parameters for sport/market configuration, and persist snapshots to disk. `_require_api_key` centralizes secrets handling.
- **`src/processing.py`** – provides deterministic helpers for flattening JSON into tidy DataFrames and for normalizing prices (American ↔ decimal) before devigging probabilities. `clean_odds` chains the helpers for end-to-end cleaning.
- **`src/analysis.py`** – offers composable utilities (`parse_market`, `find_best_odds`, `detect_arbitrage`, `detect_discrepancies`) used in notebooks and the Streamlit dashboard.
- **`src/features.py` / `src/modeling.py`** – starter feature generation and regression models; both accept pandas objects to stay notebook-friendly.
- **`web/app.py`** – Streamlit application that loads live data when credentials are available or defaults to the curated fixture. Visuals highlight the best available price per outcome and arbitrage margin when detected.

## Testing Strategy
Pytest cases live in `tests/` and cover:
- JSON flattening and structural integrity of the ingestion layer.
- Conversion heuristics for decimal and American odds.
- The probability math that ensures devigged probabilities sum to one per market.
- Arbitrage detection logic based on the curated sample odds.

Run the suite with `pytest`; CI integration can be added with GitHub Actions using the same command.

## Reproducible Analytics
- All notebooks should be checked in with outputs or committed as executed `.ran` artifacts.
- Sample data in `data/sample_odds.json` mirrors the format returned by The Odds API, enabling deterministic demos and unit tests.
- When running live ingestion, snapshots are timestamped and appended to a canonical CSV, making it simple to replay or backtest historical odds.

## Future Enhancements
1. **Data Quality** – add validation rules that flag stale bookmaker updates or missing outcomes.
2. **Modeling Depth** – expand feature generation to include opponent defensive stats and rest days; integrate gradient boosting models.
3. **Alerting** – build a lightweight scheduler that publishes Slack/webhook notifications when arbitrage margins exceed a configurable threshold.
4. **Deployment** – package ingestion/processing as a CLI (`python -m src.cli ingest`) and containerize the Streamlit UI for one-click deployment.

Keeping these notes alongside the high-level README ensures recruiters can quickly grasp both the story *and* the engineering rigor behind the project.
