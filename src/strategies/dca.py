from __future__ import annotations

import pandas as pd

from src.indicators import historical_drawdown_at
from src.strategies.base import Strategy


class DcaDrawdownBoostStrategy(Strategy):
    is_dca = True

    def generate_weights(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
        return self.contribution_plan(prices, current_date)["weights"]

    def contribution_plan(self, prices: pd.DataFrame, current_date: pd.Timestamp) -> dict:
        signal_asset = self.config["signal_asset"]
        drawdown = historical_drawdown_at(prices, signal_asset, current_date)
        selected = {
            "contribution_multiplier": 1.0,
            "weights": self.config["normal_weights"],
        }

        if pd.notna(drawdown):
            for rule in self.config.get("rules", []):
                if drawdown >= float(rule["drawdown_gte"]):
                    selected = {
                        "contribution_multiplier": float(rule.get("contribution_multiplier", 1.0)),
                        "weights": rule["weights"],
                    }

        return {
            "contribution_multiplier": selected["contribution_multiplier"],
            "weights": self.normalize(selected["weights"]),
            "drawdown": float(drawdown) if pd.notna(drawdown) else None,
        }
