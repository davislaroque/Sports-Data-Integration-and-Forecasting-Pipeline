"""
modeling.py
-----------
Simple models for player prop predictions.
"""

import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor


def train_model(X_train, y_train, model_type="linear"):
    """
    Train a regression model (linear or random forest).
    """
    if model_type == "linear":
        model = LinearRegression()
    elif model_type == "random_forest":
        model = RandomForestRegressor(n_estimators=100, random_state=42)
    else:
        raise ValueError("Invalid model_type. Use 'linear' or 'random_forest'.")

    model.fit(X_train, y_train)
    return model


def predict(model, X_test):
    """
    Generate predictions for player props.
    """
    return model.predict(X_test)
