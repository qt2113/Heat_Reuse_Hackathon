# Project Modeling Overview: Site 1, 111 8th Avenue

> **Status (2026-10-03).**
> - **Data layer:** 49 validated CSVs from 19 sources (`data/DATA_READINESS.md`).
> - **Not built yet:** no modeling or frontend code exists. The repository has `scripts/fetch_site1_data.py`, `scripts/fetch_site1_gapfill.py` (data only) and `variable_network.html`, a 160-variable dependency graph.
> - **Purpose:** this document fixes how data becomes indicators, how the indicators are computed and compared, and how results reach the frontend.
> - **Superseded figures:** files 01–06 still say "~80 MW" and "0.5%/km pipe loss". Use this file and `data/` instead: the building averages **14.9–16.9 MW** (LL84), and insulated pipe loses **0.5–1.5%/km** (CBS).

```
Raw data (data/raw, 13 CSV)  →  Processed features (data/processed, 19 CSV)  +  References & assumptions (data/reference, 11 CSV)
        →  Derived features (feature engineering)  →  Model A (hourly physics)  →  Model B (cost, carbon, value)
        →  KPIs per scenario  →  Model C (constraints + MCDA)  →  JSON/CSV outputs  →  React + TypeScript + D3 frontend
```

---

## 1. Existing dataset overview (every processed CSV, plus the reference tables the models read)

### 1.1 Building and heat demand
| CSV | What it contains | Key columns | What we can calculate | Dimension |
|---|---|---|---|---|
| `processed/offtaker_candidates_ll84.csv` (895 rows) | One row per LL84-benchmarked property within 1 km: 3-year means 2022–24 | `key_role`, `dist_m`, `largest_property_use_type`, `units_res`, `gfa_ft2`, `steam_MWh_mean`, `gas_MWh_mean`, `oil_MWh_mean`, `heat_fuel_MWh_mean/min/max`, `heat_fuel_kWh_per_ft2`, `any_estimated` | Annual heat demand per offtaker (fuel × efficiency), heat density, year-to-year range, distance. **Offtaker screening input** | Technical, Social |
| `processed/ll84_buildings_1km_by_year.csv` (1,520) | Same properties year by year, raw LL84 fields plus MWh conversions | `report_year`, `electricity_MWh`, `steam_MWh`, `gas_MWh`, `heat_fuel_MWh`, `total_location_based_ghg`, `estimated_data_flag`, `is_child_of_listed_parent` | Interannual variability (Low/High demand), data-quality flags | Technical |
| `processed/nycha_chelsea_developments.csv` (4) | NYCHA Data Book: Fulton, Elliott, Chelsea, Chelsea Addition | `apartments`, `population`, `share_fixed_income_households`, `avg_monthly_gross_rent_usd`, `stories`, `completion_date` | Households and residents served; bill change per apartment; equity weighting | Social |

### 1.2 Data center and heat supply
| CSV | What it contains | Key columns | What we can calculate | Dimension |
|---|---|---|---|---|
| `processed/source_111_8th_annual.csv` (3) | LL84 for 111 8th Ave, 2022–24 | `electricity_MWh` (130.8–148.1 GWh), `electricity_avg_MW` (14.9–16.9), `dc_gfa_share` (0.22–0.26), `steam_MWh`, `gas_MWh` | Recoverable heat ceiling (× A01 DC share); the building's own heat demand (scenario S1); ERF denominator | Technical, Environmental |
| `processed/chelsea_uten_benchmarks.csv` (16) | Values derived from Con Ed's Chelsea pilot filing | `metric`, `value`, `unit`, `formula`. Key values: `steam_to_useful_heat_efficiency` 0.77, `implied_steam_cost_per_MWh_useful_heat` 139.9, `UDS_cost_per_route_m` 29,318, `customer_building_cost_per_apartment` 63,814, `heat_purchase_price_per_MWh` 88.7, `system_heat_per_electricity_added` 1.77 | Local cost and performance anchors; checks for Model A/B results | Technical, Economic |

