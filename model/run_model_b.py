"""Run Model B over every Model A run (base B parameters) plus one-at-a-time B sensitivity on the
reference design, write outputs/model_b/*, then validate.

    python -m model.run_model_b
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import features as F
from . import model_b as MB

OUT_A = F.ROOT / "outputs" / "model_a"
OUT = F.ROOT / "outputs" / "model_b"
B_SENS = ["A05", "A06", "A07", "A08", "A12", "A21", "A22"]


def kpi_rows(e: dict, s: pd.Series) -> list[dict]:
    vals = {
        "T1": s.T1_recoverable_heat_GWh, "T2": s.T2_SCOP, "T4": s.T4_coverage_pct, "T7": s.T7_route_m,
        "C1": e["capex_total"] / (s.HP_cap_MW * 1000) if s.HP_cap_MW > 0 else np.nan,
        "C2": e["lcoh_system"],
        "C3": 100 * e["annual_savings"] / e["baseline_cost_annual"] if e["baseline_cost_annual"] > 0 else np.nan,
        "N1": 100 * e["erf"] if pd.notna(e["erf"]) else np.nan, "N2": e["co2_avoided"], "N4": e["gas_displaced_MWh"],
        "N6": e["peak_vs_ashp_MW"], "S1": e["low_income_households"], "S3": e["ej_dac_percentile"],
        "S5": np.nan, "S6": np.nan, "S7": e["dc_net"],
    }
    return [dict(run_id=e["run_id"], b_set=e["b_set"], scenario=e["scenario"], kpi_id=k, dimension=d, name=n, unit=u,
                 value=vals[k], source=src, scored_by_C=(u != "qualitative")) for k, d, n, u, src in MB.KPI_DEF]


def stakeholder_rows(e: dict, b: pd.DataFrame) -> list[dict]:
    rid, bs = e["run_id"], e["b_set"]
    R = []
    def add(st, item, value, unit, kind, note=""):
        R.append(dict(run_id=rid, b_set=bs, scenario=e["scenario"], stakeholder=st, item=item, value=value, unit=unit, kind=kind, note=note))
    add("data_center", "net financial value", e["dc_net"], "$/yr", "financial", "heat sales - source-side electricity" + (" (S1: same owner as the heat user)" if e["scenario"] == "S1" else ""))
    add("data_center", "heat-sale revenue (transfer from operator)", e["fence_revenue"], "$/yr", "transfer", f"fence price {e['fence_price_per_MWh']:.1f} $/MWh")
    add("data_center", "source-side electricity cost", -e["source_electricity_cost"], "$/yr", "financial")
    add("heat_users", "tariff + connection paid (transfer to operator)", -(e["tariff_revenue"] + e["connection_revenue"]), "$/yr", "transfer")
    add("data_center", "cooling reliability", "unchanged (H1 pass; towers take 100% in network outage)", "", "non-financial")
    add("heat_users", "net financial value (all connected buildings)", e["users_net"], "$/yr", "financial")
    add("heat_users", "NYCHA bill change per apartment (positive = saving)", e["nycha_net_per_apt"], "$/apt/yr", "financial")
    add("heat_users", "continuity of heat", "no unserved heat in all operating modes", "", "non-financial")
    add("network_operator", "net financial position", e["operator_net"], "$/yr", "financial", "tariff + connection - fence - annualised operator capex - network O&M")
    add("community", "public / ratepayer funding need", e["public_funding_need"], "$/yr", "financial", "operator shortfall, recovered from ratepayers in the pilot model")
    add("community", "CO2 avoided", e["co2_avoided"], "tCO2e/yr", "non-financial")
    add("community", "NOx avoided next to the EJ block", e["nox_avoided_kg"], "kg/yr", "non-financial")
    add("community", "low-income households served", e["low_income_households"], "households", "non-financial")
    add("community", "winter peak vs all-electric", e["peak_vs_ashp_MW"], "MW", "non-financial", "positive = less peak than ASHPs")
    add("community", "LL97 penalty exposure reduced (commercial, upper bound)", e["ll97_upper_bound_commercial"], "$/yr", "context",
        "only if those buildings exceed their LL97 limit; not added to savings")
    add("system", "annual savings (resource view)", e["annual_savings"], "$/yr", "financial", "= sum of actors (transfers cancel)")
    return R


def constraint_rows(e: dict) -> list[dict]:
    rid = e["run_id"]
    has_nycha = e["nycha_apartments"] > 0
    rows = [
        ("H6", "NYCHA heat cost not above today (at pilot tariff)", (e["nycha_net"] >= 0) if has_nycha else None,
         e["nycha_net_per_apt"], ">= 0 $/apt/yr", f"break-even tariff {e['nycha_breakeven_tariff_per_MWh']:.1f} $/MWh vs pilot {e['tariff_per_MWh']:.1f}" if has_nycha else "no NYCHA buildings connected"),
        ("F1", "Society gains: annual savings > 0 (resource view)", e["annual_savings"] > 0, e["annual_savings"], "> 0 $/yr", ""),
        ("F2", "Operator self-financing at the pilot tariff", e["operator_net"] >= 0 if e["scenario"] != "S1" else None, e["operator_net"], ">= 0 $/yr",
         "S1 has no operator" if e["scenario"] == "S1" else "negative = ratepayer/public funding needed"),
        ("F3", "Data center participates willingly (net value >= 0)", e["dc_net"] >= 0, e["dc_net"], ">= 0 $/yr", ""),
        ("F4", "Simple payback within asset life (25 yr)", e["simple_payback_yr"] <= 25, e["simple_payback_yr"], "<= 25 yr", ""),
    ]
    return [dict(run_id=rid, b_set=e["b_set"], scenario=e["scenario"], constraint_id=c, description=d,
                 status=("n/a" if ok is None else ("pass" if ok else "fail")), metric=m, threshold=t, detail=x)
            for c, d, ok, m, t, x in rows]


def delivery_assessment(cfg: dict) -> pd.DataFrame:
    g = pd.read_csv(F.ROOT / "model" / "config" / "delivery_governance.csv")
    rows = []
    for s in cfg["scenarios"]:
        if s == "S0":
            continue
        for r in g.itertuples():
            if r.scenarios == "all" or s in str(r.scenarios).split(";"):
                rows.append(dict(scenario=s, **r._asdict()))
    d = pd.DataFrame(rows).drop(columns="Index")
    return d


def main() -> None:
    t0 = time.time()
    cfg = F.load_config()
    I = MB.load_inputs()
    runs = pd.read_csv(OUT_A / "a_runs.csv")
    sysa = pd.read_csv(OUT_A / "a_annual_system.csv").set_index("run_id")
    blda = pd.read_csv(OUT_A / "a_annual_building.csv", dtype={"property_id": str})
    ref = cfg["reference_design"]
    jobs = [(r, "base", MB.b_params()) for _, r in runs.iterrows()]
    refbase = runs[(runs.assumption_set == "base") & (runs.hp_frac == ref["hp_frac"]) & (runs.tank_hours == ref["tank_hours"])]
    for _, r in refbase.iterrows():
        for aid in B_SENS:
            for lvl in ("low", "high"):
                P = MB.b_params({aid: lvl})
                if P[aid] is None:
                    continue
                jobs.append((r, f"{aid}_{lvl}", P))

    econ, bills, kpis, stake, cons = [], [], [], [], []
    for r, bset, P in jobs:
        s = sysa.loc[r.run_id]
        res = MB.evaluate(r, s, blda[blda.run_id == r.run_id], P, I, bset)
        e = res["econ"]
        econ.append(e)
        if len(res["buildings"]):
            bb = res["buildings"].copy()
            bb.insert(1, "b_set", bset)
            bb.insert(2, "scenario", r.scenario)
            bills.append(bb)
        kpis += kpi_rows(e, s)
        stake += stakeholder_rows(e, res["buildings"])
        cons += constraint_rows(e)

    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(econ).to_csv(OUT / "b_economics.csv", index=False)
    pd.concat(bills).to_csv(OUT / "b_building_bills.csv", index=False)
    pd.DataFrame(kpis).to_csv(OUT / "b_kpis.csv", index=False)
    pd.DataFrame(stake).to_csv(OUT / "b_stakeholder_value.csv", index=False)
    pd.DataFrame(cons).to_csv(OUT / "b_constraints.csv", index=False)
    delivery_assessment(cfg).to_csv(OUT / "b_delivery_assessment.csv", index=False)
    inputs = {k: v for k, v in I.items() if isinstance(v, (int, float))}
    inputs["ef"] = I["ef"]
    (OUT / "b_manifest.json").write_text(json.dumps(dict(model="B", evaluations=len(jobs), seconds=round(time.time() - t0, 1),
        fixed_inputs=inputs, base_parameters=MB.b_params(), sensitivity=B_SENS,
        boundary="served demand of connected buildings; transfers excluded from the system view",
        note="No MCDA score is produced. KPIs are for review before Model C."), indent=2, default=float), encoding="utf-8")
    print(f"Model B: {len(jobs)} evaluations in {time.time() - t0:.1f} s -> {OUT}")
    from .validate_model_b import validate
    validate()


if __name__ == "__main__":
    main()
