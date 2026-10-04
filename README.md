# Data-center heat reuse: 111 Eighth Avenue, Chelsea (Manhattan)

NYU / Grundfos / HDR heat-reuse hackathon. **Question:** can waste heat from the data center at 111 Eighth Avenue be recovered and delivered as useful heat to surrounding Chelsea buildings, reliably, affordably and with real community value?

### ▶ Live demo: https://qt2113.github.io/Heat_Reuse_Hackathon/

> **Read this before quoting numbers.** The live demo is the *original prototype's* interactive map and scenarios. **It shows the prototype's results (for example +$1.5M/yr), not our audited results.** Our audited result is in [`outputs/final_integration/abc_results.json`](outputs/final_integration/abc_results.json) and in the "Our final findings" section below. See [`RESULTS_PROVENANCE.md`](RESULTS_PROVENANCE.md).

## Our final findings (audited ABC framework)

**No network with an external offtaker pays for itself on current evidence.** The best defensible one needs public support. All figures come from `abc_results.json`.

**Recommended network: 111 8th Ave in-building reuse + the M070 public school.** It is the option with the least public support per tonne of CO₂ avoided among those that pass every hard constraint.

| KPI | Value |
|---|---|
| Waste heat recovered | 3,822 MWh/yr |
| Useful heat delivered | 5,634 MWh/yr |
| Net CO₂ avoided (including the extra electricity) | 384 t/yr |
| Net annual societal value | **−$1.10M/yr** (funding gap about $1.10M/yr, about $2,865 per tonne of CO₂) |
| Beneficiaries | 1 public school (M070), no households |
| COP / LCOH / CAPEX | 3.11 / $328 per MWh / $13.7M |
| Pipeline | 149 m |

Other scenarios in the same file:

- **+ Dream Hotel** (conditional, one year of LL84 data): −$1.12M/yr, 406 t CO₂.
- **In-building reuse only:** −$0.08M/yr, 117 t. It fails the "at least one external offtaker" constraint, so it is never recommended.
- **Rebuilt Fulton (1,335 low-income households), today's cooling** (future scenario): −924 t CO₂, so it fails the CO₂ constraint.
- **Rebuilt Fulton with 45 °C liquid cooling** (speculative technology): +1,427 t CO₂, −$0.68M/yr.
- **Existing Fulton**, with and without the 291 apartments already on the Con Ed pilot (labelled scenarios): −$4.93M and −$3.73M/yr.

Recovered heat, delivered heat, CO₂ avoided and money are four different quantities and are reported separately. Recovered heat is never called "savings".

## Project overview and workflow

1. **Data acquisition.** Public datasets for the 1 km around the site (section "Datasets"), plus values transcribed from the Con Ed Chelsea heat-network pilot filing. `scripts/fetch_site1_data.py`, `scripts/fetch_site1_gapfill.py`.
2. **Preprocessing and demand estimation.** Unit conversion, de-duplication and a coverage audit (`data/DATA_READINESS.md`); hourly building heat demand from annual fuel use and weather.
3. **Initial prototype.** A Streamlit app that estimates demand, dispatches heat hour by hour and chooses buildings with a street-routed network optimiser. It works in `streamlit_app/` and feeds the public map.
4. **ABC modelling and cross-model audit.** Model A (hourly heat physics), Model B (costs, carbon, stakeholder value), Model C (offtaker selection and allocation). `experiments/full_audit/` audits the data, features, physics and costs and compares the prototype with ABC.
5. **Four-dimension evaluation.** Technical, Economic + Delivery, Environmental, Social + Regenerative.
6. **Final recommendation and visualization.** The decision rule below, `abc_results.json`, an ABC Results Viewer (Streamlit), and the public interactive page.

