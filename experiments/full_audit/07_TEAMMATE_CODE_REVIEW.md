# Teammate's model (`heat-reuse-network.zip`): code review and reconciliation

**Scope.** Static review of all 39 files: `src/` (≈1,600 lines), `config.yaml`, `scripts/` and `tests/` (20 tests).

**Not re-run.** His dependencies (osmnx, shapely) are not installed, and the C: drive has only about 300 MB free. A partial install was removed; nothing was installed system-wide.

All numbers below come from his code plus his own exported results (`web/data.json`, identical to the published artifact).

## 1. What the model is (confirmed from the code)

| Component | Implementation | Location |
|---|---|---|
| Source | Fixed 5 MW of source heat, **one central heat pump** at the data center. COP = 0.40 × T_hot / (T_hot − T_cold), with 30 °C source and 65 °C supply + 10 K → COP 3.09. Delivered = Q_src·COP/(COP − 1) = 7.39 MW | `src/supply.py` L19, L50–51 |
| Electricity | **Compressor + pumping only** (`p_elec = q_del / COP`); **no source-side electricity (A17 = 0)** | `src/supply.py` L51; `src/metrics.py` `network_heat_cost_per_mwh` |
| Distribution | **65 °C hot-water network** on the OSM street graph (edges split to ≤ 40 m), with 20 W/m heat loss | `src/network.py`, `config.yaml` |
| Building side | **$150/kW substation for every building, NYCHA included**; no retrofit, energy centre or source interface | `config.yaml` L145; `src/metrics.py` `building_economics` |
| Demand | LL84 **2023 only** (other years as fallback). Gas 0.80 / steam 0.85 / oil 0.80; **non-heating share by type** (office 15%, hotel 10%); **hot-water share by type** (office 8%, hotel 30%, school 10%). DHW is a fixed daily curve; space heat follows degree-hours | `src/demand.py` L20–41 |
| Temperature compatibility | **None.** Every building's space heat is served from 65 °C water, steam-radiator buildings included | `src/demand.py` L37 |
| Selection | Greedy + local search (prize-collecting Steiner tree), on a cash-margin objective with optional carbon value and priority weight; capacity shared pro rata hour by hour | `src/network.py` `refine_select` |
| Economics | `net = avoided fuel + LL97 + water − electricity − annualised capex` (pipes 30 yr, heat pump 20 yr, connections 25 yr, 6%). **No O&M term**; LL97 penalties and cooling water counted as benefits | `src/metrics.py` L139–146, L173, L181 |
| Source building | `exclude_source_building: true`, so 111 8th Ave internal reuse is *not* modelled | `config.yaml` L15 |
| Con Ed pilot | `exclude_pilot_demand: false` by default (the pilot's demand is claimed); when on, 75% of lot 1007140031 | `config.yaml` L28 |

## 2. Defects found

| # | Defect | Evidence | Effect |
|---|---|---|---|
| 1 | **Web export index bug.** The building table comes from the base preparation (`p0 = preps[()]`, L120–128), but each preset's `connected[i]` comes from *its own* preparation (L61, L89). Presets that change `demand.*` or `con_ed_pilot.*` alter which buildings `screen_outliers` drops, so indices shift | `scripts/export_web.py` | The "Most realistic" map and table show the wrong buildings (e.g. "111 West 19th St, office" carrying 155 W 11th St's 9,365 MWh). The KPIs themselves are correct |
| 2 | **Steam radiators served at 65 °C** (full space heat) | No emitter rule in `demand.py` or `network.py`; the Con Ed pilot keeps steam radiators and serves hot water (and one building's small space-heat load) | The main driver of his value: 72% margins on steam buildings come from space heat that real installations don't deliver |
| 3 | **No source-side electricity** | `supply.py` L51 | The pilot needs 0.367 MWh_e per MWh injected (filing Table 8) |
| 4 | **Missing cost lines**: O&M, building retrofit, energy centre, interface, contingency, soft costs | `metrics.py` L139–181 | See the reconciliation below |
| 5 | **Pipe $3,000/m**, while his own source note says Manhattan is 2–5× higher (multiplier not applied) | `config.yaml` L131 | The Con Ed pilot is $29,318 per route-m |
| 6 | **LL97 penalties and cooling water inside "net"** | `metrics.py` L181 | LL97 is a payment to the City (a transfer). Water assumes evaporative towers (unknown). +$0.39M |
| 7 | **Pilot demand claimed by default** | `config.yaml` L28 | Double claim on 291 Fulton apartments |

## 3. What his model does better (worth adopting)
1. **Street-graph routing** (OSM, ≤ 40 m edges, service pipes) instead of our grid L1 minimum spanning tree.
2. **Hot-water and non-heating shares by property type** (CBECS/RECS).
   - Our A20 rule gives an office a 39% year-round share; his gives 8% × (1 − 15%).
   - This independently confirms our D-flag on 111 8th Ave's internal reuse: with A20 low, internal reuse falls from 198 t to about 60 t CO₂ (Stage 4).
   - His hotel non-heating share (10%) partly addresses our finding on hotel kitchen and laundry gas.
3. **Central-plant screen** (> 300 W/m² excluded), campus allocation, and a quality log with LIVE/CACHED/SAMPLE provenance.
4. **Every assumption has unit, range and source in one config file**, plus 20 unit tests, including an hourly energy-balance assertion.
5. **His key finding agrees with our audit:** network heat costs about $73/MWh against $60 from a gas boiler and $140 from Con Ed steam, so "only steam-heated buildings are worth connecting".

## 4. Reconciliation with our audit (unchanged by reading the code)
The Shapley decomposition in `outputs/redesign/reconciliation.csv` used his parameters exactly as the code applies them:
- pipe $3k/m, connections $150/kW, heat pump $1,200/kW;
- no O&M, no A17;
- prices 14 / 35 / $0.22;
- 6% discount, lives 20/30/25;
- steam efficiency 0.85, η 0.40.

The code confirms each of these. On his buildings, our model moves from −$11.97M to +$0.46M when his eight choices are applied. The largest pieces:
- building-side cost basis: +$5.4M;
- pipe: +$4.0M;
- markups: +$2.3M;
- A17: +$1.1M.

**The remaining $0.74M residual** is now attributable from the code to four things: his central heat pump (one COP for all heat), 2023-only demand, non-heating shares, and his pro-rata coverage of 80%. It can't be decomposed further without running his code.

**Verdict:** well engineered as software (config with sources, tests, provenance, a good optimiser). Its +$1.58M/yr rests on four modelling choices that the evidence does not support:
- 65 °C heat into steam radiators;
- zero source-side electricity;
- European pipe costs;
- no O&M or building-side works.

It also counts two transfer or unverified items as benefits. With those corrected, his own README's conclusion (heat-pump heat costs more than gas heat) matches ours.
