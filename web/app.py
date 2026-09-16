"""Explore sample odds or explicitly request live data with a five-minute cache."""

import json
from pathlib import Path
import streamlit as st
from src.analysis import detect_discrepancies
from src.ingestion import fetch_player_props
from src.processing import clean_odds

ROOT = Path(__file__).resolve().parents[1]


@st.cache_data(ttl=300, show_spinner=False)
def load_live(market, event_id):
    return fetch_player_props(markets=market, event_id=event_id or None)


def main():
    st.set_page_config(
        page_title="NBA Odds Data Pipeline", page_icon="🏀", layout="wide"
    )
    st.title("NBA Odds Data Pipeline")
    st.write(
        "Compare equivalent sportsbook quotes and inspect the data behind each result."
    )
    live = st.sidebar.toggle("Use live Odds API data", value=False)
    market = st.sidebar.selectbox(
        "Market", ["h2h", "totals", "spreads", "player_points"]
    )
    event_id = (
        st.sidebar.text_input("Event ID (required for live player props)")
        if market == "player_points"
        else ""
    )
    if live:
        try:
            with st.spinner("Loading odds..."):
                raw = load_live(market, event_id)
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.caption(
            "Live data, cached for five minutes. Quotes may change before execution."
        )
    else:
        raw = json.loads((ROOT / "data/sample_odds.json").read_text())
        st.caption(
            "Synthetic sample data with fictional bookmakers. These are not current offers."
        )
    cleaned = clean_odds(raw, market)
    if cleaned.empty:
        st.info(
            "No quotes for this market. The sample fixture covers h2h; choose h2h to explore the demo."
        )
        return
    report = detect_discrepancies(cleaned, market)
    st.subheader("Best price for each outcome")
    st.dataframe(report, hide_index=True)
    st.download_button(
        "Download comparison CSV",
        report.to_csv(index=False),
        "best_odds.csv",
        "text/csv",
    )
    st.caption(
        "arbitrage_margin is theoretical equal-payout return on total stake, in percent. It assumes complete matched outcomes, available prices, and no fees or limits."
    )
    st.subheader("Normalized quotes")
    st.dataframe(cleaned, hide_index=True)
    st.caption(
        "devig_prob removes margin within one bookmaker and contract. It is a market-derived estimate, not a calibrated model probability."
    )


if __name__ == "__main__":
    main()
