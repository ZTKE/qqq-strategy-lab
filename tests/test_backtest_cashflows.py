import pandas as pd
import pytest

from src.backtest import BacktestEngine
from src.strategies.dca import DcaDrawdownBoostStrategy
from src.strategies.static_allocation import StaticAllocationStrategy


def test_rebalanced_strategy_uses_initial_capital_and_monthly_contributions():
    dates = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-28", "2024-03-01"])
    prices = pd.DataFrame({"QQQ": [100.0, 100.0, 100.0, 100.0, 100.0]}, index=dates)
    strategy = StaticAllocationStrategy(
        "qqq_only",
        {"type": "static_allocation", "weights": {"QQQ": 1.0}},
    )
    engine = BacktestEngine(prices, initial_capital=20000.0, monthly_contribution=3000.0, transaction_cost=0.0)

    result = engine.run(strategy)

    assert result.metrics["total_invested"] == pytest.approx(26000.0)
    assert result.metrics["final_equity"] == pytest.approx(26000.0)
    assert result.metrics["total_return"] == pytest.approx(0.0)


def test_dca_does_not_add_extra_contribution_on_final_partial_month():
    dates = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-28", "2024-03-01"])
    prices = pd.DataFrame({"QQQ": [100.0, 100.0, 100.0, 100.0, 100.0]}, index=dates)
    strategy = DcaDrawdownBoostStrategy(
        "dca",
        {
            "type": "dca",
            "initial_capital": 20000,
            "monthly_contribution": 3000,
            "signal_asset": "QQQ",
            "normal_weights": {"QQQ": 1.0},
            "rules": [],
        },
    )
    engine = BacktestEngine(prices, initial_capital=20000.0, monthly_contribution=3000.0, transaction_cost=0.0)

    result = engine.run(strategy)

    assert result.metrics["total_invested"] == pytest.approx(26000.0)
    assert result.metrics["final_equity"] == pytest.approx(26000.0)


def test_unavailable_asset_weight_is_held_as_cash_until_price_exists():
    dates = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01"])
    prices = pd.DataFrame(
        {
            "QQQ": [100.0, 100.0, 100.0],
            "SHY": [None, None, 100.0],
        },
        index=dates,
    )
    strategy = StaticAllocationStrategy(
        "qqq_shy",
        {"type": "static_allocation", "weights": {"QQQ": 0.5, "SHY": 0.5}},
    )
    engine = BacktestEngine(prices, initial_capital=20000.0, monthly_contribution=3000.0, transaction_cost=0.0)

    result = engine.run(strategy)

    assert result.equity_curve.iloc[1] == pytest.approx(20000.0)
    assert result.metrics["total_invested"] == pytest.approx(23000.0)
    assert result.metrics["final_equity"] == pytest.approx(23000.0)
