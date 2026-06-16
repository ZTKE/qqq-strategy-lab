from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.backtest import BacktestResult
from src.metrics import performance_summary, rolling_period_performance, yearly_returns


ROLLING_YEARS = (1, 3, 5, 7, 10)


def generate_report(
    results: list[BacktestResult],
    reports_dir: str | Path,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    transaction_cost: float,
) -> pd.DataFrame:
    reports_path = Path(reports_dir)
    charts_path = reports_path / "charts"
    charts_path.mkdir(parents=True, exist_ok=True)

    rows, rolling_by_strategy = _build_results_rows(results)
    results_frame = pd.DataFrame(rows)
    results_frame.to_csv(reports_path / "results.csv", index=False)

    _plot_equity_curves(results, charts_path / "equity_curves.png")
    _plot_drawdowns(results, charts_path / "drawdowns.png")
    _plot_rolling_returns(results, charts_path / "rolling_returns.png")

    summary = _build_markdown_summary(
        results=results,
        results_frame=results_frame,
        rolling_by_strategy=rolling_by_strategy,
        start_date=start_date,
        end_date=end_date,
        transaction_cost=transaction_cost,
    )
    (reports_path / "summary.md").write_text(summary, encoding="utf-8")
    return results_frame


def _build_results_rows(results: list[BacktestResult]) -> tuple[list[dict], dict[str, dict]]:
    rows = []
    rolling_by_strategy = {}
    for result in results:
        rolling = rolling_period_performance(result.performance_curve, ROLLING_YEARS)
        rolling_by_strategy[result.strategy_name] = rolling
        row = {
            "Strategy": result.strategy_name,
            "Start Date": result.equity_curve.index[0].date().isoformat(),
            "End Date": result.equity_curve.index[-1].date().isoformat(),
            "Required Assets": ", ".join(result.metadata.get("required_assets", [])),
            "Total Return": result.metrics.get("total_return"),
            "CAGR": result.metrics.get("cagr"),
            "Max Drawdown": result.metrics.get("max_drawdown"),
            "Volatility": result.metrics.get("annualized_volatility"),
            "Sharpe": result.metrics.get("sharpe_ratio"),
            "Calmar": result.metrics.get("calmar_ratio"),
            "Final Equity": result.metrics.get("final_equity"),
            "Total Invested": result.metrics.get("total_invested", np.nan),
        }
        for year, summary in rolling.items():
            row[f"{year}Y Total Return"] = summary["total_return"]
            row[f"{year}Y CAGR"] = summary["cagr"]
            row[f"{year}Y MaxDD"] = summary["max_drawdown"]
            row[f"{year}Y Volatility"] = summary["annualized_volatility"]
            row[f"{year}Y Sharpe"] = summary["sharpe_ratio"]
            row[f"{year}Y Calmar"] = summary["calmar_ratio"]
        rows.append(row)
    return rows, rolling_by_strategy


