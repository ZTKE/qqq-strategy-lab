import pandas as pd

from src.leverage_analysis import build_tqqq_qqq_analysis, write_tqqq_qqq_analysis


def _sample_prices() -> pd.DataFrame:
    dates = pd.bdate_range("1971-02-05", periods=320)
    qqq = pd.Series([100.0 * (1.001 ** index) for index in range(len(dates))], index=dates)
    tqqq = pd.Series(index=dates, dtype=float)
    tqqq.iloc[120:] = [10.0 * (1.003 ** index) for index in range(len(dates) - 120)]
    qqq_3x = pd.Series([100.0 * (1.003 ** index) for index in range(len(dates))], index=dates)
    return pd.DataFrame({"QQQ": qqq, "TQQQ": tqqq, "QQQ_3X": qqq_3x})


def test_tqqq_qqq_analysis_separates_long_simulation_and_real_overlap():
    series_metrics, drag_summary = build_tqqq_qqq_analysis(
        _sample_prices(),
        requested_start="1970-01-01",
    )

    assert set(drag_summary["Window"]) == {
        "Long simulation from requested 1970 start",
        "Real TQQQ overlap",
    }
    assert set(series_metrics["Series"]).issuperset(
        {
            "QQQ",
            "QQQ Daily 3x Gross",
            "QQQ Daily 3x Cost Model",
            "TQQQ-like Stitched",
            "Real TQQQ",
        }
    )

    long_window = drag_summary.loc[drag_summary["Window"] == "Long simulation from requested 1970 start"].iloc[0]
    real_window = drag_summary.loc[drag_summary["Window"] == "Real TQQQ overlap"].iloc[0]

    assert long_window["Start Date"] == "1971-02-05"
    assert real_window["Start Date"] == "1971-07-23"
    assert pd.notna(real_window["Real TQQQ Gap vs Cost Model"])


def test_write_tqqq_qqq_analysis_outputs_csv_and_markdown(tmp_path):
    write_tqqq_qqq_analysis(_sample_prices(), tmp_path, requested_start="1970-01-01")

    assert (tmp_path / "tqqq_qqq_series_metrics.csv").exists()
    assert (tmp_path / "tqqq_qqq_drag_summary.csv").exists()
    assert (tmp_path / "tqqq_qqq_analysis.md").exists()
