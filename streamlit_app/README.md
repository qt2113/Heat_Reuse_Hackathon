# Data-center waste heat → Chelsea buildings

Hackathon model (NYU · Grundfos · HDR) that recovers server heat from **111 8th Avenue**
(Google-owned carrier hotel, Manhattan) with a heat pump and pipes it along streets to nearby
buildings. It estimates hourly heat demand for every disclosed building within a radius,
chooses which ones to connect, dispatches supply hour by hour (data center → storage → each
building's existing boilers) and reports heat, CO₂, money and water.

## Quick start

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-optional.txt   # optional: pcst_fast (needs a C++ compiler on some systems)
streamlit run app.py
```

Downloads are cached in `data/` (committed), so a fresh clone starts without network access.
Delete a file in `data/` to force a fresh download. If a download fails and no cache exists, the
code falls back to the bundled snapshot in `data/sample/` (LL84/PLUTO) or a synthetic
weather year / street grid, and the app labels every dataset **LIVE / CACHED / SAMPLE**.

Step-by-step scripts (each prints its results):

```bash
python scripts/step1_demand.py     # buildings, annual + peak heat, data-quality log
python scripts/step2_supply.py     # heat pump + hourly dispatch for a fixed building set
python scripts/step3_network.py    # street graph, greedy selection, KPIs, outputs/step3_map.html
python -m pytest -q                # unit tests
```

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repository (include `data/` so the app does not depend on live APIs).
2. Go to <https://share.streamlit.io> → **Create app** → pick the repo/branch, main file `app.py`.
3. **Advanced settings → Python 3.11**. Requirements are read from `requirements.txt`
   (`pcst_fast` is deliberately optional; the app falls back to greedy without it).
4. Deploy. First load takes ~10 s (demand matrix + street graph); later slider changes take < 1 s.

## Method

| Step | What | Where |
|---|---|---|
| 1. Demand | LL84 annual gas + steam + oil → useful heat (× fuel efficiency × (1 − non-heating share)), split into DHW / space heat by property type. Space heat ∝ heating degree-hours (base 18 °C, optional thermal-mass smoothing); DHW follows a fixed daily curve. 8,760 h per building; rows sum exactly to the annual total. | `src/demand.py` |
| 2. Supply | COP = η·T_hot/(T_hot − T_cold) in kelvin, T_hot = network supply + building HX penalty. Delivered = Q_src·COP/(COP−1). Hourly merit order: heat pump direct → tank → building boilers; outage block optional. Asserted every hour: served + storage + backup = demand. | `src/supply.py` |
| 3. Selection | OSM drive network, edges split to ≤ 40 m, buildings snapped with a service pipe. Prize-collecting Steiner tree from the data center. **Recommended method = greedy + local search**: greedy adds the building with the largest exact marginal value (capacity shared pro rata hour by hour, so value is not additive) minus street-path, service and substation cost; local search then re-routes the chosen set with a nearest-first Steiner tree, tries dropping each building and resumes greedy additions until no move improves (never worse than greedy; +$47k/yr and −190 m of pipe in the base case). What is maximised is set by `objective` in config: project cash, or the data-center owner's profit, optionally plus a carbon value and extra weight for public housing/schools. | `src/network.py` |
| 4. Outputs | Heat delivered, coverage split, net CO₂ (fuel displaced − grid electricity), money (avoided fuel + LL97 + cooling-tower water − electricity − annualised capex), who gets what (data-center owner vs building owners at the heat-price discount), water (recovered heat × 1.6 m³/MWh), pipe km, tank needed for outages. | `src/metrics.py` |

Unserved heat is supplied by each building's existing boilers/steam, so it changes neither cost
nor emissions relative to today — no new backup plant is costed.

## Key findings (default scenario)

* **Network heat costs ~$73/MWh** (COP 3.1 at 30 → 75 °C, $0.22/kWh) vs **$60/MWh from a gas
  boiler** and **$140/MWh from Con Ed steam**. Only steam-heated buildings are worth connecting;
  the optimiser independently picks **Fulton Houses** — the campus Con Ed chose for its pilot.
* 10 buildings, 1.9 km of pipe, 41.5 GWh/yr delivered (80 % of their demand), 3,550 tCO₂/yr net,
  ~$1.6 M/yr net after all annualised capex (~$18.5 M upfront, ~6-yr simple payback), 45,000 m³/yr of
  cooling-tower water (~$210k/yr at NYC water + sewer rates).
* Storage adds little at 5 MW: in winter the heat pump runs flat out with nothing spare to
  store. A week-long outage at peak would need ~1,240 MWh of storage → keep building boilers.

## Priority presets (for non-technical users)

The top of the app asks *"What matters most to you?"*. Pick a button or type a sentence (free keyword
matching, no AI service). Presets only set the sliders under **Advanced settings** — nothing is hidden.
Defined in `config.yaml → presets`; regenerate the table with `python scripts/presets_table.py`.

| Preset | What it does | Buildings | CO₂ cut t/yr | Net cash $M/yr |
|---|---|---|---|---|
| ⚖️ Base case | Documented defaults, cash only | 10 | 3,547 | 1.58 |
| ⭐ Most realistic | + 24 h thermal-mass smoothing, don't claim Con Ed pilot buildings | 12 | 3,846 | 1.53 |
| 🏘️ Benefit the community | Carbon valued at NYS $212/t, 2× weight for public housing & schools | 10 (7 priority) | 3,625 | 1.18 |
| 💰 Most profit for data-center owner | Owner pays all costs, sells heat 10 % below today's price | 8 | 3,413 | 1.57 (owner 0.85) |
| 🌍 Biggest CO₂ cut | Carbon valued at $400/t | 25 | 5,045 | 1.26 |
| 💧 Liquid cooling | Source 45 °C, 10 MW recoverable (COP 4.6) — gas buildings start to pay | 20 | 8,518 | 3.62 |
| 📈 Best case | Base network, every input at its favourable end | 10 | 5,833 | 7.57 |
| ⚠️ Worst case | Base network, every input at its unfavourable end at once (a bound, not a forecast) | 10 | 968 | −5.24 |

## Data and quality issues found

Sources: NYC LL84 2023-present (`5zyy-y8am`), MapPLUTO (`64uk-42ks`), Open-Meteo archive (2023
hourly), OpenStreetMap via osmnx, NYC GeoSearch for the site, Con Ed's Chelsea UTEN page for the
pilot (85 10th Ave → 401 W 16th St, 410 & 420 W 17th St; awaiting NY PSC approval).

* **Campus-level records.** NYCHA Fulton (4 lots, 12 buildings) reports all steam on one parent
  record; the "Bldgs 1–4" child repeats the campus total. Parents are allocated to children (or
  PLUTO lots) by floor area and the duplicates dropped.
* **Same building, several records.** Re-registered names/IDs across years, owner + managing
  agent filings, "Copy of …"/"zzzz…" entries: one report year is chosen per BBL, then records with
  identical fuel or same GFA at the same geocode are dropped (~90 within 800 m).
* **Central plants.** Penn South Bldg 4 shows 1,089 W/m² (the co-op's plant); anything > 300 W/m²
  is excluded as not-a-single-building.
* Other: 54 records with no heating fuel, 20 without a valid BBL, 63 using 2022/2024 because 2023
  is missing. Full log in the app ("Data provenance & quality log").
* LL84 BBLs come in mixed formats (`1007390001`, `1-00078-7506`, `a;b;c`) and are normalised.

## Limitations

* Annual LL84 totals → hourly by degree-hours; no building-specific controls or occupancy.
  Steam used for summer absorption cooling cannot be separated (no monthly steam data).
* Constant COP (fixed source and supply temperature); no outdoor-reset of supply temperature.
* Selection ignores storage (dispatch afterwards includes it). Greedy + local search is a heuristic;
  its gap to the true optimum has not been measured (an exact MILP is a possible extension).
* Hydraulics (pipe diameters, pressure drop) not yet sized; heat loss is a W/m constant.
* LL97 limits by property type are approximate (single-use, 2024-29 table) — **VERIFY**.

## Assumptions

Every number used by the model lives in `config.yaml` with unit, range and source.
Regenerate this section after editing: `python scripts/assumptions_md.py --write`.

<!-- ASSUMPTIONS:START -->
| Parameter | Value | Unit | Plausible range | Source / rationale |
|---|---|---|---|---|
| `site.lat` | 40.741366 | deg |  | NYC GeoSearch (PAD 26c) for '111 8 Avenue', BBL 1007390001 / BIN 1013043. Verified 2026-10-03. |
| `site.lon` | -74.003211 | deg |  | NYC GeoSearch (PAD 26c). |
| `con_ed_pilot.pilot_share_of_lot` | 0.75 | - | [0.5, 1.0] | Assumption: 3 of 4 buildings on BBL 1007140031 (PLUTO numbldgs=4), equal size. |
| `data.radius_m` | 800 | m | [200, 1500] | Brief default. ~10 min walk; typical first-phase district-heat cluster. |
| `data.street_graph_dist_m` | 1000 | m | [500, 2000] | Brief. Must exceed radius so routes can leave the circle. |
| `data.weather_year` | 2023 | yr |  | Brief default. 2023 NYC HDD18 = 2,441 K·d (warm winter, but Feb-4 cold snap to -16.5 °C). |
| `data.ll84_report_year` | 2023 | yr | [2022, 2024] | NYC Open Data 5zyy-y8am (LL84 2023-present). Matched to weather_year. |
| `demand.boiler_efficiency` | 0.8 | - | [0.7, 0.9] | Brief. Typical seasonal efficiency of older NYC gas/oil steam & HW boilers (ASHRAE/NYSERDA audits 0.70-0.85). |
| `demand.oil_boiler_efficiency` | 0.8 | - | [0.7, 0.88] | Assumed equal to gas boilers. |
| `demand.steam_utilization_efficiency` | 0.85 | - | [0.75, 0.95] | Assumption. Steam-to-water HX ~0.95 × condensate/flash & distribution losses ~0.9. |
| `demand.t_base_c` | 18.0 | degC | [15.0, 18.5] | Brief. EN ISO 15927-6 / Eurostat HDD base; ASHRAE 65°F = 18.3 °C. |
| `demand.space_smoothing_h` | 0 | h | [0, 48] | Option. Thermal time constants of heavy masonry NYC buildings are tens of hours (ASHRAE Fundamentals Ch.18); 24 h is a common daily-mean design simplification. |
| `demand.dhw_multiplier` | 1.0 | - | [0.5, 1.5] | Slider; scales every DHW share. |
| `demand.peak_intensity_check_w_m2` | [20, 120] | W/m2 of gross floor area |  | Brief. Typical design heat loss of NYC buildings ~30-90 W/m2. |
| `demand.exclude_peak_w_m2_above` | 300 | W/m2 | [150, 1000] | Assumption. >2.5x the upper sanity bound is not a single building: e.g. Penn South Bldg 4 (1,089 W/m2) houses the co-op's central plant. |
| `demand.heat_intensity_outlier_kbtu_ft2` | [5, 150] | kBtu/ft2/yr of heating fuel |  | Flag only. NYC multifamily median ~60-70 kBtu/ft2 site EUI (LL84). |
| `supply.q_src_mw` | 5.0 | MW_th | [1.0, 20.0] | Brief. Cross-check: 111 8th Ave bought 144.7 GWh electricity in 2022 (avg 16.5 MW, LL84) — essentially all ends as low-grade heat; 5 MW is a conservative recoverable share. |
| `supply.t_source_c` | 30.0 | degC | [20.0, 45.0] | Brief. Air-cooled DC return air/condenser water 25-35 °C; liquid cooling 40-50 °C. |
| `supply.t_supply_c` | 65.0 | degC | [45.0, 80.0] | Brief. Network supply temperature. |
| `supply.hx_penalty_k` | 10.0 | K | [5.0, 15.0] | Brief. Building HX approach + legacy radiator/DHW (legionella 60 °C) requirement. |
| `supply.cop_eta` | 0.4 | - | [0.3, 0.6] | Brief. Calibrated to Grundfos case (16-25 °C source → 60-75 °C, COP 2.95). |
| `supply.outage_hours` | 0 | h/yr | [0, 500] | Slider. DC maintenance / HP trip. |
| `supply.pumping_kwh_per_mwh` | 10.0 | kWh_e/MWh_th | [5.0, 25.0] | Assumption. Distribution pumping ~0.5-2 % of delivered heat for well-designed variable-speed networks (Grundfos / Euroheat & Power guidance). |
| `supply.storage_mwh` | 20.0 | MWh_th | [0.0, 200.0] | Assumption. Steel hot-water tank ~ 1 MWh per 20-25 m3 at ΔT 35-40 K. |
| `supply.storage_loss_per_h` | 0.001 | 1/h | [0.0, 0.005] | Assumption. Well-insulated tank ~1-2 %/day. |
| `supply.storage_max_power_mw` | 5.0 | MW_th | [1.0, 20.0] | Assumption. Charge/discharge limit. |
| `economics.gas_price_usd_mmbtu` | 14.0 | USD/MMBtu | [10.0, 18.0] | Brief, VERIFY. EIA NY commercial avg 2025 = $11.47/Mcf ≈ $11.06/MMBtu (state avg; Con Ed NYC delivery charges are higher). https://www.eia.gov/dnav/ng/hist/n3020ny3a.htm |
| `economics.steam_price_usd_mmbtu` | 35.0 | USD/MMBtu | [30.0, 60.0] | Con Ed bill examples Nov-2025: SC-3 apartment 900 Mlb/mo → $35,840 = $39.8/Mlb ≈ $33/MMBtu; SC-2 commercial 750 Mlb → $54.7/Mlb ≈ $46/MMBtu (1 Mlb = 1.194 MMBtu). https://coned.com/en/accounts-billing/your-bill/about-con-edisons-rates |
| `economics.oil_price_usd_mmbtu` | 25.0 | USD/MMBtu | [18.0, 35.0] | Assumption, VERIFY. #2 heating oil ~$3.5/gal / 0.1387 MMBtu/gal. |
| `economics.electricity_price_usd_kwh` | 0.22 | USD/kWh | [0.15, 0.3] | Brief, VERIFY. EIA Electric Power Monthly Table 5.6.A, NY commercial ~20-23 ¢/kWh 2024-25; Con Ed NYC at upper end. |
| `economics.pipe_cost_usd_m` | 3000.0 | USD/m (trench | [1000.0, 8000.0] | Brief, VERIFY. EU urban pre-insulated DN100-200 €860-1,270/m (npro.energy, DEA); Manhattan utility congestion and street-opening rules multiply this 2-5x. |
| `economics.hp_capex_usd_kw` | 1200.0 | USD/kW_th | [600.0, 2000.0] | Brief, VERIFY. DEA technology data large HP ~€0.6-1.0 M/MW_th incl. installation; US urban premium. |
| `economics.storage_capex_usd_mwh` | 3000.0 | USD/MWh_th | [1000.0, 10000.0] | Assumption. DEA: large steel tanks ~€2-5k/MWh; small urban tanks dearer. |
| `economics.discount_rate` | 0.06 | 1/yr | [0.03, 0.1] | Brief. |
| `economics.pipe_life_yr` | 30 | yr | [25, 50] | Brief. Pre-insulated steel pipe design life 30-50 yr. |
| `economics.hp_life_yr` | 20 | yr | [15, 25] | Brief. |
| `economics.diversity_factor` | 0.65 | - | [0.5, 0.9] | Brief. Network simultaneity for sizing (Winter et al. / DH design guides). |
| `network.max_segment_m` | 40.0 | m | [20.0, 100.0] | Modelling choice: street edges are split so buildings attach near their frontage, not at the nearest intersection (Manhattan cross-town blocks ~260 m). |
| `network.heat_loss_w_per_m` | 20.0 | W/m trench | [10.0, 40.0] | Assumption. Pre-insulated twin/pair DN80-150 at 65/40 °C ~15-25 W/m (Logstor/Isoplus catalogue loss tables, series 2). |
| `network.building_connection_usd_per_kw` | 150.0 | USD/kW_peak | [80.0, 300.0] | Assumption, VERIFY. Building substation (HX, controls, metering, tie-in) ~£50-100/kW in UK/DK; US labor premium. |
| `network.connection_life_yr` | 25 | yr | [20, 30] | Assumption. Substation design life. |
| `emissions.gas_tco2_per_mmbtu` | 0.05306 | tCO2/MMBtu | [0.05306, 0.05311] | Brief / EPA GHG EF hub (53.06 kg CO2/MMBtu). LL97 uses 0.05311 tCO2e/MMBtu. |
| `emissions.steam_tco2_per_mmbtu` | 0.04493 | tCO2e/MMBtu | [0.04, 0.05] | LL97 (RCNY §103-14) district steam factor 0.00004493 tCO2e/kBtu. |
| `emissions.oil_tco2_per_mmbtu` | 0.07421 | tCO2e/MMBtu | [0.0732, 0.0742] | LL97 #2 oil factor 0.00007421 tCO2e/kBtu. |
| `emissions.grid_tco2_per_kwh` | 0.000288962 | tCO2e/kWh | [0.00015, 0.00035] | Brief / LL97 2024-2029 electricity factor. |
| `emissions.ll97_penalty_usd_t` | 268.0 | USD/tCO2e |  | LL97 §28-320.6: $268 per tCO2e over the limit. |
| `emissions.water_m3_per_mwh` | 1.6 | m3/MWh_th | [1.2, 2.0] | Brief. Cooling-tower evaporation ≈ latent heat 0.68 m3/MWh + drift/blowdown. |
| `objective.heat_discount` | 0.1 | - | [0.0, 0.5] | Assumption. 'Avoided-cost minus discount' pricing, common in district heating: each building pays its current heat cost per MWh x (1 - discount). |
| `objective.carbon_price_usd_t` | 0.0 | USD/tCO2e | [0.0, 400.0] | Off by default (cash only). NYS DEC Value of Carbon 2025: $212/t (2020$, 2 % discount rate). https://dec.ny.gov/sites/default/files/2025-04/vocguide2025.pdf |
| `objective.water_price_usd_m3` | 4.62 | USD/m3 | [3.0, 6.0] | NYC Water Board FY2026: water $5.05 + sewer $8.02 = $13.07 per 100 ft3 (2.832 m3). Saved by the data center (less cooling-tower make-up). https://www.nyc.gov/site/dep/pay-my-bills/how-we-bill-you.page |
| `objective.priority_weight` | 1.0 | x | [1.0, 3.0] | Value multiplier for priority buildings in the optimiser only (equity weighting). 1 = no preference. |

### Lookup tables

**`demand.dhw_share`** — default 0.15. Brief values for multifamily/office/hotel/other; others: US DOE CBECS 2018 / RECS 2020 end-use splits (rounded). Range ±50%.

| Property type | Value |
|---|---|
| Multifamily Housing | 0.28 |
| Residence Hall/Dormitory | 0.28 |
| Senior Living Community | 0.3 |
| Senior Care Community | 0.3 |
| Hotel | 0.3 |
| Office | 0.08 |
| Medical Office | 0.1 |
| Retail Store | 0.08 |
| K-12 School | 0.1 |
| College/University | 0.12 |
| Hospital (General Medical & Surgical) | 0.25 |
| Fitness Center/Health Club/Gym | 0.4 |
| Restaurant | 0.3 |
| Supermarket/Grocery Store | 0.15 |

**`demand.non_heating_share`** — default 0.05. Assumption. Gas cooking ~3-7% of NYC multifamily gas (RECS 2020 Mid-Atlantic); restaurants/food halls mostly cooking; offices allow for steam absorption cooling.

| Property type | Value |
|---|---|
| Multifamily Housing | 0.05 |
| Office | 0.15 |
| Hotel | 0.1 |
| Restaurant | 0.5 |
| Food Service | 0.5 |
| Other - Restaurant/Bar | 0.5 |
| Supermarket/Grocery Store | 0.25 |
| Hospital (General Medical & Surgical) | 0.2 |
| Laboratory | 0.2 |

**`emissions.ll97_limits_2024_tco2e_ft2`** — default None. 1 RCNY §103-14 Table, 2024-2029 limits (rounded). VERIFY per building class.

| Property type | Value |
|---|---|
| Multifamily Housing | 0.00675 |
| Office | 0.00758 |
| Hotel | 0.00987 |
| Retail Store | 0.01181 |
| K-12 School | 0.00758 |
| Residence Hall/Dormitory | 0.00675 |
| Medical Office | 0.01194 |
| Supermarket/Grocery Store | 0.02381 |
| Restaurant | 0.02381 |
<!-- ASSUMPTIONS:END -->

## Project structure

```
app.py               Streamlit UI
config.yaml          all assumptions
src/fetch.py         downloads, caching, cleaning, sample fallbacks
src/demand.py        annual split, hourly profiles, sanity checks
src/supply.py        COP, heat pump, hourly dispatch with storage/backup
src/network.py       street graph, snapping, selection
src/metrics.py       economics, CO2, water, KPIs
src/scenario.py      prepare (cached) + evaluate (per slider change)
src/mapviz.py        folium map
scripts/             step-by-step runners, README generator
tests/               energy balance, units, COP, greedy on toy graphs
data/                cached downloads (+ data/sample fallback snapshot)
```

## Shareable web version (React + D3)

A static page with the eight presets precomputed lives in `web/`. Rebuild after changing the model or
`config.yaml` with `python scripts/export_web.py` (writes `web/data.json` and `web/index.html`, which inlines
the data into `web/template.html`). Custom slider settings still need the Streamlit app.
