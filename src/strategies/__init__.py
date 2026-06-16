from src.strategies.base import Strategy
from src.strategies.buy_and_hold import BuyAndHoldStrategy
from src.strategies.core_trend import CoreTrendStrategy
from src.strategies.dca import DcaDrawdownBoostStrategy
from src.strategies.drawdown_buy import DrawdownBuyStrategy
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
}


def build_strategy(name: str, config: dict) -> Strategy:
    strategy_type = config.get("type")
    if strategy_type not in STRATEGY_TYPES:
        raise ValueError(f"Unknown strategy type for {name}: {strategy_type}")
    return STRATEGY_TYPES[strategy_type](name, config)
