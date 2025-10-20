"""Utilities for cleaning sportsbook odds responses."""

from typing import List, Dict, Any

import numpy as np
import pandas as pd


def _american_to_decimal(odds_arr: np.ndarray) -> np.ndarray:
    """Convert American odds (e.g. -140, +120) to decimal odds."""
    odds = np.array(odds_arr, dtype=float)
    dec = np.empty_like(odds)
    pos = odds > 0
    neg = ~pos
    # for positive American odds: +120 -> 2.2  (120/100 + 1)
    dec[pos] = (odds[pos] / 100.0) + 1.0
    # for negative American odds: -140 -> 1 + 100/140
    dec[neg] = (100.0 / -odds[neg]) + 1.0
    return dec


def _maybe_convert_to_numeric(series: pd.Series) -> pd.Series:
    # Try to coerce string values like "+120" or "-140" to numeric
    return pd.to_numeric(series.astype(str).str.replace(r'^\+', '', regex=True), errors="coerce")


def flatten_odds_to_df(odds_json: List[Dict[str, Any]], market: str = "h2h") -> pd.DataFrame:
    """
    Flatten TheOddsAPI-like JSON to a tidy DataFrame with columns:
      ['game_id', 'sport', 'commence_time', 'home_team', 'away_team',
       'bookmaker', 'last_update', 'market', 'outcome', 'price']
    Parameters:
      odds_json: list (API response)
      market: market key to extract (e.g., "h2h", "spreads", "totals")
    """
    records = []
    for game in odds_json:
        game_id = f"{game.get('home_team','')}_vs_{game.get('away_team','')}_{game.get('commence_time','')}"
        sport = game.get("sport_key") or game.get("sport")
        commence_time = game.get("commence_time")
        home_team = game.get("home_team")
        away_team = game.get("away_team")

        for bookmaker in game.get("bookmakers", []):
            bookie = bookmaker.get("title")
            last_update = bookmaker.get("last_update")
            for m in bookmaker.get("markets", []):
                if m.get("key") != market:
                    continue
                for outcome in m.get("outcomes", []):
                    # price could be under 'price' or 'odds' depending on API variant
                    price = outcome.get("price", outcome.get("odds", outcome.get("price_decimal")))
                    records.append({
                        "game_id": game_id,
                        "sport": sport,
                        "commence_time": commence_time,
                        "home_team": home_team,
                        "away_team": away_team,
                        "bookmaker": bookie,
                        "last_update": last_update,
                        "market": m.get("key"),
                        "outcome": outcome.get("name") or outcome.get("outcome") or outcome.get("outcome_name"),
                        "price": price
                    })

    df = pd.DataFrame(records)
    # standardize price column to numeric where possible (strip '+' sign)
    if "price" in df.columns:
        df["price"] = _maybe_convert_to_numeric(df["price"])
    return df


def odds_to_probs(df: pd.DataFrame, price_col: str = "price", market_col: str = "game_id") -> pd.DataFrame:
    """
    Convert odds to implied probabilities and de-vig per market grouping.
    - Detects whether odds are decimal or American by heuristic:
        If any price <= 0 or abs(price) >= 100 -> treat as American.
        Otherwise treat as decimal.
    - Adds these columns to the returned DataFrame:
        'decimal_odds', 'implied_prob', 'devig_prob'
    Parameters:
      df: DataFrame containing at least [price_col, market_col]
      price_col: name of the column which stores the odds
      market_col: grouping column name used to de-vig across outcomes (game or market id)
    """
    if price_col not in df.columns:
        raise ValueError(f"price column '{price_col}' not found in DataFrame")

    # make a copy to avoid accidental mutation
    out = df.copy()

    # coerce to numeric (strip plus sign)
    out[price_col] = _maybe_convert_to_numeric(out[price_col])
    if out[price_col].isna().any():
        # keep NaNs but warn
        pass

    # Heuristic: decide odds format per-row: if any absolute value >= 100 or negative -> american
    # We'll create decimal odds column robustly:
    # For rows that look like American, convert; otherwise assume decimal.
    is_american = (out[price_col] <= 0) | (out[price_col].abs() >= 100)
    # Convert arrays
    dec = out[price_col].to_numpy(dtype=float)
    if is_american.any():
        # convert only american rows
        am_mask = is_american.to_numpy()
        dec_converted = dec.copy()
        dec_converted[am_mask] = _american_to_decimal(dec[am_mask])
        dec_converted[~am_mask] = dec[~am_mask]  # keep existing decimal values
        out["decimal_odds"] = dec_converted
    else:
        out["decimal_odds"] = dec

    # implied probability
    out["implied_prob"] = 1.0 / out["decimal_odds"]

    # devig across each market grouping
    totals = out.groupby(market_col)["implied_prob"].transform("sum")
    with np.errstate(divide="ignore", invalid="ignore"):
        out["devig_prob"] = np.where(
            totals <= 0,
            out["implied_prob"],
            out["implied_prob"] / totals,
        )

    return out
def clean_odds(raw_data: List[Dict[str, Any]], market: str = "h2h") -> pd.DataFrame:
    """Flatten odds JSON and add implied and de-vig probabilities."""

    flattened = flatten_odds_to_df(raw_data, market=market)
    if flattened.empty:
        return flattened
    return odds_to_probs(flattened, price_col="price", market_col="game_id")
