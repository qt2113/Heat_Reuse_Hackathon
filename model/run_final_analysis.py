"""Final analysis for the Site 1 proposal (no new datasets, no change to Models A/B/C results).

Stages (all outputs in outputs/final/; outputs/model_a|b|c are read, never written):
  audit     heat-flow definitions, cost decomposition, normalisation check of the Model C scores
  design    fixed-design check: heat-pump size x storage x service scope for the compared portfolios
  combined  joint Low/Base/High sensitivity of the influential assumptions + break-even conditions
  proposal  phased proposal vs minimum-cost, balanced and community-priority portfolios
  frontend  verified data bundle + contract for the interactive map

    python -m model.run_final_analysis --stage all
"""
from __future__ import annotations

import argparse
import itertools
import json
import shutil
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import features as F
from . import model_a as MA
from . import model_b as MB
from . import model_c as MC

OUT = F.ROOT / "outputs" / "final"
REF = F.ROOT / "outputs" / "model_c"
SITE = "7536925"
NAMES = {"7536925": "111 Eighth Avenue (source building)", "19906892": "363 West 16th Street (hotel)", "1634606": "M070 school",
         "1633052": "M440 school", "4040951": "Chelsea Market", "8899918": "61 9th Ave", "4769672": "London Terrace Towers",
         "2831044": "Fulton Houses (existing)", "4473909": "Elliott-Chelsea (existing)", "2830989": "Chelsea Houses",
         "rebuild:2831044": "Rebuilt Fulton", "rebuild:4473909": "Rebuilt Elliott-Chelsea"}


def _recs() -> dict:
    return json.loads((REF / "c_recommendations.json").read_text(encoding="utf-8"))


def _members(cid: str) -> list[str]:
    body = cid.split("|", 1)[1]
    return [] if body == "none" else [("rebuild:" + m[1:]) if m.startswith("R") else m for m in body.split("+")]


def portfolios() -> dict:
    r = _recs()
    return {
        "minimum_cost": dict(horizon="today", members=[SITE], role="lowest additional annual cost of any configuration (Model C enumeration)"),
        "minimum_cost_network": dict(horizon="today", members=[SITE, "1634606"], role="lowest additional annual cost with >= 2 buildings"),
        "proposal_phase1": dict(horizon="today", members=[SITE, "19906892"], role="proposal, phase 1 (2027-28)"),
        "proposal_phase2": dict(horizon="post_rebuild", members=[SITE, "19906892", "rebuild:2831044"], role="proposal, phase 2 (rebuild move-ins, A15)"),
        "proposal_phase2_school": dict(horizon="post_rebuild", members=[SITE, "19906892", "1634606", "rebuild:2831044"], role="proposal variant with M070"),
        "balanced": dict(horizon="post_rebuild", members=_members(r["post_rebuild"]["equal (demonstration baseline)"]["config_id"]),
                         role="equal-weights Model C recommendation, post-rebuild"),
        "balanced_today": dict(horizon="today", members=_members(r["today"]["equal (demonstration baseline)"]["config_id"]),
                               role="equal-weights Model C recommendation, today"),
        "community": dict(horizon="post_rebuild", members=_members(r["post_rebuild"]["social-first"]["config_id"]),
                          role="social-first Model C recommendation, post-rebuild"),
    }


def ctx_with(ctx: dict, levels: dict | None = None, dhw_only: list | None = None, design: dict | None = None) -> dict:
    """Context with assumption levels (register Low/Base/High), optional DHW-only service and design override."""
    c = dict(ctx)
    if levels:
        c["A"] = F.assumption_values(levels)
        c["P"] = dict(MB.b_params(levels), nycha_tariff_rule=ctx["P"]["nycha_tariff_rule"])
    if dhw_only:
        offt = ctx["offt"].copy()
        offt.loc[offt.property_id.isin(dhw_only) & (offt.sh_system == "hydronic_assumed"), "sh_system"] = "dhw_only_design"
        c["bundle"] = dict(ctx["bundle"], offtakers=offt)
        c["offt"] = offt
    if design:
        c["cfg"] = dict(ctx["cfg"], reference_design=dict(ctx["cfg"]["reference_design"], **design))
    return c


def evaluate(pf: dict, ctx: dict) -> dict:
    r = MC.evaluate_config(tuple(pf["members"]), pf["horizon"], ctx)
    r["internal"] = tuple(pf["members"]) == (SITE,)
    return dict(raw=r, ind=MC.indicators(r, ctx))


