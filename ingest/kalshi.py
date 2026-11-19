import requests, time
BASE = "https://api.elections.kalshi.com/trade-api/v2"
def _get(path, **params):
    for attempt in range(8):
        r = requests.get(BASE + path, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(2 ** attempt); continue
        r.raise_for_status(); time.sleep(0.15); return r.json()
    r.raise_for_status()
def settled_markets(series: str, limit_pages: int = 50):
    out, cursor = [], None
    for _ in range(limit_pages):
        j = _get("/markets", series_ticker=series, status="settled", limit=1000, **({"cursor": cursor} if cursor else {}))
        out += j.get("markets", []); cursor = j.get("cursor")
        if not cursor: break
    return out
def candles(series: str, ticker: str, start_ts: int, end_ts: int, period_interval: int = 60):
    j = _get(f"/series/{series}/markets/{ticker}/candlesticks", start_ts=start_ts, end_ts=end_ts, period_interval=period_interval)
    return j.get("candlesticks", [])
