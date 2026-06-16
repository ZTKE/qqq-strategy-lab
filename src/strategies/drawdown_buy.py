from __future__ import annotations

import pandas as pd

from src.indicators import historical_drawdown_at
from src.strategies.base import Strategy


class DrawdownBuyStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config["signal_asset"]
        drawdown = historical_drawdown_at(prices, signal_asset, current_date)
        if pd.isna(drawdown):
            return self.normalize(self.config["rules"][0]["weights"])

        for rule in self.config["rules"]:
            threshold = float(rule["drawdown_lt"])
            if drawdown < threshold:
                return self.normalize(rule["weights"])

        return self.normalize(self.config["rules"][-1]["weights"])
