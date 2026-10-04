"""Export the final A -> B -> C results as ONE frontend-ready file: outputs/final_integration/abc_results.json (+ a flat CSV).

Every scenario is re-evaluated through the production chain (Model A hourly allocation -> Model B economics -> Model C indicators),
so the numbers are the corrected-model numbers, not a copy of an earlier output. Nothing here changes a model.

    python -m model.export_abc_results

Definitions (the frontend must not rename them)
  heat_recovered_MWh   data-center waste heat taken out of the cooling loop (Model A Q_DC_used). Positive, even when the money is negative.
  heat_delivered_MWh   heat the connected buildings receive from the network (heat-pump output = recovered heat + compressor electricity).
  net_co2_avoided_t    baseline fuel CO2 (LL97 factors; oil share at the oil factor) - grid CO2 of heat-pump, pump AND source-side electricity - backup CO2.
  net_societal_value   baseline heat cost - (annualised CAPEX + O&M + electricity incl. source side + backup energy). Resources only: LL97 fines,
                       tariffs, fence payments and subsidies are transfers and are not in it. Recovered heat is NOT counted as savings by itself.
"""
from __future__ import annotations

import json
import math
import time

import numpy as np
import pandas as pd

from . import features as F
from . import model_c as MC
from .run_model_c import build_ctx
from .run_redesign import make_ctx

OUT = F.ROOT / "outputs" / "final_integration"
SITE = "7536925"
FULTON, ELLIOTT = "2831044", "4473909"
SCHEMA = "abc_results/1.0"


def _f(x, nd=1):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), nd)


def pilot_overlap_fn(ctx):
    return lambda o: F.remove_pilot_overlap(o.copy(), ctx["A"])


def route_geometry(site: dict, pts: list[dict], rotation_deg: float) -> dict:
    """Same minimum spanning tree as features.route_length_m (L1 on the rotated Manhattan grid), returned as L-shaped polylines (schematic)."""
    uniq = {}
    for p in [dict(id="source", lat=site["lat"], lon=site["lon"])] + pts:
        uniq.setdefault((round(p["lat"], 6), round(p["lon"], 6)), p)
    P = list(uniq.values())
    if len(P) < 2:
        return dict(length_m=0.0, polylines=[], method="none")
    lat0 = site["lat"]
    kx, ky = 111_320 * math.cos(math.radians(lat0)), 110_540
    xy = np.array([((p["lon"] - site["lon"]) * kx, (p["lat"] - lat0) * ky) for p in P])
    th = math.radians(rotation_deg)
    R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    rot = xy @ R
    dist = np.abs(rot[:, None, :] - rot[None, :, :]).sum(axis=2)
    tree, edges, total = {0}, [], 0.0
    while len(tree) < len(P):
        d, i, j = min((dist[i, j], i, j) for i in tree for j in range(len(P)) if j not in tree)
        edges.append((i, j))
        total += d
        tree.add(j)

    def ll(v):
        x, y = v @ R.T
        return [round(lat0 + y / ky, 6), round(site["lon"] + x / kx, 6)]
    lines = []
    for i, j in edges:
        corner = np.array([rot[j, 0], rot[i, 1]])
        lines.append(dict(from_id=P[i]["id"], to_id=P[j]["id"], latlon=[ll(rot[i]), ll(corner), ll(rot[j])], length_m=_f(dist[i, j], 0)))
    return dict(length_m=_f(total, 0), polylines=lines,
                method="minimum spanning tree, L1 distance on the Manhattan grid rotated 29 deg; drawn as L-shaped legs. Schematic: not street-graph routing")


def monthly(h: pd.DataFrame, weather: pd.DataFrame, A: dict) -> dict:
    mo = weather.month.to_numpy()
    def m(series):
        return [_f(series[mo == k].sum(), 1) for k in range(1, 13)]
    delivered = (h.Q_HP_to_load_MW + h.Q_discharge_MW).to_numpy()
    return dict(months=list(range(1, 13)), heat_recovered_MWh=m(h.Q_DC_used_MW.to_numpy()), heat_delivered_MWh=m(delivered),
                backup_heat_MWh=m(h.Q_backup_MW.to_numpy()), building_heat_demand_MWh=m(h.D_total_MW.to_numpy()),
                electricity_heat_pumps_pumps_MWh=m((h.E_HP_MW + h.E_pump_MW).to_numpy()), electricity_source_side_MWh=m((A["A17"] * h.Q_DC_used_MW).to_numpy()))


