# Final integration report

Models A/B/C now carry the audit's confirmed corrections, one frontend JSON is exported, and a Streamlit viewer shows it. Nothing is committed.

## 1. What changed

**Production corrections** (all switchable in `model/config/scenarios.yaml → corrections`; each is traceable to `experiments/full_audit/FINAL_AUDIT_REPORT.md`)

| Correction | Where |
|---|---|
| **A17 = 0.367 MWh_e per MWh extracted** (pilot 666 / 1,813.5 MWh injected). Coupled to capture temperature A02 = 30 °C: extraction ends free cooling, so compressors must run. A17 = 0 only with 45 °C liquid cooling (a scenario) | `data/reference/assumptions_scenarios.csv` |
| LL84 zero or isolated-anomaly years ignored (42 properties; n_years still counts all filings) | `model/features.py` |
| Oil share of gas/oil buildings priced at EIA NY heating oil (`data/reference/eia_ny_heating_oil_residential_weekly.csv`) with the LL97 oil factor; merit-dispatch order uses the same price | `model/model_b.py`, `model/model_c.py` |
| Existing NYCHA: hot-water-only retrofit cost ($39.8k/apt); rebuilt towers: electric backup boilers costed (DEA); storage removed from the reference design (it was never costed) | `model/model_b.py`, `scenarios.yaml` |
| **Recommendation rule replaced**: hard constraints HC0 (≥1 external offtaker), HC1-5 (technical), HC6 (CO₂ ≥ 0), HC7 (NYCHA no worse off), then **least public support per tCO₂ avoided**. The four-dimension weighted score remains only as an optional sensitivity / visualisation score | `model/model_c.py` (`recommend`), `run_model_c.py` |
| **Con Ed pilot demand is not subtracted by default** (`pilot_overlap: false`); it is a labelled scenario | `features.py`, exporter |

Also: validation test C15 (decision rule) added; C11 and B9 adapted to the corrected inputs. Old results remain in git (commit `9b72ec5`).

**Run once, all pass:** Model A (21 tests), Model B (13), Model C (19 incl. C15). The 70,000-run combined sweep was not rerun.

## 2. Final recommended network

**111 8th Ave in-building reuse + M070 public school** (main external candidate). It is the least public support per tCO₂ among 254 configurations that pass the hard constraints.

| KPI | Value |
|---|---|
| Waste heat recovered | 3,822 MWh/yr |
| Useful heat delivered | 5,634 MWh/yr |
| Net CO₂ avoided | 384 t/yr |
| Net annual societal value | **−$1.10M/yr** (needs public support; $2,865 per tCO₂) |
| Beneficiaries | 1 public school; no households |
| COP / LCOH / CAPEX | 3.11 / $328 per MWh / $13.7M |
| Pipeline | 149 m |

Other scenarios in the JSON:
- **+ Dream Hotel** (conditional): −$1.12M/yr, 406 t. Its LL84 history is a single year.
- **In-building reuse only:** −$0.08M/yr, 117 t. It fails HC0, so it is never recommended.
- **Rebuilt Fulton, today's cooling** (future): −924 t CO₂, fails HC6.
- **Rebuilt Fulton, 45 °C liquid cooling** (future, speculative): +1,427 t, −$0.68M/yr, 1,335 low-income households.
- **Existing Fulton** with and without the pilot's 291 apartments: −$4.93M and −$3.73M/yr (labelled scenarios).

## 3. Frontend data

`outputs/final_integration/abc_results.json` (schema `abc_results/1.0`, flat copy `abc_results_summary.csv`), written by `python -m model.export_abc_results`.
- **Primary KPIs per scenario:** waste heat recovered, useful heat delivered, net CO₂ avoided, net annual societal value, community beneficiaries.
- **Secondary KPIs:** COP, LCOH, CAPEX (network / building side), OPEX with breakdown, funding gap, fuel displaced by type, coverage, backup reliability.
- **Detail:** per-building records keyed by LL84 property id (`rebuild:<id>` for modelled rebuilt towers) with coordinates, the pipeline route and monthly series.
- Recovered heat is never called savings and stays positive even when value is negative.
- The older bundle `outputs/final/frontend/` was regenerated from the corrected Model C (FE1-FE5 pass).

## 4. Does our data work with the teammate's Streamlit?

**Partly, by reuse rather than by plugging in.** His `app.py` is built around his optimiser (`prepare` / `evaluate`) and needs `streamlit_folium`, `osmnx`, `shapely`, none of which are installed, and C: has about 300 MB free.
- **Reused unchanged:** hero banner and skyline (`viewer/vendor/teammate_banner.py`, fed through a small KPI adapter), theme and fonts (`viewer/.streamlit/config.toml`), colours and the layout (hero, KPI cards, full-width map, Money / Hour-by-hour / Buildings / Assumptions tabs).
- **New:** `viewer/abc_viewer.py` reads only the JSON. It does not call his optimiser and does not modify his branch.
- **Buildings** are matched by property id, never by array position (his old export bug).
- **Tested** headlessly with Streamlit's AppTest: all 7 scenarios render with no exception, and the server answers on `/_stcore/health`.
- **Components missing fields:** his sliders and Steiner-tree selection (no model re-run), street-graph routing (the pipeline is our grid-rotated tree, drawn schematically), hourly series (monthly instead), and LL97/water lines (not in the resource value).

**Launch:**
```
cd C:\Users\TQY\Downloads\Heat_Reuse_Hackathon
streamlit run viewer/abc_viewer.py
```
Needs internet for the map tiles only.

## 5. Unresolved assumptions

- **Con Ed pilot overlap:** operational overlap with Fulton is not established, so it is a scenario, not the default.
- **A17 = 0.367** is a single pilot measurement and holds only at ~30 °C capture. The data center's own plant is unknown.
- **Dream Hotel** rests on one year of data. M070 is oil-heated, so its value depends on the EIA oil price.
- **Costs:** the $29k per route-metre pilot pipe cost applies to a Manhattan retrofit. Repeat-project costs (−$0.70M) are in the audit, not the reference.
- **Stale or isolated outputs:** `outputs/final/` (proposal, combined sweep, challenge coverage) and `outputs/redesign/` were generated before these corrections. `experiments/full_audit/` scripts apply the same corrections as switches, so do not rerun them against the corrected production code (they would double-apply).
- **Dispatch ordering** uses displaced-fuel value only. It does not include source-side electricity cost.
- `experiments/cross_model_reconciliation/` (another session's folder) is untracked and untouched.
