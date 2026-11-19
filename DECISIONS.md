# Decisions
- D-001 Paper only. No order code, no trading keys (enforced by tests/test_no_orders.py).
- D-002 Phase 0 scope: 2 stations (Chicago, NYC), daily highs only, Kalshi settlement rules.
- D-003 Stations verified from Kalshi contract PDFs 2026-11-19: Chicago = Midway (CHIHIGH.pdf), NYC = Central Park (NHIGH.pdf). Settlement uses the most recent CLI available at expiration (first 7 or 8am ET after release); later revisions ignored. This corrects the earlier "first non-preliminary" assumption.
- D-004 Two gates decide whether to continue: market calibration at 72/24/6h; METAR-vs-CLI max gap.
