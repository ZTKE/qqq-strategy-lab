from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


def normalize_weights(weights: Mapping[str, float], tolerance: float = 1e-10) -> dict[str, float]:
    clean = {str(asset): float(weight) for asset, weight in weights.items() if abs(float(weight)) > tolerance}
    if any(weight < -tolerance for weight in clean.values()):
        raise ValueError(f"Weights cannot be negative: {weights}")

    total = sum(clean.values())
    if total <= tolerance:
        raise ValueError(f"Weights must sum to a positive value: {weights}")

    return {asset: weight / total for asset, weight in clean.items()}


def weights_turnover(old_weights: Mapping[str, float], new_weights: Mapping[str, float]) -> float:
    assets = set(old_weights) | set(new_weights)
    return sum(abs(float(new_weights.get(asset, 0.0)) - float(old_weights.get(asset, 0.0))) for asset in assets)


def weighted_return(weights: Mapping[str, float], daily_returns: pd.Series) -> float:
    total = 0.0
    for asset, weight in weights.items():
        value = daily_returns.get(asset, 0.0)
        if pd.isna(value):
            value = 0.0
        total += float(weight) * float(value)
    return total