**Decision rule.** Hard constraints first: at least one external offtaker, technical feasibility (cooling independence, backup, temperature compatibility), net CO₂ ≥ 0, and NYCHA households no worse off. Then the least public support per tonne of CO₂ avoided. The four-dimension weighted score is kept only for optional sensitivity and visualisation, because min-max scores favour larger networks.

## Modelling architecture

| | A. Original Streamlit prototype (`streamlit_app/`) | B. Audited ABC framework (`model/`) |
|---|---|---|
| Purpose | Exploratory demand, dispatch, network selection, scenario visualisation | Technical feasibility, full cost accounting, environmental and social assessment |
| Heat delivery | One central heat pump, 65 °C network; steam-radiator buildings treated as served | Temperature compatibility per building (steam radiators get hot water only); heat pumps in buildings |
| Electricity | Compressor and pumps | Plus extra electricity at the data center (A17 = 0.367 per MWh extracted) |
| Costs | Pipes at $3,000/m, connections, heat pump; no O&M or building retrofit | Pilot-based pipe and building costs, O&M, backup boilers; resources only |
| Net value | Includes avoided LL97 fines and cooling water | Excludes transfers (fines, tariffs, subsidies) and the unverified water saving |
| Pipe routing | OpenStreetMap street graph | Grid-rotated minimum spanning tree |

**The two models use different assumptions and give different numbers.** The prototype reports a positive net value for several scenarios; the audited framework finds none for external offtakers. `experiments/full_audit/07_TEAMMATE_CODE_REVIEW.md` explains the differences. Both models agree that network heat costs more than gas-boiler heat and is only attractive against steam.

## Datasets

| Dataset | Processed by | Used by | In the repo |
|---|---|---|---|
| NYC LL84 energy benchmarking (1 km) | `scripts/fetch_site1_data.py`; prototype `streamlit_app/src/fetch.py` | ABC; prototype | yes (subset) |
| NYC MapPLUTO lots (1 km) | same | ABC; prototype | yes (subset) |
| Historical weather (TMYx for ABC, 2023 for the prototype) | same | ABC; prototype | yes |
| OpenStreetMap streets | `streamlit_app/src/network.py` | prototype and website map | yes (`streamlit_app/data/*.graphml`) |
| Economic, utility and engineering assumptions (EIA, Con Ed, NYISO, DEA, LL97 factors, pilot filing) | `scripts/fetch_site1_data.py`; `data/reference/` is transcribed | ABC Model B | yes |

Organizer source documents (`sources/`, 223 MB) and download caches are not in the repository. Full table with file names: [`RESULTS_PROVENANCE.md`](RESULTS_PROVENANCE.md).

## Interactive visualization

The public page (`docs/index.html`) is a map-centred exhibition: scenario picker, an interactive map of candidate buildings with heat-flow pipes, a four-dimension radar, four flip cards (Technical, Economic, Environmental, Social), and proposal, method and impact sections.

**It is powered by the prototype's results, `streamlit_app/web/data.json`, not by `abc_results.json`.** It is labelled "Design preview". It preserves the prototype's map and scenarios and does not show the audited ABC outputs. The audited results are shown by `viewer/abc_viewer.py` (below).

## Repository structure

```
README.md                      this file
RESULTS_PROVENANCE.md          which number comes from which model and file
FINAL_INTEGRATION_REPORT.md    the final ABC integration (corrections, KPIs, viewer)
data/                          raw subsets, processed tables, reference values, data audits
model/                         audited ABC pipeline: model_a/b/c.py, run_*.py, validate_*.py, export_abc_results.py, config/
scripts/                       data download and processing
outputs/                       model outputs; final_integration/abc_results.json is the official result
experiments/full_audit/        end-to-end audit, source registry, review of the prototype
experiments/simplified_model/  independent cross-check model
viewer/                        Streamlit ABC Results Viewer
streamlit_app/                 the original prototype: app.py, src/, tests/, data/, scripts/, web/ (website source)
docs/index.html, docs/.nojekyll  the page published by GitHub Pages
```