# ------------------------------------------------------------------ stage: audit
HEAT_DEF = [
    ("T1_recoverable_heat_GWh", "Recoverable heat", "data-center heat available at the capture interface (A01 share x 0.95 x 0.85 capture, outage hours removed)"),
    ("Q_DC_used_MWh", "Heat reused (= heat extracted)", "data-center heat actually taken into the ambient loop by the heat pumps; this is the numerator of the ERF"),
    ("E_HP_MWh", "Heat-pump electricity", "electricity added by the building heat pumps (becomes part of the delivered heat)"),
    ("Q_network_MWh", "Heat delivered", "heat delivered by the network heat pumps to buildings = heat reused + heat-pump electricity (incl. storage discharge)"),
    ("Q_backup_MWh", "Backup heat", "served-class demand met by existing boilers/steam (or new electric boilers in rebuilt towers)"),
    ("D_useful_connected_MWh", "Useful demand of connected buildings", "LL84 fuel x efficiency; includes space heat that steam radiators cannot take (H7)"),
    ("D_sh_not_served_MWh", "Demand outside the network scope", "space heat of steam-radiator buildings; stays on existing steam/boilers"),
    ("E_src_MWh", "Source-side electricity (A17)", "extra electricity at the data center per MWh of heat reused (0.25 x heat reused at Base)"),
]


def stage_audit(ctx: dict) -> None:
    rows, cost = [], []
    for name, pf in portfolios().items():
        e = evaluate(pf, ctx)
        s, ec = e["raw"]["summary"], e["raw"]["econ"]
        for col, label, definition in HEAT_DEF:
            v = float(s[col]) * (1000 if col.endswith("GWh") else 1)
            rows.append(dict(portfolio=name, quantity=label, column=col, MWh=round(v, 1), definition=definition))
        base, capex_ann, om, el, bk = ec["baseline_cost_annual"], ec["capex_annualised"], ec["om_annual"], ec["electricity_cost"], ec["backup_fuel_cost"]
        cost.append(dict(portfolio=name, members="; ".join(NAMES.get(m, m) for m in pf["members"]),
                         baseline_heat_cost=base, capex_annualised=capex_ann, capex_pipe=ec["capex_pipe"], capex_interface=ec["capex_interface"],
                         capex_energy_centre=ec["capex_energy_centre"], capex_building_side=ec["capex_building_side"],
                         om=om, electricity_heat_pumps_pumps=el - ec["source_electricity_cost"], electricity_source_A17=ec["source_electricity_cost"],
                         backup_fuel=bk, operating_margin_before_capital=base - om - el - bk, net_annual_value=ec["annual_savings"],
                         baseline_cost_per_MWh_served=ec["baseline_cost_per_MWh"], electricity_per_MWh_delivered=el / s.Q_network_MWh if s.Q_network_MWh else np.nan))
    pd.DataFrame(rows).to_csv(OUT / "audit_heat_flows.csv", index=False)
    pd.DataFrame(cost).to_csv(OUT / "audit_cost_decomposition.csv", index=False)

    # normalisation check: constant indicators (no information) should not dilute their dimension
    c = pd.read_csv(REF / "c_configurations.csv")
    out = []
    for h, g in c.groupby("horizon"):
        g = g.reset_index(drop=True)
        pool = g[g.tech_ok | (g.n_buildings == 0)]
        const = [i[0] for i in MC.INDICATORS if pool[i[0]].astype(float).nunique() <= 1]
        alt = g.copy()
        for d in MC.DIMS:
            cols = [f"n_{i[0]}" for i in MC.INDICATORS if i[1] == d and i[0] not in const]
            alt[f"score_{MC.DIM_KEY[d]}"] = alt[cols].mean(axis=1)
        for pname, w in MC.PRESETS.items():
            a, b = MC.choose(g, w), MC.choose(alt, w)
            out.append(dict(horizon=h, preset=pname, constant_indicators=";".join(const) or "none",
                            reference_choice=a["config_id"], choice_without_constant=b["config_id"], changed=a["config_id"] != b["config_id"],
                            social_score_max_reference=float(g.score_S.max()), social_score_max_without_constant=float(alt.score_S.max())))
    pd.DataFrame(out).to_csv(OUT / "audit_normalisation.csv", index=False)
    print("audit written")


