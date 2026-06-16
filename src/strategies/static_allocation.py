from __future__ import annotations

import pandas as pd

from src.strategies.base import Strategy


class StaticAllocationStrategy(Strategy):
    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        return self.normalize(self.config["weights"])
