import numpy as np
import pandas as pd
import pytest

from src.metrics import cagr, max_drawdown, sharpe_ratio, total_return


def test_total_return():
    equity = pd.Series([100.0, 125.0])
    assert total_return(equity) == pytest.approx(0.25)


def test_max_drawdown():
    equity = pd.Series([100.0, 120.0, 90.0, 110.0])
    assert max_drawdown(equity) == pytest.approx(-0.25)


def test_cagr():
    dates = pd.bdate_range("2020-01-01", periods=253)
    equity = pd.Series(np.linspace(100.0, 110.0, len(dates)), index=dates)
    assert cagr(equity) == pytest.approx(0.10)


def test_sharpe_ratio():
    returns = pd.Series([0.01, 0.02, -0.01, 0.03, 0.00])
    value = sharpe_ratio(returns)
    assert np.isfinite(value)
    assert value > 0
