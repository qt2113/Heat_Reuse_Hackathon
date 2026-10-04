"""Model B - economic, environmental and stakeholder-value accounting (second module of A -> B -> C).

Reads Model A outputs and the data layer; computes, for every Model A run:
  * CAPEX, OPEX, LCOH, annual savings, simple payback        (system / resource view)
  * baseline vs project CO2 (LL97 factors), NOx, ERF, winter peak vs all-electric
  * separate cash flows for the data center, heat users, network operator, and community values
  * affordability (H6) and financial-feasibility checks (F1-F4)

Boundary and baseline (identical in every scenario)
  * Scope = the demand the network can serve in the connected buildings (DHW + space-heat classes from
    Model A). Heat that stays on today's system (steam radiators) is identical with and without the
    network and is left out on both sides.
  * Baseline = today's fuel (Con Ed steam at the pilot-implied marginal price, gas at the EIA NY
    commercial price) for existing buildings; an all-electric air-source heat pump for rebuilt towers
    (FAQ: new buildings move to electric heating).
  * System view counts resources only: capital, O&M, electricity (incl. source-side), backup fuel.
    Heat-sale revenue (fence price), tariffs and connection charges are transfers between actors:
    they appear only in the stakeholder view, where they cancel (validated: sum of actors = system).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import features as F

MWH_PER_MMBTU = 1 / 3.412142
OUT_A = F.ROOT / "outputs" / "model_a"


def crf(r: float, n: float) -> float:
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def load_inputs() -> dict:
    D = F.DATA
    dea = pd.read_csv(D / "processed" / "equipment_dea_heat.csv")
    dea = dea[dea.year == 2025].pivot_table(index="ws", columns="parameter", values="ctrl")
    mac = pd.read_csv(D / "processed" / "macro_cpi_fx.csv").set_index("year")
    k_usd = float(mac.loc[2020, "usd_per_eur"] * mac.loc[2020, "cpi_factor_to_latest_full_year"])   # EUR2020 -> USD2025
    bench = pd.read_csv(D / "processed" / "chelsea_uten_benchmarks.csv").set_index("metric").value
    pilot = pd.read_csv(D / "reference" / "chelsea_uten_pilot_stage2.csv").set_index("metric").value
    prices = pd.read_csv(D / "processed" / "energy_prices_ny_summary.csv").set_index("parameter").value
    ll97 = pd.read_csv(D / "reference" / "ll97_emission_coefficients.csv").set_index("fuel").tCO2e_per_MWh
    ap42 = pd.read_csv(D / "reference" / "ap42_natural_gas_boilers.csv")
    fec = pd.read_csv(D / "reference" / "fec_rebuild_facts.csv").set_index("metric").value
    dac = pd.read_csv(D / "processed" / "dac_tracts_1km.csv", dtype={"geoid": str}).set_index("geoid")
    pluto = pd.read_csv(D / "processed" / "pluto_lots_1km.csv", dtype={"bbl": str, "tract_geoid": str}).set_index("bbl").tract_geoid
    offt = pd.read_csv(F.ROOT / "outputs" / "features" / "offtakers_features.csv", dtype={"property_id": str}).set_index("property_id")

    hp_w = dea.loc["40 Comp. hp, waste heat 3 MW"]
    hp_a = dea.loc["40 Comp. hp, airsource 3 MW"]
    src_cap_MW = float(pilot["source_low_grade_capacity"]) * 1000 / 3.412142 / 1e6   # 5,000 MBH -> MW
    return dict(
        k_usd=k_usd,
        hp_capex=float(hp_w.capex_MEUR_per_MWth) * 1e6 * k_usd,               # $/MW water-source HP (DEA, installed)
        hp_fom=float(hp_w.fixed_om_EUR_per_MWth_yr) * k_usd,                   # $/MW/yr
        hp_vom=float(hp_w.var_om_EUR_per_MWhth) * k_usd,                       # $/MWh
        life=float(hp_w.lifetime_yr),
        ashp_capex=float(hp_a.capex_MEUR_per_MWth) * 1e6 * k_usd,
        ashp_fom=float(hp_a.fixed_om_EUR_per_MWth_yr) * k_usd, ashp_vom=float(hp_a.var_om_EUR_per_MWhth) * k_usd,
        ashp_scop=float(hp_a.cop_or_efficiency_annual),
        hx_capex=float(pilot["thermal_resource_construction"]) * 1e6 / src_cap_MW,  # $/MW of interface (pilot)
        src_cap_MW=src_cap_MW,
        ec_capex=float(pilot["energy_center_construction"]) * 1e6,             # $ per networked scheme (pilot)
        apt_capex=float(bench["customer_building_cost_per_apartment"]),        # $/apt existing NYCHA retrofit (pilot)
        contingency=0.15,                                                      # pilot (S13 p.89)
        steam_price=float(bench["implied_marginal_steam_cost_per_MWh_steam"]),  # $/MWh steam (pilot-implied)
        gas_price=float(prices["gas_commercial_USD_MWh_fuel_12mo_mean"]),      # $/MWh fuel (EIA)
        tariff=float(pilot["customer_thermal_rate"]) * 3.412142,                # $/MWh of loop heat (pilot $26.63/MMBtu)
        connection=float(pilot["customer_fixed_connection_charge"]),           # $/building/yr (pilot)
        ef={"steam": float(ll97["district_steam"]), "gas_or_oil": float(ll97["natural_gas"]),
            "grid": float(ll97["electricity_grid"])},
        nox=float(ap42.query("pollutant=='NOx' and control=='uncontrolled'").kg_per_MWh_fuel.iloc[0]),
        n_replacement=float(fec["existing_NYCHA_apartments_replaced"]), n_new=float(fec["new_mixed_income_units_up_to"]),
        n_affordable_new=float(fec["new_affordable_apartments_approx"]),
        dac=dac, pluto=pluto, offt=offt,
    )


def tract_of(pid: str, I: dict) -> str | None:
    base = pid.split(":")[-1]
    if base not in I["offt"].index:
        return None
    first_bbl = str(I["offt"].loc[base, "bbl"]).split(";")[0].strip()
    return I["pluto"].get(first_bbl)


def b_params(level: dict[str, str] | None = None) -> dict:
    a = F.assumption_values(level)
    return dict(A05=a["A05"], A06=a["A06"], A07=a["A07"], A08=a["A08"], A09=a["A09"], A12=a["A12"], A21=a["A21"], A22=a["A22"])


def evaluate(run: pd.Series, sysr: pd.Series, bld: pd.DataFrame, P: dict, I: dict, b_set: str = "base") -> dict:
    """All Model B quantities for one Model A run under B-parameter set P."""
    p_el, r = P["A07"], P["A08"]
    tariff = P.get("tariff", I["tariff"])                    # $/MWh of loop heat (pilot rate)
    fence = P["A06"] * 3.412142                               # A06 $/MMBtu -> $/MWh
    k = crf(r, I["life"])
    k_net = crf(r, P["network_life"]) if P.get("network_life") else k   # optional: pipe/interface life != heat-pump life
    markup = 1 + I["contingency"] + P["A21"]
    scen = run.scenario
    internal = bool(run.get("internal", scen == "S1"))      # source owner = only heat user: no operator, no transfers

    b = bld.copy()
    if len(b):
        b["served_useful_MWh"] = b.D_dhw_MWh + b.D_sh_served_MWh
        b["price_fuel"] = np.where(b.main_fuel == "steam", I["steam_price"], I["gas_price"])
        ex = ~b.rebuilt.astype(bool)
        # ---------- baseline (served scope)
        b["base_fuel_MWh"] = np.where(ex, b.served_useful_MWh / b.eta_base, 0.0)
        b["base_cost"] = np.where(ex, b.base_fuel_MWh * b.price_fuel, 0.0)
        ashp_cap = b.peak_served_MW
        ashp_el = b.served_useful_MWh / I["ashp_scop"]
        b["base_capex"] = np.where(ex, 0.0, ashp_cap * I["ashp_capex"] * markup)
        b["base_cost"] += np.where(ex, 0.0, b.base_capex * k + ashp_cap * I["ashp_fom"] + b.served_useful_MWh * I["ashp_vom"] + ashp_el * p_el)
        b["base_co2"] = np.where(ex, b.base_fuel_MWh * b.main_fuel.map(I["ef"]).fillna(I["ef"]["gas_or_oil"]), ashp_el * I["ef"]["grid"])
        # ---------- project, building side
        b["bld_capex"] = np.where(ex & b.is_nycha.astype(bool), b.units * I["apt_capex"], b.HP_cap_MW * I["hp_capex"]) * markup
        b["bld_capex_funder"] = np.where(ex, "operator", "owner")           # pilot: utility funds retrofits; developer builds new towers
        b["hp_om"] = b.HP_cap_MW * I["hp_fom"] + b.Q_network_MWh * I["hp_vom"]
        b["elec_cost"] = (b.E_HP_MWh + b.E_pump_MWh) * p_el
        b["backup_cost"] = np.where(b.backup_type == "electric_boiler", b.backup_fuel_MWh * p_el, b.backup_fuel_MWh * b.price_fuel)
        b["proj_co2"] = (b.E_HP_MWh + b.E_pump_MWh + b.E_src_MWh) * I["ef"]["grid"] + np.where(
            b.backup_type == "electric_boiler", b.backup_fuel_MWh * I["ef"]["grid"],
            b.backup_fuel_MWh * b.main_fuel.map(I["ef"]).fillna(I["ef"]["gas_or_oil"]))
        b["gas_displaced_MWh"] = np.where(ex & (b.main_fuel == "gas_or_oil"), b.base_fuel_MWh - b.backup_fuel_MWh, 0.0)
        # ---------- transfers (stakeholder view only)
        b["tariff_paid"] = 0.0 if internal else b.Q_loop_MWh * tariff
        b["connection_paid"] = 0.0 if internal else I["connection"]
        if P.get("nycha_tariff_rule", "pilot") == "affordability_cap" and not internal:
            # Term 4: NYCHA pays at most its break-even loop-heat rate and no connection charge;
            # the operator's lost revenue shows up as external funding need (nothing is hidden).
            ny_ = b.is_nycha.astype(bool)
            un0 = (b.base_cost - b.backup_cost - b.elec_cost - b.hp_om
                   - np.where(b.bld_capex_funder == "owner", b.bld_capex * k, 0.0))
            t_be = np.where(b.Q_loop_MWh > 0, un0 / b.Q_loop_MWh.where(b.Q_loop_MWh > 0), 0.0)
            t_i = np.clip(t_be, 0.0, tariff)
            b["tariff_paid"] = np.where(ny_, b.Q_loop_MWh * t_i, b.tariff_paid)
            b["connection_paid"] = np.where(ny_, 0.0, b.connection_paid)
        b["user_net"] = (b.base_cost - b.backup_cost - b.elec_cost - b.hp_om
                         - np.where(b.bld_capex_funder == "owner", b.bld_capex * k, 0.0)
                         - b.tariff_paid - b.connection_paid)
        units = b.units.where(b.units > 0)
        b["user_net_per_apt"] = b.user_net / units
        b["tract"] = [tract_of(pid, I) for pid in b.property_id]
        b["dac_pct"] = [I["dac"].percentile_rank_combined.get(t, np.nan) if t else np.nan for t in b.tract]
        b["dac_flag"] = [I["dac"].dac_designation.get(t, "") == "Designated as DAC" if t else False for t in b.tract]
        # low-income households: NYCHA apartments today; rebuilt = replacement + new affordable share of units
        li_share_new = (I["n_replacement"] + I["n_affordable_new"]) / (I["n_replacement"] + I["n_new"])
        b["low_income_hh"] = np.where(ex, np.where(b.is_nycha.astype(bool) | b.dac_flag, b.units, 0.0), b.units * li_share_new)
    # ---------- network side (operator-funded)
    if P.get("hx_scale_exp"):                                # optional: scale economies from the pilot's interface size
        hx_capex = I["hx_capex"] * I["src_cap_MW"] * (sysr.HX_cap_MW / I["src_cap_MW"]) ** P["hx_scale_exp"] * markup
    else:
        hx_capex = sysr.HX_cap_MW * I["hx_capex"] * markup
    ec_capex = (I["ec_capex"] if sysr.route_m > 0 else 0.0) * markup
    pipe_capex = sysr.route_m * P["A05"] * markup
    net_capex = hx_capex + ec_capex + pipe_capex
    net_om = P["A22"] * net_capex
    bld_capex_total = float(b.bld_capex.sum()) if len(b) else 0.0
    op_bld_capex = float(b.loc[b.bld_capex_funder == "operator", "bld_capex"].sum()) if len(b) else 0.0
    capex_total = net_capex + bld_capex_total
    hp_om = float(b.hp_om.sum()) if len(b) else 0.0
    om_total = net_om + hp_om
    elec_total = (sysr.E_HP_MWh + sysr.E_pump_MWh + sysr.E_src_MWh) * p_el
    backup_cost = float(b.backup_cost.sum()) if len(b) else 0.0
    base_cost = float(b.base_cost.sum()) if len(b) else 0.0
    capex_ann = net_capex * k_net + bld_capex_total * k
    proj_cost = capex_ann + om_total + elec_total + backup_cost
    savings = base_cost - proj_cost
    op_savings = base_cost - (om_total + elec_total + backup_cost)
    Qn = sysr.Q_network_MWh
    lcoh = (capex_ann + om_total + elec_total) / Qn if Qn > 0 else np.nan
    served = float(b.served_useful_MWh.sum()) if len(b) else 0.0

    # ---------- actors (transfers cancel in the sum)
    fence_paid = 0.0 if internal else sysr.Q_DC_used_MWh * fence
    tariff_rev = float(b.tariff_paid.sum()) if len(b) else 0.0
    conn_rev = float(b.connection_paid.sum()) if len(b) else 0.0
    dc_net = fence_paid - sysr.E_src_MWh * p_el
    users_net = float(b.user_net.sum()) if len(b) else 0.0
    op_net = tariff_rev + conn_rev - fence_paid - (net_capex * k_net + op_bld_capex * k) - net_om
    if internal:                                             # S1: one owner; all network costs sit with the building
        users_net -= net_capex * k_net + op_bld_capex * k + net_om
        op_net = 0.0

    # ---------- environment
    base_co2 = float(b.base_co2.sum()) if len(b) else 0.0
    proj_co2 = float(b.proj_co2.sum()) if len(b) else 0.0
    gas_disp = float(b.gas_displaced_MWh.sum()) if len(b) else 0.0
    p_design = sysr.P_at_design_hour_MW + sysr.E_src_at_design_hour_MW
    peak_served = float(b.peak_served_MW.sum()) if len(b) else 0.0
    n6 = peak_served / P["A12"] - p_design if len(b) else np.nan
    erf = sysr.Q_DC_used_MWh / sysr.E_IT_MWh if sysr.E_IT_MWh > 0 else np.nan

    # ---------- affordability and feasibility
    ny = b[b.is_nycha.astype(bool)] if len(b) else b
    ny_net = float(ny.user_net.sum()) if len(ny) else np.nan
    ny_apts = float(ny.units.sum()) if len(ny) else 0.0
    ny_loop = float(ny.Q_loop_MWh.sum()) if len(ny) else 0.0
    breakeven_tariff = (ny_net + float(ny.tariff_paid.sum())) / ny_loop if ny_loop > 0 else np.nan
    li = float(b.low_income_hh.sum()) if len(b) else 0.0
    w = b.Q_network_MWh if len(b) else None
    ej = float(np.average(b.dac_pct.fillna(0), weights=w)) if len(b) and w.sum() > 0 and b.dac_pct.notna().any() else np.nan

    econ = dict(
        run_id=run.run_id, b_set=b_set, scenario=scen, hp_frac=run.hp_frac, tank_hours=run.tank_hours,
        assumption_set=run.assumption_set,
        capex_network=net_capex, capex_interface=hx_capex, capex_energy_centre=ec_capex, capex_pipe=pipe_capex,
        capex_building_side=bld_capex_total, capex_total=capex_total, crf=k,
        capex_annualised=capex_ann, om_annual=om_total, electricity_cost=elec_total, backup_fuel_cost=backup_cost,
        project_cost_annual=proj_cost, baseline_cost_annual=base_cost, annual_savings=savings,
        annual_operating_savings=op_savings, simple_payback_yr=(capex_total / op_savings) if op_savings > 0 else np.inf,
        served_useful_MWh=served, network_heat_MWh=Qn, lcoh_system=lcoh,
        baseline_cost_per_MWh=base_cost / served if served > 0 else np.nan,
        fence_price_per_MWh=fence, tariff_per_MWh=tariff,
        fence_revenue=fence_paid, tariff_revenue=tariff_rev, connection_revenue=conn_rev,
        source_electricity_cost=sysr.E_src_MWh * p_el, operator_capex_annualised=net_capex * k_net + op_bld_capex * k, network_om=net_om,
        dc_net=dc_net, users_net=users_net, operator_net=op_net, public_funding_need=max(0.0, -op_net),
        actors_sum=dc_net + users_net + op_net,
        nycha_net=ny_net, nycha_apartments=ny_apts, nycha_net_per_apt=(ny_net / ny_apts) if ny_apts else np.nan,
        nycha_breakeven_tariff_per_MWh=breakeven_tariff,
        co2_baseline=base_co2, co2_project=proj_co2, co2_avoided=base_co2 - proj_co2,
        gas_displaced_MWh=gas_disp, nox_avoided_kg=gas_disp * I["nox"], erf=erf,
        peak_vs_ashp_MW=n6, network_peak_at_design_MW=p_design,
        low_income_households=li, ej_dac_percentile=ej,
        ll97_upper_bound_commercial=float(((b.base_co2 - b.proj_co2) * (~b.is_nycha.astype(bool)) * (~b.rebuilt.astype(bool))).sum()) * 268 if len(b) else 0.0,
    )
    return dict(econ=econ, buildings=b)


KPI_DEF = [  # id, dimension, name, unit, source column / model
    ("T1", "Technical", "Recoverable heat", "GWh/yr", "A:T1_recoverable_heat_GWh"),
    ("T2", "Technical", "Seasonal heat-pump COP", "-", "A:T2_SCOP"),
    ("T4", "Technical", "Hourly demand coverage (served classes)", "%", "A:T4_coverage_pct"),
    ("T7", "Technical", "Network route length", "m", "A:T7_route_m"),
    ("C1", "Economic + Delivery", "CAPEX per kW of heat-pump capacity", "$/kWth", "B:capex_per_kW"),
    ("C2", "Economic + Delivery", "Levelised cost of heat (system)", "$/MWh", "B:lcoh_system"),
    ("C3", "Economic + Delivery", "Annual saving vs current heat cost", "%", "B:saving_pct"),
    ("N1", "Environmental", "Energy Reuse Factor", "%", "B:erf_pct"),
    ("N2", "Environmental", "Net CO2 avoided", "tCO2e/yr", "B:co2_avoided"),
    ("N4", "Environmental", "On-site gas combustion displaced", "MWh/yr", "B:gas_displaced_MWh"),
    ("N6", "Environmental", "Winter peak avoided vs all-electric ASHP", "MW", "B:peak_vs_ashp_MW"),
    ("S1", "Social + Regenerative", "Low-income households served", "households", "B:low_income_households"),
    ("S3", "Social + Regenerative", "EJ exposure of served buildings (DAC percentile, heat-weighted)", "0-1", "B:ej_dac_percentile"),
    ("S5", "Social + Regenerative", "Acceptance & governance", "qualitative", "B:b_delivery_assessment"),
    ("S6", "Social + Regenerative", "Rebuild design-window fit", "qualitative", "B:b_delivery_assessment"),
    ("S7", "Social + Regenerative", "Net value to the data center", "$/yr", "B:dc_net"),
]
