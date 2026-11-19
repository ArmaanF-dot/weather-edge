"""GATE 1: is the Kalshi market already calibrated at 72/24/6h before close?
Usage: python eval/gate1_calibration.py KXHIGHCHI
Buckets implied prob (last hourly candle close before t-H) vs realised YES rate. UNTESTED against live API (sandbox egress blocked)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
from ingest.kalshi import settled_markets, candles
series = sys.argv[1]
ms = settled_markets(series); rows = []
for m in ms:
    close = pd.Timestamp(m["close_time"]).timestamp()
    y = 1 if m.get("result") == "yes" else 0
    for h in (72, 24, 6):
        t = int(close - h * 3600)
        cs = candles(series, m["ticker"], t - 86400, t)
        px = [c["price"]["close"] for c in cs if c.get("price", {}).get("close") is not None]
        if px: rows.append((m["ticker"], h, px[-1] / 100, y))
df = pd.DataFrame(rows, columns=["ticker", "h", "p", "y"])
df["bin"] = pd.cut(df.p, [0, .05, .15, .35, .65, .85, .95, 1])
for h, g in df.groupby("h"):
    print(f"\n--- {h}h before close | n={len(g)} | Brier={((g.p-g.y)**2).mean():.4f}")
    print(g.groupby("bin", observed=True).agg(n=("y", "size"), implied=("p", "mean"), realised=("y", "mean")))
df.to_parquet(f"data/gate1_{series}.parquet")