# ------------------------------------------------------------------ stage: modes (cooling independence / backup for the portfolios)
def stage_modes(ctx: dict) -> None:
    """Model A operating modes M1-M5 (config/scenarios.yaml) run on each compared portfolio, merit dispatch."""
    cfg, bundle, A = ctx["cfg"], ctx["bundle"], ctx["A"]
    H, ref = F.HOURS, cfg["reference_design"]
    T = bundle["weather"].dry_bulb_C.to_numpy(float)
    wk = int(np.argmin(np.convolve(T, np.ones(168) / 168, mode="valid")))
    fuel = ctx["offt"].set_index("property_id").main_fuel
    rows = []
    for name, pf in portfolios().items():
        existing = [m for m in pf["members"] if not m.startswith("rebuild:")]
        rebuilt = [m for m in pf["members"] if m.startswith("rebuild:")]
        scen = {"members": existing}
        if rebuilt:
            rb = cfg["scenarios"]["S3R"]["rebuild"]
            scen["rebuild"] = dict(rb, sites=[s for s in rb["sites"] if f"rebuild:{s['anchor_property_id']}" in rebuilt])
        dv = {m: ctx["dv"][fuel.get(m, "gas_or_oil")] for m in existing} | {m: ctx["dv"]["new_electric"] for m in rebuilt}
        spec = MA.RunSpec(name, name, ref["hp_frac"], ref["tank_hours"])
        for mode, m in cfg["operating_modes"].items():
            stress, win = {}, np.zeros(H, bool)
            if "source_off_hours" in m:
                win[wk:wk + m["source_off_hours"]] = True
                stress["source_off"] = win.astype(float)
            elif "hp_scale" in m:
                win[wk:wk + m["hours"]] = True
                stress["hp_scale"] = np.where(win, m["hp_scale"], 1.0)
            elif "offtake_off_hours" in m:
                win[wk:wk + m["offtake_off_hours"]] = True
                stress["offtake_off"] = win.astype(float)
            elif "month" in m:
                win = bundle["weather"].month.to_numpy() == m["month"]
            else:
                win[:] = True
            r = MA.simulate(spec, cfg, bundle, A, stress, scen_override=scen, policy="merit", dispatch_value=dv)
            e, sm = r["hourly"][win], r["summary"]
            raw = e.Q_DC_used_MW + e.Q_rejected_MW
            rows.append(dict(portfolio=name, mode=mode, event_hours=int(win.sum()), demand_MWh=float(e.D_total_MW.sum()),
                             network_heat_MWh=float((e.Q_HP_to_load_MW + e.Q_discharge_MW).sum()), backup_heat_MWh=float(e.Q_backup_MW.sum()),
                             backup_peak_MW=float(e.Q_backup_MW.max()), backup_cap_MW=sm["backup_cap_MW"], unserved_MWh=float(e.Q_unserved_MW.sum()),
                             max_share_of_dc_heat_taken_pct=float(100 * (e.Q_DC_used_MW / raw.where(raw > 0)).max()) if (raw > 0).any() else 0.0,
                             dc_heat_to_towers_pct=float(100 * e.Q_rejected_MW.sum() / raw.sum()) if raw.sum() > 0 else 100.0,
                             status="pass" if (e.Q_unserved_MW.sum() < 1e-6 and e.Q_rejected_MW.min() >= -1e-9) else "fail"))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "operating_modes_portfolios.csv", index=False)
    print(d.pivot(index="portfolio", columns="mode", values="status").to_string())
    print(d.groupby("portfolio")[["unserved_MWh", "max_share_of_dc_heat_taken_pct"]].max().round(1).to_string())


# ------------------------------------------------------------------ stage: small (final screening audit)
def stage_small(ctx: dict) -> None:
    """Small nearby buildings (0.5-2 GWh/yr fuel input, >= 2 LL84 years, year-to-year range <= 25 % of the mean, <= 300 m)
    never reach the shortlist (ranked by servable heat per metre), so test them directly: each with 111 8th Ave,
    all together, and all together on DHW-only service."""
    f = ctx["offt"].copy()
    f["yr_range"] = (f.heat_fuel_MWh_max - f.heat_fuel_MWh_min) / f.heat_fuel_MWh
    sm = f[f.heat_fuel_MWh.between(500, 2000, inclusive="left") & (f.n_years >= 2) & (f.yr_range <= 0.25) & (f.dist_m <= 300)
           & f.lat.notna() & (f.property_id != SITE)].sort_values("dist_m")
    base = evaluate(dict(horizon="today", members=[SITE]), ctx)["ind"]
    rows = []
    for r in sm.itertuples():
        i = evaluate(dict(horizon="today", members=[SITE, r.property_id]), ctx)["ind"]
        rows.append(dict(test="111 8th + one building", property_id=r.property_id, name=r.property_name, use_type=r.use_type, dist_m=r.dist_m,
                         heat_fuel_MWh=r.heat_fuel_MWh, year_to_year_range=r.yr_range, sh_system=r.sh_system,
                         net_annual_value=i["E_val"], incremental_value=i["E_val"] - base["E_val"], co2_avoided_t=i["N_co2"],
                         heat_reused_MWh=i["Q_DC_used_MWh"], route_m=i["route_m"], funding_need=i["E_fund"]))
    members = [SITE] + list(sm.property_id)
    for label, dhw in (("111 8th + all small buildings", None), ("111 8th + all small buildings, DHW-only", list(sm.property_id))):
        i = evaluate(dict(horizon="today", members=members), ctx_with(ctx, dhw_only=dhw))["ind"]
        rows.append(dict(test=label, property_id="|".join(sm.property_id), name=f"{len(sm)} buildings", dist_m=float(sm.dist_m.max()),
                         heat_fuel_MWh=float(sm.heat_fuel_MWh.sum()), net_annual_value=i["E_val"], incremental_value=i["E_val"] - base["E_val"],
                         co2_avoided_t=i["N_co2"], heat_reused_MWh=i["Q_DC_used_MWh"], route_m=i["route_m"], funding_need=i["E_fund"]))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "small_building_check.csv", index=False)
    print(d[["test", "name", "dist_m", "heat_fuel_MWh", "net_annual_value", "incremental_value", "co2_avoided_t", "route_m"]].round(0).to_string(index=False))


