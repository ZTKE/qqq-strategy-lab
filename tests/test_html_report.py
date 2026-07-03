import pandas as pd

from src.html_report import CHART_PAGE_TEMPLATE, _month_end_sample, _strategy_tags


def test_tqqq_synthetic_tags_are_minimal_and_not_window_filters():
    tags = _strategy_tags("tqqq_synthetic_buy_hold", "QQQ_3X", {})

    assert "杠杆" in tags
    assert "全周期" not in tags
    assert "短历史" not in tags
    assert "TQQQ对比" not in tags
    assert "买入持有" not in tags


def test_real_tqqq_buy_hold_does_not_get_temporary_filter_tags():
    tags = _strategy_tags("real_tqqq_buy_hold_2010", "TQQQ", {})

    assert "杠杆" in tags
    assert "全周期" not in tags
    assert "短历史" not in tags
    assert "TQQQ对比" not in tags
    assert "买入持有" not in tags


def test_chart_page_requires_explicit_strategy_selection():
    assert "selectedStrategies: {}" in CHART_PAGE_TEMPLATE
    assert "renderInteractiveLineChart(candidateRows, selectedRows)" in CHART_PAGE_TEMPLATE
    assert "renderBarChart(selectedRows)" in CHART_PAGE_TEMPLATE
    assert "renderScatter(selectedRows)" in CHART_PAGE_TEMPLATE
    assert "renderHeatmap(selectedRows)" in CHART_PAGE_TEMPLATE
    assert "state.hiddenSeries" not in CHART_PAGE_TEMPLATE


def test_chart_page_has_period_and_cashflow_recalculation_controls():
    for control_id in ["paramStart", "paramEnd", "paramInitial", "paramMonthly", "runPeriod", "runCommand"]:
        assert f'id="{control_id}"' in CHART_PAGE_TEMPLATE

    assert "function runPeriodComputation()" in CHART_PAGE_TEMPLATE
    assert "let activeRows = baseRows" in CHART_PAGE_TEMPLATE
    assert "let activeSeries = REPORT_SERIES" in CHART_PAGE_TEMPLATE
    assert "seriesPayload()[state.curveMode]" in CHART_PAGE_TEMPLATE


def test_high_risk_strategies_are_tagged_and_styled_on_chart_page():
    tags = _strategy_tags("turbo_momentum_3x", "QQQ_3X", {"highRisk": True})

    assert "\u9ad8\u98ce\u9669" in tags
    assert "function riskClass(row)" in CHART_PAGE_TEMPLATE
    assert 'legend-item ${isSelected ? "on" : "off"} ${riskClass' in CHART_PAGE_TEMPLATE
    assert 'class="bar-label ${riskClass(row)}"' in CHART_PAGE_TEMPLATE
    assert 'class="point-label ${riskClass(row)}"' in CHART_PAGE_TEMPLATE
    assert 'class="heat-cell heat-name ${riskClass(row)}"' in CHART_PAGE_TEMPLATE


def test_month_end_sample_keeps_actual_last_date_for_partial_month():
    series = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.to_datetime(["2026-06-28", "2026-06-30", "2026-07-01"]),
    )

    sampled = _month_end_sample(series)

    assert sampled.index[-1] == pd.Timestamp("2026-07-01")
