# src/analysis.py

"""Utilities for inspecting sportsbook odds data."""

from typing import Dict, Any

import pandas as pd

def parse_market(game: Dict[str, Any], market_key: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse a specific market from a single game.
    Returns nested dict: outcome -> {bookmaker, price}.
    """
    parsed = {}
    for bookmaker in game.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] == market_key:
                for outcome in market.get("outcomes", []):
                    name = outcome["name"]
                    price = outcome["price"]
                    if name not in parsed or price > parsed[name]["price"]:
                        parsed[name] = {"bookmaker": bookmaker["title"], "price": price}
    return parsed


def find_best_odds(parsed_market: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Return the highest odds per outcome (already handled in parse_market).
    Simply returns parsed_market for clarity.
    """
    return parsed_market


def implied_prob(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return 1 / decimal_odds


def detect_arbitrage(best_odds: Dict[str, Dict[str, Any]]):
    """
    Check for arbitrage opportunities in a two-outcome market.
    Returns profit margin (%) if arbitrage exists, else None.
    """
    if len(best_odds) != 2:
        return None  # Only works for two-outcome markets (H2H, spreads, totals)

    probs = [implied_prob(data["price"]) for data in best_odds.values()]
    total_prob = sum(probs)

    if total_prob < 1:
        return round((1 - total_prob) * 100, 2)
    return None


def detect_discrepancies(df: pd.DataFrame, market_key: str = "h2h") -> pd.DataFrame:
    """
    Detect arbitrage opportunities across games for a given market.
    Works for 2-outcome markets (H2H, spreads, totals).
    """

    df = df[df["market"] == market_key].copy()
    results = []

    for game_id, game_df in df.groupby("game_id"):
        home = game_df["home_team"].iloc[0]
        away = game_df["away_team"].iloc[0]

        # get best odds per outcome
        best_indices = game_df.groupby("outcome")["price"].idxmax()
        best_odds = game_df.loc[best_indices].reset_index(drop=True)

        # skip if not 2 outcomes
        if len(best_odds) != 2:
            continue  

        # compute implied probabilities
        best_odds["implied_prob"] = best_odds["price"].apply(lambda x: 1/x)
        total_prob = best_odds["implied_prob"].sum()

        arb_margin = (1 - total_prob) * 100 if total_prob < 1 else None

        # record results for both outcomes
        for _, row in best_odds.iterrows():
            results.append({
                "game_id": game_id,
                "home_team": home,
                "away_team": away,
                "market": market_key,
                "outcome": row["outcome"],
                "best_bookmaker": row["bookmaker"],
                "best_price": row["price"],
                "implied_prob": row["implied_prob"],
                "arbitrage_margin": arb_margin
            })

    return pd.DataFrame(results)

