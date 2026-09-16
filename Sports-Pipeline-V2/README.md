# Exploratory multi-sport notebook dashboard

This earlier interface adds NFL, NBA, and MLB selection, local response caching, EV arithmetic, and export controls. The maintained entry points are the [root CLI and Streamlit app](../README.md).

From the repository root, install `requirements.txt`, set `ODDS_API_KEY` in your environment, and open `jupyter lab Sports-Pipeline-V2/sports_market_dashboard.ipynb`.

The notebook imports `odds_utils.py`, `ev_calculator.py`, and `widgets_ui.py`. Normalization reuses the main pipeline's bookmaker/contract grouping. `true_prob` is retained as a legacy column name for a devigged market estimate. It is not an independently learned probability; calculating EV from a bookmaker's own prices does not establish a predictive edge.

The cache expires after 30 minutes; on an API failure, stale cached results may be returned and logged. Treat those as historical snapshots. Runtime caches, logs, and exports are ignored by Git. This interface has offline helper checks; live fetching requires your own key and has not been validated against a paid subscription here.
