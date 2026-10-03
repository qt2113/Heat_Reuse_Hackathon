# Site 1 data: sufficiency audit (111 8th Ave, Chelsea)

> **Superseded by `DATA_READINESS.md`** (the coverage audit). It adds sources S13–S19, `coverage_matrix.csv` and `reference/assumptions_scenarios.csv`. The text below is the first audit and is kept for history.

Rebuild everything with `python scripts/fetch_site1_data.py`. A clean run takes about 35 s and about 22 MB. Add `--offline` to re-process from `data/raw` and `data/cache`.
`data/validation_report.csv` shows that all 33 CSVs load with pandas. `data_dictionary.csv` passes a check that every file and column it names exists.

## 1. Audit of what existed before
- **`data/raw/` did not exist.** The only CSV was `data/ll84_site1.csv` (4 buildings, from the previous turn). It is now superseded by `processed/offtaker_candidates_ll84.csv` and has been removed.
- **`variable_network.html`** lists 28 datasets, but none was downloaded, and several were Site 2 leftovers or redundant.
- **`06_Factors_and_Datasets.md`** proposed about 20 sources. This audit keeps 12, as the table below shows.

## 2. Final inventory (12 sources; details in `dataset_inventory.csv`)
| id | Source (publisher) | Kind | Supplies |
|---|---|---|---|
| S01 | LL84 benchmarking 2022–24 (NYC DOB) | measured, annual | Source electricity; offtaker heat demand (895 properties ≤ 1 km) |
| S02 | PLUTO 26v2 (NYC DCP) | administrative | Distance, floor area, units, census tract |
| S03 | NYCHA Development Data Book | administrative | Apartments, residents, fixed-income share |
| S04 | NYS Disadvantaged Communities 2023 | statutory designation | DAC flag, LMI share, burden percentiles (18 tracts) |
| S05 | NYCCAS + boiler emissions (NYC DOHMH) | measured / inventory | PM2.5 and NO2 vs city; boiler NOx/PM density |
| S06 | Heat Vulnerability Index (NYC DOHMH) | index | Heat-risk context (low discriminating power) |
| S07 | TMYx 2011–25 Central Park + ASHRAE 2025 design conditions | measured typical year | 8,760 h temperature; −10.5 °C 99.6% design temperature |
| S08 | EIA-861M + EIA NY natural-gas prices | measured, monthly | Electricity and gas prices by sector |
| S09 | NYISO Zone J hourly load 2025 | measured, hourly | Grid peak context (winter 7,552 MW) |
| S10 | Danish Energy Agency technology data (Aug 2026) | engineering datasheet | Heat-pump CAPEX/O&M/COP/life/outage; electric and gas boilers |
| S11 | EIA equipment costs 2023 (13 values transcribed, 13/13 verified) | engineering reference | US boiler, chiller and water-loop heat-pump cost/COP |
| S12 | LL97 coefficients (law text; 5/5 verified) | statute | tCO₂e per MWh of electricity, gas, oil, steam; $268/t |

Plus `reference/engineering_parameters.csv` and `reference/reference_cases.csv`:
- **30 document parameters (E01–E30) and 5 team assumptions (A01–A05).** Each row carries its own evidence-type label, and the team assumptions are labelled `team_assumption`.
- **11 reference cases**, all quoted from the organizer pack.

## 3. Key measured numbers
- **111 8th Ave:** 130.8–148.1 GWh/yr of electricity (2022–24), a **14.9–16.9 MW average**. The data center occupies 22–26% of floor area. **The "~80 MW" in files 01–05 is wrong.**
- **Anchor heat demand (3-yr mean fuel input):**
  - Fulton: 29.4 GWh of steam, 234 m away.
  - Elliott-Chelsea: 16.2 GWh of gas, 852 m.
  - Chelsea Market: 12.4 GWh of gas, 274 m.
  - 111 8th itself: 11.5 GWh.
  - Total: **69.5 GWh/yr**.
  - Also found: Penn South (64.9 GWh, 609 m, one year of data).
- **Equity:** the site and Fulton share tract 36061008300, which is a **designated DAC** (combined percentile 0.84; 80% of households are LMI). Fulton has 944 apartments and 1,809 residents, and 50% of households are fixed-income.
- **Air:** PM2.5 in Chelsea–Clinton is 9.5 vs 6.3 µg/m³ citywide (2024). Boiler NOx is 124 vs 21 t/km² citywide (2019).

## 4. Indicators (full matrix in `data_dictionary.csv`)
There are 21 candidates, plus 4 merged duplicates (T3, C4, N3, C6) and 5 hard constraints (H1–H5).

**Shortlist (15):**
- **Technical:** T1 recoverable heat · T2 seasonal COP · T4 hourly demand coverage · T7 network distance
- **Economic:** C1 CAPEX/kW · C2 LCOH · C3 LCOH vs current heat cost
- **Environmental:** N1 ERF · N2 tCO₂e avoided · N4 on-site combustion displaced · N6 winter grid peak avoided
- **Social:** S1 low-income households served · S3 EJ exposure · S5 acceptance/governance (qualitative) · S6 rebuild design-window fit (qualitative)

By class:
- Observable: T7, S1, S3
- Derived: T1, C1, C3, N1, N2, N4
- Need simulation: T2, T4, C2, N6
- Qualitative: S5, S6

Redundancy decisions:
- **Carbon:** building GHG correlates with electricity use (ρ = 0.91), so N2 is computed from heat fuel × LL97 factors, never from LL84 total GHG.
- **Size:** heat demand vs floor area ρ = 0.61, so floor area is not a separate factor. Distance is independent (ρ ≈ 0).
- **Merged pairs:**
  - T5 duplicates T4.
  - C4, C5 and S2 are transforms of C2/C3.
  - N3 shares N2's numerator.
  - T3 is the reciprocal of T2.
  - S4 does not discriminate (ZIP 10011 = 1).
  - N5 is blocked until the tower type is confirmed.

## 5. Gaps and required assumptions
- **Missing data (GAP-01…12):**
  - **Con Ed steam tariff:** needed for the Fulton baseline price.
  - **PSC 22-M-0429 filings:** the only source for Manhattan pipe cost and Phase 0 scope.
  - **Con Ed electricity tariffs:** the EIA state average stands in for now.
  - **Hourly load shapes:** fall back to degree-hour disaggregation.
  - **Fuel-to-useful-heat efficiency for steam.**
  - **Post-2030 grid carbon factor (Cambium).**
  - **CPI escalation and discount rate.**
  - **AP-42 combustion emission factors:** optional.
  - **Tenant tower type:** blocks any water claim.
  - **ASHP COP at −10.5 °C.**
  - **Rebuild schedule.**
- **Assumptions (A01–A05):**
  - Data-center share of electricity: 0.5–0.9.
  - Tenant loop temperature: 27–35 °C.
  - Rebuilt-unit demand: 6–9 MWh/yr.
  - EUR/USD exchange rate.
  - Manhattan cost factor: 1.5–2.0×.
- **Correction to file 06:** pipe heat loss is **0.5–1.5%/km** (CBS), not 0.5%/km.

## 6. Is the data sufficient to start modeling?
**Yes, for supply–demand matching, sizing, carbon and equity indicators.** These rest on measured data: LL84, TMYx, NYCHA, DAC, NYCCAS, LL97.

**Partly, for economics:**
- Heat-pump costs and the gas baseline are covered.
- The **steam price** (GAP-01) and **Manhattan pipe cost** (GAP-02) must be added, or shown as labelled sliders, before quoting LCOH savings for Fulton.
- The **data-center share** (A01) is the largest supply-side uncertainty and should be a slider in every result.
