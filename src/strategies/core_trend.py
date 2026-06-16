from __future__ import annotations

import pandas as pd

from src.indicators import moving_average_at
from src.strategies.base import Strategy


class CoreTrendStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        signal_asset = self.config["signal_asset"]
        ma_window = int(self.config.get("ma_window", 200))
        history = prices.loc[:current_date, signal_asset].dropna()
        if history.empty:
            return self._risk_off_weights()

        current_price = float(history.iloc[-1])
        moving_average = moving_average_at(prices, signal_asset, current_date, ma_window)
        if pd.notna(moving_average) and current_price > moving_average:
            return self._risk_on_weights()
        return self._risk_off_weights()

    def _risk_on_weights(self) -> dict[str, float]:
        core_asset = self.config["core_asset"]
        risk_on_asset = self.config["risk_on_asset"]
        core_weight = float(self.config["core_weight"])
        tactical_weight = float(self.config["tactical_weight"])
        weights = {core_asset: core_weight}
        weights[risk_on_asset] = weights.get(risk_on_asset, 0.0) + tactical_weight
        return self.normalize(weights)

    def _risk_off_weights(self) -> dict[str, float]:
        core_asset = self.config["core_asset"]
        risk_off_asset = self.config["risk_off_asset"]
        core_weight = float(self.config["core_weight"])
        tactical_weight = float(self.config["tactical_weight"])
        weights = {core_asset: core_weight}
        weights[risk_off_asset] = weights.get(risk_off_asset, 0.0) + tactical_weight
        return self.normalize(weights)
