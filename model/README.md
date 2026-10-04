# Model package: A → B → C pipeline (all three implemented)

```
data/  →  features.py  →  Model A (model_a.py)  →  Model B (model_b.py)  →  Model C (model_c.py)  →  outputs/ → React + D3
          offtakers, demand,   hourly heat physics       cost, carbon,          constraints, all-4-dimension
          supply, shapes       + Technical KPIs           stakeholder value      MCDA, governance panels
```

**Run:** `python -m model.run_model_a`. This runs 155 configurations plus the operating modes in about 15 s, then validates everything.

**Model A never produces a score.** `schemas.assert_composite_ready()` refuses a composite until every dimension has at least one KPI (test V11).

## What Model A does
For each scenario (S0–S3R) × design (heat-pump size × storage) × assumption set (Base, or one Low/High), it simulates 8,760 hours:
- **Source:** 111 8th Ave metered electricity (LL84 3-year mean, 141 GWh) × DC share A01 × 0.95 heat × 0.85 capture. Source-outage hours (A16) are placed in the coldest hours.
- **Demand:** LL84 fuel × efficiency (steam 0.77, A04; gas 0.85). The hot-water share comes from the pilot (8.0 MWh per apartment) or from A20 (non-residential). Space heat is spread by degree-hours.
- **Three temperature classes:**
  - hot water at 60 °C;
  - new space heat at 45 °C (rebuilt towers);
  - existing hydronic heat at A18.
  - Steam-radiator buildings (NYCHA, 111 8th, Dream Hotel) get **hot water only** (rule H7).
- **Heat pumps:** COP = 0.45 × Carnot between condensing and evaporating temperatures (5 K approaches). Calibrated on the Con Ed pilot: DHW COP 2.99 vs 3.01, space heat 4.06 vs 3.79, electricity 865 vs 867 MWh.
- **Dispatch each hour:** source → heat pumps per class → storage → backup (existing steam/boilers; electric boilers in rebuilt towers).

## Outputs (`outputs/`)
| File | For | Contents |
|---|---|---|
| `model_a/a_annual_system.csv` | B, C, frontend | Annual MWh and MW per run, sizing, COPs, T1/T2/T4/T7 |
| `model_a/a_annual_building.csv` | B (bills, carbon, equity) | Per building: demand, heat from network, backup, fuel displaced, baseline fuel, electricity |
| `model_a/a_operating_modes.csv` | C, frontend | Normal year, DC outage 72 h, heat-pump maintenance, network outage 72 h, summer |
| `model_a/a_constraints.csv` | C | H1–H5, H7 pass/fail; H6 pending Model B |
| `model_a/a_monthly.csv`, `model_a/hourly/*.csv.gz` | frontend | Seasonal and hourly series |
| `model_a/a_validation.csv` | judges | 21 tests (pilot calibration, balances, monotonicity, coverage matrix, governance register) |
| `schema_registry.json` | everyone | Columns and consumers of every A, B and C table |

## Covering the whole TEAM DELIVERABLE
- **`config/requirements_coverage.csv`** maps all 40 official requirements to a pipeline stage, output and page. That covers the brief's "Consider" list, the deliverable sentences, the 12 dimension sub-factors and the team rules. Test V13 fails if any requirement has no registered output.
- **`config/delivery_governance.csv`** holds 37 **unscored**, evidence-backed items covering:
  - revenue/connection model, ownership, responsibilities, risk allocation, public acceptance and local-context fit;
  - the value structure for the data center, heat users and community.

  Each item carries an evidence level (NYC precedent / documented elsewhere / proposal / open issue) and a source. Model B joins these items to numbers; Model C shows them as panels next to the score.
- **Cooling independence and backup** are shown by H1/H2 plus the five operating modes. In the 72 h network outage, the towers take 100% of the data-center heat and no building goes without heat.

## Base results (reference design: space-heat heat pumps at 75% of peak, 2 h storage)
| | S1 self-use | S2 commercial | S3 NYCHA today | S3R after rebuild |
|---|---|---|---|---|
| Share of connected buildings' heat from the network | 39% | 81% | 37% (hot water only) | 89% |
| Heat delivered (GWh/yr) | 3.5 | 28.0 | 20.0 | 44.5 |
| Seasonal COP | 3.2 | 3.0 | 3.2 | 3.7 |
| Route length (m) | 0 | 525 | 1,416 | 1,416 |

## Limitations (stated, not hidden)
- **No measured hourly hot-water profile:** demand is flat, so hot-water heat pumps are sized to 100% of it.
- **Hydronic temperature (A18) is assumed** for existing commercial buildings.
- **Rebuilt-tower demand (A03, A19) is assumed.**
- **One heat-pump efficiency (0.45) for all classes,** fitted to the pilot. The Danish catalogue's two-stage machines would do better (V1d).
- **86 duplicate LL84 filings were dropped;** the list is in `outputs/features/offtakers_dropped_duplicates.csv`.

## Model B (implemented, not yet scored)
**Run:** `python -m model.run_model_b`. It covers 225 evaluations: every Model A run, plus one-at-a-time Low/High of A05–A08, A12, A21 and A22. Then it runs 13 validation tests.

**Boundary:** the demand the network can serve in the connected buildings, identical with and without the network.

