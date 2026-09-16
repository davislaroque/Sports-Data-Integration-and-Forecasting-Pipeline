import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
import requests

from src.analysis import detect_arbitrage, detect_discrepancies
from src.ingestion import fetch_player_props, props_to_dataframe, update_canonical_table
from src import ingestion
from src.processing import clean_odds, flatten_odds_to_df, odds_to_probs
from src.evaluation import backtest, evaluate_accuracy


@pytest.fixture
def sample_json():
    return json.loads((Path(__file__).parents[1] / "data/sample_odds.json").read_text())


def prop_fixture(player="Alex Demo", over=20.5, under=20.5, market="player_points"):
    return [
        {
            "id": "g1",
            "home_team": "Home",
            "away_team": "Away",
            "bookmakers": [
                {
                    "title": "Book",
                    "markets": [
                        {
                            "key": market,
                            "outcomes": [
                                {
                                    "name": "Over",
                                    "description": player,
                                    "point": over,
                                    "price": 2.1,
                                },
                                {
                                    "name": "Under",
                                    "description": player,
                                    "point": under,
                                    "price": 2.1,
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    ]


def test_flatten_retains_api_event_id_and_empty_schema(sample_json):
    frame = flatten_odds_to_df(sample_json)
    assert len(frame) == 6
    assert set(frame.game_id) == {"game_001", "game_002"}
    assert {"outcome", "player_name", "line", "contract_line"} <= set(frame)
    assert list(flatten_odds_to_df([])) == list(frame)


def test_probabilities_normalize_within_each_bookmaker(sample_json):
    frame = clean_odds(sample_json)
    sums = frame.groupby(["game_id", "bookmaker"]).devig_prob.sum()
    assert np.allclose(sums, 1)
    assert np.isclose(frame.loc[0, "devig_prob"], (1 / 1.95) / (1 / 1.95 + 1 / 2.2))


def test_odds_formats_and_invalid_prices():
    raw = pd.DataFrame({"game_id": ["g1", "g1"], "price": [-110, 120]})
    frame = odds_to_probs(raw, odds_format="american")
    assert np.allclose(frame.decimal_odds, [1 + 100 / 110, 2.2])
    large = odds_to_probs(
        pd.DataFrame({"game_id": ["g1", "g1"], "price": [101, 2]}),
        odds_format="decimal",
    )
    assert large.decimal_odds.iloc[0] == 101
    invalid = odds_to_probs(
        pd.DataFrame({"game_id": ["g1", "g1"], "price": [0, 2]}), odds_format="decimal"
    )
    assert invalid.devig_prob.isna().all()


def test_mismatched_lines_are_not_an_arbitrage():
    frame = clean_odds(prop_fixture(over=20.5, under=22.5), "player_points")
    assert frame.devig_prob.isna().all()
    assert detect_discrepancies(frame, "player_points").empty


def test_two_players_are_separate_contracts():
    raw = prop_fixture()
    second = prop_fixture(player="Casey Example")[0]["bookmakers"][0]["markets"][0][
        "outcomes"
    ]
    raw[0]["bookmakers"][0]["markets"][0]["outcomes"] += second
    frame = clean_odds(raw, "player_points")
    assert np.allclose(frame.groupby("player_name").devig_prob.sum(), 1)
    report = detect_discrepancies(frame, "player_points")
    assert len(report) == 4
    assert report.player_name.nunique() == 2


def test_spreads_match_opposite_handicaps():
    raw = prop_fixture(market="spreads")
    outcomes = raw[0]["bookmakers"][0]["markets"][0]["outcomes"]
    outcomes[0].update(name="Home", point=-3.5)
    outcomes[1].update(name="Away", point=3.5)
    for outcome in outcomes:
        outcome.pop("description")
    assert len(detect_discrepancies(clean_odds(raw, "spreads"), "spreads")) == 2
    outcomes[1]["point"] = 5.5
    assert detect_discrepancies(clean_odds(raw, "spreads"), "spreads").empty


def test_arbitrage_reports_equal_payout_roi(sample_json):
    assert detect_arbitrage({"A": {"price": 2.1}, "B": {"price": 2.1}}) == 5.0
    report = detect_discrepancies(clean_odds(sample_json))
    assert report.loc[report.game_id == "game_001", "arbitrage_margin"].notna().all()
    assert report.loc[report.game_id == "game_002", "arbitrage_margin"].isna().all()


def test_ingestion_retains_sides_and_history_is_idempotent(sample_json, tmp_path):
    frame = props_to_dataframe(sample_json, "h2h")
    assert frame.outcome.nunique() == 4
    path = tmp_path / "nested/history.csv"
    update_canonical_table(frame, path)
    update_canonical_table(frame, path)
    assert len(pd.read_csv(path)) == 6
    changed = frame.iloc[[0]].copy()
    changed["price"] = 2.5
    update_canonical_table(changed, path)
    assert len(pd.read_csv(path)) == 7


def test_player_props_require_event_and_use_event_endpoint(monkeypatch):
    calls = []

    def request(path, params):
        calls.append((path, params))
        return {"id": "event123", "bookmakers": []}

    monkeypatch.setattr(ingestion, "_request", request)
    with pytest.raises(ValueError, match="event_id"):
        fetch_player_props()
    assert calls == []
    assert fetch_player_props(event_id="event123") == [
        {"id": "event123", "bookmakers": []}
    ]
    assert calls[0][0] == "basketball_nba/events/event123/odds"
    assert calls[0][1]["markets"] == "player_points"


def test_http_timeouts_retries_and_errors_hide_credentials(monkeypatch):
    monkeypatch.setattr(ingestion, "_require_api_key", lambda: "fake-test-key")
    session = MagicMock()
    session.__enter__.return_value = session
    session.get.side_effect = requests.HTTPError("private URL with fake-test-key")
    monkeypatch.setattr(ingestion.requests, "Session", lambda: session)
    with pytest.raises(RuntimeError) as err:
        fetch_player_props(markets="h2h")
    assert "fake-test-key" not in str(err.value)
    assert session.get.call_args.kwargs["timeout"] == (5, 30)
    adapter = session.mount.call_args.args[1]
    assert adapter.max_retries.total == 2
    assert 429 in adapter.max_retries.status_forcelist


def test_backtest_requires_actual_outcomes():
    result = backtest([0.7, 0.7, 0.4], [0, 1, 1], [2, 3, 2])
    assert result["bets"] == ["loss", "win", "pass"]
    assert result["profit"] == 10
    assert result["roi_on_staked"] == 0.5
    with pytest.raises(ValueError):
        evaluate_accuracy([0.5], [])
