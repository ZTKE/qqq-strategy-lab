from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.backtest import BacktestResult


CHART_IMAGES = [
    {"label": "净值曲线", "src": "charts/equity_curves.png"},
    {"label": "回撤曲线", "src": "charts/drawdowns.png"},
    {"label": "滚动收益", "src": "charts/rolling_returns.png"},
]


STRATEGY_DESCRIPTIONS = {
    "qqq_buy_hold": "100% 长期持有 QQQ，作为所有策略的基础对照。",
    "qqq_80_spy_20": "每月再平衡到 80% QQQ / 20% SPY，用宽基组合降低单一 QQQ 波动。",
    "qqq_70_spy_20_shy_10": "每月再平衡到 70% QQQ / 20% SPY / 10% SHY，增加短债防守仓位。",
    "trend_200dma": "使用 QQQ 200 日均线做风险开关，趋势弱时提高 SHY 防守比例。",
    "core_trend": "保留 QQQ 核心仓，再用一部分仓位跟随 200 日趋势在 QQQ 和 SHY 间切换。",
    "drawdown_buy": "根据 QQQ 相对历史高点的回撤深度逐步提高进攻资产配置。",
    "momentum_rotation": "在 QQQ、SPY、XLK、SMH、GLD、SHY 中筛选趋势和 6 个月动量最强资产。",
    "dca_drawdown_boost": "月度定投策略，回撤越深，新投入资金越偏向 QQQ。",
    "daily_trend_2x": "每日趋势检查，牛市持有合成 2x QQQ，弱势切到防守资产。",
    "daily_trend_3x_defensive": "每日 50/200 日均线判断，强趋势用 3x，普通牛市用 2x，弱势防守。",
    "daily_trend_3x_defensive_v2_conservative": "3x 防守增强保守版：限制 3x 仓位，并用波动率和回撤刹车降低顶部风险。",
    "daily_trend_3x_defensive_v2_balanced": "3x 防守增强平衡版：保留强趋势进攻，同时加入波动率、均线斜率和回撤刹车。",
    "daily_trend_3x_defensive_v2_aggressive": "3x 防守增强进攻版：允许满仓 3x，但用波动率和回撤阈值控制极端风险。",
    "dual_ma_leverage_ladder": "用 20/50/200 日均线做杠杆阶梯，趋势越强杠杆越高。",
    "vol_target_trend": "先用 200 日趋势过滤，再根据近 20 日波动率在 1x/2x/3x 间切换。",
    "core_trend_2x": "保留 QQQ 核心仓，战术仓按趋势使用 2x、3x 或 SHY。",
    "momentum_rotation_2x": "动量轮动增强版，进攻资产使用合成 2x，防守资产不加杠杆。",
    "breakout_3x_with_stop": "寻找接近 252 日新高的突破行情，趋势转弱时逐级降杠杆。",
    "crash_protected_tqqq": "仅在 QQQ 高于 200 日均线且均线向上时使用合成 3x QQQ。",
    "ema5_tqqq_trend": "QQQ 沿 5 日 EMA 上行时持有 TQQQ，跌破 EMA5 后切到 SHY。",
    "adaptive_leverage_score": "综合趋势、动量、回撤和波动率打分，动态决定 1x/2x/3x 或防守。",
    "dca_leverage_boost": "只调整每月新增资金，强牛市买 3x，普通牛市买 2x，熊市转防守组合。",
}


def generate_html_report(
    results_frame: pd.DataFrame,
    reports_dir: str | Path,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    transaction_cost: float,
    results: list[BacktestResult] | None = None,
) -> Path:
    """Generate a standalone interactive dashboard for the backtest report."""

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    context_by_strategy = _context_by_strategy(results or [])
    rows = [_serialize_row(row, context_by_strategy.get(str(row["Strategy"]), {})) for _, row in results_frame.iterrows()]
    series = _serialize_interactive_series(results or [])
    first_context = next(iter(context_by_strategy.values()), {})
    meta = {
        "title": "QQQ 策略实验室",
        "subtitle": "交互式回测结果控制台",
        "startDate": _date_string(start_date),
        "endDate": _date_string(end_date),
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "transactionCost": float(transaction_cost),
        "initialCapital": _clean_value(first_context.get("initialCapital")),
        "monthlyContribution": _clean_value(first_context.get("monthlyContribution")),
        "strategyCount": int(len(results_frame)),
        "totalInvested": _clean_value(results_frame["Total Invested"].max()) if "Total Invested" in results_frame else None,
        "chartImages": CHART_IMAGES,
        "chartPage": "charts.html",
    }

    html = HTML_TEMPLATE.replace("__REPORT_META__", json.dumps(meta, ensure_ascii=False, allow_nan=False))
    html = html.replace("__REPORT_ROWS__", json.dumps(rows, ensure_ascii=False, allow_nan=False))
    html = html.replace("__REPORT_SERIES__", json.dumps(series, ensure_ascii=False, allow_nan=False))

    charts_html = CHART_PAGE_TEMPLATE.replace("__REPORT_META__", json.dumps(meta, ensure_ascii=False, allow_nan=False))
    charts_html = charts_html.replace("__REPORT_ROWS__", json.dumps(rows, ensure_ascii=False, allow_nan=False))
    charts_html = charts_html.replace("__REPORT_SERIES__", json.dumps(series, ensure_ascii=False, allow_nan=False))

    output_path = reports_path / "dashboard.html"
    output_path.write_text(html, encoding="utf-8")
    (reports_path / "charts.html").write_text(charts_html, encoding="utf-8")
    return output_path


def _context_by_strategy(results: list[BacktestResult]) -> dict[str, dict[str, Any]]:
    context = {}
    for result in results:
        config = result.metadata.get("config", {}) if result.metadata else {}
        mode = str(result.metadata.get("mode", "")) if result.metadata else ""
        context[result.strategy_name] = {
            "type": config.get("type"),
            "config": config,
            "mode": mode,
            "rebalanceFrequency": config.get("rebalance_frequency", "daily" if str(config.get("type", "")).startswith("daily") else "monthly"),
            "initialCapital": result.metadata.get("initial_capital"),
            "monthlyContribution": result.metadata.get("monthly_contribution"),
        }
    return context


def _serialize_interactive_series(results: list[BacktestResult]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "strategies": [result.strategy_name for result in results],
        "equity": {},
        "drawdown": {},
        "rolling": {},
        "performance": {},
    }
    for result in results:
        name = result.strategy_name
        equity = _month_end_sample(result.equity_curve)
        performance = result.performance_curve.astype(float)
        drawdown = performance / performance.cummax() - 1.0
        rolling = performance / performance.shift(252) - 1.0
        payload["equity"][name] = _series_points(equity)
        payload["drawdown"][name] = _series_points(_month_end_sample(drawdown))
        payload["rolling"][name] = _series_points(_month_end_sample(rolling.dropna()))
        payload["performance"][name] = _series_points(performance)
    return payload


def _month_end_sample(series: pd.Series) -> pd.Series:
    clean = series.dropna().sort_index()
    if clean.empty:
        return clean
    sampled = clean.resample("ME").last().dropna()
    if sampled.empty or sampled.index[0] != clean.index[0]:
        sampled = pd.concat([clean.iloc[[0]], sampled])
    if sampled.index[-1] != clean.index[-1]:
        sampled = pd.concat([sampled, clean.iloc[[-1]]])
    return sampled[~sampled.index.duplicated(keep="last")]


def _series_points(series: pd.Series) -> list[dict[str, Any]]:
    return [
        {"d": pd.Timestamp(index).date().isoformat(), "v": float(value)}
        for index, value in series.items()
        if pd.notna(value)
    ]


def _serialize_row(row: pd.Series, context: dict[str, Any]) -> dict[str, Any]:
    name = str(row["Strategy"])
    assets = str(row.get("Required Assets", "") or "")
    tags = _strategy_tags(name, assets, context)
    serialized = {str(column): _clean_value(row[column]) for column in row.index}
    serialized.update(
        {
            "Tags": tags,
            "Description": STRATEGY_DESCRIPTIONS.get(name, "使用配置文件定义的规则生成目标仓位，并纳入统一资金投入与交易成本假设。"),
            "Implementation": _strategy_implementation(name, context.get("config") or {}),
            "Strategy Type": context.get("type") or _infer_strategy_type(name),
            "Mode": context.get("mode") or ("dca" if "dca" in name else "rebalanced"),
            "Rebalance Frequency": context.get("rebalanceFrequency") or _infer_frequency(name),
        }
    )
    return serialized


def _strategy_tags(name: str, assets: str, context: dict[str, Any]) -> list[str]:
    lower = name.lower()
    type_name = str(context.get("type") or "").lower()
    asset_text = assets.upper()
    tags: list[str] = []

    if name == "qqq_buy_hold":
        tags.append("基准")
    if "dca" in lower or type_name.startswith("dca"):
        tags.append("定投")
    if "momentum" in lower:
        tags.append("动量")
    if "trend" in lower or "ma_" in lower or "protected" in lower or "score" in lower:
        tags.append("趋势")
    if "drawdown" in lower:
        tags.append("回撤")
    if "defensive" in lower or "protected" in lower or "stop" in lower or "shy" in asset_text:
        tags.append("防守")
    if lower.startswith("qqq_") and name != "qqq_buy_hold":
        tags.append("静态配置")
    if _uses_leverage(name, asset_text):
        tags.append("杠杆")
    else:
        tags.append("无杠杆")

    return list(dict.fromkeys(tags))


def _uses_leverage(name: str, asset_text: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in ["2x", "3x", "leverage", "tqqq"]) or "_2X" in asset_text or "_3X" in asset_text


def _infer_strategy_type(name: str) -> str:
    if "momentum" in name:
        return "momentum_rotation"
    if "dca" in name:
        return "dca"
    if "trend" in name:
        return "trend"
    if "drawdown" in name:
        return "drawdown_buy"
    if name == "qqq_buy_hold":
        return "buy_and_hold"
    return "static_allocation"


def _infer_frequency(name: str) -> str:
    if any(token in name for token in ["daily_", "_2x", "_3x", "leverage", "tqqq", "score", "breakout"]):
        return "daily"
    if "dca" in name:
        return "monthly contribution"
    return "monthly"


