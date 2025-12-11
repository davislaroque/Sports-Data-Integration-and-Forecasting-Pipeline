# Sports Pipeline V2

A Jupyter-first dashboard for scanning NFL, NBA, and MLB betting markets, devigging odds, and surfacing high-expected-value bets with risk-adjusted rankings.

## Requirements
- Python 3.11
- Install dependencies: `pip install -r requirements.txt` (core libs: requests, pandas, numpy, scipy, ipywidgets, plotly)
- Environment variable: `ODDS_API_KEY` must be set for The Odds API.

## Running the Notebook
1. Launch Jupyter: `jupyter notebook Sports-Pipeline-V2/sports_market_dashboard.ipynb`.
2. Select the sport from the dropdown and click **Fetch Odds**.
3. Optionally toggle **Show Only High-EV Bets (EV ≥ 2%)** or export the results to CSV.

## Caching
- Cached responses live in `data/cache/` with a 30-minute freshness window.
- Raw API responses are saved to `data/raw_odds/` for debugging.
- If the API fails or rate limits hit, the dashboard automatically falls back to cache or skips missing lines without crashing.

## EV vs EV_adj
- **EV**: Standard expected value per $1 stake using devigged true probabilities.
- **EV_adj**: Variance-adjusted EV = EV − λ × Var(EV) with λ defaulting to 0.5 to reward lower-risk opportunities.

## Kelly Sizing
- Uses half-Kelly (0.5x) on the devigged probability and caps suggested stake at 5% of bankroll.
- Bets with EV ≥ 2% show a ✅ Bet flag; otherwise they are labeled ❌ Pass.

## Logging
- Runtime logs are written to `logs/app.log` and displayed inline in the notebook output.
- Info logs cover API/cache loads and EV calculations; warnings surface missing/invalid lines; errors capture API failures.

## File Map
- `sports_market_dashboard.ipynb`: Main interactive UI.
- `odds_utils.py`: API calls, caching, odds conversion, and devigging. (# [Refactor Note] markers highlight reused components.)
- `ev_calculator.py`: EV, variance-adjusted EV, and Kelly sizing helpers.
- `widgets_ui.py`: IPyWidgets layout, formatting, and table rendering.
- `data/`: Cache and raw odds storage.
- `logs/app.log`: Runtime log output.
