# Data Readiness Report: Site 1 (111 8th Ave), data layer freeze candidate

**Date:** 2026-10-03. **Rebuild:** `python scripts/fetch_site1_data.py`. A clean run takes about 5 minutes and covers 19 sources.

**Validation:**
- 49 CSVs, all of which load with pandas, holding 575,553 numeric cells.
- Every transcribed value is checked against its source PDF or web text: 132 of 132 checkable values were found verbatim.
- 4 press-release figures could not be machine-checked because nyc.gov blocks scripted downloads. They were checked by hand.
- `data_dictionary.csv` passes the file/column cross-check.

## 1. Verdict
**The data is sufficient for the full four-dimensional computation, with 6 labelled scenario inputs. No dimension is blocked.**

Coverage matrix (`coverage_matrix.csv`, 39 TEAM DELIVERABLE items):

| | Model-ready | Partial (needs a labelled scenario) | Not available |
|---|---|---|---|
| Proposal (site, users, architecture) | 3 | 0 | 0 |
| Technical | 7 | 4 (source temperature, recoverable capacity, capture point, hourly shapes) | 0 |
| Economic + Delivery | 11 | 0 | 0 |
| Environmental | 3 | 2 (post-2030 grid factor, ERF denominator) | 2 (water saving, other resource claims) |
| Social + Regenerative | 6 | 1 (community value attribution) | 0 |

By evidence class:
- 22 items are actual quantitative data.
- 7 are derived.
- 6 rest on literature parameters.
- 3 are qualitative.
- 1 is missing: the tenant cooling-tower type.

## 2. What the targeted acquisition added (S13–S19)
| Gap | Closed by | Key numbers |
|---|---|---|
| Manhattan network cost (GAP-02) | **Con Ed Chelsea UTEN Stage 2 filing** (PSC 22-M-0429, Jul 2025) | Pipe network (UDS) $11.17M for a 1,250 ft route = **$29,318/route-m**. Building-side cost $63,814/apt. Construction $45.53M; $95.53M for all stages with contingency |
| Steam tariff (GAP-01) | Con Ed PSC No. 4 SC 2 Rate II + fuel adjustment; pilot bill table | Marginal steam cost implied by the pilot: **$37.65/Mlb = $140/MWh of useful heat** |
| Steam efficiency (GAP-05) | Pilot Tables 5–6 | Steam-to-useful heat **0.77** |
| Electricity tariff (GAP-03, narrowed) | EIA-861 2024 utility data | Con Ed bundled commercial $282/MWh. NYPA energy $72 + Con Ed delivery $110 ≈ $182/MWh (Fulton buys from NYPA) |
| Heat pricing / revenue / risk | Pilot filing | Fence price **$26/MMBtu** ($88.7/MWh). Resident rate $26.63/MMBtu + $5k/yr connection charge. Monthly minimum supply and offtake commitments, with capped shortfall payments. 5-year contracts |
| CPI / FX (GAP-07) | BLS CPI-U, FRED | CPI factor 2020 → 2025 = 1.244; EUR/USD (2020) = 1.141 |
| Discount rate (GAP-08) | NIST IR 85-3273-39 | FEMP real 3.0%, nominal 4.2% |
| Combustion factors (GAP-09) | EPA AP-42 §1.4 | Small-boiler NOx 0.152 kg per MWh of fuel (uncontrolled); PM 0.012 |
| Rebuild plan (GAP-12) | FEC FAQ, NYCHA press release | 2,056 replacement + up to 3,454 new units. First move-ins end of 2028. New buildings move to electric/renewable heating |
| ASHP at design temperature (GAP-11, narrowed) | ENERGY STAR cold-climate criterion | COP ≥ 1.75 at 5 °F |

