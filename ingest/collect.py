"""Daily-snapshot collector (read-only, public data). Appends one CSV row per open market per run, plus latest METAR obs.
Run hourly from GitHub Actions; output is committed to the `data` branch."""
import sys, os, time, datetime as dt, yaml, requests, pandas as pd
sys.path.insert(0, ".")
from ingest.kalshi import _get
from ingest.iem import get_asos
now = dt.datetime.now(dt.timezone.utc); ts = now.strftime("%Y-%m-%dT%H:%MZ")
cfg = yaml.safe_load(open("config/stations.yaml"))["stations"]
mk_rows, ob_rows, fc_rows = [], [], []
for name, st in cfg.items():
    time.sleep(3)
    try:
        cur = None
        while True:
            j = _get("/markets", series_ticker=st["kalshi_series"], status="open", limit=1000, **({"cursor": cur} if cur else {}))
            for m in j.get("markets", []):
                mk_rows.append(dict(ts=ts, station=name, ticker=m["ticker"], strike_type=m.get("strike_type"), floor=m.get("floor_strike"),
                    cap=m.get("cap_strike"), yes_bid=m.get("yes_bid_dollars"), yes_ask=m.get("yes_ask_dollars"), last=m.get("last_price_dollars"),
                    volume=m.get("volume_fp"), close_time=m.get("close_time")))
            cur = j.get("cursor")
            if not cur or not j.get("markets"): break
    except Exception as e: print("kalshi fail", name, e)
    try:
        d0 = (now - dt.timedelta(days=1)).strftime("%Y-%m-%d"); d1 = (now + dt.timedelta(days=1)).strftime("%Y-%m-%d")
        for _try in range(4):
            try: a = get_asos(st["icao"][1:], st["iem_network"], d0, d1).tail(12); break
            except requests.HTTPError as e:
                if e.response.status_code != 429 or _try == 3: raise
                time.sleep(10 * (_try + 1))
        for r in a.itertuples(): ob_rows.append(dict(ts=ts, station=name, obs_time=str(r.valid), tmpf=r.tmpf))
    except Exception as e: print("obs fail", name, e)
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params=dict(latitude=st["lat"], longitude=st["lon"], daily="temperature_2m_max",
            temperature_unit="fahrenheit", models="ecmwf_ifs025,gfs_seamless", timezone=st["tz"], forecast_days=3), timeout=30)
        r.raise_for_status(); d = r.json()["daily"]
        for i, day in enumerate(d["time"]):
            fc_rows.append(dict(ts=ts, station=name, date=day, ecmwf=d["temperature_2m_max_ecmwf_ifs025"][i], gfs=d["temperature_2m_max_gfs_seamless"][i]))
    except Exception as e: print("forecast fail", name, e)
day = now.strftime("%Y-%m-%d"); os.makedirs("snapshots", exist_ok=True)
for nm, rows in (("markets", mk_rows), ("obs", ob_rows), ("forecast", fc_rows)):
    if rows:
        p = f"snapshots/{nm}_{day[:7]}.csv"
        pd.DataFrame(rows).to_csv(p, mode="a", header=not os.path.exists(p), index=False)
print(f"{ts}: markets={len(mk_rows)} obs={len(ob_rows)} forecast={len(fc_rows)}")