### 1.3 Weather and geography
| CSV | What it contains | Key columns | What we can calculate | Dimension |
|---|---|---|---|---|
| `processed/weather_tmyx_hourly.csv` (8,760) | Typical year, Central Park, 2011–2025 observations | `hour_of_year`, `month`, `hour`, `dry_bulb_C`, `HDH_18C` | Hourly space-heat shape; ASHP COP(T); seasonality | Technical |
| `processed/weather_design_conditions.csv` (8) | ASHRAE 2025 design values in the EPW header | `heating_design_DB_99.6pct_C` = −10.5, `annual_HDD_18C` = 2,383 | Design peak load; backup sizing | Technical |
| `processed/pluto_lots_1km.csv` (3,450) | Tax lots within 1 km | `bbl`, `latitude`, `longitude`, `dist_m`, `bldgarea`, `unitsres`, `landuse`, `yearbuilt`, `tract_geoid` | Map geometry, distance, tract join, candidates not in LL84 | Technical, Social |
| `processed/grid_zoneJ_hourly_2025.csv` (8,759) | NYISO NYC zone load, hourly | `ts`, `zoneJ_load_MW` | Whether added heat-pump load coincides with the grid peak | Environmental |
| `processed/grid_zoneJ_summary_2025.csv` (3) | Zone J peaks | annual peak 10,825 MW; winter peak 7,552 MW | Context for peak impact | Environmental |

### 1.4 Engineering and equipment
| CSV | What it contains | Key columns | What we can calculate | Dimension |
|---|---|---|---|---|
| `processed/equipment_dea_heat.csv` (104) | Danish Energy Agency datasheets 2025/2030: heat pumps (waste heat 1/3/10 MW, air 3/10 MW), electric and gas boilers | `ws`, `year`, `parameter` (`capex_MEUR_per_MWth`, `cop_or_efficiency_annual`, `fixed_om_EUR_per_MWth_yr`, `var_om_EUR_per_MWhth`, `lifetime_yr`, `forced_outage_share`, `min_load_share`), `ctrl/lower/upper` | Heat-pump and backup CAPEX/OPEX, COP calibration, availability, lifetime | Technical, Economic |
| `processed/equipment_eia_building_scale.csv` (13) | EIA 2023 US equipment (boiler, chiller, water-loop heat pump, heat-pump water heater) | `technology`, `parameter`, `value`, `value_converted` (USD/kW_th), `verified_in_pdf_text` | US building-side costs; boiler efficiency 0.85 for gas baselines | Economic |

### 1.5 Energy prices and economics
| CSV | What it contains | Key columns | What we can calculate | Dimension |
|---|---|---|---|---|
| `processed/energy_prices_ny_monthly.csv` (139) | EIA NY electricity and gas prices, monthly | `res_price_USD_MWh`, `com_price_USD_MWh`, `gas_res_USD_MWh_fuel`, `gas_com_USD_MWh_fuel` | Baseline gas cost; price history for sensitivity | Economic |
| `processed/energy_prices_ny_summary.csv` (4) | 12-month means | electricity commercial 222; gas commercial 38.9 / residential 73.3 USD/MWh fuel | Base prices | Economic |
| `processed/utility_avg_prices_2024.csv` (8) | EIA-861: Con Ed and NYPA by sector | `utility`, `service_type`, `sector`, `avg_USD_per_MWh` | Electricity price scenario A07 (182 / 222 / 282) | Economic |
| `processed/steam_tariff_summary.csv` (5) | Con Ed SC 2 Rate II blocks; fuel adjustment; 1.194 MMBtu/Mlb | `parameter`, `value`, `unit` | Cross-check of the steam baseline | Economic |
| `processed/macro_cpi_fx.csv` (27) | CPI-U and EUR/USD | `cpi_factor_to_latest_full_year`, `usd_per_eur` | DEA EUR(2020) → USD(2025): × 1.141 × 1.244 | Economic |

