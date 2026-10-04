"""Stage 4: targeted physical-assumption tests on fixed networks (data corrections applied; costs as reference)."""
from __future__ import annotations

import pandas as pd

import audit_lib as L

OUT = L.HERE
DATA = {"outlier_years", "pilot_overlap", "oil_fuel"}
NETS = {"internal (111 8th)": (["7536925"], "today"), "+ hotel": (["7536925", "19906892"], "today"),
        "+ M070 school": (["7536925", "1634606"], "today"), "+ Dream Hotel": (["7536925", "4978579"], "today"),
        "+ Rebuilt Fulton": (["7536925", "rebuild:2831044"], "post_rebuild"),
        "phase 2 (hotel + Rebuilt Fulton)": (["7536925", "19906892", "rebuild:2831044"], "post_rebuild")}
TESTS = [("base (register values, data-corrected)", {}, {}),
         ("A17 = 0.367 (pilot, per MWh extracted)", {"A17": L.A17_PILOT_EXTRACTED}, {}), ("A17 = 0", {"A17": 0.0}, {}),
         ("A02 = 27 C", {"A02": 27.0}, {}), ("A02 = 35 C", {"A02": 35.0}, {}),
         ("A10 = 0.40", {"A10": 0.40}, {}), ("A10 = 0.50", {"A10": 0.50}, {}),
         ("A18 = 60 C", {"A18": 60.0}, {}), ("A18 = 80 C", {"A18": 80.0}, {}),
         ("A20 = 0.05 (low base load)", {"A20": 0.05}, {}), ("A20 = 0.30", {"A20": 0.30}, {}),
         ("A03 = 6 MWh/apt", {"A03": 6.0}, {}), ("A03 = 9 MWh/apt", {"A03": 9.0}, {}),
         ("A19 = 0.4", {"A19": 0.4}, {}), ("A19 = 0.6", {"A19": 0.6}, {}),
         ("A01 = 0.5", {"A01": 0.5}, {}), ("A04 = 0.85", {"A04": 0.85}, {}),
         ("no storage (tank 0 h)", {}, {"tank_hours": 0}), ("heat pumps 50 % of space-heat peak", {}, {"hp_frac": 0.5}),
         ("heat pumps 100 % of space-heat peak", {}, {"hp_frac": 1.0}),
         # physically consistent capture / source-electricity combinations
         ("COUPLED pilot-like: condenser capture 30 C with winter compressor operation (A17 0.367)", {"A02": 30.0, "A17": L.A17_PILOT_EXTRACTED}, {}),
         ("COUPLED warm-water liquid cooling 45 C, no chiller lift (A17 0)", {"A02": 45.0, "A17": 0.0}, {}),
         ("INCONSISTENT (previous 'advanced'): 35 C + A17 0 + eta 0.50", {"A02": 35.0, "A17": 0.0, "A10": 0.50}, {})]

ctx = L.base_ctx()
rows, bal = [], []
for tname, A, design in TESTS:
    c = L.ctx_for(ctx, DATA, A=A, design=design)
    for nname, (mem, h) in NETS.items():
        r = L.evaluate(mem, h, c, DATA)
        rows.append(dict(test=tname, network=nname, **{k: r[k] for k in ("heat_recovered_MWh", "heat_delivered_MWh", "net_societal_value", "co2_avoided_t",
                                                                          "energy_cost_per_MWh_delivered", "scop", "backup_MWh")}))
        if tname.startswith("base"):
            res = L.MC.evaluate_config(tuple(mem), h, c)["summary"]
            bal.append(dict(network=nname, Q_DC_used=res.Q_DC_used_MWh, E_HP=res.E_HP_MWh, Q_HP_out=res.Q_HP_out_MWh,
                            hp_balance_residual=res.Q_HP_out_MWh - res.Q_DC_used_MWh - res.E_HP_MWh,
                            Q_network=res.Q_network_MWh, charge=res.Q_charge_MWh, discharge=res.Q_discharge_MWh,
                            delivery_residual=res.Q_HP_out_MWh - res.Q_charge_MWh + res.Q_discharge_MWh - res.Q_network_MWh,
                            demand_residual=res.D_served_classes_MWh - res.Q_network_MWh - res.Q_backup_MWh - res.Q_unserved_MWh,
                            model_a_balance_max=res.balance_max_abs))
d = pd.DataFrame(rows)
base = d[d.test.str.startswith("base")].set_index("network")
d["d_value_vs_base"] = d.net_societal_value - d.network.map(base.net_societal_value)
d["d_co2_vs_base"] = d.co2_avoided_t - d.network.map(base.co2_avoided_t)
d.to_csv(OUT / "physical_tests.csv", index=False)
pd.DataFrame(bal).to_csv(OUT / "energy_balance_checks.csv", index=False)
pd.set_option("display.width", 250)
print(pd.DataFrame(bal).round(3).to_string(index=False))
print(d.pivot(index="test", columns="network", values="net_societal_value").round(0).to_string())
print(d.pivot(index="test", columns="network", values="co2_avoided_t").round(0).to_string())
