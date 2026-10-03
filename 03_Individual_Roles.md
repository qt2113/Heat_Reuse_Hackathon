# 03: Individual Playbooks (Members A, B, C), v3 (Site 1)

> **v3:** same three roles and the same model engine as v2, re-pointed to **111 8th Ave → Fulton/Elliott-Chelsea**.
> All values are **ASSUMPTIONS to verify**. They live in `config.yaml` / `offtakers.csv` (see `02_Team_Workflow.md`).
> The worked example in B, Step 2 is an **order-of-magnitude check**, not a result. B replaces the placeholders with sourced values by G1.

| | **A: Model and App** | **B: Economics, Carbon, Data** | **C: Place, Story, Deck** |
|---|---|---|---|
| Owns | Simulation engine, Streamlit app, deploy, README, demo driving | `config.yaml`, LCOH/carbon functions, alternatives comparison (per-building ASHP, steam, gas), optimizer (with A), econ slides | `offtakers.csv` from LL84/PLUTO, map, EJ story, agreement terms, hook, deck, narration |
| Rubric focus | Technology, Execution | Technology (rigor), Theme (value) | Innovation, Theme, Presentation |

---

# 🔧 Member A: Model and App Builder

### Mission
A **narrow, bulletproof** tool. Given the DC tenants' recoverable heat and loop temperature, an offtaker CSV (from LL84/PLUTO) and NYC hourly weather, it simulates 8,760 hours, checks the brief's **5 dimensions**, reports cost, carbon and value per stakeholder, and outputs the **5 heat-export agreement terms**.

### What changes from the Site 2 model (v2)
| v2 (Lansing) | v3 (Chelsea) |
|---|---|
| Liquid-cooled source 45–50 °C | **Condenser water 30–35 °C** via heat exchanger (or heat-recovery chiller) |
| Direct HX to greenhouse + central heat pump | **Ambient loop 15–25 °C** + **heat pumps in each building** (5G) |
| Central heat pump COP from 45 → 70 °C | Building heat-pump COP from loop temperature → 60 °C hot water / 45 °C space heat |
| Ithaca weather | **NYC (Central Park or LaGuardia) TMY** |
| Offtakers: greenhouse, school, town, homes | **Fulton (existing, hot water), rebuild towers by phase, 111 8th offices, Chelsea Market, schools** |
| Backup: electric boiler | **Existing steam/boilers during transition**, electric boilers in new towers |
| Conditions of approval | **Heat-export agreement terms** |

### Model specification
**Hourly demand per offtaker** (same as v2):
```
space heat(h) = annual_SH × max(0, T_base − T_out(h)) / Σ_h max(0, T_base − T_out)
hot water(h)  = annual_DHW / 8760 × daily_shape(h)       # morning + evening peaks
phase flag    = include offtaker only if its phase ≤ selected phase
```

**Dispatch, each hour:**
1. **Source:** DC heat available to the loop = min(tenant recoverable heat, HX capacity). Loop temperature T_loop ≈ 20–25 °C.
2. **Building heat pumps** lift loop heat: COP(h) = η × T_sink / (T_sink − T_loop), η ≈ 0.5, temperatures in K. ~4–5 for 25 → 45 °C space heat; ~3.5–4 for 25 → 60 °C hot water.
   Source heat drawn from the loop = output × (1 − 1/COP).
3. If demand > heat-pump capacity: **discharge storage**.
4. If still short: **backup** (steam/boiler in existing buildings; electric in new towers), sized to the **full peak**.
5. Spare heat-pump capacity charges storage.
6. DC heat not used → the tenants' own cooling towers, as today (**the DC never depends on the network**).

**Energy-balance check (✔ in the app):** source side, heat pumps, demand side and storage must each close (see `variable_network.html` → Integrity).

**KPIs (tiles by stakeholder):**

| Data center (tenants + owner) | Heat users (NYCHA, rebuild, commercial) | Community / place |
|---|---|---|
| DC heat reused (GWh), **ERF**, cooling-tower load avoided, water not evaporated (if towers are evaporative) | Coverage %, LCOH vs alternatives, $/home/yr, backup hours | tCO₂ avoided (net), **on-site combustion displaced (MWh of boiler/steam heat)**, winter grid peak avoided (MW) |

**The 5 dimensions as labels in the app:** temperature (loop + building lifts), capacity (MWth vs peak), timing (winter/summer day), seasonality (monthly), continuity (backup hours, DC-outage toggle).

**Agreement-terms panel (Innovation feature):** generated text, e.g.
> "Term 1: Tenants representing ≥ **X MW** of cooling load install heat-recovery interfaces on condenser loops at ≥ **Y °C**. Term 2: Heat is purchased at the fence at ≤ **$Z/MWh** under a standard contract open to all tenants…"