### 1.6 Environmental
| CSV | What it contains | Key columns | What we can calculate | Dimension |
|---|---|---|---|---|
| `processed/air_quality_latest.csv` (44) | NYCCAS PM2.5, NO2 and boiler-emission density | `name`, `measure`, `geo_place_name`, `data_value` | Local exposure context (PM2.5 9.5 vs 6.3 µg/m³ citywide; boiler NOx 124 vs 21 t/km²) | Environmental, Social |
| `reference/ll97_emission_coefficients.csv` | LL97 factors 2024–29 + $268/t | `fuel`, `tCO2e_per_MWh` (elec 0.289, gas 0.181, steam 0.153) | Baseline and project emissions | Environmental |
| `reference/ap42_natural_gas_boilers.csv` | AP-42 combustion factors | `pollutant`, `control`, `kg_per_MWh_fuel` | NOx/PM from displaced on-site gas | Environmental |

### 1.7 Social and community
| CSV | What it contains | Key columns | What we can calculate | Dimension |
|---|---|---|---|---|
| `processed/dac_tracts_1km.csv` (18) | NYS Disadvantaged Communities indicators | `dac_designation`, `percentile_rank_combined`, `lmi_80_ami`, `lmi_poverty_federal`, `home_energy_affordability`, `role` | Equity flag and weight per offtaker tract | Social |
| `processed/hvi_zcta.csv` (4) | NYC Heat Vulnerability Index by ZIP | `zcta20`, `hvi` | Context only (low discriminating power) | Social |
| `reference/fec_rebuild_facts.csv` | Rebuild: 2,056 + up to 3,454 units; first move-ins end of 2028; electric heating | `metric`, `value`, `verified` | Phasing of S3; design-window timing | Social |

### 1.8 Reference tables the models read (not observations)
| CSV | Role |
|---|---|
| `reference/assumptions_scenarios.csv` | **The single source of Low/Base/High inputs**, A01–A16 |
| `reference/engineering_parameters.csv` | E01–E30 literature ranges: temperatures, losses, ERF benchmarks |
| `reference/chelsea_uten_pilot_stage2.csv` | 80 verified pilot values: loads, costs, prices, risk-sharing |
| `reference/discount_rates_nist135.csv`, `reference/unit_constants.csv` | FEMP 3.0% real discount rate; steam 1,194 kBtu/Mlb; cold-climate ASHP COP ≥ 1.75 |
| `reference/reference_cases.csv` | Precedents (qualitative and benchmark) |

**Known data issues to handle in feature engineering:**
- Duplicate LL84 records still exist (for example "Copy of Orsid", "61 9th Ave" vs "61 9th Avenue", URA Group ×2). De-duplicate by BBL and keep the record with the most years.
- LL84 is annual only.
- The DC load is assumed flat because there is no hourly IT data.

**Missing variables:**
- DC share of electricity (A01)
- Tenant loop temperature (A02)
- Rebuilt-unit demand (A03)
- Tower type (A14)
- Post-2030 grid factor (A09 low)
- Measured hourly load shapes

---

## 2. Factor → indicator → computation

### 2.1 Feature layers (dependency chain)
| Layer | Examples (column or symbol) | Produced by |
|---|---|---|
| **Input features** | `heat_fuel_MWh_mean`, `steam_MWh_mean`, `gas_MWh_mean`, `dist_m`, `units_res`, `electricity_MWh` (111 8th), `dry_bulb_C`, `HDH_18C`, `capex_MEUR_per_MWth`, `tCO2e_per_MWh`, `avg_USD_per_MWh`, `dac_designation` | CSVs as they are |
| **Derived features** | D_b,useful = steam × 0.77 (A04) or gas × 0.85 (EIA boiler); f_DHW,b; hourly demand D_b,h; Q_src = E_el,111 × A01 × E01 / 8,760; COP_h; unit costs in USD 2025 | Feature-engineering step (Python) |
| **Model inputs** | Scenario definition (which buildings), design variables (heat-pump MW, storage hours A13), assumption set (Low/Base/High) | `scenarios.yaml` (to be written) |
| **Simulation outputs** | Hourly Q_HP, Q_store, Q_backup, E_HP, E_aux, unmet heat, peak electric kW, energy balance | Model A |
| **KPIs** | §2.2 | Models B and C |

**How the key derived features are built:**
- **DHW share** of the useful demand: (pilot DHW per apartment × units) / useful demand.
  - Pilot DHW per apartment = 7,960 MMBtu / 291 apts = 8.0 MWh/apt (`chelsea_uten_pilot_stage2.csv`).
  - Fulton: 944 × 8.0 / (29,396 × 0.77) ≈ **0.33**.
  - Non-residential buildings use DEA/CBS seasonal ratios (E17).