def _build_markdown_summary(
    results: list[BacktestResult],
    results_frame: pd.DataFrame,
    rolling_by_strategy: dict[str, dict],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    transaction_cost: float,
) -> str:
    strategy_names = [result.strategy_name for result in results]
    benchmark = results_frame.loc[results_frame["Strategy"] == "qqq_buy_hold"]
    if benchmark.empty:
        benchmark = results_frame.iloc[[0]]
    benchmark_row = benchmark.iloc[0]
    first_meta = results[0].metadata if results else {}
    initial_capital = float(first_meta.get("initial_capital", 20000.0))
    monthly_contribution = float(first_meta.get("monthly_contribution", 3000.0))

    lines = [
        "# QQQ 策略实验室报告",
        "",
        "## 1. 回测说明",
        "",
        "- 数据来源：yfinance 复权价格，缓存于 `data/raw`。",
        f"- 数据覆盖区间：{start_date.date()} 至 {end_date.date()}。",
        "- 所有策略尽量从 2000 年开始；如果某个 ETF 当时还没有价格数据，对应目标仓位会暂时保留为现金，直到该 ETF 有可用价格。",
        "- 再平衡频率：每月一次，使用当月最后一个交易日的信号。",
        f"- 资金口径：所有策略初始投入 {_fmt_money(initial_capital)}，之后每月追加 {_fmt_money(monthly_contribution)}。",
        f"- 交易成本：成交金额的 {transaction_cost:.4%}。",
        "- 收益率、CAGR、回撤、波动率和夏普比率使用现金流调整后的收益曲线计算；最终净值为真实账户资产。",
        f"- 策略：{', '.join(strategy_names)}。",
        "- 重要提示：历史回测不代表未来收益。",
        "",
        "## 2. 策略概览",
        "",
        _overview_table(results_frame),
        "",
        "## 3. 关键数据结论",
        "",
        *_key_findings_lines(results_frame),
        "",
        "## 4. 策略实现方法",
        "",
        *_strategy_method_lines(results),
        "",
        "## 5. 最近 1/3/5/7/10 年表现",
        "",
        _rolling_table(results_frame),
        "",
        "## 6. 相对 QQQ 的表现",
        "",
        _relative_table(results),
        "",
        "## 7. 年度收益",
        "",
        _yearly_returns_table(results),
        "",
        "## 8. 策略解读",
        "",
        *_interpretation(results_frame, benchmark_row),
        "",
        "## 9. 图表",
        "",
        "![净值曲线](charts/equity_curves.png)",
        "",
        "![回撤曲线](charts/drawdowns.png)",
        "",
        "![滚动收益](charts/rolling_returns.png)",
        "",
        "## 10. 数据充足性",
        "",
        _data_sufficiency_note(rolling_by_strategy),
    ]
    return "\n".join(lines) + "\n"


def _overview_table(frame: pd.DataFrame) -> str:
    headers = ["策略", "起始日期", "总收益", "年化收益率", "最大回撤", "波动率", "夏普比率", "Calmar 比率", "最终净值", "总投入本金"]
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            [
                row["Strategy"],
                row["Start Date"],
                _fmt_pct(row["Total Return"]),
                _fmt_pct(row["CAGR"]),
                _fmt_pct(row["Max Drawdown"]),
                _fmt_pct(row["Volatility"]),
                _fmt_num(row["Sharpe"]),
                _fmt_num(row["Calmar"]),
                _fmt_money(row["Final Equity"]),
                _fmt_money(row["Total Invested"]),
            ]
        )
    return _markdown_table(headers, rows)


