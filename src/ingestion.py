"""Functions for fetching and persisting odds data from The Odds API."""

from datetime import datetime
import os
from typing import Iterable, Mapping

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.the-odds-api.com/v4/sports"
DEFAULT_SPORT = "basketball_nba"
DEFAULT_MARKET = "player_points"
DEFAULT_REGION = "us"
DEFAULT_FORMAT = "decimal"


def _require_api_key() -> str:
    """Return the Odds API key or raise a helpful error message."""

    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        raise ValueError(
            "ODDS_API_KEY is not set. Create a .env file with 'ODDS_API_KEY=your_key' or export the variable "
            "before calling fetch_player_props."
        )
    return api_key


def fetch_player_props(
    sport: str = DEFAULT_SPORT,
    markets: str = DEFAULT_MARKET,
    regions: str = DEFAULT_REGION,
    odds_format: str = DEFAULT_FORMAT,
) -> Iterable[Mapping[str, object]]:
    """
    Fetch raw odds JSON from The Odds API.

    Parameters mirror the API; see https://the-odds-api.com/ for documentation. An
    ``ODDS_API_KEY`` must be provided either via environment variable or a ``.env`` file.
    """

    url = f"{BASE_URL}/{sport}/odds"
    params = {
        "apiKey": _require_api_key(),
        "markets": markets,
        "regions": regions,
        "oddsFormat": odds_format,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_odds(
    sport: str = DEFAULT_SPORT,
    markets: str = DEFAULT_MARKET,
    regions: str = DEFAULT_REGION,
    odds_format: str = DEFAULT_FORMAT,
) -> pd.DataFrame:
    """Fetch player props and flatten them into a DataFrame for quick analysis."""

    return props_to_dataframe(
        fetch_player_props(sport=sport, markets=markets, regions=regions, odds_format=odds_format),
        markets=markets,
    )


def props_to_dataframe(props_json, markets: str = DEFAULT_MARKET) -> pd.DataFrame:
    """
    Convert Odds API JSON to a flat pandas DataFrame with canonical fields.
    """
    records = []
    timestamp = datetime.utcnow().isoformat()
    
    for game in props_json:
        game_id = game["id"]
        home_team = game["home_team"]
        away_team = game["away_team"]
        commence_time = game["commence_time"]

        for bookmaker in game["bookmakers"]:
            book = bookmaker["title"]
            last_update = bookmaker["last_update"]

            for market in bookmaker["markets"]:
                if market["key"] != markets:
                    continue
                for outcome in market["outcomes"]:
                    records.append({
                        "timestamp": timestamp,
                        "game_id": game_id,
                        "commence_time": commence_time,
                        "home_team": home_team,
                        "away_team": away_team,
                        "bookmaker": book,
                        "last_update": last_update,
                        "player_name": outcome.get("description"),
                        "market": market["key"],
                        "line": outcome.get("point"),
                        "price": outcome.get("price")
                    })
    columns = [
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
    ]
    df = pd.DataFrame(records, columns=columns)
    return df

def save_snapshot(df, markets="player_points"):
    """
    Save DataFrame snapshot into data/ folder with timestamp in filename.
    """
    os.makedirs("data", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"data/odds_{markets}_{ts}.csv"
    df.to_csv(path, index=False)
    print(f"Saved snapshot → {path}")
    return path

def update_canonical_table(df, canonical_path="data/odds_canonical.csv"):
    """
    Append new odds snapshot into a canonical line-change table.
    """
    if os.path.exists(canonical_path):
        existing = pd.read_csv(canonical_path)
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    combined.to_csv(canonical_path, index=False)
    print(f"Canonical table updated → {canonical_path}")

if __name__ == "__main__":
    props_json = fetch_player_props(markets="player_points")
    df = props_to_dataframe(props_json, markets="player_points")
    save_snapshot(df, markets="player_points")
    update_canonical_table(df)
