from __future__ import annotations

from pathlib import Path

import math
import numpy as np
import pandas as pd

from src.metrics import annualized_volatility, cagr, max_drawdown, total_return


DEFAULT_COSTS = {
    "annual_management_fee": 0.0,
    "annual_financing_rate": 0.0,
    "annual_financing_spread": 0.0,
    "annual_tracking_decay": 0.0,
    "trading_days": 252,
}


def write_tqqq_qqq_analysis(
    prices: pd.DataFrame,
    reports_dir: str | Path,
    leverage_costs: dict | None = None,
    financing_rates: pd.Series | None = None,
    requested_start: str = "1970-01-01",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    series_metrics, drag_summary = build_tqqq_qqq_analysis(
        prices=prices,
        leverage_costs=leverage_costs,
        financing_rates=financing_rates,
        requested_start=requested_start,
    )

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    series_metrics.to_csv(reports_path / "tqqq_qqq_series_metrics.csv", index=False)
    drag_summary.to_csv(reports_path / "tqqq_qqq_drag_summary.csv", index=False)
    (reports_path / "tqqq_qqq_analysis.md").write_text(
        _build_markdown(series_metrics, drag_summary, requested_start),
        encoding="utf-8",
    )
    return series_metrics, drag_summary


def build_tqqq_qqq_analysis(
    prices: pd.DataFrame,
    leverage_costs: dict | None = None,
    financing_rates: pd.Series | None = None,
    requested_start: str = "1970-01-01",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "QQQ" not in prices:
        return pd.DataFrame(), pd.DataFrame()

    qqq = prices["QQQ"].dropna().astype(float)
    if qqq.empty:
        return pd.DataFrame(), pd.DataFrame()

    gross_3x = _daily_leverage_series(qqq, multiple=3, name="QQQ Daily 3x Gross")
    cost_model_3x = _daily_leverage_series(
        qqq,
        multiple=3,
        name="QQQ Daily 3x Cost Model",
        daily_cost=_daily_cost_series(qqq.index, "QQQ_3X", 3, leverage_costs, financing_rates),
    )

    stitched = _optional_series(prices, "QQQ_3X", "TQQQ-like Stitched")
    real_tqqq = _optional_series(prices, "TQQQ", "Real TQQQ")

    metrics_rows: list[dict] = []
    drag_rows: list[dict] = []
    requested = pd.Timestamp(requested_start)

    long_series = {
        "QQQ": qqq,
        "QQQ Daily 3x Gross": gross_3x,
        "QQQ Daily 3x Cost Model": cost_model_3x,
    }
    if stitched is not None:
        long_series["TQQQ-like Stitched"] = stitched
    _append_window(
        metrics_rows,
        drag_rows,
        window_name="Long simulation from requested 1970 start",
        series_by_name=long_series,
        start=max(requested, qqq.index[0]),
        end=qqq.index[-1],
        preferred_tqqq_like="TQQQ-like Stitched" if stitched is not None else "QQQ Daily 3x Cost Model",
    )

    if real_tqqq is not None:
        real_start = max(qqq.index[0], real_tqqq.index[0])
        real_end = min(qqq.index[-1], real_tqqq.index[-1])
        real_series = {
            "QQQ": qqq,
            "QQQ Daily 3x Gross": gross_3x,
            "QQQ Daily 3x Cost Model": cost_model_3x,
            "Real TQQQ": real_tqqq,
        }
        if stitched is not None:
            real_series["TQQQ-like Stitched"] = stitched
        _append_window(
            metrics_rows,
            drag_rows,
            window_name="Real TQQQ overlap",
            series_by_name=real_series,
            start=real_start,
            end=real_end,
            preferred_tqqq_like="Real TQQQ",
        )

    return pd.DataFrame(metrics_rows), pd.DataFrame(drag_rows)


def _optional_series(prices: pd.DataFrame, column: str, name: str) -> pd.Series | None:
    if column not in prices:
        return None
    series = prices[column].dropna().astype(float)
    if series.empty:
        return None
    return series.rename(name)


def _append_window(
    metrics_rows: list[dict],
    drag_rows: list[dict],
    window_name: str,
    series_by_name: dict[str, pd.Series],
    start: pd.Timestamp,
    end: pd.Timestamp,
    preferred_tqqq_like: str,
) -> None:
    frame = pd.concat(series_by_name.values(), axis=1).sort_index().ffill()
    frame = frame.loc[(frame.index >= start) & (frame.index <= end)].dropna()
    if len(frame) < 2 or "QQQ" not in frame:
        return

    window_metrics: dict[str, dict] = {}
    for column in frame.columns:
        normalized = (frame[column] / float(frame[column].iloc[0])).rename(column)
        returns = frame[column].pct_change().dropna()
        row = {
            "Window": window_name,
            "Series": column,
            "Start Date": frame.index[0].date().isoformat(),
            "End Date": frame.index[-1].date().isoformat(),
            "Years": (len(frame) - 1) / 252,
            "Total Return": total_return(normalized),
            "CAGR": cagr(normalized),
            "Max Drawdown": max_drawdown(normalized),
            "Volatility": annualized_volatility(returns),
            "Worst Daily Return": float(returns.min()) if not returns.empty else np.nan,
            "Final Multiple": float(normalized.iloc[-1]),
        }
        metrics_rows.append(row)
        window_metrics[column] = row

    qqq_metrics = window_metrics.get("QQQ", {})
    gross_metrics = window_metrics.get("QQQ Daily 3x Gross", {})
    cost_metrics = window_metrics.get("QQQ Daily 3x Cost Model", {})
    preferred_metrics = window_metrics.get(preferred_tqqq_like, {})
    real_metrics = window_metrics.get("Real TQQQ", {})

    qqq_cagr = qqq_metrics.get("CAGR", np.nan)
    gross_cagr = gross_metrics.get("CAGR", np.nan)
    cost_cagr = cost_metrics.get("CAGR", np.nan)
    preferred_cagr = preferred_metrics.get("CAGR", np.nan)
    real_cagr = real_metrics.get("CAGR", np.nan)

    drag_rows.append(
        {
            "Window": window_name,
            "Start Date": frame.index[0].date().isoformat(),
            "End Date": frame.index[-1].date().isoformat(),
            "Years": (len(frame) - 1) / 252,
            "QQQ CAGR": qqq_cagr,
            "3x QQQ CAGR (Naive)": qqq_cagr * 3 if pd.notna(qqq_cagr) else np.nan,
            "Daily 3x Gross CAGR": gross_cagr,
            "Volatility Drag vs Naive 3x": gross_cagr - qqq_cagr * 3
            if pd.notna(gross_cagr) and pd.notna(qqq_cagr)
            else np.nan,
            "Cost Model 3x CAGR": cost_cagr,
            "Cost Drag vs Gross Daily 3x": cost_cagr - gross_cagr
            if pd.notna(cost_cagr) and pd.notna(gross_cagr)
            else np.nan,
            "TQQQ-like CAGR": preferred_cagr,
            "TQQQ-like CAGR Gap vs QQQ": preferred_cagr - qqq_cagr
            if pd.notna(preferred_cagr) and pd.notna(qqq_cagr)
            else np.nan,
            "Real TQQQ CAGR": real_cagr,
            "Real TQQQ Gap vs Cost Model": real_cagr - cost_cagr
            if pd.notna(real_cagr) and pd.notna(cost_cagr)
            else np.nan,
            "QQQ Max Drawdown": qqq_metrics.get("Max Drawdown", np.nan),
            "Daily 3x Gross Max Drawdown": gross_metrics.get("Max Drawdown", np.nan),
            "Cost Model 3x Max Drawdown": cost_metrics.get("Max Drawdown", np.nan),
            "TQQQ-like Max Drawdown": preferred_metrics.get("Max Drawdown", np.nan),
            "Real TQQQ Max Drawdown": real_metrics.get("Max Drawdown", np.nan),
        }
    )


def _daily_leverage_series(
    base: pd.Series,
    multiple: int,
    name: str,
    daily_cost: pd.Series | None = None,
) -> pd.Series:
    base = base.dropna().astype(float)
    if base.empty:
        return pd.Series(dtype=float, name=name)

    costs = pd.Series(0.0, index=base.index)
    if daily_cost is not None and not daily_cost.empty:
        costs = daily_cost.reindex(base.index).ffill().fillna(0.0).astype(float)

    returns = base.pct_change().fillna(0.0) * multiple - costs
    returns.iloc[0] = 0.0
    returns = returns.clip(lower=-0.99)
    return ((1.0 + returns).cumprod() * float(base.iloc[0])).rename(name)


def _daily_cost_series(
    index: pd.DatetimeIndex,
    asset: str,
    multiple: int,
    leverage_costs: dict | None,
    financing_rates: pd.Series | None,
) -> pd.Series:
    config = _cost_config(asset, leverage_costs)
    trading_days = int(config.get("trading_days", DEFAULT_COSTS["trading_days"]))
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


def _cost_config(asset: str, leverage_costs: dict | None) -> dict:
    config = dict(DEFAULT_COSTS)
    if leverage_costs:
        config.update({key: value for key, value in leverage_costs.items() if key != "asset_overrides"})
        overrides = leverage_costs.get("asset_overrides") or {}
        if asset in overrides:
            config.update(overrides[asset] or {})
    return config


def _build_markdown(series_metrics: pd.DataFrame, drag_summary: pd.DataFrame, requested_start: str) -> str:
    if series_metrics.empty or drag_summary.empty:
        return "# TQQQ vs QQQ Leverage Drag Analysis\n\nNo QQQ/TQQQ comparison data was available.\n"

    lines = [
        "# TQQQ vs QQQ Leverage Drag Analysis",
        "",
        "This report separates real TQQQ history from a long TQQQ-like simulation.",
        f"The requested long start was {requested_start}; the effective start is the first available QQQ/proxy date.",
        "",
        "Definitions:",
        "",
        "- QQQ: QQQ after inception, stitched to Nasdaq proxy history before QQQ existed.",
        "- QQQ Daily 3x Gross: daily 3x QQQ/proxy returns with no financing, fee, or tracking drag.",
        "- QQQ Daily 3x Cost Model: daily 3x QQQ/proxy returns after the configured financing, fee, and tracking assumptions.",
        "- TQQQ-like Stitched: simulated before TQQQ has prices, then real TQQQ prices after they are available.",
        "- Real TQQQ: actual adjusted TQQQ prices on the overlap window only.",
        "",
        "## Drag Summary",
        "",
        _markdown_table(_format_frame(drag_summary)),
        "",
        "## Series Metrics",
        "",
        _markdown_table(_format_frame(series_metrics)),
        "",
    ]
    return "\n".join(lines)


def _format_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in output.columns:
        if column in {"Window", "Series", "Start Date", "End Date"}:
            continue
        if output[column].dtype.kind not in "biufc":
            continue
        if "CAGR" in column or "Drawdown" in column or "Drag" in column or "Gap" in column or "Return" in column or "Volatility" in column:
            output[column] = output[column].map(_fmt_pct)
        elif column == "Years":
            output[column] = output[column].map(lambda value: "N/A" if pd.isna(value) else f"{float(value):.2f}")
        else:
            output[column] = output[column].map(lambda value: "N/A" if pd.isna(value) else f"{float(value):.2f}")
    return output


def _markdown_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    rows = frame.astype(str).values.tolist()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _fmt_pct(value) -> str:
    if pd.isna(value) or (isinstance(value, float) and not math.isfinite(value)):
        return "N/A"
    return f"{float(value):.2%}"
