"""Validation of Model A. Writes outputs/model_a/a_validation.csv and prints a summary.

    python -m model.validate_model_a
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import features as F
from . import schemas
from .model_a import cop_carnot

OUT = F.ROOT / "outputs" / "model_a"


def validate() -> pd.DataFrame:
    cfg = F.load_config()
    phys = cfg["physics"]
    A = F.assumption_values()
    s = pd.read_csv(OUT / "a_annual_system.csv")
    b = pd.read_csv(OUT / "a_annual_building.csv", dtype={"property_id": str})
    c = pd.read_csv(OUT / "a_constraints.csv")
    rows = []

    def add(tid, name, ok, value, expected, detail=""):
        rows.append(dict(test_id=tid, test=name, status=("info" if ok is None else ("pass" if ok else "fail")),
                         value=value, expected=expected, detail=detail))

    # V1 calibration against the Con Ed Chelsea pilot (S13): same temperatures, A10 base efficiency
    p, e = F.pilot_reference(), F.pilot_electricity_by_end_use()
    cop_dhw = cop_carnot(p["dhw_supply_C"], p["loop_supply_C"], phys, A["A10"])
    cop_sh = cop_carnot(phys["sh_new_supply_C"], p["loop_supply_C"], phys, A["A10"])
    pilot_cop_dhw = p["dhw_MWh"] / (e["dhw_kWh"] / 1000)
    pilot_cop_sh = p["sh_MWh"] / (e["sh_kWh"] / 1000)
    el_model = p["dhw_MWh"] / cop_dhw + p["sh_MWh"] / cop_sh
    el_pilot = (e["dhw_kWh"] + e["sh_kWh"]) / 1000
    for tid, name, mv, pv in (("V1a", "Pilot DHW heat-pump COP", cop_dhw, pilot_cop_dhw),
                              ("V1b", "Pilot space-heat heat-pump COP", cop_sh, pilot_cop_sh),
                              ("V1c", "Pilot heat-pump electricity (MWh/yr)", el_model, el_pilot)):
        err = mv / pv - 1
        add(tid, name, abs(err) <= 0.15, round(mv, 3), f"{pv:.3f} (pilot) +/-15%", f"error {err:+.1%}; loop {p['loop_supply_C']:.1f} C, DHW {p['dhw_supply_C']:.1f} C")

    # V1d informational cross-check with the DEA 10 MW waste-heat datasheet (different machine type)
    dea = pd.read_csv(F.DATA / "processed" / "equipment_dea_heat.csv")
    dea_cop = float(dea.query("ws=='40 Comp. hp, waste heat 10 MW' and year==2030 and parameter=='cop_or_efficiency_annual'").ctrl.iloc[0])
    t_cond, t_evap = 70 + phys["approach_cond_K"] + 273.15, 15 - phys["approach_evap_K"] + 273.15
    add("V1d", "DEA 10 MW datasheet COP at its own temperatures (info)", None, round(A["A10"] * t_cond / (t_cond - t_evap), 2),
        f"{dea_cop} (DEA, two-stage, glide-optimised)", "Single-stage Carnot model is conservative for large two-stage DH heat pumps")

    # V2 energy balances
    add("V2", "Energy balances close in every run", bool((s.balance_max_abs < 1e-6).all()), float(s.balance_max_abs.max()), "< 1e-6")

    # V3 demand bookkeeping: served classes + not served = useful demand
    gap = (s.D_dhw_MWh + s.D_sh45_MWh + s.D_sh_exist_MWh + s.D_sh_not_served_MWh - s.D_useful_connected_MWh).abs().max()
    add("V3", "Demand split adds up (DHW + space heat served + not served = useful demand)", gap < 1e-6, float(gap), "< 1e-6")
    gap2 = (s.Q_network_MWh + s.Q_backup_MWh + s.Q_unserved_MWh - s.D_served_classes_MWh).abs().max()
    add("V3b", "Served demand = network + backup + unserved", gap2 < 1e-6, float(gap2), "< 1e-6")
    gb = b.groupby("run_id")[["Q_network_MWh", "Q_backup_MWh", "E_HP_MWh"]].sum().join(s.set_index("run_id")[["Q_network_MWh", "Q_backup_MWh", "E_HP_MWh"]], rsuffix="_sys")
    gap3 = max((gb[c] - gb[c + "_sys"]).abs().max() for c in ("Q_network_MWh", "Q_backup_MWh", "E_HP_MWh"))
    add("V3c", "Building allocation sums to system totals", gap3 < 1e-6, float(gap3), "< 1e-6")

    # V4 baseline S0 has no network flows
    s0 = s[s.scenario == "S0"]
    add("V4", "S0 (today) has zero network heat and electricity", bool((s0[["Q_network_MWh", "E_network_MWh", "Q_DC_used_MWh"]].abs() < 1e-9).all().all()),
        float(s0.Q_network_MWh.abs().max()), "0")

    # V5 technical constraints in base-assumption runs
    base_ids = set(s.loc[s.assumption_set == "base", "run_id"])
    cb = c[c.run_id.isin(base_ids) & c.constraint_id.isin(["H1", "H2", "H3", "H4", "H5", "H7"])]
    fails = cb[cb.status == "fail"]
    add("V5", "Technical constraints H1-H5, H7 in all base runs", fails.empty, int(len(fails)), "0 failures",
        "; ".join(f"{r.run_id}:{r.constraint_id}" for r in fails.itertuples())[:400])
    add("V5b", "H6 (affordability) deferred to Model B", bool((c[c.constraint_id == "H6"].status == "pending_model_B").all()),
        "pending_model_B", "pending_model_B")

    # V6 monotonic design response
    viol = []
    sb = s[(s.assumption_set == "base") & (s.scenario != "S0")]
    for sc, g in sb.groupby("scenario"):
        for tk, gg in g.groupby("tank_hours"):
            v = gg.sort_values("hp_frac").T4_coverage_pct.to_numpy()
            if (np.diff(v) < -1e-9).any():
                viol.append(f"{sc} tank {tk}: hp")
        for hp, gg in g.groupby("hp_frac"):
            v = gg.sort_values("tank_hours").T4_coverage_pct.to_numpy()
            if (np.diff(v) < -1e-9).any():
                viol.append(f"{sc} hp {hp}: tank")
    add("V6", "Coverage never falls when heat pumps or storage grow", not viol, len(viol), "0", "; ".join(viol))

    # V7 non-residential base-load share reproduces the CBS summer/winter ratio (A20)
    w = F.load_weather()
    bshare = F.nonres_base_share(w, A["A20"])
    hdh = w.groupby("month").HDH_18C.sum() / w.HDH_18C.sum()
    hrs = w.groupby("month").size() / F.HOURS
    m = bshare * hrs + (1 - bshare) * hdh
    add("V7", "Non-residential base-load share reproduces July/January = A20", abs(m[7] / m[1] - A["A20"]) < 1e-9,
        round(float(m[7] / m[1]), 4), A["A20"], f"base-load share = {bshare:.3f}")

    # V8 sensitivity directions
    ref = s[(s.scenario == "S3R")]
    def val(aid, lvl, col):
        r = ref[ref.assumption_set == f"{aid}_{lvl}"]
        return float(r[col].iloc[0]) if len(r) else np.nan
    add("V8a", "Lower DC share (A01 low) lowers recoverable heat", val("A01", "low", "T1_recoverable_heat_GWh") < val("A01", "high", "T1_recoverable_heat_GWh"),
        round(val("A01", "low", "T1_recoverable_heat_GWh"), 1), f"< {val('A01', 'high', 'T1_recoverable_heat_GWh'):.1f}")
    add("V8b", "Warmer source loop (A02 high) raises SCOP", val("A02", "high", "T2_SCOP") > val("A02", "low", "T2_SCOP"),
        round(val("A02", "high", "T2_SCOP"), 2), f"> {val('A02', 'low', 'T2_SCOP'):.2f}")

    # V9 supply ceiling from metered electricity
    ok = bool((s.Q_DC_avail_MWh <= s.E_el_111_MWh * s.P_DC_avg_MW / (s.E_el_111_MWh / 8760) + 1e-6).all())
    add("V9", "Recoverable heat <= metered electricity x DC share", ok, float(s.Q_DC_avail_MWh.max()), "<= E_el x A01")

    # V10 de-duplication of LL84 filings
    o = pd.read_csv(F.ROOT / "outputs" / "features" / "offtakers_features.csv", dtype={"property_id": str})
    add("V10", "Duplicate LL84 filings removed (Maritime = 363 W 16th St; 61 9th Ave single row)",
        ("3177669" not in set(o.property_id)) and (o.property_id == "8899918").sum() == 1, len(o), "Maritime dropped, 61 9th once")

    # V11 no score from Model A alone
    try:
        schemas.assert_composite_ready(["T1", "T2", "T4", "T7"])
        add("V11", "Composite refused with Technical KPIs only", False, "score built", "ValueError")
    except ValueError as ex:
        add("V11", "Composite refused with Technical KPIs only", True, "refused", "ValueError", str(ex))

    # V12 operating modes: cooling independence and backup
    om = pd.read_csv(OUT / "a_operating_modes.csv")
    bad = om[om.status != "pass"]
    add("V12", "Operating modes M1-M5: no unserved heat, DC heat always rejectable", bad.empty, int(len(bad)), "0 failures",
        "; ".join(f"{r.scenario}:{r.mode}" for r in bad.itertuples()))
    m4 = om[om["mode"] == "M4_network_outage_72h"]
    add("V12b", "Network outage: towers take 100% of DC heat; buildings on backup + local tanks, no unserved heat",
        bool((m4.dc_heat_to_towers_pct > 99.999).all() and (m4.unserved_MWh < 1e-6).all()),
        float(m4.dc_heat_to_towers_pct.min()), "100% and 0 MWh unserved",
        "network_heat during M4 is discharge from building tanks only")

    # V13 requirement-to-output coverage: every official requirement maps to a registered output
    cov = pd.read_csv(F.ROOT / "model" / "config" / "requirements_coverage.csv")
    reg = set(schemas.TABLES)
    problems = []
    for r in cov.itertuples():
        found = False
        for tok in str(r.outputs).split(";"):
            t = tok.strip().split(" ")[0]
            if t.startswith(("model_a/", "model_b/", "model_c/", "config/")):
                if t not in reg:
                    problems.append(f"{r.req_id}: {t} not in schema registry")
                found = True
                if t.startswith("model_a/") and "<run_id>" not in t and not (OUT.parent / t).exists() and t != "model_a/a_validation.csv":
                    problems.append(f"{r.req_id}: {t} missing on disk")
            elif t.startswith(("data/", "outputs/")):
                found = True
                if not (F.ROOT / t).exists():
                    problems.append(f"{r.req_id}: {t} missing")
            elif t.startswith(("model/schemas.py", "see")):
                found = True
        if not found:
            problems.append(f"{r.req_id}: no output mapped")
    add("V13", f"Every official requirement ({len(cov)}) maps to a registered output", not problems, len(problems), "0", "; ".join(problems)[:400])

    # V14 governance register completeness (unscored, evidence-backed)
    gv = pd.read_csv(F.ROOT / "model" / "config" / "delivery_governance.csv")
    aspects = set(schemas.registry()["governance_aspects"])
    miss_a = aspects - set(gv.aspect)
    miss_s = {"data_center", "heat_users", "community"} - set(gv[gv.aspect == "stakeholder_value"].stakeholder)
    no_ev = gv[gv.evidence_source.isna() & (gv.evidence_level != "open_issue")]
    add("V14", "Governance register covers all aspects and the three stakeholders, every item sourced",
        not miss_a and not miss_s and no_ev.empty, len(gv), f"{len(aspects)} aspects, 3 stakeholders",
        f"missing aspects {sorted(miss_a)}; missing stakeholders {sorted(miss_s)}; unsourced {list(no_ev.item_id)}")

    v = pd.DataFrame(rows)
    v.to_csv(OUT / "a_validation.csv", index=False)
    print(v[["test_id", "status", "test", "value", "expected"]].to_string(index=False))
    return v


if __name__ == "__main__":
    validate()
