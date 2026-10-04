"""Model S - a simplified, independently coded heat-reuse model for Site 1 (111 8th Avenue).

One function chain, no scoring weights:
    params()  -> buildings()  -> simulate()  (temperature-bin energy balance)
              -> economics()  (resource view + stakeholder transfers)
              -> indicators() (8 indicators) + constraints() (hard pass/fail)

Temporal model
    The 8,760 TMYx hours are collapsed into (month x 1 C outdoor-temperature bin x source-outage flag)
    groups, about 250 rows. Space heat is proportional to degree-hours (base 18 C) and hot water is flat,
    exactly as in Model A, so without storage every hour in a bin is dispatched identically: the bin
    balance is the hourly balance summed (validated against an hourly loop in validate.py).
    What is lost: thermal-storage chronology (peak shaving) and intra-day hot-water peaks.

Reads the shared data layer read-only. Writes nothing.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data"
MWH_PER_MMBTU = 1 / 3.412142
HOURS = 8760
COMMUNITY_USES = {"K-12 School", "College/University", "Library", "Museum", "Worship Facility", "Residential Care Facility",
                  "Social/Meeting Hall", "Pre-school/Daycare", "Hospital (General Medical & Surgical)"}


# ------------------------------------------------------------------ parameters
def _register() -> pd.DataFrame:
    return pd.read_csv(DATA / "reference" / "assumptions_scenarios.csv").set_index("assumption_id")


def params(overrides: dict | None = None, levels: dict | None = None) -> dict:
    """Flat parameter dict. `levels` = {"A05": "low"} picks register Low/High; `overrides` sets any key directly."""
    cfg = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    reg = _register()
    P: dict = {}
    for sect, d in cfg.items():
        for k, v in d.items():
            if isinstance(v, str) and v.startswith("register:"):
                aid = v.split(":")[1]
                lvl = (levels or {}).get(aid, "base")
                x = pd.to_numeric(reg.loc[aid, lvl], errors="coerce")
                if pd.isna(x):
                    x = pd.to_numeric(reg.loc[aid, "base"], errors="coerce")
                P[k] = float(x)
                P.setdefault("_register_ids", {})[k] = aid
            else:
                P[k] = v
    # experiment switches (defaults = this review's base case; the controlled run sets ABC-equivalent values)
    P.update(route_mode="centroid", exclude_pilot_served=True, li_definition="strict", grid_ef_scale=1.0,
             price_scale_gas=1.0, price_scale_steam=1.0, bld_capex_scale=1.0, nycha_apt_capex_scale=1.0,
             internal_only_dhw=True)
    P.update(overrides or {})
    return P


def abc_equivalent(P: dict) -> dict:
    """Switch off this review's corrections so the model uses exactly the Model A/B conventions."""
    return dict(P, dist_loss_per_km=0.0, route_mode="centroid", exclude_pilot_served=False, li_definition="abc")