- **Hourly demand:** D_b,h = D_b × [ f_DHW / 8,760 + (1 − f_DHW) × HDH_h / ΣHDH ]. This is a labelled method (GAP-04), not a measured shape.

### 2.2 Retained KPIs (16 shortlisted in `data_dictionary.csv`, plus the constraints)
| Dim. | KPI | Data / variables | Formula | Unit | Type | Assumptions |
|---|---|---|---|---|---|---|
| **Tech** | T1 Recoverable heat | `source_111_8th_annual.electricity_MWh` | Q_rec = E_el × A01 × E01 (≤ E02 = 0.85 cap) | GWh/yr, MWth | Derived | A01 |
| Tech | T2 Seasonal COP | `dry_bulb_C`, A02 loop temperature, sink 45/60 °C, DEA COP | COP_h = η_L × T_lm,sink / (T_lm,sink − T_lm,src); SCOP = ΣQ / Σ(Q/COP) | – | Simulation | A02, A10 |
| Tech | T4 Hourly demand coverage | D_b,h, Q_src, storage | Σ_h min(supply_h, D_h) / Σ_h D_h | % | Simulation | A01, A03, A13 |
| Tech | T7 Network distance | `dist_m` | route ≈ 1.3 × straight-line distance (grid) | m | Input | – |
| **Econ** | C1 CAPEX | DEA capex × FX × CPI; `UDS_cost_per_route_m` × route; `customer_building_cost_per_apartment` | Σ capacity × unit cost | M$, $/kWth | Derived | A05 |
| Econ | C2 LCOH | C1, O&M, E_HP × p_el, heat purchase | (C1 × CRF + O&M + E_el × p_el + Q × p_fence) / Q_delivered; CRF = r(1+r)ⁿ / ((1+r)ⁿ − 1) | $/MWh | Simulation + derived | A06, A07, A08 |
| Econ | C3 Saving vs current heat cost | baseline: steam 139.9 $/MWh useful; gas = `gas_*_USD_MWh_fuel` / 0.85 | 1 − LCOH / baseline cost (per offtaker) | % | Derived | A07 |
| **Env** | N1 Energy Reuse Factor | Q_delivered, E_IT | ERF = Q_reused / (E_el × A01 / PUE) | % | Derived | A01 |
| Env | N2 Net GHG avoided | baseline fuel × LL97 factor; project E_el × 0.289 + backup fuel | ΔCO2 = Σ fuel_displaced × EF_f − (E_HP + E_aux + E_src) × EF_el | tCO2e/yr | Derived | A09, A11 |
| Env | N4 On-site combustion displaced | gas displaced; AP-42 | MWh gas displaced; NOx = MWh × 0.152 kg/MWh (uncontrolled) | MWh/yr, kg NOx | Derived | – |
| Env | N6 Winter peak electricity vs all-electric ASHP | design-hour demand; COP_ASHP(−10.5 °C) | ΔP = P_peak,heat × (1/COP_ASHP − 1/COP_loop) | MW | Simulation | A12 |
| **Social** | S1 Low-income households served | `apartments`, `share_fixed_income_households`, `dac_designation` | Σ apartments connected in DAC tracts | households | Input | – |
| Social | S3 Environmental-justice exposure of the served block | `percentile_rank_combined`, PM2.5 ratio | DAC flag × percentile; PM ratio = 9.5 / 6.3 | index | Input | – |
| Social | S7 Net value to the data center | Q_sold × A06 − ΔE_src × p_el − ΔO&M + own heat displaced | V_DC | $/yr | Derived | A06, A07 |
| Social | S5 Acceptance and governance | pilot governance, reference cases | 0–4 rubric (documented evidence) | score | Qualitative | – |
| Social | S6 Rebuild design-window fit | `fec_rebuild_facts` | 0–2 rubric (heat-ready at first move-in, end 2028) | score | Qualitative | A15 |

**Value split, as the brief requires:**
- **Data center:** S7.
- **Heat users:** C3 expressed per apartment ($/apt/yr).
- **Community:** N2 + N4 + S1.

