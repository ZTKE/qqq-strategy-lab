import pandas as pd

from src.calendar_utils import monthly_last_trading_days


def test_monthly_last_trading_days():
    index = pd.to_datetime(
        [
            "2024-01-02",
            "2024-01-31",
            "2024-02-01",
            "2024-02-28",
            "2024-03-01",
        ]
    )
    result = monthly_last_trading_days(index)
    expected = pd.to_datetime(["2024-01-31", "2024-02-28", "2024-03-01"])
    assert list(result) == list(expected)
