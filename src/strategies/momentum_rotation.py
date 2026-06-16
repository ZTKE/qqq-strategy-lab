from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators import moving_average_at, trailing_month_return
from src.strategies.base import Strategy


class MomentumRotationStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        assets = list(self.config["assets"])
        lookback_months = int(self.config.get("lookback_months", 6))
        top_n = int(self.config.get("top_n", 2))
        ma_window = int(self.config.get("ma_window", 200))
        fallback_asset = self.config.get("fallback_asset", "SHY")

        scores: dict[str, float] = {}
        for asset in assets:
            if asset not in prices.columns:
                continue
            history = prices.loc[:current_date, asset].dropna()
            if history.empty:
                continue

            current_price = float(history.iloc[-1])
            moving_average = moving_average_at(prices, asset, current_date, ma_window)
            if pd.isna(moving_average) or current_price < moving_average:
                continue

            momentum = trailing_month_return(prices, asset, current_date, lookback_months)
            if not np.isnan(momentum):
                scores[asset] = float(momentum)

        if not scores:
            return self.normalize({fallback_asset: 1.0})

        selected = sorted(scores, key=scores.get, reverse=True)[:top_n]
        weight = 1.0 / len(selected)
        return self.normalize({asset: weight for asset in selected})
