from __future__ import annotations

import pandas as pd


def as_trading_index(index) -> pd.DatetimeIndex:
    trading_index = pd.DatetimeIndex(index).sort_values().unique()
    if trading_index.empty:
        raise ValueError("Trading index is empty.")
    return trading_index


def monthly_last_trading_days(index) -> pd.DatetimeIndex:
    trading_index = as_trading_index(index)
    dates = pd.Series(trading_index, index=trading_index)
    last_days = dates.groupby(dates.index.to_period("M")).max()
    return pd.DatetimeIndex(last_days.to_list())


def rebalance_signal_dates(index, include_first: bool = True) -> pd.DatetimeIndex:
    trading_index = as_trading_index(index)
    dates = list(monthly_last_trading_days(trading_index))
    if include_first and trading_index[0] not in dates:
        dates.insert(0, trading_index[0])
    return pd.DatetimeIndex(sorted(set(dates)))


def next_trading_day(index, current_date: pd.Timestamp) -> pd.Timestamp | None:
    trading_index = as_trading_index(index)
    pos = trading_index.searchsorted(pd.Timestamp(current_date), side="right")
    if pos >= len(trading_index):
        return None
    return trading_index[pos]
