"""Top-level package exports for the sports data pipeline."""

from .analysis import detect_arbitrage, detect_discrepancies, find_best_odds, implied_prob, parse_market
from .ingestion import (
    fetch_odds,
    fetch_player_props,
    props_to_dataframe,
    save_snapshot,
    update_canonical_table,
)
from .processing import clean_odds, flatten_odds_to_df, odds_to_probs

__all__ = [
    "detect_arbitrage",
    "detect_discrepancies",
    "find_best_odds",
    "implied_prob",
    "parse_market",
    "fetch_odds",
    "fetch_player_props",
    "props_to_dataframe",
    "save_snapshot",
    "update_canonical_table",
    "clean_odds",
    "flatten_odds_to_df",
    "odds_to_probs",
]
