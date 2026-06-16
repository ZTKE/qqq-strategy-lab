import numpy as np
import pandas as pd
import pytest

from src.strategies import build_strategy
from src.strategies.momentum_rotation import MomentumRotationStrategy


ASSETS = ["QQQ", "SPY", "XLK", "SMH", "GLD", "SHY"]


def _prices(up: bool = True) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=260)
    data = {}
    for index, asset in enumerate(ASSETS, start=1):
        start = 100.0
        end = 100.0 + index * 20.0 if up else 100.0 - index * 5.0
        data[asset] = np.linspace(start, end, len(dates))
    return pd.DataFrame(data, index=dates)


@pytest.mark.parametrize(
    "name,config",
    [
        ("qqq_buy_hold", {"type": "buy_and_hold", "weights": {"QQQ": 1.0}}),
        ("qqq_80_spy_20", {"type": "static_allocation", "weights": {"QQQ": 0.8, "SPY": 0.2}}),
        (
            "trend_200dma",
            {
                "type": "trend_200dma",
                "signal_asset": "QQQ",
                "ma_window": 5,
                "risk_on": {"QQQ": 0.8, "SPY": 0.2},
                "risk_off": {"QQQ": 0.3, "SPY": 0.2, "SHY": 0.5},
            },
        ),
        (
            "core_trend",
            {
                "type": "core_trend",
                "signal_asset": "QQQ",
                "ma_window": 5,
                "core_asset": "QQQ",
                "core_weight": 0.6,
                "risk_on_asset": "QQQ",
                "risk_off_asset": "SHY",
                "tactical_weight": 0.4,
            },
        ),
        (
            "drawdown_buy",
            {
                "type": "drawdown_buy",
                "signal_asset": "QQQ",
                "rules": [
                    {"drawdown_lt": 0.10, "weights": {"QQQ": 0.7, "SPY": 0.2, "SHY": 0.1}},
                    {"drawdown_lt": 0.20, "weights": {"QQQ": 0.8, "SPY": 0.15, "SHY": 0.05}},
                    {"drawdown_lt": 0.30, "weights": {"QQQ": 0.9, "SPY": 0.1}},
                    {"drawdown_lt": 1.00, "weights": {"QQQ": 1.0}},
                ],
            },
        ),
        (
            "momentum_rotation",
            {
                "type": "momentum_rotation",
                "assets": ASSETS,
                "lookback_months": 3,
                "top_n": 2,
                "ma_window": 5,
                "fallback_asset": "SHY",
            },
        ),
        (
            "dca_drawdown_boost",
            {
                "type": "dca",
                "initial_capital": 20000,
                "monthly_contribution": 3000,
                "signal_asset": "QQQ",
                "normal_weights": {"QQQ": 0.7, "SPY": 0.2, "SHY": 0.1},
                "rules": [
                    {"drawdown_gte": 0.10, "contribution_multiplier": 1.0, "weights": {"QQQ": 0.9, "SPY": 0.1}},
                    {"drawdown_gte": 0.20, "contribution_multiplier": 1.0, "weights": {"QQQ": 1.0}},
                    {"drawdown_gte": 0.30, "contribution_multiplier": 1.0, "weights": {"QQQ": 1.0}},
                ],
            },
        ),
    ],
)
def test_strategy_weights_sum_to_one_and_are_non_negative(name, config):
    prices = _prices(up=True)
    strategy = build_strategy(name, config)
    weights = strategy.generate_weights(prices, prices.index[-1])

    assert sum(weights.values()) == pytest.approx(1.0)
    assert all(value >= 0 for value in weights.values())


def test_momentum_fallback_asset_is_used():
    prices = _prices(up=False)
    strategy = MomentumRotationStrategy(
        "momentum_rotation",
        {
            "assets": ASSETS,
            "lookback_months": 3,
            "top_n": 2,
            "ma_window": 20,
            "fallback_asset": "SHY",
        },
    )
    weights = strategy.generate_weights(prices, prices.index[-1])
    assert weights == {"SHY": 1.0}