**Redundancy flags (do not score twice):**
| Dropped indicator | Why |
|---|---|
| T3 (1/SCOP) | Reciprocal of T2 |
| T5 (supply/demand ratio) | Upper bound of T4 |
| C4, C5 (bill saving, payback) | Transforms of C2/C3 |
| N3 (heat carbon intensity) | Shares N2's numerator |
| S2 (bill per apartment) | Same quantity as C3; display it, don't score it |
| S4 (HVI) | Doesn't discriminate between options |
| N5 (water) | Blocked: tower type unknown (A14) |

Also never use LL84 `total_location_based_ghg` as a heat-carbon proxy. It correlates 0.91 with electricity, not heat.

### 2.3 Hard feasibility constraints (pass/fail, never weighted)
| ID | Constraint | Check |
|---|---|---|
| H1 | DC cooling never depends on the network (existing towers and bypass retained) | Design rule; the pilot kept a 4,800-ton tower backup |
| H2 | Backup ≥ design peak of every connected building at −10.5 °C | P_backup ≥ P_peak (T6) |
| H3 | Heat delivered ≤ recoverable heat, every hour | Σ_h, ∀h |
| H4 | DHW supply ≥ 60 °C (Legionella) | Heat-pump sink temperature |
| H5 | Hourly energy balance closes | \|in − out − Δstorage\| < 1e-6 |
| H6 | NYCHA heating cost not higher than baseline (Term 4) | C3 per NYCHA apartment ≥ 0 at Base. The pilot is at +$1k/yr, so this is a binding constraint |
| H7 | Existing steam radiators are not served directly by a 45 °C loop | DHW-only for existing NYCHA unless a retrofit is costed (pilot: one building retrofitted) |

---

## 3. Modeling methods

### 3.0 Two separate evaluations
| | **Offtaker Suitability (screening)** | **Overall System Performance** |
|---|---|---|
| Question | Which buildings should be connected first? | Which configuration is best overall? |
| Unit | Each building (895 candidates) | Each scenario S0–S3 |
| Inputs | `heat_fuel_MWh_mean`, `dist_m`, `largest_property_use_type`, steam vs gas, `units_res`, DAC flag, rebuild timing | KPIs from Models A and B |
| Method | Pre-filter (≥ 2 GWh/yr fuel, ≤ 1 km, LL84 years ≥ 2), then a transparent weighted sum of min-max normalized criteria over the candidate pool | Constraints, then baseline-referenced MCDA (§3.3) |
| Output | `offtaker_scores.csv` → which buildings go into S2/S3 | `kpis.csv`, `scores.csv` |

Screening criteria:
- Demand (MWh/yr)
- Demand density (kWh/ft²) and distance (m)
- Temperature compatibility: DHW share, building type
- Baseline carbon: steam vs gas
- Equity: NYCHA or DAC
- Timing: rebuild window

### 3.1 Model A: physics-based hourly heat simulation (Python, NumPy/pandas, 8,760 steps)
**Inputs:**
- Q_src (A01, `source_111_8th_annual`), D_b,h (derived), `dry_bulb_C`
- A02 loop temperature, sink temperatures (45 °C space heat for new buildings / 60 °C DHW)
- A10 Lorenz efficiency, A11 auxiliary share, A13 storage hours, A16 availability
- Backup type (existing steam or boilers)

**Algorithm (each hour h, rule-based merit-order dispatch, no optimization needed):**
1. Building heat pumps lift loop heat to the sink: Q_HP,h = min(D_h, Q_src,h × avail_h + Q_storage). E_HP,h = Q_HP,h / COP_h, where the source supplies Q_HP × (1 − 1/COP).
2. Storage charges from any surplus and discharges at peaks. SOC_h = SOC_h−1 + charge − discharge − losses (time-lagged edges, as in the model graph).
3. Backup covers the rest: Q_backup,h = D_h − Q_HP,h − discharge_h.
4. Network losses: ambient loop ≈ 0. Insulated warm loop: E13 × length.
5. Pumps: E_aux = A11 × Q_delivered.
6. Constraint checks H1–H5 each hour. Sizing (heat-pump MW, storage hours) uses a simple grid search over 3–5 values.

