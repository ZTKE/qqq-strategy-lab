# QQQ 策略实验室

这是一个轻量级 Python 研究项目，用同一个月度回测引擎比较长期 QQQ/Nasdaq 相关 ETF 策略。

本项目仅用于研究和回测。它不会下单，不会连接券商 API，也不构成投资建议。历史结果不代表未来收益。

默认资金口径：所有策略首日投入 20000 美元，之后每月追加 3000 美元。收益率、CAGR、回撤、波动率和夏普比率使用现金流调整后的收益曲线计算，最终净值展示真实账户资产。

## 安装

```bat
cd /d D:\qqq-strategy-lab
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行回测

```bat
cd /d D:\qqq-strategy-lab
python -m src.main
```

可选参数：

```bat
python -m src.main --start 2000-01-01 --force-refresh
```

`run.bat` 会执行默认命令。

## 运行测试

```bat
cd /d D:\qqq-strategy-lab
pytest
```

## 策略

- `qqq_buy_hold`：100% 持有 QQQ。
- `qqq_80_spy_20`：每月再平衡，80% QQQ / 20% SPY。
- `qqq_70_spy_20_shy_10`：每月再平衡，70% QQQ / 20% SPY / 10% SHY。
- `trend_200dma`：基于 QQQ 200 日均线的风险控制策略。
- `core_trend`：60% 核心 QQQ 仓位，加 40% 趋势策略仓位。
- `drawdown_buy`：QQQ 回撤越深，越提高 QQQ 配置比例。
- `momentum_rotation`：选择 6 个月动量最强的前 2 个资产，并叠加 200 日均线趋势过滤。
- `dca_drawdown_boost`：月度定投策略，在回撤期间提高新增资金中 QQQ 的买入比例。

## 输出文件

- `reports/results.csv`：汇总指标和滚动周期指标。
- `reports/summary.md`：Markdown 格式报告。
- `reports/charts/equity_curves.png`：净值曲线。
- `reports/charts/drawdowns.png`：回撤曲线。
- `reports/charts/rolling_returns.png`：滚动一年收益率。

## 数据

价格数据来自 yfinance，使用复权价格，并缓存到 `data/raw`。如果 yfinance 下载失败且对应 ticker 的 CSV 已经存在，数据加载器会回退使用本地缓存。合并并对齐后的价格会保存到 `data/processed/prices.csv`。

回测默认从 2000 年开始。由于 SHY、GLD 等 ETF 在 2000 年尚未全部上市，如果某个 ETF 在当时没有价格数据，对应目标仓位会暂时保留为现金，直到该 ETF 有可用价格。

## 防止使用未来数据的规则

策略在计算移动均线、历史高点、回撤或动量之前，只会截取截至当前信号日的历史价格。再平衡类策略在月末收盘时生成信号，并从下一个交易日开始应用新的持仓和当月追加资金。为了让第一版实现更简单，DCA 策略会在月末收盘价买入。
