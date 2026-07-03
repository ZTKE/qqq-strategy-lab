import numpy as np
import pandas as pd
import pytest

from src.main import (
    add_synthetic_leverage_assets,
    apply_asset_history_proxies,
    stitch_real_leverage_series,
    synthetic_leverage_daily_cost_series,
)
from src.strategies import build_strategy


BASE_ASSETS = ["QQQ", "SPY", "XLK", "SMH", "GLD", "SHY"]
SYNTHETIC_ASSETS = ["QQQ_2X", "QQQ_3X", "SPY_2X", "XLK_2X", "SMH_2X"]


def _leveraged_prices() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", periods=320)
    data = {}
    for index, asset in enumerate(BASE_ASSETS, start=1):
        data[asset] = np.linspace(100.0, 100.0 + index * 40.0, len(dates))
    prices = pd.DataFrame(data, index=dates)
    return add_synthetic_leverage_assets(prices, SYNTHETIC_ASSETS)


@pytest.mark.parametrize(
    "name,config",
    [
        (
            "daily_trend_2x",
            {
                "type": "daily_trend_2x",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "ma_window": 20,
                "risk_on_asset": "QQQ_2X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "daily_trend_3x_defensive",
            {
                "type": "daily_trend_3x_defensive",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "fast_window": 20,
                "slow_window": 60,
                "asset_1x": "QQQ",
                "asset_2x": "QQQ_2X",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "daily_trend_3x_drawdown_boost",
            {
                "type": "daily_trend_3x_drawdown_boost",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "fast_window": 20,
                "slow_window": 60,
                "slope_lookback": 10,
                "soft_drawdown_threshold": 0.15,
                "deep_drawdown_threshold": 0.25,
                "asset_1x": "QQQ",
                "asset_2x": "QQQ_2X",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "tqqq_bull_bear_full_throttle",
            {
                "type": "tqqq_bull_bear_full_throttle",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "fast_window": 20,
                "slow_window": 60,
                "slope_lookback": 10,
                "risk_on_asset": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "leveraged_momentum_rotation_3x",
            {
                "type": "leveraged_momentum_rotation_3x",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "ma_window": 20,
                "lookback_months": 3,
                "top_n": 1,
                "candidate_assets": ["QQQ_3X", "QQQ_2X", "XLK_2X", "SMH_2X"],
                "fallback_asset": "SHY",
            },
        ),
        (
            "turbo_momentum_3x",
            {
                "type": "turbo_momentum_3x",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "fast_window": 20,
                "slow_window": 60,
                "slope_lookback": 10,
                "vol_window": 20,
                "max_volatility": 1.0,
                "reentry_drawdown_threshold": 0.20,
                "lookback_months": 3,
                "candidate_assets": ["QQQ_3X", "QQQ_2X", "XLK_2X", "SMH_2X"],
                "asset_2x": "QQQ_2X",
                "fallback_asset": "SHY",
            },
        ),
        (
            "daily_trend_3x_defensive_v2",
            {
                "type": "daily_trend_3x_defensive_v2",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "fast_window": 20,
                "slow_window": 60,
                "slope_lookback": 10,
                "vol_window": 20,
                "low_vol_threshold": 0.5,
                "high_vol_threshold": 0.8,
                "soft_drawdown_threshold": 0.2,
                "hard_drawdown_threshold": 0.4,
                "max_3x_weight": 0.8,
                "medium_3x_weight": 0.6,
                "asset_1x": "QQQ",
                "asset_2x": "QQQ_2X",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "dual_ma_leverage_ladder",
            {
                "type": "dual_ma_leverage_ladder",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "short_window": 10,
                "mid_window": 20,
                "long_window": 60,
                "asset_1x": "QQQ",
                "asset_2x": "QQQ_2X",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "vol_target_trend",
            {
                "type": "vol_target_trend",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "ma_window": 60,
                "vol_window": 20,
                "low_vol_threshold": 0.5,
                "high_vol_threshold": 0.8,
                "asset_1x": "QQQ",
                "asset_2x": "QQQ_2X",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "core_trend_2x",
            {
                "type": "core_trend_2x",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "fast_window": 20,
                "slow_window": 60,
                "core_asset": "QQQ",
                "core_weight": 0.5,
                "tactical_weight": 0.5,
                "asset_2x": "QQQ_2X",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "momentum_rotation_2x",
            {
                "type": "momentum_rotation_2x",
                "rebalance_frequency": "daily",
                "assets": BASE_ASSETS,
                "leveraged_assets": {"QQQ": "QQQ_2X", "SPY": "SPY_2X", "XLK": "XLK_2X", "SMH": "SMH_2X"},
                "lookback_months": 3,
                "top_n": 2,
                "ma_window": 20,
                "fallback_asset": "SHY",
            },
        ),
        (
            "breakout_3x_with_stop",
            {
                "type": "breakout_3x_with_stop",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "high_window": 60,
                "near_high_threshold": 0.95,
                "fast_window": 20,
                "slow_window": 60,
                "asset_1x": "QQQ",
                "asset_2x": "QQQ_2X",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "crash_protected_tqqq",
            {
                "type": "crash_protected_tqqq",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "ma_window": 60,
                "slope_lookback": 10,
                "asset_1x": "QQQ",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "ema5_tqqq_trend",
            {
                "type": "ema5_tqqq_trend",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "ema_window": 5,
                "ema_slope_lookback": 1,
                "long_ma_window": 60,
                "long_ma_slope_lookback": 1,
                "risk_on_asset": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "adaptive_leverage_score",
            {
                "type": "adaptive_leverage_score",
                "rebalance_frequency": "daily",
                "signal_asset": "QQQ",
                "fast_window": 20,
                "slow_window": 60,
                "momentum_months": 3,
                "vol_window": 20,
                "vol_threshold": 0.8,
                "drawdown_threshold": 0.10,
                "asset_1x": "QQQ",
                "asset_2x": "QQQ_2X",
                "asset_3x": "QQQ_3X",
                "risk_off_asset": "SHY",
            },
        ),
        (
            "dca_leverage_boost",
            {
                "type": "dca_leverage_boost",
                "signal_asset": "QQQ",
                "fast_window": 20,
                "ma_window": 60,
                "normal_weights": {"QQQ": 0.7, "SPY": 0.2, "SHY": 0.1},
                "bull_weights": {"QQQ_2X": 0.8, "SPY": 0.2},
                "strong_bull_weights": {"QQQ_3X": 0.8, "SPY": 0.2},
                "bear_weights": {"QQQ": 0.4, "SHY": 0.6},
            },
        ),
    ],
)
def test_leveraged_strategy_weights_are_valid(name, config):
    prices = _leveraged_prices()
    strategy = build_strategy(name, config)

    weights = strategy.generate_weights(prices, prices.index[-1])

    assert sum(weights.values()) == pytest.approx(1.0)
    assert all(value >= 0 for value in weights.values())
    assert set(weights).issubset(set(prices.columns))


def test_synthetic_leverage_assets_use_daily_compounding():
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = pd.DataFrame({"QQQ": [100.0, 110.0, 99.0]}, index=dates)

    output = add_synthetic_leverage_assets(prices, ["QQQ_2X", "QQQ_3X"])

    assert output.loc[dates[0], "QQQ_2X"] == pytest.approx(100.0)
    assert output.loc[dates[1], "QQQ_2X"] == pytest.approx(120.0)
    assert output.loc[dates[2], "QQQ_2X"] == pytest.approx(96.0)
    assert output.loc[dates[1], "QQQ_3X"] == pytest.approx(130.0)


def test_synthetic_leverage_assets_apply_management_and_financing_drag():
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = pd.DataFrame({"QQQ": [100.0, 110.0, 99.0]}, index=dates)
    leverage_costs = {
        "annual_management_fee": 0.252,
        "annual_financing_rate": 0.252,
        "annual_financing_spread": 0.0,
        "annual_tracking_decay": 0.0,
        "trading_days": 252,
    }

    output = add_synthetic_leverage_assets(prices, ["QQQ_2X", "QQQ_3X"], leverage_costs=leverage_costs)

    assert output.loc[dates[0], "QQQ_2X"] == pytest.approx(100.0)
    assert output.loc[dates[1], "QQQ_2X"] == pytest.approx(119.8)
    assert output.loc[dates[2], "QQQ_2X"] == pytest.approx(95.6004)
    assert output.loc[dates[1], "QQQ_3X"] == pytest.approx(129.7)


def test_synthetic_leverage_assets_apply_dynamic_financing_rates():
    dates = pd.bdate_range("2024-01-02", periods=2)
    financing_rates = pd.Series([0.01, 0.05], index=dates)
    leverage_costs = {
        "annual_management_fee": 0.0,
        "annual_financing_rate": 0.0,
        "annual_financing_spread": 0.0,
        "annual_tracking_decay": 0.0,
        "trading_days": 100,
    }

    daily_cost = synthetic_leverage_daily_cost_series(
        dates,
        "QQQ_3X",
        3,
        leverage_costs=leverage_costs,
        financing_rates=financing_rates,
    )

    assert daily_cost.iloc[0] == pytest.approx(0.0002)
    assert daily_cost.iloc[1] == pytest.approx(0.001)


def test_stitch_real_leverage_series_preserves_continuity_at_first_real_date():
    dates = pd.bdate_range("2024-01-02", periods=4)
    synthetic = pd.Series([100.0, 120.0, 140.0, 160.0], index=dates, name="QQQ_3X")
    real = pd.Series([10.0, 11.0], index=dates[2:])

    stitched = stitch_real_leverage_series(synthetic, real)

    assert stitched.loc[dates[1]] == pytest.approx(120.0)
    assert stitched.loc[dates[2]] == pytest.approx(140.0)
    assert stitched.loc[dates[3]] == pytest.approx(154.0)


def test_apply_asset_history_proxies_builds_chained_prehistory():
    dates = pd.bdate_range("2024-01-02", periods=6)
    prices = pd.DataFrame(
        {
            "QQQ": [np.nan, np.nan, np.nan, np.nan, 100.0, 110.0],
            "^NDX": [np.nan, np.nan, 40.0, 50.0, 100.0, 110.0],
            "^IXIC": [10.0, 20.0, 16.0, 20.0, 40.0, 44.0],
        },
        index=dates,
    )
    proxy_config = {
        "QQQ": {
            "proxies": [
                {"ticker": "^IXIC", "label": "oldest"},
                {"ticker": "^NDX", "label": "newer"},
            ]
        }
    }

    output, summary = apply_asset_history_proxies(prices, proxy_config)

    assert output.loc[dates[0], "QQQ"] == pytest.approx(25.0)
    assert output.loc[dates[1], "QQQ"] == pytest.approx(50.0)
    assert output.loc[dates[2], "QQQ"] == pytest.approx(40.0)
    assert output.loc[dates[3], "QQQ"] == pytest.approx(50.0)
    assert output.loc[dates[4], "QQQ"] == pytest.approx(100.0)
    assert output.loc[dates[5], "QQQ"] == pytest.approx(110.0)
    assert set(summary["Proxy Ticker"]) == {"^NDX", "^IXIC"}
