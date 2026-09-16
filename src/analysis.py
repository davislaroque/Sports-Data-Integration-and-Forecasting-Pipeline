"""Compare equivalent contracts and compute theoretical two-way arbitrage ROI."""

import math
import pandas as pd
from .processing import CONTRACT, clean_odds, complete_two_way


def implied_prob(decimal_odds):
    value = float(decimal_odds)
    if not math.isfinite(value) or value <= 1:
        raise ValueError("Decimal odds must be finite and greater than one.")
    return 1 / value


def parse_market(game, market_key):
    if market_key != "h2h":
        raise ValueError(
            "Use detect_discrepancies for totals, spreads, or player props."
        )
    frame = clean_odds([game], market=market_key)
    best = find_best_odds(frame)
    return {
        row.outcome: {"bookmaker": row.bookmaker, "price": row.decimal_odds}
        for row in best.itertuples()
    }


def find_best_odds(data):
    if isinstance(data, dict):
        return data
    valid = data.dropna(subset=["decimal_odds"]).copy()
    if valid.empty:
        return valid
    return (
        valid.sort_values("decimal_odds", ascending=False)
        .drop_duplicates(CONTRACT + ["outcome"])
        .reset_index(drop=True)
    )


def detect_arbitrage(best_odds):
    """Return equal-payout ROI (%) for an already matched two-outcome contract."""
    if len(best_odds) != 2:
        return None
    total = sum(implied_prob(item["price"]) for item in best_odds.values())
    return round((1 / total - 1) * 100, 4) if total < 1 else None


def detect_discrepancies(df, market_key="h2h"):
    columns = CONTRACT + [
        "home_team",
        "away_team",
        "outcome",
        "line",
        "best_bookmaker",
        "best_price",
        "implied_prob",
        "arbitrage_margin",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    best = find_best_odds(df.loc[df["market"] == market_key])
    for _, group in best.groupby(CONTRACT, dropna=False):
        if not complete_two_way(group):
            continue
        odds = {row.outcome: {"price": row.decimal_odds} for row in group.itertuples()}
        roi = detect_arbitrage(odds)
        for _, row in group.iterrows():
            rows.append(
                {
                    **{key: row[key] for key in CONTRACT},
                    "home_team": row.home_team,
                    "away_team": row.away_team,
                    "outcome": row.outcome,
                    "line": row.line,
                    "best_bookmaker": row.bookmaker,
                    "best_price": row.decimal_odds,
                    "implied_prob": row.implied_prob,
                    "arbitrage_margin": roi,
                }
            )
    return pd.DataFrame(rows, columns=columns)