def _key_findings_lines(frame: pd.DataFrame) -> list[str]:
    clean = frame.copy()
    benchmark = clean.loc[clean["Strategy"] == "qqq_buy_hold"]
    benchmark_row = benchmark.iloc[0] if not benchmark.empty else clean.iloc[0]

    best_final = clean.loc[clean["Final Equity"].idxmax()]
    best_cagr = clean.loc[clean["CAGR"].idxmax()]
    lowest_drawdown = clean.loc[clean["Max Drawdown"].idxmax()]
    best_calmar = clean.loc[clean["Calmar"].idxmax()]
    best_risk_adjusted = best_calmar
    best_1y = clean.loc[clean["1Y CAGR"].idxmax()]
    best_3y = clean.loc[clean["3Y CAGR"].idxmax()]
    best_5y = clean.loc[clean["5Y CAGR"].idxmax()]
    best_10y = clean.loc[clean["10Y CAGR"].idxmax()]

    rows = [
        [
            "最终账户资产最高",
            best_final["Strategy"],
            f"{_fmt_money(best_final['Final Equity'])}；总收益 {_fmt_pct(best_final['Total Return'])}",
            "回答“最后账户里最多是多少钱”。",
        ],
        [
            "现金流调整年化最高",
            best_cagr["Strategy"],
            _fmt_pct(best_cagr["CAGR"]),
            "回答“同样持续投入下，收益路径效率最高是谁”。",
        ],
        [
            "最大回撤最低",
            lowest_drawdown["Strategy"],
            _fmt_pct(lowest_drawdown["Max Drawdown"]),
            "回答“历史最难熬时，账户从高点跌了多少”。",
        ],
        [
            "风险调整最好",
            best_risk_adjusted["Strategy"],
            f"Sharpe {_fmt_num(best_risk_adjusted['Sharpe'])}；Calmar {_fmt_num(best_risk_adjusted['Calmar'])}",
            "夏普看单位波动收益，Calmar 看收益与最大回撤的关系。",
        ],
        [
            "近 1/3/5 年最强",
            f"{best_1y['Strategy']} / {best_3y['Strategy']} / {best_5y['Strategy']}",
            f"{_fmt_pct(best_1y['1Y CAGR'])} / {_fmt_pct(best_3y['3Y CAGR'])} / {_fmt_pct(best_5y['5Y CAGR'])}",
            "回答“最近这轮行情谁最强”。",
        ],
        [
            "近 10 年最强",
            best_10y["Strategy"],
            _fmt_pct(best_10y["10Y CAGR"]),
            "回答“中长期牛市里谁最能吃到上涨”。",
        ],
    ]

    benchmark_maxdd = float(benchmark_row["Max Drawdown"])
    benchmark_cagr = float(benchmark_row["CAGR"])
    drawdown_improvement = float(best_risk_adjusted["Max Drawdown"]) - benchmark_maxdd
    cagr_advantage = float(best_risk_adjusted["CAGR"]) - benchmark_cagr

    drawdown_buy = clean.loc[clean["Strategy"] == "drawdown_buy"]
    lines = [
        "这部分是建议优先看的数据：终值看财富结果，CAGR 看资金效率，最大回撤看心理压力，夏普和 Calmar 看风险调整后表现。",
        "",
        _markdown_table(["你关心的问题", "当前答案", "关键数据", "怎么看"], rows),
        "",
        "核心判断：",
        f"- 如果只追求最终账户金额，`{best_final['Strategy']}` 最高，最终净值为 {_fmt_money(best_final['Final Equity'])}。",
        f"- 如果看收益和回撤的综合表现，`{best_risk_adjusted['Strategy']}` 最突出：年化 {_fmt_pct(best_risk_adjusted['CAGR'])}，比 QQQ 高 {_fmt_pct(cagr_advantage)}；最大回撤 {_fmt_pct(best_risk_adjusted['Max Drawdown'])}，比 QQQ 少跌约 {_fmt_pct(drawdown_improvement)}。",
        f"- `trend_200dma` 是更简单的风控基准：年化 {_fmt_pct(_value_for(clean, 'trend_200dma', 'CAGR'))}，最大回撤 {_fmt_pct(_value_for(clean, 'trend_200dma', 'Max Drawdown'))}，比纯 QQQ 少承受很多深跌。",
        f"- `core_trend` 更像折中方案：保留 QQQ 核心仓位，最终净值 {_fmt_money(_value_for(clean, 'core_trend', 'Final Equity'))}，但最大回撤仍有 {_fmt_pct(_value_for(clean, 'core_trend', 'Max Drawdown'))}。",
    ]
    if not drawdown_buy.empty:
        row = drawdown_buy.iloc[0]
        lines.append(
            f"- `drawdown_buy` 当前结果不理想：年化 {_fmt_pct(row['CAGR'])}，最大回撤 {_fmt_pct(row['Max Drawdown'])}，"
            f"没有比 QQQ 买入持有提供更好的风险收益交换。"
        )

    return lines


def _value_for(frame: pd.DataFrame, strategy_name: str, column: str):
    match = frame.loc[frame["Strategy"] == strategy_name]
    if match.empty:
        return np.nan
    return match.iloc[0][column]


