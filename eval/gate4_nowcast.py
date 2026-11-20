"""GATE 4 (intraday nowcast): obs-so-far + day-1 forecast vs market at 09/12/15 LST. Based on does a simple calibrated forecast model (EMOS on ECMWF+GFS day-ahead forecasts) beat the market at D 00:00 LST?
Walk-forward: mu/sigma fit only on days strictly before each target date. Paper P&L net of Kalshi taker fee.
Usage: python eval/gate3_model_vs_market.py chicago 2400"""
import sys, re, yaml, requests, numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, ".")
from ingest.kalshi import settled_markets, historical_markets, candles_any
from ingest.iem import get_cli, get_asos
from rules.registry import kalshi_taker_fee, lst_day_window_utc
name, N = sys.argv[1], int(sys.argv[2])
st = yaml.safe_load(open("config/stations.yaml"))["stations"][name]; off = st["lst_utc_offset_hours"]
# markets
ms = {m["ticker"]: m for m in historical_markets(st["kalshi_series"])}
ms.update({m["ticker"]: m for m in settled_markets(st["kalshi_series"])})
ms = sorted(ms.values(), key=lambda m: m["close_time"])[-N:]
print("markets:", len(ms), "from", ms[0]["close_time"][:10], "to", ms[-1]["close_time"][:10])
# truth + forecasts
cli = pd.concat([get_cli(st["cli_site"], y) for y in range(2025, 2027)]).dropna(subset=["high"]).set_index("valid")["high"]
today = pd.Timestamp.utcnow().strftime("%Y-%m-%d")
def lst_daily_max(h):
    # h is indexed by UTC; LST = UTC + off hours (off=-6). Day label = LST date. Require 20+ hourly values.
    l = h.copy(); l.index = l.index + pd.Timedelta(hours=off)
    g = l.groupby(l.index.date); mx = g.max(); cnt = g.count()
    mx = mx[cnt >= 20]; mx.index = pd.to_datetime(mx.index).strftime("%Y-%m-%d"); return mx
import time
def raw_utc(model):
    parts = []
    for start, end in [(f"{y}-{m:02d}-01", (pd.Timestamp(f"{y}-{m:02d}-01") + pd.offsets.DateOffset(months=6, days=-1)).strftime("%Y-%m-%d"))
                       for y in (2025, 2026) for m in (1, 7)]:
        if start > today: break
        end = min(end, today)
        for attempt in range(7):
            try:
                r = requests.get("https://previous-runs-api.open-meteo.com/v1/forecast", params=dict(latitude=st["lat"], longitude=st["lon"],
                    start_date=start, end_date=end, hourly="temperature_2m_previous_day1", temperature_unit="fahrenheit",
                    models=model, timezone="GMT"), timeout=60)
                if r.status_code == 429:
                    print('429', model, start, r.text[:120]); time.sleep(45 * (attempt + 1)); continue
                r.raise_for_status(); break
            except requests.RequestException as e:
                print("retry", model, start, type(e).__name__); time.sleep(10 * (attempt + 1))
        else: raise RuntimeError(f"open-meteo failed {model} {start}")
        h = r.json()["hourly"]
        parts.append(pd.Series(h["temperature_2m_previous_day1"], index=pd.to_datetime(h["time"]), dtype=float))
        time.sleep(1)
    return pd.concat(parts).dropna()