# ------------------------------------------------------------------ data (read-only)
@lru_cache(maxsize=1)
def data() -> dict:
    w = pd.read_csv(DATA / "processed" / "weather_tmyx_hourly.csv")
    assert len(w) == HOURS
    design = pd.read_csv(DATA / "processed" / "weather_design_conditions.csv").set_index("parameter").value
    src = pd.read_csv(DATA / "processed" / "source_111_8th_annual.csv")
    offt = pd.read_csv(ROOT / "outputs" / "features" / "offtakers_features.csv", dtype={"property_id": str})
    pilot = pd.read_csv(DATA / "reference" / "chelsea_uten_pilot_stage2.csv").set_index("metric").value
    bench = pd.read_csv(DATA / "processed" / "chelsea_uten_benchmarks.csv").set_index("metric").value
    prices = pd.read_csv(DATA / "processed" / "energy_prices_ny_summary.csv").set_index("parameter").value
    ll97 = pd.read_csv(DATA / "reference" / "ll97_emission_coefficients.csv").set_index("fuel").tCO2e_per_MWh
    ap42 = pd.read_csv(DATA / "reference" / "ap42_natural_gas_boilers.csv")
    fec = pd.read_csv(DATA / "reference" / "fec_rebuild_facts.csv").set_index("metric").value
    dac = pd.read_csv(DATA / "processed" / "dac_tracts_1km.csv", dtype={"geoid": str}).set_index("geoid")
    pluto = pd.read_csv(DATA / "processed" / "pluto_lots_1km.csv", dtype={"bbl": str, "tract_geoid": str}).set_index("bbl")
    dea = pd.read_csv(DATA / "processed" / "equipment_dea_heat.csv")
    dea = dea[dea.year == 2025].pivot_table(index="ws", columns="parameter", values="ctrl")
    mac = pd.read_csv(DATA / "processed" / "macro_cpi_fx.csv").set_index("year")
    k_usd = float(mac.loc[2020, "usd_per_eur"] * mac.loc[2020, "cpi_factor_to_latest_full_year"])
    hpw, hpa = dea.loc["40 Comp. hp, waste heat 3 MW"], dea.loc["40 Comp. hp, airsource 3 MW"]
    src_cap_MW = float(pilot["source_low_grade_capacity"]) * 1000 * MWH_PER_MMBTU / 1e6

    # building -> tract, DAC flag, lot size (first BBL of the filing)
    first_bbl = offt.bbl.astype(str).str.split(";").str[0].str.strip()
    offt["tract"] = first_bbl.map(pluto.tract_geoid)
    offt["lotarea_ft2"] = first_bbl.map(pluto.lotarea)
    offt["dac"] = offt.tract.map(dac.dac_designation).eq("Designated as DAC")
    offt["community"] = offt.use_type.isin(COMMUNITY_USES)

    pilot_dhw = (float(pilot["dhw_load_401_W_16th"]) + float(pilot["dhw_load_410_W_17th"])
                 + float(pilot["dhw_load_420_W_17th"])) * MWH_PER_MMBTU
    return dict(
        weather=w, T_design=float(design["heating_design_DB_99.6pct_C"]), E_el_src=float(src.electricity_MWh.mean()),
        offt=offt.set_index("property_id", drop=False),
        q_dhw_apt=pilot_dhw / float(pilot["apartments_served"]),
        pilot_hp_elec_MWh=(float(pilot["customer_hp_electricity_water_heating"]) + float(pilot["customer_hp_electricity_space_heating"])) / 1000,
        pilot_heat_MWh=float(bench["useful_heat_supplied_by_UTEN"]), pilot_src_elec_MWh=float(pilot["source_building_electricity_delta"]) / 1000,
        cost=dict(
            hp_capex=float(hpw.capex_MEUR_per_MWth) * 1e6 * k_usd, hp_fom=float(hpw.fixed_om_EUR_per_MWth_yr) * k_usd,
            hp_vom=float(hpw.var_om_EUR_per_MWhth) * k_usd, life=float(hpw.lifetime_yr),
            ashp_capex=float(hpa.capex_MEUR_per_MWth) * 1e6 * k_usd, ashp_fom=float(hpa.fixed_om_EUR_per_MWth_yr) * k_usd,
            ashp_vom=float(hpa.var_om_EUR_per_MWhth) * k_usd, ashp_scop=float(hpa.cop_or_efficiency_annual),
            hx_per_MW=float(pilot["thermal_resource_construction"]) * 1e6 / src_cap_MW,
            energy_centre=float(pilot["energy_center_construction"]) * 1e6,
            nycha_per_apt=float(bench["customer_building_cost_per_apartment"]),
            tariff=float(pilot["customer_thermal_rate"]) / MWH_PER_MMBTU, connection=float(pilot["customer_fixed_connection_charge"]),
        ),
        price=dict(steam=float(bench["implied_marginal_steam_cost_per_MWh_steam"]), gas=float(prices["gas_commercial_USD_MWh_fuel_12mo_mean"])),
        ef=dict(steam=float(ll97["district_steam"]), gas=float(ll97["natural_gas"]), grid=float(ll97["electricity_grid"])),
        nox_kg_per_MWh=float(ap42.query("pollutant=='NOx' and control=='uncontrolled'").kg_per_MWh_fuel.iloc[0]),
        fec=dict(replacement=float(fec["existing_NYCHA_apartments_replaced"]), new=float(fec["new_mixed_income_units_up_to"]),
                 affordable_new=float(fec["new_affordable_apartments_approx"])),
    )


