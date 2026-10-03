# 06: Factors and Datasets (Site 1, 111 8th Ave)

> **Purpose.** The factors our computation needs across the brief's 4 dimensions, and **one authoritative quantitative dataset per factor**.
> **How it was built.** Sources: the 23 organizer documents in `sources/` and the 28 datasets already in `variable_network.html`, plus live checks on 2026-10-03.
> **Selection rules (picky):**
> 1. Primary publisher only: a government agency, utility tariff, national lab or standards body. No blogs or trackers.
> 2. Site-specific beats national: metered beats modeled, and modeled beats a literature range.
> 3. It must give a **number we can put in `config.yaml`**, not just context.
> 4. At most **one primary + one cross-check** per factor.
>
> Legend: ✅ already in the HTML · 🆕 add · ⬆ promote to primary · ⚠ no dataset exists, so use a labeled assumption from the organizer documents.

---

## 0. What the data changed (read first)

Pulled today from **NYC LL84 benchmarking 2022–2024** (dataset `5zyy-y8am`). The extract is in `data/ll84_site1.csv`.

| Building | 2024 metered | What it means |
|---|---|---|
| **111 8th Ave** (the source) | Electricity **130.8 GWh** = **14.9 MW average** (16.5 MW in 2022). Data-center floor area 531k ft² of 2.38M ft² | **Our "~80 MW" is wrong.** The whole building averages ~15 MW, so recoverable heat is roughly **≤ 13–15 MWth**, and less if the DC share is smaller. "5–10 MWth" is still plausible but now near the ceiling. **Fix in files 01, 03, 04, 05.** |
| 111 8th Ave (also a user) | Steam 9.1 GWh + gas 1.7 GWh | The building itself is a **10.7 GWh/yr heat customer**, the cheapest offtaker (0 m of pipe) |
| **NYCHA Fulton** (401 W 16th St, 12 buildings, 944 apts) | Con Ed steam **29.5 GWh** (27.6–31.0 over 2022–24); gas 0 | Real anchor demand. **31 MWh of steam per apartment per year**, a very inefficient steam system |
| **NYCHA Elliott-Chelsea** (1,129 apts) | Gas **17.8 GWh** | Second anchor. Gas boilers, so the **largest carbon and air-quality win** |
| **Chelsea Market** | Gas 12.1 GWh, electricity 25.6 GWh | Commercial offtaker; LL97 applies |
| **Total heat fuel, 4 buildings** | **≈ 70 GWh/yr** (NYCHA alone 47 GWh) | Replaces our "35–50 GWh" guess. Phase 1 can be sized on **measured** data |

Other numbers pulled live:
- **NYCHA Development Data Book** (`evjd-dqpz`):
  - Fulton: 944 apts, 1,809 residents, **49.8% fixed-income households**, average rent $756.
  - Elliott + Chelsea + Chelsea Addition: 1,129 apts, 2,091 residents.
  - Chelsea Addition: 96% fixed income (senior building).
- **NYCCAS** (`c3uy-2p5r`): PM2.5 in Chelsea–Clinton is **8.4 µg/m³ vs 6.0 µg/m³ citywide** (2024, matching series). That is about 35% above the city. Check the season column before quoting.

> Caveats:
> - LL84 marks some years as "estimated". Quote 3-year ranges, not one year.
> - Whether tenant-direct meters are included in the 111 8th total should be verified. The building has 8 active meters.

---

## 1. TECHNICAL