**Baseline:**
- existing buildings: today's fuel (Con Ed steam at the pilot-implied marginal price of $107.6/MWh, gas at $38.9/MWh);
- rebuilt towers: an all-electric air-source heat pump (Danish Energy Agency cost; seasonal efficiency 2.8).

**System view (resources only):**
- **What's counted:** capital (DEA heat pumps; pilot interfaces, energy centre, pipe and building retrofit costs), O&M, electricity (including the data center's extra electricity, A17) and backup fuel.
- **What's excluded:** heat sales, tariffs and connection charges. These are transfers between actors and appear only in the stakeholder view. Test B1 shows they cancel.

**Markups:** 15% pilot contingency plus A21 soft costs, applied to both sides.

**Outputs:**
- `b_economics.csv`: costs, LCOH, savings, payback, actor positions, carbon, NOx, peak.
- `b_kpis.csv`: all 16 KPIs across the four dimensions. S5 and S6 stay qualitative and are listed in `b_delivery_assessment.csv`.
- `b_stakeholder_value.csv`: data center, heat users, network operator, community; financial vs non-financial.
- `b_building_bills.csv`: per building and per apartment.
- `b_constraints.csv`: H6 affordability, plus F1–F4 (society gains, operator self-financing, data-center participation, payback).
- `b_kpi_comparison.csv`: reference design, with sensitivity ranges.

## Model C: offtaker selection and heat allocation (implemented)
**Run:** `python -m model.run_model_c`. It evaluates 1,536 configurations in about 2 minutes (×2 with the pilot-tariff comparison), then runs 18 tests.

**Steps:**
1. **Screening** (`c_candidates.csv`). Explicit rules: within 1 km, ≥ 2 LL84 years, ≥ 2 GWh/yr, coordinates present. Shortlist = source building + all NYCHA + the best by servable heat per metre (≤ 2 per building type). That gives 10 buildings. Every other record carries a reason.
2. **Planning level.** Every subset of the shortlist is enumerated, in two horizons that cannot coexist:
   - `today`: 10 candidates, 1,024 configurations.
   - `post_rebuild`: the rebuilt Fulton and Elliott-Chelsea replace the existing NYCHA buildings; 9 candidates, 512 configurations.
3. **Operation level.** Model A `policy="merit"` (`dispatch_kernel.py`, numba) allocates the finite data-center heat each hour to building streams, in order of net value per MWh of source heat.
   - It reproduces the validated class-priority totals exactly whenever supply does not bind (test C2).
   - It is worth more when heat is scarce (test C11).
4. **Economics.** Model B, with the **Term 4 tariff rule**: NYCHA pays at most its break-even loop-heat rate, with no connection charge. The shortfall appears as external funding need (E_fund). `c_recommendations_pilot_tariff.csv` shows the result without the cap.
5. **Feasibility.**
   - Technical: H1–H5, H7.
   - Financial: F1 society savings, F2 operator self-financing, F3 data-center value, H6 NYCHA affordability.
   - Class: fully feasible / conditionally feasible / infeasible.
   - With nothing fully feasible, the output says "No fully feasible configuration under the current assumptions" and quantifies the levers (pipe, interface, source electricity, soft costs, carbon price, electricity price).
6. **Indicators.** 13 indicators (3 Technical, 3 Economic, 3 Environmental, 4 Social), min-max normalised over the technically feasible configurations of each horizon. Dimension score = mean; overall = Σ weight × dimension score. Weights must sum to 100%; equal weights are only the demo default.
7. **Outputs.** Weight sensitivity (10% simplex grid), Pareto set, and explanations from leave-one-out and add-one comparisons. Allocation JSON gives monthly figures plus coldest-week, April and July hourly series per building.

**Screening parameters.** These live in `config/scenarios.yaml` under `screening`:

| Parameter | Reference value | Meaning |
|---|---|---|
| `search_radius_m` | 1000 | Search radius; at most 1000, because the feature table stops at 1 km |
| `max_candidates` | 10 | Shortlist size, including the source building and every eligible NYCHA campus |
| `min_annual_heat_demand_gwh` | 2 | Minimum LL84 heating-fuel input |
| `max_candidates_per_building_type` | 2 | Cap per building type; `null` removes it |

A rebuilt campus is a candidate only if its existing NYCHA anchor passes screening.

`python -m model.run_screening_sensitivity` reruns the full chain (screening, enumeration, A, B, feasibility) for 13 combinations of radius, shortlist size and per-type cap.
- It writes to `outputs/model_c/screening_sensitivity/` and never to the reference outputs.
- Tests S1–S3 check that the 1 km / 10 / cap-2 run reproduces the reference results exactly.
- MCDA scores are normalised within each run, so they can't be compared across runs; the KPIs can.

**Why these indicators (changes from the earlier list):**
- **Heat utilisation is dropped:** across configurations it ranks identically to ERF (same numerator, fixed denominators).
- **Route length moves into cost:** it enters through CAPEX and LCOH.
- **Temperature compatibility is absorbed into T_cov:** incompatible heat simply cannot be served.
- **NYCHA bill change (S_aff) is kept, but is non-negative under Term 4.**
- **CAPEX, payback and peak are shown as context only, not scored.**
