"""GATE 1: is the Kalshi market already calibrated at 72/24/6h before close?
Also checks Kalshi's recorded expiration_value against the NWS CLI high (settlement-source check).
Usage: python eval/gate1_calibration.py KXHIGHCHI 400 KMDW"""
import sys, re, numpy as np, pandas as pd
sys.path.insert(0, ".")
from ingest.kalshi import settled_markets, candles
from ingest.iem import get_cli
series, n, cli_site = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ms = settled_markets(series)
print("settled markets fetched:", len(ms))
ms = ms[-n:]
# --- settlement-source check: expiration_value vs CLI high
cli = pd.concat([get_cli(cli_site, y) for y in (2025, 2026)]).set_index("valid")["high"]
chk = []
for m in ms:
    d = re.search(r"-(\d\d)([A-Z]{3})(\d\d)", m["ticker"])
    if not d or not m.get("expiration_value"): continue
    date = pd.to_datetime(f"20{d[1]} {d[2]} {d[3]}", format="%Y %b %d").strftime("%Y-%m-%d")
    if date in cli.index: chk.append((date, float(m["expiration_value"]), cli[date]))
c = pd.DataFrame(chk, columns=["date", "kalshi_exp_value", "cli_high"]).drop_duplicates("date")
c["diff"] = c.kalshi_exp_value - c.cli_high
print(f"\nSETTLEMENT CHECK n={len(c)} days: exact match {(c['diff']==0).mean():.3f}; within 1F {(c['diff'].abs()<=1).mean():.3f}")
print(c["diff"].value_counts().sort_index().to_string())
# --- calibration
def px(cs):
    for k in reversed(cs):
        p = k.get("price", {})
        v = p.get("close_dollars") or p.get("previous_dollars")
        if v is not None: return float(v)
rows = []
for m in ms:
    close = pd.Timestamp(m["close_time"]).timestamp()
    y = 1 if m.get("result") == "yes" else 0
    for h in (72, 24, 6):
        t = int(close - h * 3600)
        p = px(candles(series, m["ticker"], t - 86400, t))
        if p is not None: rows.append((m["ticker"], h, p, y))
df = pd.DataFrame(rows, columns=["ticker", "h", "p", "y"])
df["bin"] = pd.cut(df.p, [-.001, .05, .15, .35, .65, .85, .95, 1]).astype(str)
for h, g in df.groupby("h"):
    print(f"\n--- {h}h before close | n={len(g)} | Brier={((g.p-g.y)**2).mean():.4f}")
    print(g.groupby("bin").agg(n=("y", "size"), implied=("p", "mean"), realised=("y", "mean")).to_string())
df.to_parquet(f"data/gate1_{series}.parquet")
