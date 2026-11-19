"""GATE 3 v2 (fixed-lead, leak-free): does a simple calibrated forecast model (EMOS on ECMWF+GFS day-ahead forecasts) beat the market at D 00:00 LST?
Walk-forward: mu/sigma fit only on days strictly before each target date. Paper P&L net of Kalshi taker fee.
Usage: python eval/gate3_model_vs_market.py chicago 2400"""
import sys, re, yaml, requests, numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, ".")
from ingest.kalshi import settled_markets, historical_markets, candles_any
from ingest.iem import get_cli
from rules.registry import kalshi_taker_fee
name, N = sys.argv[1], int(sys.argv[2])
st = yaml.safe_load(open("config/stations.yaml"))["stations"][name]; off = st["lst_utc_offset_hours"]
# markets
ms = {m["ticker"]: m for m in historical_markets(st["kalshi_series"])}
ms.update({m["ticker"]: m for m in settled_markets(st["kalshi_series"])})
ms = sorted(ms.values(), key=lambda m: m["close_time"])[-N:]
print("markets:", len(ms), "from", ms[0]["close_time"][:10], "to", ms[-1]["close_time"][:10])
# truth + forecasts
cli = pd.concat([get_cli(st["cli_site"], y) for y in range(2023, 2027)]).dropna(subset=["high"]).set_index("valid")["high"]
today = pd.Timestamp.utcnow().strftime("%Y-%m-%d")
def lst_daily_max(h):
    # h is indexed by UTC; LST = UTC + off hours (off=-6). Day label = LST date. Require 20+ hourly values.
    l = h.copy(); l.index = l.index + pd.Timedelta(hours=off)
    g = l.groupby(l.index.date); mx = g.max(); cnt = g.count()
    mx = mx[cnt >= 20]; mx.index = pd.to_datetime(mx.index).strftime("%Y-%m-%d"); return mx
def raw_utc(model):
    parts = []
    for y in range(2023, 2027):
        r = requests.get("https://previous-runs-api.open-meteo.com/v1/forecast", params=dict(latitude=st["lat"], longitude=st["lon"],
            start_date=f"{y}-01-01", end_date=min(f"{y}-12-31", today), hourly="temperature_2m_previous_day1", temperature_unit="fahrenheit",
            models=model, timezone="GMT"), timeout=180)
        r.raise_for_status(); h = r.json()["hourly"]
        parts.append(pd.Series(h["temperature_2m_previous_day1"], index=pd.to_datetime(h["time"]), dtype=float))
    return pd.concat(parts).dropna()
f = pd.DataFrame({"e": lst_daily_max(raw_utc("ecmwf_ifs025")), "g": lst_daily_max(raw_utc("gfs_seamless"))})
f["fc"] = f[["e", "g"]].mean(axis=1)
print("fixed-lead (day-1) forecast days:", f.fc.notna().sum(), "| model-only MAE vs CLI:", (f.fc - cli.reindex(f.index)).abs().mean().round(2))
tr = pd.DataFrame({"cli": cli}).join(f["fc"], how="inner").dropna(); tr.index = pd.to_datetime(tr.index)
print("training days available:", len(tr))
def fit(date):
    h = tr[(tr.index < date) & (tr.index >= date - pd.Timedelta(days=400))]
    if len(h) < 120: return None
    b, a = np.polyfit(h.fc, h.cli, 1); res = h.cli - (a + b * h.fc)
    return a, b, max(res.std(), 1.0)
def prob(m, mu, sd):
    t, fl, cp = m.get("strike_type"), m.get("floor_strike"), m.get("cap_strike")
    if t == "greater": return 1 - norm.cdf((fl + .5 - mu) / sd)
    if t == "less": return norm.cdf((cp - .5 - mu) / sd)
    if t == "between": return norm.cdf((cp + .5 - mu) / sd) - norm.cdf((fl - .5 - mu) / sd)
def quote(cs, t):
    q = None
    for k in cs:
        if k["end_period_ts"] <= t:
            a, b = k.get("yes_ask", {}).get("close_dollars"), k.get("yes_bid", {}).get("close_dollars")
            p = k.get("price", {}); mid = p.get("close_dollars") or p.get("previous_dollars")
            if a and b and float(a) > 0 and float(b) >= 0: q = (float(b), float(a), float(mid) if mid else (float(a) + float(b)) / 2)
    return q
rows, nodata, nofit = [], 0, 0
for m in ms:
    d = re.search(r"-(\d\d)([A-Z]{3})(\d\d)", m["ticker"])
    if not d or m.get("result") not in ("yes", "no"): continue
    date = pd.to_datetime(f"20{d[1]} {d[2]} {d[3]}", format="%Y %b %d"); ds = str(date.date())
    if ds not in f.index or np.isnan(f.loc[ds, "fc"]): continue
    fp = fit(date)
    if fp is None: nofit += 1; continue
    mu = fp[0] + fp[1] * f.loc[ds, "fc"]; pm = prob(m, mu, fp[2])
    d0 = int((date - pd.Timestamp("1970-01-01")).total_seconds()) - off * 3600
    try: q = quote(candles_any(st["kalshi_series"], m["ticker"], d0 - 16 * 3600, d0), d0)
    except Exception as e: q = None
    if q is None: nodata += 1; continue
    rows.append((m["ticker"], ds, q[0], q[1], q[2], pm, 1 if m["result"] == "yes" else 0))
df = pd.DataFrame(rows, columns=["ticker", "date", "bid", "ask", "mkt", "model", "y"])
print("rows:", len(df), "days:", df.date.nunique(), "| no price data:", nodata, "| not enough training:", nofit)
def brier(p): return ((p - df.y) ** 2).mean()
bl = 0.5 * df.mkt + 0.5 * df.model
print(f"\nBrier  market={brier(df.mkt):.4f}  model={brier(df.model):.4f}  50/50 blend={brier(bl):.4f}")
for lo, hi, lab in ((0, .05, "mkt<5%"), (.05, .15, "5-15%"), (.15, .85, "15-85%"), (.85, 1.01, ">85%")):
    g = df[(df.mkt >= lo) & (df.mkt < hi)]
    if len(g): print(f"  {lab:8s} n={len(g):4d} mkt={g.mkt.mean():.3f} model={g.model.mean():.3f} realised={g.y.mean():.3f}")
# paper P&L: 1 contract, take liquidity at the ask when model edge > threshold
print("\nPaper P&L per contract (taker, fee included):")
for thr in (0.05, 0.08, 0.12, 0.20):
    pnl = []
    for r_ in df.itertuples():
        if r_.model - r_.ask > thr:      # buy YES at ask
            c = r_.ask; pnl.append((1 - c if r_.y else -c) - kalshi_taker_fee(1, c))
        elif (1 - r_.model) - (1 - r_.bid) > thr:   # buy NO at 1-bid
            c = 1 - r_.bid; pnl.append((1 - c if not r_.y else -c) - kalshi_taker_fee(1, c))
    if pnl: print(f"  edge>{thr:.2f}: trades={len(pnl):4d} total=${sum(pnl):7.2f} mean=${np.mean(pnl):.4f} sd/sqrt(n)={np.std(pnl)/np.sqrt(len(pnl)):.4f}")
df.to_csv(f"data/gate3v2_{name}.csv", index=False)