def scenario_record(key, label, status, description, members, horizon, ctx, notes=None, assumptions=None) -> dict:
    cfg, offt = ctx["cfg"], ctx["offt"].set_index("property_id")
    r = MC.evaluate_config(tuple(members), horizon, ctx)
    r["internal"] = tuple(m for m in members) == (SITE,)
    ind = MC.indicators(r, ctx)
    s, e, b = r["summary"], r["econ"], r["buildings"].copy()
    I, A = ctx["I"], ctx["A"]
    # fuel displaced by type (served scope: baseline fuel not burnt any more)
    disp = {"steam_MWh": 0.0, "gas_MWh": 0.0, "oil_MWh": 0.0}
    for x in b.itertuples():
        if bool(x.rebuilt):
            continue
        d = float(x.base_fuel_MWh - x.backup_fuel_MWh)
        if x.main_fuel == "steam":
            disp["steam_MWh"] += d
        else:
            g, o = float(offt.loc[x.property_id, "gas_MWh"]), float(offt.loc[x.property_id, "oil_MWh"])
            so = o / max(g + o, 1e-9)
            disp["oil_MWh"] += d * so
            disp["gas_MWh"] += d * (1 - so)
    blds, pts = [], []
    for x in b.itertuples():
        pid = x.property_id
        base = pid.replace("rebuild:", "")
        row = offt.loc[base] if base in offt.index else None
        lat, lon = (float(row.lat), float(row.lon)) if row is not None and pd.notna(row.lat) else (None, None)
        use = "Multifamily Housing (rebuilt, modelled)" if bool(x.rebuilt) else (str(row.use_type) if row is not None else "")
        community = (not bool(x.rebuilt)) and use in MC.COMMUNITY_USES
        blds.append(dict(
            id=pid, name=x.name if not pid.startswith("rebuild:") else ("Rebuilt Fulton" if pid.endswith(FULTON) else "Rebuilt Elliott-Chelsea"),
            role="source and offtaker" if pid == SITE else "offtaker", lat=lat, lon=lon, use_type=use,
            households=_f(x.units, 0) if float(x.units) > 0 else 0, low_income_households=_f(x.low_income_hh, 0), is_nycha=bool(x.is_nycha),
            community_facility=bool(community), rebuilt=bool(x.rebuilt), heating_system=str(x.sh_system),
            main_fuel_today=str(x.main_fuel), backup=str(x.backup_type),
            heat_from_network_MWh=_f(x.Q_network_MWh, 0), backup_heat_MWh=_f(x.Q_backup_MWh, 0),
            share_of_served_heat_from_network=_f(x.share_heat_from_network, 3), heat_pump_MW=_f(x.HP_cap_MW, 2),
            annual_bill_change_usd=_f(x.user_net, 0), distance_to_source_m=_f(row.dist_m, 0) if row is not None else None))
        if pid != SITE and lat is not None:
            pts.append(dict(id=pid, lat=lat, lon=lon))
    pipe = route_geometry(cfg["site"], pts, cfg["physics"]["grid_rotation_deg"])
    served = float(s.D_served_classes_MWh)
    houses = float(b.loc[b.units > 0, "units"].sum())
    facilities = [bb["name"] for bb in blds if bb["community_facility"]]
    support = max(0.0, -float(e["annual_savings"]))
    con = r["constraints"].set_index("constraint_id").status.to_dict()
    unserved = float(s.Q_unserved_MWh)
    rec = dict(
        key=key, label=label, status=status, description=description, horizon=horizon, members=list(members), notes=notes or [],
        primary=dict(
            waste_heat_recovered_MWh_per_year=_f(s.Q_DC_used_MWh, 0),
            useful_heat_delivered_MWh_per_year=_f(s.Q_network_MWh, 0),
            net_co2_avoided_t_per_year=_f(e["co2_avoided"], 0),
            co2_baseline_t_per_year=_f(e["co2_baseline"], 0), co2_project_t_per_year=_f(e["co2_project"], 0),
            net_annual_societal_value_usd_per_year=_f(e["annual_savings"], 0),
            community_beneficiaries=dict(households_served=_f(houses, 0), low_income_households=_f(e["low_income_households"], 0),
                                         community_facilities=len(facilities), community_facility_names=facilities)),
        secondary=dict(
            cop_seasonal=_f(s.T2_SCOP, 2), lcoh_usd_per_MWh=_f(e["lcoh_system"], 0),
            capex_total_usd=_f(e["capex_total"], 0), capex_network_usd=_f(e["capex_network"], 0), capex_building_side_usd=_f(e["capex_building_side"], 0),
            capex_annualised_usd_per_year=_f(e["capex_annualised"], 0),
            opex_usd_per_year=_f(e["om_annual"] + e["electricity_cost"] + e["backup_fuel_cost"], 0),
            opex_breakdown_usd_per_year=dict(om=_f(e["om_annual"], 0), electricity_heat_pumps_pumps=_f(e["electricity_cost"] - e["source_electricity_cost"], 0),
                                             electricity_source_side=_f(e["source_electricity_cost"], 0), backup_energy=_f(e["backup_fuel_cost"], 0)),
            baseline_heat_cost_usd_per_year=_f(e["baseline_cost_annual"], 0),
            funding_gap_usd_per_year=dict(operator_gap_at_tariff=_f(e["public_funding_need"], 0), minimum_public_support=_f(support, 0),
                                          note="minimum_public_support = max(0, -net societal value); operator_gap_at_tariff depends on the heat-price rules (stakeholder view)"),
            fuel_displaced_MWh_per_year=dict(total=_f(sum(disp.values()), 0), **{k: _f(v, 0) for k, v in disp.items()}),
            coverage=dict(recovered_heat_share_of_connected_demand_pct=_f(ind["T_cov"], 1), network_share_of_served_demand_pct=_f(100 * s.Q_network_MWh / served, 1) if served else None),
            backup_reliability=dict(backup_share_of_served_demand_pct=_f(ind["T_bk"], 1), unserved_heat_MWh=_f(unserved, 1),
                                    technical_constraints={k: v for k, v in con.items()}, technical_feasible=bool(ind["tech_ok"]),
                                    note="buildings keep their own boilers/steam (existing) or electric boilers (rebuilt), so heat is never unserved; reliability = how little of the served heat depends on backup"),
            heat_recovery_interface_load_factor_pct=_f(ind["T_lf"], 1), energy_reuse_factor_pct=_f(ind["N_erf"], 2),
            feasibility=ind["feasibility"], failed_checks=ind["failed_checks"],
            hard_constraints=dict(HC0_external_offtaker=bool(ind["n_external"] >= 1), HC1_5_technical=bool(ind["tech_ok"]),
                                  HC6_co2_not_negative=bool(e["co2_avoided"] >= 0), HC7_nycha_no_worse_off=str(ind["H6_affordability"]) != "False"),
            net_value_to_data_center_usd=_f(e["dc_net"], 0), net_value_to_heat_users_usd=_f(e["users_net"], 0), net_value_to_operator_usd=_f(e["operator_net"], 0),
            cost_per_tCO2_avoided_usd=_f(support / e["co2_avoided"], 0) if e["co2_avoided"] > 0 and support > 0 else None),
        buildings=blds,
        pipeline=dict(route_length_m=_f(s.route_m, 0), capex_usd=_f(e["capex_pipe"], 0), heat_exchanger_MW=_f(s.HX_cap_MW, 2), **{k: v for k, v in pipe.items() if k != "length_m"}),
        monthly=monthly(r["hourly"], ctx["bundle"]["weather"], A),
        assumptions=dict(A17_source_electricity_MWh_per_MWh_extracted=_f(A["A17"], 3), capture_temperature_C=_f(A["A02"], 0),
                         electricity_price_usd_per_MWh=_f(ctx["P"]["A07"], 1), gas_price_usd_per_MWh_fuel=_f(I["gas_price"], 1), oil_price_usd_per_MWh_fuel=_f(I["oil_price"], 1),
                         steam_price_usd_per_MWh=_f(I["steam_price"], 1), pipe_cost_usd_per_m=_f(ctx["P"]["A05"], 0), discount_rate=ctx["P"]["A08"],
                         storage_hours=ctx["cfg"]["reference_design"]["tank_hours"], **(assumptions or {})))
    return rec