| Factor (model variable) | What we need | **Primary dataset** (publisher) | Cross-check | Status |
|---|---|---|---|---|
| Heat available at capture point (`P_IT`, `Q_DC`) | MW available, hourly | **NYC LL84** electricity for BBL 1007390001 (NYC DOB / Open Data) → average MW × recoverable fraction | Organizer [OCP-101]: ~100% of IT power becomes heat; [Grundfos slides] "up to 85% recoverable" | ⬆ (replaces `dc_tracker`) |
| Capture temperature (`T_src`) | °C by cooling type | **ASHRAE TC 9.9 liquid-cooling classes (W17–W45+)** | [OCP-101]: air 27–28 °C, direct liquid cooling 45–65 °C; [CBS]: "most waste heat 20–26 °C" | 🆕 / ⚠ tenant loop temperature unknown, so use a slider of 27–35 °C |
| Ambient-loop temperatures (`T_loop`) | Supply/return | [CBS] 5G networks: 10–25 °C flow, 3–15 °C return | — | ✅ (organizer document) |
| Heat-pump COP (`COP_bldg`) | COP vs lift | **AHRI Directory**: water-source heat-pump ratings (ISO 13256-1) → calibrate the Carnot fraction | [Danfoss] case 16 → 60 °C, COP ≈ 5; [CBS] 3 connection modes | 🆕 |
| Baseline ASHP COP (all-electric alternative) | COP at 47 / 17 / 5 °F | **NEEP Cold-Climate ASHP List** | — | 🆕 (replaces `cleanheat`) |
| Hourly weather (`T_amb`) | 8,760 h | **NSRDB TMY** for NYC | — | ✅ (drop the NOAA LCD duplicate) |
| Design-day peak (`T_design`) | 99.6% heating dry-bulb | **ASHRAE Climatic Design Conditions** (Central Park / LGA station) | — | 🆕 |
| Hourly demand shape (`D_sh`, `D_dhw`) | Normalized 8,760 profile | **NLR End-Use Load Profiles** (ResStock/ComStock, New York County, OEDI) | — | ⬆ (merge `resstock` + `comstock` into one) |
| Annual demand per offtaker (`E_annual`) | MWh/yr | **NYC LL84** (pulled; §0) | NYCHA Data Book for unit counts | ✅ ⬆ (now the primary source; drop EIA RECS/CBECS) |
| Distance / candidate offtakers (`dist`) | m, ft², use | **NYC MapPLUTO** | — | ✅ |
| Network heat loss (`q_loss_km`) | %/km | [CBS]: well-insulated 70–80 °C pipe ≈ 0.5%/km; ambient loop ≈ 0 | — | ⚠ (organizer document) |
| Storage (`Tank_cap`, `loss_tank`) | Round-trip efficiency, life | [IDEA TES]: hot/chilled-water TES ~100% round trip, 40+ yr life | DEA Technology Catalogue | ⚠ → 🆕 |
| Reliability / continuity (`avail_DC`) | Downtime h/yr | [OCP-101]: DC uptime ≥ 99.8% (≤ 20 h/yr); backup sized to the full peak | FPCJ meeting: Verizon asked that the system "not solely rely" on DC heat | ⚠ (organizer document) |
| Oversizing margin | % above peak | [CBS]: networks carry 30–60% over peak | — | ⚠ (organizer document) |

## 2. ECONOMIC + DELIVERY

| Factor | What we need | **Primary dataset** | Cross-check | Status |
|---|---|---|---|---|
| Electricity price (`p_el`) | $/MWh, NYC commercial/residential | **EIA Electric Power Monthly, Table 5.6.A** (NY) | **Con Ed SC-8/SC-9 tariffs** (`coned`) for the demand charge | ✅ |
| Steam price (baseline for Fulton) | $/Mlb → $/MWh | **Con Ed steam tariff (PSC No. 4)** | LL84 steam volume × tariff = Fulton's annual bill | ✅ |
| Gas price (baseline for Elliott, Chelsea Market) | $/MMBtu | **EIA Natural Gas Prices, NY** (commercial + residential, monthly) | — | 🆕 (replaces `eia_fuel`, which is heating oil/propane left over from Site 2) |
| CAPEX: heat pumps, pipe, tanks, heat-recovery chillers (`c_HP`, `c_pipe`, `uc_tank`) | $/kW, $/m, $/m³ | **Danish Energy Agency Technology Data, Generation of Electricity and District Heating** (CAPEX, fixed and variable O&M, lifetime; peer-reviewed annually) | **PSC Case 22-M-0429** (Con Ed Chelsea pilot filing: real Manhattan cost) | 🆕 DEA · ✅ PSC |
| Connection cost vs distance | % of CAPEX | [CBS]: 3% at 50 m → 50% at 4 km | — | ⚠ (organizer document) |
| Discount rate, analysis life (`r`, `n`) | Real % | **NIST Handbook 135 Annual Supplement** (DOE FEMP) | — | 🆕 |
| Business-case benchmark | Payback | [CBS] 10 MW case: €6M heat pump, ~9-yr payback (vs > 30 yr for an ambient-source heat pump) | [DATA HEAT]: DC OPEX savings < 5%; DC contracts ≤ 10 yr | ⚠ (organizer document) |
| Incentives | % of CAPEX | **IRS Form 3468 instructions** (§48 / §48E eligibility, verify) | [DATA HEAT]: 2021 ITC 26% for waste-energy recovery | 🆕 (verify before quoting) |
| Revenue model / heat price cap (`p_fence`) | $/MWh | Avoided-cost cap = min(steam tariff, all-electric ASHP cost) from the rows above | Stockholm open-district-heating model (organizer documents) | ⚠ derived |
| Ownership / regulation | Who may own a thermal network | **NY UTENJA (S9422) + PSC 22-M-0429** | [DATA HEAT] NY section | ✅ |

## 3. ENVIRONMENTAL