# ------------------------------------------------------------------ reduced temporal model
@lru_cache(maxsize=8)
def bins(availability: float, width: float = 1.0) -> pd.DataFrame:
    """(month, temperature bin, outage) groups. Outage hours sit in the coldest hours (as Model A)."""
    w = data()["weather"]
    T = w.dry_bulb_C.to_numpy(float)
    out = np.zeros(HOURS, bool)
    n_out = int(round((1 - availability) * HOURS))
    if n_out:
        out[np.argsort(T)[:n_out]] = True
    g = pd.DataFrame({"month": w.month, "tbin": np.floor(T / width) * width, "outage": out, "hdh": w.HDH_18C, "T": T})
    b = g.groupby(["month", "tbin", "outage"]).agg(hours=("hdh", "size"), hdh=("hdh", "sum"), T=("T", "mean")).reset_index()
    b["hdh_per_h"] = b.hdh / b.hours
    return b


def nonres_base_share(ratio: float) -> float:
    """Base-load share b of a non-residential building such that July/January demand = ratio (A20)."""
    w = data()["weather"]
    hdh, hrs = w.groupby("month").HDH_18C.sum(), w.groupby("month").size()
    tot = hdh.sum()
    a_j, h_j, a_l, h_l = hrs[1] / HOURS, hdh[1] / tot, hrs[7] / HOURS, hdh[7] / tot
    return float(np.clip((ratio * h_j - h_l) / ((a_l - h_l) - ratio * (a_j - h_j)), 0, 1))


def cop(supply_C: float, P: dict) -> float:
    t_cond = supply_C + P["approach_cond_K"] + 273.15
    t_evap = P["loop_temp_C"] - P["hx_approach_K"] - P["loop_dT_K"] - P["approach_evap_K"] + 273.15
    return P["carnot_eff"] * t_cond / (t_cond - t_evap)


# ------------------------------------------------------------------ buildings
def buildings(members: list[str], P: dict) -> pd.DataFrame:
    """Connected buildings with their servable demand split into temperature classes.
    `rebuild:<anchor pid>` adds a rebuilt NYCHA campus (low-temperature design)."""
    D = data()
    o = D["offt"]
    b_nonres = nonres_base_share(P["nonres_summer_winter_ratio"])
    rows = []
    li_new = (D["fec"]["replacement"] + D["fec"]["affordable_new"]) / (D["fec"]["replacement"] + D["fec"]["new"])
    for m in members:
        if m.startswith("rebuild:"):
            anc = o.loc[m.split(":")[1]]
            share = {"2831044": 0.4554, "4473909": 0.5446}[anc.property_id]
            units = P["rebuild_units"] * share
            D_u = units * P["rebuild_MWh_per_apt"]
            rows.append(dict(pid=m, name=f"Rebuilt {anc.property_name.title()}", use="Multifamily Housing (rebuilt NYCHA)", fuel="new_electric",
                             heating="low_temp_new", rebuilt=True, eta=1.0, D_useful=D_u, f_base=P["rebuild_dhw_share"], units=units,
                             li_units=units * li_new, dac=bool(anc.dac), community=False, nycha=True,
                             lat=anc.lat, lon=anc.lon, lotarea_ft2=anc.lotarea_ft2, n_years=anc.n_years))
            continue
        r = o.loc[m]
        if pd.isna(r.lat) or pd.isna(r.lon) or not r.heat_fuel_MWh > 0:
            raise ValueError(f"{m}: no coordinates or no LL84 heating fuel - cannot be connected")
        steam = r.main_fuel == "steam"
        eta = P["eta_steam"] if steam else P["eta_gas"]
        D_u = float(r.heat_fuel_MWh) * eta
        units = float(r.units_res) if pd.notna(r.units_res) else 0.0
        if r.is_residential and pd.notna(r.units_res) and D_u > 0:
            f_base = min(P["dhw_share_cap_residential"], units * D["q_dhw_apt"] / D_u)
        else:
            f_base = b_nonres
        if P["exclude_pilot_served"] and m == "2831044":
            # 291 Fulton apartments already get hot water from the Con Ed pilot loop (85 10th Ave): not new demand
            keep = 1 - P["pilot_apartments_already_served"] / units
            dhw_old = D_u * f_base
            D_u = D_u - dhw_old * (1 - keep)
            f_base, units = dhw_old * keep / D_u, units * keep
        if P["li_definition"] == "abc":
            li = units if (bool(r.is_nycha) or bool(r.dac)) else 0.0
        else:   # strict: only households that are verifiably low-income (NYCHA); DAC-tract market-rate units are context
            li = units if bool(r.is_nycha) else 0.0
        rows.append(dict(pid=m, name=r.property_name, use=r.use_type, fuel="steam" if steam else "gas", heating=r.sh_system,
                         rebuilt=False, eta=eta, D_useful=D_u, f_base=f_base, units=units, li_units=li, dac=bool(r.dac),
                         community=bool(r.community), nycha=bool(r.is_nycha), lat=r.lat, lon=r.lon,
                         lotarea_ft2=r.lotarea_ft2, n_years=r.n_years))
    b = pd.DataFrame(rows)
    if not len(b):
        return b
    b["D_dhw"] = b.D_useful * b.f_base
    b["D_sh"] = b.D_useful - b.D_dhw
    # temperature compatibility (hard rule): steam radiators cannot take low-temperature space heat
    b["sh_class"] = np.select([b.rebuilt, b.heating.eq("hydronic_assumed")], ["sh45", "sh_exist"], default="none")
    b["D_sh_served"] = np.where(b.sh_class == "none", 0.0, b.D_sh)
    return b


