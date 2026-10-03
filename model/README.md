# Model package: A → B → C pipeline (Model A implemented)

```
data/  →  features.py  →  Model A (model_a.py)  →  Model B (planned)  →  Model C (planned)  →  outputs/ → React + D3
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
- **`config/requirements_coverage.csv`** maps all 39 official requirements to a pipeline stage, output and page. That covers the brief's "Consider" list, the deliverable sentences, the 12 dimension sub-factors and the team rules. Test V13 fails if any requirement has no registered output.
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
