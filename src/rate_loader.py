from __future__ import annotations

from pathlib import Path

import pandas as pd


class FredRateLoader:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def load_rates(
        self,
        series_ids: list[str],
        start: str = "2000-01-01",
        end: str | None = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        rates = {}
        errors = {}
        for series_id in sorted(set(series_ids)):
            try:
                rates[series_id] = self._load_one(series_id, start, end, force_refresh)
            except Exception as exc:
                errors[series_id] = str(exc)

        if not rates:
            if errors:
                print(f"Warning: no FRED rates loaded: {errors}")
            return pd.DataFrame()

        frame = pd.concat(rates.values(), axis=1).sort_index()
        frame = frame.ffill().dropna(how="all")
        if errors:
            print(f"Warning: some FRED rates failed and were skipped: {errors}")
        return frame

    def _load_one(self, series_id: str, start: str, end: str | None, force_refresh: bool) -> pd.Series:
        cache_path = self.raw_dir / f"{series_id}.csv"
        if cache_path.exists() and not force_refresh:
            cached = self._read_cache(cache_path, series_id)
            cached = self._filter_date_range(cached, start, end)
            if not cached.empty:
                return cached

        try:
            downloaded = self._download(series_id)
            downloaded.to_frame(series_id).to_csv(cache_path, index_label="Date")
            return self._filter_date_range(downloaded, start, end)
        except Exception:
            if cache_path.exists():
                cached = self._read_cache(cache_path, series_id)
                cached = self._filter_date_range(cached, start, end)
                if not cached.empty:
                    print(f"Warning: FRED download failed for {series_id}; using cached CSV.")
                    return cached
            raise

    def _read_cache(self, cache_path: Path, series_id: str) -> pd.Series:
        data = pd.read_csv(cache_path, parse_dates=["Date"], index_col="Date")
        if series_id in data.columns:
            series = data[series_id]
        elif "Value" in data.columns:
            series = data["Value"]
        else:
            series = data.iloc[:, 0]
        series = self._normalize_rate_units(pd.to_numeric(series, errors="coerce").dropna())
        series.name = series_id
        return series

    def _normalize_rate_units(self, series: pd.Series) -> pd.Series:
        if series.empty:
            return series
        # Project-written caches store decimal rates; raw FRED values are percentage points.
        if series.abs().max() > 1.0:
            return series / 100.0
        return series

    def _filter_date_range(self, series: pd.Series, start: str, end: str | None) -> pd.Series:
        output = series.loc[series.index >= pd.Timestamp(start)]
        if end:
            output = output.loc[output.index <= pd.Timestamp(end)]
        return output

    def _download(self, series_id: str) -> pd.Series:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        data = pd.read_csv(url, parse_dates=["observation_date"])
        if series_id not in data.columns:
            raise RuntimeError(f"FRED response missing column {series_id}.")
        series = pd.to_numeric(data[series_id], errors="coerce").dropna() / 100.0
        series.index = pd.DatetimeIndex(data.loc[series.index, "observation_date"]).tz_localize(None)
        series.name = series_id
        return series
