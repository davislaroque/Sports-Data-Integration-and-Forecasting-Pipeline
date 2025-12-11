"""Expected value, variance-adjusted EV, and Kelly sizing utilities."""
from typing import Optional

import numpy as np
import pandas as pd

from odds_utils import _american_to_decimal  # [Refactor Note]


def _american_implied_prob(american_odds: float) -> float:
    """Convert American odds to implied probability."""
    decimal = _american_to_decimal(np.array([american_odds]))[0]
    return 1.0 / decimal if decimal > 0 else 0.0


def compute_expected_value(american_odds: float, true_prob: float) -> float:
    """Compute expected value (per $1 stake) for American odds."""
    decimal = _american_to_decimal(np.array([american_odds]))[0]
    payout = decimal - 1.0
    lose_prob = 1.0 - true_prob
    return (true_prob * payout) - lose_prob


def compute_variance(american_odds: float, true_prob: float, ev: Optional[float] = None) -> float:
    """Return variance of the bet outcome for a $1 stake."""
    decimal = _american_to_decimal(np.array([american_odds]))[0]
    payout = decimal - 1.0
    expected = ev if ev is not None else compute_expected_value(american_odds, true_prob)
    return (true_prob * (payout - expected) ** 2) + ((1 - true_prob) * (-1 - expected) ** 2)


def compute_adjusted_ev(ev: float, variance: float, risk_aversion: float = 0.5) -> float:
    """Variance-penalized expected value."""
    return ev - risk_aversion * variance


def half_kelly_fraction(american_odds: float, true_prob: float, cap: float = 0.05) -> float:
    """Compute conservative Kelly fraction (0.5x) capped at ``cap``."""
    decimal = _american_to_decimal(np.array([american_odds]))[0]
    b = decimal - 1.0
    p = true_prob
    q = 1 - p
    full_kelly = ((b * p) - q) / b if b > 0 else 0.0
    half = max(0.0, full_kelly) * 0.5
    return min(half, cap)


def enrich_dataframe(df: pd.DataFrame, risk_aversion: float = 0.5) -> pd.DataFrame:
    """Add EV, variance-adjusted EV, and Kelly sizing to a standardized odds DataFrame."""
    if df.empty:
        return df
    out = df.copy()
    out["true_prob"].fillna(out.get("implied_prob"), inplace=True)

    out["ev"] = out.apply(lambda r: compute_expected_value(r["odds_american"], r["true_prob"]), axis=1)
    out["variance"] = out.apply(
        lambda r: compute_variance(r["odds_american"], r["true_prob"], r["ev"]), axis=1
    )
    out["ev_adj"] = out.apply(
        lambda r: compute_adjusted_ev(r["ev"], r["variance"], risk_aversion), axis=1
    )
    out["kelly_fraction"] = out.apply(
        lambda r: half_kelly_fraction(r["odds_american"], r["true_prob"]), axis=1
    )
    out["bet_flag"] = out["ev"] >= 0.02
    return out
