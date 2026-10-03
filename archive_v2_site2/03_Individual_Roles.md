# 03: Individual Playbooks (Members A, B, C), v2

> **v2:** roles reorganized around the **working tool**. The worked example is corrected:
> - realistic full-load hours
> - greenhouse served **directly** through a heat exchanger
> - backup sized to the full peak
> - like-for-like ASHP comparison
>
> All values are **ASSUMPTIONS to verify**. They live in `config.yaml` / `offtakers.csv` (see `02_Team_Workflow.md`).

| | **A: Model and App** | **B: Economics, Carbon, Data** | **C: Place, Story, Deck** |
|---|---|---|---|
| Owns | Simulation engine, Streamlit app, deploy, README, demo driving | `config.yaml`, LCOH/carbon functions, ASHP counterfactual, optimizer (with A), econ slides | `offtakers.csv`, map, conditions-of-approval text, regenerative framing, hook, deck, narration |
| Rubric focus | Technology, Execution | Technology (rigor), Theme (value) | Innovation, Theme, Presentation |
| Best fit | Strongest Python person | Numbers / econ / policy person | Design / planning / communication person |

---

# 🔧 Member A: Model and App Builder

### Mission
Build a **narrow, bulletproof** tool. Given the DC's MW and source temperature, an offtaker CSV and a weather file, it simulates 8,760 hours and shows whether supply meets demand on **temperature, capacity, timing, seasonality and continuity**. It also reports cost, carbon and value for each stakeholder, and outputs **conditions of approval**.

### Timeline
| Time | Task | Gate |
|---|---|---|
| Night before | Environment + repo + (if allowed) skeleton | n/a |
| 09:30–10:30 | Weather → hourly degree-hours; agree CSV/YAML columns | G0 |
| 10:30–13:00 | Simulation core + KPIs + **energy-balance check** | **G1: MVP runs** |
| 13:15–15:30 | Streamlit app: map, sliders, KPI tiles, charts, conditions panel | G2 |
| 15:30–16:00 | Input validation; preloaded Lansing scenario | **G3: freeze** |
| 16:00–17:30 | Bug fixes, deploy to Streamlit Cloud, README + screenshots | G4 |
| 17:30–18:15 | Record backup video | n/a |
| 18:15+ | Drive the demo in rehearsals | n/a |

### Model specification (keep it this simple)
**Inputs:**
- `weather.csv` (hourly outdoor temperature)
- `offtakers.csv`
- `config.yaml`
- slider values: heat pump MW, tank MWh, pipe km, electricity $/kWh, "DC funds the heat recovery station" on/off, which offtakers are included

**Hourly demand per offtaker:**
```
space heat(h) = annual_SH × max(0, T_base − T_out(h)) / Σ_h max(0, T_base − T_out)   # T_base ≈ 15.5–18 °C
DHW(h)        = annual_DHW / 8760 × daily_shape(h)      # optional morning/evening peaks
greenhouse(h) = annual_GH × weight(h), weighted to cold hours + nights (winter-weighted, NOT flat)
```

**Cascade dispatch, each hour:**
1. **Low-temperature tier (greenhouse, 30–45 °C):** served **directly** through a heat exchanger from the DC loop (45–50 °C). Electricity = pumping only (~2–4% of the heat).
2. **High-temperature tier (school DHW/heating 60–70 °C, homes 45–55 °C):** served by the heat pump, capped at HP_MW.
   COP(h) = η × T_sink / (T_sink − T_source), with η ≈ 0.5 and temperatures in K. This gives ~5 for 45→70 °C and ~7 for 45→50 °C.