# ------------------------------------------------------------------ stage: design (fixed-parameter check)
def stage_design(ctx: dict) -> None:
    rows = []
    for name, pf in portfolios().items():
        hydronic = [m for m in pf["members"] if m in set(ctx["offt"].loc[ctx["offt"].sh_system == "hydronic_assumed", "property_id"])]
        scopes = {"full (DHW + space heat)": None}
        if hydronic:
            scopes["DHW / base load only"] = hydronic
        for (scope, dhw), hp, tank in itertools.product(scopes.items(), (0.5, 0.75, 1.0), (0, 2, 6)):
            c = ctx_with(ctx, dhw_only=dhw, design=dict(hp_frac=hp, tank_hours=tank))
            e = evaluate(pf, c)
            i, s = e["ind"], e["raw"]["summary"]
            rows.append(dict(portfolio=name, service_scope=scope, hp_frac=hp, tank_hours=tank, heat_reused_MWh=s.Q_DC_used_MWh,
                             heat_delivered_MWh=s.Q_network_MWh, net_annual_value=i["E_val"], co2_avoided_t=i["N_co2"], backup_share_pct=i["T_bk"],
                             unserved_MWh=s.Q_unserved_MWh, capex=i["capex_total"], funding_need=i["E_fund"], tech_ok=i["tech_ok"],
                             is_reference_design=(scope.startswith("full") and hp == 0.75 and tank == 2)))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "design_check.csv", index=False)
    best = d[d.tech_ok].sort_values("net_annual_value", ascending=False).groupby("portfolio").head(1)
    ref = d[d.is_reference_design].set_index("portfolio").net_annual_value
    best = best.assign(reference_value=best.portfolio.map(ref), gain_vs_reference=lambda x: x.net_annual_value - x.reference_value)
    best.to_csv(OUT / "design_check_best.csv", index=False)
    print(best[["portfolio", "service_scope", "hp_frac", "tank_hours", "net_annual_value", "gain_vs_reference"]].to_string(index=False))


# ------------------------------------------------------------------ stage: combined sensitivity
# Register assumptions (Low/Base/High from data/reference/assumptions_scenarios.csv) plus four price/engineering
# factors not in the register; each with its source. "fav" = the level that favours the project.
A_SIDE = {"A02": ("low", "base", "high"), "A10": ("low", "base", "high"), "A18": ("low", "base", "high"), "A17": ("low", "base")}
B_SIDE = {"A05": ("low", "base", "high"), "A07": ("low", "base", "high"), "A21": ("low", "base", "high"), "A08": ("low", "base", "high")}
EXTRA = {
    "gas_price": ({"base": None, "high": 73.27}, "EIA NY residential gas 12-month mean ($/MWh fuel), upper bound for small-volume firm service; Base = EIA commercial mean 38.85"),
    "steam_price": ({"low": 89.2, "base": None}, "Con Ed SC2 Rate II winter tail block 26.97 + fuel adjustment 4.25 $/Mlb (S07), lower than the pilot-implied marginal 107.6 $/MWh"),
    "hx_scale_exp": ({"base": None, "low": 0.7}, "engineering cost-capacity rule (exponent 0.6-0.7) scaling the pilot's 1.47 MW interface; Base = linear"),
    "network_life": ({"base": None, "low": 40}, "pipe / interface life 40 yr instead of the heat-pump life 25 yr used for all assets at Base"),
}
FAV = {"A02": "high", "A10": "high", "A18": "low", "A17": "low", "A05": "low", "A07": "low", "A21": "low", "A08": "low",
       "gas_price": "high", "steam_price": "base", "hx_scale_exp": "low", "network_life": "low"}


