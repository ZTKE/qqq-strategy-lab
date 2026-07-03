from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.indicators import historical_drawdown_at, moving_average_at, trailing_month_return
from src.strategies.base import Strategy


_VOL_CACHE: dict[tuple[int, str, int], pd.Series] = {}
_HIGH_CACHE: dict[tuple[int, str, int], pd.Series] = {}
_MA_SERIES_CACHE: dict[tuple[int, str, int], pd.Series] = {}
_EMA_CACHE: dict[tuple[int, str, int], pd.Series] = {}


def _series_value_at(series: pd.Series, current_date: pd.Timestamp) -> float:
    position = series.index.searchsorted(pd.Timestamp(current_date), side="right") - 1
    if position < 0:
        return np.nan
    value = series.iloc[position]
    return float(value) if pd.notna(value) else np.nan


class DailyTrend2xStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        ma_window = int(self.config.get("ma_window", 200))
        risk_on_asset = self.config.get("risk_on_asset", "QQQ_2X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        if _above_ma(prices, signal_asset, current_date, ma_window):
            return self.normalize({risk_on_asset: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class DailyTrend3xDefensiveStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        fast_window = int(self.config.get("fast_window", 50))
        slow_window = int(self.config.get("slow_window", 200))
        asset_1x = self.config.get("asset_1x", "QQQ")
        asset_2x = self.config.get("asset_2x", "QQQ_2X")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, slow_window)
        if pd.isna(price) or pd.isna(fast_ma) or pd.isna(slow_ma):
            return self.normalize({risk_off_asset: 1.0})
        if price > fast_ma and fast_ma > slow_ma:
            return self.normalize({asset_3x: 1.0})
        if price > slow_ma:
            return self.normalize({asset_2x: 1.0})
        if price > fast_ma:
            return self.normalize({asset_1x: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class Ema5TqqqTrendStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        ema_window = int(self.config.get("ema_window", 5))
        ema_slope_lookback = int(self.config.get("ema_slope_lookback", self.config.get("slope_lookback", 1)))
        long_ma_window = int(self.config.get("long_ma_window", 200))
        long_ma_slope_lookback = int(self.config.get("long_ma_slope_lookback", 1))
        risk_on_asset = self.config.get("risk_on_asset", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        ema = _ema_at(prices, signal_asset, current_date, ema_window)
        ema_rising = _ema_slope_positive(prices, signal_asset, current_date, ema_window, ema_slope_lookback)
        long_ma_rising = _ma_slope_positive(
            prices,
            signal_asset,
            current_date,
            long_ma_window,
            long_ma_slope_lookback,
        )
        if pd.notna(price) and pd.notna(ema) and price > ema and ema_rising and long_ma_rising:
            return self.normalize({risk_on_asset: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class DailyTrend3xDefensiveV2Strategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        fast_window = int(self.config.get("fast_window", 50))
        slow_window = int(self.config.get("slow_window", 200))
        slope_lookback = int(self.config.get("slope_lookback", 20))
        vol_window = int(self.config.get("vol_window", 20))
        low_vol = float(self.config.get("low_vol_threshold", 0.28))
        high_vol = float(self.config.get("high_vol_threshold", 0.35))
        soft_drawdown = float(self.config.get("soft_drawdown_threshold", 0.15))
        hard_drawdown = float(self.config.get("hard_drawdown_threshold", 0.25))
        max_3x_weight = float(self.config.get("max_3x_weight", 0.8))
        medium_3x_weight = float(self.config.get("medium_3x_weight", 0.6))
        asset_1x = self.config.get("asset_1x", "QQQ")
        asset_2x = self.config.get("asset_2x", "QQQ_2X")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, slow_window)
        volatility = _realized_volatility(prices, signal_asset, current_date, vol_window)
        drawdown = historical_drawdown_at(prices, signal_asset, current_date)
        fast_rising = _ma_slope_positive(prices, signal_asset, current_date, fast_window, slope_lookback)
        slow_rising = _ma_slope_positive(prices, signal_asset, current_date, slow_window, slope_lookback)

        if any(pd.isna(value) for value in [price, fast_ma, slow_ma, volatility, drawdown]):
            return self.normalize({risk_off_asset: 1.0})
        if drawdown >= hard_drawdown:
            return self.normalize({risk_off_asset: 1.0})
        if drawdown >= soft_drawdown:
            if price > slow_ma:
                return self.normalize({asset_1x: 1.0})
            return self.normalize({risk_off_asset: 1.0})

        strong_trend = price > fast_ma and fast_ma > slow_ma and fast_rising and slow_rising
        if strong_trend and volatility <= low_vol:
            return self.normalize({asset_3x: max_3x_weight, risk_off_asset: 1.0 - max_3x_weight})
        if strong_trend and volatility <= high_vol:
            return self.normalize({asset_3x: medium_3x_weight, risk_off_asset: 1.0 - medium_3x_weight})
        if price > slow_ma:
            return self.normalize({asset_2x: 1.0})
        if price > fast_ma:
            return self.normalize({asset_1x: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class DualMaLeverageLadderStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        short_window = int(self.config.get("short_window", 20))
        mid_window = int(self.config.get("mid_window", 50))
        long_window = int(self.config.get("long_window", 200))
        asset_1x = self.config.get("asset_1x", "QQQ")
        asset_2x = self.config.get("asset_2x", "QQQ_2X")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        short_ma = moving_average_at(prices, signal_asset, current_date, short_window)
        mid_ma = moving_average_at(prices, signal_asset, current_date, mid_window)
        long_ma = moving_average_at(prices, signal_asset, current_date, long_window)
        if any(pd.isna(value) for value in [price, short_ma, mid_ma, long_ma]):
            return self.normalize({risk_off_asset: 1.0})

        if price > short_ma > mid_ma > long_ma:
            return self.normalize({asset_3x: 1.0})
        if price > mid_ma > long_ma:
            return self.normalize({asset_2x: 1.0})
        if price > long_ma:
            return self.normalize({asset_1x: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class VolTargetTrendStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        ma_window = int(self.config.get("ma_window", 200))
        vol_window = int(self.config.get("vol_window", 20))
        low_vol = float(self.config.get("low_vol_threshold", 0.18))
        high_vol = float(self.config.get("high_vol_threshold", 0.28))
        asset_1x = self.config.get("asset_1x", "QQQ")
        asset_2x = self.config.get("asset_2x", "QQQ_2X")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        if not _above_ma(prices, signal_asset, current_date, ma_window):
            return self.normalize({risk_off_asset: 1.0})

        volatility = _realized_volatility(prices, signal_asset, current_date, vol_window)
        if pd.isna(volatility):
            return self.normalize({asset_1x: 1.0})
        if volatility <= low_vol:
            return self.normalize({asset_3x: 1.0})
        if volatility <= high_vol:
            return self.normalize({asset_2x: 1.0})
        return self.normalize({asset_1x: 1.0})


class CoreTrend2xStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        fast_window = int(self.config.get("fast_window", 50))
        slow_window = int(self.config.get("slow_window", 200))
        core_asset = self.config.get("core_asset", "QQQ")
        core_weight = float(self.config.get("core_weight", 0.5))
        tactical_weight = float(self.config.get("tactical_weight", 0.5))
        asset_2x = self.config.get("asset_2x", "QQQ_2X")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, slow_window)
        weights = {core_asset: core_weight}
        if pd.notna(price) and pd.notna(fast_ma) and pd.notna(slow_ma) and price > fast_ma and fast_ma > slow_ma:
            weights[asset_3x] = tactical_weight
        elif pd.notna(price) and pd.notna(slow_ma) and price > slow_ma:
            weights[asset_2x] = tactical_weight
        else:
            weights[risk_off_asset] = tactical_weight
        return self.normalize(weights)


class MomentumRotation2xStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        assets = list(self.config["assets"])
        leveraged_assets = dict(self.config.get("leveraged_assets", {}))
        lookback_months = int(self.config.get("lookback_months", 6))
        top_n = int(self.config.get("top_n", 2))
        ma_window = int(self.config.get("ma_window", 200))
        fallback_asset = self.config.get("fallback_asset", "SHY")

        scores: dict[str, float] = {}
        for asset in assets:
            if not _above_ma(prices, asset, current_date, ma_window):
                continue
            momentum = trailing_month_return(prices, asset, current_date, lookback_months)
            if not np.isnan(momentum):
                scores[asset] = float(momentum)

        if not scores:
            return self.normalize({fallback_asset: 1.0})

        selected = sorted(scores, key=scores.get, reverse=True)[:top_n]
        weight = 1.0 / len(selected)
        return self.normalize({leveraged_assets.get(asset, asset): weight for asset in selected})


class LeveragedMomentumRotation3xStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        ma_window = int(self.config.get("ma_window", 200))
        lookback_months = int(self.config.get("lookback_months", 6))
        top_n = int(self.config.get("top_n", 1))
        candidate_assets = list(self.config.get("candidate_assets", ["QQQ_3X", "XLK_2X", "SMH_2X"]))
        fallback_asset = self.config.get("fallback_asset", "SHY")

        if not _above_ma(prices, signal_asset, current_date, ma_window):
            return self.normalize({fallback_asset: 1.0})

        selected = _top_momentum_assets(
            prices,
            current_date,
            candidate_assets,
            lookback_months=lookback_months,
            top_n=top_n,
            ma_window=ma_window,
        )
        if not selected:
            return self.normalize({fallback_asset: 1.0})
        weight = 1.0 / len(selected)
        return self.normalize({asset: weight for asset in selected})


class TqqqBullBearFullThrottleStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        fast_window = int(self.config.get("fast_window", 50))
        slow_window = int(self.config.get("slow_window", 200))
        slope_lookback = int(self.config.get("slope_lookback", 20))
        risk_on_asset = self.config.get("risk_on_asset", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, slow_window)
        slow_rising = _ma_slope_positive(prices, signal_asset, current_date, slow_window, slope_lookback)
        if pd.notna(price) and pd.notna(fast_ma) and pd.notna(slow_ma) and price > slow_ma and fast_ma > slow_ma and slow_rising:
            return self.normalize({risk_on_asset: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class DailyTrend3xDrawdownBoostStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        fast_window = int(self.config.get("fast_window", 50))
        slow_window = int(self.config.get("slow_window", 200))
        slope_lookback = int(self.config.get("slope_lookback", 10))
        soft_drawdown = float(self.config.get("soft_drawdown_threshold", 0.15))
        deep_drawdown = float(self.config.get("deep_drawdown_threshold", 0.25))
        asset_1x = self.config.get("asset_1x", "QQQ")
        asset_2x = self.config.get("asset_2x", "QQQ_2X")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, slow_window)
        drawdown = historical_drawdown_at(prices, signal_asset, current_date)
        fast_rising = _ma_slope_positive(prices, signal_asset, current_date, fast_window, slope_lookback)
        if any(pd.isna(value) for value in [price, fast_ma, slow_ma, drawdown]):
            return self.normalize({risk_off_asset: 1.0})

        repaired_deep_drawdown = drawdown >= deep_drawdown and price > fast_ma and fast_rising
        repaired_soft_drawdown = drawdown >= soft_drawdown and price > slow_ma
        if repaired_deep_drawdown or repaired_soft_drawdown:
            return self.normalize({asset_3x: 1.0})
        if price > fast_ma and fast_ma > slow_ma:
            return self.normalize({asset_3x: 1.0})
        if price > slow_ma:
            return self.normalize({asset_2x: 1.0})
        if price > fast_ma:
            return self.normalize({asset_1x: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class TurboMomentum3xStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        fast_window = int(self.config.get("fast_window", 50))
        slow_window = int(self.config.get("slow_window", 200))
        slope_lookback = int(self.config.get("slope_lookback", 20))
        vol_window = int(self.config.get("vol_window", 20))
        max_vol = float(self.config.get("max_volatility", 0.45))
        reentry_drawdown = float(self.config.get("reentry_drawdown_threshold", 0.20))
        lookback_months = int(self.config.get("lookback_months", 6))
        candidate_assets = list(self.config.get("candidate_assets", ["QQQ_3X", "XLK_2X", "SMH_2X", "QQQ_2X"]))
        fallback_asset = self.config.get("fallback_asset", "SHY")
        asset_2x = self.config.get("asset_2x", "QQQ_2X")

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, slow_window)
        volatility = _realized_volatility(prices, signal_asset, current_date, vol_window)
        drawdown = historical_drawdown_at(prices, signal_asset, current_date)
        fast_rising = _ma_slope_positive(prices, signal_asset, current_date, fast_window, max(1, slope_lookback // 2))
        slow_rising = _ma_slope_positive(prices, signal_asset, current_date, slow_window, slope_lookback)
        if any(pd.isna(value) for value in [price, fast_ma, slow_ma, volatility, drawdown]):
            return self.normalize({fallback_asset: 1.0})
        if volatility > max_vol:
            return self.normalize({fallback_asset: 1.0})

        strong_trend = price > slow_ma and fast_ma > slow_ma and slow_rising
        repaired_after_drawdown = drawdown >= reentry_drawdown and price > fast_ma and fast_rising
        if strong_trend or repaired_after_drawdown:
            selected = _top_momentum_assets(
                prices,
                current_date,
                candidate_assets,
                lookback_months=lookback_months,
                top_n=1,
                ma_window=slow_window,
            )
            if selected:
                return self.normalize({selected[0]: 1.0})
        if price > slow_ma:
            return self.normalize({asset_2x: 1.0})
        return self.normalize({fallback_asset: 1.0})


class Breakout3xWithStopStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        high_window = int(self.config.get("high_window", 252))
        near_high_threshold = float(self.config.get("near_high_threshold", 0.95))
        fast_window = int(self.config.get("fast_window", 50))
        slow_window = int(self.config.get("slow_window", 200))
        asset_1x = self.config.get("asset_1x", "QQQ")
        asset_2x = self.config.get("asset_2x", "QQQ_2X")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, slow_window)
        rolling_high = _rolling_high(prices, signal_asset, current_date, high_window)
        if any(pd.isna(value) for value in [price, fast_ma, slow_ma, rolling_high]):
            return self.normalize({risk_off_asset: 1.0})

        near_high = price >= rolling_high * near_high_threshold
        if near_high and price > fast_ma and fast_ma > slow_ma:
            return self.normalize({asset_3x: 1.0})
        if price > fast_ma and price > slow_ma:
            return self.normalize({asset_2x: 1.0})
        if price > slow_ma:
            return self.normalize({asset_1x: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class CrashProtectedTqqqStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        ma_window = int(self.config.get("ma_window", 200))
        slope_lookback = int(self.config.get("slope_lookback", 20))
        asset_1x = self.config.get("asset_1x", "QQQ")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        ma = moving_average_at(prices, signal_asset, current_date, ma_window)
        ma_rising = _ma_slope_positive(prices, signal_asset, current_date, ma_window, slope_lookback)
        if pd.isna(price) or pd.isna(ma) or price <= ma:
            return self.normalize({risk_off_asset: 1.0})
        if ma_rising:
            return self.normalize({asset_3x: 1.0})
        return self.normalize({asset_1x: 1.0})


class AdaptiveLeverageScoreStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config.get("signal_asset", "QQQ")
        fast_window = int(self.config.get("fast_window", 50))
        slow_window = int(self.config.get("slow_window", 200))
        momentum_months = int(self.config.get("momentum_months", 6))
        vol_window = int(self.config.get("vol_window", 20))
        vol_threshold = float(self.config.get("vol_threshold", 0.25))
        drawdown_threshold = float(self.config.get("drawdown_threshold", 0.10))
        asset_1x = self.config.get("asset_1x", "QQQ")
        asset_2x = self.config.get("asset_2x", "QQQ_2X")
        asset_3x = self.config.get("asset_3x", "QQQ_3X")
        risk_off_asset = self.config.get("risk_off_asset", "SHY")

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, slow_window)
        momentum = trailing_month_return(prices, signal_asset, current_date, momentum_months)
        volatility = _realized_volatility(prices, signal_asset, current_date, vol_window)
        drawdown = historical_drawdown_at(prices, signal_asset, current_date)
        if any(pd.isna(value) for value in [price, fast_ma, slow_ma, momentum, volatility, drawdown]):
            return self.normalize({risk_off_asset: 1.0})

        score = 0
        score += int(price > slow_ma)
        score += int(fast_ma > slow_ma)
        score += int(momentum > 0)
        score += int(drawdown < drawdown_threshold)
        score += int(volatility < vol_threshold)

        if score >= 5:
            return self.normalize({asset_3x: 1.0})
        if score >= 4:
            return self.normalize({asset_2x: 1.0})
        if score >= 3:
            return self.normalize({asset_1x: 1.0})
        return self.normalize({risk_off_asset: 1.0})


class DcaLeverageBoostStrategy(Strategy):
    is_dca = True

    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        return self.contribution_plan(prices, current_date)["weights"]

    def contribution_plan(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict:
        signal_asset = self.config.get("signal_asset", "QQQ")
        ma_window = int(self.config.get("ma_window", 200))
        fast_window = int(self.config.get("fast_window", 50))
        normal_weights = dict(self.config.get("normal_weights", {"QQQ": 1.0}))
        bull_weights = dict(self.config.get("bull_weights", {"QQQ_2X": 1.0}))
        strong_bull_weights = dict(self.config.get("strong_bull_weights", {"QQQ_3X": 1.0}))
        bear_weights = dict(self.config.get("bear_weights", {"QQQ": 0.5, "SHY": 0.5}))

        price = _latest_price(prices, signal_asset, current_date)
        fast_ma = moving_average_at(prices, signal_asset, current_date, fast_window)
        slow_ma = moving_average_at(prices, signal_asset, current_date, ma_window)
        if pd.isna(price) or pd.isna(fast_ma) or pd.isna(slow_ma):
            weights = normal_weights
        elif price > fast_ma and fast_ma > slow_ma:
            weights = strong_bull_weights
        elif price > slow_ma:
            weights = bull_weights
        else:
            weights = bear_weights

        return {
            "contribution_multiplier": 1.0,
            "weights": self.normalize(weights),
            "drawdown": historical_drawdown_at(prices, signal_asset, current_date),
        }


def _latest_price(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp) -> float:
    if asset not in prices.columns:
        return np.nan
    history = prices[asset].dropna().astype(float)
    position = history.index.searchsorted(pd.Timestamp(current_date), side="right") - 1
    if position < 0:
        return np.nan
    return float(history.iloc[position])


def _top_momentum_assets(
    prices: pd.DataFrame,
    current_date: pd.Timestamp,
    assets: list[str],
    lookback_months: int,
    top_n: int,
    ma_window: int,
) -> list[str]:
    scores: dict[str, float] = {}
    for asset in assets:
        if asset not in prices.columns:
            continue
        trend_asset = _trend_asset_for(asset)
        if trend_asset in prices.columns and not _above_ma(prices, trend_asset, current_date, ma_window):
            continue
        momentum = trailing_month_return(prices, asset, current_date, lookback_months)
        if not np.isnan(momentum):
            scores[asset] = float(momentum)
    if not scores:
        return []
    return sorted(scores, key=scores.get, reverse=True)[: max(1, top_n)]


def _trend_asset_for(asset: str) -> str:
    if asset.endswith("_2X") or asset.endswith("_3X"):
        return asset.rsplit("_", 1)[0]
    return asset


def _above_ma(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp, window: int) -> bool:
    price = _latest_price(prices, asset, current_date)
    moving_average = moving_average_at(prices, asset, current_date, window)
    return pd.notna(price) and pd.notna(moving_average) and price > moving_average


def _realized_volatility(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp, window: int) -> float:
    if asset not in prices.columns:
        return np.nan
    key = (id(prices), asset, int(window))
    volatility = _VOL_CACHE.get(key)
    if volatility is None:
        returns = prices[asset].dropna().astype(float).pct_change()
        volatility = returns.rolling(window=window, min_periods=max(2, window // 2)).std(ddof=1) * math.sqrt(252)
        _VOL_CACHE[key] = volatility
    return _series_value_at(volatility, current_date)


def _rolling_high(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp, window: int) -> float:
    if asset not in prices.columns:
        return np.nan
    key = (id(prices), asset, int(window))
    rolling_high = _HIGH_CACHE.get(key)
    if rolling_high is None:
        rolling_high = prices[asset].dropna().astype(float).rolling(window=window, min_periods=window).max()
        _HIGH_CACHE[key] = rolling_high
    return _series_value_at(rolling_high, current_date)


def _ma_slope_positive(
    prices: pd.DataFrame,
    asset: str,
    current_date: pd.Timestamp,
    window: int,
    slope_lookback: int,
) -> bool:
    if asset not in prices.columns:
        return False
    key = (id(prices), asset, int(window))
    ma = _MA_SERIES_CACHE.get(key)
    if ma is None:
        ma = prices[asset].dropna().astype(float).rolling(window=window, min_periods=window).mean()
        _MA_SERIES_CACHE[key] = ma
    current_pos = ma.index.searchsorted(pd.Timestamp(current_date), side="right") - 1
    if current_pos < slope_lookback:
        return False
    current = ma.iloc[current_pos]
    previous = ma.iloc[current_pos - slope_lookback]
    return pd.notna(current) and pd.notna(previous) and float(current) > float(previous)


def _ema_at(prices: pd.DataFrame, asset: str, current_date: pd.Timestamp, window: int) -> float:
    ema = _ema_series(prices, asset, window)
    if ema is None:
        return np.nan
    return _series_value_at(ema, current_date)


def _ema_slope_positive(
    prices: pd.DataFrame,
    asset: str,
    current_date: pd.Timestamp,
    window: int,
    slope_lookback: int,
) -> bool:
    ema = _ema_series(prices, asset, window)
    if ema is None:
        return False
    current_pos = ema.index.searchsorted(pd.Timestamp(current_date), side="right") - 1
    if current_pos < slope_lookback:
        return False
    current = ema.iloc[current_pos]
    previous = ema.iloc[current_pos - slope_lookback]
    return pd.notna(current) and pd.notna(previous) and float(current) > float(previous)


def _ema_series(prices: pd.DataFrame, asset: str, window: int) -> pd.Series | None:
    if asset not in prices.columns:
        return None
    key = (id(prices), asset, int(window))
    ema = _EMA_CACHE.get(key)
    if ema is None:
        ema = (
            prices[asset]
            .dropna()
            .astype(float)
            .ewm(span=int(window), adjust=False, min_periods=int(window))
            .mean()
        )
        _EMA_CACHE[key] = ema
    return ema
