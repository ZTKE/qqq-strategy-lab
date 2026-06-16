from __future__ import annotations

import numpy as np
import pandas as pd


def simple_moving_average(series: pd.Series, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("Window must be positive.")
    return series.astype(float).rolling(window=window, min_periods=window).mean()


def moving_average_at(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp, window: int) -> float:
    history = prices.loc[:current_date, asset].dropna()
    if len(history) < window:
        return np.nan
    return float(history.tail(window).mean())


def historical_drawdown_at(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp) -> float:
    history = prices.loc[:current_date, asset].dropna()
    if history.empty:
        return np.nan
    current_price = float(history.iloc[-1])
    peak = float(history.max())
    if peak <= 0:
        return np.nan
    return 1.0 - current_price / peak


def trailing_month_return(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp, months: int) -> float:
    history = prices.loc[:current_date, asset].dropna()
    if history.empty:
        return np.nan

    current_price = float(history.iloc[-1])
    lookback_date = pd.Timestamp(current_date) - pd.DateOffset(months=months)
    eligible = history.loc[:lookback_date]
    if eligible.empty:
        return np.nan

    past_price = float(eligible.iloc[-1])
    if past_price <= 0:
        return np.nan
    return current_price / past_price - 1.0
