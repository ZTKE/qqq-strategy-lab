import pandas as pd

from src.data_loader import DataLoader


def test_cached_prices_respect_requested_date_range(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    pd.DataFrame(
        {
            "Date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"]),
            "Close": [100.0, 101.0, 102.0],
        }
    ).to_csv(raw_dir / "QQQ.csv", index=False)

    loader = DataLoader(raw_dir)
    prices = loader.load_prices(["QQQ"], start="2020-01-03", end="2020-01-03")

    assert list(prices.index) == [pd.Timestamp("2020-01-03")]
    assert prices.loc[pd.Timestamp("2020-01-03"), "QQQ"] == 101.0


def test_cached_prices_do_not_update_when_requested_end_is_covered(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    pd.DataFrame(
        {
            "Date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "Close": [100.0, 101.0],
        }
    ).to_csv(raw_dir / "QQQ.csv", index=False)

    loader = DataLoader(raw_dir)

    def fail_download(*args, **kwargs):
        raise AssertionError("download should not be called")

    monkeypatch.setattr(loader, "_download", fail_download)
    prices = loader.load_prices(["QQQ"], start="2020-01-02", end="2020-01-03")

    assert list(prices.index) == [pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03")]


def test_cached_prices_incrementally_update_when_end_is_open(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    pd.DataFrame(
        {
            "Date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "Close": [100.0, 101.0],
        }
    ).to_csv(raw_dir / "QQQ.csv", index=False)

    loader = DataLoader(raw_dir)
    calls = []

    def fake_download(ticker, start, end):
        calls.append((ticker, start, end))
        return pd.Series(
            [101.5, 102.0],
            index=pd.to_datetime(["2020-01-03", "2020-01-06"]),
            name=ticker,
        )

    monkeypatch.setattr(loader, "_download", fake_download)
    prices = loader.load_prices(["QQQ"], start="2020-01-02", end=None)
    cached = pd.read_csv(raw_dir / "QQQ.csv", parse_dates=["Date"])

    assert calls == [("QQQ", "2019-12-27", None)]
    assert prices.index.max() == pd.Timestamp("2020-01-06")
    assert cached["Date"].max() == pd.Timestamp("2020-01-06")
