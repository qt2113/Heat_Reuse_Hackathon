"""Validation tests for Model S. Called by run_experiment.py; also runnable alone: python validate.py"""
from __future__ import annotations

import numpy as np
import pandas as pd

import smodel as S

SITE = "7536925"


def _t(rows, tid, name, ok, detail=""):
    rows.append(dict(test=tid, name=name, passed=bool(ok), detail=detail))


def hourly_reference(members: list[str], P: dict) -> dict:
    """Independent hourly loop (no storage) of the same dispatch rules, to prove the bin model is exact."""
    D = S.data()
    w = D["weather"]
    T = w.dry_bulb_C.to_numpy(float)
    hdh = w.HDH_18C.to_numpy(float)
    avail = np.ones(S.HOURS)
    n_out = int(round((1 - P["availability"]) * S.HOURS))
    avail[np.argsort(T)[:n_out]] = 0.0
    sim = S.simulate(members, P)                      # reuse stream definitions (caps, COPs, merit order)
    loss = sim["loss_frac"]
    Q_av = sim["P_DC"] * P["f_heat"] * P["f_capture"]
    src_left = avail * min(Q_av, sim["hx_cap"])
    Q = E = 0.0
    for s in sorted(sim["streams"], key=lambda s: -s["merit"]):
        ann = (s["load"] * sim["bins"].hours.to_numpy()).sum()
        load = np.full(S.HOURS, ann / S.HOURS) if s["cls"] == "dhw" else ann * hdh / hdh.sum()
        need = (1 - 1 / s["cop"]) * (1 + loss)
        q = np.minimum(load, np.minimum(s["cap"], src_left / need))
        src_left = src_left - q * need
        Q += q.sum()
        E += (q / s["cop"]).sum()
    return dict(Q_del=Q, E_HP=E)


