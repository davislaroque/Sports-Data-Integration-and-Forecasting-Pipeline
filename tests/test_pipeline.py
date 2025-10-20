import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import analysis
from src.ingestion import props_to_dataframe
from src.processing import clean_odds, flatten_odds_to_df, odds_to_probs


@pytest.fixture(scope="module")
def sample_json():
    sample_path = Path(__file__).parents[1] / "data" / "sample_odds.json"
    with sample_path.open() as fp:
        return json.load(fp)


def test_flatten_odds_creates_expected_rows(sample_json):
    df = flatten_odds_to_df(sample_json, market="h2h")
    assert not df.empty
    assert set(["game_id", "bookmaker", "market", "price", "outcome"]).issubset(df.columns)
    assert len(df) == 6  # 3 markets * 2 outcomes each


def test_odds_to_probs_handles_decimal_and_american():
    raw = pd.DataFrame(
        {
            "game_id": ["g1", "g1", "g2", "g2"],
            "price": [1.9, 2.0, -110, +120],
        }
    )
    converted = odds_to_probs(raw, price_col="price", market_col="game_id")

    # decimal odds should remain roughly untouched
    dec_slice = converted[converted["game_id"] == "g1"]
    assert np.allclose(dec_slice["decimal_odds"].values, [1.9, 2.0])

    # American odds should be converted correctly
    am_slice = converted[converted["game_id"] == "g2"].sort_values("price")
    assert np.allclose(am_slice["decimal_odds"].values, [1 + 100 / 110, 1 + 120 / 100])

    # Devig probabilities should sum to 1 per game
    grouped = converted.groupby("game_id")["devig_prob"].sum()
    assert np.allclose(grouped.values, np.ones_like(grouped.values))


def test_clean_odds_pipeline_adds_probabilities(sample_json):
    cleaned = clean_odds(sample_json, market="h2h")
    assert set(["decimal_odds", "implied_prob", "devig_prob"]).issubset(cleaned.columns)
    grouped = cleaned.groupby("game_id")["devig_prob"].sum().round(6)
    assert np.allclose(grouped.values, np.ones_like(grouped.values))


def test_analysis_detects_arbitrage(sample_json):
    df = flatten_odds_to_df(sample_json, market="h2h")
    best_idx = df.groupby(["game_id", "outcome"])["price"].idxmax()
    best = df.loc[best_idx].reset_index(drop=True)
    game_groups = best.groupby("game_id")
    arbitrage_games = {}
    for game_id, group in game_groups:
        parsed = {
            row["outcome"]: {"price": row["price"], "bookmaker": row["bookmaker"]}
            for _, row in group.iterrows()
        }
        arbitrage_games[game_id] = analysis.detect_arbitrage(parsed)

    assert arbitrage_games["Los Angeles Lakers_vs_Miami Heat_2025-01-01T00:00:00Z"] is not None
    assert arbitrage_games["Denver Nuggets_vs_Phoenix Suns_2025-01-02T01:00:00Z"] is None


def test_props_to_dataframe_structure(sample_json):
    df = props_to_dataframe(sample_json, markets="h2h")
    expected_columns = {
        "timestamp",
        "game_id",
        "commence_time",
        "home_team",
        "away_team",
        "bookmaker",
        "last_update",
        "player_name",
        "market",
        "line",
        "price",
    }
    assert expected_columns.issubset(df.columns)
    assert len(df) == 6
