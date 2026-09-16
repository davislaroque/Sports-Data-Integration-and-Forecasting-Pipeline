"""
interface.py
------------
Simple Streamlit dashboard to display model predictions vs. market odds.
"""

import streamlit as st
import pandas as pd


def run_interface(df):
    st.title("NBA Player Prop Model vs. Market")
    st.write("Compare model probabilities with sportsbook lines.")

    player = st.selectbox("Choose a player:", df["player"].unique())
    filtered = df[df["player"] == player]

    st.dataframe(filtered)

    st.bar_chart(filtered[["prob"]])
