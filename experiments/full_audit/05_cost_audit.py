"""Stage 5: cost audit - registry of every CAPEX/OPEX line, accepted corrections vs labelled alternatives, reconciled ledger."""
from __future__ import annotations

import csv

import numpy as np
import pandas as pd

import audit_lib as L

OUT = L.HERE
MB = L.MB

# ---------------------------------------------------------------- 1. cost registry (every line Models A/B use or omit)
REG = [
 # id, item, model_location, value_basis, original_source_scope, applicable, duplicated_elsewhere, scaling, fixed_or_variable, life_annualisation, verdict
 ["K01", "Distribution pipe (route)", "model_b.py L153 pipe_capex = route_m x A05 x markup", "$29,318 per route-m (11.17 M$ / 381 m)",
  "S13 UDS: 2 x 10in pre-insulated steel, leak detection, excavation/backfill/street restoration under W 16th St, isolation valves (pp.48-51)",
  "yes - same street type and utility; diameter similar for 1-5 MW", "no (pumps/HX are separate lines)", "route length (MST, L1 street grid)", "variable",
  "25 yr (NY DPS LCCA convention used by the pilot, footnote 23)", "VALID reference; 0.6x repeat-project and 40-yr life are labelled alternatives"],
 ["K02", "Excavation / civil works", "inside K01", "-", "included in S13 UDS line", "yes", "would duplicate K01 if added", "-", "-", "-", "VALID (not separately added - correct)"],
 ["K03", "Energy centre", "model_b.py L152 ec_capex = 2.69 M$ x markup if route > 0", "fixed $2.69M",
  "S13: decentralised pump room - 3 x 125 HP UDS pumps (2,400 gpm), air separator, expansion tank, valves, controls, new electric service ($97k) (p.51)",
  "yes for any street loop; oversized for a ~1 MW spur", "no (HX in K04, building equipment in K05)", "fixed per network", "fixed", "25 yr",
  "VALID reference; size-scaled energy centre is a labelled alternative"],
 ["K04", "Source heat-exchanger interface", "model_b.py L151 hx_capex = HX_cap_MW x $1.75M/MW x markup", "2.56 M$ / 1.465 MW",
  "S13: 3 x 6,000 MBH plate HX (2 F approach), 10in piping from chilled-water plant, 2 x 1,200 gpm condenser pumps, metering/valves/controls (pp.46-47)",
  "yes (same type of interface on a commercial cooling plant)", "no", "linear in interface MW (pilot: largely fixed scope)", "mostly fixed in reality", "25 yr",
  "VALID reference; economies-of-scale exponent 0.7 is a labelled alternative"],
 ["K05", "Building heat pumps (commercial / rebuilt)", "model_b.py L117 HP_cap x DEA capex x markup", "DEA waste-heat HP 3 MW, EUR2020 -> USD2025",
  "DEA: installed large heat pump incl. installation (Danish district heating)", "transferred (no NYC labour factor; building-scale units cost more per MW)",
  "possible partial overlap of DEA 'installed' cost with A21 soft costs", "HP capacity", "variable", "25 yr (DEA lifetime)", "VALID with caveat; markup on DEA tested as alternative"],
 ["K06", "Existing-NYCHA building retrofit", "model_b.py L117 units x $63.8k x markup", "18.57 M$ / 291 apts",
  "S13 customer-side: water-source HPs, fan coils, DHW systems, HX, electrical + plumbing upgrades; DHW for 3 buildings + space heating & cooling for 401 W 16th (p.89-90)",
  "partly: our H7 scope is hot water only", "no (no separate HP added for NYCHA)", "apartments", "variable", "25 yr",
  "MISAPPLIED SCOPE -> correct to DHW-only (18.57 - ~7) M$ / 291 = $39.8k/apt (p.90: removing one building's HVAC saved ~$7M)"],
 ["K07", "Rebuilt-tower building retrofit", "model_b.py L117 (rebuilt rows) HP_cap x DEA capex (owner)", "-", "new construction: no retrofit", "yes - correctly NO $/apt retrofit applied",
  "baseline ASHP capex credited (avoided)", "HP capacity", "variable", "25 yr", "VALID (rebuilt Fulton does not carry existing-building retrofit cost)"],
 ["K08", "Electrical upgrades in commercial buildings", "not modelled", "-", "S13 includes them inside customer-side cost", "required for building HPs",
  "-", "HP capacity", "variable", "-", "OMITTED (understates commercial connections; no NYC source to quantify) - flag"],
 ["K09", "Backup heating equipment", "existing plant: none (kept); rebuilt: not costed", "-", "existing boilers/steam remain in both cases; rebuilt towers need electric boilers",
  "yes", "-", "peak MW", "variable", "-", "OMITTED for rebuilt towers -> correct (DEA electric boiler capex + fixed O&M)"],
 ["K10", "Thermal storage tanks", "Model A sizes 2 h of peak; model_b.py has NO storage capex", "-", "-", "storage changes heat < 0.3 % (Model S V5; Stage 4: <= $5k)",
  "-", "MWh", "variable", "-", "UNCOSTED COMPONENT -> correct by removing storage (tank 0 h)"],
 ["K11", "Engineering / design (soft costs)", "model_b.py L99 markup = 1 + 0.15 + A21 (0.29)", "design 10.08 / construction 34.99",
  "S13 design incl. Stage 1-2 first-of-kind design (100% design of an innovative pilot)", "transferred; first-of-kind", "applied ONCE per capex line (verified)",
  "% of capex", "-", "-", "VALID reference (once); 0.15 repeat-project is a labelled alternative"],
 ["K12", "Contingency 15 %", "same markup", "standard Con Ed procedure (p.89)", "pilot line items EXCLUDE contingency (p.88)", "yes", "applied ONCE (verified)", "%", "-", "-", "VALID"],
 ["K13", "Pilot admin, outreach, SCADA/data, 5-yr EM&V operations", "excluded", "16.26 + 0.78 + 3.64 + 18.37 M$", "pilot / research / regulatory", "no", "-", "-", "-", "-",
  "CORRECTLY EXCLUDED (non-recurring pilot expenses)"],
 ["K14", "Pilot cost escalation", "pilot $ used as USD2025", "3 %/yr inflation + 10 % material tariff to Stage-3 construction", "nominal construction-year dollars", "tariff yes; inflation ~1 yr",
  "-", "-", "-", "-", "MINOR overstatement (~3 %); not corrected (immaterial, timing uncertain)"],
 ["K15", "Annualisation", "model_b.py crf(r=5 %, 25 yr) on all capex", "-", "pilot uses a 25-yr lifetime per NY DPS LCCA guidance", "yes", "-", "-", "-", "25 yr", "VALID (40-yr pipes = alternative)"],
 ["O01", "Heat-pump + pumping electricity", "model_b.py L161 (E_HP + E_pump) x A07", "$222/MWh", "EIA NY commercial 12-mo", "consistent with Con Ed weighted all-in ~$210", "-", "MWh", "variable", "-", "VALID"],
 ["O02", "Source-side electricity (A17)", "model_b.py L161 E_src x A07", "0.25 x heat extracted", "S13 Table 8: 666 MWh / 2,680 MWh DELIVERED", "basis mismatch", "-", "MWh extracted", "variable", "-",
  "CORRECT basis -> 0.367 per MWh extracted (physics, Stage 4)"],
 ["O03", "Backup fuel", "model_b.py L121", "fuel price by main fuel", "-", "yes", "-", "MWh", "variable", "-", "VALID, but oil priced as gas (data correction Q5)"],
 ["O04", "Heat-pump O&M", "DEA fixed + variable", "-", "DEA", "transferred", "-", "MW / MWh", "variable", "-", "VALID"],
 ["O05", "Network O&M", "A22 = 1 % of network capex", "team assumption", "-", "plausible", "-", "% capex", "-", "-", "VALID (uncertain)"],
 ["O06", "Avoided baseline heating cost", "model_b.py L109-114", "served heat / efficiency x price (steam 107.6, gas 38.85)", "-", "yes; oil mispriced", "no double counting with backup (served scope)", "-", "-", "-", "VALID after oil fix"],
 ["O07", "Existing boiler O&M / replacement", "not credited", "-", "boilers retained as backup in project and baseline", "yes", "-", "-", "-", "-", "VALID (cancels)"],
 ["O08", "DC cooling-energy savings", "not credited (A17 >= 0)", "-", "pilot shows the opposite (+666 MWh)", "-", "-", "-", "-", "-", "VALID (no evidence of savings)"],
 ["T01", "Fence price, tariffs, connection charges", "stakeholder view only", "S13 pilot rates", "-", "transfers", "cancel in the sum (test C5)", "-", "-", "-", "VALID (excluded from societal value)"],
 ["T02", "LL97 penalty avoided", "not in societal value", "$268/t", "penalty paid to the City", "transfer", "-", "-", "-", "-", "VALID (owner benefit only)"],
]
cols = ["cost_id", "item", "model_location", "value_basis", "original_scope", "applicable", "duplication_check", "scales_with", "fixed_or_variable", "life_annualisation", "verdict"]
with open(OUT / "cost_registry.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for r in REG:
        w.writerow(r)

# ---------------------------------------------------------------- 2. corrections vs alternatives on fixed networks
DATA = {"outlier_years", "pilot_overlap", "oil_fuel"}
NETS = {"internal (111 8th)": (["7536925"], "today"), "+ Dream Hotel": (["7536925", "4978579"], "today"),
        "+ M070 school": (["7536925", "1634606"], "today"), "+ hotel": (["7536925", "19906892"], "today"),
        "+ existing Fulton (DHW)": (["7536925", "2831044"], "today"), "+ Rebuilt Fulton": (["7536925", "rebuild:2831044"], "post_rebuild"),
        "phase 2 (hotel + Rebuilt Fulton)": (["7536925", "19906892", "rebuild:2831044"], "post_rebuild")}
ctx = L.base_ctx()
I0 = ctx["I"]
CASES = [
    ("data-corrected reference", "reference", DATA, {}, {}, {}),
    ("+ K06 NYCHA DHW-only retrofit cost", "accepted correction", DATA | {"nycha_dhw_cost"}, {}, {}, {}),
    ("+ K09 rebuilt-tower backup boilers", "accepted correction", DATA | {"nycha_dhw_cost", "backup_boiler"}, {}, {}, {}),
    ("+ K10 remove uncosted storage", "accepted correction", DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage"}, {}, {}, {}),
    ("+ O02 A17 per MWh extracted (0.367) = CORRECTED", "accepted correction", DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage", "A17_basis"}, {}, {}, {}),
    ("alt J1: pipe 0.6 x pilot (repeat project)", "labelled alternative", DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage", "A17_basis"}, {"A05": 17590.0}, {}, {}),
    ("alt J2: soft costs 15 %", "labelled alternative", DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage", "A17_basis"}, {"A21": 0.15}, {}, {}),
    ("alt J3: 40-yr network life", "labelled alternative", DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage", "A17_basis"}, {"network_life": 40}, {}, {}),
    ("alt J4: interface scale exponent 0.7", "labelled alternative", DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage", "A17_basis"}, {"hx_scale_exp": 0.7}, {}, {}),
    ("alt J5: no soft costs on DEA heat pumps (DEA 'installed')", "labelled alternative", DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage", "A17_basis"}, {}, {"hp_capex": I0["hp_capex"] / 1.44 * 1.15}, {}),
    ("alt J1-J4 combined (repeat-project urban case)", "labelled alternative", DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage", "A17_basis"},
     {"A05": 17590.0, "A21": 0.15, "network_life": 40, "hx_scale_exp": 0.7}, {}, {}),
]
rows = []
for name, kind, fl, P, I, A in CASES:
    c = L.ctx_for(ctx, fl, A=A, P=P, I=I)
    for nn, (mem, h) in NETS.items():
        r = L.evaluate(mem, h, c, fl)
        rows.append(dict(case=name, kind=kind, network=nn, **{k: r[k] for k in ("capex_total", "capex_annualised", "om", "electricity_hp_pump", "electricity_source_A17",
                                                                               "backup_fuel", "baseline_cost", "net_societal_value", "co2_avoided_t", "funding_gap_at_tariff")}))
d = pd.DataFrame(rows)
ref = d[d.case == "data-corrected reference"].set_index("network")
d["d_value_vs_reference"] = d.net_societal_value - d.network.map(ref.net_societal_value)
d.to_csv(OUT / "cost_corrections.csv", index=False)
pd.set_option("display.width", 260)
print(d.pivot(index="case", columns="network", values="net_societal_value").reindex([x[0] for x in CASES]).round(0).to_string())

# ---------------------------------------------------------------- 3. reconciled ledger (corrected evidence case) with stakeholder split
fl = DATA | {"nycha_dhw_cost", "backup_boiler", "no_storage", "A17_basis"}
c = L.ctx_for(ctx, fl)
led = []
for nn, (mem, h) in NETS.items():
    r = L.evaluate(mem, h, c, fl)
    raw = L.MC.evaluate_config(tuple(mem), h, c)
    e = raw["econ"]
    lines = [("A  avoided baseline heating cost", r["baseline_cost"]), ("B  heat-pump + pumping electricity", -r["electricity_hp_pump"]),
             ("C  additional data-center electricity (A17)", -r["electricity_source_A17"]), ("D  backup fuel", -r["backup_fuel"]),
             ("E  maintenance (heat pumps + network)", -r["om"]), ("F  annualised CAPEX (25 yr, 5 %)", -r["capex_annualised"])]
    total = sum(v for _, v in lines)
    for ln, v in lines:
        led.append(dict(network=nn, line=ln, usd_per_year=v))
    led.append(dict(network=nn, line="= NET ANNUAL SOCIETAL VALUE", usd_per_year=total))
    led.append(dict(network=nn, line="check: ledger - audit evaluate()", usd_per_year=total - r["net_societal_value"]))
    # stakeholder view (transfers at pilot prices). Each audit correction is attributed once, to the party that bears it:
    #   oil pricing -> building owners; NYCHA DHW-only retrofit saving -> operator (funds NYCHA retrofits); rebuilt-tower boilers -> owner
    xa = L.electric_boiler_cost(raw, c)[1] if "backup_boiler" in fl else 0.0
    oil_adj = (r["baseline_cost"] - e["baseline_cost_annual"]) - (r["backup_fuel"] - e["backup_fuel_cost"])
    nycha_k = (e["capex_annualised"] - r["capex_annualised"]) + xa
    internal = tuple(mem) == (L.SITE,)
    dc = e["dc_net"]
    users = e["users_net"] + oil_adj - xa + (nycha_k if internal else 0.0)
    op = e["operator_net"] + (0.0 if internal else nycha_k)
    for ln, v in (("stakeholder: data center (fence revenue - extra electricity)", dc), ("stakeholder: heat users / building owners (incl. NYCHA)", users),
                  ("stakeholder: network operator (tariffs - fence - network capex/O&M)", op),
                  ("stakeholder sum (must equal societal value; transfers cancel)", dc + users + op),
                  ("transfer: fence payments to data center", e["fence_revenue"]), ("transfer: tariffs + connection charges", e["tariff_revenue"] + e["connection_revenue"]),
                  ("memo: funding gap at pilot tariffs (operator deficit)", r["funding_gap_at_tariff"]), ("memo: minimum support if all parties held harmless", r["minimum_support"]),
                  ("memo: LL97 penalty avoidance (transfer, not societal)", e["ll97_upper_bound_commercial"]),
                  ("memo: CO2 avoided t/yr (LL97 2024-29 factors; baseline existing fuel, ASHP for rebuilt)", r["co2_avoided_t"])):
        led.append(dict(network=nn, line=ln, usd_per_year=v))
L_ = pd.DataFrame(led)
L_.to_csv(OUT / "reconciled_cashflow.csv", index=False)
print(L_.pivot(index="line", columns="network", values="usd_per_year").round(0).to_string())
