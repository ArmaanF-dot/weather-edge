import io, requests, pandas as pd
BASE = "https://mesonet.agron.iastate.edu"
def get_cli(station: str, year: int) -> pd.DataFrame:
    r = requests.get(f"{BASE}/json/cli.py", params={"station": station, "year": year}, timeout=60)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["results"])
    return df[["valid", "high", "low"]].assign(valid=lambda d: pd.to_datetime(d["valid"]).dt.date.astype(str))
def get_asos(station3: str, network: str, start: str, end: str) -> pd.DataFrame:
    """Hourly+special METAR air temp (degF). station3 = ICAO without leading K."""
    r = requests.get(f"{BASE}/cgi-bin/request/asos.py", params={
        "station": station3, "data": "tmpf", "year1": start[:4], "month1": start[5:7], "day1": start[8:10],
        "year2": end[:4], "month2": end[5:7], "day2": end[8:10], "tz": "UTC", "format": "onlycomma",
        "latlon": "no", "missing": "M", "trace": "T", "report_type": "3"}, timeout=300)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), na_values=["M"])
    df["valid"] = pd.to_datetime(df["valid"], utc=True)
    return df.dropna(subset=["tmpf"])
