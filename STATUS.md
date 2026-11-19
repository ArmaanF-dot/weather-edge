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