f = pd.DataFrame({"e": lst_daily_max(raw_utc("ecmwf_ifs025")), "g": lst_daily_max(raw_utc("gfs_seamless"))})
f["fc"] = f[["e", "g"]].mean(axis=1)
print("fixed-lead (day-1) forecast days:", f.fc.notna().sum(), "| model-only MAE vs CLI:", (f.fc - cli.reindex(f.index)).abs().mean().round(2))
asos = get_asos(st["icao"][1:], st["iem_network"], "2025-01-01", today)
asos["tmpf"] = asos["tmpf"].astype(float)
CUTS = (9, 12, 15)
def obs_max(ds, h):
    s0, _ = lst_day_window_utc(ds, off)
    d = asos[(asos.valid >= s0) & (asos.valid < s0 + pd.Timedelta(hours=h))]
    return round(d.tmpf.max()) if len(d) >= max(3, h // 3) else np.nan
feat = {h: pd.Series({ds: obs_max(ds, h) for ds in f.index}) for h in CUTS}
tr = pd.DataFrame({"cli": cli}).join(f["fc"], how="inner").dropna(); tr.index = pd.to_datetime(tr.index)
print("training days available:", len(tr))
from scipy.stats import norm as N
def fit(date, h):
    d = pd.DataFrame({"H": cli, "F": f.fc, "O": feat[h]}).dropna(); d.index = pd.to_datetime(d.index)
    d = d[(d.index < date) & (d.index >= date - pd.Timedelta(days=400))]
    if len(d) < 90: return None
    X = np.c_[np.ones(len(d)), d.F, np.maximum(d.O, 0)]; beta, *_ = np.linalg.lstsq(X, d.H, rcond=None)
    sd = max((d.H - X @ beta).std(), 0.8); return beta, sd
def cdf_le(x, mu, sd, o):          # P(H <= x), H integer-valued, truncated below at o (running max can't fall)
    zo = N.cdf((o - 0.5 - mu) / sd)
    if x < o: return 0.0
    return min(1.0, max(0.0, (N.cdf((x + 0.5 - mu) / sd) - zo) / max(1 - zo, 1e-9)))
def prob(m, mu, sd, o):
    t, fl, cp = m.get("strike_type"), m.get("floor_strike"), m.get("cap_strike")
    if t == "greater": return 1 - cdf_le(fl, mu, sd, o)
    if t == "less": return cdf_le(cp - 1, mu, sd, o)
    if t == "between": return cdf_le(cp, mu, sd, o) - cdf_le(fl - 1, mu, sd, o)
def quote(cs, t):
    q = None
    for k in cs:
        if k["end_period_ts"] <= t:
            a, b = k.get("yes_ask", {}).get("close_dollars"), k.get("yes_bid", {}).get("close_dollars")
            p = k.get("price", {}); mid = p.get("close_dollars") or p.get("previous_dollars")
            if a and b and float(a) > 0 and float(b) >= 0: q = (float(b), float(a), float(mid) if mid else (float(a) + float(b)) / 2)
    return q
rows, nodata = [], 0
for m in ms:
    d = re.search(r"-(\d\d)([A-Z]{3})(\d\d)", m["ticker"])
    if not d or m.get("result") not in ("yes", "no"): continue
    date = pd.to_datetime(f"20{d[1]} {d[2]} {d[3]}", format="%Y %b %d"); ds = str(date.date())
    if ds not in f.index or np.isnan(f.loc[ds, "fc"]): continue
    d0 = int((date - pd.Timestamp("1970-01-01")).total_seconds()) - off * 3600
    try: cs = candles_any(st["kalshi_series"], m["ticker"], d0 - 16 * 3600, d0 + 17 * 3600)
    except Exception: cs = []
    for h in CUTS:
        o = feat[h].get(ds, np.nan); fp = fit(date, h)
        q = quote(cs, d0 + h * 3600)
        if fp is None or np.isnan(o) or q is None: nodata += 1; continue
        mu = fp[0][0] + fp[0][1] * f.loc[ds, "fc"] + fp[0][2] * o
        rows.append((m["ticker"], ds, h, q[0], q[1], q[2], prob(m, mu, fp[1], o), 1 if m["result"] == "yes" else 0))
df = pd.DataFrame(rows, columns=["ticker", "date", "cut", "bid", "ask", "mkt", "model", "y"])
print("rows:", len(df), "| skipped (no data/fit):", nodata)
for h in CUTS:
    g = df[df.cut == h]
    if g.empty: continue
    br = lambda p: ((p - g.y) ** 2).mean()
    print(f"\n=== cutoff {h:02d}:00 LST | n={len(g)} days={g.date.nunique()} | Brier market={br(g.mkt):.4f} model={br(g.model):.4f} blend={br(.5*g.mkt+.5*g.model):.4f}")
    for thr in (0.05, 0.10, 0.20):
        pnl = []
        for r_ in g.itertuples():
            if r_.model - r_.ask > thr: c = r_.ask; pnl.append((1 - c if r_.y else -c) - kalshi_taker_fee(1, c))
            elif r_.bid - r_.model > thr: c = 1 - r_.bid; pnl.append((1 - c if not r_.y else -c) - kalshi_taker_fee(1, c))
        if pnl: print(f"   edge>{thr:.2f}: trades={len(pnl):4d} total=${sum(pnl):7.2f} mean=${np.mean(pnl):+.4f} se={np.std(pnl)/np.sqrt(len(pnl)):.4f}")
df.to_csv(f"data/gate4_{name}.csv", index=False)
