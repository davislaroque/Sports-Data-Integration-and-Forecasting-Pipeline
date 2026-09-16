"""Evaluate forecasts using observed outcomes and explicit offered prices."""

import numpy as np


def _probabilities(values, name):
    array = np.asarray(values, dtype=float)
    if (
        array.ndim != 1
        or not len(array)
        or not np.isfinite(array).all()
        or ((array < 0) | (array > 1)).any()
    ):
        raise ValueError(f"{name} must be a nonempty one-dimensional array in [0, 1].")
    return array


def evaluate_accuracy(predictions, outcomes):
    probs = _probabilities(predictions, "predictions")
    actual = _probabilities(outcomes, "outcomes")
    if len(probs) != len(actual) or not np.isin(actual, [0, 1]).all():
        raise ValueError("Provide one observed binary outcome per prediction.")
    return float(np.mean((probs >= 0.5) == actual))


def backtest(
    predictions, outcomes, decimal_odds, threshold=0.55, stake=10, initial_bankroll=1000
):
    """Settle a fixed stake on the modeled outcome when its edge exceeds zero.

    Each row is an independently resolved binary bet. No push, partial settlement,
    or overlapping-exposure model is implemented. Prices alone cannot settle bets.
    """
    probs = _probabilities(predictions, "predictions")
    actual = _probabilities(outcomes, "outcomes")
    prices = np.asarray(decimal_odds, dtype=float)
    if prices.ndim == 0:
        prices = np.full(len(probs), prices)
    if (
        actual.shape != probs.shape
        or prices.shape != probs.shape
        or not np.isin(actual, [0, 1]).all()
    ):
        raise ValueError("Predictions, binary outcomes, and odds must align.")
    if not np.isfinite(prices).all() or (prices <= 1).any():
        raise ValueError("Decimal odds must be finite and greater than one.")
    if (
        not 0 <= threshold <= 1
        or not np.isfinite(stake)
        or stake <= 0
        or not np.isfinite(initial_bankroll)
        or initial_bankroll <= 0
    ):
        raise ValueError(
            "Use a probability threshold and positive finite stake and bankroll."
        )
    selected = (probs >= threshold) & (probs > 1 / prices)
    profits = np.where(selected, np.where(actual == 1, prices - 1, -1) * stake, 0)
    staked = float(selected.sum() * stake)
    profit = float(profits.sum())
    return {
        "final_bankroll": initial_bankroll + profit,
        "profit": profit,
        "total_staked": staked,
        "roi_on_staked": profit / staked if staked else 0.0,
        "bets": np.where(
            selected, np.where(actual == 1, "win", "loss"), "pass"
        ).tolist(),
    }
