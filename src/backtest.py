from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.calendar_utils import daily_signal_dates, monthly_last_trading_days, rebalance_signal_dates
from src.metrics import performance_summary
from src.strategies.base import Strategy


@dataclass
class BacktestResult:
    strategy_name: str
    equity_curve: pd.Series
    performance_curve: pd.Series
    daily_returns: pd.Series
    weights_history: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float]
    metadata: dict = field(default_factory=dict)


class BacktestEngine:
    def __init__(
        self,
        prices: pd.DataFrame,
        initial_capital: float = 20000.0,
        monthly_contribution: float = 1000.0,
        transaction_cost: float = 0.0005,
    ):
        self.prices = prices.sort_index().ffill().dropna(how="all")
        self.initial_capital = float(initial_capital)
        self.monthly_contribution = float(monthly_contribution)
        self.transaction_cost = float(transaction_cost)
        if self.prices.empty:
            raise ValueError("Prices are empty.")

    def run(self, strategy: Strategy) -> BacktestResult:
        if getattr(strategy, "is_dca", False):
            return self._run_dca(strategy)
        return self._run_rebalanced(strategy)

    def _run_rebalanced(self, strategy: Strategy) -> BacktestResult:
        index = self.prices.index
        monthly_dates = set(monthly_last_trading_days(index))
        first_date = index[0]
        frequency = str(strategy.config.get("rebalance_frequency", "monthly")).lower()
        if frequency == "daily":
            signal_dates = daily_signal_dates(index, include_first=True)
        elif frequency == "monthly":
            signal_dates = rebalance_signal_dates(index, include_first=True)
        else:
            raise ValueError(f"Unsupported rebalance_frequency for {strategy.name}: {frequency}")
        scheduled_weights = {
            date: self._validate_weights(strategy.generate_weights(self.prices, date))
            for date in signal_dates
        }

        shares = {asset: 0.0 for asset in self.prices.columns}
        cash = self.initial_capital
        total_invested = self.initial_capital
        contributions = []
        equity_values = []
        weights_rows = []
        trades = []

        for position, date in enumerate(index):
            contribution = 0.0
            if position > 0:
                previous_date = index[position - 1]
                if previous_date in scheduled_weights:
                    if previous_date in monthly_dates and previous_date != first_date:
                        contribution = self.monthly_contribution
                        cash += contribution
                        total_invested += contribution

                    new_weights = scheduled_weights[previous_date]
                    available_weights = self._available_weights(new_weights, date)
                    cash_weight = max(0.0, 1.0 - sum(available_weights.values()))
                    portfolio_value = self._portfolio_value(shares, date) + cash
                    current_values = {
                        asset: self._asset_value(shares, date, asset)
                        for asset in self.prices.columns
                    }
                    target_values = {
                        asset: portfolio_value * float(available_weights.get(asset, 0.0))
                        for asset in self.prices.columns
                    }
                    turnover_notional = sum(
                        abs(target_values[asset] - current_values[asset])
                        for asset in self.prices.columns
                    )
                    cost = turnover_notional * self.transaction_cost
                    investable_value = portfolio_value - cost
                    for asset in self.prices.columns:
                        price = self._price_at(date, asset)
                        target_value = investable_value * float(available_weights.get(asset, 0.0))
                        shares[asset] = target_value / price if target_value > 0 and pd.notna(price) else 0.0
                    cash = investable_value * cash_weight
                    trades.append(
                        {
                            "signal_date": previous_date,
                            "effective_date": date,
                            "contribution": contribution,
                            "turnover_notional": turnover_notional,
                            "turnover": turnover_notional / portfolio_value if portfolio_value > 0 else 0.0,
                            "cost": cost,
                            "weights": dict(new_weights),
                            "cash_weight": cash_weight,
                        }
                    )

            equity = self._portfolio_value(shares, date) + cash
            equity_values.append(equity)
            contributions.append(contribution)
            weights_rows.append(self._share_weights(shares, date, equity))

        equity_curve = pd.Series(equity_values, index=index, name=strategy.name)
        contribution_series = pd.Series(contributions, index=index, name="contribution")
        daily_returns = self._cashflow_adjusted_returns(equity_curve, contribution_series)
        performance_curve = self._return_index(daily_returns, self.initial_capital, strategy.name)
        weights_history = pd.DataFrame(weights_rows, index=index).fillna(0.0)
        trades_frame = pd.DataFrame(trades)
        metrics = performance_summary(performance_curve, daily_returns)
        metrics["total_invested"] = total_invested
        metrics["total_return"] = equity_curve.iloc[-1] / total_invested - 1.0 if total_invested > 0 else float("nan")
        metrics["final_equity"] = float(equity_curve.iloc[-1])

        return BacktestResult(
            strategy_name=strategy.name,
            equity_curve=equity_curve,
            performance_curve=performance_curve,
            daily_returns=daily_returns,
            weights_history=weights_history,
            trades=trades_frame,
            metrics=metrics,
            metadata={
                "initial_capital": self.initial_capital,
                "monthly_contribution": self.monthly_contribution,
                "transaction_cost": self.transaction_cost,
                "mode": "rebalanced",
                "total_invested": total_invested,
                "config": dict(strategy.config),
            },
        )

    def _run_dca(self, strategy: Strategy) -> BacktestResult:
        index = self.prices.index
        monthly_dates = set(monthly_last_trading_days(index))
        first_date = index[0]
        shares = {asset: 0.0 for asset in self.prices.columns}
        cash = 0.0
        total_invested = 0.0
        contributions = []
        equity_values = []
        weights_rows = []
        trades = []

        for date in index:
            contribution = 0.0
            if date == first_date:
                contribution = float(strategy.config.get("initial_capital", self.initial_capital))
            elif date in monthly_dates and date != index[-1]:
                contribution = float(strategy.config.get("monthly_contribution", self.monthly_contribution))

            if contribution > 0:
                plan = strategy.contribution_plan(self.prices, date)
                weights = self._validate_weights(plan["weights"])
                available_weights = self._available_weights(weights, date)
                available_weight_sum = sum(available_weights.values())
                cash_weight = max(0.0, 1.0 - available_weight_sum)
                cost = contribution * available_weight_sum * self.transaction_cost
                # DCA buys at the signal-date close for simplicity, matching the first-version assumption.
                for asset, weight in available_weights.items():
                    investable = contribution * weight * (1.0 - self.transaction_cost)
                    shares[asset] += investable / float(self.prices.loc[date, asset])
                cash += contribution * cash_weight
                total_invested += contribution
                trades.append(
                    {
                        "signal_date": date,
                        "effective_date": date,
                        "contribution": contribution,
                        "cost": cost,
                        "weights": dict(weights),
                        "cash_weight": cash_weight,
                        "drawdown": plan.get("drawdown"),
                        "configured_multiplier": plan.get("contribution_multiplier"),
                    }
                )

            equity = self._portfolio_value(shares, date) + cash
            equity_values.append(equity)
            contributions.append(contribution)
            weights_rows.append(self._share_weights(shares, date, equity))

        equity_curve = pd.Series(equity_values, index=index, name=strategy.name)
        contribution_series = pd.Series(contributions, index=index, name="contribution")
        daily_returns = self._cashflow_adjusted_returns(equity_curve, contribution_series)
        performance_curve = self._return_index(daily_returns, self.initial_capital, strategy.name)
        weights_history = pd.DataFrame(weights_rows, index=index).fillna(0.0)
        trades_frame = pd.DataFrame(trades)
        metrics = performance_summary(performance_curve, daily_returns)
        metrics["total_invested"] = total_invested
        metrics["total_return"] = equity_curve.iloc[-1] / total_invested - 1.0 if total_invested > 0 else float("nan")
        metrics["dca_simplified_return"] = metrics["total_return"]
        metrics["final_equity"] = float(equity_curve.iloc[-1])

        return BacktestResult(
            strategy_name=strategy.name,
            equity_curve=equity_curve,
            performance_curve=performance_curve,
            daily_returns=daily_returns,
            weights_history=weights_history,
            trades=trades_frame,
            metrics=metrics,
            metadata={
                "initial_capital": float(strategy.config.get("initial_capital", self.initial_capital)),
                "monthly_contribution": float(strategy.config.get("monthly_contribution", 0.0)),
                "transaction_cost": self.transaction_cost,
                "mode": "dca",
                "total_invested": total_invested,
                "config": dict(strategy.config),
            },
        )

    def _validate_weights(self, weights: dict[str, float]) -> dict[str, float]:
        missing = sorted(set(weights) - set(self.prices.columns))
        if missing:
            raise ValueError(f"Weights reference assets missing from prices: {missing}")
        return weights

    def _weights_row(self, weights: dict[str, float]) -> dict[str, float]:
        return {asset: float(weights.get(asset, 0.0)) for asset in self.prices.columns}

    def _share_weights(self, shares: dict[str, float], date: pd.Timestamp, equity: float) -> dict[str, float]:
        if equity <= 0:
            return {asset: 0.0 for asset in self.prices.columns}
        return {
            asset: self._asset_value(shares, date, asset) / equity
            for asset in self.prices.columns
        }

    def _portfolio_value(self, shares: dict[str, float], date: pd.Timestamp) -> float:
        return sum(self._asset_value(shares, date, asset) for asset in self.prices.columns)

    def _asset_value(self, shares: dict[str, float], date: pd.Timestamp, asset: str) -> float:
        share_count = float(shares.get(asset, 0.0))
        if share_count == 0.0:
            return 0.0
        price = self._price_at(date, asset)
        if pd.isna(price):
            raise ValueError(f"Missing price for held asset {asset} on {date.date()}.")
        return share_count * float(price)

    def _available_weights(self, weights: dict[str, float], date: pd.Timestamp) -> dict[str, float]:
        return {
            asset: float(weight)
            for asset, weight in weights.items()
            if asset in self.prices.columns and pd.notna(self._price_at(date, asset))
        }

    def _price_at(self, date: pd.Timestamp, asset: str) -> float:
        return self.prices.loc[date, asset]

    @staticmethod
    def _cashflow_adjusted_returns(equity_curve: pd.Series, contributions: pd.Series) -> pd.Series:
        previous_equity = equity_curve.shift(1)
        returns = (equity_curve - previous_equity - contributions) / previous_equity
        returns.iloc[0] = 0.0
        return returns.replace([float("inf"), float("-inf")], 0.0).fillna(0.0)

    @staticmethod
    def _return_index(daily_returns: pd.Series, initial_value: float, name: str) -> pd.Series:
        return (1.0 + daily_returns).cumprod().mul(float(initial_value)).rename(name)
