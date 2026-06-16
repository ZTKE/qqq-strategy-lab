from __future__ import annotations

import pandas as pd

from src.portfolio import normalize_weights


class Strategy:
    is_dca = False

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        raise NotImplementedError

    def normalize(self, weights: dict[str, float]) -> dict[str, float]:
        return normalize_weights(weights)

    def available_prices(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> pd.DataFrame:
        return prices.loc[:current_date]