# ------------------------------------------------------------------ route (street-following MST)
def route_length(b: pd.DataFrame, P: dict) -> float:
    site = (P["lat"], P["lon"])
    ext = [tuple(P["lot_half_extent_m"])]
    pts = [site]
    for r in b.itertuples():
        if r.pid == P["property_id"]:
            continue
        pts.append((r.lat, r.lon))
        a = float(r.lotarea_ft2) * 0.0929 if pd.notna(r.lotarea_ft2) else 900.0
        if a >= 150_000 * 0.0929:
            ext.append((122.0, 30.0))
        else:
            ay = min(30.0, math.sqrt(a) / 2)
            ext.append((a / (4 * ay), ay))
    key = {}
    for i, p in enumerate(pts):                     # co-located points (two rebuild sites on one campus) merge
        key.setdefault((round(p[0], 6), round(p[1], 6)), i)
    idx = sorted(set(key.values()))
    if len(idx) < 2:
        return 0.0
    lat0 = site[0]
    xy = np.array([((pts[i][1] - site[1]) * 111_320 * math.cos(math.radians(lat0)), (pts[i][0] - lat0) * 110_540) for i in idx])
    th = math.radians(29.0)
    rot = xy @ np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    E = np.array([ext[i] for i in idx])
    d = np.abs(rot[:, None, :] - rot[None, :, :])
    if P["route_mode"] == "facade":
        d = np.clip(d - E[:, None, :] - E[None, :, :], 0, None)
        L = np.maximum(d.sum(axis=2), P["min_route_edge_m"])
    else:
        L = d.sum(axis=2)
    n, tree, total = len(idx), {0}, 0.0
    while len(tree) < n:
        c, j = min((L[i, j], j) for i in tree for j in range(n) if j not in tree)
        total += c
        tree.add(j)
    return float(total)


