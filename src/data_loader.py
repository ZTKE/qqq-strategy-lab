from __future__ import annotations

from pathlib import Path

import pandas as pd


class DataLoader:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def load_prices(
        self,
        tickers: list[str],
        start: str = "2000-01-01",
        end: str | None = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        series_by_ticker = {}
        errors = {}

        for ticker in sorted(set(tickers)):
            try:
                series_by_ticker[ticker] = self._load_one(ticker, start, end, force_refresh)
            except Exception as exc:
                errors[ticker] = str(exc)

        if not series_by_ticker:
            raise RuntimeError(f"No price data could be loaded. Errors: {errors}")

        prices = pd.concat(series_by_ticker.values(), axis=1).sort_index()
        prices = prices.ffill().dropna(how="all")
        if prices.empty:
            raise RuntimeError(f"Loaded price data is empty after alignment. Errors: {errors}")

        processed_path = self.raw_dir.parent / "processed" / "prices.csv"
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        prices.to_csv(processed_path, index_label="Date")
        if errors:
            print(f"Warning: some tickers failed and were skipped: {errors}")
        return prices

    def _load_one(self, ticker: str, start: str, end: str | None, force_refresh: bool) -> pd.Series:
        cache_path = self.raw_dir / f"{ticker}.csv"
        if cache_path.exists() and not force_refresh:
            cached = self._read_cache(cache_path, ticker)
            if self._cache_covers_requested_end(cached, end):
                filtered = self._filter_date_range(cached, start, end)
                if not filtered.empty:
                    return filtered

            try:
                updated = self._update_cache(ticker, cached, cache_path, end)
                filtered = self._filter_date_range(updated, start, end)
                if not filtered.empty:
                    return filtered
            except Exception:
                filtered = self._filter_date_range(cached, start, end)
                if not filtered.empty:
                    print(f"Warning: yfinance update failed for {ticker}; using cached CSV through {cached.index.max().date()}.")
                    return filtered

        try:
            downloaded = self._download(ticker, start, end)
            downloaded.to_frame("Close").to_csv(cache_path, index_label="Date")
            return downloaded
        except Exception:
            if cache_path.exists():
                cached = self._read_cache(cache_path, ticker)
                cached = self._filter_date_range(cached, start, end)
                if not cached.empty:
                    print(f"Warning: yfinance failed for {ticker}; using cached CSV.")
                    return cached
            raise

    def _cache_covers_requested_end(self, cached: pd.Series, end: str | None) -> bool:
        if cached.empty:
            return False
        if end is None:
            return False
        return cached.index.max() >= pd.Timestamp(end)

    def _update_cache(self, ticker: str, cached: pd.Series, cache_path: Path, end: str | None) -> pd.Series:
        if cached.empty:
            downloaded = self._download(ticker, "1970-01-01", end)
            downloaded.to_frame("Close").to_csv(cache_path, index_label="Date")
            return downloaded

        old_last_date = cached.index.max()
        # Use a short overlap so late adjustments, holidays, or partial prior downloads are corrected.
        update_start = (old_last_date - pd.Timedelta(days=7)).date().isoformat()
        downloaded = self._download(ticker, update_start, end)
        combined = pd.concat([cached, downloaded]).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.name = ticker
        combined.to_frame("Close").to_csv(cache_path, index_label="Date")
        new_last_date = combined.index.max()
        if new_last_date > old_last_date:
            print(f"Updated {ticker}: {old_last_date.date()} -> {new_last_date.date()}")
        return combined

    def _read_cache(self, cache_path: Path, ticker: str) -> pd.Series:
        data = pd.read_csv(cache_path, parse_dates=["Date"], index_col="Date")
        if "Close" in data.columns:
            series = data["Close"]
        elif ticker in data.columns:
            series = data[ticker]
        else:
            series = data.iloc[:, 0]
        series = pd.to_numeric(series, errors="coerce").dropna()
        series.name = ticker
        return series

    def _filter_date_range(self, series: pd.Series, start: str, end: str | None) -> pd.Series:
        start_date = pd.Timestamp(start)
        output = series.loc[series.index >= start_date]
        if end:
            # User-facing end dates are inclusive; yfinance receives the equivalent exclusive date.
            output = output.loc[output.index <= pd.Timestamp(end)]
        return output

    def _download(self, ticker: str, start: str, end: str | None) -> pd.Series:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("yfinance is not installed. Run: pip install -r requirements.txt") from exc

        yfinance_end = None
        if end:
            yfinance_end = (pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat()

        data = yf.download(
            ticker,
            start=start,
            end=yfinance_end,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if data.empty:
            raise RuntimeError(f"yfinance returned no data for {ticker}.")

        if isinstance(data.columns, pd.MultiIndex):
            if ("Close", ticker) in data.columns:
                series = data[("Close", ticker)]
            else:
                close = data.xs("Close", axis=1, level=0)
                series = close.iloc[:, 0]
        elif "Close" in data.columns:
            series = data["Close"]
        elif "Adj Close" in data.columns:
            series = data["Adj Close"]
        else:
            raise RuntimeError(f"No Close column found for {ticker}.")

        series = pd.to_numeric(series, errors="coerce").dropna()
        series.index = pd.DatetimeIndex(series.index).tz_localize(None)
        series.name = ticker
        return series