## How to reproduce

All commands are run from the repository root unless stated. Status of each is in "Verification" below.

**1. Original Streamlit prototype** (needs `pip install -r streamlit_app/requirements.txt`; Python 3.11+)

```bash
cd streamlit_app
streamlit run app.py
python -m pytest -q          # unit tests (on Windows: set PYTHONUTF8=1 first)
```

**2. Corrected ABC framework**

```bash
python -m model.run_model_a        # hourly physics + its validation tests
python -m model.run_model_b        # economics + validation tests
python -m model.run_model_c        # selection + validation tests (about 4 minutes)
python -m model.export_abc_results # writes outputs/final_integration/abc_results.json
streamlit run viewer/abc_viewer.py # ABC Results Viewer
```

**3. Rebuild the static visualization** (reads `streamlit_app/web/data.json` and `template_abc.html`)

```bash
python streamlit_app/scripts/build_abc_web.py   # writes streamlit_app/web/abc.html
cp streamlit_app/web/abc.html docs/index.html   # the file GitHub Pages serves
```

**4. Open the published website:** https://qt2113.github.io/Heat_Reuse_Hackathon/ (Pages source: branch `main`, folder `/docs`). To preview locally: `python -m http.server 8777 --directory docs`, then open http://localhost:8777/.

## Verification

Executed on 2026-10-04 (Windows, Python 3.12) on the integration branch.

| Check | Result |
|---|---|
| `python -m model.run_model_a` / `run_model_b` / `run_model_c` | Model A: 21 tests, Model B: 13 tests (2 informational), Model C: 19 tests; no failures. Re-running reproduced the committed outputs; only timestamps and run times changed |
| `python -m model.export_abc_results` | writes `abc_results.json` with the figures above; only its timestamp changes between runs |
| `streamlit run viewer/abc_viewer.py` | all 7 scenarios render without errors (headless Streamlit test) |
| Prototype: `python -m pytest -q` in `streamlit_app/` | **29 passed** in a fresh virtual environment with `pip install -r requirements.txt pytest`. On Windows set `PYTHONUTF8=1` first, otherwise 2 tests fail and 9 error on a text-encoding default |
| Prototype: `streamlit run app.py` | starts and renders without errors in the headless test; its base case shows 41.5 GWh/yr delivered and +$1.58M/yr (the prototype's own result) |
| `python streamlit_app/scripts/build_abc_web.py` | rebuilds `abc.html` identical to the published `docs/index.html` (same hash, ignoring line endings) |

Not re-run in this pass: `scripts/fetch_site1_data.py` (data download and processing), the `experiments/full_audit/` scripts (written against the pre-correction models: do not rerun them on the corrected code), and the public-URL tests, which follow the GitHub Pages switch.

## Limitations

- **Reported data:** LL84 energy use (self-reported by owners, some years estimated or anomalous), PLUTO lot attributes, weather, tariffs and prices, and the Con Ed pilot filing values.
- **Modelled estimates:** hourly demand shapes, the hot-water and space-heat split, heat-pump performance, costs by analogy with the pilot (one pilot, not a Manhattan retrofit programme), and A17 (a single pilot measurement valid near 30 °C capture).
- **Speculative scenarios:** the rebuilt Fulton campus (design not final) and warm-water liquid cooling (outside the register's temperature range).
- **Not established:** whether the Con Ed pilot already serves the Fulton apartments (a labelled scenario); Dream Hotel rests on one year of data.
- **The public website shows prototype results** that the audit does not support (section "Modelling architecture").

## Credits

- **Modelling:** the ABC framework (Models A, B, C), data layer, cross-model audit, ABC Results Viewer and results export, by qt2113 with Claude Code.
- **Prototype and original frontend:** the teammate's heat-reuse-network Streamlit app (`streamlit_app/`), including the street-routed network optimiser and the original interactive map and visualization on which the public page is built.
