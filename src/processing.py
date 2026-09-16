"""Normalize odds while preserving the event, player, side, and handicap."""

import numpy as np
import pandas as pd

COLUMNS = [
    "game_id",
    "sport",
    "commence_time",
    "home_team",
    "away_team",
    "bookmaker",
    "last_update",
    "market",
    "player_name",
    "outcome",
    "line",
    "contract_line",
    "price",
]
CONTRACT = ["game_id", "market", "player_name", "contract_line"]


def _american_to_decimal(odds_arr):
    odds = np.asarray(odds_arr, dtype=float)
    if not np.isfinite(odds).all() or (np.abs(odds) < 100).any():
        raise ValueError(
            "American odds must be finite with absolute value at least 100."
        )
    return np.where(odds > 0, 1 + odds / 100, 1 + 100 / np.abs(odds))


def _maybe_convert_to_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def flatten_odds_to_df(odds_json, market="h2h"):
    records = []
    for game in odds_json:
        game_id = (
            game.get("id")
            or f"{game.get('home_team')}_vs_{game.get('away_team')}_{game.get('commence_time')}"
        )
        for book in game.get("bookmakers", []):
            for item in book.get("markets", []):
                if item.get("key") != market:
                    continue
                for outcome in item.get("outcomes", []):
                    side = outcome.get("name")
                    line = outcome.get("point")
                    contract_line = line
                    if (
                        market == "spreads"
                        and side == game.get("away_team")
                        and line is not None
                    ):
                        contract_line = -float(line)
                    records.append(
                        {
                            "game_id": game_id,
                            "sport": game.get("sport_key"),
                            "commence_time": game.get("commence_time"),
                            "home_team": game.get("home_team"),
                            "away_team": game.get("away_team"),
                            "bookmaker": book.get("title") or book.get("key"),
                            "last_update": item.get("last_update")
                            or book.get("last_update"),
                            "market": market,
                            "player_name": outcome.get("description"),
                            "outcome": side,
                            "line": line,
                            "contract_line": contract_line,
                            "price": outcome.get("price"),
                        }
                    )
    out = pd.DataFrame(records, columns=COLUMNS)
    for col in ["price", "line", "contract_line"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def complete_two_way(group):
    """Require the actual opposing sides, not just two arbitrary rows."""
    names = set(group["outcome"])
    market = group["market"].iloc[0]
    if market in ("h2h", "spreads"):
        expected = {group["home_team"].iloc[0], group["away_team"].iloc[0]}
    elif market == "totals" or str(market).startswith("player_"):
        expected = {"Over", "Under"}
    else:
        return False
    if market != "h2h" and group["contract_line"].isna().any():
        return False
    if str(market).startswith("player_") and group["player_name"].isna().any():
        return False
    return len(expected) == 2 and names == expected


def odds_to_probs(df, price_col="price", market_col="game_id", odds_format="auto"):
    """Remove margin within each bookmaker and identical two-way contract.

    Set odds_format explicitly for API data. Auto detection is only a convenience
    for legacy mixed-format inputs; large decimal odds are otherwise ambiguous.
    Incomplete or invalid markets retain NaN devig probabilities.
    """
    if price_col not in df:
        raise ValueError(f"price column '{price_col}' not found in DataFrame")
    if odds_format not in ("auto", "decimal", "american"):
        raise ValueError("odds_format must be auto, decimal, or american.")
    out = df.copy().reset_index(drop=True)
    prices = pd.to_numeric(out[price_col], errors="coerce")
    mask = (
        (prices <= -100) | (prices >= 100)
        if odds_format == "auto"
        else pd.Series(odds_format == "american", index=out.index)
    )
    decimal = prices.to_numpy(dtype=float).copy()
    if mask.any():
        decimal[mask] = _american_to_decimal(prices.loc[mask].to_numpy())
    valid = np.isfinite(decimal) & (decimal > 1)
    out["decimal_odds"] = np.where(valid, decimal, np.nan)
    out["implied_prob"] = 1 / out["decimal_odds"]
    out["devig_prob"] = np.nan
    keys = [market_col] + [
        col
        for col in ["bookmaker", "market", "player_name", "contract_line", "timestamp"]
        if col in out and col != market_col
    ]
    for _, group in out.groupby(keys, dropna=False):
        if group["implied_prob"].isna().any():
            continue
        if "outcome" in group:
            if not complete_two_way(group) or group["outcome"].duplicated().any():
                continue
        elif len(group) != 2:
            continue
        out.loc[group.index, "devig_prob"] = (
            group["implied_prob"] / group["implied_prob"].sum()
        )
    return out


def clean_odds(raw_data, market="h2h", odds_format="decimal"):
    return odds_to_probs(flatten_odds_to_df(raw_data, market), odds_format=odds_format)
