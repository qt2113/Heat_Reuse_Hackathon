"""Model C - offtaker selection (planning) + heat allocation (operation) + explainable multi-criteria choice.

Planning level : which candidate buildings to connect. Every subset of a screened shortlist is evaluated
                 (exhaustive enumeration; 2^9-2^10 configurations per horizon), separately for two horizons
                 that cannot coexist physically: 'today' (existing NYCHA buildings) and 'post_rebuild'
                 (the rebuilt Fulton / Elliott-Chelsea campus replaces them).
Operation level: for each configuration Model A allocates the finite data-center heat hour by hour
                 (policy="merit": building-level streams in order of net value per MWh of source heat).
Evaluation     : Model B economics/carbon/stakeholder value -> feasibility screening -> 13 indicators in
                 four dimensions -> min-max normalisation over the enumerated set -> dimension scores ->
                 user-weighted overall score. Weights only re-rank configurations; they never change the
                 physical or economic results of a configuration.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from . import features as F
from . import model_a as MA
from . import model_b as MB

DIMS = ("Technical", "Economic + Delivery", "Environmental", "Social + Regenerative")
DIM_KEY = {"Technical": "T", "Economic + Delivery": "E", "Environmental": "N", "Social + Regenerative": "S"}
COMMUNITY_USES = {"K-12 School", "College/University", "Library", "Museum", "Worship Facility", "Residential Care Facility",
                  "Social/Meeting Hall", "Pre-school/Daycare", "Hospital (General Medical & Surgical)"}

# id, dimension, name, unit, direction, level, formula, source
INDICATORS = [
    ("T_cov", "Technical", "Recovered-heat share of connected buildings' heat", "%", "max", "network",
     "100 x Q_network / D_useful_connected", "A: a_annual_system.Q_network_MWh, D_useful_connected_MWh"),
    ("T_lf", "Technical", "Seasonal load factor of the heat-recovery interface", "%", "max", "network",
     "100 x Q_DC_used / (HX_cap x 8760)", "A: Q_DC_used_MWh, HX_cap_MW"),
    ("T_bk", "Technical", "Backup dependency of served demand", "%", "min", "network",
     "100 x (Q_backup + Q_unserved) / D_served_classes", "A: Q_backup_MWh, Q_unserved_MWh, D_served_classes_MWh"),
    ("E_lcoh", "Economic + Delivery", "Levelised cost of network heat (system)", "$/MWh", "min", "network",
     "(CAPEX x CRF + O&M + electricity incl. source side) / Q_network", "B: b_economics.lcoh_system"),
    ("E_val", "Economic + Delivery", "Annual net economic value (system, vs today)", "$/yr", "max", "network",
     "baseline cost of served demand - (annualised CAPEX + O&M + electricity + backup fuel)", "B: annual_savings"),
    ("E_fund", "Economic + Delivery", "External funding needed by the network operator", "$/yr", "min", "stakeholder",
     "max(0, -(tariff + connection - fence payments - operator capex x CRF - network O&M))", "B: public_funding_need"),
    ("N_co2", "Environmental", "Net CO2 avoided (LL97 factors)", "tCO2e/yr", "max", "network",
     "baseline CO2 of served demand - (electricity x 0.289 + backup fuel x EF)", "B: co2_avoided"),
    ("N_erf", "Environmental", "Energy Reuse Factor", "%", "max", "network",
     "100 x Q_DC_used / E_IT", "B: erf"),
    ("N_gas", "Environmental", "On-site gas combustion displaced", "MWh/yr", "max", "network",
     "sum over gas buildings of (baseline fuel of served demand - backup fuel)", "B: gas_displaced_MWh"),
    ("S_li", "Social + Regenerative", "Low-income households benefited", "households", "max", "building",
     "NYCHA / DAC apartments connected (rebuild: replacement + new affordable share)", "B: low_income_households"),
    ("S_aff", "Social + Regenerative", "NYCHA heating-cost change per apartment", "$/apt/yr", "max", "stakeholder",
     "NYCHA users' net value / NYCHA apartments (0 when none connected)", "B: nycha_net_per_apt"),
    ("S_eq", "Social + Regenerative", "Share of network heat delivered to low-income / DAC buildings", "%", "max", "network",
     "100 x Q_network(NYCHA or DAC buildings) / Q_network", "A+B: b_building_bills"),
    ("S_fac", "Social + Regenerative", "Community facilities served", "count", "max", "building",
     "number of connected schools, universities, museums, care facilities", "features: use_type"),
]
CONTEXT = ["capex_total", "route_m", "dc_net", "operator_net", "users_net", "simple_payback_yr", "nox_avoided_kg",
           "peak_vs_ashp_MW", "nycha_breakeven_tariff_per_MWh", "Q_network_MWh", "Q_DC_used_MWh", "D_useful_connected_MWh"]


# ------------------------------------------------------------------ screening
SCREENING_KEYS = ("search_radius_m", "max_candidates", "min_annual_heat_demand_gwh", "max_candidates_per_building_type")


def screening_params(cfg: dict, overrides: dict | None = None) -> dict:
    """Reference screening parameters from config/scenarios.yaml, optionally overridden (sensitivity runs)."""
    p = {k: cfg["screening"][k] for k in SCREENING_KEYS}
    p.update(overrides or {})
    if set(p) != set(SCREENING_KEYS):
        raise ValueError(f"unknown screening parameter(s): {sorted(set(p) - set(SCREENING_KEYS))}")
    if not 0 < p["search_radius_m"] <= 1000:
        raise ValueError("search_radius_m must be in (0, 1000]: the LL84 feature table stops at 1 km")
    return p


def screen_candidates(offt: pd.DataFrame, A: dict, weather: pd.DataFrame, q_dhw_apt: float, site_pid: str,
                      params: dict) -> pd.DataFrame:
    """Explicit, reproducible shortlist. Every record gets a status and a reason."""
    radius, max_n = params["search_radius_m"], params["max_candidates"]
    min_mwh, per_type = 1000 * params["min_annual_heat_demand_gwh"], params["max_candidates_per_building_type"]
    b_nonres = F.nonres_base_share(weather, A["A20"])
    t = offt.copy()
    eta = np.where(t.main_fuel == "steam", A["A04"], 0.85)
    t["D_useful_MWh"] = t.heat_fuel_MWh * eta
    f_res = np.minimum(0.6, t.units_res.fillna(0) * q_dhw_apt / t.D_useful_MWh.replace(0, np.nan))
    t["f_base"] = np.where(t.is_residential & t.units_res.notna(), f_res, b_nonres)
    t["servable_share"] = np.where(t.sh_system == "hydronic_assumed", 1.0, t.f_base)
    t["servable_MWh"] = t.D_useful_MWh * t.servable_share
    t["screen_index"] = t.servable_MWh / (t.dist_m + 50)
    reasons = []
    for r in t.itertuples():
        if r.property_id == site_pid:
            reasons.append("")
        elif not (r.dist_m <= radius):
            reasons.append("outside the 1 km study area" if radius == 1000 else f"outside the {radius:g} m search radius")
        elif r.n_years < 2:
            reasons.append(f"insufficient data: only {r.n_years} year of LL84 records")
        elif not (r.heat_fuel_MWh >= min_mwh):
            reasons.append(f"heat demand below {min_mwh / 1000:g} GWh/yr (too small for a street connection)")
        elif pd.isna(r.lat) or pd.isna(r.lon):
            reasons.append("missing coordinates")
        else:
            reasons.append("")
    t["exclusion_reason"] = reasons
    elig = t[t.exclusion_reason == ""].copy()
    cat = np.select([elig.is_nycha, elig.use_type.eq("Multifamily Housing"), elig.use_type.isin(COMMUNITY_USES)],
                    ["NYCHA", "Residential", "Community"], default=elig.use_type)
    elig["category"] = cat
    chosen = [site_pid] + list(elig.loc[elig.is_nycha, "property_id"])
    counts: dict = {}
    for r in elig.sort_values("screen_index", ascending=False).itertuples():
        if len(chosen) >= max_n:
            break
        if r.property_id in chosen:
            continue
        if per_type is not None and counts.get(r.category, 0) >= per_type:
            continue
        chosen.append(r.property_id)
        counts[r.category] = counts.get(r.category, 0) + 1
    t["status"] = "excluded"
    t.loc[t.exclusion_reason == "", "status"] = "eligible_not_shortlisted"
    t.loc[t.property_id.isin(chosen), "status"] = "shortlisted"
    rank = elig.sort_values("screen_index", ascending=False).property_id.tolist()
    t["screen_rank"] = t.property_id.map({p: i + 1 for i, p in enumerate(rank)})
    t.loc[t.status == "eligible_not_shortlisted", "exclusion_reason"] = (
        "eligible but below the shortlist cut (rank " + t.screen_rank.astype("Int64").astype(str) + " by servable heat per metre"
        + (f", max {per_type} per building type)" if per_type is not None else ")"))
    t["category"] = t.property_id.map(dict(zip(elig.property_id, elig.category)))
    return t


# ------------------------------------------------------------------ evaluation of one configuration
def dispatch_values(I: dict, A: dict) -> dict:
    """$ of displaced heat per useful MWh, used only to order hourly allocation (Model A merit policy)."""
    return {"steam": I["steam_price"] / A["A04"], "gas_or_oil": I["gas_price"] / 0.85, "new_electric": A["A07"] / I["ashp_scop"]}


def evaluate_config(members: tuple, horizon: str, ctx: dict, return_streams: bool = False) -> dict:
    cfg, bundle, A, I, P = ctx["cfg"], ctx["bundle"], ctx["A"], ctx["I"], ctx["P"]
    ref = cfg["reference_design"]
    existing = [m for m in members if not m.startswith("rebuild:")]
    rebuilt = [m for m in members if m.startswith("rebuild:")]
    scen = {"members": existing}
    if rebuilt:
        rb = cfg["scenarios"]["S3R"]["rebuild"]
        scen["rebuild"] = dict(rb, sites=[s for s in rb["sites"] if f"rebuild:{s['anchor_property_id']}" in rebuilt])
    cid = config_id(horizon, members)
    spec = MA.RunSpec(cid, cid, ref["hp_frac"], ref["tank_hours"])
    fuel = ctx["offt"].set_index("property_id").main_fuel
    dv = {m: ctx["dv"][fuel.get(m, "gas_or_oil")] for m in existing}
    dv.update({m: ctx["dv"]["new_electric"] for m in rebuilt})
    res = MA.simulate(spec, cfg, bundle, A, scen_override=scen, policy="merit", dispatch_value=dv, return_streams=return_streams)
    s = pd.Series(res["summary"])
    run = pd.Series(dict(run_id=cid, scenario=cid, hp_frac=ref["hp_frac"], tank_hours=ref["tank_hours"], assumption_set="base",
                         internal=(tuple(existing) == (cfg["site"]["property_id"],) and not rebuilt)))
    ev = MB.evaluate(run, s, res["buildings"], P, I)
    return dict(id=cid, members=members, summary=s, buildings=ev["buildings"], econ=ev["econ"], constraints=res["constraints"],
                streams=res.get("streams"), hourly=res["hourly"])


def config_id(horizon: str, members: tuple) -> str:
    return f"{horizon}|" + "+".join(sorted(m.replace("rebuild:", "R") for m in members)) if members else f"{horizon}|none"


def indicators(r: dict, ctx: dict) -> dict:
    s, e, b = r["summary"], r["econ"], r["buildings"]
    uses = ctx["offt"].set_index("property_id").use_type
    con = r["constraints"].set_index("constraint_id").status
    tech_ok = all(con.get(k) == "pass" for k in ("H1", "H2", "H3", "H4", "H5", "H7"))
    has_ny = e["nycha_apartments"] > 0
    internal = bool(r.get("internal", False))
    F1 = e["annual_savings"] > 0
    F2 = True if internal else e["operator_net"] >= 0
    F3 = (e["dc_net"] + e["users_net"] >= 0) if internal else e["dc_net"] >= 0
    H6 = (e["nycha_net"] >= 0) if has_ny else True
    q = s.Q_network_MWh
    eq = float(b.loc[b.is_nycha.astype(bool) | b.dac_flag.astype(bool), "Q_network_MWh"].sum()) / q * 100 if len(b) and q > 0 else 0.0
    fac = int(sum(uses.get(m, "") in COMMUNITY_USES for m in r["members"]))
    out = dict(
        config_id=r["id"], n_buildings=len(r["members"]), members="|".join(r["members"]),
        names="; ".join(b.name) if len(b) else "",
        T_cov=100 * q / s.D_useful_connected_MWh if s.D_useful_connected_MWh > 0 else 0.0,
        T_lf=100 * s.Q_DC_used_MWh / (s.HX_cap_MW * 8760) if s.HX_cap_MW > 0 else 0.0,
        T_bk=100 * (s.Q_backup_MWh + s.Q_unserved_MWh) / s.D_served_classes_MWh if s.D_served_classes_MWh > 0 else 100.0,
        E_lcoh=e["lcoh_system"], E_val=e["annual_savings"], E_fund=e["public_funding_need"],
        N_co2=e["co2_avoided"], N_erf=100 * e["erf"], N_gas=e["gas_displaced_MWh"],
        S_li=e["low_income_households"], S_aff=e["nycha_net_per_apt"] if has_ny else 0.0, S_eq=eq, S_fac=fac,
        tech_ok=tech_ok, F1_society=F1, F2_operator=F2, F3_data_center=F3, H6_affordability=H6 if has_ny else None,
        balance_max_abs=s.balance_max_abs, actors_gap=abs(e["actors_sum"] - e["annual_savings"]),
        Q_loop_sum_gap=abs(float(b.Q_loop_MWh.sum()) - s.Q_DC_used_MWh) if len(b) else 0.0,
        capex_pipe=e["capex_pipe"], capex_interface=e["capex_interface"], crf=e["crf"],
        source_electricity_cost=e["source_electricity_cost"], electricity_cost=e["electricity_cost"],
        fence_price_per_MWh=e["fence_price_per_MWh"], tariff_per_MWh=e["tariff_per_MWh"],
    )
    for k in CONTEXT:
        out[k] = e.get(k, s.get(k, np.nan))
    out["route_m"] = s.route_m
    if not tech_ok:
        out["feasibility"] = "infeasible"
    elif F1 and F2 and F3 and H6:
        out["feasibility"] = "fully_feasible"
    else:
        out["feasibility"] = "conditionally_feasible"
    out["failed_checks"] = ";".join([k for k, v in (("F1 society savings", F1), ("F2 operator self-financing", F2),
                                                     ("F3 data-center value", F3), ("H6 NYCHA affordability", H6)) if not v]
                                    + [k for k in ("H1", "H2", "H3", "H4", "H5", "H7") if con.get(k) != "pass"])
    out.update(conditions(out, e, ctx))
    return out


def conditions(o: dict, e: dict, ctx: dict) -> dict:
    """What would have to change for a technically feasible configuration to pass the financial checks."""
    P, I = ctx["P"], ctx["I"]
    deficit = max(0.0, -e["annual_savings"])
    k = e["crf"]
    markup = 1 + I["contingency"] + P["A21"]
    levers = {
        "pipe_cost": e["capex_pipe"] * k,
        "interface_cost": e["capex_interface"] * k,
        "source_side_electricity (A17 -> 0)": e["source_electricity_cost"],
        "soft_costs (A21 -> 0)": e["capex_total"] * k * P["A21"] / markup,
    }
    txt = []
    for name, ann in levers.items():
        if deficit <= 0:
            break
        if ann > 0:
            need = deficit / ann
            txt.append(f"{name}: -{100 * need:.0f}% closes F1" if need <= 1 else f"{name}: removing it entirely closes only {100 / need:.0f}% of the gap")
    gap_all = deficit - sum(levers.values())
    el_MWh = e["electricity_cost"] / P["A07"] if P["A07"] else 0.0
    return dict(
        f1_carbon_price_to_close=(deficit / e["co2_avoided"]) if deficit > 0 and e["co2_avoided"] > 0 else np.nan,
        f1_electricity_price_to_close=(P["A07"] - deficit / el_MWh) if deficit > 0 and el_MWh > 0 else np.nan,
        f1_deficit=deficit,
        f1_levers="; ".join(txt),
        f1_closable_by_levers=bool(deficit > 0 and gap_all <= 0),
        funding_needed_per_household=(e["public_funding_need"] / e["low_income_households"]) if e["low_income_households"] > 0 else np.nan,
        fence_increase_for_F3=(max(0.0, -e["dc_net"]) / e["Q_DC_used_MWh"]) if e.get("Q_DC_used_MWh") else np.nan,
    )


# ------------------------------------------------------------------ scoring (weights never touch physical results)
def check_weights(w: dict) -> dict:
    if set(w) != set(DIMS):
        raise ValueError(f"weights must cover exactly {DIMS}")
    if any(v < 0 for v in w.values()) or abs(sum(w.values()) - 1) > 1e-9:
        raise ValueError("weights must be non-negative and sum to 100%")
    return w


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Min-max over the technically feasible configurations of a horizon (incl. today = empty network)."""
    out = df.copy()
    pool = df[df.tech_ok | (df.n_buildings == 0)]
    for iid, dim, *_rest in INDICATORS:
        direction = next(x[4] for x in INDICATORS if x[0] == iid)
        x = pool[iid].astype(float)
        lo, hi = np.nanmin(x), np.nanmax(x)
        v = df[iid].astype(float)
        n = (v - lo) / (hi - lo) if hi > lo else pd.Series(0.0, index=df.index)
        if direction == "min":
            n = 1 - n
        out[f"n_{iid}"] = n.fillna(0.0).clip(0, 1)
    for d in DIMS:
        cols = [f"n_{i[0]}" for i in INDICATORS if i[1] == d]
        out[f"score_{DIM_KEY[d]}"] = out[cols].mean(axis=1)
    return out


