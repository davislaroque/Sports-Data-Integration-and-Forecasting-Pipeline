"""IPyWidgets helpers for the sports betting dashboard."""
import logging
import os
from typing import Callable, Dict, List

import ipywidgets as widgets
import pandas as pd
from IPython.display import display

from ev_calculator import enrich_dataframe
from odds_utils import (
    DEFAULT_SPORTS,
    add_true_probabilities,
    fetch_odds,
    standardize_odds,
)

logger = logging.getLogger(__name__)


EV_THRESHOLDS = [0.0, 0.01, 0.02]
EV_COLORS = ["#ffcccc", "#fff3cd", "#d4edda"]


def style_ev(val: float) -> str:
    """Return CSS style for EV cells based on thresholds."""
    if val < EV_THRESHOLDS[1]:
        return f"background-color: {EV_COLORS[0]}"
    if val < EV_THRESHOLDS[2]:
        return f"background-color: {EV_COLORS[1]}"
    return f"background-color: {EV_COLORS[2]}"


def build_tables(df: pd.DataFrame) -> Dict[str, pd.io.formats.style.Styler]:
    """Create styled tables for all games and high-EV subset."""
    if df.empty:
        return {}
    base = df.copy()
    base["EV %"] = (base["ev"] * 100).round(2)
    base["EV_adj %"] = (base["ev_adj"] * 100).round(2)
    base["Kelly %"] = (base["kelly_fraction"] * 100).round(2)
    base["Decision"] = base["bet_flag"].map({True: "✅ Bet", False: "❌ Pass"})

    tooltip_text = base.apply(
        lambda r: f"Implied: {r['implied_prob']:.2%}\nTrue: {r['true_prob']:.2%}\nEV: {r['ev']:.2%}\nEV_adj: {r['ev_adj']:.2%}",
        axis=1,
    )
    tooltip_df = pd.DataFrame({"EV %": tooltip_text, "EV_adj %": tooltip_text}, index=base.index)

    styled_all = (
        base.style.applymap(style_ev, subset=["EV %", "EV_adj %"])
        .format({"EV %": "{:.2f}", "EV_adj %": "{:.2f}", "Kelly %": "{:.2f}"})
        .set_tooltips(tooltip_df)
    )
    high_ev = base[base["ev"] >= 0.02].copy().sort_values("ev_adj", ascending=False)
    styled_high = (
        high_ev.style.applymap(style_ev, subset=["EV %", "EV_adj %"])
        .format({"EV %": "{:.2f}", "EV_adj %": "{:.2f}", "Kelly %": "{:.2f}"})
        .set_tooltips(tooltip_df.loc[high_ev.index])
    )
    return {"all": styled_all, "high": styled_high}


def render_log_output(log_path: str = os.path.join("logs", "app.log")) -> widgets.Textarea:
    """Display the latest logs inside the notebook."""
    content = ""
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            content = f.read()
    return widgets.Textarea(value=content, layout=widgets.Layout(width="100%", height="200px"))


def build_dashboard(fetch_fn: Callable[..., pd.DataFrame]) -> None:
    """Assemble interactive widgets and hook up callbacks."""
    sport_dd = widgets.Dropdown(options=list(DEFAULT_SPORTS.keys()), description="Sport:")
    fetch_btn = widgets.Button(description="Fetch Odds", button_style="primary")
    filter_cb = widgets.Checkbox(value=False, description="Show Only High-EV Bets (EV ≥ 2%)")
    export_btn = widgets.Button(description="📥 Export Results")
    log_output = widgets.Output()
    table_output = widgets.Output()

    def on_fetch(_):
        table_output.clear_output()
        log_output.clear_output()
        with table_output:
            api_key = os.getenv("ODDS_API_KEY", "")
            if not api_key:
                print("Missing ODDS_API_KEY in environment.")
                return
            sport_key = DEFAULT_SPORTS.get(sport_dd.value)
            raw_games = fetch_fn(api_key=api_key, sport_key=sport_key)
            if not raw_games:
                print("No data available (API error or empty cache).")
                return
            standardized = standardize_odds(raw_games, market_keys=["h2h", "spreads"])
            with_true = add_true_probabilities(standardized, group_col="game_id")
            enriched = enrich_dataframe(with_true)
            tables = build_tables(enriched)
            if not tables:
                print("No valid odds to display.")
                return
            show_table = tables["high"] if filter_cb.value else tables["all"]
            display(show_table)
        with log_output:
            display(render_log_output())

    def on_export(_):
        api_key = os.getenv("ODDS_API_KEY", "")
        if not api_key:
            print("Missing ODDS_API_KEY in environment.")
            return
        sport_key = DEFAULT_SPORTS.get(sport_dd.value)
        raw_games = fetch_fn(api_key=api_key, sport_key=sport_key)
        standardized = standardize_odds(raw_games, market_keys=["h2h", "spreads"])
        enriched = enrich_dataframe(add_true_probabilities(standardized, group_col="game_id"))
        if enriched.empty:
            print("No data to export.")
            return
        path = os.path.join("data", f"ev_export_{sport_key}_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}.csv")
        enriched.to_csv(path, index=False)
        print(f"Exported to {path}")

    fetch_btn.on_click(on_fetch)
    export_btn.on_click(on_export)

    controls = widgets.HBox([sport_dd, fetch_btn, filter_cb, export_btn])
    display(controls, table_output, log_output)
