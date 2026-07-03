from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path

import pandas as pd
import yaml

from src.backtest import BacktestEngine
from src.data_loader import DataLoader
from src.leverage_analysis import write_tqqq_qqq_analysis
from src.rate_loader import FredRateLoader
from src.report import generate_report
from src.strategies import build_strategy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INITIAL_CAPITAL = 20000.0
DEFAULT_MONTHLY_CONTRIBUTION = 1000.0
DEFAULT_TRANSACTION_COST = 0.0005
DEFAULT_SYNTHETIC_LEVERAGE_COSTS = {
    "annual_management_fee": 0.0,
    "annual_financing_rate": 0.0,
    "annual_financing_spread": 0.0,
    "annual_tracking_decay": 0.0,
    "trading_days": 252,
    "use_dynamic_financing_rate": False,
    "use_real_when_available": False,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QQQ Strategy Lab backtests.")
    parser.add_argument("--start", default="1970-01-01", help="Download start date, YYYY-MM-DD.")
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
    start: str = "1970-01-01",
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
    prices, proxy_summary = apply_asset_history_proxies(prices, assets_config.get("asset_history_proxies", {}))
    leverage_costs = assets_config.get("synthetic_leverage", {})
    financing_rates = load_financing_rates(
        leverage_costs=leverage_costs,
        start=start,
        end=end,
        force_refresh=force_refresh,
    )
    prices = add_synthetic_leverage_assets(
        prices,
        collect_required_assets(strategies_config),
        leverage_costs=leverage_costs,
        financing_rates=financing_rates,
    )
    leverage_calibration = build_leverage_calibration(
        prices=prices,
        required_assets=collect_required_assets(strategies_config),
        leverage_costs=leverage_costs,
        financing_rates=financing_rates,
    )

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
        result.metadata["synthetic_leverage_costs"] = leverage_costs
        result.metadata["dynamic_financing_rates"] = financing_rates is not None and not financing_rates.empty
        results.append(result)

    results_frame = generate_report(
        results=results,
        reports_dir=PROJECT_ROOT / "reports",
        start_date=min(result.equity_curve.index[0] for result in results),
        end_date=max(result.equity_curve.index[-1] for result in results),
        transaction_cost=transaction_cost,
        leverage_calibration=leverage_calibration,
        proxy_summary=proxy_summary,
    )
    write_tqqq_qqq_analysis(
        prices=prices,
        reports_dir=PROJECT_ROOT / "reports",
        leverage_costs=leverage_costs,
        financing_rates=financing_rates,
        requested_start=start,
    )
    return results_frame


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
    for proxy_config in (assets_config.get("asset_history_proxies") or {}).values():
        for proxy in proxy_config.get("proxies", []):
            if proxy.get("ticker"):
                tickers.add(proxy["ticker"])
    tickers.update((assets_config.get("synthetic_leverage", {}).get("real_asset_map") or {}).values())

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
        for key in ["assets", "candidate_assets", "defensive_assets"]:
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
    for key in ["assets", "candidate_assets", "defensive_assets"]:
        assets.update(config.get(key, []))
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


def apply_asset_history_proxies(prices: pd.DataFrame, proxy_config: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not proxy_config:
        return prices, pd.DataFrame()

    output = prices.copy()
    rows = []
    for asset, config in proxy_config.items():
        proxies = list((config or {}).get("proxies", []))
        if asset not in output.columns or not proxies:
            continue

        combined = output[asset].dropna().astype(float)
        original_start = combined.index[0] if not combined.empty else pd.NaT
        for proxy in reversed(proxies):
            proxy_ticker = proxy.get("ticker")
            if not proxy_ticker or proxy_ticker not in output.columns or combined.empty:
                continue

            proxy_series = output[proxy_ticker].dropna().astype(float)
            common = proxy_series.index.intersection(combined.index)
            if proxy_series.empty or common.empty:
                continue

            anchor_date = common[0]
            if proxy_series.loc[anchor_date] <= 0:
                continue
            scale = float(combined.loc[anchor_date]) / float(proxy_series.loc[anchor_date])
            proxy_scaled = proxy_series * scale
            prehistory = proxy_scaled.loc[proxy_scaled.index < combined.index[0]]
            if prehistory.empty:
                continue

            combined = pd.concat([prehistory, combined]).sort_index()
            rows.append(
                {
                    "Asset": asset,
                    "Proxy Ticker": proxy_ticker,
                    "Proxy Label": proxy.get("label", ""),
                    "Proxy Start": prehistory.index[0].date().isoformat(),
                    "Proxy End": prehistory.index[-1].date().isoformat(),
                    "Anchor Date": anchor_date.date().isoformat(),
                    "Scale": scale,
                    "Original Asset Start": original_start.date().isoformat() if pd.notna(original_start) else "",
                }
            )

        new_index = output.index.union(combined.index).sort_values()
        output = output.reindex(new_index)
        output[asset] = combined.reindex(new_index)

    return output.sort_index(), pd.DataFrame(rows)


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


def load_financing_rates(
    leverage_costs: dict | None,
    start: str,
    end: str | None,
    force_refresh: bool = False,
) -> pd.Series | None:
    if not leverage_costs or not leverage_costs.get("use_dynamic_financing_rate", False):
        return None

    preferred = leverage_costs.get("financing_rate_series", "SOFR")
    fallback = leverage_costs.get("fallback_financing_rate_series", "FEDFUNDS")
    series_ids = [series_id for series_id in [preferred, fallback] if series_id]
    if not series_ids:
        return None

    rates = FredRateLoader(PROJECT_ROOT / "data" / "raw" / "rates").load_rates(
        series_ids,
        start=start,
        end=end,
        force_refresh=force_refresh,
    )
    if rates.empty:
        return None

    output = pd.Series(index=rates.index, dtype=float, name="financing_rate")
    if fallback in rates:
        output = rates[fallback].combine_first(output)
    if preferred in rates:
        output = rates[preferred].combine_first(output)
    return output.sort_index().ffill().dropna()


def add_synthetic_leverage_assets(
    prices,
    required_assets: list[str],
    leverage_costs: dict | None = None,
    financing_rates: pd.Series | None = None,
):
    output = prices.copy()
    for asset in required_assets:
        multiple = leverage_multiple(asset)
        if multiple is None or asset in output.columns:
            continue
        base_asset = base_asset_name(asset)
        if base_asset not in output.columns:
            raise ValueError(f"Cannot synthesize {asset}; missing base asset {base_asset}.")

        synthetic = build_synthetic_leverage_series(
            base=output[base_asset].dropna(),
            asset=asset,
            multiple=multiple,
            leverage_costs=leverage_costs,
            financing_rates=financing_rates,
        )
        real_asset = synthetic_leverage_real_asset(asset, leverage_costs)
        if real_asset and real_asset in output.columns and synthetic_leverage_cost_config(asset, leverage_costs).get(
            "use_real_when_available",
            False,
        ):
            synthetic = stitch_real_leverage_series(synthetic, output[real_asset].dropna())
        output[asset] = synthetic
    return output


def build_synthetic_leverage_series(
    base: pd.Series,
    asset: str,
    multiple: int,
    leverage_costs: dict | None = None,
    financing_rates: pd.Series | None = None,
) -> pd.Series:
    base = base.dropna().astype(float)
    if base.empty:
        return pd.Series(dtype=float, name=asset)
    daily_cost = synthetic_leverage_daily_cost_series(base.index, asset, multiple, leverage_costs, financing_rates)
    leveraged_returns = base.pct_change().fillna(0.0) * multiple - daily_cost
    leveraged_returns.iloc[0] = 0.0
    leveraged_returns = leveraged_returns.clip(lower=-0.99)
    return ((1.0 + leveraged_returns).cumprod() * float(base.iloc[0])).rename(asset)


def stitch_real_leverage_series(synthetic: pd.Series, real: pd.Series) -> pd.Series:
    synthetic = synthetic.dropna().astype(float)
    real = real.dropna().astype(float)
    common = synthetic.index.intersection(real.index)
    if synthetic.empty or real.empty or common.empty:
        return synthetic

    first_real_date = common[0]
    if real.loc[first_real_date] <= 0:
        return synthetic
    scale = float(synthetic.loc[first_real_date]) / float(real.loc[first_real_date])
    stitched = synthetic.copy()
    real_scaled = (real.loc[first_real_date:] * scale).reindex(stitched.loc[first_real_date:].index).ffill()
    stitched.loc[first_real_date:] = real_scaled
    return stitched.rename(synthetic.name)


def synthetic_leverage_daily_cost(asset: str, multiple: int, leverage_costs: dict | None = None) -> float:
    config = synthetic_leverage_cost_config(asset, leverage_costs)
    trading_days = int(config.get("trading_days", DEFAULT_SYNTHETIC_LEVERAGE_COSTS["trading_days"]))
    if trading_days <= 0:
        raise ValueError("synthetic leverage trading_days must be positive.")

    management_fee = float(config.get("annual_management_fee", 0.0))
    financing_rate = float(config.get("annual_financing_rate", 0.0))
    financing_spread = float(config.get("annual_financing_spread", 0.0))
    tracking_decay = float(config.get("annual_tracking_decay", 0.0))
    borrowed_exposure = max(0, multiple - 1)
    annual_drag = management_fee + tracking_decay + borrowed_exposure * (financing_rate + financing_spread)
    return annual_drag / trading_days


def synthetic_leverage_daily_cost_series(
    index: pd.DatetimeIndex,
    asset: str,
    multiple: int,
    leverage_costs: dict | None = None,
    financing_rates: pd.Series | None = None,
) -> pd.Series:
    config = synthetic_leverage_cost_config(asset, leverage_costs)
    trading_days = int(config.get("trading_days", DEFAULT_SYNTHETIC_LEVERAGE_COSTS["trading_days"]))
    if trading_days <= 0:
        raise ValueError("synthetic leverage trading_days must be positive.")

    fixed_financing_rate = float(config.get("annual_financing_rate", 0.0))
    if financing_rates is not None and not financing_rates.empty:
        financing_rate = financing_rates.reindex(index).ffill().fillna(fixed_financing_rate).astype(float)
    else:
        financing_rate = pd.Series(fixed_financing_rate, index=index, dtype=float)

    management_fee = float(config.get("annual_management_fee", 0.0))
    financing_spread = float(config.get("annual_financing_spread", 0.0))
    tracking_decay = float(config.get("annual_tracking_decay", 0.0))
    borrowed_exposure = max(0, multiple - 1)
    annual_drag = management_fee + tracking_decay + borrowed_exposure * (financing_rate + financing_spread)
    return (annual_drag / trading_days).rename(asset)


def synthetic_leverage_cost_config(asset: str, leverage_costs: dict | None = None) -> dict:
    config = dict(DEFAULT_SYNTHETIC_LEVERAGE_COSTS)
    if leverage_costs:
        config.update({key: value for key, value in leverage_costs.items() if key != "asset_overrides"})
        overrides = leverage_costs.get("asset_overrides") or {}
        if asset in overrides:
            config.update(overrides[asset] or {})
    return config


def synthetic_leverage_real_asset(asset: str, leverage_costs: dict | None = None) -> str | None:
    if not leverage_costs:
        return None
    return (leverage_costs.get("real_asset_map") or {}).get(asset)


def build_leverage_calibration(
    prices: pd.DataFrame,
    required_assets: list[str],
    leverage_costs: dict | None = None,
    financing_rates: pd.Series | None = None,
) -> pd.DataFrame:
    rows = []
    for asset in sorted(set(required_assets)):
        multiple = leverage_multiple(asset)
        real_asset = synthetic_leverage_real_asset(asset, leverage_costs)
        base_asset = base_asset_name(asset)
        if multiple is None or not real_asset or base_asset not in prices or real_asset not in prices:
            continue

        synthetic = build_synthetic_leverage_series(
            base=prices[base_asset],
            asset=asset,
            multiple=multiple,
            leverage_costs=leverage_costs,
            financing_rates=financing_rates,
        )
        real = prices[real_asset].dropna().astype(float)
        common = synthetic.dropna().index.intersection(real.index)
        if len(common) < 252:
            continue

        synthetic_window = synthetic.loc[common]
        real_window = real.loc[common]
        synthetic_norm = synthetic_window / float(synthetic_window.iloc[0])
        real_norm = real_window / float(real_window.iloc[0])
        gap = synthetic_norm / real_norm - 1.0
        synthetic_returns = synthetic_window.pct_change().dropna()
        real_returns = real_window.pct_change().dropna()
        tracking_diff = synthetic_returns - real_returns
        rows.append(
            {
                "Synthetic Asset": asset,
                "Real ETF": real_asset,
                "Start Date": common[0].date().isoformat(),
                "End Date": common[-1].date().isoformat(),
                "Years": (len(common) - 1) / 252,
                "Synthetic CAGR": _series_cagr(synthetic_norm),
                "Real ETF CAGR": _series_cagr(real_norm),
                "CAGR Gap": _series_cagr(synthetic_norm) - _series_cagr(real_norm),
                "Synthetic MaxDD": _series_max_drawdown(synthetic_norm),
                "Real ETF MaxDD": _series_max_drawdown(real_norm),
                "End Gap": float(gap.iloc[-1]),
                "Max Abs Gap": float(gap.abs().max()),
                "Daily Return Corr": float(synthetic_returns.corr(real_returns)),
                "Annualized Tracking Error": float(tracking_diff.std(ddof=1) * math.sqrt(252)),
            }
        )
    return pd.DataFrame(rows)


def _series_cagr(series: pd.Series) -> float:
    series = series.dropna().astype(float)
    if len(series) < 2 or series.iloc[0] <= 0 or series.iloc[-1] <= 0:
        return float("nan")
    years = (len(series) - 1) / 252
    if years <= 0:
        return float("nan")
    return float((series.iloc[-1] / series.iloc[0]) ** (1.0 / years) - 1.0)


def _series_max_drawdown(series: pd.Series) -> float:
    series = series.dropna().astype(float)
    if series.empty:
        return float("nan")
    return float((series / series.cummax() - 1.0).min())


if __name__ == "__main__":
    main()