def overall(df: pd.DataFrame, w: dict) -> pd.Series:
    check_weights(w)
    return sum(w[d] * df[f"score_{DIM_KEY[d]}"] for d in DIMS)


def choose(df: pd.DataFrame, w: dict) -> dict:
    sc = overall(df, w)
    cand = df[df.n_buildings > 0]
    full = cand[cand.feasibility == "fully_feasible"]
    if len(full):
        best = sc.loc[full.index].idxmax()
        return dict(config_id=df.loc[best, "config_id"], status="fully_feasible", score=float(sc[best]), message="")
    cond = cand[cand.feasibility == "conditionally_feasible"]
    msg = "No fully feasible configuration under the current assumptions."
    if len(cond):
        best = sc.loc[cond.index].idxmax()
        return dict(config_id=df.loc[best, "config_id"], status="conditionally_feasible", score=float(sc[best]), message=msg)
    return dict(config_id=None, status="none", score=np.nan, message=msg + " No technically feasible configuration either.")


def pareto(df: pd.DataFrame) -> pd.Series:
    cols = [f"score_{DIM_KEY[d]}" for d in DIMS]
    pool = df[(df.n_buildings > 0) & df.tech_ok]
    X = pool[cols].to_numpy()
    nd = np.ones(len(X), bool)
    for i in range(len(X)):
        dom = (X >= X[i]).all(axis=1) & (X > X[i]).any(axis=1)
        nd[i] = not dom.any()
    s = pd.Series(False, index=df.index)
    s.loc[pool.index[nd]] = True
    return s


def weight_grid(step: float = 0.1):
    n = int(round(1 / step))
    for a, b, c in itertools.product(range(n + 1), repeat=3):
        d = n - a - b - c
        if d >= 0:
            yield dict(zip(DIMS, (a * step, b * step, c * step, d * step)))


PRESETS = {
    "equal (demonstration baseline)": dict(zip(DIMS, (0.25, 0.25, 0.25, 0.25))),
    "technical-first": dict(zip(DIMS, (0.55, 0.15, 0.15, 0.15))),
    "economic-first": dict(zip(DIMS, (0.15, 0.55, 0.15, 0.15))),
    "environmental-first": dict(zip(DIMS, (0.15, 0.15, 0.55, 0.15))),
    "social-first": dict(zip(DIMS, (0.15, 0.15, 0.15, 0.55))),
}
