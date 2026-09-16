"""Postgame feature rows for next-game prediction, with explicit target dates."""

import pandas as pd


def build_features(df):
    required = {"player", "date", "points", "rebounds", "assists"}
    if not required <= set(df):
        raise ValueError(f"Missing columns: {sorted(required - set(df))}")
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    if out.duplicated(["player", "date"]).any():
        raise ValueError("Expected one row per player and date.")
    out = out.sort_values(["player", "date"])
    for stat in ["points", "rebounds", "assists"]:
        out[f"{stat}_rolling_avg"] = out.groupby("player")[stat].transform(
            lambda values: values.rolling(5, min_periods=1).mean()
        )
    out["target_points"] = out.groupby("player")["points"].shift(-1)
    out["target_date"] = out.groupby("player")["date"].shift(-1)
    return out.dropna(subset=["target_points", "target_date"])