def _strategy_implementation(name: str, config: dict[str, Any]) -> str:
    strategy_type = str(config.get("type") or _infer_strategy_type(name))
    if strategy_type == "buy_and_hold":
        return f"首日按目标权重买入并长期持有；目标权重为 {_format_weights(config.get('weights', {}))}。"
    if strategy_type == "static_allocation":
        return f"每月最后一个交易日生成再平衡信号，下一个交易日调回固定权重：{_format_weights(config.get('weights', {}))}。"
    if strategy_type == "trend_200dma":
        return (
            f"用 `{config.get('signal_asset', 'QQQ')}` 的 {config.get('ma_window', 200)} 日均线判断趋势；"
            f"价格在均线之上使用风险开启权重：{_format_weights(config.get('risk_on', {}))}；"
            f"否则使用风险关闭权重：{_format_weights(config.get('risk_off', {}))}。"
        )
    if strategy_type == "core_trend":
        return (
            f"固定保留 `{config.get('core_asset', 'QQQ')}` 核心仓 {_fmt_pct(config.get('core_weight'))}；"
            f"剩余 {_fmt_pct(config.get('tactical_weight'))} 用 `{config.get('signal_asset', 'QQQ')}` 的 "
            f"{config.get('ma_window', 200)} 日均线切换：趋势强买 `{config.get('risk_on_asset', 'QQQ')}`，"
            f"趋势弱买 `{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "drawdown_buy":
        return (
            f"计算 `{config.get('signal_asset', 'QQQ')}` 相对历史高点的回撤，回撤越深越提高进攻资产权重；"
            f"规则为 {_format_drawdown_rules(config.get('rules', []), 'drawdown_lt', '<')}。"
        )
    if strategy_type == "momentum_rotation":
        return (
            f"候选资产为 {', '.join(config.get('assets', []))}；先剔除低于 {config.get('ma_window', 200)} 日均线的资产，"
            f"再按过去 {config.get('lookback_months', 6)} 个月收益排序，等权持有前 {config.get('top_n', 2)} 名；"
            f"若没有资产通过过滤，则持有 `{config.get('fallback_asset', 'SHY')}`。"
        )
    if strategy_type == "dca":
        return (
            f"首日投入 {_fmt_money(config.get('initial_capital'))}，之后每月投入 {_fmt_money(config.get('monthly_contribution'))}；"
            f"正常按 {_format_weights(config.get('normal_weights', {}))} 买入，"
            f"当 `{config.get('signal_asset', 'QQQ')}` 回撤触发阈值时改用："
            f"{_format_drawdown_rules(config.get('rules', []), 'drawdown_gte', '>=')}。"
        )
    if strategy_type == "daily_trend_2x":
        return (
            f"每日检查 `{config.get('signal_asset', 'QQQ')}` 是否高于 {config.get('ma_window', 200)} 日均线；"
            f"满足则持有 `{config.get('risk_on_asset', 'QQQ_2X')}`，否则切到 `{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "daily_trend_3x_defensive":
        return (
            f"每日比较 `{config.get('signal_asset', 'QQQ')}` 的 {config.get('fast_window', 50)} 日和 "
            f"{config.get('slow_window', 200)} 日均线；强趋势用 `{config.get('asset_3x', 'QQQ_3X')}`，"
            f"普通趋势用 `{config.get('asset_2x', 'QQQ_2X')}`，弱势用 `{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "daily_trend_3x_defensive_v2":
        return (
            f"每日比较 `{config.get('signal_asset', 'QQQ')}` 的 {config.get('fast_window', 50)} / "
            f"{config.get('slow_window', 200)} 日均线，并要求均线斜率向上才允许 3x；"
            f"20 日波动率低于 {_fmt_pct(config.get('low_vol_threshold'))} 时最高 "
            f"{_fmt_pct(config.get('max_3x_weight'))} `{config.get('asset_3x', 'QQQ_3X')}`，"
            f"波动率低于 {_fmt_pct(config.get('high_vol_threshold'))} 时最高 "
            f"{_fmt_pct(config.get('medium_3x_weight'))} 3x；"
            f"`{config.get('signal_asset', 'QQQ')}` 回撤超过 {_fmt_pct(config.get('soft_drawdown_threshold'))} "
            f"降到 `{config.get('asset_1x', 'QQQ')}`，超过 {_fmt_pct(config.get('hard_drawdown_threshold'))} "
            f"切到 `{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "dual_ma_leverage_ladder":
        return (
            f"每日用 {config.get('short_window', 20)} / {config.get('mid_window', 50)} / {config.get('long_window', 200)} "
            f"日均线给趋势分层；强趋势用 `{config.get('asset_3x', 'QQQ_3X')}`，中等趋势用 "
            f"`{config.get('asset_2x', 'QQQ_2X')}` 或 `{config.get('asset_1x', 'QQQ')}`，长期趋势破坏时用 "
            f"`{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "vol_target_trend":
        return (
            f"每日先要求 `{config.get('signal_asset', 'QQQ')}` 高于 {config.get('ma_window', 200)} 日均线；"
            f"趋势有效后按近 {config.get('vol_window', 20)} 日年化波动率调杠杆：低于 "
            f"{_fmt_pct(config.get('low_vol_threshold'))} 用 `{config.get('asset_3x', 'QQQ_3X')}`，"
            f"高于 {_fmt_pct(config.get('high_vol_threshold'))} 降到 `{config.get('asset_1x', 'QQQ')}`，"
            f"中间用 `{config.get('asset_2x', 'QQQ_2X')}`。"
        )
    if strategy_type == "core_trend_2x":
        return (
            f"每日保留 `{config.get('core_asset', 'QQQ')}` 核心仓 {_fmt_pct(config.get('core_weight'))}；"
            f"战术仓 {_fmt_pct(config.get('tactical_weight'))} 根据 {config.get('fast_window', 50)} / "
            f"{config.get('slow_window', 200)} 日趋势在 `{config.get('asset_3x', 'QQQ_3X')}`、"
            f"`{config.get('asset_2x', 'QQQ_2X')}` 和 `{config.get('risk_off_asset', 'SHY')}` 间切换。"
        )
    if strategy_type == "momentum_rotation_2x":
        leveraged_assets = config.get("leveraged_assets", {})
        return (
            f"每日在 {', '.join(config.get('assets', []))} 中做 {config.get('ma_window', 200)} 日趋势过滤和 "
            f"{config.get('lookback_months', 6)} 个月动量排名，持有前 {config.get('top_n', 2)} 名；"
            f"进攻资产映射到杠杆版本 {', '.join(f'{k}->{v}' for k, v in leveraged_assets.items())}，"
            f"无合格资产时持有 `{config.get('fallback_asset', 'SHY')}`。"
        )
    if strategy_type == "breakout_3x_with_stop":
        return (
            f"每日检查 `{config.get('signal_asset', 'QQQ')}` 是否接近 {config.get('high_window', 252)} 日新高；"
            f"价格达到新高阈值 {_fmt_pct(config.get('near_high_threshold'))} 且均线结构强时用 "
            f"`{config.get('asset_3x', 'QQQ_3X')}`，趋势转弱时逐级降到 `{config.get('asset_2x', 'QQQ_2X')}`、"
            f"`{config.get('asset_1x', 'QQQ')}` 或 `{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "crash_protected_tqqq":
        return (
            f"每日要求 `{config.get('signal_asset', 'QQQ')}` 高于 {config.get('ma_window', 200)} 日均线，且均线在 "
            f"{config.get('slope_lookback', 20)} 日窗口内向上；满足时用 `{config.get('asset_3x', 'QQQ_3X')}`，"
            f"否则降到 `{config.get('asset_1x', 'QQQ')}` 或 `{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "ema5_tqqq_trend":
        return (
            f"每日检查 `{config.get('signal_asset', 'QQQ')}` 是否站上 {config.get('ema_window', 5)} 日 EMA，且 EMA 在 "
            f"{config.get('slope_lookback', 1)} 日窗口内上行；满足时持有 `{config.get('risk_on_asset', 'QQQ_3X')}`，"
            f"否则切到 `{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "adaptive_leverage_score":
        return (
            f"每日综合 `{config.get('signal_asset', 'QQQ')}` 的均线结构、{config.get('momentum_months', 6)} 个月动量、"
            f"回撤和近 {config.get('vol_window', 20)} 日波动率打分；高分用 `{config.get('asset_3x', 'QQQ_3X')}`，"
            f"中高分用 `{config.get('asset_2x', 'QQQ_2X')}`，中性用 `{config.get('asset_1x', 'QQQ')}`，低分用 "
            f"`{config.get('risk_off_asset', 'SHY')}`。"
        )
    if strategy_type == "dca_leverage_boost":
        return (
            f"首日投入 {_fmt_money(config.get('initial_capital'))}，之后每月投入 {_fmt_money(config.get('monthly_contribution'))}；"
            f"只调整新增资金：普通状态 {_format_weights(config.get('normal_weights', {}))}，牛市 "
            f"{_format_weights(config.get('bull_weights', {}))}，强牛市 {_format_weights(config.get('strong_bull_weights', {}))}，"
            f"熊市 {_format_weights(config.get('bear_weights', {}))}。"
        )
    return "使用配置文件中的规则生成目标仓位，并按统一现金流、交易成本和再平衡日执行。"


def _format_weights(weights: dict[str, Any]) -> str:
    if not weights:
        return "未配置"
    return " / ".join(f"`{asset}` {_fmt_pct(weight)}" for asset, weight in weights.items())


def _format_drawdown_rules(rules: list[dict[str, Any]], key: str, operator: str) -> str:
    if not rules:
        return "未配置"
    parts = []
    for rule in rules:
        threshold = rule.get(key)
        weights = _format_weights(rule.get("weights", {}))
        parts.append(f"回撤 {operator} {_fmt_pct(threshold)} 时 {weights}")
    return "；".join(parts)


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_money(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _date_string(value: pd.Timestamp) -> str:
    stamp = pd.Timestamp(value)
    return stamp.date().isoformat()


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return float(value)
    if isinstance(value, int):
        return int(value)
    return value


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QQQ 策略实验室 - 交互式结果报告</title>
  <style>
    :root {
      --bg: #f6f8f7;
      --surface: #ffffff;
      --surface-soft: #eef3f1;
      --ink: #18211f;
      --muted: #66736f;
      --line: #d8e0dd;
      --accent: #0f766e;
      --accent-strong: #0b5f59;
      --blue: #2563eb;
      --orange: #c05621;
      --red: #b42318;
      --green: #0b7a53;
      --shadow: 0 12px 34px rgba(24, 33, 31, 0.10);
      --radius: 8px;
    }

    * {
      box-sizing: border-box;
    }

    html {
      color-scheme: light;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Inter", "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      letter-spacing: 0;
    }

    button,
    input,
    select {
      font: inherit;
    }

    button {
      cursor: pointer;
    }

    .page-shell {
      max-width: 1480px;
      margin: 0 auto;
      padding: 24px;
    }

    .topbar {
      display: grid;
      grid-template-columns: minmax(260px, 1fr) auto;
      gap: 18px;
      align-items: start;
      margin-bottom: 18px;
    }

    .title-block h1 {
      margin: 0 0 8px;
      font-size: 30px;
      line-height: 1.12;
      font-weight: 760;
      overflow-wrap: anywhere;
    }

    .meta-line {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }

    .meta-pill {
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      border-radius: 999px;
      padding: 5px 9px;
      white-space: nowrap;
    }

    .action-row {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .button {
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--ink);
      min-height: 36px;
      padding: 7px 12px;
      border-radius: var(--radius);
      display: inline-flex;
      align-items: center;
      gap: 7px;
      box-shadow: 0 1px 0 rgba(255,255,255,0.8);
    }

    .button:hover {
      border-color: #b9c8c4;
      background: #fbfdfc;
    }

    .button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }

    .button.primary:hover {
      background: var(--accent-strong);
      border-color: var(--accent-strong);
    }

    .icon {
      width: 16px;
      height: 16px;
      display: inline-block;
      flex: 0 0 auto;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .kpi-card,
    .panel,
    .control-surface {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }

    .kpi-card {
      min-height: 126px;
      padding: 15px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 12px;
    }

    .kpi-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }

    .kpi-value {
      font-size: 23px;
      line-height: 1.08;
      font-weight: 760;
    }

    .kpi-owner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      min-width: 0;
    }

    .strategy-name {
      min-width: 0;
      overflow-wrap: anywhere;
      font-weight: 650;
      color: var(--ink);
    }

    .delta-pill {
      border-radius: 999px;
      padding: 4px 8px;
      background: var(--surface-soft);
      white-space: nowrap;
      font-size: 12px;
      color: var(--muted);
    }

    .delta-pill.good {
      background: #e5f5ee;
      color: var(--green);
    }

    .delta-pill.risk {
      background: #fff0e8;
      color: var(--orange);
    }

    .dashboard-grid {
      display: grid;
      grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }

    .control-surface {
      position: sticky;
      top: 14px;
      padding: 15px;
      display: grid;
      gap: 16px;
    }

    .section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 10px;
    }

    .title-actions {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .section-title h2,
    .section-title h3 {
      margin: 0;
      font-size: 15px;
      line-height: 1.25;
    }

    .section-title small {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .collapse-toggle {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fbfcfc;
      color: var(--ink);
      min-height: 30px;
      padding: 5px 9px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 12px;
      white-space: nowrap;
    }

    .collapse-toggle:hover {
      border-color: rgba(15, 118, 110, 0.48);
      background: #f1faf7;
    }

    .chart-panel.is-hidden .collapsible-content {
      display: none;
    }

    .chart-panel.is-hidden {
      box-shadow: none;
    }

    .chart-hidden-note {
      display: none;
      min-height: 84px;
      place-items: center;
      border: 1px dashed var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
      padding: 16px;
    }

    .chart-panel.is-hidden .chart-hidden-note {
      display: grid;
    }

    .field {
      display: grid;
      gap: 6px;
    }

    .field label {
      color: var(--muted);
      font-size: 12px;
    }

    .searchbox,
    .selectbox {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      color: var(--ink);
      padding: 8px 10px;
      outline: none;
    }

    .searchbox:focus,
    .selectbox:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
    }

    .chip-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }

    .filter-chip,
    .metric-chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fbfcfc;
      color: var(--ink);
      padding: 7px 10px;
      min-height: 34px;
      white-space: nowrap;
      font-size: 13px;
    }

    .filter-chip.active,
    .metric-chip.active {
      color: white;
      background: var(--accent);
      border-color: var(--accent);
    }

    .range-row {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
    }

    input[type="range"] {
      width: 100%;
      accent-color: var(--accent);
    }

    .toggle-row {
      display: grid;
      gap: 9px;
    }

    .toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--ink);
      font-size: 13px;
    }

    .toggle input {
      width: 17px;
      height: 17px;
      accent-color: var(--accent);
    }

    .chart-toggle-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .chart-toggle {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      color: var(--ink);
      min-height: 36px;
      padding: 7px 9px;
      display: flex;
      align-items: center;
      gap: 7px;
      text-align: left;
      font-size: 13px;
    }

    .chart-toggle::before {
      content: "";
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--accent);
      flex: 0 0 auto;
    }

    .chart-toggle.off {
      color: var(--muted);
      background: #f1f4f3;
    }

    .chart-toggle.off::before {
      background: #a9b6b2;
    }

    .param-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .param-input {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      color: var(--ink);
      padding: 7px 9px;
      outline: none;
    }

    .command-box {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #f3f7f6;
      color: #283633;
      padding: 10px;
      min-height: 82px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-family: Consolas, "Cascadia Mono", monospace;
      font-size: 12px;
      line-height: 1.45;
    }

    .run-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .run-status {
      min-height: 18px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }

    .run-status.error {
      color: var(--red);
    }

    .main-stack {
      display: grid;
      gap: 16px;
    }

    .panel {
      padding: 16px;
      min-width: 0;
    }

    .chart-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      gap: 16px;
    }

    .chart-toggle-field,
    .dashboard-inline-chart {
      display: none;
    }

    .chart-link-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(150px, 1fr));
      gap: 10px;
    }

    .chart-link-card {
      min-height: 98px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      color: var(--ink);
      text-decoration: none;
      padding: 12px;
      display: grid;
      align-content: start;
      gap: 7px;
    }

    .chart-link-card:hover {
      border-color: rgba(15, 118, 110, 0.46);
      background: #f1faf7;
    }

    .chart-link-card strong {
      font-size: 14px;
    }

    .chart-link-card span {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .chart-stage {
      min-height: 300px;
      overflow: hidden;
    }

    .chart-stage svg {
      width: 100%;
      height: auto;
      display: block;
    }

    .line-chart-layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(220px, 280px);
      gap: 14px;
      align-items: start;
    }

    .line-chart-stage {
      min-height: 460px;
      overflow: auto;
    }

    .line-chart-stage svg {
      width: 100%;
      min-width: 820px;
      height: auto;
      display: block;
    }

    .line-legend {
      display: grid;
      gap: 6px;
      max-height: 500px;
      overflow: auto;
      padding-right: 4px;
    }

    .legend-item {
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fbfcfc;
      color: var(--ink);
      min-height: 34px;
      padding: 6px 8px;
      display: flex;
      align-items: center;
      gap: 8px;
      text-align: left;
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .legend-item:hover {
      border-color: rgba(15, 118, 110, 0.42);
      background: #f1faf7;
    }

    .legend-item.off {
      color: var(--muted);
      background: #f1f4f3;
      text-decoration: line-through;
    }

    .legend-swatch {
      width: 18px;
      height: 3px;
      border-radius: 999px;
      flex: 0 0 auto;
    }

    .legend-item.off .legend-swatch {
      opacity: 0.35;
    }

    .legend-count {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      padding: 0 2px 4px;
    }

    .line-path {
      fill: none;
      stroke-linecap: round;
      stroke-linejoin: round;
      vector-effect: non-scaling-stroke;
    }

    .line-grid {
      stroke: #e5ece9;
      stroke-width: 1;
    }

    .line-axis {
      stroke: #bfcbc7;
      stroke-width: 1;
    }

    .axis-label {
      fill: var(--muted);
      font-size: 11px;
    }

    .bar-label,
    .point-label {
      fill: var(--ink);
      font-size: 12.5px;
      font-weight: 620;
    }

    .bar-value {
      fill: var(--muted);
      font-size: 12px;
    }

    .empty-state {
      min-height: 180px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      text-align: center;
      padding: 18px;
    }

    .detail-layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(300px, 0.9fr);
      gap: 14px;
      align-items: start;
    }

    .detail-name {
      margin: 0 0 8px;
      font-size: 21px;
      overflow-wrap: anywhere;
    }

    .detail-text {
      color: var(--muted);
      line-height: 1.58;
      margin: 0 0 12px;
      font-size: 14px;
    }

    .implementation-box {
      margin-top: 12px;
      border-left: 3px solid var(--accent);
      background: #f4faf8;
      padding: 10px 12px;
      border-radius: 0 var(--radius) var(--radius) 0;
      color: #31413d;
      line-height: 1.58;
      font-size: 13px;
    }

    .tag-row {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }

    .tag {
      border-radius: 999px;
      padding: 5px 8px;
      background: var(--surface-soft);
      color: var(--muted);
      font-size: 12px;
    }

    .mini-metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }

    .mini-metric {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 10px;
      background: #fbfcfc;
      min-height: 70px;
    }

    .mini-metric span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }

    .mini-metric strong {
      display: block;
      font-size: 17px;
      overflow-wrap: anywhere;
    }

    .method-list {
      display: grid;
      gap: 8px;
    }

    .method-item {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      color: var(--ink);
      padding: 11px 12px;
      text-align: left;
      display: grid;
      grid-template-columns: minmax(170px, 0.34fr) minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }

    .method-item:hover,
    .method-item.selected {
      border-color: rgba(15, 118, 110, 0.48);
      background: #f1faf7;
    }

    .method-name {
      font-weight: 760;
      overflow-wrap: anywhere;
      line-height: 1.35;
    }

    .method-meta {
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .method-text {
      color: #31413d;
      line-height: 1.58;
      font-size: 13px;
    }

    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      max-height: 620px;
      background: var(--surface);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 1320px;
    }

    th,
    td {
      padding: 10px 11px;
      border-bottom: 1px solid var(--line);
      text-align: right;
      font-size: 13px;
      white-space: nowrap;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f0f4f3;
      color: #394743;
      font-size: 12px;
      font-weight: 720;
      user-select: none;
    }

    th.sortable {
      cursor: pointer;
    }

    th:first-child,
    td:first-child {
      text-align: left;
      position: sticky;
      left: 0;
      background: inherit;
      z-index: 2;
      width: 280px;
      min-width: 280px;
      max-width: 320px;
      white-space: normal;
      overflow-wrap: normal;
      word-break: normal;
    }

    th:first-child {
      z-index: 3;
      background: #f0f4f3;
    }

    tbody tr {
      background: var(--surface);
      cursor: pointer;
    }

    tbody tr:hover {
      background: #f8fbfa;
    }

    tbody tr.selected {
      background: #e8f4f1;
    }

    .table-strategy-name {
      cursor: help;
      text-decoration: underline;
      text-decoration-style: dotted;
      text-underline-offset: 3px;
      overflow-wrap: break-word;
      word-break: normal;
    }

    .strategy-tooltip {
      position: fixed;
      z-index: 999;
      width: min(440px, calc(100vw - 28px));
      border: 1px solid rgba(15, 118, 110, 0.30);
      border-radius: var(--radius);
      background: rgba(255, 255, 255, 0.98);
      color: var(--ink);
      box-shadow: 0 18px 48px rgba(24, 33, 31, 0.18);
      padding: 13px 14px;
      pointer-events: none;
      opacity: 0;
      transform: translateY(4px);
      transition: opacity 120ms ease, transform 120ms ease;
    }

    .strategy-tooltip.is-visible {
      opacity: 1;
      transform: translateY(0);
    }

    .strategy-tooltip[hidden] {
      display: none;
    }

    .tooltip-title {
      margin: 0 0 5px;
      font-size: 15px;
      line-height: 1.35;
      font-weight: 760;
      overflow-wrap: anywhere;
    }

    .tooltip-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 8px;
    }

    .tooltip-pill {
      border-radius: 999px;
      background: var(--surface-soft);
      color: var(--muted);
      padding: 4px 7px;
      font-size: 11px;
      line-height: 1.2;
    }

    .tooltip-body {
      color: #31413d;
      font-size: 12px;
      line-height: 1.55;
      margin: 0 0 8px;
    }

    .tooltip-body strong {
      color: var(--ink);
    }

    .tooltip-kpis {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 6px;
    }

    .tooltip-kpi {
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fbfcfc;
      padding: 6px;
      min-width: 0;
    }

    .tooltip-kpi span {
      display: block;
      color: var(--muted);
      font-size: 10px;
      margin-bottom: 3px;
    }

    .tooltip-kpi strong {
      display: block;
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .number.good {
      color: var(--green);
      font-weight: 700;
    }

    .number.bad {
      color: var(--red);
      font-weight: 700;
    }

    .rank-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      margin-right: 7px;
      border-radius: 50%;
      background: var(--surface-soft);
      color: var(--muted);
      font-size: 11px;
      font-weight: 760;
      vertical-align: middle;
    }

    .rank-badge.top {
      background: #dff3ec;
      color: var(--green);
    }

    .heatmap {
      display: grid;
      gap: 6px;
      overflow: auto;
      padding-bottom: 3px;
    }

    .heat-row {
      display: grid;
      grid-template-columns: minmax(180px, 1fr) repeat(5, minmax(74px, 0.34fr));
      gap: 6px;
      align-items: stretch;
      min-width: 640px;
    }

    .heat-cell {
      border: 0;
      border-radius: 7px;
      padding: 7px 8px;
      min-height: 32px;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      font-size: 12px;
      font-weight: 680;
      color: #17332a;
    }

    button.heat-cell {
      cursor: pointer;
      font: inherit;
    }

    button.heat-cell:hover {
      outline: 2px solid rgba(15, 118, 110, 0.28);
      outline-offset: 0;
    }

    .heat-name {
      justify-content: flex-start;
      background: #f1f5f4;
      color: var(--ink);
      overflow-wrap: anywhere;
    }

    .heat-head {
      background: transparent;
      color: var(--muted);
      font-weight: 700;
      min-height: 22px;
      padding-top: 0;
      padding-bottom: 0;
    }

    .image-tabs {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }

    .image-frame {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      overflow: auto;
      min-height: 360px;
    }

    .image-frame img {
      display: block;
      width: 100%;
      min-width: 760px;
      height: auto;
    }

    .footnote {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.55;
      margin: 0;
    }

    @media (max-width: 1120px) {
      .kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .chart-link-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .dashboard-grid,
      .chart-grid,
      .line-chart-layout,
      .detail-layout {
        grid-template-columns: 1fr;
      }

      .control-surface {
        position: static;
      }
    }

    @media (max-width: 680px) {
      .page-shell {
        padding: 14px;
      }

      .topbar {
        grid-template-columns: 1fr;
      }

      .action-row {
        justify-content: stretch;
      }

      .action-row .button {
        flex: 1 1 auto;
        justify-content: center;
      }

      .kpi-grid,
      .mini-metrics {
        grid-template-columns: 1fr;
      }

      .title-block h1 {
        font-size: 24px;
      }

      .kpi-value {
        font-size: 20px;
      }

      .param-grid,
      .chart-link-grid,
      .method-item {
        grid-template-columns: 1fr;
      }

      .tooltip-kpis {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .kpi-owner {
        align-items: flex-start;
        flex-wrap: wrap;
      }

      .delta-pill,
      .meta-pill {
        white-space: normal;
      }
    }
  </style>
</head>
<body>
  <main class="page-shell">
    <header class="topbar">
      <div class="title-block">
        <h1 id="reportTitle">QQQ 策略实验室</h1>
        <div class="meta-line" id="metaLine"></div>
      </div>
      <div class="action-row">
        <button class="button" id="resetFilters" type="button" title="清空筛选条件">
          <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 4v6h6M20 20v-6h-6M5 15a7 7 0 0 0 12 3l3-3M19 9A7 7 0 0 0 7 6l-3 3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          重置
        </button>
        <button class="button primary" id="downloadCsv" type="button" title="下载当前筛选后的表格">
          <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          导出 CSV
        </button>
      </div>
    </header>

    <section class="kpi-grid" id="kpiGrid"></section>

    <div class="dashboard-grid">
      <aside class="control-surface" aria-label="筛选条件">
        <div>
          <div class="section-title">
            <h2>筛选策略</h2>
            <small id="resultCount"></small>
          </div>
          <div class="field">
            <label for="searchInput">搜索名称 / 资产</label>
            <input class="searchbox" id="searchInput" type="search" placeholder="例如 trend、QQQ_3X、SHY" />
          </div>
        </div>

        <div class="field">
          <div class="section-title">
            <h3>回测参数</h3>
            <small>选好后运行运算</small>
          </div>
          <div class="param-grid">
            <div>
              <label for="paramStart">开始日期</label>
              <input class="param-input" id="paramStart" type="date" />
            </div>
            <div>
              <label for="paramEnd">结束日期</label>
              <input class="param-input" id="paramEnd" type="date" />
            </div>
            <div>
              <label for="paramInitial">初始资金</label>
              <input class="param-input" id="paramInitial" type="number" min="0" step="1000" />
            </div>
            <div>
              <label for="paramMonthly">每月追加</label>
              <input class="param-input" id="paramMonthly" type="number" min="0" step="100" />
            </div>
          </div>
          <div class="field">
            <label for="runCommand">运行命令</label>
            <div class="command-box" id="runCommand"></div>
            <div class="run-actions">
              <button class="button primary" id="runPeriod" type="button" title="按所选日期重新计算页面指标">
                <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                运行运算
              </button>
              <button class="button" id="copyCommand" type="button" title="复制这条命令">
                <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M8 8h10v12H8zM6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
                复制命令
              </button>
            </div>
            <div class="run-status" id="runStatus"></div>
          </div>
          <p class="footnote">页面内运算使用已生成的曲线序列；完整刷新数据时仍可复制命令运行。</p>
        </div>

        <div class="field">
          <label>点击标签筛选</label>
          <div class="chip-grid" id="filterChips"></div>
        </div>

        <div class="field chart-toggle-field">
          <label>图表显示</label>
          <div class="chart-toggle-grid" id="chartToggles"></div>
        </div>

        <div class="field">
          <label for="sortSelect">排序方式</label>
          <select class="selectbox" id="sortSelect">
            <option value="CAGR:desc">年化收益从高到低</option>
            <option value="Final Equity:desc">最终净值从高到低</option>
            <option value="Max Drawdown:desc">最大回撤从低到高</option>
            <option value="Sharpe:desc">夏普比率从高到低</option>
            <option value="Calmar:desc">Calmar 从高到低</option>
            <option value="Volatility:asc">波动率从低到高</option>
            <option value="1Y CAGR:desc">近 1 年年化从高到低</option>
            <option value="3Y CAGR:desc">近 3 年年化从高到低</option>
            <option value="10Y CAGR:desc">近 10 年年化从高到低</option>
          </select>
        </div>

        <div class="field">
          <div class="range-row">
            <label for="minCagr">最低年化收益</label>
            <strong id="minCagrValue"></strong>
          </div>
          <input id="minCagr" type="range" min="0" max="30" step="1" value="0" />
        </div>

        <div class="field">
          <div class="range-row">
            <label for="maxDrawdown">最大可承受回撤</label>
            <strong id="maxDrawdownValue"></strong>
          </div>
          <input id="maxDrawdown" type="range" min="30" max="90" step="1" value="90" />
        </div>

        <div class="toggle-row">
          <label class="toggle">
            <input id="beatQqqToggle" type="checkbox" />
            年化收益高于 QQQ
          </label>
          <label class="toggle">
            <input id="betterDdToggle" type="checkbox" />
            最大回撤优于 QQQ
          </label>
        </div>
      </aside>

      <div class="main-stack">
        <section class="panel" aria-label="策略详情">
          <div class="section-title">
            <h2>当前策略</h2>
            <small>点击表格行切换</small>
          </div>
          <div id="detailPanel"></div>
        </section>

        <section class="panel" aria-label="策略实施说明">
          <div class="section-title">
            <h2>全部策略实施说明</h2>
            <small>点击可联动详情</small>
          </div>
          <div id="methodPanel" class="method-list"></div>
        </section>

        <section class="panel" aria-label="独立图表页面">
          <div class="section-title">
            <h2>独立图表页面</h2>
            <small>每张图占完整页面宽度</small>
          </div>
          <div class="chart-link-grid">
            <a class="chart-link-card" href="charts.html#curves">
              <strong>策略曲线图</strong>
              <span>净值、回撤、滚动 1 年，图例逐条隐藏。</span>
            </a>
            <a class="chart-link-card" href="charts.html#rank">
              <strong>收益 / 回撤排行</strong>
              <span>按指标切换，完整横向空间看排名。</span>
            </a>
            <a class="chart-link-card" href="charts.html#scatter">
              <strong>风险收益散点</strong>
              <span>波动率、年化收益和回撤一起看。</span>
            </a>
            <a class="chart-link-card" href="charts.html#heatmap">
              <strong>滚动周期热力图</strong>
              <span>1 / 3 / 5 / 7 / 10 年周期对比。</span>
            </a>
            <a class="chart-link-card" href="charts.html#images">
              <strong>原始回测图</strong>
              <span>保留 PNG 原图，可横向滚动查看。</span>
            </a>
          </div>
        </section>

        <section class="panel chart-panel dashboard-inline-chart" data-chart-panel="curves" aria-label="策略曲线图">
          <div class="section-title">
            <h2>策略曲线图</h2>
            <div class="title-actions">
              <small>图例可切换</small>
              <button class="collapse-toggle" type="button" data-chart-toggle="curves"></button>
            </div>
          </div>
          <div class="chart-hidden-note">已隐藏策略曲线图，点击显示按钮恢复。</div>
          <div class="collapsible-content">
            <div class="chip-grid" id="curveModeChips"></div>
            <div class="line-chart-layout">
              <div class="line-chart-stage" id="interactiveLineChart"></div>
              <div class="line-legend" id="lineLegend"></div>
            </div>
          </div>
        </section>

        <section class="chart-grid" aria-label="交互图表">
          <div class="panel chart-panel dashboard-inline-chart" data-chart-panel="rank">
            <div class="section-title">
              <h2>收益 / 回撤排行</h2>
              <div class="title-actions">
                <small>受筛选影响</small>
                <button class="collapse-toggle" type="button" data-chart-toggle="rank"></button>
              </div>
            </div>
            <div class="chart-hidden-note">已隐藏收益 / 回撤排行，点击显示按钮恢复。</div>
            <div class="collapsible-content">
              <div class="chip-grid" id="metricChips"></div>
              <div class="chart-stage" id="barChart"></div>
            </div>
          </div>

          <div class="panel chart-panel dashboard-inline-chart" data-chart-panel="scatter">
            <div class="section-title">
              <h2>风险收益散点</h2>
              <div class="title-actions">
                <small>横轴波动，纵轴年化</small>
                <button class="collapse-toggle" type="button" data-chart-toggle="scatter"></button>
              </div>
            </div>
            <div class="chart-hidden-note">已隐藏风险收益散点，点击显示按钮恢复。</div>
            <div class="collapsible-content">
              <div class="chart-stage" id="scatterChart"></div>
            </div>
          </div>
        </section>

        <section class="panel chart-panel dashboard-inline-chart" data-chart-panel="heatmap" aria-label="滚动周期热力图">
          <div class="section-title">
            <h2>近 1 / 3 / 5 / 7 / 10 年年化热力图</h2>
            <div class="title-actions">
              <small>绿色越深越强</small>
              <button class="collapse-toggle" type="button" data-chart-toggle="heatmap"></button>
            </div>
          </div>
          <div class="chart-hidden-note">已隐藏滚动年化热力图，点击显示按钮恢复。</div>
          <div class="collapsible-content">
            <div id="heatmap" class="heatmap"></div>
          </div>
        </section>

        <section class="panel" aria-label="数据表">
          <div class="section-title">
            <h2>策略数据表</h2>
            <small>点表头排序</small>
          </div>
          <div class="table-wrap">
            <table id="resultsTable"></table>
          </div>
        </section>

        <section class="panel chart-panel dashboard-inline-chart" data-chart-panel="images" aria-label="原始图表">
          <div class="section-title">
            <h2>原始回测图</h2>
            <div class="title-actions">
              <small>来自 reports/charts</small>
              <button class="collapse-toggle" type="button" data-chart-toggle="images"></button>
            </div>
          </div>
          <div class="chart-hidden-note">已隐藏原始回测图，点击显示按钮恢复。</div>
          <div class="collapsible-content">
            <div class="image-tabs" id="imageTabs"></div>
            <div class="image-frame">
              <img id="chartImage" alt="回测图表" />
            </div>
            <p class="footnote">提示：上方交互图表来自汇总指标，原始 PNG 图保留完整时间序列视角。历史回测不构成投资建议。</p>
          </div>
        </section>
      </div>
    </div>
  </main>

  <div id="strategyTooltip" class="strategy-tooltip" role="tooltip" hidden></div>

  <script>
    const REPORT_META = __REPORT_META__;
    const REPORT_ROWS = __REPORT_ROWS__;
    const REPORT_SERIES = __REPORT_SERIES__;
    const baseRows = REPORT_ROWS.map(row => ({ ...row, Tags: [...(row.Tags || [])] }));
    let activeRows = baseRows;
    let activeSeries = REPORT_SERIES;

    const state = {
      filter: "all",
      search: "",
      minCagr: 0,
      maxDrawdown: 0.9,
      beatQqq: false,
      betterDd: false,
      sortKey: "CAGR",
      sortDir: "desc",
      chartMetric: "CAGR",
      curveMode: "equity",
      selected: null,
      imageIndex: 0,
      hiddenSeries: {},
      chartVisibility: {
        curves: true,
        rank: true,
        scatter: true,
        heatmap: true,
        images: true
      }
    };

    const chartOptions = [
      ["curves", "曲线图"],
      ["rank", "排行图"],
      ["scatter", "散点图"],
      ["heatmap", "热力图"],
      ["images", "原始图"]
    ];

    const filterOptions = [
      ["all", "全部"],
      ["基准", "基准"],
      ["无杠杆", "无杠杆"],
      ["杠杆", "杠杆"],
      ["趋势", "趋势"],
      ["动量", "动量"],
      ["定投", "定投"],
      ["防守", "防守"],
      ["回撤", "回撤"]
    ];

    const metricOptions = [
      ["CAGR", "年化"],
      ["Final Equity", "终值"],
      ["Max Drawdown", "回撤"],
      ["Sharpe", "夏普"],
      ["Calmar", "Calmar"],
      ["10Y CAGR", "10 年"]
    ];

    const curveModeOptions = [
      ["equity", "净值"],
      ["drawdown", "回撤"],
      ["rolling", "滚动 1 年"]
    ];

    const lineColors = [
      "#0f766e",
      "#2563eb",
      "#c05621",
      "#7c3aed",
      "#dc2626",
      "#0891b2",
      "#16a34a",
      "#9333ea",
      "#ea580c",
      "#64748b",
      "#be123c",
      "#0d9488",
      "#4f46e5",
      "#ca8a04",
      "#15803d",
      "#b45309",
      "#0369a1",
      "#a21caf"
    ];

    const columns = [
      ["Strategy", "策略", "text"],
      ["Final Equity", "最终净值", "money"],
      ["Total Return", "总收益", "pct"],
      ["CAGR", "年化", "pct"],
      ["Max Drawdown", "最大回撤", "pct"],
      ["Volatility", "波动率", "pct"],
      ["Sharpe", "夏普", "num"],
      ["Calmar", "Calmar", "num"],
      ["1Y CAGR", "1 年", "pct"],
      ["3Y CAGR", "3 年", "pct"],
      ["5Y CAGR", "5 年", "pct"],
      ["10Y CAGR", "10 年", "pct"],
      ["Required Assets", "资产", "text"]
    ];

    function allRows() {
      return activeRows || baseRows;
    }

    function seriesPayload() {
      return activeSeries || REPORT_SERIES;
    }

    function benchmarkRow() {
      return allRows().find(row => row.Strategy === "qqq_buy_hold") || allRows()[0];
    }

    function fmtPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
      return `${(Number(value) * 100).toFixed(2)}%`;
    }

    function fmtMoney(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
      return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value));
    }

    function fmtCompactMoney(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        notation: "compact",
        maximumFractionDigits: 1
      }).format(Number(value));
    }

    function fmtNum(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
      return Number(value).toFixed(2);
    }

    function fmtMetric(value, type) {
      if (type === "money") return fmtMoney(value);
      if (type === "pct") return fmtPct(value);
      if (type === "num") return fmtNum(value);
      return value ?? "N/A";
    }

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    function compactName(value) {
      return String(value).replaceAll("_", " ");
    }

    function fmtCurveValue(value) {
      return state.curveMode === "equity" ? fmtCompactMoney(value) : fmtPct(value);
    }

    function fmtDate(value) {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return "";
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    }

    function metricFormatFor(key) {
      if (key.includes("Return") || key.includes("CAGR") || key.includes("Drawdown") || key.includes("MaxDD") || key === "Volatility") return "pct";
      if (key.includes("Equity") || key.includes("Invested")) return "money";
      return "num";
    }

    function colorForStrategy(strategyName) {
      const seriesIndex = (seriesPayload().strategies || []).indexOf(strategyName);
      const rowIndex = allRows().findIndex(row => row.Strategy === strategyName);
      const index = seriesIndex >= 0 ? seriesIndex : Math.max(0, rowIndex);
      return lineColors[index % lineColors.length];
    }

    function parsedSeries(strategyName, seriesByStrategy) {
      return (seriesByStrategy[strategyName] || [])
        .map(point => ({ t: Date.parse(point.d), v: Number(point.v), d: point.d }))
        .filter(point => Number.isFinite(point.t) && Number.isFinite(point.v))
        .sort((a, b) => a.t - b.t);
    }

    function performancePoints(strategyName, sourceSeries = REPORT_SERIES.performance || REPORT_SERIES.equity || {}) {
      return parsedSeries(strategyName, sourceSeries);
    }

    function pointsInRange(points, startDate, endDate) {
      const start = Date.parse(startDate);
      const end = Date.parse(endDate);
      return points.filter(point => point.t >= start && point.t <= end);
    }

    function sampleMonthEnd(points) {
      if (!points.length) return [];
      const sampled = [];
      let currentMonth = "";
      let lastInMonth = null;
      points.forEach(point => {
        const month = point.d.slice(0, 7);
        if (currentMonth && month !== currentMonth && lastInMonth) {
          sampled.push(lastInMonth);
        }
        currentMonth = month;
        lastInMonth = point;
      });
      if (lastInMonth) sampled.push(lastInMonth);
      if (sampled[0]?.d !== points[0].d) sampled.unshift(points[0]);
      if (sampled[sampled.length - 1]?.d !== points[points.length - 1].d) sampled.push(points[points.length - 1]);
      const byDate = new Map(sampled.map(point => [point.d, point]));
      return Array.from(byDate.values()).sort((a, b) => a.t - b.t);
    }

    function cleanNumber(value) {
      return Number.isFinite(value) ? value : null;
    }

    function dailyReturns(points) {
      const returns = [];
      for (let index = 1; index < points.length; index += 1) {
        const previous = points[index - 1].v;
        const current = points[index].v;
        if (previous > 0 && Number.isFinite(current)) {
          returns.push(current / previous - 1);
        }
      }
      return returns;
    }

    function average(values) {
      return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : NaN;
    }

    function sampleStd(values) {
      if (values.length < 2) return NaN;
      const mean = average(values);
      const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (values.length - 1);
      return Math.sqrt(variance);
    }

    function maxDrawdownFromPoints(points) {
      let peak = -Infinity;
      let maxDrawdown = 0;
      points.forEach(point => {
        peak = Math.max(peak, point.v);
        if (peak > 0) {
          maxDrawdown = Math.min(maxDrawdown, point.v / peak - 1);
        }
      });
      return maxDrawdown;
    }

    function yearsBetween(points) {
      if (points.length < 2) return 0;
      return Math.max(0, (points[points.length - 1].t - points[0].t) / (365.25 * 24 * 60 * 60 * 1000));
    }

    function inferredPeriodsPerYear(points, fallback = 252) {
      const years = yearsBetween(points);
      if (years <= 0) return fallback;
      return Math.max(1, (points.length - 1) / years);
    }

    function performanceSummary(points, periodsPerYear = null) {
      if (points.length < 2 || points[0].v <= 0 || points[points.length - 1].v <= 0) {
        return {
          totalReturn: null,
          cagr: null,
          maxDrawdown: null,
          volatility: null,
          sharpe: null,
          calmar: null
        };
      }
      const years = periodsPerYear ? (points.length - 1) / periodsPerYear : yearsBetween(points);
      const annualization = periodsPerYear || inferredPeriodsPerYear(points);
      const returns = dailyReturns(points);
      const volatility = sampleStd(returns) * Math.sqrt(annualization);
      const cagr = years > 0 ? (points[points.length - 1].v / points[0].v) ** (1 / years) - 1 : NaN;
      const maxDrawdown = maxDrawdownFromPoints(points);
      const sharpe = volatility > 0 ? average(returns) * annualization / volatility : NaN;
      const calmar = maxDrawdown < 0 ? cagr / Math.abs(maxDrawdown) : NaN;
      return {
        totalReturn: cleanNumber(points[points.length - 1].v / points[0].v - 1),
        cagr: cleanNumber(cagr),
        maxDrawdown: cleanNumber(maxDrawdown),
        volatility: cleanNumber(volatility),
        sharpe: cleanNumber(sharpe),
        calmar: cleanNumber(calmar)
      };
    }

    function contributionDay(points, index, mode) {
      if (index <= 0 || index >= points.length) return false;
      const month = points[index].d.slice(0, 7);
      const previousMonth = points[index - 1].d.slice(0, 7);
      const nextMonth = points[index + 1]?.d.slice(0, 7);
      if (String(mode || "").toLowerCase() === "dca") {
        return nextMonth !== month && index < points.length - 1;
      }
      return previousMonth !== month;
    }

    function simulatedEquity(points, row, initialCapital, monthlyContribution) {
      let equity = Number(initialCapital || 0);
      let totalInvested = equity;
      const output = [{ d: points[0].d, t: points[0].t, v: equity }];
      for (let index = 1; index < points.length; index += 1) {
        const previous = points[index - 1].v;
        const dailyReturn = previous > 0 ? points[index].v / previous - 1 : 0;
        const contribution = contributionDay(points, index, row.Mode) ? Number(monthlyContribution || 0) : 0;
        equity = equity * (1 + dailyReturn) + contribution;
        totalInvested += contribution;
        output.push({ d: points[index].d, t: points[index].t, v: equity });
      }
      return {
        finalEquity: cleanNumber(equity),
        totalInvested: cleanNumber(totalInvested),
        points: output
      };
    }

    function adjustedPerformancePointsFromEquity(points, row) {
      if (points.length < 2) return points;
      const originalInitial = Number(REPORT_META.initialCapital || 20000);
      const originalMonthly = Number(REPORT_META.monthlyContribution || 0);
      const output = [{ d: points[0].d, t: points[0].t, v: originalInitial }];
      for (let index = 1; index < points.length; index += 1) {
        const previous = points[index - 1].v;
        const contribution = contributionDay(points, index, row.Mode) ? originalMonthly : 0;
        const periodReturn = previous > 0 ? (points[index].v - previous - contribution) / previous : 0;
        const nextValue = output[output.length - 1].v * (1 + periodReturn);
        output.push({ d: points[index].d, t: points[index].t, v: nextValue });
      }
      return output;
    }

    function drawdownPoints(points) {
      let peak = -Infinity;
      return points.map(point => {
        peak = Math.max(peak, point.v);
        return { d: point.d, t: point.t, v: peak > 0 ? point.v / peak - 1 : 0 };
      });
    }

    function rollingReturnPoints(points, window = 252) {
      const output = [];
      for (let index = window; index < points.length; index += 1) {
        const base = points[index - window].v;
        if (base > 0) {
          output.push({ d: points[index].d, t: points[index].t, v: points[index].v / base - 1 });
        }
      }
      return output;
    }

    function rollingReturnPointsByYears(points, years = 1) {
      const output = [];
      for (let index = 1; index < points.length; index += 1) {
        const cutoff = cutoffDate(points[index].d, years);
        const basePoint = [...points.slice(0, index)].reverse().find(point => point.d <= cutoff);
        if (basePoint?.v > 0) {
          output.push({ d: points[index].d, t: points[index].t, v: points[index].v / basePoint.v - 1 });
        }
      }
      return output;
    }

    function cutoffDate(endDate, years) {
      const date = new Date(`${endDate}T00:00:00`);
      date.setFullYear(date.getFullYear() - years);
      return date.toISOString().slice(0, 10);
    }

    function periodWindow(points, years) {
      const cutoff = cutoffDate(points[points.length - 1].d, years);
      return points.filter(point => point.d >= cutoff);
    }

    function computedRow(row, points, initialCapital, monthlyContribution, periodsPerYear = null) {
      const summary = performanceSummary(points, periodsPerYear);
      const equity = simulatedEquity(points, row, initialCapital, monthlyContribution);
      const output = {
        ...row,
        "Start Date": points[0].d,
        "End Date": points[points.length - 1].d,
        "Total Return": equity.totalInvested > 0 ? cleanNumber(equity.finalEquity / equity.totalInvested - 1) : null,
        "CAGR": summary.cagr,
        "Max Drawdown": summary.maxDrawdown,
        "Volatility": summary.volatility,
        "Sharpe": summary.sharpe,
        "Calmar": summary.calmar,
        "Final Equity": equity.finalEquity,
        "Total Invested": equity.totalInvested
      };
      [1, 3, 5, 7, 10].forEach(year => {
        const window = periodWindow(points, year);
        const period = window.length >= 2 ? performanceSummary(window, periodsPerYear) : {};
        output[`${year}Y Total Return`] = period.totalReturn ?? null;
        output[`${year}Y CAGR`] = period.cagr ?? null;
        output[`${year}Y MaxDD`] = period.maxDrawdown ?? null;
        output[`${year}Y Volatility`] = period.volatility ?? null;
        output[`${year}Y Sharpe`] = period.sharpe ?? null;
        output[`${year}Y Calmar`] = period.calmar ?? null;
      });
      return { row: output, equity };
    }

    function setRunStatus(message, isError = false) {
      const element = document.getElementById("runStatus");
      if (!element) return;
      element.textContent = message;
      element.classList.toggle("error", isError);
    }

    function numericParam(id, fallback) {
      const value = Number(document.getElementById(id).value);
      return Number.isFinite(value) ? value : Number(fallback || 0);
    }

    function resetPeriodComputation(message = "") {
      activeRows = baseRows;
      activeSeries = REPORT_SERIES;
      if (state.selected && !activeRows.some(row => row.Strategy === state.selected)) {
        state.selected = null;
      }
      setRunStatus(message);
      sync();
    }

    function runPeriodComputation() {
      renderRunCommand();
      const start = document.getElementById("paramStart").value || REPORT_META.startDate;
      const end = document.getElementById("paramEnd").value || REPORT_META.endDate;
      const initial = numericParam("paramInitial", REPORT_META.initialCapital);
      const monthly = numericParam("paramMonthly", REPORT_META.monthlyContribution);
      const startTime = Date.parse(start);
      const endTime = Date.parse(end);
      if (Number.isNaN(startTime) || Number.isNaN(endTime) || startTime > endTime) {
        setRunStatus("日期区间无效。", true);
        return;
      }
      const sourceSeries = REPORT_SERIES.performance || REPORT_SERIES.equity;
      const usingSampledSeries = !REPORT_SERIES.performance;
      const periodsPerYear = usingSampledSeries ? null : 252;
      if (!sourceSeries) {
        setRunStatus("当前报告缺少可用曲线序列，请重新生成报告。", true);
        return;
      }
      if (
        start === REPORT_META.startDate &&
        end === REPORT_META.endDate &&
        initial === Number(REPORT_META.initialCapital || 0) &&
        monthly === Number(REPORT_META.monthlyContribution || 0)
      ) {
        resetPeriodComputation("已恢复完整报告区间。");
        return;
      }

      const nextRows = [];
      const nextSeries = {
        strategies: [],
        equity: {},
        drawdown: {},
        rolling: {},
        performance: sourceSeries
      };

      baseRows.forEach(row => {
        const rawPoints = pointsInRange(performancePoints(row.Strategy, sourceSeries), start, end);
        if (rawPoints.length < 2) return;
        const points = usingSampledSeries ? adjustedPerformancePointsFromEquity(rawPoints, row) : rawPoints;
        const result = computedRow(row, points, initial, monthly, periodsPerYear);
        nextRows.push(result.row);
        nextSeries.strategies.push(row.Strategy);
        nextSeries.equity[row.Strategy] = sampleMonthEnd(result.equity.points);
        nextSeries.drawdown[row.Strategy] = sampleMonthEnd(drawdownPoints(points));
        nextSeries.rolling[row.Strategy] = sampleMonthEnd(usingSampledSeries ? rollingReturnPointsByYears(points) : rollingReturnPoints(points));
      });

      if (!nextRows.length) {
        setRunStatus("所选区间没有足够数据。", true);
        return;
      }
      activeRows = nextRows;
      activeSeries = nextSeries;
      if (state.selected && !activeRows.some(row => row.Strategy === state.selected)) {
        state.selected = activeRows[0]?.Strategy || null;
      }
      setRunStatus(`已按 ${start} 至 ${end} 重算 ${nextRows.length} 个策略${usingSampledSeries ? "，使用当前报告曲线序列" : ""}。`);
      sync();
    }

    function getFilteredRows() {
      const query = state.search.trim().toLowerCase();
      const benchmark = benchmarkRow();
      const rows = allRows().filter(row => {
        const tags = row.Tags || [];
        const text = `${row.Strategy} ${row["Required Assets"]} ${tags.join(" ")}`.toLowerCase();
        if (state.filter !== "all" && !tags.includes(state.filter)) return false;
        if (query && !text.includes(query)) return false;
        if ((row.CAGR ?? -Infinity) < state.minCagr) return false;
        if (Math.abs(row["Max Drawdown"] ?? 0) > state.maxDrawdown) return false;
        if (state.beatQqq && benchmark && row.CAGR <= benchmark.CAGR) return false;
        if (state.betterDd && benchmark && row["Max Drawdown"] <= benchmark["Max Drawdown"]) return false;
        return true;
      });

      rows.sort((a, b) => {
        const av = a[state.sortKey];
        const bv = b[state.sortKey];
        if (typeof av === "string" || typeof bv === "string") {
          return state.sortDir === "asc"
            ? String(av).localeCompare(String(bv))
            : String(bv).localeCompare(String(av));
        }
        const an = Number(av ?? (state.sortDir === "asc" ? Infinity : -Infinity));
        const bn = Number(bv ?? (state.sortDir === "asc" ? Infinity : -Infinity));
        return state.sortDir === "asc" ? an - bn : bn - an;
      });
      return rows;
    }

    function renderMeta() {
      document.getElementById("reportTitle").textContent = `${REPORT_META.title} · ${REPORT_META.subtitle}`;
      document.getElementById("metaLine").innerHTML = [
        `区间 ${REPORT_META.startDate} 至 ${REPORT_META.endDate}`,
        `${REPORT_META.strategyCount} 个策略`,
        `初始资金 ${fmtMoney(REPORT_META.initialCapital)}`,
        `每月追加 ${fmtMoney(REPORT_META.monthlyContribution)}`,
        `总投入 ${fmtMoney(REPORT_META.totalInvested)}`,
        `交易成本 ${fmtPct(REPORT_META.transactionCost)}`,
        `生成 ${REPORT_META.generatedAt}`
      ].map(item => `<span class="meta-pill">${esc(item)}</span>`).join("");
    }

    function renderRunCommand() {
      const start = document.getElementById("paramStart").value || REPORT_META.startDate;
      const end = document.getElementById("paramEnd").value || REPORT_META.endDate;
      const initial = Number(document.getElementById("paramInitial").value || REPORT_META.initialCapital || 0);
      const monthly = Number(document.getElementById("paramMonthly").value || REPORT_META.monthlyContribution || 0);
      const cost = Number(REPORT_META.transactionCost ?? 0.0005);
      const command = [
        ".\\.venv\\Scripts\\python.exe -m src.main",
        `--start ${start}`,
        `--end ${end}`,
        `--initial-capital ${initial}`,
        `--monthly-contribution ${monthly}`,
        `--transaction-cost ${cost}`
      ].join(" ");
      document.getElementById("runCommand").textContent = command;
    }

    function renderRunForm() {
      document.getElementById("paramStart").value = REPORT_META.startDate || "";
      document.getElementById("paramEnd").value = REPORT_META.endDate || "";
      document.getElementById("paramStart").min = REPORT_META.startDate || "";
      document.getElementById("paramStart").max = REPORT_META.endDate || "";
      document.getElementById("paramEnd").min = REPORT_META.startDate || "";
      document.getElementById("paramEnd").max = REPORT_META.endDate || "";
      document.getElementById("paramInitial").value = Math.round(Number(REPORT_META.initialCapital || 0));
      document.getElementById("paramMonthly").value = Math.round(Number(REPORT_META.monthlyContribution || 0));
      setRunStatus("");
      renderRunCommand();
    }

    async function copyRunCommand() {
      const text = document.getElementById("runCommand").textContent;
      try {
        await navigator.clipboard.writeText(text);
      } catch (error) {
        const area = document.createElement("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
    }

    function renderControls() {
      const filterHost = document.getElementById("filterChips");
      filterHost.innerHTML = filterOptions.map(([value, label]) => (
        `<button class="filter-chip ${state.filter === value ? "active" : ""}" type="button" data-filter="${esc(value)}">${esc(label)}</button>`
      )).join("");
      filterHost.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.filter = button.dataset.filter;
          sync();
        });
      });

      const chartToggleHost = document.getElementById("chartToggles");
      chartToggleHost.innerHTML = chartOptions.map(([key, label]) => (
        `<button class="chart-toggle ${state.chartVisibility[key] ? "" : "off"}" type="button" data-chart-toggle="${esc(key)}">${esc(label)}</button>`
      )).join("");
      chartToggleHost.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          toggleChart(button.dataset.chartToggle);
        });
      });

      const metricHost = document.getElementById("metricChips");
      metricHost.innerHTML = metricOptions.map(([value, label]) => (
        `<button class="metric-chip ${state.chartMetric === value ? "active" : ""}" type="button" data-metric="${esc(value)}">${esc(label)}</button>`
      )).join("");
      metricHost.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.chartMetric = button.dataset.metric;
          sync();
        });
      });

      const curveModeHost = document.getElementById("curveModeChips");
      curveModeHost.innerHTML = curveModeOptions.map(([value, label]) => (
        `<button class="metric-chip ${state.curveMode === value ? "active" : ""}" type="button" data-curve-mode="${esc(value)}">${esc(label)}</button>`
      )).join("");
      curveModeHost.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.curveMode = button.dataset.curveMode;
          sync();
        });
      });
    }

    function toggleChart(key) {
      state.chartVisibility[key] = !state.chartVisibility[key];
      syncChartVisibility();
      renderControls();
    }

    function syncChartVisibility() {
      document.querySelectorAll("[data-chart-panel]").forEach(panel => {
        const key = panel.dataset.chartPanel;
        const visible = state.chartVisibility[key] !== false;
        panel.classList.toggle("is-hidden", !visible);
      });
      document.querySelectorAll("button.collapse-toggle[data-chart-toggle]").forEach(button => {
        const key = button.dataset.chartToggle;
        const visible = state.chartVisibility[key] !== false;
        button.textContent = visible ? "隐藏" : "显示";
        button.setAttribute("aria-expanded", String(visible));
        button.setAttribute("title", visible ? "隐藏这个图表" : "显示这个图表");
      });
    }

    function renderKpis(rows) {
      const host = document.getElementById("kpiGrid");
      if (!rows.length) {
        host.innerHTML = `<div class="kpi-card"><div class="kpi-label">当前筛选</div><div class="kpi-value">无匹配策略</div><div class="kpi-owner">放宽筛选条件后再看。</div></div>`;
        return;
      }
      const bestFinal = maxBy(rows, "Final Equity");
      const bestCagr = maxBy(rows, "CAGR");
      const lowestDd = maxBy(rows, "Max Drawdown");
      const bestRisk = maxBy(rows, "Calmar");
      const cards = [
        ["最终资产最高", fmtMoney(bestFinal["Final Equity"]), bestFinal.Strategy, "Total Return", "good"],
        ["年化收益最高", fmtPct(bestCagr.CAGR), bestCagr.Strategy, "Sharpe", "good"],
        ["历史回撤最低", fmtPct(lowestDd["Max Drawdown"]), lowestDd.Strategy, "Volatility", "risk"],
        ["收益回撤最好", fmtNum(bestRisk.Calmar), bestRisk.Strategy, "Calmar", "good"]
      ];
      host.innerHTML = cards.map(([label, value, owner, subKey, tone]) => {
        const row = rows.find(item => item.Strategy === owner);
        const type = metricFormatFor(subKey);
        return `<article class="kpi-card">
          <div class="kpi-label">${esc(label)}</div>
          <div class="kpi-value">${esc(value)}</div>
          <div class="kpi-owner">
            <span class="strategy-name">${esc(owner)}</span>
            <span class="delta-pill ${tone}">${esc(subKey)} ${esc(fmtMetric(row?.[subKey], type))}</span>
          </div>
        </article>`;
      }).join("");
    }

    function maxBy(rows, key) {
      return rows.reduce((best, row) => {
        const current = Number(row[key] ?? -Infinity);
        const previous = Number(best?.[key] ?? -Infinity);
        return current > previous ? row : best;
      }, rows[0]);
    }

    function renderDetail(rows) {
      const host = document.getElementById("detailPanel");
      const selected = rows.find(row => row.Strategy === state.selected) || rows[0];
      if (!selected) {
        host.innerHTML = `<div class="empty-state">没有可展示的策略。调整左侧筛选条件试试。</div>`;
        return;
      }
      state.selected = selected.Strategy;
      const benchmark = benchmarkRow();
      const qqqCagrDelta = benchmark ? selected.CAGR - benchmark.CAGR : null;
      const qqqDdDelta = benchmark ? selected["Max Drawdown"] - benchmark["Max Drawdown"] : null;
      host.innerHTML = `<div class="detail-layout">
        <div>
          <h3 class="detail-name">${esc(selected.Strategy)}</h3>
          <p class="detail-text">${esc(selected.Description)}</p>
          <div class="tag-row">${(selected.Tags || []).map(tag => `<span class="tag">${esc(tag)}</span>`).join("")}</div>
          <div class="implementation-box"><strong>实施规则：</strong>${esc(selected.Implementation)}</div>
        </div>
        <div class="mini-metrics">
          <div class="mini-metric"><span>最终净值</span><strong>${fmtMoney(selected["Final Equity"])}</strong></div>
          <div class="mini-metric"><span>年化收益</span><strong>${fmtPct(selected.CAGR)}</strong></div>
          <div class="mini-metric"><span>最大回撤</span><strong>${fmtPct(selected["Max Drawdown"])}</strong></div>
          <div class="mini-metric"><span>相对 QQQ 年化</span><strong>${fmtPct(qqqCagrDelta)}</strong></div>
          <div class="mini-metric"><span>相对 QQQ 回撤</span><strong>${fmtPct(qqqDdDelta)}</strong></div>
          <div class="mini-metric"><span>资产需求</span><strong>${esc(selected["Required Assets"])}</strong></div>
        </div>
      </div>`;
    }

    function renderMethodPanel(rows) {
      const host = document.getElementById("methodPanel");
      if (!rows.length) {
        host.innerHTML = `<div class="empty-state">没有可展示的策略。调整左侧筛选条件试试。</div>`;
        return;
      }
      host.innerHTML = rows.map(row => `<button class="method-item ${row.Strategy === state.selected ? "selected" : ""}" type="button" data-strategy="${esc(row.Strategy)}">
        <div>
          <div class="method-name">${esc(row.Strategy)}</div>
          <div class="method-meta">${esc(row["Rebalance Frequency"] || "monthly")} · ${esc((row.Tags || []).join(" / "))}</div>
          <div class="method-meta">${esc(row["Required Assets"] || "")}</div>
        </div>
        <div class="method-text">${esc(row.Implementation)}</div>
      </button>`).join("");
      host.querySelectorAll("[data-strategy]").forEach(button => {
        button.addEventListener("click", () => {
          state.selected = button.dataset.strategy;
          sync();
          document.getElementById("detailPanel").scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
      });
    }

    function renderInteractiveLineChart(rows) {
      const chartHost = document.getElementById("interactiveLineChart");
      const legendHost = document.getElementById("lineLegend");
      const seriesByStrategy = seriesPayload()[state.curveMode] || {};
      const strategies = rows
        .map(row => row.Strategy)
        .filter(strategy => (seriesByStrategy[strategy] || []).length);

      const visibleCount = strategies.filter(strategy => !state.hiddenSeries[strategy]).length;
      legendHost.innerHTML = strategies.length
        ? `<div class="legend-count">${visibleCount} / ${strategies.length} 条曲线显示</div>` + strategies.map(strategy => {
            const hidden = Boolean(state.hiddenSeries[strategy]);
            return `<button class="legend-item ${hidden ? "off" : ""}" type="button" aria-pressed="${hidden ? "false" : "true"}" data-line-strategy="${esc(strategy)}">
              <span class="legend-swatch" style="background:${colorForStrategy(strategy)}"></span>
              <span>${esc(strategy)}</span>
            </button>`;
          }).join("")
        : `<div class="legend-count">当前筛选没有可绘制曲线</div>`;

      legendHost.querySelectorAll("[data-line-strategy]").forEach(button => {
        button.addEventListener("click", () => {
          const strategy = button.dataset.lineStrategy;
          state.hiddenSeries[strategy] = !state.hiddenSeries[strategy];
          renderInteractiveLineChart(getFilteredRows());
        });
      });

      if (!strategies.length) {
        chartHost.innerHTML = `<div class="empty-state">没有曲线可画。</div>`;
        return;
      }

      const seriesMap = new Map(strategies.map(strategy => [strategy, parsedSeries(strategy, seriesByStrategy)]));
      const visibleStrategies = strategies.filter(strategy => !state.hiddenSeries[strategy] && (seriesMap.get(strategy) || []).length);
      if (!visibleStrategies.length) {
        chartHost.innerHTML = `<div class="empty-state">全部曲线已隐藏。</div>`;
        return;
      }

      const allPoints = visibleStrategies.flatMap(strategy => seriesMap.get(strategy));
      const xValues = allPoints.map(point => point.t);
      const yValues = allPoints.map(point => point.v);
      let minX = Math.min(...xValues);
      let maxX = Math.max(...xValues);
      let minY = Math.min(...yValues);
      let maxY = Math.max(...yValues);

      if (minX === maxX) {
        minX -= 86400000;
        maxX += 86400000;
      }
      if (state.curveMode === "equity") {
        minY = Math.max(0, minY * 0.96);
        maxY = maxY * 1.04;
      } else if (state.curveMode === "drawdown") {
        minY = Math.min(minY * 1.08, minY - 0.01);
        maxY = 0;
      } else {
        const yPad = Math.max(0.02, (maxY - minY) * 0.08);
        minY -= yPad;
        maxY += yPad;
      }
      if (minY === maxY) {
        minY -= 0.01;
        maxY += 0.01;
      }

      const width = 980;
      const height = 500;
      const pad = { left: 78, right: 28, top: 30, bottom: 48 };
      const innerW = width - pad.left - pad.right;
      const innerH = height - pad.top - pad.bottom;
      const xScale = value => pad.left + (value - minX) / (maxX - minX) * innerW;
      const yScale = value => height - pad.bottom - (value - minY) / (maxY - minY) * innerH;
      const yTicks = Array.from({ length: 5 }, (_, index) => minY + (maxY - minY) * index / 4);
      const xTicks = Array.from({ length: 4 }, (_, index) => minX + (maxX - minX) * index / 3);
      const modeLabel = curveModeOptions.find(([value]) => value === state.curveMode)?.[1] || "曲线";

      const yGrid = yTicks.map(value => {
        const y = yScale(value);
        return `<g>
          <line class="line-grid" x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" />
          <text class="axis-label" x="${pad.left - 10}" y="${y + 4}" text-anchor="end">${esc(fmtCurveValue(value))}</text>
        </g>`;
      }).join("");
      const xGrid = xTicks.map(value => {
        const x = xScale(value);
        return `<g>
          <line class="line-grid" x1="${x}" y1="${pad.top}" x2="${x}" y2="${height - pad.bottom}" />
          <text class="axis-label" x="${x}" y="${height - 18}" text-anchor="middle">${esc(fmtDate(value))}</text>
        </g>`;
      }).join("");

      const paths = visibleStrategies.map(strategy => {
        const points = seriesMap.get(strategy);
        const d = points.map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(point.t).toFixed(2)} ${yScale(point.v).toFixed(2)}`).join(" ");
        const last = points[points.length - 1];
        const color = colorForStrategy(strategy);
        return `<g data-line-strategy="${esc(strategy)}">
          <path class="line-path" d="${d}" stroke="${color}" stroke-width="${strategy === state.selected ? 3 : 2}" opacity="${strategy === state.selected ? 0.98 : 0.82}">
            <title>${esc(strategy)} · ${esc(modeLabel)} · ${esc(fmtCurveValue(last.v))}</title>
          </path>
          <circle cx="${xScale(last.t)}" cy="${yScale(last.v)}" r="${strategy === state.selected ? 4 : 3}" fill="${color}" stroke="white" stroke-width="1.5">
            <title>${esc(strategy)} · ${esc(fmtCurveValue(last.v))}</title>
          </circle>
        </g>`;
      }).join("");

      chartHost.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="策略${esc(modeLabel)}曲线">
        ${yGrid}
        ${xGrid}
        <line class="line-axis" x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" />
        <line class="line-axis" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" />
        <text class="axis-label" x="${pad.left}" y="18">${esc(modeLabel)}</text>
        ${paths}
      </svg>`;

      chartHost.querySelectorAll("[data-line-strategy]").forEach(group => {
        group.addEventListener("click", () => {
          state.selected = group.dataset.lineStrategy;
          sync();
        });
      });
    }

    function renderBarChart(rows) {
      const host = document.getElementById("barChart");
      if (!rows.length) {
        host.innerHTML = `<div class="empty-state">没有数据可画。</div>`;
        return;
      }
      const key = state.chartMetric;
      const sorted = [...rows].sort((a, b) => {
        if (key.includes("Drawdown")) return Number(b[key] ?? -Infinity) - Number(a[key] ?? -Infinity);
        return Number(b[key] ?? -Infinity) - Number(a[key] ?? -Infinity);
      }).slice(0, 18);
      const width = 760;
      const rowH = 34;
      const top = 22;
      const left = 210;
      const right = 82;
      const height = top + sorted.length * rowH + 22;
      const values = sorted.map(row => Number(row[key] ?? 0));
      const min = Math.min(0, ...values);
      const max = Math.max(...values);
      const span = Math.max(0.0001, max - min);
      const axisX = left + (0 - min) / span * (width - left - right);
      const type = metricFormatFor(key);
      const bars = sorted.map((row, index) => {
        const value = Number(row[key] ?? 0);
        const y = top + index * rowH;
        const xValue = left + (value - min) / span * (width - left - right);
        const x = Math.min(axisX, xValue);
        const barW = Math.max(3, Math.abs(xValue - axisX));
        const color = value >= 0 ? "var(--accent)" : "var(--red)";
        const selectedClass = row.Strategy === state.selected ? `stroke="var(--ink)" stroke-width="2"` : "";
        return `<g role="button" tabindex="0" data-strategy="${esc(row.Strategy)}">
          <text class="bar-label" x="10" y="${y + 20}">${esc(row.Strategy)}</text>
          <rect x="${x}" y="${y + 7}" width="${barW}" height="18" rx="5" fill="${color}" ${selectedClass}></rect>
          <text class="bar-value" x="${Math.max(xValue, axisX) + 8}" y="${y + 21}">${esc(fmtMetric(value, type))}</text>
        </g>`;
      }).join("");
      host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="策略排行图">
        <line x1="${axisX}" y1="10" x2="${axisX}" y2="${height - 12}" stroke="var(--line)" />
        ${bars}
      </svg>`;
      host.querySelectorAll("[data-strategy]").forEach(group => {
        group.addEventListener("click", () => {
          state.selected = group.dataset.strategy;
          sync();
        });
      });
    }

    function renderScatter(rows) {
      const host = document.getElementById("scatterChart");
      if (!rows.length) {
        host.innerHTML = `<div class="empty-state">没有数据可画。</div>`;
        return;
      }
      const width = 520;
      const height = 360;
      const pad = { left: 52, right: 22, top: 28, bottom: 46 };
      const xs = rows.map(row => Number(row.Volatility ?? 0));
      const ys = rows.map(row => Number(row.CAGR ?? 0));
      const minX = Math.max(0, Math.min(...xs) * 0.88);
      const maxX = Math.max(...xs) * 1.08;
      const minY = Math.min(0, Math.min(...ys) * 0.9);
      const maxY = Math.max(...ys) * 1.12;
      const xScale = value => pad.left + (value - minX) / Math.max(0.0001, maxX - minX) * (width - pad.left - pad.right);
      const yScale = value => height - pad.bottom - (value - minY) / Math.max(0.0001, maxY - minY) * (height - pad.top - pad.bottom);
      const points = rows.map(row => {
        const drawdown = Math.abs(Number(row["Max Drawdown"] ?? 0));
        const radius = 7 + Math.min(12, Math.max(0, Number(row["Final Equity"] ?? 0) / 12000000));
        const color = drawdown > 0.65 ? "var(--red)" : drawdown > 0.5 ? "var(--orange)" : "var(--accent)";
        const selected = row.Strategy === state.selected;
        return `<g role="button" tabindex="0" data-strategy="${esc(row.Strategy)}">
          <circle cx="${xScale(Number(row.Volatility ?? 0))}" cy="${yScale(Number(row.CAGR ?? 0))}" r="${selected ? radius + 2 : radius}" fill="${color}" opacity="${selected ? 0.96 : 0.72}" stroke="${selected ? "var(--ink)" : "white"}" stroke-width="${selected ? 2 : 1.5}">
            <title>${esc(row.Strategy)} · 年化 ${fmtPct(row.CAGR)} · 波动 ${fmtPct(row.Volatility)} · 回撤 ${fmtPct(row["Max Drawdown"])}</title>
          </circle>
          ${selected ? `<text class="point-label" x="${xScale(Number(row.Volatility ?? 0)) + 12}" y="${yScale(Number(row.CAGR ?? 0)) - 10}">${esc(row.Strategy)}</text>` : ""}
        </g>`;
      }).join("");
      host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="风险收益散点图">
        <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" stroke="var(--line)" />
        <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" stroke="var(--line)" />
        <text class="axis-label" x="${width / 2 - 36}" y="${height - 12}">波动率</text>
        <text class="axis-label" x="12" y="18">年化收益</text>
        <text class="axis-label" x="${pad.left - 40}" y="${height - pad.bottom + 4}">${fmtPct(minY)}</text>
        <text class="axis-label" x="${pad.left - 44}" y="${pad.top + 4}">${fmtPct(maxY)}</text>
        <text class="axis-label" x="${pad.left - 8}" y="${height - pad.bottom + 22}">${fmtPct(minX)}</text>
        <text class="axis-label" x="${width - pad.right - 42}" y="${height - pad.bottom + 22}">${fmtPct(maxX)}</text>
        ${points}
      </svg>`;
      host.querySelectorAll("[data-strategy]").forEach(group => {
        group.addEventListener("click", () => {
          state.selected = group.dataset.strategy;
          sync();
        });
      });
    }

    function renderHeatmap(rows) {
      const host = document.getElementById("heatmap");
      if (!rows.length) {
        host.innerHTML = `<div class="empty-state">没有数据可展示。</div>`;
        return;
      }
      const periods = ["1Y CAGR", "3Y CAGR", "5Y CAGR", "7Y CAGR", "10Y CAGR"];
      const values = rows.flatMap(row => periods.map(period => Number(row[period] ?? 0)));
      const min = Math.min(...values);
      const max = Math.max(...values);
      const colorFor = value => {
        const t = (Number(value ?? 0) - min) / Math.max(0.0001, max - min);
        const light = 94 - t * 28;
        const sat = 32 + t * 26;
        return `hsl(158, ${sat}%, ${light}%)`;
      };
      const header = `<div class="heat-row">
        <div class="heat-cell heat-head heat-name">策略</div>
        ${periods.map(period => `<div class="heat-cell heat-head">${period.replace(" CAGR", "")}</div>`).join("")}
      </div>`;
      const body = rows.map(row => `<div class="heat-row">
        <button class="heat-cell heat-name" type="button" data-strategy="${esc(row.Strategy)}">${esc(row.Strategy)}</button>
        ${periods.map(period => `<div class="heat-cell" style="background:${colorFor(row[period])}">${fmtPct(row[period])}</div>`).join("")}
      </div>`).join("");
      host.innerHTML = header + body;
      host.querySelectorAll("[data-strategy]").forEach(button => {
        button.addEventListener("click", () => {
          state.selected = button.dataset.strategy;
          sync();
        });
      });
    }

    function renderTable(rows) {
      const table = document.getElementById("resultsTable");
      const header = `<thead><tr>${columns.map(([key, label]) => {
        const mark = state.sortKey === key ? (state.sortDir === "asc" ? " ↑" : " ↓") : "";
        return `<th class="sortable" data-key="${esc(key)}">${esc(label + mark)}</th>`;
      }).join("")}</tr></thead>`;
      const body = rows.map((row, index) => `<tr class="${row.Strategy === state.selected ? "selected" : ""}" data-strategy="${esc(row.Strategy)}">
        ${columns.map(([key, _label, type], colIndex) => {
          const raw = row[key];
          const value = fmtMetric(raw, type);
          const tone = key.includes("CAGR") || key === "Total Return" ? (Number(raw) >= 0 ? "good" : "bad") : key.includes("Drawdown") || key.includes("MaxDD") ? (Number(raw) > -0.5 ? "good" : "bad") : "";
          if (colIndex === 0) {
            return `<td><span class="rank-badge ${index < 3 ? "top" : ""}">${index + 1}</span><span class="strategy-name table-strategy-name" tabindex="0" data-strategy-tooltip="${esc(row.Strategy)}">${esc(value)}</span></td>`;
          }
          return `<td class="number ${tone}">${esc(value)}</td>`;
        }).join("")}
      </tr>`).join("");
      table.innerHTML = header + `<tbody>${body}</tbody>`;
      table.querySelectorAll("th.sortable").forEach(th => {
        th.addEventListener("click", () => {
          const key = th.dataset.key;
          if (state.sortKey === key) {
            state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
          } else {
            state.sortKey = key;
            state.sortDir = key === "Max Drawdown" || key === "Volatility" ? "asc" : "desc";
          }
          document.getElementById("sortSelect").value = `${state.sortKey}:${state.sortDir}`;
          sync();
        });
      });
      table.querySelectorAll("tbody tr").forEach(row => {
        row.addEventListener("click", () => {
          state.selected = row.dataset.strategy;
          sync();
        });
      });
      bindStrategyTooltips(table);
    }

    function rowForStrategy(strategyName) {
      return allRows().find(row => row.Strategy === strategyName);
    }

    function tooltipHtml(row) {
      return `<div class="tooltip-title">${esc(row.Strategy)}</div>
        <div class="tooltip-meta">
          ${(row.Tags || []).map(tag => `<span class="tooltip-pill">${esc(tag)}</span>`).join("")}
          <span class="tooltip-pill">${esc(row["Rebalance Frequency"] || "monthly")}</span>
          <span class="tooltip-pill">${esc(row["Required Assets"] || "N/A")}</span>
        </div>
        <p class="tooltip-body"><strong>简介：</strong>${esc(row.Description)}</p>
        <p class="tooltip-body"><strong>实施：</strong>${esc(row.Implementation)}</p>
        <div class="tooltip-kpis">
          <div class="tooltip-kpi"><span>年化</span><strong>${fmtPct(row.CAGR)}</strong></div>
          <div class="tooltip-kpi"><span>最大回撤</span><strong>${fmtPct(row["Max Drawdown"])}</strong></div>
          <div class="tooltip-kpi"><span>夏普</span><strong>${fmtNum(row.Sharpe)}</strong></div>
          <div class="tooltip-kpi"><span>最终净值</span><strong>${fmtMoney(row["Final Equity"])}</strong></div>
        </div>`;
    }

    function showStrategyTooltip(strategyName, event) {
      const row = rowForStrategy(strategyName);
      const tooltip = document.getElementById("strategyTooltip");
      if (!row || !tooltip) return;
      tooltip.innerHTML = tooltipHtml(row);
      tooltip.hidden = false;
      tooltip.classList.add("is-visible");
      if (event && typeof event.clientX === "number") {
        positionStrategyTooltip(event);
      } else if (event?.currentTarget) {
        positionTooltipNearElement(event.currentTarget);
      }
    }

    function positionStrategyTooltip(event) {
      const tooltip = document.getElementById("strategyTooltip");
      if (!tooltip || tooltip.hidden) return;
      const offset = 16;
      const rect = tooltip.getBoundingClientRect();
      let left = event.clientX + offset;
      let top = event.clientY + offset;
      if (left + rect.width > window.innerWidth - 12) {
        left = event.clientX - rect.width - offset;
      }
      if (top + rect.height > window.innerHeight - 12) {
        top = event.clientY - rect.height - offset;
      }
      tooltip.style.left = `${Math.max(12, left)}px`;
      tooltip.style.top = `${Math.max(12, top)}px`;
    }

    function positionTooltipNearElement(element) {
      const tooltip = document.getElementById("strategyTooltip");
      if (!tooltip || tooltip.hidden) return;
      const elementRect = element.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();
      let left = elementRect.left;
      let top = elementRect.bottom + 10;
      if (left + tooltipRect.width > window.innerWidth - 12) {
        left = window.innerWidth - tooltipRect.width - 12;
      }
      if (top + tooltipRect.height > window.innerHeight - 12) {
        top = elementRect.top - tooltipRect.height - 10;
      }
      tooltip.style.left = `${Math.max(12, left)}px`;
      tooltip.style.top = `${Math.max(12, top)}px`;
    }

    function hideStrategyTooltip() {
      const tooltip = document.getElementById("strategyTooltip");
      if (!tooltip) return;
      tooltip.classList.remove("is-visible");
      tooltip.hidden = true;
    }

    function bindStrategyTooltips(table) {
      table.querySelectorAll("[data-strategy-tooltip]").forEach(element => {
        element.addEventListener("mouseenter", event => showStrategyTooltip(element.dataset.strategyTooltip, event));
        element.addEventListener("mousemove", positionStrategyTooltip);
        element.addEventListener("mouseleave", hideStrategyTooltip);
        element.addEventListener("focus", event => showStrategyTooltip(element.dataset.strategyTooltip, event));
        element.addEventListener("blur", hideStrategyTooltip);
      });
      const wrapper = table.closest(".table-wrap");
      if (wrapper && !wrapper.dataset.tooltipBound) {
        wrapper.addEventListener("scroll", hideStrategyTooltip);
        wrapper.dataset.tooltipBound = "true";
      }
    }

    function renderImages() {
      const tabs = document.getElementById("imageTabs");
      tabs.innerHTML = REPORT_META.chartImages.map((image, index) => (
        `<button class="metric-chip ${state.imageIndex === index ? "active" : ""}" type="button" data-image-index="${index}">${esc(image.label)}</button>`
      )).join("");
      tabs.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.imageIndex = Number(button.dataset.imageIndex);
          renderImages();
        });
      });
      const image = REPORT_META.chartImages[state.imageIndex] || REPORT_META.chartImages[0];
      const element = document.getElementById("chartImage");
      element.src = image.src;
      element.alt = image.label;
    }

    function renderCounts(rows) {
      document.getElementById("resultCount").textContent = `${rows.length} / ${allRows().length}`;
      document.getElementById("minCagrValue").textContent = fmtPct(state.minCagr);
      document.getElementById("maxDrawdownValue").textContent = fmtPct(-state.maxDrawdown);
    }

    function sync() {
      const rows = getFilteredRows();
      if (state.selected && !rows.some(row => row.Strategy === state.selected)) {
        state.selected = rows[0]?.Strategy || null;
      }
      renderControls();
      renderCounts(rows);
      renderKpis(rows);
      renderDetail(rows);
      renderMethodPanel(rows);
      renderInteractiveLineChart(rows);
      renderBarChart(rows);
      renderScatter(rows);
      renderHeatmap(rows);
      renderTable(rows);
      syncChartVisibility();
    }

    function resetFilters() {
      state.filter = "all";
      state.search = "";
      state.minCagr = 0;
      state.maxDrawdown = 0.9;
      state.beatQqq = false;
      state.betterDd = false;
      state.sortKey = "CAGR";
      state.sortDir = "desc";
      state.chartMetric = "CAGR";
      state.curveMode = "equity";
      state.hiddenSeries = {};
      state.chartVisibility = {
        curves: true,
        rank: true,
        scatter: true,
        heatmap: true,
        images: true
      };
      document.getElementById("searchInput").value = "";
      document.getElementById("minCagr").value = "0";
      document.getElementById("maxDrawdown").value = "90";
      document.getElementById("beatQqqToggle").checked = false;
      document.getElementById("betterDdToggle").checked = false;
      document.getElementById("sortSelect").value = "CAGR:desc";
      sync();
    }

    function downloadCsv() {
      const rows = getFilteredRows();
      const header = columns.map(([, label]) => label);
      const csvRows = [header.join(",")];
      rows.forEach(row => {
        csvRows.push(columns.map(([key]) => {
          const value = row[key] ?? "";
          const text = String(value).replaceAll('"', '""');
          return `"${text}"`;
        }).join(","));
      });
      const blob = new Blob(["\ufeff" + csvRows.join("\n")], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "qqq_strategy_filtered_results.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    }

    function bindInputs() {
      document.getElementById("searchInput").addEventListener("input", event => {
        state.search = event.target.value;
        sync();
      });
      document.getElementById("sortSelect").addEventListener("change", event => {
        const [key, dir] = event.target.value.split(":");
        state.sortKey = key;
        state.sortDir = dir;
        sync();
      });
      document.getElementById("minCagr").addEventListener("input", event => {
        state.minCagr = Number(event.target.value) / 100;
        sync();
      });
      document.getElementById("maxDrawdown").addEventListener("input", event => {
        state.maxDrawdown = Number(event.target.value) / 100;
        sync();
      });
      document.getElementById("beatQqqToggle").addEventListener("change", event => {
        state.beatQqq = event.target.checked;
        sync();
      });
      document.getElementById("betterDdToggle").addEventListener("change", event => {
        state.betterDd = event.target.checked;
        sync();
      });
      ["paramStart", "paramEnd", "paramInitial", "paramMonthly"].forEach(id => {
        document.getElementById(id).addEventListener("input", () => {
          renderRunCommand();
          setRunStatus("参数已修改，点击运行运算。");
        });
      });
      document.querySelectorAll(".chart-panel [data-chart-toggle]").forEach(button => {
        button.addEventListener("click", () => {
          toggleChart(button.dataset.chartToggle);
        });
      });
      document.getElementById("resetFilters").addEventListener("click", resetFilters);
      document.getElementById("downloadCsv").addEventListener("click", downloadCsv);
      document.getElementById("runPeriod").addEventListener("click", runPeriodComputation);
      document.getElementById("copyCommand").addEventListener("click", copyRunCommand);
    }

    renderMeta();
    renderRunForm();
    bindInputs();
    renderImages();
    sync();
  </script>
</body>
</html>
"""


CHART_PAGE_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QQQ 策略实验室 - 独立图表页面</title>
  <style>
    :root {
      --bg: #f6f8f7;
      --surface: #ffffff;
      --surface-soft: #eef3f1;
      --ink: #18211f;
      --muted: #66736f;
      --line: #d8e0dd;
      --accent: #0f766e;
      --accent-strong: #0b5f59;
      --blue: #2563eb;
      --orange: #c05621;
      --red: #b42318;
      --green: #0b7a53;
      --shadow: 0 12px 34px rgba(24, 33, 31, 0.10);
      --radius: 8px;
    }

    * {
      box-sizing: border-box;
    }

    html {
      color-scheme: light;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Inter", "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      letter-spacing: 0;
    }

    button,
    input,
    select {
      font: inherit;
    }

    button {
      cursor: pointer;
    }

    .chart-shell {
      width: min(100%, 1760px);
      margin: 0 auto;
      padding: 22px 28px 30px;
    }

    .topbar {
      display: grid;
      grid-template-columns: minmax(260px, 1fr) auto;
      gap: 18px;
      align-items: start;
      margin-bottom: 14px;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 30px;
      line-height: 1.12;
      font-weight: 760;
      overflow-wrap: anywhere;
    }

    .meta-line {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }

    .meta-pill {
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      border-radius: 999px;
      padding: 5px 9px;
      white-space: nowrap;
    }

    .button {
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--ink);
      min-height: 36px;
      padding: 7px 12px;
      border-radius: var(--radius);
      display: inline-flex;
      align-items: center;
      gap: 7px;
      text-decoration: none;
      box-shadow: 0 1px 0 rgba(255,255,255,0.8);
    }

    .button.primary,
    .tab.active,
    .filter-chip.active,
    .metric-chip.active {
      background: var(--accent);
      color: #ffffff;
      border-color: var(--accent);
    }

    .control-panel,
    .panel {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgba(255, 255, 255, 0.94);
      box-shadow: var(--shadow);
    }

    .control-panel {
      display: grid;
      grid-template-columns: minmax(220px, 0.8fr) minmax(280px, 1.4fr) minmax(240px, 0.8fr) minmax(250px, 0.8fr);
      gap: 12px;
      padding: 14px;
      margin-bottom: 14px;
      align-items: end;
    }

    .field {
      display: grid;
      gap: 7px;
      min-width: 0;
    }

    label,
    .field-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .searchbox,
    .selectbox {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      color: var(--ink);
      padding: 8px 10px;
      outline: none;
    }

    .chip-grid,
    .tab-row,
    .toggle-row,
    .image-tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }

    .tab-row {
      margin-bottom: 14px;
    }

    .tab,
    .filter-chip,
    .metric-chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fbfcfc;
      color: var(--ink);
      min-height: 36px;
      padding: 7px 13px;
      text-decoration: none;
    }

    .tab {
      border-radius: var(--radius);
      font-weight: 720;
    }

    .toggle {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      padding: 7px 10px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: #31413d;
      font-size: 13px;
    }

    .range-row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
    }

    input[type="range"] {
      width: 100%;
      accent-color: var(--accent);
    }

    .panel {
      padding: 16px;
      min-width: 0;
    }

    .chart-view[hidden] {
      display: none;
    }

    .section-title {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }

    .section-title h2 {
      margin: 0;
      font-size: 21px;
      line-height: 1.25;
    }

    .section-title small {
      color: var(--muted);
      line-height: 1.45;
    }

    .chart-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }

    .line-chart-layout {
      display: grid;
      gap: 12px;
    }

    .line-chart-stage,
    .chart-stage {
      width: 100%;
      min-height: 620px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
    }

    .line-chart-stage svg,
    .chart-stage svg {
      width: 100%;
      min-width: 1120px;
      height: auto;
      display: block;
    }

    .legend-panel {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
      gap: 7px;
      max-height: 230px;
      overflow: auto;
      padding: 2px 4px 2px 0;
    }

    .legend-count {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      padding: 8px 2px 0;
    }

    .legend-item {
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fbfcfc;
      color: var(--ink);
      min-height: 34px;
      padding: 6px 8px;
      display: flex;
      align-items: center;
      gap: 8px;
      text-align: left;
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .legend-item:hover {
      border-color: rgba(15, 118, 110, 0.42);
      background: #f1faf7;
    }

    .legend-item.off {
      color: var(--muted);
      background: #f1f4f3;
      text-decoration: line-through;
    }

    .legend-swatch {
      width: 18px;
      height: 3px;
      border-radius: 999px;
      flex: 0 0 auto;
    }

    .legend-item.off .legend-swatch {
      opacity: 0.35;
    }

    .line-path {
      fill: none;
      stroke-linecap: round;
      stroke-linejoin: round;
      vector-effect: non-scaling-stroke;
    }

    .line-grid {
      stroke: #e5ece9;
      stroke-width: 1;
    }

    .line-axis {
      stroke: #bfcbc7;
      stroke-width: 1;
    }

    .axis-label {
      fill: var(--muted);
      font-size: 12px;
    }

    .bar-label,
    .point-label {
      fill: var(--ink);
      font-size: 13px;
      font-weight: 650;
    }

    .bar-value {
      fill: var(--muted);
      font-size: 12px;
    }

    .heatmap {
      display: grid;
      gap: 7px;
      overflow: auto;
      padding-bottom: 3px;
    }

    .heat-row {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) repeat(5, minmax(108px, 0.34fr));
      gap: 7px;
      align-items: stretch;
      min-width: 860px;
    }

    .heat-cell {
      border: 0;
      border-radius: 7px;
      padding: 9px 10px;
      min-height: 38px;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      font-size: 13px;
      font-weight: 680;
      color: #17332a;
    }

    button.heat-cell {
      cursor: pointer;
      font: inherit;
    }

    button.heat-cell:hover {
      outline: 2px solid rgba(15, 118, 110, 0.28);
      outline-offset: 0;
    }

    .heat-name {
      justify-content: flex-start;
      background: #f1f5f4;
      color: var(--ink);
      overflow-wrap: anywhere;
    }

    .heat-head {
      background: transparent;
      color: var(--muted);
      font-weight: 700;
      min-height: 22px;
      padding-top: 0;
      padding-bottom: 0;
    }

    .image-frame {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      overflow: auto;
      min-height: 620px;
    }

    .image-frame img {
      display: block;
      width: 100%;
      min-width: 1120px;
      height: auto;
    }

    .empty-state {
      min-height: 280px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: var(--radius);
      background: #fbfcfc;
      text-align: center;
      padding: 18px;
    }

    .footnote {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.55;
      margin: 10px 0 0;
    }

    @media (max-width: 1180px) {
      .control-panel {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 760px) {
      .chart-shell {
        padding: 14px;
      }

      .topbar,
      .control-panel {
        grid-template-columns: 1fr;
      }

      h1 {
        font-size: 24px;
      }
    }
  </style>
</head>
<body>
  <main class="chart-shell">
    <header class="topbar">
      <div>
        <h1 id="reportTitle">QQQ 策略实验室 · 独立图表页面</h1>
        <div class="meta-line" id="metaLine"></div>
      </div>
      <a class="button" href="dashboard.html">返回总览</a>
    </header>

    <section class="control-panel" aria-label="图表筛选">
      <div class="field">
        <label for="searchInput">搜索策略 / 资产 / 标签</label>
        <input class="searchbox" id="searchInput" type="search" placeholder="例如 trend、2x、SHY" />
      </div>
      <div class="field">
        <span class="field-label">策略标签</span>
        <div class="chip-grid" id="filterChips"></div>
      </div>
      <div class="field">
        <div class="range-row">
          <label for="minCagr">最低年化收益</label>
          <strong id="minCagrValue"></strong>
        </div>
        <input id="minCagr" type="range" min="0" max="30" step="1" value="0" />
      </div>
      <div class="field">
        <div class="range-row">
          <label for="maxDrawdown">最大可承受回撤</label>
          <strong id="maxDrawdownValue"></strong>
        </div>
        <input id="maxDrawdown" type="range" min="30" max="90" step="1" value="90" />
      </div>
      <div class="field">
        <span class="field-label">快速条件</span>
        <div class="toggle-row">
          <label class="toggle">
            <input id="beatQqqToggle" type="checkbox" />
            年化收益高于 QQQ
          </label>
          <label class="toggle">
            <input id="betterDdToggle" type="checkbox" />
            最大回撤优于 QQQ
          </label>
          <button class="button" id="resetFilters" type="button">重置</button>
        </div>
      </div>
      <div class="field">
        <span class="field-label">当前结果</span>
        <div class="meta-line" id="chartSummary"></div>
      </div>
    </section>

    <nav class="tab-row" id="chartTabs" aria-label="图表导航"></nav>

    <section class="panel chart-view" data-view="curves">
      <div class="section-title">
        <h2>策略曲线图</h2>
        <small>图例在下方，点击策略名隐藏或恢复对应曲线。</small>
      </div>
      <div class="chart-toolbar">
        <div class="chip-grid" id="curveModeChips"></div>
      </div>
      <div class="line-chart-layout">
        <div class="line-chart-stage" id="interactiveLineChart"></div>
        <div>
          <div class="legend-count" id="lineLegendCount"></div>
          <div class="legend-panel" id="lineLegend"></div>
        </div>
      </div>
    </section>

    <section class="panel chart-view" data-view="rank" hidden>
      <div class="section-title">
        <h2>收益 / 回撤排行</h2>
        <small>当前筛选后的策略会重新排序。</small>
      </div>
      <div class="chart-toolbar">
        <div class="chip-grid" id="metricChips"></div>
      </div>
      <div class="chart-stage" id="barChart"></div>
    </section>

    <section class="panel chart-view" data-view="scatter" hidden>
      <div class="section-title">
        <h2>风险收益散点</h2>
        <small>横轴是波动率，纵轴是年化收益，点大小参考最终净值。</small>
      </div>
      <div class="chart-stage" id="scatterChart"></div>
    </section>

    <section class="panel chart-view" data-view="heatmap" hidden>
      <div class="section-title">
        <h2>滚动周期热力图</h2>
        <small>绿色越深表示对应周期年化收益越高。</small>
      </div>
      <div id="heatmap" class="heatmap"></div>
    </section>

    <section class="panel chart-view" data-view="images" hidden>
      <div class="section-title">
        <h2>原始回测图</h2>
        <small>来自 reports/charts 的 PNG 原图。</small>
      </div>
      <div class="image-tabs" id="imageTabs"></div>
      <div class="image-frame">
        <img id="chartImage" alt="回测图表" />
      </div>
      <p class="footnote">历史回测不构成投资建议。</p>
    </section>
  </main>

  <script>
    const REPORT_META = __REPORT_META__;
    const REPORT_ROWS = __REPORT_ROWS__;
    const REPORT_SERIES = __REPORT_SERIES__;

    const viewOptions = [
      ["curves", "策略曲线图"],
      ["rank", "收益排行"],
      ["scatter", "风险散点"],
      ["heatmap", "周期热力图"],
      ["images", "原始图"]
    ];

    const filterOptions = [
      ["all", "全部"],
      ["基准", "基准"],
      ["无杠杆", "无杠杆"],
      ["杠杆", "杠杆"],
      ["趋势", "趋势"],
      ["动量", "动量"],
      ["定投", "定投"],
      ["防守", "防守"],
      ["回撤", "回撤"]
    ];

    const metricOptions = [
      ["CAGR", "年化"],
      ["Final Equity", "终值"],
      ["Max Drawdown", "回撤"],
      ["Sharpe", "夏普"],
      ["Calmar", "Calmar"],
      ["10Y CAGR", "10 年"]
    ];

    const curveModeOptions = [
      ["equity", "净值"],
      ["drawdown", "回撤"],
      ["rolling", "滚动 1 年"]
    ];

    const lineColors = [
      "#0f766e", "#2563eb", "#c05621", "#7c3aed", "#dc2626", "#0891b2",
      "#16a34a", "#9333ea", "#ea580c", "#64748b", "#be123c", "#0d9488",
      "#4f46e5", "#ca8a04", "#15803d", "#b45309", "#0369a1", "#a21caf"
    ];

    const state = {
      view: "curves",
      filter: "all",
      search: "",
      minCagr: 0,
      maxDrawdown: 0.9,
      beatQqq: false,
      betterDd: false,
      chartMetric: "CAGR",
      curveMode: "equity",
      imageIndex: 0,
      selected: null,
      hiddenSeries: {}
    };

    const benchmark = REPORT_ROWS.find(row => row.Strategy === "qqq_buy_hold") || REPORT_ROWS[0];

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    function fmtPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
      return `${(Number(value) * 100).toFixed(2)}%`;
    }

    function fmtMoney(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
      return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value));
    }

    function fmtCompactMoney(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        notation: "compact",
        maximumFractionDigits: 1
      }).format(Number(value));
    }

    function fmtNum(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
      return Number(value).toFixed(2);
    }

    function fmtMetric(value, type) {
      if (type === "money") return fmtMoney(value);
      if (type === "pct") return fmtPct(value);
      if (type === "num") return fmtNum(value);
      return value ?? "N/A";
    }

    function fmtCurveValue(value) {
      return state.curveMode === "equity" ? fmtCompactMoney(value) : fmtPct(value);
    }

    function fmtDate(value) {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return "";
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    }

    function metricFormatFor(key) {
      if (key.includes("Return") || key.includes("CAGR") || key.includes("Drawdown") || key.includes("MaxDD") || key === "Volatility") return "pct";
      if (key.includes("Equity") || key.includes("Invested")) return "money";
      return "num";
    }

    function colorForStrategy(strategyName) {
      const seriesIndex = (REPORT_SERIES.strategies || []).indexOf(strategyName);
      const rowIndex = REPORT_ROWS.findIndex(row => row.Strategy === strategyName);
      const index = seriesIndex >= 0 ? seriesIndex : Math.max(0, rowIndex);
      return lineColors[index % lineColors.length];
    }

    function parsedSeries(strategyName, seriesByStrategy) {
      return (seriesByStrategy[strategyName] || [])
        .map(point => ({ t: Date.parse(point.d), v: Number(point.v), d: point.d }))
        .filter(point => Number.isFinite(point.t) && Number.isFinite(point.v))
        .sort((a, b) => a.t - b.t);
    }

    function getViewFromHash() {
      const view = location.hash.replace("#", "");
      return viewOptions.some(([value]) => value === view) ? view : "curves";
    }

    function getFilteredRows() {
      const query = state.search.trim().toLowerCase();
      return REPORT_ROWS.filter(row => {
        const tags = row.Tags || [];
        const text = `${row.Strategy} ${row["Required Assets"]} ${tags.join(" ")}`.toLowerCase();
        if (state.filter !== "all" && !tags.includes(state.filter)) return false;
        if (query && !text.includes(query)) return false;
        if ((row.CAGR ?? -Infinity) < state.minCagr) return false;
        if (Math.abs(row["Max Drawdown"] ?? 0) > state.maxDrawdown) return false;
        if (state.beatQqq && benchmark && row.CAGR <= benchmark.CAGR) return false;
        if (state.betterDd && benchmark && row["Max Drawdown"] <= benchmark["Max Drawdown"]) return false;
        return true;
      });
    }

    function renderMeta() {
      document.getElementById("reportTitle").textContent = `${REPORT_META.title} · 独立图表页面`;
      document.getElementById("metaLine").innerHTML = [
        `区间 ${REPORT_META.startDate} 至 ${REPORT_META.endDate}`,
        `${REPORT_META.strategyCount} 个策略`,
        `初始资金 ${fmtMoney(REPORT_META.initialCapital)}`,
        `每月追加 ${fmtMoney(REPORT_META.monthlyContribution)}`,
        `生成 ${REPORT_META.generatedAt}`
      ].map(item => `<span class="meta-pill">${esc(item)}</span>`).join("");
    }

    function renderTabs() {
      const host = document.getElementById("chartTabs");
      host.innerHTML = viewOptions.map(([value, label]) => (
        `<a class="tab ${state.view === value ? "active" : ""}" href="#${esc(value)}">${esc(label)}</a>`
      )).join("");
    }

    function renderControls(rows) {
      document.getElementById("minCagrValue").textContent = fmtPct(state.minCagr);
      document.getElementById("maxDrawdownValue").textContent = fmtPct(-state.maxDrawdown);
      document.getElementById("chartSummary").innerHTML = [
        `${rows.length} / ${REPORT_ROWS.length} 个策略`,
        `当前图：${viewOptions.find(([value]) => value === state.view)?.[1] || ""}`
      ].map(item => `<span class="meta-pill">${esc(item)}</span>`).join("");

      const filterHost = document.getElementById("filterChips");
      filterHost.innerHTML = filterOptions.map(([value, label]) => (
        `<button class="filter-chip ${state.filter === value ? "active" : ""}" type="button" data-filter="${esc(value)}">${esc(label)}</button>`
      )).join("");
      filterHost.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.filter = button.dataset.filter;
          sync();
        });
      });

      const curveModeHost = document.getElementById("curveModeChips");
      curveModeHost.innerHTML = curveModeOptions.map(([value, label]) => (
        `<button class="metric-chip ${state.curveMode === value ? "active" : ""}" type="button" data-curve-mode="${esc(value)}">${esc(label)}</button>`
      )).join("");
      curveModeHost.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.curveMode = button.dataset.curveMode;
          sync();
        });
      });

      const metricHost = document.getElementById("metricChips");
      metricHost.innerHTML = metricOptions.map(([value, label]) => (
        `<button class="metric-chip ${state.chartMetric === value ? "active" : ""}" type="button" data-metric="${esc(value)}">${esc(label)}</button>`
      )).join("");
      metricHost.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.chartMetric = button.dataset.metric;
          sync();
        });
      });
    }

    function syncView() {
      document.querySelectorAll("[data-view]").forEach(section => {
        section.hidden = section.dataset.view !== state.view;
      });
      renderTabs();
    }

    function renderInteractiveLineChart(rows) {
      const chartHost = document.getElementById("interactiveLineChart");
      const legendHost = document.getElementById("lineLegend");
      const legendCount = document.getElementById("lineLegendCount");
      const seriesByStrategy = REPORT_SERIES[state.curveMode] || {};
      const strategies = rows
        .map(row => row.Strategy)
        .filter(strategy => (seriesByStrategy[strategy] || []).length);

      const visibleCount = strategies.filter(strategy => !state.hiddenSeries[strategy]).length;
      legendCount.textContent = strategies.length ? `${visibleCount} / ${strategies.length} 条曲线显示` : "当前筛选没有可绘制曲线";
      legendHost.innerHTML = strategies.map(strategy => {
        const hidden = Boolean(state.hiddenSeries[strategy]);
        return `<button class="legend-item ${hidden ? "off" : ""}" type="button" aria-pressed="${hidden ? "false" : "true"}" data-line-strategy="${esc(strategy)}">
          <span class="legend-swatch" style="background:${colorForStrategy(strategy)}"></span>
          <span>${esc(strategy)}</span>
        </button>`;
      }).join("");

      legendHost.querySelectorAll("[data-line-strategy]").forEach(button => {
        button.addEventListener("click", () => {
          const strategy = button.dataset.lineStrategy;
          state.hiddenSeries[strategy] = !state.hiddenSeries[strategy];
          renderInteractiveLineChart(getFilteredRows());
        });
      });

      if (!strategies.length) {
        chartHost.innerHTML = `<div class="empty-state">没有曲线可画。</div>`;
        return;
      }

      const seriesMap = new Map(strategies.map(strategy => [strategy, parsedSeries(strategy, seriesByStrategy)]));
      const visibleStrategies = strategies.filter(strategy => !state.hiddenSeries[strategy] && (seriesMap.get(strategy) || []).length);
      if (!visibleStrategies.length) {
        chartHost.innerHTML = `<div class="empty-state">全部曲线已隐藏。</div>`;
        return;
      }

      const allPoints = visibleStrategies.flatMap(strategy => seriesMap.get(strategy));
      const xValues = allPoints.map(point => point.t);
      const yValues = allPoints.map(point => point.v);
      let minX = Math.min(...xValues);
      let maxX = Math.max(...xValues);
      let minY = Math.min(...yValues);
      let maxY = Math.max(...yValues);

      if (minX === maxX) {
        minX -= 86400000;
        maxX += 86400000;
      }
      if (state.curveMode === "equity") {
        minY = Math.max(0, minY * 0.96);
        maxY = maxY * 1.04;
      } else if (state.curveMode === "drawdown") {
        minY = Math.min(minY * 1.08, minY - 0.01);
        maxY = 0;
      } else {
        const yPad = Math.max(0.02, (maxY - minY) * 0.08);
        minY -= yPad;
        maxY += yPad;
      }
      if (minY === maxY) {
        minY -= 0.01;
        maxY += 0.01;
      }

      const width = 1380;
      const height = 640;
      const pad = { left: 90, right: 34, top: 34, bottom: 56 };
      const innerW = width - pad.left - pad.right;
      const innerH = height - pad.top - pad.bottom;
      const xScale = value => pad.left + (value - minX) / (maxX - minX) * innerW;
      const yScale = value => height - pad.bottom - (value - minY) / (maxY - minY) * innerH;
      const yTicks = Array.from({ length: 6 }, (_, index) => minY + (maxY - minY) * index / 5);
      const xTicks = Array.from({ length: 6 }, (_, index) => minX + (maxX - minX) * index / 5);
      const modeLabel = curveModeOptions.find(([value]) => value === state.curveMode)?.[1] || "曲线";

      const yGrid = yTicks.map(value => {
        const y = yScale(value);
        return `<g>
          <line class="line-grid" x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" />
          <text class="axis-label" x="${pad.left - 12}" y="${y + 4}" text-anchor="end">${esc(fmtCurveValue(value))}</text>
        </g>`;
      }).join("");
      const xGrid = xTicks.map(value => {
        const x = xScale(value);
        return `<g>
          <line class="line-grid" x1="${x}" y1="${pad.top}" x2="${x}" y2="${height - pad.bottom}" />
          <text class="axis-label" x="${x}" y="${height - 20}" text-anchor="middle">${esc(fmtDate(value))}</text>
        </g>`;
      }).join("");

      const paths = visibleStrategies.map(strategy => {
        const points = seriesMap.get(strategy);
        const d = points.map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(point.t).toFixed(2)} ${yScale(point.v).toFixed(2)}`).join(" ");
        const last = points[points.length - 1];
        const color = colorForStrategy(strategy);
        return `<g data-line-strategy="${esc(strategy)}">
          <path class="line-path" d="${d}" stroke="${color}" stroke-width="${strategy === state.selected ? 3.2 : 2.2}" opacity="${strategy === state.selected ? 0.98 : 0.82}">
            <title>${esc(strategy)} · ${esc(modeLabel)} · ${esc(fmtCurveValue(last.v))}</title>
          </path>
          <circle cx="${xScale(last.t)}" cy="${yScale(last.v)}" r="${strategy === state.selected ? 4.4 : 3.2}" fill="${color}" stroke="white" stroke-width="1.5">
            <title>${esc(strategy)} · ${esc(fmtCurveValue(last.v))}</title>
          </circle>
        </g>`;
      }).join("");

      chartHost.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="策略${esc(modeLabel)}曲线">
        ${yGrid}
        ${xGrid}
        <line class="line-axis" x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" />
        <line class="line-axis" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" />
        <text class="axis-label" x="${pad.left}" y="20">${esc(modeLabel)}</text>
        ${paths}
      </svg>`;

      chartHost.querySelectorAll("[data-line-strategy]").forEach(group => {
        group.addEventListener("click", () => {
          state.selected = group.dataset.lineStrategy;
          sync();
        });
      });
    }

    function renderBarChart(rows) {
      const host = document.getElementById("barChart");
      if (!rows.length) {
        host.innerHTML = `<div class="empty-state">没有数据可画。</div>`;
        return;
      }
      const key = state.chartMetric;
      const sorted = [...rows].sort((a, b) => Number(b[key] ?? -Infinity) - Number(a[key] ?? -Infinity));
      const width = 1380;
      const rowH = 38;
      const top = 26;
      const left = 280;
      const right = 116;
      const height = top + sorted.length * rowH + 28;
      const values = sorted.map(row => Number(row[key] ?? 0));
      const min = Math.min(0, ...values);
      const max = Math.max(...values);
      const span = Math.max(0.0001, max - min);
      const axisX = left + (0 - min) / span * (width - left - right);
      const type = metricFormatFor(key);
      const bars = sorted.map((row, index) => {
        const value = Number(row[key] ?? 0);
        const y = top + index * rowH;
        const xValue = left + (value - min) / span * (width - left - right);
        const x = Math.min(axisX, xValue);
        const barW = Math.max(3, Math.abs(xValue - axisX));
        const color = value >= 0 ? "var(--accent)" : "var(--red)";
        const selectedClass = row.Strategy === state.selected ? `stroke="var(--ink)" stroke-width="2"` : "";
        return `<g role="button" tabindex="0" data-strategy="${esc(row.Strategy)}">
          <text class="bar-label" x="14" y="${y + 23}">${esc(row.Strategy)}</text>
          <rect x="${x}" y="${y + 8}" width="${barW}" height="21" rx="6" fill="${color}" ${selectedClass}></rect>
          <text class="bar-value" x="${Math.max(xValue, axisX) + 10}" y="${y + 24}">${esc(fmtMetric(value, type))}</text>
        </g>`;
      }).join("");
      host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="策略排行图">
        <line x1="${axisX}" y1="12" x2="${axisX}" y2="${height - 14}" stroke="var(--line)" />
        ${bars}
      </svg>`;
      host.querySelectorAll("[data-strategy]").forEach(group => {
        group.addEventListener("click", () => {
          state.selected = group.dataset.strategy;
          sync();
        });
      });
    }

    function renderScatter(rows) {
      const host = document.getElementById("scatterChart");
      if (!rows.length) {
        host.innerHTML = `<div class="empty-state">没有数据可画。</div>`;
        return;
      }
      const width = 1280;
      const height = 640;
      const pad = { left: 76, right: 36, top: 42, bottom: 66 };
      const xs = rows.map(row => Number(row.Volatility ?? 0));
      const ys = rows.map(row => Number(row.CAGR ?? 0));
      const minX = Math.max(0, Math.min(...xs) * 0.88);
      const maxX = Math.max(...xs) * 1.08;
      const minY = Math.min(0, Math.min(...ys) * 0.9);
      const maxY = Math.max(...ys) * 1.12;
      const xScale = value => pad.left + (value - minX) / Math.max(0.0001, maxX - minX) * (width - pad.left - pad.right);
      const yScale = value => height - pad.bottom - (value - minY) / Math.max(0.0001, maxY - minY) * (height - pad.top - pad.bottom);
      const xTicks = Array.from({ length: 5 }, (_, index) => minX + (maxX - minX) * index / 4);
      const yTicks = Array.from({ length: 5 }, (_, index) => minY + (maxY - minY) * index / 4);
      const grid = [
        ...xTicks.map(value => `<g><line class="line-grid" x1="${xScale(value)}" y1="${pad.top}" x2="${xScale(value)}" y2="${height - pad.bottom}" /><text class="axis-label" x="${xScale(value)}" y="${height - 24}" text-anchor="middle">${fmtPct(value)}</text></g>`),
        ...yTicks.map(value => `<g><line class="line-grid" x1="${pad.left}" y1="${yScale(value)}" x2="${width - pad.right}" y2="${yScale(value)}" /><text class="axis-label" x="${pad.left - 12}" y="${yScale(value) + 4}" text-anchor="end">${fmtPct(value)}</text></g>`)
      ].join("");
      const points = rows.map(row => {
        const drawdown = Math.abs(Number(row["Max Drawdown"] ?? 0));
        const radius = 8 + Math.min(18, Math.max(0, Number(row["Final Equity"] ?? 0) / 10000000));
        const color = drawdown > 0.65 ? "var(--red)" : drawdown > 0.5 ? "var(--orange)" : "var(--accent)";
        const selected = row.Strategy === state.selected;
        return `<g role="button" tabindex="0" data-strategy="${esc(row.Strategy)}">
          <circle cx="${xScale(Number(row.Volatility ?? 0))}" cy="${yScale(Number(row.CAGR ?? 0))}" r="${selected ? radius + 2 : radius}" fill="${color}" opacity="${selected ? 0.96 : 0.72}" stroke="${selected ? "var(--ink)" : "white"}" stroke-width="${selected ? 2 : 1.5}">
            <title>${esc(row.Strategy)} · 年化 ${fmtPct(row.CAGR)} · 波动 ${fmtPct(row.Volatility)} · 回撤 ${fmtPct(row["Max Drawdown"])}</title>
          </circle>
          ${selected ? `<text class="point-label" x="${xScale(Number(row.Volatility ?? 0)) + 14}" y="${yScale(Number(row.CAGR ?? 0)) - 12}">${esc(row.Strategy)}</text>` : ""}
        </g>`;
      }).join("");
      host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="风险收益散点图">
        ${grid}
        <line class="line-axis" x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" />
        <line class="line-axis" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" />
        <text class="axis-label" x="${width / 2 - 36}" y="${height - 12}">波动率</text>
        <text class="axis-label" x="20" y="24">年化收益</text>
        ${points}
      </svg>`;
      host.querySelectorAll("[data-strategy]").forEach(group => {
        group.addEventListener("click", () => {
          state.selected = group.dataset.strategy;
          sync();
        });
      });
    }

    function renderHeatmap(rows) {
      const host = document.getElementById("heatmap");
      if (!rows.length) {
        host.innerHTML = `<div class="empty-state">没有数据可展示。</div>`;
        return;
      }
      const periods = ["1Y CAGR", "3Y CAGR", "5Y CAGR", "7Y CAGR", "10Y CAGR"];
      const values = rows.flatMap(row => periods.map(period => Number(row[period] ?? 0)));
      const min = Math.min(...values);
      const max = Math.max(...values);
      const colorFor = value => {
        const t = (Number(value ?? 0) - min) / Math.max(0.0001, max - min);
        const light = 94 - t * 28;
        const sat = 32 + t * 26;
        return `hsl(158, ${sat}%, ${light}%)`;
      };
      const header = `<div class="heat-row">
        <div class="heat-cell heat-head heat-name">策略</div>
        ${periods.map(period => `<div class="heat-cell heat-head">${period.replace(" CAGR", "")}</div>`).join("")}
      </div>`;
      const body = rows.map(row => `<div class="heat-row">
        <button class="heat-cell heat-name" type="button" data-strategy="${esc(row.Strategy)}">${esc(row.Strategy)}</button>
        ${periods.map(period => `<div class="heat-cell" style="background:${colorFor(row[period])}">${fmtPct(row[period])}</div>`).join("")}
      </div>`).join("");
      host.innerHTML = header + body;
      host.querySelectorAll("[data-strategy]").forEach(button => {
        button.addEventListener("click", () => {
          state.selected = button.dataset.strategy;
          sync();
        });
      });
    }

    function renderImages() {
      const tabs = document.getElementById("imageTabs");
      tabs.innerHTML = REPORT_META.chartImages.map((image, index) => (
        `<button class="metric-chip ${state.imageIndex === index ? "active" : ""}" type="button" data-image-index="${index}">${esc(image.label)}</button>`
      )).join("");
      tabs.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.imageIndex = Number(button.dataset.imageIndex);
          renderImages();
        });
      });
      const image = REPORT_META.chartImages[state.imageIndex] || REPORT_META.chartImages[0];
      const element = document.getElementById("chartImage");
      element.src = image.src;
      element.alt = image.label;
    }

    function sync() {
      state.view = getViewFromHash();
      const rows = getFilteredRows();
      if (state.selected && !rows.some(row => row.Strategy === state.selected)) {
        state.selected = rows[0]?.Strategy || null;
      }
      renderControls(rows);
      syncView();
      renderInteractiveLineChart(rows);
      renderBarChart(rows);
      renderScatter(rows);
      renderHeatmap(rows);
      renderImages();
    }

    function resetFilters() {
      state.filter = "all";
      state.search = "";
      state.minCagr = 0;
      state.maxDrawdown = 0.9;
      state.beatQqq = false;
      state.betterDd = false;
      state.hiddenSeries = {};
      document.getElementById("searchInput").value = "";
      document.getElementById("minCagr").value = "0";
      document.getElementById("maxDrawdown").value = "90";
      document.getElementById("beatQqqToggle").checked = false;
      document.getElementById("betterDdToggle").checked = false;
      sync();
    }

    function bindInputs() {
      document.getElementById("searchInput").addEventListener("input", event => {
        state.search = event.target.value;
        sync();
      });
      document.getElementById("minCagr").addEventListener("input", event => {
        state.minCagr = Number(event.target.value) / 100;
        sync();
      });
      document.getElementById("maxDrawdown").addEventListener("input", event => {
        state.maxDrawdown = Number(event.target.value) / 100;
        sync();
      });
      document.getElementById("beatQqqToggle").addEventListener("change", event => {
        state.beatQqq = event.target.checked;
        sync();
      });
      document.getElementById("betterDdToggle").addEventListener("change", event => {
        state.betterDd = event.target.checked;
        sync();
      });
      document.getElementById("resetFilters").addEventListener("click", resetFilters);
      window.addEventListener("hashchange", sync);
    }

    if (!location.hash) {
      history.replaceState(null, "", "#curves");
    }
    renderMeta();
    bindInputs();
    sync();
  </script>
</body>
</html>
"""
