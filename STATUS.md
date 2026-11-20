# Status (2026-11-19)
Phase 0 gates ran on GitHub Actions (workflow: phase0-gates; manual dispatch).

Gate 2 (METAR hourly max vs final CLI high, Chicago/NYC, 2024-25, ~730 days each):
- Cutoff 12:00 LST: mean gap +2.8F (p95 +7). 15:00: +0.9. 18:00: +0.7. 23:00: +0.6-0.7 (p95 +2).
- Even at end of day, hourly METAR misses the CLI max by >1F on ~8-9% of days (CLI uses finer-grained obs). Need 5-min/1-min ASOS data for the nowcast.

Gate 1 (Chicago, last 400 settled markets, ~67 days):
- Kalshi expiration_value == NWS CLI high on 67/67 days (settlement source confirmed in practice).
- "24h before close" (= ~1am local on the day): calibrated within noise; tails slightly overpriced (implied 9% vs realised 4%, n=71). Brier 0.094.
- CAVEAT: horizons are relative to close_time (07:00Z next day), so "6h" is after the day ends (meaningless) and 72h has no data (markets open ~2 days out). Redo at horizons relative to local day start.

## Gate 1 v2 (2026-11-19, day-relative snapshots, market vs seasonal climatology)
Chicago (69 days) / NYC (68 days). Brier market vs climatology; skill = 1 - mkt/clim:
- D-1 09:00 LST: 0.104 vs 0.203 (skill 0.49), Chicago only (NYC markets open later)
- D 00:00: Chi 0.096 vs 0.204 (0.53) | NYC 0.082 vs 0.181 (0.55)
- D 09:00: Chi 0.092 (0.55) | NYC 0.079 (0.57)
- D 12:00: Chi 0.061 (0.70) | NYC 0.061 (0.66)
- D 15:00: Chi 0.018 (0.91) | NYC 0.035 (0.81)
Calibration looks good in the middle; cheap tails (<15%) slightly overpriced (Chi D 00:00: 9% implied vs 4% realised, n=71) - small sample.
Limits: only ~68 days (API default window; older data needs /historical endpoints); baseline is climatology only, so this shows the market is far better than naive, NOT whether a NWS/NBM/ECMWF-based model beats it. Next test: add NWS/NBM or ECMWF forecast baseline.

## Gate 3 (2026-11-19): EMOS(ECMWF+GFS) vs market at D 00:00 LST, ~68 days/station — NOT TRUSTWORTHY YET
- Chicago: Brier model 0.0775 vs market 0.0957; paper P&L +$0.19-0.30/contract after fees. NYC: model 0.0915 vs market 0.0817; P&L ~ +$0.02-0.06 (within noise).
- Chicago result is likely inflated: Open-Meteo "historical forecast" stitches short-lead hours from the latest runs (near-analysis), so it can leak same-day information. Must redo with true fixed-lead forecasts (Previous Runs API, hourly temperature_2m_previous_day1 -> LST-day max) before believing any edge.
- Price history: candles only exist for ~69 days; older (historical) markets returned no candles (1,986 of 2,400 markets had no price data). Real fix = start a daily snapshot collector now so a clean out-of-sample record accrues.
- Sample is tiny and brackets within a day are correlated (effective n ~ 69), so reported standard errors are understated.

## Gate 3 v2 (2026-11-20): leak-free day-1 forecasts (Open-Meteo Previous Runs, ECMWF+GFS mean, EMOS walk-forward)
At D 00:00 LST, ~69 days/station, model-only MAE vs CLI 2.4-2.5F:
- Chicago: Brier market 0.0957, model 0.1266, blend 0.1050. Paper P&L at edge>0.05..0.20: -$0.05 to -$0.07 per contract (after fees).
- NYC: Brier market 0.0817, model 0.1198, blend 0.0949. Paper P&L: -$0.09 to -$0.15 per contract.
- The earlier Gate 3 "Chicago edge" was forecast leakage; it disappears with fixed-lead forecasts. Model is over-dispersed on tails (5-15% bucket: model ~18-20% vs realised 1-5%).
- Verdict so far: a simple two-model day-ahead EMOS does NOT beat Kalshi at midnight. Market skill vs climatology is already 50%+ the day before and 80-90% by 15:00.
- Untested: NBM/NWS point forecasts, ensemble spread, ML residuals, intraday nowcast vs market at 09-12 LST, longer history (only ~69 priced days exist).
