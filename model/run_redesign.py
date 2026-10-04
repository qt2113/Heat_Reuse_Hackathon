"""Engineering and economic redesign experiment for a small external network at Site 1.

Models A/B/C and their outputs are not changed; everything is written to outputs/redesign/.

  reconcile  our model vs the teammate's visualizer on the same buildings: Shapley decomposition of the gap into
             steam compatibility, pipe cost, A17, omitted CAPEX, omitted OPEX and the teammate's prices/finance
  cases      three design cases (NYC-calibrated reference, optimised urban retrofit, advanced heat recovery,
             plus a speculative liquid-cooling variant); 111 8th Ave + 1-3 external offtakers, design grid per network
  breakeven  exact one-at-a-time break-even conditions for the best small external network

    python -m model.run_redesign --stage all
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from concurrent.futures import ProcessPoolExecutor
from math import factorial

import numpy as np
import pandas as pd

from . import features as F
from . import model_b as MB
from . import model_c as MC

OUT = F.ROOT / "outputs" / "redesign"
SITE = "7536925"
FULTON = "2831044"
# teammate's base-case buildings mapped to our LL84 records ("200 W. 18th St.", 870 MWh, has no record in our 1 km table)
TEAMMATE = [FULTON, "6666490", "6311955", "3522266", "4038849", "2384020"]
TEAMMATE_RESULT = dict(net_usd=1_579_715, avoided_ll97_usd=176_101, water_usd=209_512, served_mwh=41_458, capex_annualised=1_494_978)
POOL_TODAY = ["4040951", "4769672", "19906892", "1633052", "8899918", "1634606", FULTON, "4473909", "2830989"]
POOL_POST = ["4040951", "4769672", "19906892", "1633052", "8899918", "1634606", "rebuild:2831044", "rebuild:4473909"]


# ------------------------------------------------------------------ context helpers
def make_ctx(ctx: dict, A=None, P=None, I=None, offt_fn=None, design=None) -> dict:
    c = dict(ctx)
    c["A"] = dict(ctx["A"], **(A or {}))
    c["P"] = dict(ctx["P"], **(P or {}))
    c["I"] = dict(ctx["I"], **(I or {}))
    if offt_fn:
        offt = offt_fn(ctx["offt"].copy())
        c["offt"], c["bundle"] = offt, dict(ctx["bundle"], offtakers=offt)
    if design:
        c["cfg"] = dict(ctx["cfg"], reference_design=dict(ctx["cfg"]["reference_design"], **design))
    c["dv"] = MC.dispatch_values(c["I"], c["A"])
    return c


def run(members: list, horizon: str, ctx: dict) -> dict:
    r = MC.evaluate_config(tuple(members), horizon, ctx)
    r["internal"] = tuple(members) == (SITE,)
    return dict(raw=r, ind=MC.indicators(r, ctx))


def relabel(ids, to: str, only_from: tuple = ("steam_radiators", "hydronic_assumed")):
    def f(o):
        m = o.property_id.isin(ids) & o.sh_system.isin(only_from)
        o.loc[m, "sh_system"] = to
        return o
    return f


def chain(*fns):
    def f(o):
        for g in fns:
            o = g(o)
        return o
    return f


def prewar_gas_as_steam(o: pd.DataFrame) -> pd.DataFrame:
    """Correction: gas/oil buildings built before 1940 (PLUTO yearbuilt) are assumed to have steam radiators -> hot water only."""
    pl = pd.read_csv(F.DATA / "processed" / "pluto_lots_1km.csv", dtype=str).set_index("bbl").yearbuilt
    yb = o.bbl.astype(str).str.split(";").str[0].str.strip().map(pd.to_numeric(pl, errors="coerce"))
    m = (o.main_fuel == "gas_or_oil") & ~o.is_nycha & (yb > 0) & (yb < 1940)
    o.loc[m, "sh_system"] = "steam_radiators"
    o["year_built"] = yb
    return o


def remove_pilot_overlap(o: pd.DataFrame) -> pd.DataFrame:
    """Correction: Con Ed Chelsea pilot serves 291 Fulton apartments (2,333 MWh DHW + 348 MWh space heat, S13)."""
    pr = pd.read_csv(F.DATA / "reference" / "chelsea_uten_pilot_stage2.csv").set_index("metric").value
    useful = sum(float(pr[k]) for k in ("dhw_load_401_W_16th", "dhw_load_410_W_17th", "dhw_load_420_W_17th", "space_heating_load_401_W_16th")) / 3.412142
    a4 = F.assumption_values()["A04"]
    i = o.index[o.property_id == FULTON]
    o.loc[i, "heat_fuel_MWh"] = o.loc[i, "heat_fuel_MWh"] - useful / a4
    o.loc[i, "units_res"] = o.loc[i, "units_res"] - float(pr["apartments_served"])
    return o


def electric_boiler_cost(raw: dict, ctx: dict) -> tuple[float, float]:
    """Correction: capital (annualised) + fixed O&M of the electric backup boilers of rebuilt towers (DEA '41 Electric boiler, large')."""
    b = raw["buildings"]
    reb = b[b.rebuilt.astype(bool)] if len(b) else b
    if not len(reb):
        return 0.0, 0.0
    dea = pd.read_csv(F.DATA / "processed" / "equipment_dea_heat.csv")
    d = dea[(dea.ws == "41 Electric boiler, large") & (dea.year == 2025)].set_index("parameter").ctrl
    cap = float(reb.peak_served_MW.sum())
    markup = 1 + ctx["I"]["contingency"] + ctx["P"]["A21"]
    capex = cap * float(d["capex_MEUR_per_MWth"]) * 1e6 * ctx["I"]["k_usd"] * markup
    ann = capex * MB.crf(ctx["P"]["A08"], ctx["I"]["life"]) + cap * float(d["fixed_om_EUR_per_MWth_yr"]) * ctx["I"]["k_usd"]
    return capex, ann


def metrics(res: dict, ctx: dict, extra_capex=0.0, extra_ann=0.0) -> dict:
    i, s, e = res["ind"], res["raw"]["summary"], res["raw"]["econ"]
    val = e["annual_savings"] - extra_ann
    return dict(heat_recovered_MWh=s.Q_DC_used_MWh, heat_delivered_MWh=s.Q_network_MWh, capex_total=e["capex_total"] + extra_capex,
                capex_annualised=e["capex_annualised"] + extra_ann, opex_annual=e["om_annual"] + e["electricity_cost"] + e["backup_fuel_cost"],
                electricity_cost=e["electricity_cost"], source_electricity_cost=e["source_electricity_cost"], om_annual=e["om_annual"],
                baseline_energy_cost=e["baseline_cost_annual"],
                gross_energy_savings=e["baseline_cost_annual"] - e["electricity_cost"] - e["backup_fuel_cost"],
                net_societal_value=val, co2_avoided_t=e["co2_avoided"], low_income_households=e["low_income_households"],
                community_facilities=i["S_fac"], funding_gap_at_tariff=e["public_funding_need"],
                funding_gap_no_worse_off=max(0.0, -val + max(0.0, e["dc_net"])), dc_net=e["dc_net"], route_m=s.route_m,
                scop=s.T2_SCOP, coverage_pct=i["T_cov"], tech_ok=i["tech_ok"], lcoh=(e["capex_annualised"] + extra_ann + e["om_annual"] + e["electricity_cost"]) / s.Q_network_MWh if s.Q_network_MWh else np.nan)


# ------------------------------------------------------------------ 1. reconciliation
FACTORS = ["steam_compatibility", "pipe_cost", "A17_source_electricity", "capex_building_retrofit_basis", "capex_markups",
           "capex_energy_centre_interface", "omitted_opex", "teammate_prices_finance_efficiency"]
FACTOR_DESC = {
    "steam_compatibility": "steam-radiator buildings take all their heat (space heat included) at the hydronic temperature, instead of hot water only (H7)",
    "pipe_cost": "pipe $3,000/m (teammate) instead of $29,318/m (Con Ed pilot)",
    "A17_source_electricity": "no extra electricity at the data center (A17 = 0 instead of 0.25)",
    "capex_building_retrofit_basis": "building side at heat-pump cost $1,200/kW for every building (NYCHA included) instead of the pilot's "
                                     "$63.8k per NYCHA apartment and DEA heat-pump cost elsewhere",
    "capex_markups": "no 15 % contingency and no 29 % soft costs (pilot ratios)",
    "capex_energy_centre_interface": "no energy centre ($2.69M pilot) and no source heat-recovery interface ($1.75M/MW pilot), replaced by the "
                                     "teammate's $150/kW building connection",
    "omitted_opex": "no heat-pump or network O&M",
    "teammate_prices_finance_efficiency": "gas $14/MMBtu, steam $35/MMBtu, electricity $0.22/kWh, 6 % discount, lives 20/30/25 yr, "
                                          "steam utilisation 0.85, heat-pump eta 0.40",
}


def reconcile_value(on: set, ctx: dict, members=TEAMMATE) -> dict:
    A, P, I, fn = {}, {}, {}, None
    if "steam_compatibility" in on:
        fn = relabel(members, "hydronic_assumed", ("steam_radiators",))
    if "pipe_cost" in on:
        P["A05"] = 3000.0
    if "A17_source_electricity" in on:
        A["A17"] = 0.0
    if "capex_building_retrofit_basis" in on:
        I["hp_capex"] = 1.2e6
    if "capex_markups" in on:
        I["contingency"] = 0.0
        P["A21"] = 0.0
    if "capex_energy_centre_interface" in on:
        I.update(ec_capex=0.0, hx_capex=0.0)
    if "omitted_opex" in on:
        I.update(hp_fom=0.0, hp_vom=0.0)
        P["A22"] = 0.0
    if "teammate_prices_finance_efficiency" in on:
        I.update(gas_price=14 * 3.412142, steam_price=35 * 3.412142, life=20)
        P.update(A07=220.0, A08=0.06, network_life=30)
        A.update(A04=0.85, A10=0.40)
    c = make_ctx(ctx, A=A, P=P, I=I, offt_fn=fn)
    res = run(members, "today", c)
    e, b = res["raw"]["econ"], res["raw"]["buildings"]
    val = e["annual_savings"]
    if "capex_building_retrofit_basis" in on:
        k = MB.crf(c["P"]["A08"], c["I"]["life"])
        markup = 1 + c["I"]["contingency"] + c["P"]["A21"]
        ny = b[b.is_nycha.astype(bool) & ~b.rebuilt.astype(bool)]
        val += float((ny.bld_capex - ny.HP_cap_MW * c["I"]["hp_capex"] * markup).sum()) * k            # NYCHA at heat-pump cost
    if "capex_energy_centre_interface" in on:
        val -= float(b.peak_served_MW.sum()) * 150e3 * MB.crf(c["P"]["A08"], 25)                        # $150/kW connection
    return dict(value=val, heat_delivered_MWh=res["raw"]["summary"].Q_network_MWh, heat_recovered_MWh=res["raw"]["summary"].Q_DC_used_MWh,
                co2=e["co2_avoided"], route_m=res["raw"]["summary"].route_m)


def stage_reconcile(ctx: dict) -> None:
    n = len(FACTORS)
    v = {}
    for mask in range(2 ** n):
        on = {FACTORS[j] for j in range(n) if mask >> j & 1}
        v[frozenset(on)] = reconcile_value(on, ctx)
    sh = {}
    for f in FACTORS:
        tot = 0.0
        for S, val in v.items():
            if f in S:
                continue
            w = factorial(len(S)) * factorial(n - len(S) - 1) / factorial(n)
            tot += w * (v[S | {f}]["value"] - val["value"])
        sh[f] = tot
    base, full = v[frozenset()], v[frozenset(FACTORS)]
    rows = [dict(item="our model, teammate's buildings, our assumptions", value=base["value"], heat_delivered_MWh=base["heat_delivered_MWh"])]
    rows += [dict(item=f, description=FACTOR_DESC[f], shapley_contribution=sh[f]) for f in FACTORS]
    rows += [dict(item="our model with all eight teammate choices", value=full["value"], heat_delivered_MWh=full["heat_delivered_MWh"]),
             dict(item="teammate resource value (their net minus LL97 and water items)",
                  value=TEAMMATE_RESULT["net_usd"] - TEAMMATE_RESULT["avoided_ll97_usd"] - TEAMMATE_RESULT["water_usd"], heat_delivered_MWh=TEAMMATE_RESULT["served_mwh"]),
             dict(item="residual (demand data, dispatch, 200 W 18th St, central vs building heat pumps)",
                  value=TEAMMATE_RESULT["net_usd"] - TEAMMATE_RESULT["avoided_ll97_usd"] - TEAMMATE_RESULT["water_usd"] - full["value"]),
             dict(item="teammate non-resource items: LL97 penalties avoided (a transfer to the city) + cooling water (tower type unknown)",
                  value=TEAMMATE_RESULT["avoided_ll97_usd"] + TEAMMATE_RESULT["water_usd"]),
             dict(item="teammate reported net", value=TEAMMATE_RESULT["net_usd"], heat_delivered_MWh=TEAMMATE_RESULT["served_mwh"])]
    pd.DataFrame(rows).to_csv(OUT / "reconciliation.csv", index=False)
    seq, on = [], set()
    for f in FACTORS:                                 # one intuitive order, for a waterfall chart
        prev = v[frozenset(on)]["value"]
        on = on | {f}
        seq.append(dict(step=f, value_after=v[frozenset(on)]["value"], change=v[frozenset(on)]["value"] - prev))
    pd.DataFrame(seq).to_csv(OUT / "reconciliation_waterfall.csv", index=False)
    pd.DataFrame([dict(factors="+".join(sorted(S)) or "none", **val) for S, val in v.items()]).to_csv(OUT / "reconciliation_all_subsets.csv", index=False)
    print(pd.DataFrame(rows)[["item", "value", "shapley_contribution", "heat_delivered_MWh"]].round(0).to_string(index=False))


# ------------------------------------------------------------------ 2. design cases
CASES = {
    "reference": dict(desc="NYC-calibrated reference (validated Models A/B, reference design)", A={}, P={}, I={}, corrections=False, grid=False),
    "optimised_urban": dict(desc="optimised urban retrofit: corrections (pre-war gas = steam, pilot overlap removed, rebuilt-tower boiler cost) + "
                                 "pipe cost at 0.6 x pilot (A05 Low), soft costs 15 % (A21 Low), 40-yr network life, best sizing and service scope",
                            A={}, P=dict(A05=17590.0, A21=0.15, network_life=40), I={}, corrections=True, grid=True),
    "advanced_recovery": dict(desc="optimised urban + advanced heat recovery: capture at 35 C (A02 High, pilot loop up to 36 C), heat-pump eta 0.50 "
                                   "(A10 High), no extra data-center electricity (A17 Low)",
                              A=dict(A02=35.0, A10=0.50, A17=0.0), P=dict(A05=17590.0, A21=0.15, network_life=40), I={}, corrections=True, grid=True),
    "liquid_cooling_speculative": dict(desc="speculative: direct liquid cooling at 45 C capture (outside the register range), eta 0.50, A17 = 0",
                                       A=dict(A02=45.0, A10=0.50, A17=0.0), P=dict(A05=17590.0, A21=0.15, network_life=40), I={}, corrections=True, grid=True),
}
GRID = [dict(scope=sc, hp_frac=hp, tank_hours=tk) for sc in ("full", "dhw_only") for hp in (0.5, 0.75) for tk in (2, 6)]


def networks() -> list[tuple[str, list]]:
    out = []
    for horizon, pool in (("today", POOL_TODAY), ("post_rebuild", POOL_POST)):
        for k in (1, 2, 3):
            for ext in itertools.combinations(pool, k):
                out.append((horizon, [SITE, *ext]))
    return out


def case_ctx(ctx: dict, case: dict, design: dict | None = None, members=()) -> dict:
    fns = [prewar_gas_as_steam, remove_pilot_overlap] if case["corrections"] else []
    if design and design["scope"] == "dhw_only":
        fns.append(relabel([m for m in members if not m.startswith("rebuild:")], "dhw_only_design", ("hydronic_assumed",)))
    d = dict(hp_frac=design["hp_frac"], tank_hours=design["tank_hours"]) if design else None
    return make_ctx(ctx, A=case["A"], P=case["P"], I=case["I"], offt_fn=chain(*fns) if fns else None, design=d)


def _case_one(name: str) -> pd.DataFrame:
    from .run_model_c import build_ctx
    ctx = build_ctx()
    case = CASES[name]
    rows = []
    designs = GRID if case["grid"] else [None]
    base_ctx = case_ctx(ctx, case)
    internal = metrics(run([SITE], "today", base_ctx), base_ctx)
    for horizon, mem in networks():
        for d in designs:
            c = case_ctx(ctx, case, d, mem)
            res = run(mem, horizon, c)
            xc, xa = electric_boiler_cost(res["raw"], c) if case["corrections"] else (0.0, 0.0)
            m = metrics(res, c, xc, xa)
            rows.append(dict(case=name, horizon=horizon, members="|".join(mem), external="|".join(mem[1:]), n_external=len(mem) - 1,
                             scope=d["scope"] if d else "full", hp_frac=d["hp_frac"] if d else 0.75, tank_hours=d["tank_hours"] if d else 2,
                             **m, value_vs_internal_only=m["net_societal_value"] - internal["net_societal_value"]))
    return pd.DataFrame(rows)


def stage_cases(workers: int) -> None:
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_case_one, CASES))
    d = pd.concat(res, ignore_index=True)
    d.to_csv(OUT / "networks_all.csv.gz", index=False)
    postprocess_cases(round(time.time() - t0, 1))


def postprocess_cases(seconds=None) -> None:
    d = pd.read_csv(OUT / "networks_all.csv.gz")
    d = d[d.tech_ok]
    # best design per network
    best = d.sort_values("net_societal_value", ascending=False).groupby(["case", "horizon", "members"]).head(1)
    best.to_csv(OUT / "networks_best_design.csv", index=False)
    # incremental value of each external offtaker joining 111 8th Ave alone (best design each)
    inc = best[best.n_external == 1].copy()
    from .run_model_c import build_ctx
    ctx = build_ctx()
    rows = []
    for name, case in CASES.items():
        c = case_ctx(ctx, case)
        intr = metrics(run([SITE], "today", c), c)
        g = inc[inc.case == name]
        for r in g.itertuples():
            rows.append(dict(case=name, horizon=r.horizon, offtaker=r.external, scope=r.scope, hp_frac=r.hp_frac, tank_hours=r.tank_hours,
                             d_net_value=r.net_societal_value - intr["net_societal_value"], d_heat_recovered=r.heat_recovered_MWh - intr["heat_recovered_MWh"],
                             d_co2=r.co2_avoided_t - intr["co2_avoided_t"], d_low_income_hh=r.low_income_households, d_facilities=r.community_facilities,
                             d_capex=r.capex_total - intr["capex_total"], route_m=r.route_m,
                             cost_per_t_co2=(-(r.net_societal_value - intr["net_societal_value"]) / (r.co2_avoided_t - intr["co2_avoided_t"]))
                             if r.co2_avoided_t > intr["co2_avoided_t"] else np.nan,
                             cost_per_household=(-(r.net_societal_value - intr["net_societal_value"]) / r.low_income_households) if r.low_income_households > 0 else np.nan))
        rows.append(dict(case=name, horizon="today", offtaker="(internal 111 8th Ave only)", d_net_value=intr["net_societal_value"],
                         d_heat_recovered=intr["heat_recovered_MWh"], d_co2=intr["co2_avoided_t"]))
    pd.DataFrame(rows).sort_values(["case", "d_net_value"], ascending=[True, False]).to_csv(OUT / "incremental_offtakers.csv", index=False)
    # headline picks per case: best value; best with community beneficiaries; best CO2-positive value
    picks = []
    for name, g in best.groupby("case", sort=False):
        for label, pool in (("best net value (>= 1 external)", g),
                            ("best with low-income households", g[g.low_income_households > 0]),
                            ("best with a community facility", g[g.community_facilities > 0]),
                            ("best with CO2 >= internal-only + 300 t", g[g.co2_avoided_t >= g.co2_avoided_t.min() + 300])):
            if len(pool):
                r = pool.loc[pool.net_societal_value.idxmax()]
                picks.append({**r.to_dict(), "pick": label})
    p = pd.DataFrame(picks)
    p.to_csv(OUT / "best_networks.csv", index=False)
    meta = dict(seconds=seconds, cases={k: v["desc"] for k, v in CASES.items()}, design_grid=GRID,
                pools=dict(today=POOL_TODAY, post_rebuild=POOL_POST))
    (OUT / "cases_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(p[["case", "pick", "external", "scope", "hp_frac", "tank_hours", "heat_recovered_MWh", "net_societal_value", "co2_avoided_t",
             "low_income_households", "community_facilities", "funding_gap_no_worse_off"]].round(0).to_string(index=False))


# ------------------------------------------------------------------ 3. break-even
def stage_breakeven() -> None:
    from .run_model_c import build_ctx
    ctx = build_ctx()
    p = pd.read_csv(OUT / "best_networks.csv")
    rows = []
    for _, r in p[p.case.isin(["reference", "optimised_urban", "advanced_recovery"])].iterrows():
        case = CASES[r.case]
        mem = r.members.split("|")
        d = dict(scope=r["scope"], hp_frac=r.hp_frac, tank_hours=r.tank_hours)
        c = case_ctx(ctx, case, d, mem)

        def value(Aover=None):
            cc = make_ctx(c, A=Aover or {})
            res = run(mem, r.horizon, cc)
            xc, xa = electric_boiler_cost(res["raw"], cc) if case["corrections"] else (0.0, 0.0)
            return res, res["raw"]["econ"]["annual_savings"] - xa

        res, v0 = value()
        e, s, b = res["raw"]["econ"], res["raw"]["summary"], res["raw"]["buildings"]
        markup = 1 + c["I"]["contingency"] + c["P"]["A21"]
        k_net = MB.crf(c["P"]["A08"], c["P"].get("network_life") or c["I"]["life"])
        el_mwh = e["electricity_cost"] / c["P"]["A07"]
        gas_net = float(((b.base_fuel_MWh - b.backup_fuel_MWh) * (b.main_fuel == "gas_or_oil") * ~b.rebuilt.astype(bool)).sum())
        steam_net = float(((b.base_fuel_MWh - b.backup_fuel_MWh) * (b.main_fuel == "steam")).sum())

        def bisect(key, lo, hi, n=30):
            f_lo, f_hi = value({key: lo})[1], value({key: hi})[1]
            if f_lo >= 0:
                return lo
            if f_hi < 0:
                return None
            for _ in range(n):
                mid = 0.5 * (lo + hi)
                if value({key: mid})[1] >= 0:
                    hi = mid
                else:
                    lo = mid
            return hi

        rows.append(dict(
            case=r.case, pick=r.pick, external=r.external, horizon=r.horizon, scope=r["scope"], net_value=v0,
            pipe_cost_needed_usd_per_m=(c["P"]["A05"] + v0 / (s.route_m * markup * (k_net + c["P"]["A22"]))) if s.route_m > 0 else None,
            pipe_cost_now=c["P"]["A05"],
            A17_needed=c["A"]["A17"] + v0 / (s.Q_DC_used_MWh * c["P"]["A07"]) if s.Q_DC_used_MWh else None, A17_now=c["A"]["A17"],
            electricity_price_needed=c["P"]["A07"] + v0 / el_mwh if el_mwh else None, electricity_price_now=c["P"]["A07"],
            gas_price_needed=c["I"]["gas_price"] - v0 / gas_net if gas_net > 0 else None, gas_price_now=c["I"]["gas_price"],
            steam_price_needed=c["I"]["steam_price"] - v0 / steam_net if steam_net > 0 else None, steam_price_now=c["I"]["steam_price"],
            hp_eta_needed=bisect("A10", c["A"]["A10"], 0.95), hp_eta_now=c["A"]["A10"],
            source_temp_needed_C=bisect("A02", c["A"]["A02"], 60.0), source_temp_now_C=c["A"]["A02"],
            scop_now=s.T2_SCOP, carbon_price_needed=(-v0 / e["co2_avoided"]) if v0 < 0 and e["co2_avoided"] > 0 else None,
            capital_grant_share_needed=min(1.0, -v0 / (e["capex_annualised"])) if v0 < 0 else 0.0,
            upfront_grant_equivalent_usd=(-v0 / (e["capex_annualised"] / e["capex_total"])) if v0 < 0 else 0.0,
            annual_support_needed=max(0.0, -v0)))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "break_even.csv", index=False)
    print(d.round(2).T.to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["reconcile", "cases", "post", "breakeven", "all"])
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    from .run_model_c import build_ctx
    for st in (["reconcile", "cases", "breakeven"] if a.stage == "all" else [a.stage]):
        t = time.time()
        if st == "reconcile":
            stage_reconcile(build_ctx())
        elif st == "cases":
            stage_cases(a.workers)
        elif st == "post":
            postprocess_cases()
        else:
            stage_breakeven()
        print(f"[{st}] {time.time() - t:.1f} s")


if __name__ == "__main__":
    main()
