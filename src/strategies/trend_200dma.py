from __future__ import annotations

import pandas as pd

from src.indicators import moving_average_at
from src.strategies.base import Strategy


class Trend200DmaStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config["signal_asset"]
        ma_window = int(self.config.get("ma_window", 200))
        history = prices.loc[:current_date, signal_asset].dropna()
        if history.empty:
            return self.normalize(self.config["risk_off"])

        current_price = float(history.iloc[-1])
        moving_average = moving_average_at(prices, signal_asset, current_date, ma_window)
        if pd.notna(moving_average) and current_price > moving_average:
            return self.normalize(self.config["risk_on"])
        return self.normalize(self.config["risk_off"])