# ------------------------------------------------------------------ simulation (temperature-bin energy balance)
def simulate(members: list[str], P: dict) -> dict:
    D = data()
    b = buildings(members, P)
    bn = bins(P["availability"], P["bin_width_C"])
    hours = bn.hours.to_numpy(float)
    hdh_h = bn.hdh_per_h.to_numpy(float)
    hdh_tot = float(D["weather"].HDH_18C.sum())
    sh_peak_factor = max(P["t_balance_C"] - D["T_design"], float(D["weather"].HDH_18C.max())) / hdh_tot

    P_DC = D["E_el_src"] / HOURS * P["dc_share"]                 # MW (flat)
    Q_raw = P_DC * P["f_heat"]
    Q_avail = Q_raw * P["f_capture"]
    internal = list(members) == [P["property_id"]]
    route = 0.0 if internal or not len(b) else route_length(b, P)
    loss = P["dist_loss_per_km"] * route / 1000                   # share of extracted heat lost in the loop

    T = {"dhw": P["dhw_C"], "sh45": P["sh_new_C"], "sh_exist": P["sh_exist_C"]}
    streams = []
    p_el = P["elec_price"]
    for i, r in (b.iterrows() if len(b) else []):
        for cls, ann in (("dhw", r.D_dhw), (r.sh_class, r.D_sh_served)):
            if cls == "none" or ann <= 0:
                continue
            c = cop(T[cls], P)
            if cls == "dhw":
                load = np.full(len(bn), ann / HOURS)
                peak = ann / HOURS
                cap = P["hp_frac_dhw"] * peak
            else:
                load = ann * hdh_h / hdh_tot
                peak = ann * sh_peak_factor
                cap = P["hp_frac_sh"] * peak
            if r.rebuilt:
                v = p_el / D["cost"]["ashp_scop"]
            else:
                v = (D["price"]["steam"] * P["price_scale_steam"] if r.fuel == "steam" else D["price"]["gas"] * P["price_scale_gas"]) / r.eta
            merit = (v - p_el / c) / (1 - 1 / c)                    # $ per MWh of source heat (Model C merit rule)
            streams.append(dict(bi=i, cls=cls, cop=c, load=load, peak=peak, cap=cap, merit=merit))
    hx_cap = sum(s["cap"] * (1 - 1 / s["cop"]) for s in streams) * (1 + loss)
    src_left = np.where(bn.outage, 0.0, min(Q_avail, hx_cap)) * np.ones(len(bn))
    src_cap_bin = src_left.copy()
    for s in sorted(streams, key=lambda s: -s["merit"]):
        need = (1 - 1 / s["cop"]) * (1 + loss)                    # DC heat per MWh delivered (incl. loop loss)
        qmax = np.minimum(s["cap"], src_left / need)
        q = np.minimum(s["load"], qmax)
        s["q"], s["src"] = q, q * need
        s["backup"] = s["load"] - q
        s["unserved"] = np.maximum(0.0, s["backup"] - s["peak"])   # backup sized to 100% of design peak (H2)
        src_left = src_left - s["src"]

    def tot(key, mask=None):
        return float(sum((s[key] * hours).sum() for s in streams if mask is None or mask(s)))
    Q_del = tot("q")
    Q_src = tot("src")
    E_HP = float(sum((s["q"] / s["cop"] * hours).sum() for s in streams))
    E_pump = P["aux_elec_frac"] * Q_del
    E_src = P["source_elec_per_MWh_src"] * Q_src
    Q_loss = Q_src * loss / (1 + loss)
    D_served = float(sum((s["load"] * hours).sum() for s in streams))
    Q_bk = tot("backup")
    # design-hour electric demand with the source available (grid planning case)
    q_design = [min(s["cap"], s["peak"]) for s in streams]
    e_design = sum(q / s["cop"] + P["aux_elec_frac"] * q + P["source_elec_per_MWh_src"] * q * (1 - 1 / s["cop"]) * (1 + loss)
                   for q, s in zip(q_design, streams))
    # per-building totals
    if len(b):
        for col in ("Q_del", "Q_src", "E_HP", "Q_backup", "HP_cap", "peak_served", "unserved"):
            b[col] = 0.0
        for s in streams:
            i = s["bi"]
            b.loc[i, "Q_del"] += (s["q"] * hours).sum()
            b.loc[i, "Q_src"] += (s["src"] * hours).sum()
            b.loc[i, "E_HP"] += (s["q"] / s["cop"] * hours).sum()
            b.loc[i, "Q_backup"] += (s["backup"] * hours).sum()
            b.loc[i, "unserved"] += (s["unserved"] * hours).sum()
            b.loc[i, "HP_cap"] += s["cap"]
            b.loc[i, "peak_served"] += s["peak"]
    bal_bin = (sum(s["q"] - s["src"] / (1 + loss) - s["q"] / s["cop"] for s in streams) if streams else np.zeros(len(bn)))
    return dict(
        members=list(members), b=b, streams=streams, bins=bn, route_m=route, internal=internal, loss_frac=loss,
        P_DC=P_DC, Q_raw=Q_raw * HOURS, Q_avail=float((np.where(bn.outage, 0, Q_avail) * hours).sum()), E_IT=P_DC * HOURS / 1.5,
        Q_del=Q_del, Q_src=Q_src, Q_loss=Q_loss, E_HP=E_HP, E_pump=E_pump, E_src=E_src, Q_backup=Q_bk, D_served=D_served,
        D_useful=float(b.D_useful.sum()) if len(b) else 0.0, hx_cap=hx_cap, HP_cap=float(sum(s["cap"] for s in streams)),
        unserved=tot("unserved"), e_design_MW=e_design,
        src_violation=float(max(0.0, (sum(s["src"] for s in streams) - src_cap_bin).max())) if streams else 0.0,
        balance_err=float(np.abs(bal_bin).max()) if streams else 0.0,
        monthly=_monthly(bn, streams, hours, Q_avail),
    )


