"""Feature engineering: data/ -> Model A inputs.

Everything here is deterministic and traceable to a CSV column or to an assumption ID (A01-A20).
No observation is invented: where a value is unknown the Low/Base/High register supplies it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = ROOT / "model" / "config" / "scenarios.yaml"
HOURS = 8760


def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ assumptions
def load_assumptions() -> pd.DataFrame:
    return pd.read_csv(DATA / "reference" / "assumptions_scenarios.csv").set_index("assumption_id")


def assumption_values(level_overrides: dict[str, str] | None = None) -> dict[str, float]:
    """Base values of the numeric assumptions; `level_overrides` maps an ID to 'low' or 'high'."""
    a = load_assumptions()
    out = {}
    for aid, row in a.iterrows():
        lvl = (level_overrides or {}).get(aid, "base")
        v = pd.to_numeric(row[lvl], errors="coerce")
        if pd.isna(v):
            v = pd.to_numeric(row["base"], errors="coerce")
        out[aid] = None if pd.isna(v) else float(v)
    return out


# ------------------------------------------------------------------ weather
def load_weather() -> pd.DataFrame:
    w = pd.read_csv(DATA / "processed" / "weather_tmyx_hourly.csv")
    assert len(w) == HOURS, "weather file must have 8,760 hours"
    return w


def design_temperature() -> float:
    d = pd.read_csv(DATA / "processed" / "weather_design_conditions.csv").set_index("parameter")
    return float(d.loc["heating_design_DB_99.6pct_C", "value"])


# ------------------------------------------------------------------ supply
def source_annual_electricity_MWh() -> float:
    s = pd.read_csv(DATA / "processed" / "source_111_8th_annual.csv")
    return float(s.electricity_MWh.mean())  # 3-year mean of metered LL84 electricity


# ------------------------------------------------------------------ offtakers (property level, de-duplicated)
def build_offtakers() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rebuild the offtaker table by LL84 property_id (names change between years) and drop
    same-lot duplicate filings. Returns (clean table, log of dropped rows)."""
    y = pd.read_csv(DATA / "processed" / "ll84_buildings_1km_by_year.csv", dtype={"property_id": str, "report_year": str})
    y = y[~y.is_child_of_listed_parent.astype(bool)].copy()
    for c in ("steam_MWh", "gas_MWh", "oil_MWh", "heat_fuel_MWh", "electricity_MWh"):
        y[c] = pd.to_numeric(y[c], errors="coerce")
    y = y.sort_values("report_year")
    g = y.groupby("property_id")
    t = pd.DataFrame({
        "property_name": g.property_name.last(),
        "bbl": g.nyc_borough_block_and_lot.last(),
        "use_type": g.largest_property_use_type.last(),
        "dist_m": g.dist_m.min(),
        "lat": g.latitude.mean(), "lon": g.longitude.mean(),
        "years": g.report_year.apply(lambda s: ",".join(sorted(set(s)))),
        "n_years": g.report_year.nunique(),
        "gfa_ft2": g.property_gfa_calculated_1.median(),
        "units_res": g.multifamily_housing_total.median(),
        "steam_MWh": g.steam_MWh.mean(), "gas_MWh": g.gas_MWh.mean(), "oil_MWh": g.oil_MWh.mean(),
        "heat_fuel_MWh": g.heat_fuel_MWh.mean(),
        "heat_fuel_MWh_min": g.heat_fuel_MWh.min(), "heat_fuel_MWh_max": g.heat_fuel_MWh.max(),
        "any_estimated": g.estimated_data_flag.apply(lambda s: "Yes" in set(s)),
    }).reset_index()
    t[["steam_MWh", "gas_MWh", "oil_MWh"]] = t[["steam_MWh", "gas_MWh", "oil_MWh"]].fillna(0.0)

    # same BBL set filed twice with overlapping years -> keep the record with more years (then more heat)
    t["_yrs"] = t.years.str.split(",").apply(set)
    t = t.sort_values(["n_years", "heat_fuel_MWh"], ascending=False)
    keep, dropped = [], []
    for bbl, grp in t.groupby("bbl", sort=False):
        kept_years: list[set] = []
        for _, r in grp.iterrows():
            if any(r._yrs & ky for ky in kept_years):
                dropped.append(dict(property_id=r.property_id, property_name=r.property_name, bbl=bbl, years=r.years,
                                    reason="same tax lot and overlapping report years as a kept record"))
            else:
                kept_years.append(r._yrs)
                keep.append(r.property_id)
    t = t[t.property_id.isin(keep)].drop(columns="_yrs")

    # fuel classification and the heating-system rule used by H7
    t["main_fuel"] = np.select([t.steam_MWh >= t[["gas_MWh", "oil_MWh"]].sum(axis=1)], ["steam"], default="gas_or_oil")
    t["is_residential"] = t.use_type.eq("Multifamily Housing")
    t["is_nycha"] = t.property_id.isin(["2831044", "4473909", "2830989"])  # Fulton, Elliott-Chelsea campus, Chelsea
    # existing steam buildings and NYCHA (steam radiators, pilot) cannot take low-temperature space heat (H7)
    t["sh_system"] = np.where((t.main_fuel == "steam") | t.is_nycha, "steam_radiators", "hydronic_assumed")
    return t.sort_values("heat_fuel_MWh", ascending=False).reset_index(drop=True), pd.DataFrame(dropped)


