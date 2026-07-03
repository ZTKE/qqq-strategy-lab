# TQQQ vs QQQ Leverage Drag Analysis

This report separates real TQQQ history from a long TQQQ-like simulation.
The requested long start was 1970-01-01; the effective start is the first available QQQ/proxy date.

Definitions:

- QQQ: QQQ after inception, stitched to Nasdaq proxy history before QQQ existed.
- QQQ Daily 3x Gross: daily 3x QQQ/proxy returns with no financing, fee, or tracking drag.
- QQQ Daily 3x Cost Model: daily 3x QQQ/proxy returns after the configured financing, fee, and tracking assumptions.
- TQQQ-like Stitched: simulated before TQQQ has prices, then real TQQQ prices after they are available.
- Real TQQQ: actual adjusted TQQQ prices on the overlap window only.

## Drag Summary

| Window | Start Date | End Date | Years | QQQ CAGR | 3x QQQ CAGR (Naive) | Daily 3x Gross CAGR | Volatility Drag vs Naive 3x | Cost Model 3x CAGR | Cost Drag vs Gross Daily 3x | TQQQ-like CAGR | TQQQ-like CAGR Gap vs QQQ | Real TQQQ CAGR | Real TQQQ Gap vs Cost Model | QQQ Max Drawdown | Daily 3x Gross Max Drawdown | Cost Model 3x Max Drawdown | TQQQ-like Max Drawdown | Real TQQQ Max Drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Long simulation from requested 1970 start | 1971-02-05 | 2026-07-01 | 55.42 | 12.97% | 38.92% | 23.18% | -15.74% | 6.39% | -16.79% | 7.32% | -5.66% | N/A | N/A | -82.96% | -99.96% | -99.98% | -99.98% | N/A |
| Real TQQQ overlap | 2010-02-11 | 2026-07-01 | 16.35 | 19.79% | 59.38% | 50.93% | -8.44% | 39.56% | -11.37% | 43.72% | 23.92% | 43.72% | 4.16% | -35.12% | -80.29% | -81.92% | -81.66% | -81.66% |

## Series Metrics

| Window | Series | Start Date | End Date | Years | Total Return | CAGR | Max Drawdown | Volatility | Worst Daily Return | Final Multiple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Long simulation from requested 1970 start | QQQ | 1971-02-05 | 2026-07-01 | 55.42 | 86235.93% | 12.97% | -82.96% | 22.77% | -15.08% | 863.36 |
| Long simulation from requested 1970 start | QQQ Daily 3x Gross | 1971-02-05 | 2026-07-01 | 55.42 | 10412471.37% | 23.18% | -99.96% | 68.30% | -45.23% | 104125.71 |
| Long simulation from requested 1970 start | QQQ Daily 3x Cost Model | 1971-02-05 | 2026-07-01 | 55.42 | 3000.04% | 6.39% | -99.98% | 68.31% | -45.31% | 31.00 |
| Long simulation from requested 1970 start | TQQQ-like Stitched | 1971-02-05 | 2026-07-01 | 55.42 | 4908.85% | 7.32% | -99.98% | 68.09% | -45.31% | 50.09 |
| Real TQQQ overlap | QQQ | 2010-02-11 | 2026-07-01 | 16.35 | 1815.28% | 19.79% | -35.12% | 20.66% | -11.98% | 19.15 |
| Real TQQQ overlap | QQQ Daily 3x Gross | 2010-02-11 | 2026-07-01 | 16.35 | 83654.24% | 50.93% | -80.29% | 61.98% | -35.94% | 837.54 |
| Real TQQQ overlap | QQQ Daily 3x Cost Model | 2010-02-11 | 2026-07-01 | 16.35 | 23166.10% | 39.56% | -81.92% | 61.98% | -35.96% | 232.66 |
| Real TQQQ overlap | Real TQQQ | 2010-02-11 | 2026-07-01 | 16.35 | 37491.85% | 43.72% | -81.66% | 61.16% | -34.47% | 375.92 |
| Real TQQQ overlap | TQQQ-like Stitched | 2010-02-11 | 2026-07-01 | 16.35 | 37491.85% | 43.72% | -81.66% | 61.16% | -34.47% | 375.92 |