def _strategy_method_lines(results: list[BacktestResult]) -> list[str]:
    lines = [
        "- 所有策略统一使用现金流：首日投入初始资金，之后每月追加固定资金。",
        "- 非 DCA 策略在月末最后一个交易日根据当时可见的历史价格生成目标权重，新的持仓和当月追加资金从下一个交易日开始生效，并按换手金额扣除交易成本。",
        "- DCA 策略按月投入现金：普通月份投入固定月供，触发回撤增强规则时只调整新增资金的买入权重，月供仍保持固定金额；为了简化，买入按当日收盘价执行。",
    ]
    for result in results:
        config = result.metadata.get("config", {})
        lines.append(f"- `{result.strategy_name}`：{_strategy_method_text(config)}")
    return lines


def _strategy_method_text(config: dict) -> str:
    strategy_type = config.get("type")
    if strategy_type == "buy_and_hold":
        return f"买入并长期持有目标组合，目标权重为 {_format_weights(config.get('weights', {}))}。"
    if strategy_type == "static_allocation":
        return f"每月把组合再平衡回固定目标权重：{_format_weights(config.get('weights', {}))}。"
    if strategy_type == "trend_200dma":
        signal_asset = config.get("signal_asset", "信号资产")
        ma_window = int(config.get("ma_window", 200))
        return (
            f"用 `{signal_asset}` 的 {ma_window} 日均线做趋势过滤；如果月末收盘价高于均线，"
            f"使用风险开启权重 {_format_weights(config.get('risk_on', {}))}；否则切换到风险关闭权重 {_format_weights(config.get('risk_off', {}))}。"
        )
    if strategy_type == "core_trend":
        signal_asset = config.get("signal_asset", "信号资产")
        ma_window = int(config.get("ma_window", 200))
        core_asset = config.get("core_asset", "核心资产")
        core_weight = float(config.get("core_weight", 0.0))
        tactical_weight = float(config.get("tactical_weight", 0.0))
        risk_on_asset = config.get("risk_on_asset", "风险资产")
        risk_off_asset = config.get("risk_off_asset", "防守资产")
        return (
            f"保留 {_fmt_pct(core_weight)} 的 `{core_asset}` 核心仓位，另外 {_fmt_pct(tactical_weight)} 作为趋势仓位；"
            f"当 `{signal_asset}` 月末收盘价高于 {ma_window} 日均线时，趋势仓位买入 `{risk_on_asset}`，否则买入 `{risk_off_asset}`。"
        )
    if strategy_type == "drawdown_buy":
        signal_asset = config.get("signal_asset", "信号资产")
        return f"计算 `{signal_asset}` 相对历史最高价的回撤，回撤越深越提高进攻资产配置；分档规则为 {_format_drawdown_rules(config.get('rules', []))}。"
    if strategy_type == "momentum_rotation":
        assets = ", ".join(f"`{asset}`" for asset in config.get("assets", []))
        lookback_months = int(config.get("lookback_months", 6))
        top_n = int(config.get("top_n", 2))
        ma_window = int(config.get("ma_window", 200))
        fallback_asset = config.get("fallback_asset", "SHY")
        return (
            f"在候选资产 {assets} 中，先剔除月末收盘价低于 {ma_window} 日均线的资产；"
            f"再按过去 {lookback_months} 个月收益率排序，等权持有前 {top_n} 名。若没有资产通过趋势过滤，则持有 `{fallback_asset}`。"
        )
    if strategy_type == "dca":
        initial_capital = float(config.get("initial_capital", 0.0))
        monthly_contribution = float(config.get("monthly_contribution", 0.0))
        signal_asset = config.get("signal_asset", "信号资产")
        return (
            f"首日投入 {_fmt_money(initial_capital)}，之后每月投入 {_fmt_money(monthly_contribution)}；"
            f"正常按 {_format_weights(config.get('normal_weights', {}))} 买入，"
            f"并根据 `{signal_asset}` 回撤调整买入权重：{_format_dca_rules(config.get('rules', []))}。"
        )
    return "使用配置文件中定义的策略类型和参数生成月度目标权重。"


def _format_weights(weights: dict) -> str:
    if not weights:
        return "未配置"
    normalized = {asset: float(weight) for asset, weight in weights.items()}
    return " / ".join(f"`{asset}` {_fmt_pct(weight)}" for asset, weight in normalized.items())