# ------------------------------------------------------------------ demand features
def nonres_base_share(weather: pd.DataFrame, ratio: float) -> float:
    """Base-load (hot water / process) share of annual demand for a non-residential building such that
    July demand / January demand = `ratio` (A20, CBS E17), with space heat proportional to degree-hours."""
    hdh = weather.groupby("month").HDH_18C.sum()
    hrs = weather.groupby("month").size()
    tot_hdh, jan, jul = hdh.sum(), 1, 7
    # monthly demand m = b*hrs/8760 + (1-b)*hdh/tot_hdh ; solve m_jul = ratio * m_jan for b
    a_j, h_j = hrs[jan] / HOURS, hdh[jan] / tot_hdh
    a_l, h_l = hrs[jul] / HOURS, hdh[jul] / tot_hdh
    # b*a_l + (1-b)*h_l = ratio*(b*a_j + (1-b)*h_j)
    num = ratio * h_j - h_l
    den = (a_l - h_l) - ratio * (a_j - h_j)
    return float(np.clip(num / den, 0.0, 1.0))


@dataclass
class Building:
    pid: str
    name: str
    fuel: str
    sh_system: str
    eta_base: float
    D_useful: float          # MWh/yr useful heat today
    f_base: float            # share that is hot water / base load (served at DHW temperature)
    units: float
    dist_m: float
    lat: float
    lon: float
    is_nycha: bool
    rebuilt: bool = False
    backup: str = "existing"


def building_demands(t: pd.DataFrame, members: list[str], A: dict, weather: pd.DataFrame,
                     q_dhw_apt: float, cfg_rebuild: dict | None) -> list[Building]:
    """Useful-heat demand per connected building (A04 steam efficiency, 0.85 gas boilers per EIA S11)."""
    eta_gas = 0.85
    b_nonres = nonres_base_share(weather, A["A20"])
    out = []
    for pid in members:
        r = t.set_index("property_id").loc[pid]
        eta = A["A04"] if r.main_fuel == "steam" else eta_gas
        D = float(r.heat_fuel_MWh) * eta
        if r.is_residential and pd.notna(r.units_res):
            f_base = min(0.6, float(r.units_res) * q_dhw_apt / D)   # pilot DHW per apartment (S13)
        else:
            f_base = b_nonres
        out.append(Building(pid, r.property_name, r.main_fuel, r.sh_system, eta, D, f_base,
                            float(r.units_res) if pd.notna(r.units_res) else 0.0, float(r.dist_m),
                            float(r.lat), float(r.lon), bool(r.is_nycha)))
    if cfg_rebuild:
        tt = t.set_index("property_id")
        for s in cfg_rebuild["sites"]:
            anchor = tt.loc[s["anchor_property_id"]]
            units = cfg_rebuild["units"] * s["share"]
            out.append(Building(f"rebuild:{s['anchor_property_id']}", s["name"], "new_electric", "low_temp_new", 1.0,
                                units * A["A03"], A["A19"], units, float(anchor.dist_m), float(anchor.lat), float(anchor.lon),
                                True, rebuilt=True, backup=cfg_rebuild.get("backup", "electric_boiler")))
    return out


def hourly_shapes(weather: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Normalised hourly shapes (each sums to 1): space heat by degree-hours; hot water flat
    (no measured draw profile exists - GAP-04; storage is sized on the space-heat peaks)."""
    hdh = weather.HDH_18C.to_numpy(dtype=float)
    return hdh / hdh.sum(), np.full(HOURS, 1.0 / HOURS)


# ------------------------------------------------------------------ network route length (T7)
def route_length_m(site: dict, buildings: list[Building], rotation_deg: float) -> float:
    """Minimum spanning tree over the source and connected buildings with L1 distance on the
    Manhattan street grid (rotated ~29 deg): a street-following trench estimate."""
    pts = [(site["lat"], site["lon"])] + [(b.lat, b.lon) for b in buildings if not b.pid == site["property_id"]]
    # de-duplicate co-located points (e.g. two rebuild sites anchored to one campus)
    pts = list(dict.fromkeys((round(a, 6), round(o, 6)) for a, o in pts))
    if len(pts) < 2:
        return 0.0
    lat0 = site["lat"]
    xy = np.array([((o - site["lon"]) * 111_320 * math.cos(math.radians(lat0)), (a - lat0) * 110_540) for a, o in pts])
    th = math.radians(rotation_deg)
    rot = xy @ np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    n = len(rot)
    dist = np.abs(rot[:, None, :] - rot[None, :, :]).sum(axis=2)
    in_tree, total = {0}, 0.0
    while len(in_tree) < n:
        best = min(((dist[i, j], j) for i in in_tree for j in range(n) if j not in in_tree))
        total += best[0]
        in_tree.add(best[1])
    return float(total)


def pilot_reference() -> dict:
    """Con Ed Chelsea pilot values used to calibrate and validate Model A (S13)."""
    r = pd.read_csv(DATA / "reference" / "chelsea_uten_pilot_stage2.csv").set_index("metric").value
    mmbtu = 1 / 3.412142
    return dict(
        dhw_MWh=(float(r["dhw_load_401_W_16th"]) + float(r["dhw_load_410_W_17th"]) + float(r["dhw_load_420_W_17th"])) * mmbtu,
        sh_MWh=float(r["space_heating_load_401_W_16th"]) * mmbtu,
        loop_supply_C=(5 / 9) * ((float(r["loop_supply_temp_heating_mode_min"]) + float(r["loop_supply_temp_heating_mode_max"])) / 2 - 32),
        dhw_supply_C=(5 / 9) * (float(r["dhw_design_temperature"]) - 32),
        apartments=float(r["apartments_served"]),
    )


def pilot_electricity_by_end_use() -> dict:
    """Pilot modeled heat-pump electricity by end use (filing Table 7, transcribed and verified in S13)."""
    r = pd.read_csv(DATA / "reference" / "chelsea_uten_pilot_stage2.csv").set_index("metric").value
    return dict(dhw_kWh=float(r["customer_hp_electricity_water_heating"]), sh_kWh=float(r["customer_hp_electricity_space_heating"]))