def _monthly(bn, streams, hours, Q_avail) -> pd.DataFrame:
    m = pd.DataFrame({"month": bn.month, "hours": hours})
    m["demand"] = sum(s["load"] for s in streams) * hours if streams else 0.0
    m["delivered"] = sum(s["q"] for s in streams) * hours if streams else 0.0
    m["source_used"] = sum(s["src"] for s in streams) * hours if streams else 0.0
    m["source_available"] = np.where(bn.outage, 0, Q_avail) * hours
    return m.groupby("month")[["demand", "delivered", "source_used", "source_available"]].sum().reset_index()


# ------------------------------------------------------------------ economics + environment + social
def crf(r: float, n: float) -> float:
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def economics(sim: dict, P: dict) -> dict:
    D = data()
    C, b = D["cost"], sim["b"].copy() if len(sim["b"]) else sim["b"]
    p_el, k = P["elec_price"], crf(P["discount_rate"], D["cost"]["life"])
    markup = 1 + P["contingency_frac"] + P["soft_cost_frac"]
    ef_grid = D["ef"]["grid"] * P["grid_ef_scale"]
    out = dict(crf=k, markup=markup)
    if not len(b):
        return dict(out, **{x: 0.0 for x in ("gross_savings", "avoided_conv_capex_ann", "new_opex", "capex_ann", "net_value", "capex_total",
                                               "co2_base", "co2_proj", "co2_avoided", "gas_displaced_MWh", "li_households", "facilities")}, b=b)
    ex = ~b.rebuilt
    price = np.where(b.fuel == "steam", D["price"]["steam"] * P["price_scale_steam"], D["price"]["gas"] * P["price_scale_gas"])
    ef_fuel = np.where(b.fuel == "steam", D["ef"]["steam"], D["ef"]["gas"])
    served = b.D_dhw + b.D_sh_served
    # ---- baseline (served scope only; unserved space heat is identical with and without the network)
    base_fuel = np.where(ex, served / b.eta, 0.0)
    ashp_el = np.where(ex, 0.0, served / C["ashp_scop"])
    ashp_capex = np.where(ex, 0.0, b.peak_served * C["ashp_capex"] * markup * P["bld_capex_scale"])
    b["base_opex"] = base_fuel * price + np.where(ex, 0.0, b.peak_served * C["ashp_fom"] + served * C["ashp_vom"] + ashp_el * p_el)
    b["base_capex_ann"] = ashp_capex * k
    b["co2_base"] = base_fuel * ef_fuel + ashp_el * ef_grid
    # ---- project
    backup_fuel = np.where(ex, b.Q_backup / b.eta, b.Q_backup / P["eta_elec_boiler"])
    b["backup_cost"] = np.where(ex, backup_fuel * price, backup_fuel * p_el)
    b["E_pump"] = P["aux_elec_frac"] * b.Q_del
    b["E_src"] = P["source_elec_per_MWh_src"] * b.Q_src
    b["elec_cost"] = (b.E_HP + b.E_pump + b.E_src) * p_el
    nycha_ex = ex & b.nycha
    b["bld_capex"] = np.where(nycha_ex, b.units * C["nycha_per_apt"] * P["nycha_apt_capex_scale"],
                              b.HP_cap * C["hp_capex"] * P["bld_capex_scale"]) * markup
    b["hp_om"] = b.HP_cap * C["hp_fom"] + b.Q_del * C["hp_vom"]
    b["co2_proj"] = (b.E_HP + b.E_pump + b.E_src) * ef_grid + np.where(ex, backup_fuel * ef_fuel, backup_fuel * ef_grid)
    b["gas_displaced"] = np.where(ex & (b.fuel == "gas"), base_fuel - backup_fuel, 0.0)
    # ---- network side
    hx = sim["hx_cap"] * C["hx_per_MW"] * markup
    ec = (C["energy_centre"] if sim["route_m"] > 0 else 0.0) * markup
    pipe = sim["route_m"] * P["pipe_cost_per_route_m"] * markup
    net_capex = hx + ec + pipe
    net_om = P["network_om_frac"] * net_capex
    capex_total = net_capex + float(b.bld_capex.sum())
    # ---- the four separated money lines (resource view; transfers excluded)
    gross = float((b.base_opex - b.backup_cost).sum())                      # conventional energy + O&M no longer bought
    avoided_capex_ann = float(b.base_capex_ann.sum())                      # ASHP plant the rebuilt towers no longer need
    new_opex = float(b.elec_cost.sum() + b.hp_om.sum()) + net_om           # incl. source-side electricity (A17)
    capex_ann = capex_total * k
    net = gross + avoided_capex_ann - new_opex - capex_ann
    co2_b, co2_p = float(b.co2_base.sum()), float(b.co2_proj.sum())
    gas = float(b.gas_displaced.sum())
    return dict(out, b=b, capex_pipe=pipe, capex_hx=hx, capex_energy_centre=ec, capex_building=float(b.bld_capex.sum()),
                capex_network=net_capex, capex_total=capex_total, network_om=net_om,
                gross_savings=gross, avoided_conv_capex_ann=avoided_capex_ann, new_opex=new_opex, capex_ann=capex_ann, net_value=net,
                electricity_cost=float(b.elec_cost.sum()), source_elec_cost=float(b.E_src.sum() * p_el),
                co2_base=co2_b, co2_proj=co2_p, co2_avoided=co2_b - co2_p, gas_displaced_MWh=gas, nox_avoided_kg=gas * D["nox_kg_per_MWh"],
                li_households=float(b.li_units.sum()), dac_units=float(b.loc[b.dac, "units"].sum()), facilities=int(b.community.sum()),
                ashp_peak_MW=float(b.loc[~ex, "peak_served"].sum() / P.get("ashp_cop_design", 2.2)))


