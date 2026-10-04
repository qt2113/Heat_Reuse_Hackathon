"""Step 1: fetch real data, compute annual + peak heat, print the building table."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import Config  # noqa: E402
from src.demand import annual_heat, hourly_demand, peak_check, screen_outliers  # noqa: E402
from src.fetch import QualityLog, fetch_weather, load_buildings  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    cfg = Config.load()
    b, qlog = load_buildings(cfg)
    temp = fetch_weather(cfg, qlog)
    b = annual_heat(b, cfg, qlog)
    dem = hourly_demand(b, temp, cfg)
    b = peak_check(b, dem, cfg, qlog)
    b, dem = screen_outliers(b, dem, cfg, qlog)

    print("\n=== DATA PROVENANCE ===")
    for k, v in qlog.provenance.items():
        print(f"  {k:28s} {v.upper()}")
    print(f"\nWeather {int(cfg.v('data.weather_year'))}: min {temp.min():.1f} °C, "
          f"HDD18 {(18 - temp).clip(lower=0).sum() / 24:,.0f} K·d")

    pd.set_option("display.width", 250, "display.max_rows", 300, "display.max_colwidth", 34)
    cols = ["property_name", "primary_property_type", "report_year", "distance_m", "gfa_ft2", "main_fuel",
            "annual_heat_mwh", "annual_dhw_mwh", "peak_kw", "peak_w_m2", "full_load_hours", "peak_flag"]
    t = b.sort_values("annual_heat_mwh", ascending=False)[cols].copy()
    t["primary_property_type"] = t["primary_property_type"].str.slice(0, 18)
    print(f"\n=== {len(b)} BUILDINGS WITHIN {cfg.v('data.radius_m'):.0f} m (sorted by annual heat) ===")
    print(t.round({"distance_m": 0, "gfa_ft2": 0, "annual_heat_mwh": 0, "annual_dhw_mwh": 0,
                   "peak_kw": 0, "peak_w_m2": 0, "full_load_hours": 0}).to_string(index=False))

    print("\n=== TOTALS ===")
    print(f"  annual heat {b['annual_heat_mwh'].sum():,.0f} MWh/yr "
          f"(gas {b['heat_gas_mwh'].sum():,.0f}, steam {b['heat_steam_mwh'].sum():,.0f}, oil {b['heat_oil_mwh'].sum():,.0f})")
    print(f"  sum of building peaks {b['peak_kw'].sum() / 1000:,.1f} MW; coincident peak {dem.sum(axis=0).max():,.1f} MW")
    assert abs(dem.sum() - b["annual_heat_mwh"].sum()) < 1e-6 * b["annual_heat_mwh"].sum()

    q = qlog.frame()
    print(f"\n=== DATA-QUALITY LOG ({len(q)} items) — counts ===")
    print(q["kind"].value_counts().to_string())
    for kind in ["campus record", "duplicate", "missing coordinates", "missing BBL", "intensity outlier",
                 "excluded outlier", "no heating fuel", "year fallback", "peak W/m2 out of range", "excluded"]:
        sub = q[q["kind"] == kind]
        if len(sub):
            print(f"\n-- {kind} --")
            print(sub[["building", "detail"]].to_string(index=False, max_colwidth=110))


if __name__ == "__main__":
    main()