| Factor | What we need | **Primary dataset** | Cross-check | Status |
|---|---|---|---|---|
| Carbon factors (`EF_el`, `EF_gas`, `EF_steam`) | tCO₂e per unit | **LL97 coefficients, 1 RCNY §103-14** (NYC DOB): electricity 0.288962 t/MWh (2024–29), gas 0.05311 t/MMBtu (= 0.181 t/MWh fuel), steam 0.04493 t/MMBtu (= 0.153 t/MWh) | — | ⬆ (the DOB page replaces the Accelerator brief; drop `egrid`) |
| Future grid carbon (2030+) | Long-run marginal emissions | **NLR Cambium** (NYISO Zone J, mid-case) | — | 🆕 (answers "the grid will decarbonize anyway") |
| LL97 penalty value (`LL97_avoided`) | $/t | LL97: **$268/tCO₂e**, commercial offtakers only | — | ✅ |
| Energy efficiency (`ERF`, `ERE`, `PUE`) | Definitions + benchmarks | [HDR deck] Green Grid definitions; colocation PUE < 1.5; **ISO/IEC 30134-6** for ERF | [DATA HEAT]: EU average reuse ~15%; Germany EnEfG 10/15/20% | ✅ (drop the White & Case summary; the DATA HEAT guide covers it) |
| Water saved (`W_saved`) | m³ per MWh not sent to towers | Physics: evaporation ≈ latent heat; [HDR deck]: evaporation 67% / blowdown 32% of tower water; industry WUE 1.8 L/kWh | **NYC Water Board rates** ($ value) | ⚠ (only if the towers are evaporative) · 🆕 rates |
| Air quality (`Q_comb`, local PM2.5) | Combustion displaced; local exposure | **NYCCAS** (NYC DOHMH, `c3uy-2p5r`), pulled in §0 | [SP-111] EJScreen percentiles | 🆕 |
| Health value of NOx/PM avoided | $/t | **EPA Benefits-per-Ton** (PM2.5 precursors) or EPA COBRA | — | 🆕 (stretch) |
| Grid peak relief (`P_peak_avoided`) | MW on Zone J | **NYISO Gold Book 2025** (Zone J winter peak forecast) | — | 🆕 |

## 4. SOCIAL + REGENERATIVE

| Factor | What we need | **Primary dataset** | Cross-check | Status |
|---|---|---|---|---|
| Who benefits (units, residents, fixed income) | Counts | **NYCHA Development Data Book** (NYC Open Data, pulled in §0) | Rebuild FAQ (`fec_faq`) for future units | 🆕 |
| Energy burden | % of income on energy | **DOE LEAD Tool** (tract-level, by income band) | ACS B25040 (heating fuel) | 🆕 (replaces `acs` as the primary) |
| EJ designation | Official flag | **NYS Final Disadvantaged Communities 2023** (data.ny.gov `2e6c-s6fp`) | [SP-111] percentiles (poverty 83rd, PM2.5 92nd, SVI 79th) | ✅ |
| Heat vulnerability | Index 1–5 by neighborhood | **NYC Heat Vulnerability Index** (DOHMH) | [SP-111]: 19 → 69 days above 90 °F by 2050 | 🆕 (cooling co-benefit) |
| Public acceptance | Evidence of opposition and trust | [CenTrio]: 25+ projects cancelled over backlash; [T5]: $150B delayed; FPCJ meeting (NYSERDA, EDC, Verizon) | — | ⚠ qualitative (organizer documents) |
| Local-context fit | Rebuild phasing, design window | **Fulton/Elliott-Chelsea FAQs** + HUD approval documents | — | ✅ |

---

## 5. Remove or demote in `variable_network.html`

| Dataset id | Why |
|---|---|
| `dc_tracker` | Secondary blog estimate; LL84 metered data replaces it |
| `eia_fuel` | Heating oil/propane prices; Site 2 leftover (Manhattan offtakers use steam/gas) |
| `eia_cons` (RECS/CBECS) | National survey; LL84 gives metered data for our exact buildings |
| `noaa_lcd` | Duplicates NSRDB |
| `egrid` | LL97 coefficients (compliance) + Cambium (future) cover it |
| `enefg` (White & Case) | Law-firm summary; the DATA HEAT guide covers EnEfG |
| `cleanheat` | Program page, no numbers; replace with NEEP |
| `resstock` + `comstock` | Merge into the single End-Use Load Profiles entry |

**Result:** 28 → 20 datasets, and every remaining one yields a number.

## 6. Gaps no dataset fills (state them as assumptions on a slide)
1. **DC share of 111 8th electricity, and tenant loop temperatures.** Slider: DC share 50–90%, loop 27–35 °C. Ask Google or the tenants.
2. **Whether tenant towers are evaporative.** Gates the water claim.
3. **Rebuilt-tower heat demand.** Efficient new build ≈ 6–9 MWh/unit (assumption) vs today's measured 16–31 MWh/apt.
4. **Manhattan pipe cost.** Read the PSC 22-M-0429 filings first; otherwise use the DEA catalogue ×1.5–2 urban factor (labeled).
