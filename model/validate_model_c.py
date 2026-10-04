"""Validation of Model C (and re-check of Models A and B). Writes outputs/model_c/c_validation.csv."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import features as F
from . import model_a as MA
from . import model_c as MC

OUT = F.ROOT / "outputs" / "model_c"


def validate(ctx: dict | None = None) -> pd.DataFrame:
    if ctx is None:
        from .run_model_c import build_ctx
        ctx = build_ctx()
    c = pd.read_csv(OUT / "c_configurations.csv")
    cand = pd.read_csv(OUT / "c_candidates.csv", dtype={"property_id": str})
    recs = json.loads((OUT / "c_recommendations.json").read_text(encoding="utf-8"))
    rows = []

    def add(tid, name, ok, value, expected, detail=""):
        rows.append(dict(test_id=tid, test=name, status=("info" if ok is None else ("pass" if ok else "fail")),
                         value=value, expected=expected, detail=detail))

    # C1 previous model tests still pass
    for m, f in (("A", F.ROOT / "outputs" / "model_a" / "a_validation.csv"), ("B", F.ROOT / "outputs" / "model_b" / "b_validation.csv")):
        v = pd.read_csv(f)
        add(f"C1{m}", f"All Model {m} tests still pass", bool((v.status != "fail").all()), int((v.status == "fail").sum()), "0 failures")

    # C2 merit dispatch = validated class policy when supply does not bind (reference scenarios)
    cfg, bundle, A = ctx["cfg"], ctx["bundle"], ctx["A"]
    worst = 0.0
    for s in ("S1", "S2", "S3", "S3R"):
        spec = MA.RunSpec(f"{s}_chk", s, cfg["reference_design"]["hp_frac"], cfg["reference_design"]["tank_hours"])
        a = MA.simulate(spec, cfg, bundle, A)["summary"]
        m = MA.simulate(spec, cfg, bundle, A, policy="merit", dispatch_value={})["summary"]
        worst = max(worst, max(abs(a[k] - m[k]) for k in ("Q_network_MWh", "Q_backup_MWh", "E_HP_MWh", "Q_DC_used_MWh")))
    add("C2", "Merit allocation reproduces validated Model A totals for S1-S3R", worst < 1e-6, worst, "< 1e-6 MWh")

    # C3 physics in every enumerated configuration
    add("C3", f"Energy balance closes in all {len(c)} configurations", bool((c.balance_max_abs < 1e-6).all()), float(c.balance_max_abs.max()), "< 1e-6")
    add("C4", "No double counting: buildings' loop heat sums to the network's data-center heat", bool((c.Q_loop_sum_gap < 1e-6).all()),
        float(c.Q_loop_sum_gap.max()), "< 1e-6 MWh")
    add("C4b", "Data-center heat used never exceeds heat available (H3) in any configuration",
        not c.failed_checks.fillna("").str.contains("H3").any(), int(c.failed_checks.fillna("").str.contains("H3").sum()), "0 violations")
    add("C5", "Financial transfers cancel in every configuration (actors = system)", bool((c.actors_gap < 1e-3).all()), float(c.actors_gap.max()), "< 0.001 $/yr")

    # C6 optimizer respects feasibility
    bad = []
    for h, r in recs.items():
        for p, ch in r.items():
            if p.startswith("explanation") or not ch.get("config_id"):
                continue
            row = c[c.config_id == ch["config_id"]].iloc[0]
            anyfull = ((c.horizon == h) & (c.feasibility == "fully_feasible") & (c.n_buildings > 0)).any()
            if row.feasibility == "infeasible" or row.n_buildings == 0 or (anyfull and row.feasibility != "fully_feasible"):
                bad.append(f"{h}:{p}")
            if not anyfull and ch["message"] != "No fully feasible configuration under the current assumptions.":
                bad.append(f"{h}:{p}: missing message")
    add("C6", "Recommendations respect feasibility (and say so when nothing is fully feasible)", not bad, len(bad), "0", "; ".join(bad))

    # C7 weights must sum to 100%
    try:
        MC.check_weights(dict(zip(MC.DIMS, (0.4, 0.4, 0.4, 0.4))))
        ok = False
    except ValueError:
        ok = True
    add("C7", "Weights that do not sum to 100% are rejected", ok, "rejected" if ok else "accepted", "rejected")

    # C8 selection follows weights: single-dimension weights pick the best eligible configuration in that dimension
    viol = []
    for h in c.horizon.unique():
        d = c[c.horizon == h].reset_index(drop=True)
        cand_pool = d[(d.n_buildings > 0) & (d.feasibility == ("fully_feasible" if (d.feasibility == "fully_feasible").any() else "conditionally_feasible"))]
        for dim in MC.DIMS:
            w = {x: (1.0 if x == dim else 0.0) for x in MC.DIMS}
            ch = MC.choose(d, w)
            best = cand_pool[f"score_{MC.DIM_KEY[dim]}"].max()
            got = float(d.loc[d.config_id == ch["config_id"], f"score_{MC.DIM_KEY[dim]}"].iloc[0])
            if abs(got - best) > 1e-12:
                viol.append(f"{h}:{dim}")
    add("C8", "Single-dimension weights select the best eligible configuration in that dimension", not viol, len(viol), "0", "; ".join(viol))

    # C9 weights never change a configuration's physical / economic results
    kcols = [i[0] for i in MC.INDICATORS] + ["Q_network_MWh", "capex_total"]
    before = c[kcols].copy()
    _ = MC.overall(c, dict(zip(MC.DIMS, (0.7, 0.1, 0.1, 0.1))))
    _ = MC.overall(c, dict(zip(MC.DIMS, (0.1, 0.1, 0.1, 0.7))))
    add("C9", "Changing weights leaves every configuration's KPIs unchanged", bool(before.equals(c[kcols])), "identical", "identical")
    ch_counts = pd.read_csv(OUT / "c_weight_sensitivity.csv").groupby("horizon").winner.nunique()
    add("C9b", "Different weights can select different networks (weight grid, 10% steps)", None, ch_counts.to_dict(), "> 1 winner where trade-offs exist")

    # C10 missing / unsupported data never enters a configuration
    used = set("|".join(c.members.fillna("")).split("|")) - {""}
    excluded = set(cand.loc[cand.status == "excluded", "property_id"])
    add("C10", "Excluded candidates (missing or insufficient data) never appear in a configuration", not (used & excluded), len(used & excluded), "0")
    add("C10b", "Every excluded or non-shortlisted record has a stated reason",
        bool(cand.loc[cand.status != "shortlisted", "exclusion_reason"].fillna("").str.len().gt(0).all()), int((cand.status != "shortlisted").sum()), "all")
    add("C10c", "Shortlisted candidates are unique LL84 properties", bool(cand.loc[cand.status == "shortlisted", "property_id"].is_unique), int((cand.status == "shortlisted").sum()), "unique")

    # C11 operational optimisation adds value when supply binds (stress: DC share A01 low, all today candidates)
    from . import model_b as MB
    A_low = dict(A, A01=0.3)
    today = [m for m in c[c.horizon == "today"].members.iloc[-1].split("|")]
    spec = MA.RunSpec("stress", "stress", cfg["reference_design"]["hp_frac"], cfg["reference_design"]["tank_hours"])
    fuel = ctx["offt"].set_index("property_id").main_fuel
    dv = {m: ctx["dv"][fuel.get(m, "gas_or_oil")] for m in today}
    vals = {}
    for pol in ("class_priority", "merit"):
        r = MA.simulate(spec, cfg, bundle, A_low, scen_override={"members": today}, policy=pol, dispatch_value=dv)
        run = pd.Series(dict(run_id="stress", scenario="stress", hp_frac=0.75, tank_hours=2, assumption_set="stress", internal=False))
        vals[pol] = MB.evaluate(run, pd.Series(r["summary"]), r["buildings"], ctx["P"], ctx["I"])["econ"]["annual_savings"]
    add("C11", "When heat is scarce, merit allocation is worth at least as much as class priority", vals["merit"] >= vals["class_priority"] - 1e-6,
        round(vals["merit"] - vals["class_priority"], 0), ">= 0 $/yr", f"A01 = 0.3, all {len(today)} today candidates")

    # C12 Pareto set is non-dominated; C13 today (no network) is never recommended
    cols = [f"score_{MC.DIM_KEY[d]}" for d in MC.DIMS]
    p = c[c.pareto]
    dom = 0
    for h in c.horizon.unique():
        X = c[(c.horizon == h) & (c.n_buildings > 0) & c.tech_ok][cols].to_numpy()
        for x in p[p.horizon == h][cols].to_numpy():
            dom += int(((X >= x).all(axis=1) & (X > x).any(axis=1)).any())
    add("C12", "Pareto configurations are non-dominated", dom == 0, dom, "0")
    add("C13", "'No network' is never recommended", all(not str(ch.get("config_id", "")).endswith("|none") for r in recs.values()
                                                       for k, ch in r.items() if not k.startswith("explanation")), "never", "never")

    # C14 screening is configurable, and the configured reference values reproduce the validated shortlist
    from .run_model_c import screen
    short, params = screen(ctx)
    same = set(short.loc[short.status == "shortlisted", "property_id"]) == set(cand.loc[cand.status == "shortlisted", "property_id"])
    add("C14", "Configured screening parameters reproduce the reference shortlist", same, json.dumps(params), "same 10 buildings")

    v = pd.DataFrame(rows)
    v.to_csv(OUT / "c_validation.csv", index=False)
    print(v[["test_id", "status", "test", "value", "expected"]].to_string(index=False))
    return v


if __name__ == "__main__":
    validate()