def _format_drawdown_rules(rules: list[dict]) -> str:
    if not rules:
        return "未配置"
    parts = []
    for rule in rules:
        threshold = float(rule.get("drawdown_lt", 0.0))
        parts.append(f"回撤 < {_fmt_pct(threshold)} 时配置 {_format_weights(rule.get('weights', {}))}")
    return "；".join(parts)


def _format_dca_rules(rules: list[dict]) -> str:
    if not rules:
        return "未配置"
    parts = []
    for rule in rules:
        threshold = float(rule.get("drawdown_gte", 0.0))
        parts.append(f"回撤 >= {_fmt_pct(threshold)} 时配置 {_format_weights(rule.get('weights', {}))}")
    return "；".join(parts)


def _rolling_table(frame: pd.DataFrame) -> str:
    headers = [
        "策略",
        "1 年年化收益",
        "3 年年化收益",
        "5 年年化收益",
        "7 年年化收益",
        "10 年年化收益",
        "1 年最大回撤",
        "3 年最大回撤",
        "5 年最大回撤",
        "10 年最大回撤",
    ]
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            [
                row["Strategy"],
                _fmt_pct(row["1Y CAGR"]),
                _fmt_pct(row["3Y CAGR"]),
                _fmt_pct(row["5Y CAGR"]),
                _fmt_pct(row["7Y CAGR"]),
                _fmt_pct(row["10Y CAGR"]),
                _fmt_pct(row["1Y MaxDD"]),
                _fmt_pct(row["3Y MaxDD"]),
                _fmt_pct(row["5Y MaxDD"]),
                _fmt_pct(row["10Y MaxDD"]),
            ]
        )
    return _markdown_table(headers, rows)


def _relative_table(results: list[BacktestResult]) -> str:
    headers = ["策略", "年化收益率相对 QQQ 差值", "最大回撤相对 QQQ 差值", "夏普比率相对 QQQ 差值"]
    benchmark = next((result for result in results if result.strategy_name == "qqq_buy_hold"), None)
    rows = []
    for result in results:
        if benchmark is None:
            cagr_diff = maxdd_diff = sharpe_diff = np.nan
        elif result.strategy_name == benchmark.strategy_name:
            cagr_diff = maxdd_diff = sharpe_diff = 0.0
        else:
            benchmark_window = benchmark.performance_curve.loc[
                result.performance_curve.index[0] : result.performance_curve.index[-1]
            ]
            if len(benchmark_window) < 2:
                cagr_diff = maxdd_diff = sharpe_diff = np.nan
            else:
                benchmark_metrics = performance_summary(benchmark_window, benchmark_window.pct_change().dropna())
                cagr_diff = result.metrics["cagr"] - benchmark_metrics["cagr"]
                maxdd_diff = result.metrics["max_drawdown"] - benchmark_metrics["max_drawdown"]
                sharpe_diff = result.metrics["sharpe_ratio"] - benchmark_metrics["sharpe_ratio"]
        rows.append(
            [
                result.strategy_name,
                _fmt_pct(cagr_diff),
                _fmt_pct(maxdd_diff),
                _fmt_num(sharpe_diff),
            ]
        )
    return _markdown_table(headers, rows)


def _yearly_returns_table(results: list[BacktestResult]) -> str:
    yearly = {}
    for result in results:
        yearly[result.strategy_name] = yearly_returns(result.performance_curve)
    frame = pd.DataFrame(yearly).sort_index()
    headers = ["年份", *frame.columns.to_list()]
    rows = []
    for year, row in frame.iterrows():
        rows.append([str(year), *[_fmt_pct(value) for value in row]])
    return _markdown_table(headers, rows)


