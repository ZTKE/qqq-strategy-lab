import pandas as pd

from src.rate_loader import FredRateLoader


def test_cached_decimal_rates_are_not_scaled_again(tmp_path):
    raw_dir = tmp_path / "rates"
    raw_dir.mkdir()
    pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "SOFR": [0.0525, 0.0526],
        }
    ).to_csv(raw_dir / "SOFR.csv", index=False)

    loader = FredRateLoader(raw_dir)
    rates = loader.load_rates(["SOFR"], start="2024-01-02", end="2024-01-03")

    assert rates.loc[pd.Timestamp("2024-01-02"), "SOFR"] == 0.0525
    assert rates.loc[pd.Timestamp("2024-01-03"), "SOFR"] == 0.0526


def test_cached_percentage_point_rates_are_scaled_to_decimal(tmp_path):
    raw_dir = tmp_path / "rates"
    raw_dir.mkdir()
    pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "SOFR": [5.25, 5.26],
        }
    ).to_csv(raw_dir / "SOFR.csv", index=False)

    loader = FredRateLoader(raw_dir)
    rates = loader.load_rates(["SOFR"], start="2024-01-02", end="2024-01-03")

    assert rates.loc[pd.Timestamp("2024-01-02"), "SOFR"] == 0.0525
    assert rates.loc[pd.Timestamp("2024-01-03"), "SOFR"] == 0.0526