**City-wide screen (stretch, high value):** a dropdown of other NYC carrier hotels (60 Hudson St, 32 Avenue of the Americas, 375 Pearl St; verify) that reruns the same model with their LL84 neighbors. Even 2 extra sites make "reusable product" credible.

**Optimizer (stretch):** grid search over heat-pump MW × tank MWh × phase → min LCOH with zero unserved heat.

### App layout
```
Sidebar: site selector | phase (0–3) | sliders (DC heat MW, HP MW, tank MWh, pipe m, electricity $/kWh) | "DC outage" toggle
Row 1:  map (111 8th, Fulton, Elliott-Chelsea, Chelsea Market, loop route) | architecture diagram
Row 2:  KPI tiles: Data center | Heat users | Community        [Energy balance ✔]
Row 3:  tabs → Seasonality | Timing | Economics (vs ASHP / steam / gas) | Agreement terms | EJ context (site-pack facts)
```

### A's "done" checklist
- [ ] Simulation runs on NYC weather; energy balance ✔
- [ ] Phase selector 0–3 works
- [ ] Sliders validated (no NaN or negative values)
- [ ] 5 dimensions labeled; KPI tiles for 3 stakeholders
- [ ] Agreement-terms panel
- [ ] Hosted link + README + backup video

---

# 💰 Member B: Economics, Carbon and Data

### Mission
Make the numbers **right, honest and comparable** for Manhattan. Own `config.yaml`.

