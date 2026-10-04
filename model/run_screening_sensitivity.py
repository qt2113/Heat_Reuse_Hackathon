"""Sensitivity of Model C to the candidate-screening choices (search radius, shortlist size, per-type cap).

For each experiment the full Model C chain is rerun: screening -> exhaustive enumeration of both horizons
-> Model A merit dispatch -> Model B -> feasibility -> indicators. Assumptions, physics and tariff rule are
the reference ones; only the screening parameters change. The validated reference outputs in
outputs/model_c/ are never written; everything goes to outputs/model_c/screening_sensitivity/.

    python -m model.run_screening_sensitivity            # all experiments, 4 worker processes
    python -m model.run_screening_sensitivity --workers 1

MCDA scores are min-max normalised within each experiment's enumerated set, so they are not comparable
across experiments; the physical and economic KPIs (heat, $/yr, tCO2, households) are.
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import features as F
from . import model_c as MC

OUT = F.ROOT / "outputs" / "model_c" / "screening_sensitivity"
REF_OUT = F.ROOT / "outputs" / "model_c"
DEFAULT_W = MC.PRESETS["equal (demonstration baseline)"]
MSG = "No fully feasible configuration under the current assumptions."


def experiments(suite: str = "screening") -> list[dict]:
    if suite == "threshold":       # final screening audit: smaller buildings (fuel input 0.5 / 1 GWh/yr), 1 km
        exps = [dict(search_radius_m=1000, max_candidates=n, max_candidates_per_building_type=cap, min_annual_heat_demand_gwh=g)
                for g in (0.5, 1.0) for n, cap in ((10, 2), (12, None))]
    else:
        exps = [dict(search_radius_m=r, max_candidates=n, max_candidates_per_building_type=2)
                for r in (500, 750, 1000) for n in (5, 10, 12)]
        exps += [dict(search_radius_m=r, max_candidates=n, max_candidates_per_building_type=None)
                 for r, n in ((1000, 10), (1000, 12), (750, 12), (500, 12))]
    for e in exps:
        e.setdefault("min_annual_heat_demand_gwh", 2.0)
        cap = "nocap" if e["max_candidates_per_building_type"] is None else f"cap{e['max_candidates_per_building_type']}"
        g = "" if e["min_annual_heat_demand_gwh"] == 2.0 else f"_G{e['min_annual_heat_demand_gwh']:g}"
        e["experiment_id"] = f"R{e['search_radius_m']}_N{e['max_candidates']}_{cap}{g}"
    return exps


def _pick(df: pd.DataFrame, cid: str | None, prefix: str) -> dict:
    if not cid:
        return {f"{prefix}_config_id": None}
    r = df[df.config_id == cid].iloc[0]
    return {f"{prefix}_config_id": cid, f"{prefix}_names": r.names, f"{prefix}_n_buildings": int(r.n_buildings),
            f"{prefix}_heat_reused_MWh": float(r.Q_DC_used_MWh), f"{prefix}_heat_delivered_MWh": float(r.Q_network_MWh),
            f"{prefix}_net_value_usd_yr": float(r.E_val), f"{prefix}_co2_avoided_t": float(r.N_co2),
            f"{prefix}_low_income_households": float(r.S_li), f"{prefix}_community_facilities": int(r.S_fac),
            f"{prefix}_funding_need_usd_yr": float(r.E_fund), f"{prefix}_feasibility": r.feasibility,
            f"{prefix}_failed_checks": r.failed_checks, f"{prefix}_capex_usd": float(r.capex_total),
            f"{prefix}_lcoh_usd_MWh": float(r.E_lcoh), f"{prefix}_carbon_price_to_close": float(r.f1_carbon_price_to_close)}


def summarise(df: pd.DataFrame) -> dict:
    nets = df[(df.n_buildings > 0) & df.tech_ok]
    multi = nets[nets.n_buildings >= 2]
    ch = MC.choose(df, DEFAULT_W)
    out = dict(n_configurations=len(df), n_technically_feasible=len(nets),
               n_fully_feasible=int((nets.feasibility == "fully_feasible").sum()),
               n_pass_F1_society=int(nets.F1_society.sum()), n_pass_F2_operator=int(nets.F2_operator.sum()),
               n_closable_by_all_levers=int(nets.f1_closable_by_levers.sum()),
               recommendation_status=ch["status"], recommendation_message=ch["message"])
    out.update(_pick(df, ch["config_id"], "rec"))
    out.update(_pick(df, nets.loc[nets.E_val.idxmax(), "config_id"] if len(nets) else None, "mincost"))
    out.update(_pick(df, multi.loc[multi.E_val.idxmax(), "config_id"] if len(multi) else None, "mincost_multi"))
    return out


def run_experiment(exp: dict) -> dict:
    from .run_model_c import build_ctx, enumerate_horizon, horizons, screen
    t0 = time.time()
    ctx = build_ctx()
    t_ctx = time.time() - t0
    overrides = {k: exp[k] for k in MC.SCREENING_KEYS}
    t1 = time.time()
    short, params = screen(ctx, overrides)
    H = horizons(short, ctx["cfg"])
    rows, tables = [], []
    for hname, cands in H.items():
        th = time.time()
        df, _ = enumerate_horizon(hname, cands, ctx)
        tables.append(df)
        rows.append(dict(experiment_id=exp["experiment_id"], **params, horizon=hname, n_candidates=len(cands),
                         seconds=round(time.time() - th, 1), **summarise(df)))
    sec = time.time() - t1
    out = F.Path(exp["out_dir"]) if "out_dir" in exp else OUT
    short[["property_id", "property_name", "use_type", "dist_m", "heat_fuel_MWh", "servable_share", "screen_index", "screen_rank",
           "category", "status", "exclusion_reason"]].to_csv(out / f"candidates_{exp['experiment_id']}.csv", index=False)
    pd.concat(tables, ignore_index=True).to_csv(out / f"configurations_{exp['experiment_id']}.csv.gz", index=False)
    head = dict(experiment_id=exp["experiment_id"], **params,
                n_eligible=int(short.status.isin(["shortlisted", "eligible_not_shortlisted"]).sum()),
                n_shortlisted=int((short.status == "shortlisted").sum()),
                shortlist="; ".join(short.loc[short.status == "shortlisted", "property_name"]),
                n_configurations=int(sum(len(t) for t in tables)), seconds_model_c=round(sec, 1), seconds_setup=round(t_ctx, 1))
    return dict(head=head, rows=rows)


def check_reference(summary: pd.DataFrame) -> pd.DataFrame:
    """The 1 km / 10 / cap-2 experiment must reproduce the validated reference outputs exactly."""
    ref = pd.read_csv(REF_OUT / "c_configurations.csv")
    new = pd.read_csv(OUT / "configurations_R1000_N10_cap2.csv.gz")
    keys = ["E_val", "N_co2", "Q_DC_used_MWh", "Q_network_MWh", "S_li", "E_fund", "capex_total", "overall_equal_weights"]
    m = ref.merge(new, on="config_id", suffixes=("_ref", "_new"))
    worst = max(float((m[f"{k}_ref"] - m[f"{k}_new"]).abs().max()) for k in keys)
    same_feas = bool((m.feasibility_ref == m.feasibility_new).all())
    recs = json.loads((REF_OUT / "c_recommendations.json").read_text(encoding="utf-8"))
    s = summary[summary.experiment_id == "R1000_N10_cap2"].set_index("horizon")
    same_rec = all(recs[h]["equal (demonstration baseline)"]["config_id"] == s.loc[h, "rec_config_id"] for h in s.index)
    rows = [dict(test_id="S1", test="Reference experiment enumerates the same configurations as outputs/model_c",
                 status="pass" if len(m) == len(ref) == len(new) else "fail", value=f"{len(m)} / {len(ref)}", expected="all"),
            dict(test_id="S2", test="Reference experiment reproduces every KPI and feasibility class",
                 status="pass" if worst < 1e-6 and same_feas else "fail", value=worst, expected="< 1e-6"),
            dict(test_id="S3", test="Reference experiment reproduces the equal-weights recommendation",
                 status="pass" if same_rec else "fail", value=same_rec, expected=True)]
    v = pd.DataFrame(rows)
    v.to_csv(OUT / "validation.csv", index=False)
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", nargs="*", help="experiment ids to run")
    ap.add_argument("--suite", default="screening", choices=["screening", "threshold"])
    a = ap.parse_args()
    global OUT
    if a.suite != "screening":
        OUT = OUT.parent / f"{OUT.name}_{a.suite}"
    OUT.mkdir(parents=True, exist_ok=True)
    exps = [dict(e, out_dir=str(OUT)) for e in experiments(a.suite) if not a.only or e["experiment_id"] in a.only]
    t0 = time.time()
    if a.workers > 1:
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            res = list(ex.map(run_experiment, exps))
    else:
        res = [run_experiment(e) for e in exps]
    head = pd.DataFrame([r["head"] for r in res])
    summ = pd.DataFrame([row for r in res for row in r["rows"]])
    head.to_csv(OUT / "experiments.csv", index=False)
    summ.to_csv(OUT / "summary.csv", index=False)
    nets = summ.dropna(subset=["mincost_config_id"])
    best = {h: g.loc[g.mincost_net_value_usd_yr.idxmax()][["experiment_id", "mincost_config_id", "mincost_names", "mincost_net_value_usd_yr"]].to_dict()
            for h, g in nets.groupby("horizon")}
    bestm = {h: g.loc[g.mincost_multi_net_value_usd_yr.idxmax()][["experiment_id", "mincost_multi_config_id", "mincost_multi_names",
                                                                   "mincost_multi_net_value_usd_yr"]].to_dict()
             for h, g in summ.dropna(subset=["mincost_multi_config_id"]).groupby("horizon")}
    verdict = dict(
        any_fully_feasible=bool((summ.n_fully_feasible > 0).any()),
        any_pass_F1_society=bool((summ.n_pass_F1_society > 0).any()),
        message_in_every_experiment=bool((summ.recommendation_message == MSG).all()),
        lowest_additional_cost=best, lowest_additional_cost_multi_building=bestm,
        wall_seconds=round(time.time() - t0, 1), workers=a.workers,
        note="MCDA scores are normalised within each experiment and are not comparable across experiments; KPIs are.")
    (OUT / "verdict.json").write_text(json.dumps(verdict, indent=2, default=str), encoding="utf-8")
    if "R1000_N10_cap2" in set(head.experiment_id):
        print(check_reference(summ).to_string(index=False))
    print(head[["experiment_id", "n_eligible", "n_shortlisted", "n_configurations", "seconds_model_c"]].to_string(index=False))
    print(json.dumps(verdict, indent=2, default=str))


if __name__ == "__main__":
    main()
