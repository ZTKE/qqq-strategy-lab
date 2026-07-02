from __future__ import annotations

import numpy as np
import pandas as pd


_MA_CACHE: dict[tuple[int, str, int], pd.Series] = {}
_DRAWDOWN_CACHE: dict[tuple[int, str], pd.Series] = {}


def _series_value_at(series: pd.Series, current_date: pd.Timestamp) -> float:
    position = series.index.searchsorted(pd.Timestamp(current_date), side="right") - 1
    if position < 0:
        return np.nan
    value = series.iloc[position]
    return float(value) if pd.notna(value) else np.nan


def simple_moving_average(series: pd.Series, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("Window must be positive.")
    return series.astype(float).rolling(window=window, min_periods=window).mean()


def moving_average_at(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp, window: int) -> float:
    if asset not in prices.columns:
        return np.nan
    key = (id(prices), asset, int(window))
    moving_average = _MA_CACHE.get(key)
    if moving_average is None:
        moving_average = simple_moving_average(prices[asset].dropna(), int(window))
        _MA_CACHE[key] = moving_average
    return _series_value_at(moving_average, current_date)


def historical_drawdown_at(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp) -> float:
    if asset not in prices.columns:
        return np.nan
    key = (id(prices), asset)
    drawdown = _DRAWDOWN_CACHE.get(key)
    if drawdown is None:
        series = prices[asset].dropna().astype(float)
        drawdown = 1.0 - series / series.cummax()
        _DRAWDOWN_CACHE[key] = drawdown
    return _series_value_at(drawdown, current_date)


def trailing_month_return(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp, months: int) -> float:
    if asset not in prices.columns:
        return np.nan
    history = prices[asset].dropna().astype(float)
    current_pos = history.index.searchsorted(pd.Timestamp(current_date), side="right") - 1
    if current_pos < 0:
        return np.nan

    current_price = float(history.iloc[current_pos])
    lookback_date = pd.Timestamp(current_date) - pd.DateOffset(months=months)
    past_pos = history.index.searchsorted(lookback_date, side="right") - 1
    if past_pos < 0:
        return np.nan

    past_price = float(history.iloc[past_pos])
    if past_price <= 0:
        return np.nan
    return current_price / past_price - 1.0