def run_all(P: dict, configs: dict, comp: pd.DataFrame | None = None) -> pd.DataFrame:
    rows: list = []
    big = list(S.data()["offt"].query("sh_system == 'hydronic_assumed' and dist_m <= 1000 and heat_fuel_MWh > 2000 and lat == lat").property_id)
    stress = [SITE] + big                                              # supply-binding stress network
    evals = {k: S.evaluate(m, P) for k, m in configs.items() if m}
    evals["stress (all large hydronic buildings, DC share 0.5)"] = S.evaluate(stress, S.params(levels={"A01": "low"}))

    # V1 energy balance in every bin, every configuration
    worst = max(r["sim"]["balance_err"] for r in evals.values())
    dem = max(abs(r["sim"]["D_served"] - r["sim"]["Q_del"] - r["sim"]["Q_backup"]) for r in evals.values())
    _t(rows, "V1", "Energy balance closes (HP: out = source + electricity; demand = delivered + backup)", worst < 1e-9 and dem < 1e-6,
       f"max bin HP imbalance {worst:.1e} MW; max demand imbalance {dem:.1e} MWh")

    # V2 finite supply / cooling independence, including a case where supply binds
    st = evals["stress (all large hydronic buildings, DC share 0.5)"]["sim"]
    binding = st["Q_src"] / st["Q_avail"]
    ok = all(r["con"]["HC1_cooling_independent"] for r in evals.values())
    _t(rows, "V2", "Extracted heat never exceeds available DC heat (stress case binds)", ok and binding > 0.3,
       f"stress network uses {100 * binding:.0f}% of available DC heat over the year; {len(stress)} buildings")

    # V3 bin model == hourly dispatch without storage (independent hourly loop)
    errs = []
    for k in ("C1 Internal reuse", "C4 Large network (ABC equal-weights, today)", "R3 Internal + full rebuild campus (2029+)"):
        if k in configs:
            h = hourly_reference(configs[k], P)
            errs.append(abs(evals[k]["sim"]["Q_del"] / h["Q_del"] - 1))
    h = hourly_reference(stress, S.params(levels={"A01": "low"}))
    errs.append(abs(st["Q_del"] / h["Q_del"] - 1))
    _t(rows, "V3", "Temperature-bin model reproduces an hourly loop (no storage), incl. supply-binding case", max(errs) < 0.005,
       f"max |error| in heat delivered {100 * max(errs):.3f}%")

    # V4 controlled reproduction of Models A/B (hourly, merit dispatch)
    if comp is not None and len(comp):
        piv = comp.pivot_table(index="case", columns="model", values=["heat_delivered_MWh", "net_value"])
        a0 = piv["heat_delivered_MWh"]["Model A hourly + B, no storage (rerun)"]
        s0 = piv["heat_delivered_MWh"]["Model S, ABC-equivalent settings"]
        n0 = piv["net_value"]["Model A hourly + B, no storage (rerun)"]
        ns = piv["net_value"]["Model S, ABC-equivalent settings"]
        a2 = piv["heat_delivered_MWh"]["Model A hourly + B, tank 2 h (rerun)"]
        e_heat = float((s0 / a0 - 1).abs().max())
        e_net = float(((ns - n0) / n0.abs()).abs().max())
        e_store = float((s0 / a2 - 1).abs().max())
        _t(rows, "V4", "Model S (ABC settings) = Model A+B without storage", e_heat < 0.001 and e_net < 0.001,
           f"max heat error {100 * e_heat:.3f}%, max net-value error {100 * e_net:.3f}%")
        _t(rows, "V5", "Dropping the 2 h storage tank changes heat delivered by < 1%", e_store < 0.01,
           f"max difference vs Model A with tank: {100 * e_store:.2f}%")
        st_ = piv["heat_delivered_MWh"]["ABC stored (Model C output)"]
        a2r = piv["heat_delivered_MWh"]["Model A hourly + B, tank 2 h (rerun)"]
        _t(rows, "V6", "Rerun of Model A/B reproduces the stored Model C outputs (read-only rerun is faithful)",
           float((a2r / st_ - 1).abs().max()) < 1e-6, f"max diff {float((a2r / st_ - 1).abs().max()):.1e}")

    # V7 pilot calibration: DHW COP at pilot loop temperature
    D = S.data()
    pilot_loop = (5 / 9) * ((54 + 97) / 2 - 32)
    c = S.cop(60.0, dict(P, loop_temp_C=pilot_loop + P["hx_approach_K"]))
    pilot_cop = 7960 / 3.412142 / (D["pilot_hp_elec_MWh"] - 91.721)
    _t(rows, "V7", "Heat-pump COP reproduces the Con Ed pilot DHW COP", abs(c / pilot_cop - 1) < 0.03,
       f"model {c:.2f} vs pilot {pilot_cop:.2f}")

    # V8 stakeholder transfers cancel
    gap = max(abs(r["stake"]["transfer_check"]) for r in evals.values())
    _t(rows, "V8", "Stakeholder transfers cancel (DC + users + operator = system net value)", gap < 1e-3, f"max gap ${gap:.2e}")

    # V9 monotonicity
    m = configs.get("C3 Small network (2-4 offtakers)", [SITE, "19906892"])
    f = lambda **kw: S.evaluate(m, S.params(kw))["econ"]
    p_lo, p_hi = f(pipe_cost_per_route_m=15000), f(pipe_cost_per_route_m=40000)
    a_lo, a_hi = f(source_elec_per_MWh_src=0.0), f(source_elec_per_MWh_src=0.4)
    t_lo, t_hi = f(loop_temp_C=27), f(loop_temp_C=35)
    ok = p_lo["net_value"] > p_hi["net_value"] and a_lo["net_value"] > a_hi["net_value"] and a_lo["co2_avoided"] > a_hi["co2_avoided"] \
        and t_hi["net_value"] > t_lo["net_value"]
    _t(rows, "V9", "Monotonic: net value falls with pipe cost and A17, rises with source temperature; CO2 falls with A17", ok)

    # V10 temperature compatibility: steam-radiator buildings receive hot water only
    ok = all(r["con"]["HC5_temperature_compatible"] for r in evals.values())
    _t(rows, "V10", "No low-temperature space heat into steam-radiator buildings", ok)

    # V11 backup covers 100% of design peak, incl. DC outage hours
    ok = all(r["sim"]["unserved"] < 1e-6 for r in evals.values())
    _t(rows, "V11", "No unserved heat in any configuration (backup = 100% of served design peak)", ok)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    P = S.params()
    print(run_all(P, {"C1 Internal reuse": [SITE], "C3 Small network (2-4 offtakers)": [SITE, "19906892", "4040951"]}).to_string(index=False))
