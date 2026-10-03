"""Run Model A for every scenario x design (base assumptions) and one-at-a-time sensitivity runs,
write outputs/model_a/*, the feature tables and the schema registry, then validate.

    python -m model.run_model_a
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import features as F
from . import schemas
from .model_a import RunSpec, simulate

OUT = F.ROOT / "outputs"


def load_bundle() -> dict:
    weather = F.load_weather()
    offt, dropped = F.build_offtakers()
    sh, dhw = F.hourly_shapes(weather)
    pilot = F.pilot_reference()
    return dict(weather=weather, offtakers=offt, dropped=dropped, shape_sh=sh, shape_dhw=dhw,
                E_el_111=F.source_annual_electricity_MWh(), T_design=F.design_temperature(),
                q_dhw_apt=pilot["dhw_MWh"] / pilot["apartments"])


def run_specs(cfg: dict) -> list[RunSpec]:
    specs, ref = [], cfg["reference_design"]
    for s in cfg["scenarios"]:
        for hp in cfg["design_grid"]["hp_frac"]:
            for tk in cfg["design_grid"]["tank_hours"]:
                specs.append(RunSpec(f"{s}_hp{hp:g}_tk{tk:g}_base", s, hp, tk))
        for aid in cfg["sensitivity_assumptions"]:
            for lvl in ("low", "high"):
                specs.append(RunSpec(f"{s}_hp{ref['hp_frac']:g}_tk{ref['tank_hours']:g}_{aid}_{lvl}", s,
                                     ref["hp_frac"], ref["tank_hours"], f"{aid}_{lvl}", aid, lvl))
    return specs


def operating_modes(cfg: dict, bundle: dict) -> pd.DataFrame:
    """Cooling-independence and backup stress tests on each scenario's reference design (base assumptions)."""
    ref, H = cfg["reference_design"], F.HOURS
    T = bundle["weather"].dry_bulb_C.to_numpy(float)
    wk = int(np.argmin(np.convolve(T, np.ones(168) / 168, mode="valid")))      # start of the coldest week
    A = F.assumption_values()
    rows = []
    for s in cfg["scenarios"]:
        if s == "S0":
            continue
        spec = RunSpec(f"{s}_hp{ref['hp_frac']:g}_tk{ref['tank_hours']:g}_base", s, ref["hp_frac"], ref["tank_hours"])
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
            r = simulate(spec, cfg, bundle, A, stress)
            hr, sm = r["hourly"], r["summary"]
            e = hr[win]
            raw = e.Q_DC_used_MW + e.Q_rejected_MW
            rows.append(dict(
                scenario=s, mode=mode, description=m["description"], event_hours=int(win.sum()),
                event_start_hour=int(np.argmax(win)) + 1 if win.any() else None,
                demand_MWh=float(e.D_total_MW.sum()), network_heat_MWh=float((e.Q_HP_to_load_MW + e.Q_discharge_MW).sum()),
                backup_heat_MWh=float(e.Q_backup_MW.sum()), backup_peak_MW=float(e.Q_backup_MW.max()),
                backup_cap_MW=sm["backup_cap_MW"], unserved_MWh=float(e.Q_unserved_MW.sum()),
                dc_heat_to_towers_pct=float(100 * e.Q_rejected_MW.sum() / raw.sum()) if raw.sum() > 0 else 100.0,
                min_heat_to_towers_MW=float(e.Q_rejected_MW.min()),
                cooling_dependency="none: towers keep full rejection capacity; network takes at most "
                                   f"{100 * (e.Q_DC_used_MW / raw).max():.0f}% of DC heat in any hour",
                status="pass" if (e.Q_unserved_MW.sum() < 1e-6 and e.Q_rejected_MW.min() >= -1e-9) else "fail"))
    return pd.DataFrame(rows)


def main() -> None:
    t0 = time.time()
    cfg = F.load_config()
    bundle = load_bundle()
    (OUT / "model_a" / "hourly").mkdir(parents=True, exist_ok=True)
    (OUT / "features").mkdir(parents=True, exist_ok=True)
    bundle["offtakers"].to_csv(OUT / "features" / "offtakers_features.csv", index=False)
    bundle["dropped"].to_csv(OUT / "features" / "offtakers_dropped_duplicates.csv", index=False)

    ref = cfg["reference_design"]
    runs, summ, blds, cons, monthly = [], [], [], [], []
    for spec in run_specs(cfg):
        A = F.assumption_values({spec.varied: spec.level} if spec.varied else None)
        res = simulate(spec, cfg, bundle, A)
        runs.append(dict(run_id=spec.run_id, scenario=spec.scenario, hp_frac=spec.hp_frac, tank_hours=spec.tank_hours,
                         assumption_set=spec.assumption_set, varied=spec.varied, level=spec.level,
                         is_reference=(spec.hp_frac == ref["hp_frac"] and spec.tank_hours == ref["tank_hours"]),
                         **{f"param_{k}": v for k, v in A.items() if v is not None}))
        summ.append(res["summary"])
        blds.append(res["buildings"])
        cons.append(res["constraints"])
        m = res["hourly"].groupby("month")[["D_total_MW", "Q_HP_to_load_MW", "Q_discharge_MW", "Q_backup_MW", "E_HP_MW",
                                             "E_pump_MW", "Q_DC_used_MW", "Q_unserved_MW"]].sum()
        m.columns = [c.replace("_MW", "_MWh") for c in m.columns]
        m.insert(0, "run_id", spec.run_id)
        monthly.append(m.reset_index())
        if spec.assumption_set == "base" and spec.hp_frac == ref["hp_frac"] and spec.tank_hours == ref["tank_hours"]:
            res["hourly"].to_csv(OUT / "model_a" / "hourly" / f"{spec.run_id}.csv.gz", index=False, float_format="%.5g")

    d = OUT / "model_a"
    pd.DataFrame(runs).to_csv(d / "a_runs.csv", index=False)
    pd.DataFrame(summ).to_csv(d / "a_annual_system.csv", index=False)
    pd.concat([b for b in blds if len(b)]).to_csv(d / "a_annual_building.csv", index=False)
    pd.concat(cons).to_csv(d / "a_constraints.csv", index=False)
    pd.concat(monthly).to_csv(d / "a_monthly.csv", index=False)
    operating_modes(cfg, bundle).to_csv(d / "a_operating_modes.csv", index=False)
    (OUT / "schema_registry.json").write_text(json.dumps(schemas.registry(), indent=2), encoding="utf-8")
    manifest = dict(model="A", runs=len(runs), seconds=round(time.time() - t0, 1),
                    E_el_111_MWh_3yr_mean=bundle["E_el_111"], design_temperature_C=bundle["T_design"],
                    q_dhw_per_apartment_MWh=bundle["q_dhw_apt"], offtakers_after_dedup=len(bundle["offtakers"]),
                    duplicates_dropped=len(bundle["dropped"]), config=str(F.CONFIG.relative_to(F.ROOT)),
                    note="No score is produced by Model A. Composite requires Model B KPIs for all four dimensions.")
    (d / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Model A: {len(runs)} runs in {manifest['seconds']} s -> {d}")

    from .validate_model_a import validate
    validate()


if __name__ == "__main__":
    main()