def _combined_one(args) -> pd.DataFrame:
    name, pf = args
    from .run_model_c import build_ctx
    ctx = build_ctx()
    rows = []
    a_keys, b_keys, x_keys = list(A_SIDE), list(B_SIDE), list(EXTRA)
    for a_lv in itertools.product(*A_SIDE.values()):
        lv_a = dict(zip(a_keys, a_lv))
        ca = ctx_with(ctx, levels={k: v for k, v in lv_a.items() if v != "base"})
        r = MC.evaluate_config(tuple(pf["members"]), pf["horizon"], ca)
        s, bld = r["summary"], r["buildings"]
        internal = tuple(pf["members"]) == (SITE,)
        run = pd.Series(dict(run_id=name, scenario=name, hp_frac=0.75, tank_hours=2, assumption_set="combined", internal=internal))
        for b_lv in itertools.product(*B_SIDE.values()):
            lv_b = dict(zip(b_keys, b_lv))
            lv = {**lv_a, **lv_b}
            P = dict(MB.b_params({k: v for k, v in lv.items() if v != "base"}), nycha_tariff_rule="affordability_cap")
            for x_lv in itertools.product(*[list(EXTRA[k][0]) for k in x_keys]):
                lx = dict(zip(x_keys, x_lv))
                I = dict(ctx["I"])
                if EXTRA["gas_price"][0][lx["gas_price"]]:
                    I["gas_price"] = EXTRA["gas_price"][0][lx["gas_price"]]
                if EXTRA["steam_price"][0][lx["steam_price"]]:
                    I["steam_price"] = EXTRA["steam_price"][0][lx["steam_price"]]
                PP = dict(P, hx_scale_exp=EXTRA["hx_scale_exp"][0][lx["hx_scale_exp"]], network_life=EXTRA["network_life"][0][lx["network_life"]])
                e = MB.evaluate(run, s, bld, PP, I)["econ"]
                rows.append(dict(portfolio=name, **lv, **lx, n_nonbase=sum(v != "base" for v in {**lv, **lx}.values()),
                                 n_favourable=sum({**lv, **lx}[k] == FAV[k] and FAV[k] != "base" for k in FAV),
                                 net_annual_value=e["annual_savings"], co2_avoided_t=e["co2_avoided"], funding_need=e["public_funding_need"],
                                 operator_net=e["operator_net"], dc_net=e["dc_net"], heat_reused_MWh=s.Q_DC_used_MWh, lcoh=e["lcoh_system"]))
    return pd.DataFrame(rows)


