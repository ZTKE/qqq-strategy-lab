from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from src.backtest import BacktestEngine
from src.data_loader import DataLoader
from src.report import generate_report
from src.strategies import build_strategy


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QQQ Strategy Lab backtests.")
    parser.add_argument("--start", default="2000-01-01", help="Download start date, YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="Download end date, YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cached CSV files and re-download.")
    args = parser.parse_args()

    assets_config = _load_yaml(PROJECT_ROOT / "configs" / "assets.yaml")
    strategies_config = _load_yaml(PROJECT_ROOT / "configs" / "strategies.yaml")
    tickers = collect_tickers(assets_config, strategies_config)

    loader = DataLoader(PROJECT_ROOT / "data" / "raw")
    prices = loader.load_prices(tickers, start=args.start, end=args.end, force_refresh=args.force_refresh)

    results = []
    for name, config in strategies_config.items():
        required_assets = strategy_required_assets(config)
        strategy_prices = prices[required_assets].ffill().dropna(how="all")
        if strategy_prices.empty:
            raise RuntimeError(f"No aligned price history is available for strategy {name}: {required_assets}")

        strategy = build_strategy(name, config)
        engine = BacktestEngine(strategy_prices, initial_capital=20000.0, monthly_contribution=3000.0, transaction_cost=0.0005)
        result = engine.run(strategy)
        result.metadata["required_assets"] = required_assets
        result.metadata["start_date"] = strategy_prices.index[0]
        result.metadata["end_date"] = strategy_prices.index[-1]
        results.append(result)

    generate_report(
        results=results,
        reports_dir=PROJECT_ROOT / "reports",
        start_date=min(result.equity_curve.index[0] for result in results),
        end_date=max(result.equity_curve.index[-1] for result in results),
        transaction_cost=0.0005,
    )

    print("Backtest complete.")
    print(f"Project: {PROJECT_ROOT}")
    print(f"Report: {PROJECT_ROOT / 'reports' / 'summary.md'}")
    print(f"Results: {PROJECT_ROOT / 'reports' / 'results.csv'}")


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def collect_tickers(assets_config: dict, strategies_config: dict) -> list[str]:
    tickers: set[str] = set()
    for group in assets_config.get("assets", {}).values():
        tickers.update(group)

    for config in strategies_config.values():
        for key in ["signal_asset", "fallback_asset", "core_asset", "risk_on_asset", "risk_off_asset"]:
            if config.get(key):
                tickers.add(config[key])
        for key in ["assets"]:
            tickers.update(config.get(key, []))
        for key in ["weights", "risk_on", "risk_off", "normal_weights"]:
            tickers.update((config.get(key) or {}).keys())
        for rule in config.get("rules", []):
            tickers.update((rule.get("weights") or {}).keys())

    return sorted(tickers)


def strategy_required_assets(config: dict) -> list[str]:
    assets: set[str] = set()
    for key in ["signal_asset", "fallback_asset", "core_asset", "risk_on_asset", "risk_off_asset"]:
        if config.get(key):
            assets.add(config[key])
    assets.update(config.get("assets", []))
    for key in ["weights", "risk_on", "risk_off", "normal_weights"]:
        assets.update((config.get(key) or {}).keys())
    for rule in config.get("rules", []):
        assets.update((rule.get("weights") or {}).keys())
    return sorted(assets)


if __name__ == "__main__":
    main()