**Outputs:** hourly `Q_HP, Q_backup, Q_storage, E_HP, E_aux, unmet, SOC, P_el`, plus annual sums, SCOP, coverage, design-hour peaks.

**Calibration check:** rerun the Con Ed pilot buildings and compare against the pilot's modeled values: system heat per added electricity 1.77, added electricity 1.51 GWh/yr.

### 3.2 Model B: techno-economic and environmental accounting (deterministic, vectorised over scenarios × assumption sets)
**Inputs:** Model A annual outputs; DEA/EIA unit costs (USD 2025 via `macro_cpi_fx`); pilot unit costs; A05–A08; LL97 factors; AP-42 factors; baseline costs.

**Method:**
- Annuitised CAPEX (CRF), plus O&M, electricity, heat purchase → **LCOH**.
- Baseline cost per building → **savings per offtaker and per apartment**.
- Fuel balance × LL97 factors → **ΔCO₂**.
- Gas displaced × AP-42 → **NOx/PM**.
- Cash flows by actor → **V_DC, V_users, V_community**.

**Outputs:** `kpis.csv` with one row per scenario × assumption set, plus `stakeholder_value.csv`.

### 3.3 Model C: constraints + MCDA
1. **Feasibility gate:** a scenario that fails any H1–H7 is shown as infeasible with the reason. It is not scored.
2. **Normalisation, baseline-referenced:** s_k = clip( (x_k − x_k,S0) / (x_k,target − x_k,S0), 0, 1 ). Use 1 − … for "lower is better" KPIs.
   - Targets are documented, not arbitrary. Examples:
     - ERF: EU average 15%, EnEfG 20%.
     - LCOH: ≤ baseline cost.
     - Coverage: 85% (DEA heat-pump share).
     - ΔCO₂: 100% of baseline heat emissions.
   - Min-max over only four scenarios is avoided because it is unstable and always produces a 0 and a 1.
3. **Weights:**
   - Default: equal across the 4 dimensions (25% each), and equal across KPIs within each dimension.
   - Variants shown: an "equity-first" set and a "cost-first" set.
4. **Composite:** C = Σ_d w_d × mean_k∈d(s_k). It lies in [0, 1].
5. **Sensitivity:**
   - (a) One-at-a-time Low/High for A01–A16 → tornado chart of LCOH, ΔCO₂ and composite.
   - (b) Weight Monte Carlo: 1,000 Dirichlet draws around the defaults → rank-stability (% of draws where each scenario ranks first).
   - (c) A scenario is reported as "robustly better" only if it beats S0 in ≥ 80% of draws.

**Do we need ML training? No.**
- There are no labelled outcomes: no fleet of built heat networks with measured success.
- The physics and accounting relationships are known and auditable.
- There is one site with four alternatives, so a learned model would replace transparent formulas with an unexplainable fit.
- The two places a learned method could help are already covered:
  - **Hourly load shapes:** handled by the degree-hour method.
  - **Optimisation:** handled by grid search.

---

## 4. Scenario design (same pipeline, different connection sets)
| ID | Configuration | Members (from `offtaker_candidates_ll84.csv`) | Annual heat fuel today |
|---|---|---|---|
| **S0** | Today's heating baseline: Con Ed steam (Fulton, 111 8th); gas boilers (Elliott-Chelsea, Chelsea Market, hotels); DC heat rejected through towers. The Con Ed pilot (85 10th Ave → 3 Fulton buildings) is reported as context | All the buildings below, unconnected | – |
| **S1** | Internal reuse: 111 8th Ave supplies its own steam/gas loads | 111 Eighth Avenue (0 m) | 11.5 GWh |
| **S2** | Nearby commercial network | S1 + Chelsea Market (274 m, 12.4), Maritime Hotel (132 m, 8.5), 363 W 16th St (132 m, 6.0), M440 school (230 m, 5.6), 61 9th Ave (183 m, 4.4), Dream Hotel (105 m, 2.2) | ≈ 50 GWh |
| **S3** | Expanded community network, phased with the rebuild | S1 + Fulton (234 m, 29.4 steam; DHW-only until rebuilt, then space heat + DHW), joining the Con Ed pilot UTEN as a second source; Elliott-Chelsea (852 m, 16.2); NYCHA Chelsea (816 m, 10.0); rebuilt units at A03 × (2,056 + up to 3,454); commercial anchors from S2 optional for load balance | ≈ 67 GWh today; rebuild-dependent later |

