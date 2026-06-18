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
