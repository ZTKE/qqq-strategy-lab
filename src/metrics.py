from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd


def _clean_equity(equity_curve: pd.Series) -> pd.Series:
    series = pd.Series(equity_curve).dropna().astype(float)
    if isinstance(series.index, pd.DatetimeIndex):
        series = series.sort_index()
    return series


def total_return(equity_curve: pd.Series) -> float:
    series = _clean_equity(equity_curve)
    if len(series) < 2 or series.iloc[0] <= 0:
        return np.nan
    return float(series.iloc[-1] / series.iloc[0] - 1.0)


def cagr(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    series = _clean_equity(equity_curve)
    if len(series) < 2 or series.iloc[0] <= 0 or series.iloc[-1] <= 0:
        return np.nan

    years = (len(series) - 1) / periods_per_year
    if years <= 0:
        return np.nan
    return float((series.iloc[-1] / series.iloc[0]) ** (1.0 / years) - 1.0)


def max_drawdown(equity_curve: pd.Series) -> float:
    series = _clean_equity(equity_curve)
    if series.empty:
        return np.nan
    rolling_peak = series.cummax()
    drawdown = series / rolling_peak - 1.0
    return float(drawdown.min())


def annualized_volatility(daily_returns: pd.Series, periods_per_year: int = 252) -> float:
    returns = pd.Series(daily_returns).dropna().astype(float)
    if len(returns) < 2:
        return np.nan
    return float(returns.std(ddof=1) * math.sqrt(periods_per_year))


def sharpe_ratio(
    daily_returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    returns = pd.Series(daily_returns).dropna().astype(float)
    if len(returns) < 2:
        return np.nan

    daily_risk_free = risk_free_rate / periods_per_year
    excess = returns - daily_risk_free
    volatility = excess.std(ddof=1) * math.sqrt(periods_per_year)
    if volatility == 0 or np.isnan(volatility):
        return np.nan
    return float(excess.mean() * periods_per_year / volatility)


def calmar_ratio(cagr_value: float, max_drawdown_value: float) -> float:
    if pd.isna(cagr_value) or pd.isna(max_drawdown_value):
        return np.nan
    denominator = abs(float(max_drawdown_value))
    if denominator == 0:
        return np.nan
    return float(cagr_value / denominator)


def yearly_returns(equity_curve: pd.Series) -> pd.Series:
    series = _clean_equity(equity_curve)
    if not isinstance(series.index, pd.DatetimeIndex) or series.empty:
        return pd.Series(dtype=float)

    year_end = series.resample("YE").last()
    returns = year_end.pct_change()
    first_year = year_end.index[0]
    first_year_start = series.loc[series.index.year == first_year.year].iloc[0]
    returns.iloc[0] = year_end.iloc[0] / first_year_start - 1.0
    returns.index = returns.index.year
    return returns


def monthly_returns(equity_curve: pd.Series) -> pd.Series:
    series = _clean_equity(equity_curve)
    if not isinstance(series.index, pd.DatetimeIndex) or series.empty:
        return pd.Series(dtype=float)

    month_end = series.resample("ME").last()
    returns = month_end.pct_change()
    first_month = month_end.index[0]
    first_month_start = series.loc[(series.index.year == first_month.year) & (series.index.month == first_month.month)].iloc[0]
    returns.iloc[0] = month_end.iloc[0] / first_month_start - 1.0
    return returns


def performance_summary(equity_curve: pd.Series, daily_returns: pd.Series | None = None) -> dict[str, float]:
    series = _clean_equity(equity_curve)
    returns = pd.Series(daily_returns).dropna() if daily_returns is not None else series.pct_change().dropna()
    cagr_value = cagr(series)
    max_dd = max_drawdown(series)
    return {
        "total_return": total_return(series),
        "cagr": cagr_value,
        "max_drawdown": max_dd,
        "annualized_volatility": annualized_volatility(returns),
        "sharpe_ratio": sharpe_ratio(returns),
        "calmar_ratio": calmar_ratio(cagr_value, max_dd),
        "final_equity": float(series.iloc[-1]) if not series.empty else np.nan,
    }


def rolling_period_performance(
    equity_curve: pd.Series,
    years: Iterable[int] = (1, 3, 5, 7, 10),
) -> dict[int, dict[str, float]]:
    series = _clean_equity(equity_curve)
    output: dict[int, dict[str, float]] = {}
    if series.empty or not isinstance(series.index, pd.DatetimeIndex):
        return {int(year): _empty_period_summary() for year in years}

    end_date = series.index[-1]
    first_date = series.index[0]

    for year in years:
        cutoff = end_date - pd.DateOffset(years=int(year))
        if first_date > cutoff:
            output[int(year)] = _empty_period_summary()
            continue

        window = series.loc[series.index >= cutoff]
        if len(window) < 2:
            output[int(year)] = _empty_period_summary()
            continue

        output[int(year)] = performance_summary(window, window.pct_change().dropna())

    return output


def _empty_period_summary() -> dict[str, float]:
    return {
        "total_return": np.nan,
        "cagr": np.nan,
        "max_drawdown": np.nan,
        "annualized_volatility": np.nan,
        "sharpe_ratio": np.nan,
        "calmar_ratio": np.nan,
        "final_equity": np.nan,
    }
