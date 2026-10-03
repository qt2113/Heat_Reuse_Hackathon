"""Model A - hourly physics-based heat simulation (first module of the A -> B -> C pipeline).

For one scenario x design x assumption set it simulates 8,760 hours:
    data-center heat (111 8th Ave, metered LL84 electricity x A01) -> ambient loop
    -> building heat pumps per temperature class (DHW 60 C, new space heat 45 C, existing hydronic A18)
    -> storage per class -> backup (existing steam/boilers, or electric boilers in rebuilt towers).

Model A produces *physical quantities* and the four Technical indicators (T1, T2, T4, T7) plus the
technical feasibility checks (H1-H5, H7). It does not score anything: Model B turns these quantities
into the Economic, Environmental and Social indicators, and Model C combines all four dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import features as F

K = 273.15
CLASSES = ("dhw", "sh45", "sh_exist")   # dispatch priority order


def cop_carnot(t_supply_C: float, t_loop_supply_C: float, phys: dict, eta: float) -> float:
    """Heat-pump COP = eta x Carnot COP between condensing and evaporating temperatures.
    Calibrated on the Con Ed pilot (validate_model_a.py)."""
    t_cond = t_supply_C + phys["approach_cond_K"] + K
    t_evap = t_loop_supply_C - phys["loop_dT_K"] - phys["approach_evap_K"] + K
    return eta * t_cond / (t_cond - t_evap)


@dataclass
class RunSpec:
    run_id: str
    scenario: str
    hp_frac: float
    tank_hours: float
    assumption_set: str = "base"      # base | <Axx>_low | <Axx>_high
    varied: str = ""
    level: str = "base"


def simulate(spec: RunSpec, cfg: dict, bundle: dict, A: dict, stress: dict | None = None) -> dict:
    """Run one configuration. `bundle` holds data loaded once (weather, offtakers, ...).
    `stress` (operating-mode tests) may hold hourly arrays: source_off (1 = data-center heat unavailable),
    hp_scale (0-1 heat-pump capacity factor), offtake_off (1 = network cannot deliver heat)."""
    phys, scen = cfg["physics"], cfg["scenarios"][spec.scenario]
    weather = bundle["weather"]
    shape_sh, shape_dhw = bundle["shape_sh"], bundle["shape_dhw"]
    T_out = weather.dry_bulb_C.to_numpy(float)
    H = F.HOURS

    # ---------------- supply (A01, A16, E01, E02)
    E_el = bundle["E_el_111"]
    P_DC = E_el / H * A["A01"]                                  # MW, flat load (LF = 1)
    Q_raw = np.full(H, P_DC * phys["f_heat"])
    avail = np.ones(H)
    n_out = int(round((1 - A["A16"]) * H))
    if n_out:
        avail[np.argsort(T_out)[:n_out]] = 0.0                   # conservative: outages in the coldest hours
    stress = stress or {}
    if "source_off" in stress:
        avail = avail * (1 - stress["source_off"])
    hp_scale = stress.get("hp_scale", np.ones(H))
    offtake_off = stress.get("offtake_off", np.zeros(H))
    Q_avail = Q_raw * phys["f_capture"] * avail
    E_IT = P_DC / phys["pue"] * H

    # ---------------- demand (connected buildings)
    blds = F.building_demands(bundle["offtakers"], scen["members"], A, weather, bundle["q_dhw_apt"], scen.get("rebuild"))
    T_design = bundle["T_design"]
    sh_design_factor = (18.0 - T_design) / weather.HDH_18C.sum()   # design-hour share of annual space heat
    rows, Dc = [], {c: np.zeros(H) for c in CLASSES}
    for b in blds:
        dhw = b.D_useful * b.f_base
        sh = b.D_useful - dhw
        if b.rebuilt:
            cls_sh, sh_served = "sh45", sh
        elif b.sh_system == "hydronic_assumed":
            cls_sh, sh_served = "sh_exist", sh
        else:                                                   # steam radiators: not served (H7)
            cls_sh, sh_served = None, 0.0
        Dc["dhw"] += dhw * shape_dhw
        if cls_sh:
            Dc[cls_sh] += sh_served * shape_sh
        rows.append(dict(property_id=b.pid, name=b.name, main_fuel=b.fuel, sh_system=b.sh_system, rebuilt=b.rebuilt,
                         backup_type=("electric_boiler" if b.backup == "electric_boiler" else b.fuel),
                         eta_base=b.eta_base, units=b.units, dist_m=b.dist_m, is_nycha=b.is_nycha,
                         D_useful_MWh=b.D_useful, f_base=b.f_base, D_dhw_MWh=dhw,
                         D_sh_served_MWh=sh_served, D_sh_not_served_MWh=sh - sh_served, sh_class=cls_sh or "none"))
    cols = ["property_id", "name", "main_fuel", "sh_system", "rebuilt", "backup_type", "eta_base", "units", "dist_m", "is_nycha",
            "D_useful_MWh", "f_base", "D_dhw_MWh", "D_sh_served_MWh", "D_sh_not_served_MWh", "sh_class"]
    bdf = pd.DataFrame(rows, columns=cols)

    # ---------------- temperatures, COP, sizing
    t_loop = A["A02"] - phys["approach_hx_K"]
    supply_T = {"dhw": phys["dhw_supply_C"], "sh45": phys["sh_new_supply_C"], "sh_exist": A["A18"]}
    COP = {c: cop_carnot(supply_T[c], t_loop, phys, A["A10"]) for c in CLASSES}
    peak = {"dhw": float(Dc["dhw"].max()),
            "sh45": float(bdf.loc[bdf.sh_class == "sh45", "D_sh_served_MWh"].sum() * sh_design_factor),
            "sh_exist": float(bdf.loc[bdf.sh_class == "sh_exist", "D_sh_served_MWh"].sum() * sh_design_factor)}
    peak = {c: max(peak[c], float(Dc[c].max())) for c in CLASSES}
    # DHW demand is flat (no measured draw profile), so DHW heat pumps are sized to 100% of it;
    # the design grid (hp_frac) applies to the space-heat classes, whose peaks storage can shave.
    hp_cap = {c: (phys.get("dhw_hp_frac", 1.0) if c == "dhw" else spec.hp_frac) * peak[c] for c in CLASSES}
    tank = {c: spec.tank_hours * peak[c] for c in CLASSES}
    backup_cap = {c: peak[c] for c in CLASSES}                  # existing plant / new boilers sized to design peak (H2)
    hx_cap = sum(hp_cap[c] * (1 - 1 / COP[c]) for c in CLASSES)

    # ---------------- hourly dispatch
    out = {f"{k}_{c}": np.zeros(H) for c in CLASSES for k in ("load", "ch", "dis", "soc", "backup", "unserved", "E", "src")}
    soc = {c: 0.0 for c in CLASSES}
    for h in range(H):
        src_left = 0.0 if offtake_off[h] else min(Q_avail[h], hx_cap)
        for c in CLASSES:
            d = Dc[c][h]
            cop = COP[c]
            cap_h = hp_cap[c] * hp_scale[h]
            qmax = min(cap_h, src_left * cop / (cop - 1)) if cap_h > 0 else 0.0
            load = min(d, qmax)
            ch = min(qmax - load, tank[c] - soc[c]) if tank[c] > 0 else 0.0
            q_out = load + ch
            src = q_out * (1 - 1 / cop)
            src_left -= src
            need = d - load
            dis = min(need, soc[c])
            soc[c] += ch - dis
            bk = need - dis
            uns = max(0.0, bk - backup_cap[c])
            bk -= uns
            o = out
            o[f"load_{c}"][h], o[f"ch_{c}"][h], o[f"dis_{c}"][h], o[f"soc_{c}"][h] = load, ch, dis, soc[c]
            o[f"backup_{c}"][h], o[f"unserved_{c}"][h], o[f"E_{c}"][h], o[f"src_{c}"][h] = bk, uns, q_out / cop, src

    D_tot = sum(Dc[c] for c in CLASSES)
    Q_net = sum(out[f"load_{c}"] + out[f"dis_{c}"] for c in CLASSES)
    Q_bk = sum(out[f"backup_{c}"] for c in CLASSES)
    Q_uns = sum(out[f"unserved_{c}"] for c in CLASSES)
    Q_out = sum(out[f"load_{c}"] + out[f"ch_{c}"] for c in CLASSES)
    E_HP = sum(out[f"E_{c}"] for c in CLASSES)
    Q_used = sum(out[f"src_{c}"] for c in CLASSES)
    E_pump = A["A11"] * Q_net
    E_src = A["A17"] * Q_used
    Q_rej = Q_raw - Q_used

    # ---------------- energy balances (H5)
    bal = {
        "hp": float(np.max(np.abs(Q_out - (Q_used + E_HP)))),
        "demand": float(np.max(np.abs((Q_net + Q_bk + Q_uns) - D_tot))),
        "storage": float(max(abs((out[f"ch_{c}"].sum() - out[f"dis_{c}"].sum()) - out[f"soc_{c}"][-1]) for c in CLASSES)),
        "source": float(np.max(np.abs(Q_raw - (Q_used + Q_rej)))),
    }

    # ---------------- allocate class results to buildings (all buildings in a class share its hourly shape)
    def share(col_D, cls_mask):
        tot = bdf.loc[cls_mask, col_D].sum()
        return np.where(cls_mask, bdf[col_D] / tot, 0.0) if tot > 0 else np.zeros(len(bdf))
    bdf["Q_network_MWh"] = 0.0
    bdf["Q_backup_MWh"] = 0.0
    bdf["Q_unserved_MWh"] = 0.0
    bdf["E_HP_MWh"] = 0.0
    for c in CLASSES:
        if c == "dhw":
            sh_ = share("D_dhw_MWh", bdf.D_dhw_MWh > 0)
        else:
            sh_ = share("D_sh_served_MWh", bdf.sh_class == c)
        bdf["Q_network_MWh"] += sh_ * float((out[f"load_{c}"] + out[f"dis_{c}"]).sum())
        bdf["Q_backup_MWh"] += sh_ * float(out[f"backup_{c}"].sum())
        bdf["Q_unserved_MWh"] += sh_ * float(out[f"unserved_{c}"].sum())
        bdf["E_HP_MWh"] += sh_ * float(out[f"E_{c}"].sum())
    bdf["E_pump_MWh"] = A["A11"] * bdf.Q_network_MWh
    # fuel use with the network: backup heat / backup efficiency; heat not served stays on today's system
    bdf["backup_fuel_MWh"] = np.where(bdf.backup_type == "electric_boiler", bdf.Q_backup_MWh / 0.99,
                                      bdf.Q_backup_MWh / bdf.eta_base)
    bdf["remaining_fuel_MWh"] = np.where(bdf.rebuilt, 0.0, bdf.D_sh_not_served_MWh / bdf.eta_base)
    bdf["baseline_fuel_MWh"] = np.where(bdf.rebuilt, np.nan, bdf.D_useful_MWh / bdf.eta_base)   # rebuilt: no 'today' (B uses ASHP counterfactual)
    bdf["fuel_displaced_MWh"] = np.where(bdf.rebuilt, 0.0, bdf.Q_network_MWh / bdf.eta_base)
    bdf["share_heat_from_network"] = bdf.Q_network_MWh / bdf.D_useful_MWh

    # ---------------- technical indicators (not scored here) and annual summary
    served = D_tot.sum()
    hp_out_total = Q_out.sum()
    route = F.route_length_m(cfg["site"], blds, phys["grid_rotation_deg"]) if blds else 0.0
    if spec.scenario == "S1":
        route = 0.0                                              # in-building
    peak_hour = int(np.argmax(E_HP + E_pump)) if served > 0 else -1
    summ = dict(
        run_id=spec.run_id, scenario=spec.scenario, hp_frac=spec.hp_frac, tank_hours=spec.tank_hours,
        assumption_set=spec.assumption_set, varied=spec.varied, level=spec.level,
        n_buildings=len(bdf), apartments_connected=float(bdf.units.sum()) if len(bdf) else 0.0,
        nycha_apartments_connected=float(bdf.loc[bdf.is_nycha, "units"].sum()) if len(bdf) else 0.0,
        E_el_111_MWh=E_el, P_DC_avg_MW=P_DC, E_IT_MWh=E_IT, Q_DC_raw_MWh=float(Q_raw.sum()),
        Q_DC_avail_MWh=float(Q_avail.sum()), outage_hours=n_out,
        D_useful_connected_MWh=float(bdf.D_useful_MWh.sum()) if len(bdf) else 0.0,
        D_served_classes_MWh=float(served), D_dhw_MWh=float(Dc["dhw"].sum()), D_sh45_MWh=float(Dc["sh45"].sum()),
        D_sh_exist_MWh=float(Dc["sh_exist"].sum()),
        D_sh_not_served_MWh=float(bdf.D_sh_not_served_MWh.sum()) if len(bdf) else 0.0,
        D_peak_design_MW=float(sum(peak.values())),
        Q_network_MWh=float(Q_net.sum()), Q_backup_MWh=float(Q_bk.sum()), Q_unserved_MWh=float(Q_uns.sum()),
        Q_HP_out_MWh=float(hp_out_total), Q_charge_MWh=float(sum(out[f"ch_{c}"].sum() for c in CLASSES)),
        Q_discharge_MWh=float(sum(out[f"dis_{c}"].sum() for c in CLASSES)),
        Q_DC_used_MWh=float(Q_used.sum()), Q_rejected_MWh=float(Q_rej.sum()),
        E_HP_MWh=float(E_HP.sum()), E_pump_MWh=float(E_pump.sum()), E_src_MWh=float(E_src.sum()),
        E_network_MWh=float(E_HP.sum() + E_pump.sum()),
        P_peak_network_MW=float((E_HP + E_pump).max()) if served > 0 else 0.0,
        P_peak_hour=peak_hour, P_at_design_hour_MW=float((E_HP + E_pump)[int(np.argmin(T_out))]),
        backup_hours=int(((Q_bk) > 1e-9).sum()),
        backup_fuel_steam_MWh=float(bdf.loc[bdf.backup_type == "steam", "backup_fuel_MWh"].sum()) if len(bdf) else 0.0,
        backup_fuel_gas_MWh=float(bdf.loc[bdf.backup_type == "gas_or_oil", "backup_fuel_MWh"].sum()) if len(bdf) else 0.0,
        backup_elec_MWh=float(bdf.loc[bdf.backup_type == "electric_boiler", "backup_fuel_MWh"].sum()) if len(bdf) else 0.0,
        fuel_displaced_steam_MWh=float(bdf.loc[bdf.main_fuel == "steam", "fuel_displaced_MWh"].sum()) if len(bdf) else 0.0,
        fuel_displaced_gas_MWh=float(bdf.loc[bdf.main_fuel == "gas_or_oil", "fuel_displaced_MWh"].sum()) if len(bdf) else 0.0,
        HP_cap_MW=float(sum(hp_cap.values())), HX_cap_MW=float(hx_cap), tank_MWh=float(sum(tank.values())),
        backup_cap_MW=float(sum(backup_cap.values())),
        COP_dhw=COP["dhw"], COP_sh45=COP["sh45"], COP_sh_exist=COP["sh_exist"], T_loop_C=t_loop,
        route_m=route, balance_max_abs=max(bal.values()),
        # Technical indicators (data_dictionary IDs) - inputs to Model C, NOT a score
        T1_recoverable_heat_GWh=float(Q_avail.sum() / 1000),
        T2_SCOP=float(hp_out_total / E_HP.sum()) if E_HP.sum() > 0 else np.nan,
        T4_coverage_pct=float(100 * Q_net.sum() / served) if served > 0 else np.nan,
        T4b_share_of_building_heat_pct=float(100 * Q_net.sum() / bdf.D_useful_MWh.sum()) if len(bdf) else np.nan,
        T7_route_m=route,
    )

    # ---------------- technical feasibility checks (H6 needs Model B)
    cons = [
        ("H1", "DC cooling independent of the network", bool((Q_rej >= -1e-9).all()),
         float(Q_rej.min()), ">= 0 every hour; towers retained by design", "Network never takes more than the DC produces; existing towers reject the rest"),
        ("H2", "Backup covers the design peak; no unserved heat", bool(Q_uns.sum() < 1e-6),
         float(Q_uns.sum()), "= 0 MWh", f"Includes {n_out} source-outage hours placed in the coldest hours"),
        ("H3", "Heat used <= heat available", bool((Q_used <= np.minimum(Q_avail, hx_cap) + 1e-9).all()),
         float((Q_used - np.minimum(Q_avail, hx_cap)).max()) if served > 0 else 0.0, "<= 0", "Hourly source limit and interface capacity"),
        ("H4", "Hot water >= 60 C", phys["dhw_supply_C"] >= 60, phys["dhw_supply_C"], ">= 60 C", "DHW class supply temperature"),
        ("H5", "Energy balance closes", max(bal.values()) < 1e-6, max(bal.values()), "< 1e-6", str({k: f"{v:.1e}" for k, v in bal.items()})),
        ("H6", "NYCHA heat cost not above today", None, np.nan, "bill change >= 0", "pending_model_B"),
        ("H7", "No low-temperature heat into steam radiators", bool((bdf.loc[bdf.sh_system == "steam_radiators", "D_sh_served_MWh"] == 0).all()) if len(bdf) else True,
         float(bdf.loc[bdf.sh_system == "steam_radiators", "D_sh_served_MWh"].sum()) if len(bdf) else 0.0, "= 0 MWh", "Steam-radiator buildings receive hot water only"),
    ]
    cdf = pd.DataFrame([dict(run_id=spec.run_id, constraint_id=c[0], description=c[1],
                             status=("pending_model_B" if c[2] is None else ("pass" if c[2] else "fail")),
                             metric=c[3], threshold=c[4], detail=c[5]) for c in cons])

    hourly = pd.DataFrame({
        "hour_of_year": np.arange(1, H + 1), "month": weather.month.to_numpy(), "T_out_C": T_out,
        "D_dhw_MW": Dc["dhw"], "D_sh45_MW": Dc["sh45"], "D_sh_exist_MW": Dc["sh_exist"], "D_total_MW": D_tot,
        "Q_HP_to_load_MW": sum(out[f"load_{c}"] for c in CLASSES), "Q_charge_MW": sum(out[f"ch_{c}"] for c in CLASSES),
        "Q_discharge_MW": sum(out[f"dis_{c}"] for c in CLASSES), "SOC_MWh": sum(out[f"soc_{c}"] for c in CLASSES),
        "Q_backup_MW": Q_bk, "Q_unserved_MW": Q_uns, "E_HP_MW": E_HP, "E_pump_MW": E_pump, "E_src_MW": E_src,
        "Q_DC_avail_MW": Q_avail, "Q_DC_used_MW": Q_used, "Q_rejected_MW": Q_rej,
    })
    bdf.insert(0, "run_id", spec.run_id)
    return dict(summary=summ, buildings=bdf, constraints=cdf, hourly=hourly)