def main() -> None:
    t0 = time.time()
    ctx = build_ctx()
    cfg = ctx["cfg"]
    rec_json = json.loads((F.ROOT / "outputs" / "model_c" / "c_recommendations.json").read_text(encoding="utf-8"))
    rec = rec_json["today"]["recommendation"]
    rec_members = rec["members"].split("|")
    ext = [m for m in rec_members if m != SITE]
    ph = ctx["cfg"]["corrections"].get("pilot_overlap", False)
    ctx_no_pilot = make_ctx(ctx, offt_fn=pilot_overlap_fn(ctx))
    ctx_liquid = make_ctx(ctx, A=dict(A02=45.0, A17=0.0))
    S = []
    S.append(scenario_record("recommended", "Recommended: in-building reuse + M070 school", "recommended (main external offtaker candidate)",
                             "111 8th Ave heat reused in the building plus the M070 public school: chosen by the hard-constraint / least-public-support rule.",
                             rec_members, "today", ctx,
                             notes=["Needs public support: no network with an external offtaker pays for itself on current evidence.",
                                    f"Selected by Model C: {rec['rule']} (n={rec['n_pass']} configurations passed the hard constraints)."]))
    S.append(scenario_record("recommended_plus_dream_hotel", "Recommended + Dream Hotel (conditional)", "conditional",
                             "Adds the Dream Hotel (steam-heated). Conditional: its LL84 history is a single year with a large steam share.",
                             [SITE] + ext + ["4978579"], "today", ctx, notes=["Conditional on a second year of Dream Hotel data and on the hotel agreeing to hot-water-only service."]))
    S.append(scenario_record("internal_only", "In-building reuse only (111 8th Ave)", "reference",
                             "No external offtaker: the data-center building uses its own heat. Fails HC0 (needs at least one external offtaker) so is never recommended.",
                             [SITE], "today", ctx))
    S.append(scenario_record("rebuilt_fulton", "Rebuilt Fulton (future, with today's cooling technology)", "future scenario (technology-dependent)",
                             "The rebuilt Fulton / Elliott-Chelsea campus designed for 45 C space heat. Evaluated with the evidence-based source-side electricity (A17 = 0.367).",
                             [SITE, f"rebuild:{FULTON}"], "post_rebuild", ctx,
                             notes=["Net CO2 is negative at A17 = 0.367, so it fails HC6 and is never recommended in this configuration."]))
    S.append(scenario_record("rebuilt_fulton_liquid_cooling", "Rebuilt Fulton with warm-water liquid cooling (future technology)", "future scenario (speculative technology)",
                             "As above but the data center captures heat at 45 C by direct liquid cooling, so no compressor-forced extra electricity (A17 = 0).",
                             [SITE, f"rebuild:{FULTON}"], "post_rebuild", ctx_liquid,
                             notes=["Technology-dependent: outside the register range for capture temperature (A02 30 C base). Not a current-evidence result."],
                             assumptions=dict(technology="warm-water liquid cooling")))
    S.append(scenario_record("existing_fulton_pilot_double_count", "Existing Fulton as today's candidate, pilot demand claimed (default)", "labelled scenario",
                             "Existing Fulton houses served hot water only; the Con Ed pilot demand is still counted as available (as in the input data).",
                             [SITE, FULTON], "today", ctx,
                             notes=["Whether the pilot's 291 apartments are already served is not established operationally; the default does not subtract them."]))
    S.append(scenario_record("existing_fulton_pilot_removed", "Existing Fulton with pilot-served apartments removed", "labelled scenario",
                             "Same as above but the 291 apartments already on the Con Ed pilot loop are excluded from the demand.",
                             [SITE, FULTON], "today", ctx_no_pilot, assumptions=dict(pilot_overlap_removed=True),
                             notes=["Scenario only: applies the Con Ed pilot overlap (S13). Not the reference."]))
    heat = pd.read_csv(F.DATA / "processed" / "source_111_8th_annual.csv")
    doc = dict(
        schema=SCHEMA, generated=pd.Timestamp.now().isoformat(timespec="seconds"), seconds=round(time.time() - t0, 1),
        site=dict(name="111 8th Avenue", property_id=SITE, lat=cfg["site"]["lat"], lon=cfg["site"]["lon"], source_it_electricity_MWh_3yr_mean=_f(heat.electricity_MWh.mean(), 0)),
        recommended_scenario="recommended",
        decision_rule=dict(rule="hard constraints then least public support per tCO2 avoided", constraints=MC.HARD_CONSTRAINTS,
                           weights="the four-dimension weighted score is optional (sensitivity / visualisation only) and does not drive the recommendation"),
        definitions=dict(
            waste_heat_recovered="data-center waste heat extracted from the cooling loop (MWh/yr). Not net energy savings.",
            useful_heat_delivered="heat received by connected buildings from the network (MWh/yr). Higher than recovered heat because it includes heat-pump compressor input.",
            net_co2_avoided="baseline fuel CO2 minus grid CO2 of all added electricity (heat pumps, pumps and source side) minus backup CO2, LL97 factors, t/yr",
            net_annual_societal_value="baseline heat cost minus annualised CAPEX, O&M, all electricity and backup energy, USD/yr; negative means the system costs more than today's heating",
            community_beneficiaries="households served (all residential units connected), low-income households (NYCHA / rebuilt affordable share) and community facilities (schools etc.)"),
        corrections_applied=[
            "A17 = 0.367 MWh_e per MWh extracted (Con Ed pilot 666 MWh / 1,813.5 MWh injected); A17 = 0 only for the liquid-cooling scenario (capture 45 C)",
            "oil share of gas/oil buildings priced at the EIA NY heating-oil price and LL97 oil factor",
            "LL84 zero / isolated-anomaly years ignored (42 properties)",
            "existing NYCHA: hot-water-only retrofit cost; rebuilt towers: electric backup boilers costed; storage removed (it was not costed)",
            "Con Ed pilot demand NOT subtracted by default (scenario flag: corrections.pilot_overlap = " + str(ph).lower() + ")"],
        scenarios=S)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "abc_results.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    flat = []
    for sc in S:
        p, q = sc["primary"], sc["secondary"]
        flat.append(dict(key=sc["key"], label=sc["label"], status=sc["status"], horizon=sc["horizon"], members="|".join(sc["members"]),
                         waste_heat_recovered_MWh=p["waste_heat_recovered_MWh_per_year"], useful_heat_delivered_MWh=p["useful_heat_delivered_MWh_per_year"],
                         net_co2_avoided_t=p["net_co2_avoided_t_per_year"], net_societal_value_usd=p["net_annual_societal_value_usd_per_year"],
                         households_served=p["community_beneficiaries"]["households_served"], low_income_households=p["community_beneficiaries"]["low_income_households"],
                         community_facilities=p["community_beneficiaries"]["community_facilities"], cop=q["cop_seasonal"], lcoh_usd_per_MWh=q["lcoh_usd_per_MWh"],
                         capex_usd=q["capex_total_usd"], opex_usd_per_year=q["opex_usd_per_year"], minimum_public_support_usd=q["funding_gap_usd_per_year"]["minimum_public_support"],
                         fuel_displaced_MWh=q["fuel_displaced_MWh_per_year"]["total"], coverage_pct=q["coverage"]["recovered_heat_share_of_connected_demand_pct"],
                         backup_share_pct=q["backup_reliability"]["backup_share_of_served_demand_pct"], route_m=sc["pipeline"]["route_length_m"]))
    pd.DataFrame(flat).to_csv(OUT / "abc_results_summary.csv", index=False)
    print(pd.DataFrame(flat).drop(columns=["label", "members", "horizon"]).to_string(index=False))


if __name__ == "__main__":
    main()