3. If demand > heat pump: **discharge storage** (state of charge ≥ 0).
4. If still short: **backup electric boiler** (must be sized to the **full peak**: flag it red if it can't cover the peak).
5. If the heat pump has spare capacity: charge storage (state of charge ≤ tank size).
6. DC heat not used → rejected through the DC's own dry coolers (**the DC never depends on the network**).

**Energy-balance check (show a ✔ in the app):**
```
Σ delivered heat = Σ direct-HX heat + Σ HP heat (= DC heat to HP + HP electricity) + Σ backup + Δstorage − losses
assert |imbalance| < 0.5%   → green tick
```

**KPIs (tiles grouped by stakeholder):**

| Data center | Heat users | Community / place |
|---|---|---|
| DC heat reused (GWh), **ERF**, cooling load avoided (GWh) | Coverage % by DC heat, LCOH vs like-for-like ASHP and propane, $/home/yr | tCO₂ avoided (net), homes-equivalent, public buildings served, backup hours |

**The brief's 5 dimensions as explicit labels in the app:**
- **Temperature:** the cascade diagram with tier temperatures
- **Capacity:** heat pump MW vs. peak
- **Timing:** typical winter and summer day, hourly
- **Seasonality:** monthly stacked chart
- **Continuity:** hours on backup; storage hours; DC-outage scenario toggle

**Conditions-of-approval panel (the Innovation feature):** generated text from the results, for example:
> "Condition 1: The applicant shall construct a heat recovery station of ≥ **X MW** capacity at a supply temperature ≥ **Y °C** before Phase I occupancy, …"

**Stretch: grid-search optimizer.** Loop over HP MW × tank MWh × offtaker subsets (a few hundred runs) → pick the minimum LCOH with backup hours ≤ target. Show the result as "Optimized" vs "Manual". It is honest to call it an optimizer.

### App layout (Streamlit)
```
Sidebar: scenario preset | sliders | offtaker checkboxes | "DC outage" toggle
Row 1:  map (DC, offtakers, pipe route)  |  cascade/architecture diagram
Row 2:  KPI tiles: Data center | Heat users | Community        [Energy balance ✔]
Row 3:  tabs → Seasonality (monthly) | Timing (winter/summer day) | Economics (LCOH vs ASHP vs propane) | Conditions of approval
```

### Skeleton (only if pre-written code is allowed)
```python
import numpy as np, pandas as pd, yaml
cfg = yaml.safe_load(open("config.yaml")); W = pd.read_csv("data/weather.csv")  # column T_out (°C), 8760 rows
off = pd.read_csv("data/offtakers.csv")
def hourly_demand(row, T):
    dh = np.clip(cfg["T_base"] - T, 0, None)
    sh = row.annual_sh_mwh * dh / dh.sum()
    return sh + row.annual_dhw_mwh / 8760
def cop(Tsrc, Tsink, eta=0.5):
    Ts, Tk = Tsrc + 273.15, Tsink + 273.15
    return eta * Tk / (Tk - Ts)
def simulate(hp_mw, tank_mwh, include):
    T = W.T_out.values; soc = 0; out = []
    gh = sum(hourly_demand(r, T) for r in off[include & (off.tier == "low")].itertuples())
    hi = sum(hourly_demand(r, T) for r in off[include & (off.tier == "high")].itertuples())
    c = cop(cfg["T_source"], cfg["T_high"])
    for h in range(8760):
        hp = min(hi[h], hp_mw); short = hi[h] - hp
        dis = min(short, soc); soc -= dis; short -= dis
        ch = min(hp_mw - hp, tank_mwh - soc); soc += ch
        out.append((gh[h], hp, (hp + ch) / c, dis, short, ch))
    return pd.DataFrame(out, columns=["direct", "hp", "hp_elec", "storage", "backup", "charge"])
```
*(1-hour steps, so MW in an hour = MWh. Add losses and pumping later.)*

### A's "done" checklist
- [ ] Simulation runs; energy balance ✔
- [ ] App runs offline with the preloaded Lansing scenario
- [ ] Sliders validated (no NaN or negative values)
- [ ] 5 dimensions labeled with the brief's words
- [ ] KPI tiles for 3 stakeholders
- [ ] Conditions-of-approval panel
- [ ] Hosted link + README + backup video
- [ ] Demo script rehearsed (≤ 2 min)

---

# 💰 Member B: Economics, Carbon and Data

### Mission
Make the numbers **right, honest and comparable**. Own `config.yaml`. Write the LCOH, carbon and comparison functions for A. From 14:30, help with the optimizer.

### Step 1: `config.yaml` values (ASSUMPTIONS, verify)
| Parameter | Value | Source to check |
|---|---|---|
| Electricity, upstate commercial / residential | ~$0.09 / ~$0.18–0.20 per kWh | EIA |
| Propane / heating oil / natural gas | ~$3/gal / ~$4/gal / ~$1.5/therm | EIA |
| Discount rate / lifetime | 6% / 25 yr (network), 15 yr (ASHP) | Standard |
| Heat pump (large, installed) | ~$1,000 per kW_th of **installed** capacity (N+1 means installed > delivered) | Vendor/IEA |
| Heat recovery station | ~$200/kW | OCP/vendor |
| Pipe (suburban, pre-insulated pair) | ~$2,000 per trench-m. **Slider: 4–10 km** | DH literature |
| Building substation / HIU | ~$5–8k per home; ~$100k+ per large building | Vendor |
| Storage tank (small, ~600 m³) | ~$1M total (small tanks cost more per m³ than large ones) | DH literature |
| Electric backup boiler | ~$150/kW, sized to the **full peak** | Vendor |
| O&M | 2% of CAPEX/yr | Standard |
| Cold-climate ASHP retrofit | ~$15–25k per home, seasonal COP ~2.5 | NYSERDA / contractor data |
| Federal credit | 30%? **Check the post-2025 status** | IRS/DOE |
| Emission factors | Gas 53.1, propane 62.9, oil 74.0 kgCO₂/MMBtu; upstate grid ~0.1 t/MWh (verify eGRID NYUP) | EPA |

### Step 2: Corrected worked example (Site 2, full build-out)
**Load mix:**

| Offtaker | Tier | Annual heat | Peak |
|---|---|---|---|
| Greenhouse, 4 ha (tenant recruited under the community benefit agreement) | Low: **direct HX** | ~16 GWh (~14 GWh from DC, rest backup) | ~8 MW |
| School campus | High: heat pump | ~4 GWh | ~2.5 MW |
| Town facilities | High: heat pump | ~2 GWh | ~1 MW |
| ~400 new low-temperature homes (**Phase 2**, gas-moratorium area) | High: heat pump | ~6 GWh | ~2 MW (diversified) |
| **Total** | | **~28 GWh** | **~12.5–13 MW coincident** |

**Sizing:**
- Heat pump: 3 MW delivered / **4 MW installed** (N+1), ~10 GWh at COP 5 → **2 GWh electricity**
- Direct HX: ~14 GWh with pumping only (~0.5 GWh electricity)
- Backup: ~4.0 GWh (= 28 − 10 − 14), boiler sized to the **full ~13 MW peak**
- ⚠️ All numbers here are **full build-out (Phase 1 + 2)**. **Phase 1 alone** (no homes) ≈ 22 GWh, with the heat pump serving only the school + town. The app's phase toggle must show that LCOH separately.
- Pipe: ~4 km (optimistic; make it a slider)

**CAPEX:**

| Item | Cost |
|---|---|
| Heat recovery station | $1.2M |
| Heat pumps (4 MW) | $4.0M |
| Pipe (4 km) | $8.0M |
| Substations | $1.5M |
| Storage | $1.0M |
| Backup boiler (13 MW) | $2.0M |
| Subtotal | $17.7M |
| **Total (+20%)** | **≈ $21M** |

**LCOH:**
```
Annualized CAPEX = 21M × 0.078 ≈ $1.66M → $59/MWh
Electricity      = (2 + 0.5 + 4.0) GWh × $0.09 ≈ $0.59M → $21/MWh
O&M              = 2% × 21M ≈ $0.42M → $15/MWh
LCOH ≈ $95/MWh    (≈ $77 with a 30% capital credit; lower again if the DC funds the heat recovery station)
```
**Like-for-like comparison (cost per MWh delivered, including equipment):**

| Option | ~$/MWh | Notes |
|---|---|---|
| **DC heat network** | **~$95 (~$77 with credit)** | Includes all CAPEX + HIU |
| Cold-climate ASHP per home | **~$160–230** | ~$100–170 capex share + ~$60–80 electricity |
| Propane boiler | ~$125 fuel + boiler capex | State "fuel only" if you omit capex |
| Natural gas | ~$55 fuel | **Not available**: moratorium |

→ **Headline:** "Once equipment cost is counted, the network beats per-home heat pumps and propane. It depends on three things, all shown live in the app: the DC funds the heat recovery station, a greenhouse anchor, and pipe km."

**ERF reality check (important honesty point):**
- DC heat actually used ≈ 14 + 10 × (1 − 1/5) ≈ **22 GWh/yr**.
- A 150 MW campus (**facility power, assumed at full load all year**: an upper bound; state this) rejects ~**1,300 GWh/yr**, so ERF ≈ **1.7%**.
- Germany's EnEfG would require 10–20% for a new DC. **Lansing's local demand can't absorb that.**
- Reaching 10% (~130 GWh) would need heat-intensive **co-located** users: a greenhouse park (~30 ha), aquaculture, timber/food drying.
- ⚠️ ~30 ha is huge by US standards. AppHarvest's ~24 ha Kentucky greenhouse went bankrupt in 2023 (verify). So co-location must be an obligation to **offer** heat and land at a capped price, **not** a promise that growers will come.
- Check whether Germany's EnEfG exempts DCs that have no offtaker. If it does, that supports our argument that flat mandates need local flexibility.
- This feeds directly into the conditions design (file 04).

### Step 3: Carbon (net)
```
tCO₂ avoided = Σ heat delivered by fuel displaced × EF_fuel  −  (HP + pumping + backup electricity) × EF_grid
```
- Baseline for homes/school: a propane/oil/electric mix from ACS heating-fuel data (C provides it).
- Greenhouse baseline: gas (if available) or propane.
- Upstate grid ~0.1 t/MWh, so the net savings are large. Show the result per stakeholder.

### Step 4: Ownership and revenue (one diagram; details go to backup slides)
- **The DC funds and owns the heat recovery station** inside its fence, as a **condition of approval** and community benefit agreement item. It provides heat at zero or low cost at the fence.
- **NYSEG (under the thermal-network law, UTENJA) or a town/co-op energy district** owns the heat pump plant, network and backup.
- **Tariff:** guaranteed ≤ X% of the like-for-like ASHP/propane cost. Free connection for the school, public buildings and low-income homes.
- **Greenhouse:** industrial tariff with a 15–20-yr contract.
- **Backup slides:** RACI table and risk register (DC delay/cancel, load drop, cost overrun, opposition, regulatory delay, stranded assets → **source-agnostic network**).

### Step 5: Sensitivity + optimizer (from 14:30)
- Run Low/Base/High for COP, electricity price, pipe km, DC funding of the heat recovery station, and the greenhouse on/off. Show the tornado or the 3 scenarios.
- Help A write the grid-search loop and the LCOH objective.

### B's "done" checklist
- [ ] `config.yaml` complete with sources
- [ ] LCOH + like-for-like comparison function
- [ ] Carbon function (net)
- [ ] ERF reality check stated
- [ ] Ownership diagram (+ RACI/risk as backup slides)
- [ ] Sensitivity
- [ ] Assumptions/sources appendix

---

# 🗺️ Member C: Place, Story and Deck

### Mission
Make it **novel, local and engaging**: own the Lansing case, the conditions-of-approval idea, the regenerative framing and the pitch.

### Step 1: `offtakers.csv` (by 10:30)
Columns: `name, lat, lon, type, tier(low/high), annual_sh_mwh, annual_dhw_mwh, peak_kw, supply_T, distance_km, owner, equity_flag, phase, source`.
- **Rows:**
  - greenhouse (hypothetical tenant next to the DC)
  - Lansing Central School campus (**measure the distance**)
  - town hall / library / community center
  - moratorium-area housing (Phase 2; co-locate near the site if possible)
  - nearest hamlet clusters
- **Estimate demand** from floor area × intensity (CBECS/RECS) or school data. Label each estimate.
- **ACS table B25040** (house heating fuel) for the Lansing tracts → % propane/oil/electric. These households gain most.

### Step 2: Offtaker scoring (one slide, or a tab in the app)
| Criterion | Weight |
|---|---|
| Demand size | 20% |
| Temperature fit (low = better) | 20% |
| Distance | 15% |
| Load factor | 15% |
| Single owner / contract ease | 10% |
| Equity / public use | 15% |
| Timing (new build) | 5% |

Show the rejected options and why (e.g., Cornell: too far for Phase 1).

### Step 3: Conditions of approval (the Innovation core)
Write 5 short model conditions the **Town of Lansing Planning Board could adopt** (phrase it as "model language", **not** "legally binding"):
1. **Heat-recovery readiness:** liquid-cooled design with a heat-recovery interface ≥ X MW at ≥ Y °C before Phase I occupancy.
2. **Heat recovery station funded by the applicant** as part of the community benefit agreement; heat supplied at the fence at ≤ $Z/MWh for 20 years.
3. **Phased reuse obligation:** ERF targets by year, linked to the offtakers that connect; obligation to host heat-intensive co-located users (greenhouse/agriculture park).
4. **Affordability guarantee:** residential tariff ≤ X% of the like-for-like ASHP/propane cost; free connection for public and low-income buildings.
5. **Continuity and transparency:** backup sized to the full peak by the network operator; public dashboard of heat delivered, ERF and tCO₂.

Stay **neutral on the DC itself**: "*If* approved, these are the conditions."

### Step 4: Story and deck
- **Hook (30 s):** "Lansing can't connect a new home to gas, and a 150 MW data center wants to move into its old coal plant. Every year it will throw away the heat-equivalent of ~65,000 homes, more than 10× every household in Lansing, unless the town makes heat reuse a condition of approval."
  - Basis: ~1,300 GWh ÷ ~20 MWh/home ≈ 65,000. Lansing has ~4–5k households (verify with ACS). Always say "**heat-equivalent**": it's low-grade heat, not a claim that it could heat 65,000 homes.
- **Regenerative arc** (HDR): coal plant → data center → **clean heat commons**. The place is better off with the project than without it.
- **Decide which slides the live demo replaces.** The demo sits in the middle of the pitch, not at the end.
- Takeaway slide titles; consistent colors (DC heat = orange, heat pump = red, backup = grey, direct HX = yellow).
- **Stakeholder sensitivity:**
  - acknowledge residents' concerns (noise, rates, lake, moratorium vote)
  - heat pumps go indoors
  - closed loop, no lake water
  - the community fund becomes tangible heat

### C's "done" checklist
- [ ] `offtakers.csv` with sources
- [ ] Map + scoring + rejected options
- [ ] 5 model conditions
- [ ] Hook + regenerative arc
- [ ] Deck (8–10 slides) with the demo slot
- [ ] Backup slides: RACI, risk, Site 1 fallback
- [ ] Rehearsal timing
