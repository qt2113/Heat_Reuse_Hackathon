# Results provenance

Two different models live in this repository. They use different assumptions and give different numbers. This file says which number comes from where, so that a prototype figure is never read as an audited one.

## 1. Which result is which

| Result | Where it is shown | Produced by | Status |
|---|---|---|---|
| **Audited ABC results** (recommended network: in-building reuse + M070 school, −$1.10M/yr, 384 t CO₂/yr) | `outputs/final_integration/abc_results.json`, `outputs/final_integration/abc_results_summary.csv`, the Streamlit ABC Results Viewer (`viewer/abc_viewer.py`), the README | `model/run_model_a.py` → `run_model_b.py` → `run_model_c.py` → `model/export_abc_results.py` | **Our audited result.** Corrections listed in section 3 |
| **Prototype results** (e.g. "Base case" +$1.58M/yr, "Most realistic" +$1.53M/yr) | `streamlit_app/web/data.json` → **the public website** (`docs/index.html`) | `streamlit_app/scripts/export_web.py` (the teammate's Streamlit prototype model) | **Exploratory. Not audited.** Known modelling differences in section 4 |

**The public website shows the prototype results, not the audited ones.** The page carries a "Design preview" label saying so.

## 2. Lineage of the audited ABC results

```
data/raw/*                          subsets of public datasets, exactly as published
  └─ scripts/fetch_site1_data.py    unit conversion, de-duplication → data/processed/*
data/reference/*                    constants and values transcribed from documents (each row cites its source)
  └─ model/features.py              building table, demand shapes, data corrections → outputs/features/offtakers_features.csv
       └─ Model A  model/model_a.py (+ dispatch_kernel.py)   hourly heat physics and allocation        → outputs/model_a/
            └─ Model B model/model_b.py                       costs, carbon, stakeholder value         → outputs/model_b/
                 └─ Model C model/model_c.py                  screening, enumeration, decision rule    → outputs/model_c/
                      └─ model/export_abc_results.py          one frontend file                        → outputs/final_integration/abc_results.json
```

Each model has a validation script (`model/validate_model_a.py`, `validate_model_b.py`, `validate_model_c.py`) that runs at the end of its run script.

## 3. Corrections that distinguish the audited ABC results from the original ABC run

They are switches in `model/config/scenarios.yaml` (`corrections:`) and in `data/reference/assumptions_scenarios.csv`. Evidence trail: `experiments/full_audit/FINAL_AUDIT_REPORT.md`.

- **A17** (extra electricity at the data center) = 0.367 MWh per MWh of heat extracted, from the Con Ed Chelsea pilot (666 MWh / 1,813.5 MWh). Valid at the pilot's capture temperature (about 30 °C). It is 0 only in the 45 °C liquid-cooling scenario.
- LL84 zero-value or isolated-anomaly years are ignored (42 properties).
- The oil share of gas/oil buildings uses the EIA New York heating-oil price and the LL97 oil emission factor.
- Existing NYCHA buildings use the hot-water-only retrofit cost; electric backup boilers of rebuilt towers are costed; the uncosted storage tank is removed from the reference design.
- The automatic recommendation uses hard constraints and the least public support per tonne of CO₂ avoided. The four-dimension weighted score is only an optional visualisation.
- The Con Ed pilot overlap with Fulton (291 apartments) is **not** subtracted by default; it is a labelled scenario.

## 4. Why the prototype and the audited results differ

Checked by code review (`experiments/full_audit/07_TEAMMATE_CODE_REVIEW.md`) and a decomposition (`outputs/redesign/reconciliation.csv`):

- The prototype serves steam-radiator buildings at 65 °C without a temperature-compatibility test.
- It has no extra electricity at the data center (A17 = 0).
- It uses a pipe cost of $3,000/m, while the Con Ed pilot cost is about $29,000 per route-metre; it includes no operating cost and no building-side retrofit cost.
- It counts avoided LL97 fines and cooling-tower water in its net value.
- It routes pipes along OpenStreetMap streets (our model uses a grid-rotated minimum spanning tree) and its hot-water shares by building type are better than ours. These two parts are worth adopting.

## 5. Datasets

| Dataset | Raw / processed file | Processed by | Used by | In the repository |
|---|---|---|---|---|
| NYC LL84 energy benchmarking | `data/raw/s01_ll84_benchmarking_1km.csv`, `data/processed/ll84_buildings_1km_by_year.csv`; prototype: `streamlit_app/data/ll84_near_site.csv` | `scripts/fetch_site1_data.py`; prototype: `streamlit_app/src/fetch.py` | ABC (via `model/features.py`); prototype | yes (1 km subset) |
| NYC MapPLUTO | `data/raw/s02_pluto_lots_1km.csv`, `data/processed/pluto_lots_1km.csv`; prototype: `streamlit_app/data/pluto_near_site.csv` | same | ABC; prototype | yes (1 km subset) |
| Weather | `data/raw/s07_tmyx_central_park_hourly.csv` (TMYx), `data/processed/weather_tmyx_hourly.csv`; prototype: `streamlit_app/data/weather_2023.csv` (2023, Open-Meteo) | `scripts/fetch_site1_data.py`; prototype: `streamlit_app/src/fetch.py` | ABC uses TMYx; prototype uses 2023 | yes |
| OpenStreetMap streets | `streamlit_app/data/streets_drive_1000m.graphml`, `streets_drive_1400m.graphml` | `streamlit_app/src/network.py` | prototype and website map only. ABC does not use them | yes |
| Economic, utility and engineering values | `data/raw/s08*`, `s09`, `s10` (Danish Energy Agency heat technology data), `s11`, `s14`–`s16`; `data/reference/*` (Con Ed pilot filing values, LL97 factors, EIA heating oil, assumptions register) | `scripts/fetch_site1_data.py`; reference files are transcribed | ABC (Model B) | yes |
| Organizer source documents (`sources/`, 223 MB) and download caches (`data/cache/`) | – | – | read while building the register | **no** (git-ignored) |

`data/README.md`, `data/DATA_READINESS.md` and `data/dataset_inventory.csv` document every source.
