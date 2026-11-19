"""GATE 2: how far is the METAR-implied daily max from the final CLI max, by local-standard-time cutoff hour?
Usage: python eval/gate2_metar_gap.py chicago 2024 2025"""
import sys, yaml, pandas as pd, numpy as np
sys.path.insert(0, ".")
from ingest.iem import get_cli, get_asos
from rules.registry import lst_day_window_utc
name, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
st = yaml.safe_load(open("config/stations.yaml"))["stations"][name]
cli = pd.concat([get_cli(st["cli_site"], y) for y in range(y0, y1 + 1)]).dropna(subset=["high"])
asos = get_asos(st["icao"][1:], st["iem_network"], f"{y0}-01-01", f"{y1+1}-01-02")
rows = []
for _, r in cli.iterrows():
    s, e = lst_day_window_utc(r["valid"], st["lst_utc_offset_hours"])
    day = asos[(asos.valid >= s) & (asos.valid < e)]
    for h in (12, 15, 18, 23):
        part = day[day.valid < s + pd.Timedelta(hours=h)]
        if len(part): rows.append((r["valid"], h, r["high"] - round(part.tmpf.max())))
df = pd.DataFrame(rows, columns=["date", "cutoff_lst_hour", "gap_f"])
summ = df.groupby("cutoff_lst_hour").gap_f.describe(percentiles=[.05, .5, .95])
print(summ); print("\nShare |gap|<=1F at 23h:", (df[df.cutoff_lst_hour == 23].gap_f.abs() <= 1).mean())
df.to_parquet(f"data/gate2_{name}.parquet")
