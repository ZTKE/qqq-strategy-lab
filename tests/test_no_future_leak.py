import pandas as pd

from src.strategies.drawdown_buy import DrawdownBuyStrategy
from src.strategies.trend_200dma import Trend200DmaStrategy


def test_trend_strategy_ignores_future_prices():
    dates = pd.bdate_range("2024-01-01", periods=8)
    prices = pd.DataFrame(
        {
            "QQQ": [100, 100, 100, 90, 90, 1000, 1000, 1000],
            "SPY": [100] * 8,
            "SHY": [100] * 8,
        },
        index=dates,
    )
    current_date = dates[4]
    strategy = Trend200DmaStrategy(
        "trend",
        {
            "signal_asset": "QQQ",
            "ma_window": 3,
            "risk_on": {"QQQ": 1.0},
            "risk_off": {"SHY": 1.0},
        },
    )

    weights_with_future = strategy.generate_weights(prices, current_date)
    weights_without_future = strategy.generate_weights(prices.loc[:current_date], current_date)

    assert weights_with_future == weights_without_future
    assert weights_with_future == {"SHY": 1.0}


def test_drawdown_strategy_ignores_future_highs():
    dates = pd.bdate_range("2024-01-01", periods=5)
    prices = pd.DataFrame(
        {
            "QQQ": [100, 120, 100, 1000, 1000],
            "SPY": [100] * 5,
            "SHY": [100] * 5,
        },
        index=dates,
    )
    current_date = dates[2]
    strategy = DrawdownBuyStrategy(
        "drawdown",
        {
            "signal_asset": "QQQ",
            "rules": [
                {"drawdown_lt": 0.10, "weights": {"QQQ": 0.7, "SPY": 0.2, "SHY": 0.1}},
                {"drawdown_lt": 0.20, "weights": {"QQQ": 0.8, "SPY": 0.15, "SHY": 0.05}},
                {"drawdown_lt": 1.00, "weights": {"QQQ": 1.0}},
            ],
        },
    )

    weights_with_future = strategy.generate_weights(prices, current_date)
    weights_without_future = strategy.generate_weights(prices.loc[:current_date], current_date)

    assert weights_with_future == weights_without_future
    assert weights_with_future["QQQ"] == 0.8
