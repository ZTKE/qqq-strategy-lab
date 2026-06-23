from __future__ import annotations

import argparse
import copy
from pathlib import Path

import pandas as pd
import yaml

from src.backtest import BacktestEngine
from src.data_loader import DataLoader
from src.report import generate_report
from src.strategies import build_strategy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INITIAL_CAPITAL = 20000.0
DEFAULT_MONTHLY_CONTRIBUTION = 3000.0
DEFAULT_TRANSACTION_COST = 0.0005


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QQQ Strategy Lab backtests.")
    parser.add_argument("--start", default="2000-01-01", help="Download start date, YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="Inclusive end date, YYYY-MM-DD. Defaults to latest available data.")
    parser.add_argument("--initial-capital", type=float, default=DEFAULT_INITIAL_CAPITAL, help="Initial investment amount.")
    parser.add_argument(
        "--monthly-contribution",
        type=float,
        default=DEFAULT_MONTHLY_CONTRIBUTION,
        help="Monthly contribution amount.",
    )
    parser.add_argument("--transaction-cost", type=float, default=DEFAULT_TRANSACTION_COST, help="Transaction cost rate.")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cached CSV files and re-download.")
    args = parser.parse_args()

    run_backtests(
        start=args.start,
        end=args.end,
        force_refresh=args.force_refresh,
        initial_capital=args.initial_capital,
        monthly_contribution=args.monthly_contribution,
        transaction_cost=args.transaction_cost,
    )

    print("Backtest complete.")
    print(f"Project: {PROJECT_ROOT}")
    print(f"Report: {PROJECT_ROOT / 'reports' / 'summary.md'}")
    print(f"Dashboard: {PROJECT_ROOT / 'reports' / 'dashboard.html'}")
    print(f"Charts: {PROJECT_ROOT / 'reports' / 'charts.html'}")
    print(f"Results: {PROJECT_ROOT / 'reports' / 'results.csv'}")


def run_backtests(
    start: str = "2000-01-01",
    end: str | None = None,
    force_refresh: bool = False,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    monthly_contribution: float = DEFAULT_MONTHLY_CONTRIBUTION,
    transaction_cost: float = DEFAULT_TRANSACTION_COST,
) -> pd.DataFrame:
    if initial_capital < 0:
        raise ValueError("initial_capital must be non-negative.")
    if monthly_contribution < 0:
        raise ValueError("monthly_contribution must be non-negative.")
    if transaction_cost < 0:
        raise ValueError("transaction_cost must be non-negative.")

    assets_config = _load_yaml(PROJECT_ROOT / "configs" / "assets.yaml")
    strategies_config = _load_yaml(PROJECT_ROOT / "configs" / "strategies.yaml")
    tickers = collect_tickers(assets_config, strategies_config)

    loader = DataLoader(PROJECT_ROOT / "data" / "raw")
    prices = loader.load_prices(tickers, start=start, end=end, force_refresh=force_refresh)
    prices = add_synthetic_leverage_assets(prices, collect_required_assets(strategies_config))

    results = []
    for name, config in strategies_config.items():
        strategy_config = _with_cashflow_settings(config, initial_capital, monthly_contribution)
        required_assets = strategy_required_assets(strategy_config)
        strategy_prices = prices[required_assets].ffill().dropna(how="all")
        if strategy_prices.empty:
            raise RuntimeError(f"No aligned price history is available for strategy {name}: {required_assets}")

        strategy = build_strategy(name, strategy_config)
        engine = BacktestEngine(
            strategy_prices,
            initial_capital=initial_capital,
            monthly_contribution=monthly_contribution,
            transaction_cost=transaction_cost,
        )
        result = engine.run(strategy)
        result.metadata["required_assets"] = required_assets
        result.metadata["start_date"] = strategy_prices.index[0]
        result.metadata["end_date"] = strategy_prices.index[-1]
        results.append(result)

    return generate_report(
        results=results,
        reports_dir=PROJECT_ROOT / "reports",
        start_date=min(result.equity_curve.index[0] for result in results),
        end_date=max(result.equity_curve.index[-1] for result in results),
        transaction_cost=transaction_cost,
    )


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _with_cashflow_settings(config: dict, initial_capital: float, monthly_contribution: float) -> dict:
    output = copy.deepcopy(config)
    if str(output.get("type", "")).startswith("dca"):
        output["initial_capital"] = float(initial_capital)
        output["monthly_contribution"] = float(monthly_contribution)
    return output


def collect_tickers(assets_config: dict, strategies_config: dict) -> list[str]:
    tickers: set[str] = set()
    for group in assets_config.get("assets", {}).values():
        tickers.update(group)

    for config in strategies_config.values():
        for key in [
            "signal_asset",
            "fallback_asset",
            "core_asset",
            "risk_on_asset",
            "risk_off_asset",
            "asset_1x",
            "asset_2x",
            "asset_3x",
        ]:
            if config.get(key):
                tickers.add(base_asset_name(config[key]))
        for key in ["assets"]:
            tickers.update(base_asset_name(asset) for asset in config.get(key, []))
        for key in ["leveraged_assets"]:
            tickers.update(base_asset_name(asset) for asset in (config.get(key) or {}).values())
        for key in ["weights", "risk_on", "risk_off", "normal_weights", "bull_weights", "strong_bull_weights", "bear_weights"]:
            tickers.update(base_asset_name(asset) for asset in (config.get(key) or {}).keys())
        for rule in config.get("rules", []):
            tickers.update(base_asset_name(asset) for asset in (rule.get("weights") or {}).keys())

    return sorted(ticker for ticker in tickers if ticker)


def strategy_required_assets(config: dict) -> list[str]:
    assets: set[str] = set()
    for key in [
        "signal_asset",
        "fallback_asset",
        "core_asset",
        "risk_on_asset",
        "risk_off_asset",
        "asset_1x",
        "asset_2x",
        "asset_3x",
    ]:
        if config.get(key):
            assets.add(config[key])
    assets.update(config.get("assets", []))
    assets.update((config.get("leveraged_assets") or {}).values())
    for key in ["weights", "risk_on", "risk_off", "normal_weights", "bull_weights", "strong_bull_weights", "bear_weights"]:
        assets.update((config.get(key) or {}).keys())
    for rule in config.get("rules", []):
        assets.update((rule.get("weights") or {}).keys())
    return sorted(assets)


def collect_required_assets(strategies_config: dict) -> list[str]:
    assets: set[str] = set()
    for config in strategies_config.values():
        assets.update(strategy_required_assets(config))
    return sorted(assets)


def base_asset_name(asset: str) -> str:
    if asset.endswith("_2X") or asset.endswith("_3X"):
        return asset.rsplit("_", 1)[0]
    return asset


def leverage_multiple(asset: str) -> int | None:
    if asset.endswith("_2X"):
        return 2
    if asset.endswith("_3X"):
        return 3
    return None


def add_synthetic_leverage_assets(prices, required_assets: list[str]):
    output = prices.copy()
    for asset in required_assets:
        multiple = leverage_multiple(asset)
        if multiple is None or asset in output.columns:
            continue
        base_asset = base_asset_name(asset)
        if base_asset not in output.columns:
            raise ValueError(f"Cannot synthesize {asset}; missing base asset {base_asset}.")

        base = output[base_asset].dropna()
        leveraged_returns = base.pct_change().fillna(0.0) * multiple
        leveraged_returns = leveraged_returns.clip(lower=-0.99)
        output[asset] = (1.0 + leveraged_returns).cumprod() * float(base.iloc[0])
    return output


if __name__ == "__main__":
    main()
