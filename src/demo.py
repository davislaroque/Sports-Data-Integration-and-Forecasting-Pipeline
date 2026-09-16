"""Run sample odds through ingestion, processing, and reporting; opt in to live data."""

import argparse
import json
from pathlib import Path
from .analysis import detect_discrepancies
from .ingestion import (
    fetch_player_props,
    props_to_dataframe,
    update_canonical_table,
    ROOT,
)
from .processing import clean_odds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--market", choices=["h2h", "spreads", "totals", "player_points"], default="h2h"
    )
    parser.add_argument("--event-id", help="Required for live player props")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts")
    args = parser.parse_args()
    try:
        raw = (
            fetch_player_props(markets=args.market, event_id=args.event_id)
            if args.live
            else json.loads((ROOT / "data/sample_odds.json").read_text())
        )
        cleaned = clean_odds(raw, args.market)
        report = detect_discrepancies(cleaned, args.market)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        cleaned.to_csv(args.output_dir / "cleaned_odds.csv", index=False)
        report.to_csv(args.output_dir / "best_odds.csv", index=False)
        update_canonical_table(
            props_to_dataframe(raw, args.market), args.output_dir / "odds_history.csv"
        )
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    print(
        f"Source: {'live API' if args.live else 'synthetic sample fixture'} | Events: {len(raw)} | Quotes: {len(cleaned)}"
    )
    if report.empty:
        print("No complete two-way contracts available for this market.")
    else:
        print(
            report[
                ["home_team", "away_team", "outcome", "best_price", "arbitrage_margin"]
            ].to_string(index=False)
        )
    print(f"Reports saved to {args.output_dir}")


if __name__ == "__main__":
    main()