### Step 1: `config.yaml` values (ASSUMPTIONS, verify every row)
| Parameter | Placeholder | Source to check |
|---|---|---|
| Con Ed electricity, commercial / residential | ~$0.20–0.25 / ~$0.25–0.30 per kWh | Con Ed tariffs, EIA |
| **Con Ed steam** | $/Mlb from the steam tariff → convert to $/MWh (1 Mlb ≈ 0.29 MWh of heat; verify) | Con Ed steam rates |
| Natural gas (commercial) | ~$1.2–1.8/therm | EIA / Con Ed |
| LL97 factors (2024–29) | electricity 0.289 t/MWh; gas 0.0531 t/MMBtu; steam 0.0449 t/MMBtu | NYC LL97 rules |
| LL97 penalty | $268/tCO₂e (**commercial offtakers only**; NYCHA follows Article 321, verify) | NYC DOB |
| Building water-to-water heat pump | ~$1,000–1,500 per kW installed | Vendor |
| Ambient loop pipe, Manhattan | **high uncertainty**: several × suburban; use a slider (e.g., $5–15k per trench-m) | Con Ed pilot filings (PSC 22-M-0429) |
| HX / interconnection at 111 8th | ~$150–300 per kW | OCP / vendor |
| Storage tanks in new basements | per tower; small tanks cost more per m³ | DH literature |
| Central air-source heat pump (the rebuild's likely alternative) | ~$1,500–2,000 per kW; seasonal COP ~2.5–2.8 in NYC | Vendor / NYSERDA |
| Discount rate / life / O&M | 6% / 25 yr / 2% CAPEX per yr | Standard |
| Funding | UTENJA rate base (Con Ed); NYSERDA PON 5614 design study (≤ $750k); federal credit status after 2025 (verify) | — |

### Step 2: Order-of-magnitude check (full build-out, placeholders)
| Offtaker | Phase | Annual heat | Notes |
|---|---|---|---|
| Fulton Houses, existing buildings, hot water (beyond the 372 pilot apartments) | 1 | ~1–3 GWh | NYCHA unit counts (verify) |
| 111 8th Ave offices | 1 | from LL84 (verify) | Zero pipe distance |
| Rebuilt Fulton + Elliott-Chelsea, ~5,500 efficient units × 6–9 MWh | 2 | **~35–50 GWh** | Designed for 45 °C space heat |
| Chelsea Market | 3 | from LL84 (verify) | LL97 applies |

- Peak: NYC space heat runs ~1,500–2,000 full-load hours → the rebuild alone peaks at roughly 15–20 MW.
- Size building heat pumps to ~55% of peak → ~85% of annual energy. At COP ~4 the DC must supply **~6–9 MWth** to the loop. That matches "5–10 MWth from 1–2 tenants' plants".
- **ERF:** DC heat used ≈ 0.75 × ~40 GWh ≈ 30 GWh ÷ (~80 MW × 8,760 h ≈ 700 GWh) ≈ **~4–5%** (assumption; vs ~1.7% at Lansing; Germany's 2026 bar is 10%).
- **What to expect from LCOH:** with Manhattan electricity and pipe costs, the network will likely land **near parity** with a central air-source heat pump, not far below it. **Say so.** The case rests on COP, winter grid peak, no rooftop units, DC cooling/water benefit and air quality, plus rate-base and NYSERDA funding.

### Step 3: Carbon (net, LL97 factors)
Per MWh of heat delivered (placeholders):
| Option | tCO₂/MWh heat |
|---|---|
| Building heat pump on the DC loop (COP ~4) | 0.289 / 4 ≈ **0.07** |
| Central air-source heat pump (COP ~2.8) | ≈ 0.10 |
| Con Ed steam | ≈ 0.15 |
| Gas boiler (90%) | ≈ 0.20 |
- Biggest savings: vs **gas and steam** (Phase 1 existing buildings, Phase 3 commercial). Vs an all-electric rebuild the saving is smaller (~0.03 t/MWh) but real, and the grid factor falls over time.
- Also report: **MWh of on-site combustion displaced** (the EJ metric) and **winter peak MW avoided** (vs air-source heat pumps at cold-weather COP).

### Step 4: Ownership and revenue (one diagram; details to backup slides)
- **Tenants** install heat-recovery interfaces on their condenser loops and **sell heat at the fence** under one **standard contract** (Term 2). Their return: cooling-tower energy and water savings + heat revenue + community license.
- **Con Ed** (UTENJA thermal network) owns and operates the ambient loop, as in the pilot, with costs in the rate base.
- **NYCHA / the rebuild developer** build heat-ready towers: 45 °C space heat, basement plant room, connection point (Term 3).
- **Residents:** tariff ≤ the all-electric alternative; free connection; no rent pass-through (Term 4).
- Backup slides: RACI and risk register (tenant churn, rebuild delay, cost overrun, regulatory delay, stranded asset → source-agnostic loop).

### B's "done" checklist
- [ ] `config.yaml` with NYC sources (steam tariff conversion stated)
- [ ] LCOH + like-for-like comparison (central ASHP, steam, gas)
- [ ] Net carbon + combustion displaced + winter peak avoided
- [ ] ERF stated with its assumptions
- [ ] Ownership diagram (+ RACI/risk as backup slides)
- [ ] Sensitivity: electricity price, pipe $/m, DC heat MW, phase

---

# 🗺️ Member C: Place, Story and Deck

### Mission
Own the **Chelsea case**, the EJ evidence, the agreement terms and the pitch.

### Step 1: `offtakers.csv` from **NYC LL84 + PLUTO**
Columns: `name, lat, lon, type, tier, annual_sh_mwh, annual_dhw_mwh, peak_kw, supply_T, distance_m, owner, equity_flag, phase, source`.
- Rows: Fulton Houses (existing, hot water), rebuild towers (one row per phase), Elliott-Chelsea, 111 8th offices, Chelsea Market, PS 11 / nearby schools, any pool or rec center within ~3 blocks.
- Use LL84 for actual fuel and steam use where available; otherwise floor area × intensity. Label every estimate.
- Find which building is the pilot's heat source (PSC Case 22-M-0429).

### Step 2: Offtaker scoring (one slide or an app tab)
| Criterion | Weight |
|---|---|
| Distance (blocks) | 20% |
| Equity / public housing | 20% |
| Year-round load (hot water) | 15% |
| Timing (rebuild design window) | 15% |
| Demand size | 15% |
| Single owner / contract ease | 10% |
| Temperature fit | 5% |

### Step 3: The 5 heat-export agreement terms (model language, not legally binding)
1. **Readiness:** tenants representing ≥ X MW install heat-recovery interfaces on condenser loops at ≥ Y °C.
2. **Standard heat contract:** any tenant can sell heat at the fence at ≤ $Z/MWh (Stockholm Data Parks model); the owner of 111 8th hosts the interconnection.
3. **Design-window offtake:** each rebuild phase is designed for 45 °C space heat, with a basement plant room and a loop connection.
4. **Affordability:** NYCHA residents' heat cost ≤ the all-electric alternative; free connection; no rent pass-through.
5. **Continuity + transparency:** backup covers the full peak; public dashboard of heat delivered, CO₂ and combustion displaced.

### Step 4: Story and deck
- **Hook (30 s):** "111 8th Avenue carries much of Manhattan's internet traffic, and it throws its heat into the sky. One block west, the organizers' own data puts residents in the 83rd percentile for poverty and the 92nd for PM2.5, and their homes are about to be rebuilt. Let's design the rebuild to run on that heat."
- **Credit Con Ed's pilot early** (Phase 0). Then show what's new.
- **Regenerative arc (HDR):** the internet's backbone becomes the neighborhood's heat source; buildings become source and sink.
- **Neutral on the rebuild itself:** "whatever is built should be heat-ready".
- The demo sits in the middle of the pitch. Takeaway titles; colors: DC heat orange, loop teal, backup grey.

### C's "done" checklist
- [ ] `offtakers.csv` with LL84/PLUTO sources
- [ ] Map + scoring + rejected options
- [ ] 5 agreement terms
- [ ] EJ slide from the site pack (cite [SP-111])
- [ ] Hook + regenerative arc
- [ ] Deck (8–10 slides) with the demo slot; backup slides
- [ ] Rehearsal timing
