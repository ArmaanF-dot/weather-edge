"""GATE 1 v2: market vs climatology at snapshots tied to the LOCAL standard-time day.
Snapshots (LST, event date D): D-1 09:00, D 00:00, D 09:00, D 12:00, D 15:00.
Usage: python eval/gate1_v2.py chicago 900"""
import sys, re, yaml, numpy as np, pandas as pd
sys.path.insert(0, ".")
from ingest.kalshi import settled_markets, candles
from ingest.iem import get_cli
name, n = sys.argv[1], int(sys.argv[2])
st = yaml.safe_load(open("config/stations.yaml"))["stations"][name]
off = st["lst_utc_offset_hours"]
ms = settled_markets(st["kalshi_series"])
print("settled fetched:", len(ms), "| sample keys:", sorted(ms[-1].keys())[:60])
ms = ms[-n:]
hist = []
for y in range(2012, 2027):
    try: hist.append(get_cli(st["cli_site"], y))
    except Exception as e: print("cli skip", y, e)
hist = pd.concat(hist).dropna(subset=["high"]); hist["d"] = pd.to_datetime(hist.valid)
hist["doy"] = hist.d.dt.dayofyear; hist["yr"] = hist.d.dt.year
def clim(date, test):
    doy = date.dayofyear
    h = hist[(hist.yr != date.year) & ((hist.doy - doy).abs() <= 7)].high
    return float(test(h).mean()) if len(h) else np.nan
def tester(m):
    t, fl, cp = m.get("strike_type"), m.get("floor_strike"), m.get("cap_strike")
    if t == "greater": return lambda h: h > fl
    if t == "less": return lambda h: h < cp
    if t == "between": return lambda h: (h >= fl) & (h <= cp)
    return None
def px(cs, t):
    best = None
    for k in cs:
        if k["end_period_ts"] <= t:
            p = k.get("price", {}); v = p.get("close_dollars") or p.get("previous_dollars")
            if v is None:
                b, a = k.get("yes_bid", {}).get("close_dollars"), k.get("yes_ask", {}).get("close_dollars")
                v = (float(b) + float(a)) / 2 if b and a else None
            if v is not None: best = float(v)
    return best
SNAPS = {"D-1 09:00": -15, "D 00:00": 0, "D 09:00": 9, "D 12:00": 12, "D 15:00": 15}
rows, skipped = [], 0
for m in ms:
    d = re.search(r"-(\d\d)([A-Z]{3})(\d\d)", m["ticker"]); te = tester(m)
    if not d or te is None or m.get("result") not in ("yes", "no"): skipped += 1; continue
    date = pd.to_datetime(f"20{d[1]} {d[2]} {d[3]}", format="%Y %b %d")
    d0 = int((date - pd.Timestamp("1970-01-01")).total_seconds()) - off * 3600   # UTC ts of local-day start
    cs = candles(st["kalshi_series"], m["ticker"], d0 - 16 * 3600, d0 + 16 * 3600)
    pc = clim(date, te); y = 1 if m["result"] == "yes" else 0
    for lab, hrs in SNAPS.items():
        p = px(cs, d0 + hrs * 3600)
        if p is not None and not np.isnan(pc): rows.append((m["ticker"], str(date.date()), lab, p, pc, y))
df = pd.DataFrame(rows, columns=["ticker", "date", "snap", "mkt", "clim", "y"])
print("skipped markets:", skipped, "| rows:", len(df), "| days:", df.date.nunique())
eps = 1e-3
def ll(p, y): p = np.clip(p, eps, 1 - eps); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
out = []
for s in SNAPS:
    g = df[df.snap == s]
    if g.empty: continue
    bm, bc = ((g.mkt - g.y) ** 2).mean(), ((g.clim - g.y) ** 2).mean()
    out.append((s, len(g), bm, bc, 1 - bm / bc, ll(g.mkt, g.y).mean(), ll(g.clim, g.y).mean()))
print("\n" + pd.DataFrame(out, columns=["snapshot", "n", "brier_mkt", "brier_clim", "skill_vs_clim", "logloss_mkt", "logloss_clim"]).round(4).to_string(index=False))
df["bin"] = pd.cut(df.mkt, [-.001, .05, .15, .35, .65, .85, .95, 1]).astype(str)
for s in ("D-1 09:00", "D 00:00", "D 12:00"):
    g = df[df.snap == s]
    if len(g): print(f"\n--- calibration @ {s}"); print(g.groupby("bin").agg(n=("y", "size"), implied=("mkt", "mean"), realised=("y", "mean")).round(3).to_string())
df.to_csv(f"data/gate1v2_{name}.csv", index=False)
