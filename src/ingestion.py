"""Explicit live API access, normalized snapshots, and deduplicated CSV history."""

from datetime import datetime, timezone
import os
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from .processing import flatten_odds_to_df

BASE_URL = "https://api.the-odds-api.com/v4/sports"
DEFAULT_SPORT = "basketball_nba"
DEFAULT_MARKET = "player_points"
DEFAULT_REGION = "us"
DEFAULT_FORMAT = "decimal"
ROOT = Path(__file__).resolve().parents[1]


def _require_api_key():
    load_dotenv(ROOT / ".env")
    key = os.getenv("ODDS_API_KEY")
    if not key or key == "your_key_here":
        raise ValueError("Set ODDS_API_KEY in your environment or a local .env file.")
    return key


def _request(path, params):
    api_key = _require_api_key()
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        try:
            response = session.get(
                f"{BASE_URL}/{path}",
                params={**params, "apiKey": api_key},
                timeout=(5, 30),
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            # requests exception strings can include the credential-bearing URL.
            raise RuntimeError(
                "Odds API request failed. Check credentials, quota, market access, and connectivity."
            ) from None
        except ValueError:
            raise RuntimeError("Odds API returned invalid JSON.") from None


def fetch_events(sport=DEFAULT_SPORT):
    result = _request(f"{quote(sport, safe='')}/events", {})
    if not isinstance(result, list):
        raise RuntimeError("Expected a list of events from Odds API.")
    return result


def fetch_player_props(
    sport=DEFAULT_SPORT,
    markets=DEFAULT_MARKET,
    regions=DEFAULT_REGION,
    odds_format=DEFAULT_FORMAT,
    event_id=None,
):
    """Player props require an event ID; standard markets support bulk odds."""
    selected = {part.strip() for part in markets.split(",") if part.strip()}
    if not selected:
        raise ValueError("Select at least one market.")
    if odds_format not in ("decimal", "american"):
        raise ValueError("odds_format must be decimal or american.")
    if not event_id and not selected <= {"h2h", "spreads", "totals"}:
        raise ValueError(
            "Player props require event_id. Get an ID with fetch_events()."
        )
    path = f"{quote(sport, safe='')}/odds"
    if event_id:
        path = f"{quote(sport, safe='')}/events/{quote(str(event_id), safe='')}/odds"
    result = _request(
        path,
        {
            "markets": ",".join(sorted(selected)),
            "regions": regions,
            "oddsFormat": odds_format,
        },
    )
    if event_id:
        if not isinstance(result, dict) or "id" not in result:
            raise RuntimeError("Expected one event object from Odds API.")
        return [result]
    if not isinstance(result, list):
        raise RuntimeError("Expected an event list from Odds API.")
    return result


def props_to_dataframe(props_json, markets=DEFAULT_MARKET):
    frames = [
        flatten_odds_to_df(props_json, item.strip())
        for item in markets.split(",")
        if item.strip()
    ]
    if not frames:
        raise ValueError("Select at least one market.")
    frame = pd.concat(frames, ignore_index=True)
    frame.insert(0, "timestamp", datetime.now(timezone.utc).isoformat())
    return frame


def fetch_odds(
    sport=DEFAULT_SPORT,
    markets=DEFAULT_MARKET,
    regions=DEFAULT_REGION,
    odds_format=DEFAULT_FORMAT,
    event_id=None,
):
    raw = fetch_player_props(sport, markets, regions, odds_format, event_id)
    frame = props_to_dataframe(raw, markets)
    frame["odds_format"] = odds_format
    return frame


def save_snapshot(df, markets=DEFAULT_MARKET, output_dir=ROOT / "data"):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    label = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in markets)
    path = directory / f"odds_{label}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.csv"
    df.to_csv(path, index=False)
    return str(path)


def update_canonical_table(df, canonical_path=ROOT / "data/odds_canonical.csv"):
    path = Path(canonical_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = pd.read_csv(path) if path.exists() else pd.DataFrame()
    combined = pd.concat([existing, df], ignore_index=True)
    keys = [
        key
        for key in [
            "game_id",
            "bookmaker",
            "market",
            "player_name",
            "outcome",
            "line",
            "price",
            "last_update",
            "odds_format",
        ]
        if key in combined
    ]
    if keys:
        combined = combined.drop_duplicates(keys, keep="last")
    temp = path.with_suffix(path.suffix + ".tmp")
    combined.to_csv(temp, index=False)
    temp.replace(path)
    return str(path)


if __name__ == "__main__":
    from .demo import main

    main()