## 3. Findings that change the proposal (act on these before modelling)
1. **The Con Ed pilot's heat source is 85 10th Avenue, not 111 8th Ave.** It serves 291 apartments, not 372. Google (111 8th) has only "expressed interest in potentially joining". Our story becomes: **111 8th is the second, much larger source that turns the pilot into a neighbourhood network.** The pilot already installed valves for future connections, and $19M of its assets are designed to survive the rebuild.
2. **Pilot affordability is marginal.** Fulton's net saving is $1k/yr: $375k of avoided steam against $146k + $5k + $193k + $30k of new costs. Our design has to beat this, through scale, a lower fence price or a cheaper NYPA electricity basis. That makes affordability the key economic indicator.
3. **The pilot shows no automatic grid-peak benefit.** It uses 10–15% more electricity than air-source heat pumps on peak days and about 40% more over the year, and the customer winter peak rises by 320 kW. Indicator N6 must be modelled, not asserted.
4. **Pilot carbon is small on LL97 factors:** about 97 tCO₂e/yr (9,961 Mlb of steam saved against 1.51 GWh of added electricity). The filing's "15,000 t lifetime" claim uses steam intensity over a long life. Report both bases.
5. **111 8th Ave averages 14.9–16.9 MW** (LL84), so the "~80 MW" figure in files 01–05 must be corrected.

## 4. Remaining assumptions (`reference/assumptions_scenarios.csv`, Low / Base / High)
| ID | Parameter | Low / Base / High | Status |
|---|---|---|---|
| A01 | DC share of 111 8th electricity | 0.5 / 0.7 / 0.9 | unresolved: ask the tenants |
| A02 | Tenant loop temperature (°C) | 27 / 30 / 35 | literature-bounded |
| A03 | Rebuilt apartment heat demand (MWh/apt/yr) | 6 / 7.5 / 9 | unresolved (existing DHW alone = 8.0) |
| A04 | Steam-to-useful efficiency | 0.70 / **0.77** / 0.85 | base from the pilot |
| A05 | Network cost ($/route-m) | 17,590 / **29,318** / 38,113 | base from the pilot; scaling assumed |
| A06 | Fence price ($/MMBtu) | 19.5 / **26** / 31.5 | all three from the pilot or derived |
| A07 | Electricity price ($/MWh) | 182 / 222 / 282 | measured averages |
| A08 | Real discount rate | **3%** / 5% / 7% | low case from FEMP |
| A09 | Grid factor (t/MWh) | — / **0.289** / 0.289 | post-2030 left blank, not guessed |
| A10 | Heat-pump Lorenz efficiency | 0.40 / 0.45 / 0.50 | DEA |
| A11 | Auxiliary/pumping electricity share | 0.005 / **0.01** / 0.03 | base from DEA |
| A12 | ASHP COP at design temperature | **1.75** / 2.2 / 2.8 | bounded by ENERGY STAR and DEA |
| A13 | Storage (hours of peak) | 0 / 2 / 6 | design variable |
| A14 | Tower type | unresolved | **water claim excluded** |
| A15 | Rebuild first move-ins | **2028** / 2028 / 2030 | FAQ |
| A16 | DC heat availability | 0.998 | OCP |

## 5. Still open (does not block the computation)
- **Hourly measured load shapes (GAP-04):** use degree-hours from the TMYx weather file plus the pilot's measured daily DHW load, and label the method.
- **Post-2030 grid factor (GAP-06):** run a sensitivity case.
- **Exact NYPA/SC-9 bill (GAP-03):** covered by scenario A07.
- **Tenant tower type (GAP-10):** N5 stays out of scoring.
- **Rebuilt-tower energy design:** covered by A03.
- **Attributing rebuild jobs to the network:** excluded.

## 6. Freeze checklist
- [x] 19 sources with an inventory entry: authority, coverage, limitations and file paths (`dataset_inventory.csv`)
- [x] Coverage matrix of the TEAM DELIVERABLE (`coverage_matrix.csv`)
- [x] 31 indicators in the dictionary (16 shortlisted, 5 constraints), each traced to files and columns
- [x] Assumptions separated from observations, with Low/Base/High
- [x] No synthetic observations: derived rows state their formula; transcribed rows carry quote, page and verification flag
- [ ] Team decision on A01 (DC share) and A06 (fence price) defaults
- [ ] Fix "~80 MW" and the pipe-loss figure in files 01–06; re-frame Phase 0 (85 10th Ave source)