def _interpretation(frame: pd.DataFrame, benchmark_row: pd.Series) -> list[str]:
    clean = frame.copy()
    best_return = clean.loc[clean["Total Return"].idxmax(), "Strategy"]
    lowest_drawdown = clean.loc[clean["Max Drawdown"].idxmax(), "Strategy"]
    sharpe_frame = clean.dropna(subset=["Sharpe"])
    best_sharpe = sharpe_frame.loc[sharpe_frame["Sharpe"].idxmax(), "Strategy"] if not sharpe_frame.empty else "N/A"

    candidates = clean[
        (clean["Strategy"] != benchmark_row["Strategy"])
        & (clean["Max Drawdown"] > benchmark_row["Max Drawdown"])
    ].copy()
    if candidates.empty:
        closest_lower_drawdown = "本次回测中，没有策略同时做到接近 QQQ 的年化收益率和更低回撤。"
    else:
        candidates["cagr_gap_abs"] = (candidates["CAGR"] - benchmark_row["CAGR"]).abs()
        closest = candidates.loc[candidates["cagr_gap_abs"].idxmin()]
        closest_lower_drawdown = f"{closest['Strategy']} 的年化收益率最接近 QQQ，同时回撤更低。"

    trend = clean.loc[clean["Strategy"] == "trend_200dma"]
    if not trend.empty:
        trend_gap = float(trend.iloc[0]["CAGR"] - benchmark_row["CAGR"])
        trend_note = "趋势模型的年化收益率落后于 QQQ，可能存在来回止损或错过上涨行情的问题。" if trend_gap < 0 else "本次回测中，趋势模型的年化收益率没有落后于 QQQ。"
    else:
        trend_note = "趋势模型结果不可用。"

    drawdown_buy = clean.loc[clean["Strategy"] == "drawdown_buy"]
    if not drawdown_buy.empty:
        gap = float(drawdown_buy.iloc[0]["CAGR"] - benchmark_row["CAGR"])
        drawdown_note = "回撤买入模型的年化收益率追平或超过了 QQQ。" if gap >= 0 else "在本次回测中，回撤买入模型没有追上 QQQ 的年化收益率。"
    else:
        drawdown_note = "回撤买入模型结果不可用。"

    return [
        f"- 总收益最高：{best_return}。",
        f"- 最大回撤最低：{lowest_drawdown}。",
        f"- 夏普比率最高：{best_sharpe}。",
        f"- {closest_lower_drawdown}",
        f"- {trend_note}",
        f"- {drawdown_note}",
        "- 所有策略都包含相同的初始资金和月度追加资金；总收益按最终净值除以总投入本金再减一计算。",
    ]


def _data_sufficiency_note(rolling_by_strategy: dict[str, dict]) -> str:
    missing = []
    for strategy, periods in rolling_by_strategy.items():
        for year, summary in periods.items():
            if pd.isna(summary["cagr"]):
                missing.append(f"{strategy}: {year}Y")
    if not missing:
        return "所有请求的滚动周期都有足够的可用数据。"
    return "以下周期数据不足：" + ", ".join(missing) + "。"


def _plot_equity_curves(results: list[BacktestResult], output_path: Path) -> None:
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 7))
    for result in results:
        plt.plot(result.equity_curve.index, result.equity_curve.values, label=result.strategy_name, linewidth=1.5)
    plt.title("Equity Curves")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.legend(fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def _plot_drawdowns(results: list[BacktestResult], output_path: Path) -> None:
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 7))
    for result in results:
        curve = result.performance_curve
        drawdown = curve / curve.cummax() - 1.0
        plt.plot(drawdown.index, drawdown.values, label=result.strategy_name, linewidth=1.2)
    plt.title("Drawdowns")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.legend(fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def _plot_rolling_returns(results: list[BacktestResult], output_path: Path) -> None:
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 7))
    for result in results:
        rolling = result.performance_curve / result.performance_curve.shift(252) - 1.0
        plt.plot(rolling.index, rolling.values, label=result.strategy_name, linewidth=1.1)
    plt.title("Rolling 1Y Returns")
    plt.xlabel("Date")
    plt.ylabel("Return")
    plt.legend(fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _fmt_pct(value) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2%}"


def _fmt_num(value) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2f}"


def _fmt_money(value) -> str:
    if pd.isna(value):
        return "N/A"
    return f"${float(value):,.2f}"