**Consistency rules:**
- Every scenario is a list of building IDs plus design variables, run through the same Models A → B → C.
- All scenarios use the same weather year, assumption set and constraint list. Only the connection set and sizing change.
- Supply ceiling, for reference: Q_rec = 130.8–148.1 GWh × A01 (0.5 / 0.7 / 0.9).

**What the Composite Score means:**
- It measures how far a feasible configuration moves from today's system (S0 = 0) toward documented targets (= 1), averaged over the four dimensions with stated weights.
- It is **not** an absolute "goodness" grade.
- Always show it next to:
  - the raw KPIs and constraint status;
  - the tornado and rank-stability charts.

So the honest comparison is: "S3 achieves X of the way to target, and beats the baseline in Y% of weight draws."

---

## 5. Visualization architecture (React + TypeScript + D3; Python stays the engine)

**Data contract:** Python writes `outputs/` and the frontend reads static files, with no live Python. That keeps the demo robust offline.

| File | Content |
|---|---|
| `offtaker_scores.csv` | Building ID, coordinates, criteria, score, rank, scenario membership |
| `scenarios.json` | Members, design variables, constraint results |
| `hourly_<S>.json` | Daily aggregates + 3 representative weeks (winter, shoulder, summer) of Q_HP, Q_backup, SOC, D, P_el; not the full 8,760 h, to keep it small |
| `kpis.csv`, `scores.csv` | Per scenario × assumption set |
| `sensitivity.csv` | Tornado data and rank-stability data |
| `sankey_<S>.json` | DC heat → loop → heat pumps → buildings; grid electricity in; backup |
| `provenance.json` | Each KPI → `data_dictionary.csv` row → dataset IDs (S01–S19) |

| Page | Main purpose | Recommended visualization | Required model output |
|---|---|---|---|
| **1. Where: site and offtakers** | Show the place, the heat source and why these users | D3 map (`pluto_lots_1km` points, offtaker bubbles sized by heat demand and coloured by suitability score, DAC tracts shaded, 250/500/1,000 m rings, scenario network lines); ranked bar chart of offtakers; site facts card (15 MW, PM2.5, DAC) | `offtaker_scores.csv`, `scenarios.json` |
| **2. How: system operation** | Prove temperature, capacity, timing, seasonality and continuity | Scenario selector; Sankey of energy flows; stacked area of hourly supply vs demand (heat pump / storage / backup) for representative weeks; monthly bars; load-duration curve; COP vs outdoor temperature; constraint pass/fail badges (H1–H7) | `hourly_<S>.json`, `sankey_<S>.json`, `scenarios.json` |
| **3. Why: value and decision** | Compare scenarios against S0 and show who benefits | KPI cards (Δ vs S0); four-dimension radar or parallel coordinates; composite bar with a weight slider (recomputed client-side from `scores.csv`); stakeholder value split (DC / residents / community); tornado; rank-stability bar | `kpis.csv`, `scores.csv`, `sensitivity.csv`, `provenance.json` |

`variable_network.html` becomes a **"Methodology" drawer** on page 3 that links each KPI to its variables and datasets. It needs re-labelling from v3 values: 80 MW → 15 MW, and the pilot source changes to 85 10th Ave.

---

## 6. Build order and open decisions
1. Feature engineering:
   - `features.py`: de-duplication, useful demand, f_DHW, hourly demand, unit costs in USD 2025.
   - `scenarios.yaml`.
2. Model A, with the pilot calibration check.
3. Model B.
4. Model C, plus offtaker screening.
5. Export `outputs/`.
6. React/D3 pages 1 → 3.

**Decisions needed from the team:**
- Base values for A01 (DC share) and A06 (fence price).
- KPI targets for normalisation.
- Default weight set.
- Whether S3 includes the commercial anchors.