def stakeholders(sim: dict, ec: dict, P: dict) -> dict:
    """Transfers between actors (they cancel in the sum). Tariff = cost-reflective test, not an assumption:
    the user break-even tariff (max a user can pay without losing) vs the operator break-even tariff."""
    D = data()
    b, k = ec["b"], ec["crf"]
    if not len(b) or sim["internal"]:
        return dict(dc_net=ec["net_value"] if sim["internal"] else 0.0, users_net=0.0, operator_net=0.0, transfer_check=0.0,
                    user_breakeven_tariff=np.nan, operator_breakeven_tariff=np.nan, subsidy_needed=max(0.0, -ec["net_value"]))
    p_el = P["elec_price"]
    fence = P["fence_price_per_MMBtu"] / MWH_PER_MMBTU
    loop = b.Q_src - b.Q_src * sim["loss_frac"] / (1 + sim["loss_frac"])   # heat arriving at buildings' evaporators
    owner_capex = np.where(b.rebuilt, b.bld_capex * k, 0.0)                    # developer builds rebuilt plant; operator funds retrofits
    user_pre = (b.base_opex + b.base_capex_ann - b.backup_cost - (b.E_HP + b.E_pump) * p_el - b.hp_om - owner_capex)
    dc = fence * sim["Q_src"] - sim["E_src"] * p_el
    op_cost = fence * sim["Q_src"] + ec["capex_network"] * k + float(np.where(b.rebuilt, 0.0, b.bld_capex).sum()) * k + ec["network_om"]
    lq = float(loop.sum())
    user_be = float(user_pre.sum()) / lq if lq > 0 else np.nan
    op_be = op_cost / lq if lq > 0 else np.nan
    tariff = D["cost"]["tariff"]
    users = float(user_pre.sum()) - tariff * lq - D["cost"]["connection"] * len(b)
    oper = tariff * lq + D["cost"]["connection"] * len(b) - op_cost
    return dict(dc_net=dc, users_net=users, operator_net=oper, transfer_check=dc + users + oper - ec["net_value"],
                user_breakeven_tariff=user_be, operator_breakeven_tariff=op_be, pilot_tariff=tariff, fence_price=fence,
                subsidy_needed=max(0.0, -ec["net_value"]), loop_heat_MWh=lq)


