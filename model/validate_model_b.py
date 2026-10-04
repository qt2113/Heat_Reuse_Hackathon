"""Validation of Model B. Writes outputs/model_b/b_validation.csv.

    python -m model.validate_model_b
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import features as F
from . import schemas

OUT = F.ROOT / "outputs" / "model_b"


def validate() -> pd.DataFrame:
    cfg = F.load_config()
    ref = cfg["reference_design"]
    e = pd.read_csv(OUT / "b_economics.csv")
    b = pd.read_csv(OUT / "b_building_bills.csv", dtype={"property_id": str})
    k = pd.read_csv(OUT / "b_kpis.csv")
    c = pd.read_csv(OUT / "b_constraints.csv")
    rows = []

    def add(tid, name, ok, value, expected, detail=""):
        rows.append(dict(test_id=tid, test=name, status=("info" if ok is None else ("pass" if ok else "fail")),
                         value=value, expected=expected, detail=detail))

    # B1 transfers cancel: actors' net = system savings
    gap = float((e.actors_sum - e.annual_savings).abs().max())
    add("B1", "Transfers cancel: data center + users + operator = system savings", gap < 1e-3, gap, "< 0.001 $/yr")

    # B2 one baseline per building across scenarios
    rb = b[(b.b_set == "base") & b.run_id.str.endswith(f"_hp{ref['hp_frac']:g}_tk{ref['tank_hours']:g}_base")]
    spread = rb.groupby("property_id").base_cost.agg(lambda s: s.max() - s.min())
    add("B2", "Each building has the same baseline cost in every scenario", float(spread.max()) < 1e-6, float(spread.max()), "0",
        f"{(rb.groupby('property_id').scenario.nunique() > 1).sum()} buildings appear in more than one scenario")

    # B3 S0 has no costs and no savings
    s0 = e[e.scenario == "S0"]
    add("B3", "S0 (today) has zero project cost and savings", bool((s0[["capex_total", "annual_savings", "co2_avoided"]].abs() < 1e-9).all().all()),
        float(s0.capex_total.abs().max()), "0")

    # B4 carbon bookkeeping
    g = b.groupby(["run_id", "b_set"])[["base_co2", "proj_co2"]].sum()
    m = e.set_index(["run_id", "b_set"]).join(g)
    gap = float(((m.co2_baseline - m.base_co2).abs() + (m.co2_project - m.proj_co2).abs()).max(skipna=True))
    add("B4", "Carbon: system = sum of buildings; avoided = baseline - project", gap < 1e-6 and bool(((e.co2_baseline - e.co2_project - e.co2_avoided).abs() < 1e-6).all()), gap, "< 1e-6")

    # B5 plausibility of LCOH
    l = e.loc[e.network_heat_MWh > 0, "lcoh_system"]
    add("B5", "System LCOH positive and finite in every run with network heat", bool(np.isfinite(l).all() and (l > 0).all()), f"{l.min():.0f}-{l.max():.0f}", "> 0, finite")
    # B5b cross-check: the Con Ed pilot priced with the same method (construction categories of Table 11)
    from . import model_b as MB
    I, P = MB.load_inputs(), MB.b_params()
    pil = pd.read_csv(F.DATA / "reference" / "chelsea_uten_pilot_stage2.csv").set_index("metric").value
    bench = pd.read_csv(F.DATA / "processed" / "chelsea_uten_benchmarks.csv").set_index("metric").value
    constr = sum(float(pil[m]) for m in ("UDS_construction", "thermal_resource_construction", "energy_center_construction", "customer_building_construction")) * 1e6
    pilot_lcoh = (constr * (1 + I["contingency"] + P["A21"]) * MB.crf(P["A08"], I["life"])
                  + float(bench["electricity_added_customer_plus_source"]) * P["A07"]) / float(bench["useful_heat_supplied_by_UTEN"])
    s3 = float(e[(e.scenario == "S3") & (e.b_set == "base") & (e.run_id == f"S3_hp{ref['hp_frac']:g}_tk{ref['tank_hours']:g}_base")].lcoh_system.iloc[0])
    add("B5b", "Con Ed pilot priced with the same method (reference for S3)", None, round(pilot_lcoh, 0), f"S3 = {s3:.0f} $/MWh",
        "pilot: 34.99 M$ construction, 2,680 MWh/yr, 1,514 MWh/yr added electricity")

    # B6 sensitivity directions (reference design, S3R and S2)
    def val(scen, bset, col):
        r = e[(e.scenario == scen) & (e.b_set == bset) & (e.run_id == f"{scen}_hp{ref['hp_frac']:g}_tk{ref['tank_hours']:g}_base")]
        return float(r[col].iloc[0])
    checks = [
        ("electricity price raises LCOH", val("S3R", "A07_high", "lcoh_system") > val("S3R", "A07_low", "lcoh_system")),
        ("discount rate raises LCOH", val("S3R", "A08_high", "lcoh_system") > val("S3R", "A08_low", "lcoh_system")),
        ("pipe cost raises CAPEX", val("S2", "A05_high", "capex_total") > val("S2", "A05_low", "capex_total")),
        ("fence price raises data-center value", val("S2", "A06_high", "dc_net") > val("S2", "A06_low", "dc_net")),
        ("fence price lowers operator position", val("S2", "A06_high", "operator_net") < val("S2", "A06_low", "operator_net")),
        ("fence price leaves system savings unchanged", abs(val("S2", "A06_high", "annual_savings") - val("S2", "A06_low", "annual_savings")) < 1e-6),
    ]
    bad = [n for n, ok in checks if not ok]
    add("B6", "Sensitivity directions are physical (and transfers do not change system savings)", not bad, len(bad), "0", "; ".join(bad))

    # B7 KPI completeness: all quantitative KPIs present for S1-S3R reference base
    kr = k[(k.b_set == "base") & k.run_id.str.endswith(f"_hp{ref['hp_frac']:g}_tk{ref['tank_hours']:g}_base") & (k.scenario != "S0")]
    miss = kr[kr.scored_by_C & kr.value.isna()]
    add("B7", "All quantitative KPIs computed for S1-S3R", miss.empty, len(miss), "0", "; ".join(f"{r.scenario}:{r.kpi_id}" for r in miss.itertuples()))
    dims = set(kr.dimension)
    add("B7b", "KPIs cover all four dimensions", dims == set(schemas.DIMENSIONS), len(dims), 4)

    # B8 S1 internal: no transfers
    s1 = e[e.scenario == "S1"]
    add("B8", "S1 (single owner) books no heat sales, tariffs or operator", bool((s1[["fence_revenue", "tariff_revenue", "operator_net"]].abs() < 1e-9).all().all()), 0, "0")

    # B9 pilot cross-checks (information)
    s3 = b[(b.scenario == "S3") & (b.b_set == "base") & b.is_nycha.astype(bool)]
    add("B9", "S3 NYCHA building-side cost per apartment equals the pilot (incl. markups)", None,
        round(float((s3.bld_capex / s3.units).median()), 0), "39,759 $/apt (hot-water-only scope, S13 p.90) x (1 + 15% contingency + A21)")

    # B10 constraints recorded; no score produced
    add("B10", "H6 and F1-F4 evaluated for every run", bool(c.groupby("run_id").constraint_id.nunique().eq(5).all()), int(c.run_id.nunique()), "5 checks per run")
    score_cols = [col for f in OUT.glob("b_*.csv") for col in pd.read_csv(f, nrows=0).columns if col.lower().startswith(("score_", "overall", "composite"))]
    add("B11", "Model B produces no MCDA scores (scoring belongs to Model C)", not score_cols, len(score_cols), "0", "; ".join(score_cols))

    v = pd.DataFrame(rows)
    v.to_csv(OUT / "b_validation.csv", index=False)
    print(v[["test_id", "status", "test", "value", "expected"]].to_string(index=False))
    return v


if __name__ == "__main__":
    validate()
