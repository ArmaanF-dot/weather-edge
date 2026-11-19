# Status (2026-11-19)
Phase 0 gates ran on GitHub Actions (workflow: phase0-gates; manual dispatch).

Gate 2 (METAR hourly max vs final CLI high, Chicago/NYC, 2024-25, ~730 days each):
- Cutoff 12:00 LST: mean gap +2.8F (p95 +7). 15:00: +0.9. 18:00: +0.7. 23:00: +0.6-0.7 (p95 +2).
- Even at end of day, hourly METAR misses the CLI max by >1F on ~8-9% of days (CLI uses finer-grained obs). Need 5-min/1-min ASOS data for the nowcast.

Gate 1 (Chicago, last 400 settled markets, ~67 days):
- Kalshi expiration_value == NWS CLI high on 67/67 days (settlement source confirmed in practice).
- "24h before close" (= ~1am local on the day): calibrated within noise; tails slightly overpriced (implied 9% vs realised 4%, n=71). Brier 0.094.
- CAVEAT: horizons are relative to close_time (07:00Z next day), so "6h" is after the day ends (meaningless) and 72h has no data (markets open ~2 days out). Redo at horizons relative to local day start.
