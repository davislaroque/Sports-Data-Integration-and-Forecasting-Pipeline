"""Streamlit application for exploring NBA odds discrepancies."""

import json
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd
import streamlit as st

from src import analysis
from src.ingestion import DEFAULT_MARKET, fetch_player_props
from src.processing import clean_odds

SAMPLE_DATA_PATH = Path(__file__).parents[1] / "data" / "sample_odds.json"


def _load_sample_json() -> List[Dict[str, Any]]:
    with SAMPLE_DATA_PATH.open() as fp:
        return json.load(fp)


def _load_data(market: str, use_live: bool) -> pd.DataFrame:
    if use_live:
        try:
            raw = fetch_player_props(markets=market)
        except ValueError as exc:
            st.warning(f"{exc}. Falling back to bundled sample odds.")
            raw = _load_sample_json()
    else:
        raw = _load_sample_json()

    cleaned = clean_odds(raw, market=market)
    return cleaned


def _build_summary(cleaned: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []
    for game_id, group in cleaned.groupby("game_id"):
        best = (
            group.sort_values("price", ascending=False)
            .groupby("outcome", as_index=False)
            .first()
        )
        odds_map = {
            row.outcome: {"price": row.price, "bookmaker": row.bookmaker}
            for row in best.itertuples()
        }
        arbitrage_margin = analysis.detect_arbitrage(odds_map)
        for row in best.itertuples():
            summary_rows.append(
                {
                    "game_id": game_id,
                    "home_team": row.home_team,
                    "away_team": row.away_team,
                    "outcome": row.outcome,
                    "best_price": row.price,
                    "best_bookmaker": row.bookmaker,
                    "arbitrage_margin_pct": arbitrage_margin,
                }
            )
    if not summary_rows:
        return pd.DataFrame(columns=[
            "game_id",
            "home_team",
            "away_team",
            "outcome",
            "best_price",
            "best_bookmaker",
            "arbitrage_margin_pct",
        ])
    return pd.DataFrame(summary_rows)


def main():
    st.set_page_config(page_title="NBA Odds Pipeline", page_icon="🏀", layout="wide")
    st.title("NBA Odds Pipeline Dashboard")
    st.write(
        "Compare sportsbook prices, surface arbitrage opportunities, and validate the data pipeline end-to-end."
    )

    market = st.sidebar.selectbox(
        "Market",
        options=["h2h", "totals", "spreads", DEFAULT_MARKET],
        index=0,
    )
    use_live = st.sidebar.toggle("Fetch live data (requires API key)", value=False)

    cleaned = _load_data(market, use_live)

    if cleaned.empty:
        st.info("No odds returned for the selected market.")
        return

    summary = _build_summary(cleaned)

    st.subheader("Best Prices per Outcome")
    st.dataframe(summary, use_container_width=True)

    arb_games = summary.dropna(subset=["arbitrage_margin_pct"]).drop_duplicates("game_id")
    if not arb_games.empty:
        st.subheader("Arbitrage Opportunities")
        for row in arb_games.itertuples():
            st.metric(
                label=f"{row.home_team} vs {row.away_team}",
                value=f"{row.arbitrage_margin_pct:.2f}% edge",
                help="Combined implied probability across books is below 100%.",
            )
    else:
        st.subheader("Arbitrage Opportunities")
        st.write("No arbitrage edges detected in the current dataset.")

    st.subheader("Cleaned Odds (with Probabilities)")
    st.dataframe(cleaned, use_container_width=True)


if __name__ == "__main__":
    main()
