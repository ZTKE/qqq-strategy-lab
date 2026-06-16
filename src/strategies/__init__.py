from src.strategies.base import Strategy
from src.strategies.buy_and_hold import BuyAndHoldStrategy
from src.strategies.core_trend import CoreTrendStrategy
from src.strategies.dca import DcaDrawdownBoostStrategy
from src.strategies.drawdown_buy import DrawdownBuyStrategy
from src.strategies.leveraged import (
    AdaptiveLeverageScoreStrategy,
    Breakout3xWithStopStrategy,
    CoreTrend2xStrategy,
    CrashProtectedTqqqStrategy,
    DailyTrend2xStrategy,
    DailyTrend3xDefensiveStrategy,
    DcaLeverageBoostStrategy,
    DualMaLeverageLadderStrategy,
    MomentumRotation2xStrategy,
    VolTargetTrendStrategy,
)
from src.strategies.momentum_rotation import MomentumRotationStrategy
from src.strategies.static_allocation import StaticAllocationStrategy
from src.strategies.trend_200dma import Trend200DmaStrategy


STRATEGY_TYPES = {
    "buy_and_hold": BuyAndHoldStrategy,
    "static_allocation": StaticAllocationStrategy,
    "trend_200dma": Trend200DmaStrategy,
    "core_trend": CoreTrendStrategy,
    "drawdown_buy": DrawdownBuyStrategy,
    "momentum_rotation": MomentumRotationStrategy,
    "dca": DcaDrawdownBoostStrategy,
    "daily_trend_2x": DailyTrend2xStrategy,
    "daily_trend_3x_defensive": DailyTrend3xDefensiveStrategy,
    "dual_ma_leverage_ladder": DualMaLeverageLadderStrategy,
    "vol_target_trend": VolTargetTrendStrategy,
    "core_trend_2x": CoreTrend2xStrategy,
    "momentum_rotation_2x": MomentumRotation2xStrategy,
    "breakout_3x_with_stop": Breakout3xWithStopStrategy,
    "crash_protected_tqqq": CrashProtectedTqqqStrategy,
    "adaptive_leverage_score": AdaptiveLeverageScoreStrategy,
    "dca_leverage_boost": DcaLeverageBoostStrategy,
}


def build_strategy(name: str, config: dict) -> Strategy:
    strategy_type = config.get("type")
    if strategy_type not in STRATEGY_TYPES:
        raise ValueError(f"Unknown strategy type for {name}: {strategy_type}")
    return STRATEGY_TYPES[strategy_type](name, config)