# ------------------------------------------------------------------ indicators and hard constraints
INDICATORS = [  # id, dimension, name, unit, formula
    ("I1", "Technical", "Useful heat delivered from recovered heat", "GWh/yr", "sum over bins of heat-pump output to loads"),
    ("I2", "Technical", "Recovery-plant load factor (seasonal match / continuity)", "%", "Q_extracted / (HX capacity x 8760)"),
    ("I3", "Economic + Delivery", "Net annual system value (resource view)", "$k/yr", "gross savings + avoided conventional capex - new opex - annualised capex"),
    ("I4", "Economic + Delivery", "Up-front capital", "$M", "network + building-side capex incl. contingency and soft costs"),
    ("I5", "Environmental", "Net CO2 avoided", "tCO2e/yr", "baseline CO2 of served demand - (electricity incl. source side x grid EF + backup fuel x EF)"),
    ("I6", "Environmental", "System efficiency (heat delivered per MWh of added electricity)", "MWh/MWh", "Q_delivered / (E_HP + E_pump + E_source)"),
    ("I7", "Social + Regenerative", "Low-income households served", "households", "NYCHA apartments (rebuild: replacement + affordable units)"),
    ("I8", "Social + Regenerative", "Community facilities served", "count", "schools, hospitals, care facilities, cultural buildings connected"),
]


def evaluate(members: list[str], P: dict) -> dict:
    sim = simulate(members, P)
    ec = economics(sim, P)
    st = stakeholders(sim, ec, P)
    e_add = sim["E_HP"] + sim["E_pump"] + sim["E_src"]
    ind = dict(
        I1=sim["Q_del"] / 1000,
        I2=100 * sim["Q_src"] / (sim["hx_cap"] * HOURS) if sim["hx_cap"] > 0 else 0.0,
        I3=ec["net_value"] / 1000, I4=ec["capex_total"] / 1e6, I5=ec["co2_avoided"],
        I6=sim["Q_del"] / e_add if e_add > 0 else np.nan, I7=ec["li_households"], I8=ec["facilities"],
    )
    b = ec["b"]
    con = {
        "HC1_cooling_independent": sim["src_violation"] < 1e-9,     # network never needs more than the DC rejects; towers kept
        "HC2_backup_full_peak": sim["unserved"] < 1e-6,              # backup = 100% of served design peak, incl. outage hours
        "HC3_energy_balance": sim["balance_err"] < 1e-9,
        "HC4_dhw_60C": P["dhw_C"] >= 60,
        "HC5_temperature_compatible": bool((b.loc[b.heating.eq("steam_radiators"), "D_sh_served"] == 0).all()) if len(b) else True,
        # energy conservation: no connected building may emit more than its counterfactual (no hiding in a portfolio)
        "HC6_no_emission_increase": bool((b.co2_base - b.co2_proj > 0).all()) if len(b) else True,
    }
    return dict(sim=sim, econ=ec, stake=st, ind=ind, con=con, feasible=all(con.values()))


def summary_row(label: str, r: dict) -> dict:
    s, e, st = r["sim"], r["econ"], r["stake"]
    row = dict(config=label, members="|".join(s["members"]), n_buildings=len(s["members"]),
               names="; ".join(s["b"].name) if len(s["b"]) else "", route_m=s["route_m"])
    row.update({k: v for k, v in r["ind"].items()})
    row.update(heat_extracted_MWh=s["Q_src"], heat_delivered_MWh=s["Q_del"], backup_MWh=s["Q_backup"], loop_loss_MWh=s["Q_loss"],
               D_useful_connected_MWh=s["D_useful"], D_served_MWh=s["D_served"], E_HP_MWh=s["E_HP"], E_pump_MWh=s["E_pump"], E_src_MWh=s["E_src"],
               HP_cap_MW=s["HP_cap"], HX_cap_MW=s["hx_cap"], design_hour_elec_MW=s["e_design_MW"], erf_pct=100 * s["Q_src"] / s["E_IT"])
    for k in ("gross_savings", "avoided_conv_capex_ann", "new_opex", "capex_ann", "net_value", "capex_total", "capex_pipe", "capex_hx",
              "capex_energy_centre", "capex_building", "electricity_cost", "source_elec_cost", "co2_avoided", "gas_displaced_MWh",
              "nox_avoided_kg", "li_households", "dac_units", "facilities"):
        row[k] = e.get(k, 0.0)
    for k in ("dc_net", "users_net", "operator_net", "user_breakeven_tariff", "operator_breakeven_tariff", "subsidy_needed"):
        row[k] = st.get(k, np.nan)
    row["abatement_cost_per_t"] = (-e["net_value"] / e["co2_avoided"]) if e.get("co2_avoided", 0) > 0 else np.nan
    row.update({k: v for k, v in r["con"].items()})
    row["feasible"] = r["feasible"]
    return row