def stage_combined(ctx: dict, workers: int = 6) -> None:
    pfs = {k: v for k, v in portfolios().items() if k != "balanced_today"}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_combined_one, pfs.items()))
    d = pd.concat(res, ignore_index=True)
    d.to_csv(OUT / "combined_sensitivity.csv.gz", index=False)
    params = list(A_SIDE) + list(B_SIDE) + list(EXTRA)
    summ, eff = [], []
    for name, g in d.groupby("portfolio", sort=False):
        base = g[g.n_nonbase == 0].iloc[0]
        allfav = g[g.n_favourable == g.n_favourable.max()].net_annual_value.max()
        ok = g[g.net_annual_value > 0]
        minimal = ok[ok.n_nonbase == ok.n_nonbase.min()] if len(ok) else ok
        summ.append(dict(portfolio=name, n_combinations=len(g), base_value=base.net_annual_value, min_value=g.net_annual_value.min(),
                         max_value=g.net_annual_value.max(), all_favourable_value=allfav, share_combinations_positive=len(ok) / len(g),
                         base_co2=base.co2_avoided_t, min_co2=g.co2_avoided_t.min(), max_co2=g.co2_avoided_t.max(),
                         share_co2_positive=float((g.co2_avoided_t > 0).mean()),
                         fewest_changes_to_break_even=int(ok.n_nonbase.min()) if len(ok) else None,
                         example_break_even=("; ".join(f"{k}={minimal.iloc[0][k]}" for k in params if minimal.iloc[0][k] != "base") if len(ok) else "none")))
        for p in params:
            m = g.groupby(p).net_annual_value.mean()
            eff.append(dict(portfolio=name, parameter=p, swing_of_mean_value=float(m.max() - m.min()),
                            **{f"mean_at_{k}": float(v) for k, v in m.items()}))
    pd.DataFrame(summ).to_csv(OUT / "combined_summary.csv", index=False)
    e = pd.DataFrame(eff).sort_values(["portfolio", "swing_of_mean_value"], ascending=[True, False])
    e.to_csv(OUT / "combined_main_effects.csv", index=False)
    meta = dict(seconds=round(time.time() - t0, 1), register_levels={**A_SIDE, **B_SIDE},
                extra_factors={k: dict(levels={kk: vv for kk, vv in v[0].items()}, source=v[1]) for k, v in EXTRA.items()},
                favourable_level=FAV, note="Full factorial; shares are shares of combinations, not probabilities. Merit order of hourly allocation kept at Base prices.")
    (OUT / "combined_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(pd.DataFrame(summ).round(0).to_string(index=False))


def break_even(pf: dict, ctx: dict) -> dict:
    e = evaluate(pf, ctx)
    ec, b = e["raw"]["econ"], e["raw"]["buildings"]
    deficit = max(0.0, -ec["annual_savings"])
    gas_net = float((b.base_fuel_MWh - b.backup_fuel_MWh).where(b.main_fuel == "gas_or_oil", 0).where(~b.rebuilt.astype(bool), 0).sum()) if len(b) else 0
    steam_net = float((b.base_fuel_MWh - b.backup_fuel_MWh).where(b.main_fuel == "steam", 0).where(~b.rebuilt.astype(bool), 0).sum()) if len(b) else 0
    el = ec["electricity_cost"] / ctx["P"]["A07"]
    return dict(deficit=deficit,
                carbon_price=deficit / ec["co2_avoided"] if ec["co2_avoided"] > 0 and deficit else (0 if not deficit else None),
                electricity_price=ctx["P"]["A07"] - deficit / el if el else None,
                gas_price_needed=ctx["I"]["gas_price"] + deficit / gas_net if gas_net > 0 else None,
                steam_price_needed=ctx["I"]["steam_price"] + deficit / steam_net if steam_net > 0 else None,
                capital_grant_share=min(1.0, deficit / ec["capex_annualised"]) if ec["capex_annualised"] else None,
                grant_closes=deficit <= ec["capex_annualised"])


# ------------------------------------------------------------------ stage: proposal
def stage_proposal(ctx: dict) -> None:
    from .run_model_c import allocation_json
    gov = pd.read_csv(F.ROOT / "model" / "config" / "delivery_governance.csv")
    month = ctx["bundle"]["weather"].month.to_numpy()
    cards = {}
    for name, pf in portfolios().items():
        e = evaluate(pf, ctx)
        i, s, ec, b, h = e["ind"], e["raw"]["summary"], e["raw"]["econ"], e["raw"]["buildings"], e["raw"]["hourly"]
        alloc = allocation_json(tuple(sorted(pf["members"])), pf["horizon"], ctx)
        bl = []
        for ab in alloc["buildings"]:
            row = b[b.property_id == ab["property_id"]].iloc[0]
            mon = np.array(ab["monthly_network_MWh"])
            bl.append(dict(property_id=ab["property_id"], name=NAMES.get(ab["property_id"], row["name"]), use=row.sh_system,
                           fuel=row.main_fuel, distance_m=float(row.dist_m), units=float(row.units),
                           served_scope="hot water only (steam radiators, H7)" if row.sh_system == "steam_radiators" else
                           ("new low-temperature space heat 45 C + hot water" if bool(row.rebuilt) else "hot water + existing hydronic space heat (A18)"),
                           useful_demand_MWh=float(row.D_useful_MWh), network_heat_MWh=float(row.Q_network_MWh), heat_reused_MWh=float(row.Q_loop_MWh),
                           share_of_building_heat=float(row.share_heat_from_network), heat_pump_MW=float(row.HP_cap_MW), peak_MW=float(row.peak_served_MW),
                           summer_to_winter_ratio=float(mon[5:8].sum() / mon[[0, 1, 11]].sum()) if mon[[0, 1, 11]].sum() else None,
                           backup=row.backup_type, bill_change_per_year=float(row.user_net), merit_rank=ab["merit_rank"],
                           monthly_network_MWh=ab["monthly_network_MWh"]))
        ms = alloc["monthly_system"]
        cards[name] = dict(
            role=pf["role"], horizon=pf["horizon"], config_id=i["config_id"], members=pf["members"], buildings=bl,
            architecture=dict(capture="heat exchanger on the tenant condenser-water loop at 111 8th Ave (A02 30 C at Base); loop "
                                      f"{ctx['A']['A02'] - ctx['cfg']['physics']['approach_hx_K']:.0f} C",
                              interface_MW=float(s.HX_cap_MW), distribution=("none (in-building)" if s.route_m == 0 else
                                                                            f"ambient-temperature two-pipe loop, {s.route_m:.0f} m route"),
                              heat_pumps=f"decentralised building heat pumps, {s.HP_cap_MW:.1f} MW total; COP DHW {s.COP_dhw:.2f}, "
                                         f"new space heat {s.COP_sh45:.2f}, existing hydronic {s.COP_sh_exist:.2f}; seasonal COP {s.T2_SCOP:.2f}",
                              storage_MWh=float(s.tank_MWh), backup_MW=float(s.backup_cap_MW)),
            outcomes=dict(heat_reused_MWh=float(s.Q_DC_used_MWh), heat_delivered_MWh=float(s.Q_network_MWh), erf_pct=i["N_erf"],
                          net_annual_value=i["E_val"], co2_avoided_t=i["N_co2"], gas_displaced_MWh=i["N_gas"], low_income_households=i["S_li"],
                          community_facilities=i["S_fac"], funding_need_per_year=i["E_fund"], capex=i["capex_total"], lcoh=i["E_lcoh"],
                          dc_net=ec["dc_net"], users_net=ec["users_net"], operator_net=ec["operator_net"], backup_share_pct=i["T_bk"],
                          coverage_pct=i["T_cov"], feasibility=i["feasibility"], failed_checks=i["failed_checks"]),
            matching=dict(dc_heat_available_MWh_monthly=ms["dc_heat_available_MWh"], dc_heat_used_MWh_monthly=ms["dc_heat_used_MWh"],
                          demand_MWh_monthly=ms["demand_MWh"],
                          peak_demand_vs_interface=f"{s.D_peak_design_MW:.1f} MW design peak vs {s.HX_cap_MW:.1f} MW interface "
                                                   f"(heat pumps at {ctx['cfg']['reference_design']['hp_frac']:.0%} of space-heat peak; backup covers the rest)",
                          hours_dc_heat_binding=int(((h.Q_DC_used_MW >= 0.999 * h.Q_DC_avail_MW) & (h.Q_DC_avail_MW > 0)).sum()),
                          hours_dc_heat_unavailable=int((h.Q_DC_avail_MW <= 0).sum())),
            no_worse_off=dict(users_net_at_tariff=ec["users_net"], dc_net_at_fence_price=ec["dc_net"],
                              funding_gap_if_all_users_held_harmless=max(0.0, -ec["annual_savings"] + max(0.0, ec["dc_net"])),
                              funding_gap_if_users_and_dc_held_harmless_at_cost=max(0.0, -ec["annual_savings"]),
                              peak_vs_all_electric_ASHP_MW=ec["peak_vs_ashp_MW"]),
            break_even=break_even(pf, ctx),
        )
    cards["_governance"] = gov[["item_id", "aspect", "stakeholder", "statement", "evidence_level", "open_question"]].to_dict("records")
    (OUT / "proposal_portfolios.json").write_text(json.dumps(cards, indent=2, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else float(o)),
                                                  encoding="utf-8")
    flat = [dict(portfolio=k, role=v["role"], horizon=v["horizon"], buildings="; ".join(x["name"] for x in v["buildings"]), **v["outcomes"],
                 **{f"break_even_{kk}": vv for kk, vv in v["break_even"].items()}) for k, v in cards.items() if not k.startswith("_")]
    pd.DataFrame(flat).to_csv(OUT / "proposal_comparison.csv", index=False)
    print(pd.DataFrame(flat)[["portfolio", "heat_reused_MWh", "net_annual_value", "co2_avoided_t", "low_income_households", "community_facilities",
                              "funding_need_per_year", "break_even_carbon_price"]].round(0).to_string(index=False))


# ------------------------------------------------------------------ stage: frontend bundle
def stage_frontend(ctx: dict) -> None:
    fe = OUT / "frontend"
    fe.mkdir(parents=True, exist_ok=True)
    c = pd.read_csv(REF / "c_configurations.csv")
    keep = ["config_id", "horizon", "n_buildings", "members", "feasibility", "failed_checks", "tech_ok"] + [i[0] for i in MC.INDICATORS] + \
           [f"n_{i[0]}" for i in MC.INDICATORS] + ["score_T", "score_E", "score_N", "score_S", "pareto", "Q_DC_used_MWh", "Q_network_MWh",
                                                   "capex_total", "route_m", "f1_carbon_price_to_close", "overall_equal_weights"]
    recs = []
    for r in c[keep].itertuples(index=False):
        d = r._asdict()
        d["members"] = d["members"].split("|") if isinstance(d["members"], str) else []
        d["failed_checks"] = d["failed_checks"].split(";") if isinstance(d["failed_checks"], str) else []
        recs.append({k: (None if isinstance(v, float) and np.isnan(v) else (bool(v) if isinstance(v, (bool, np.bool_)) else v)) for k, v in d.items()})
    (fe / "configurations.json").write_text(json.dumps(recs, default=float), encoding="utf-8")
    shutil.copy(REF / "c_candidates.geojson", fe / "candidates.geojson")
    shutil.copy(REF / "c_recommendations.json", fe / "recommendations.json")
    for h in ("today", "post_rebuild"):
        shutil.copy(REF / f"c_allocation_{h}.json", fe / f"allocation_{h}.json")
    shutil.copy(OUT / "proposal_portfolios.json", fe / "portfolios.json")
    ind = [dict(id=i[0], dimension=i[1], key=MC.DIM_KEY[i[1]], name=i[2], unit=i[3], direction=i[4], formula=i[6]) for i in MC.INDICATORS]
    (fe / "indicators.json").write_text(json.dumps(ind, indent=2), encoding="utf-8")
    # contract checks
    geo = json.loads((fe / "candidates.geojson").read_text(encoding="utf-8"))
    ids = {f["properties"]["id"] for f in geo["features"]}
    miss = {m.replace("rebuild:", "") for r in recs for m in r["members"]} - ids
    w = MC.PRESETS["equal (demonstration baseline)"]
    worst = max(abs(sum(w[d] * r[f"score_{MC.DIM_KEY[d]}"] for d in MC.DIMS) - r["overall_equal_weights"]) for r in recs)
    rj = json.loads((fe / "recommendations.json").read_text(encoding="utf-8"))
    df = pd.DataFrame(recs)
    rep_ok = all(_js_choose(df[df.horizon == h], w)["config_id"] == rj[h]["equal (demonstration baseline)"]["config_id"] for h in ("today", "post_rebuild"))
    al = json.loads((fe / "allocation_today.json").read_text(encoding="utf-8"))
    sel = df[df.config_id == al["config_id"]].iloc[0]
    mon_gap = abs(sum(al["monthly_system"]["dc_heat_used_MWh"]) - sel.Q_DC_used_MWh)
    checks = pd.DataFrame([
        dict(test_id="FE1", test="Every configuration member has a map feature", status="pass" if not miss else "fail", value=len(miss)),
        dict(test_id="FE2", test="Overall score = sum of weight x dimension score (frontend recomputation)", status="pass" if worst < 1e-9 else "fail", value=worst),
        dict(test_id="FE3", test="Contract recommendation rule reproduces Model C recommendations", status="pass" if rep_ok else "fail", value=rep_ok),
        dict(test_id="FE4", test="Monthly allocation sums to the annual heat reused of the configuration", status="pass" if mon_gap < 1 else "fail", value=mon_gap),
        dict(test_id="FE5", test="Weights that do not sum to 100% are rejected by the rule", status="pass" if _rejects() else "fail", value=True),
    ])
    checks.to_csv(fe / "contract_validation.csv", index=False)
    print(checks.to_string(index=False))


def _js_choose(df: pd.DataFrame, w: dict) -> dict:
    """Reference implementation of the frontend rule (mirrors frontend/CONTRACT.md)."""
    if abs(sum(w.values()) - 1) > 1e-9:
        raise ValueError("weights must sum to 100%")
    sc = sum(w[d] * df[f"score_{MC.DIM_KEY[d]}"] for d in MC.DIMS)
    nets = df[df.n_buildings > 0]
    for cls in ("fully_feasible", "conditionally_feasible"):
        pool = nets[nets.feasibility == cls]
        if len(pool):
            return dict(config_id=df.loc[sc.loc[pool.index].idxmax(), "config_id"], status=cls)
    return dict(config_id=None, status="none")


def _rejects() -> bool:
    try:
        _js_choose(pd.DataFrame(), dict(zip(MC.DIMS, (0.5, 0.5, 0.5, 0.5))))
        return False
    except ValueError:
        return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["audit", "small", "modes", "design", "combined", "proposal", "frontend", "all"])
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    from .run_model_c import build_ctx
    ctx = build_ctx()
    for st in (["audit", "small", "modes", "design", "combined", "proposal", "frontend"] if a.stage == "all" else [a.stage]):
        t = time.time()
        {"audit": stage_audit, "small": stage_small, "modes": stage_modes, "design": stage_design, "proposal": stage_proposal, "frontend": stage_frontend}.get(st, lambda c: stage_combined(c, a.workers))(ctx)
        print(f"[{st}] {time.time() - t:.1f} s")


if __name__ == "__main__":
    main()
