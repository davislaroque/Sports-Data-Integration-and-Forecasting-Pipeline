"""Odds retrieval and caching utilities for the Jupyter dashboard.

Key features
------------
- Fetch odds from The Odds API for NFL, NBA, MLB with caching.
- Store raw responses for diagnostics.
- Convert odds to American format and implied probabilities.
- Graceful fallbacks when data is missing or API fails.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

# Logging setup
LOG_PATH = os.path.join("logs", "app.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4/sports"
DEFAULT_REGION = "us"
DEFAULT_MARKETS = "h2h,spreads"
DEFAULT_SPORTS = {
    "NFL": "americanfootball_nfl",
    "NBA": "basketball_nba",
    "MLB": "baseball_mlb",
}
CACHE_DIR = os.path.join("data", "cache")
RAW_DIR = os.path.join("data", "raw_odds")
CACHE_TTL_MINUTES = 30


# [Refactor Note] Adapted from src/processing.py in the original project.
def _american_to_decimal(odds_arr: np.ndarray) -> np.ndarray:
    """Convert American odds (e.g. -140, +120) to decimal odds."""
    odds = np.array(odds_arr, dtype=float)
    dec = np.empty_like(odds)
    pos = odds > 0
    neg = ~pos
    dec[pos] = (odds[pos] / 100.0) + 1.0
    dec[neg] = (100.0 / -odds[neg]) + 1.0
    return dec


# [Refactor Note] Adapted from src/processing.py to standardize numeric odds inputs.
def _maybe_convert_to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(r"^\+", "", regex=True), errors="coerce")


def _decimal_to_american(decimal_odds: float) -> Optional[float]:
    """Convert decimal odds to American odds.

    Returns ``None`` when conversion is not possible (e.g., invalid value).
    """
    try:
        if decimal_odds <= 1:
            return None
        if decimal_odds >= 2:
            return round((decimal_odds - 1) * 100, 2)
        return round(-100 / (decimal_odds - 1), 2)
    except Exception:
        return None


def _build_cache_key(params: Dict[str, Any]) -> str:
    serial = json.dumps(params, sort_keys=True)
    return hashlib.md5(serial.encode()).hexdigest()


def _cache_file_path(cache_key: str) -> str:
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def _is_cache_fresh(path: str, ttl_minutes: int = CACHE_TTL_MINUTES) -> bool:
    if not os.path.exists(path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.utcnow() - mtime < timedelta(minutes=ttl_minutes)


def _load_cache(path: str) -> Optional[List[Dict[str, Any]]]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to load cache %s: %s", path, exc)
        return None


def _save_cache(path: str, data: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception as exc:
        logger.warning("Failed to write cache %s: %s", path, exc)


def _save_raw(path: str, data: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"saved_at": datetime.utcnow().isoformat(), "data": data}, f, indent=2)


def _fetch_from_api(api_key: str, sport: str, markets: str, regions: str = DEFAULT_REGION) -> List[Dict[str, Any]]:
    url = f"{BASE_URL}/{sport}/odds"
    params = {
        "apiKey": api_key,
        "markets": markets,
        "regions": regions,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_odds(
    api_key: str,
    sport_key: str,
    markets: str = DEFAULT_MARKETS,
    regions: str = DEFAULT_REGION,
    use_cache: bool = True,
    cache_ttl_minutes: int = CACHE_TTL_MINUTES,
) -> List[Dict[str, Any]]:
    """Fetch odds with caching and graceful fallback.

    Parameters
    ----------
    api_key : str
        Odds API key.
    sport_key : str
        Sport key accepted by The Odds API.
    markets : str
        Comma-separated markets to request (e.g., ``"h2h,spreads"``).
    regions : str
        Region code.
    use_cache : bool
        Whether to prefer cached responses when available.
    cache_ttl_minutes : int
        Freshness window for cached data.
    """
    params = {"sport": sport_key, "markets": markets, "regions": regions}
    cache_key = _build_cache_key(params)
    cache_path = _cache_file_path(cache_key)

    if use_cache and _is_cache_fresh(cache_path, ttl_minutes=cache_ttl_minutes):
        cached = _load_cache(cache_path)
        if cached is not None:
            logger.info("Loaded odds from cache for %s", sport_key)
            return cached

    try:
        data = _fetch_from_api(api_key, sport_key, markets, regions)
        _save_cache(cache_path, data)
        raw_name = f"{sport_key}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.json"
        _save_raw(os.path.join(RAW_DIR, raw_name), data)
        logger.info("Fetched odds from API for %s", sport_key)
        return data
    except Exception as exc:
        logger.error("API fetch failed for %s: %s", sport_key, exc)
        cached = _load_cache(cache_path)
        if cached is not None:
            logger.warning("Using stale cache for %s due to API error", sport_key)
            return cached
        logger.warning("No cache available; returning empty list for %s", sport_key)
        return []


def _flatten_market(game: Dict[str, Any], market_key: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for bookmaker in game.get("bookmakers", []):
        bookie = bookmaker.get("title")
        last_update = bookmaker.get("last_update")
        for market in bookmaker.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                price = outcome.get("price", outcome.get("odds", outcome.get("price_decimal")))
                rows.append(
                    {
                        "game_id": game.get("id") or f"{game.get('home_team')}_vs_{game.get('away_team')}_{game.get('commence_time')}",
                        "sport_key": game.get("sport_key"),
                        "commence_time": game.get("commence_time"),
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "bookmaker": bookie,
                        "last_update": last_update,
                        "market": market_key,
                        "outcome": outcome.get("name") or outcome.get("description") or outcome.get("team"),
                        "price_decimal": _maybe_convert_to_numeric(pd.Series([price])).iloc[0],
                    }
                )
    return rows


def standardize_odds(raw_games: List[Dict[str, Any]], market_keys: List[str]) -> pd.DataFrame:
    """Flatten and standardize odds for selected markets.

    Ensures all prices are converted to American odds with implied probabilities.
    Missing prices are skipped with warnings rather than raising exceptions.
    """
    records: List[Dict[str, Any]] = []
    for game in raw_games:
        for market_key in market_keys:
            rows = _flatten_market(game, market_key)
            if not rows:
                logger.warning("Missing market %s for game %s", market_key, game.get("id"))
                continue
            for row in rows:
                decimal_price = row.get("price_decimal")
                if pd.isna(decimal_price) or decimal_price is None or decimal_price <= 1:
                    logger.warning("Skipping missing/invalid price for %s", row.get("game_id"))
                    continue
                american_price = _decimal_to_american(float(decimal_price))
                if american_price is None:
                    logger.warning("Unable to convert decimal odds %s for %s", decimal_price, row.get("game_id"))
                    continue
                implied_prob = 1.0 / float(decimal_price)
                row.update({"odds_american": american_price, "implied_prob": implied_prob})
                records.append(row)
    return pd.DataFrame(records)


def devig_power_method(probabilities: List[float], power: float = 1.05) -> np.ndarray:
    """Compute devigged probabilities using the power method.

    Mathematically, we solve for ``p_true`` such that ``sum(p_true ** power) = 1``.
    This reweights implied probabilities to remove bookmaker margin while preserving
    outcome ordering. The exponent ``power`` (>1) deflates the probabilities.
    """
    probs = np.array(probabilities, dtype=float)
    probs = probs / probs.sum() if probs.sum() > 0 else probs
    with np.errstate(divide="ignore", invalid="ignore"):
        adjusted = probs ** (1 / power)
    total = adjusted.sum()
    if total <= 0:
        return probs
    return adjusted / total


def add_true_probabilities(df: pd.DataFrame, group_col: str = "game_id") -> pd.DataFrame:
    """Add devigged probabilities per game using the power method."""
    if df.empty:
        return df
    df = df.copy()
    df["true_prob"] = df.groupby(group_col)["implied_prob"].transform(
        lambda p: devig_power_method(p.tolist())
    )
    return df
