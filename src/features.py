import pandas as pd

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling averages and other predictive features to player game logs.
    Expects columns: player, date, points, rebounds, assists.
    """
    df = df.sort_values(["player", "date"])
    
    df["points_rolling_avg"] = (
        df.groupby("player")["points"].transform(lambda x: x.rolling(5, min_periods=1).mean())
    )
    df["rebounds_rolling_avg"] = (
        df.groupby("player")["rebounds"].transform(lambda x: x.rolling(5, min_periods=1).mean())
    )
    df["assists_rolling_avg"] = (
        df.groupby("player")["assists"].transform(lambda x: x.rolling(5, min_periods=1).mean())
    )
    
    # Define next-game points as prediction target
    df["target_points"] = df.groupby("player")["points"].shift(-1)
    
    return df.dropna(subset=["target_points"])

