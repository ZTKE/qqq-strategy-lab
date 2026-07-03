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
| Long simulation from requested 1970 start | 1971-02-05 | 2026-07-02 | 55.42 | 12.94% | 38.81% | 23.06% | -15.76% | 6.29% | -16.77% | 7.21% | -5.73% | N/A | N/A | -82.96% | -99.96% | -99.98% | -99.98% | N/A |
| Real TQQQ overlap | 2010-02-11 | 2026-07-02 | 16.35 | 19.66% | 58.98% | 50.43% | -8.55% | 39.09% | -11.34% | 43.23% | 23.57% | 43.23% | 4.14% | -35.12% | -80.29% | -81.92% | -81.66% | -81.66% |

## Series Metrics

| Window | Series | Start Date | End Date | Years | Total Return | CAGR | Max Drawdown | Volatility | Worst Daily Return | Final Multiple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Long simulation from requested 1970 start | QQQ | 1971-02-05 | 2026-07-02 | 55.42 | 84739.39% | 12.94% | -82.96% | 22.77% | -15.08% | 848.39 |
| Long simulation from requested 1970 start | QQQ Daily 3x Gross | 1971-02-05 | 2026-07-02 | 55.42 | 9871000.68% | 23.06% | -99.96% | 68.30% | -45.23% | 98711.01 |
| Long simulation from requested 1970 start | QQQ Daily 3x Cost Model | 1971-02-05 | 2026-07-02 | 55.42 | 2837.33% | 6.29% | -99.98% | 68.31% | -45.31% | 29.37 |
| Long simulation from requested 1970 start | TQQQ-like Stitched | 1971-02-05 | 2026-07-02 | 55.42 | 4643.08% | 7.21% | -99.98% | 68.09% | -45.31% | 47.43 |
| Real TQQQ overlap | QQQ | 2010-02-11 | 2026-07-02 | 16.35 | 1782.08% | 19.66% | -35.12% | 20.66% | -11.98% | 18.82 |
| Real TQQQ overlap | QQQ Daily 3x Gross | 2010-02-11 | 2026-07-02 | 16.35 | 79298.89% | 50.43% | -80.29% | 61.99% | -35.94% | 793.99 |
| Real TQQQ overlap | QQQ Daily 3x Cost Model | 2010-02-11 | 2026-07-02 | 16.35 | 21944.93% | 39.09% | -81.92% | 61.98% | -35.96% | 220.45 |
| Real TQQQ overlap | Real TQQQ | 2010-02-11 | 2026-07-02 | 16.35 | 35497.24% | 43.23% | -81.66% | 61.16% | -34.47% | 355.97 |
| Real TQQQ overlap | TQQQ-like Stitched | 2010-02-11 | 2026-07-02 | 16.35 | 35497.24% | 43.23% | -81.66% | 61.16% | -34.47% | 355.97 |
