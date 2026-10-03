# Project Modeling Overview: Site 1, 111 8th Avenue

**In one sentence:** we take measured data about the data center and its neighbours, simulate the heat network hour by hour, turn the results into costs, carbon and community value, and compare four options against today's heating.

```
Data (data/)  →  Model A: hourly heat  →  Model B: cost, carbon, value  →  Model C: rules + scoring  →  Website (React + D3)
```

The details live in the CSVs; this page only explains the logic:
- `data/data_dictionary.csv`: every indicator and its formula
- `data/dataset_inventory.csv`: every source
- `data/reference/assumptions_scenarios.csv`: every Low/Base/High input
- `variable_network.html`: the full variable graph

---

## 1. What data we have (19 sources, all in `data/`)

| Group | Main files | What it tells us |
|---|---|---|
| **Heat supply** | `source_111_8th_annual.csv` | 111 8th Ave uses 131–148 GWh of electricity a year, about **15–17 MW** on average. That is the ceiling on usable heat |
| **Heat demand** | `offtaker_candidates_ll84.csv`, `nycha_chelsea_developments.csv` | Measured heating fuel of 895 nearby buildings. Fulton 29 GWh (steam), Elliott-Chelsea 16, Chelsea Market 12. Apartments and residents |
| **Weather & map** | `weather_tmyx_hourly.csv`, `weather_design_conditions.csv`, `pluto_lots_1km.csv` | Hourly temperature for a typical year; coldest design hour −10.5 °C; locations and distances |
| **Equipment** | `equipment_dea_heat.csv`, `equipment_eia_building_scale.csv` | Heat-pump cost, efficiency and lifetime |
| **Local pilot** | `chelsea_uten_benchmarks.csv` | Con Ed's Chelsea pilot (85 10th Ave → 291 Fulton apartments). Real Manhattan pipe cost **$29k per metre**, heat price $26/MMBtu, steam cost $140/MWh |
| **Prices** | `energy_prices_ny_summary.csv`, `utility_avg_prices_2024.csv` | Electricity $182–282/MWh; gas and steam prices |
| **Environment** | `ll97_emission_coefficients.csv`, `ap42_natural_gas_boilers.csv`, `air_quality_latest.csv` | Carbon per MWh by fuel; boiler NOx; local air quality |
| **Community** | `dac_tracts_1km.csv`, `fec_rebuild_facts.csv` | The site and Fulton sit in a state-designated disadvantaged tract. The rebuild adds up to 3,454 new homes (first move-ins end of 2028) |

**Still unknown**, so each uses a Low/Base/High scenario:
- the data center's share of the building's electricity (0.5 / 0.7 / 0.9);
- the tenants' cooling-loop temperature;
- the heat demand of a rebuilt apartment;
- the cooling-tower type (until confirmed, we make no water-saving claim).

---

## 2. What we measure: 16 indicators + 7 rules

| Dimension | Indicator (ID) | How it's calculated (simple form) |
|---|---|---|
| **Technical** | T1 Recoverable heat | building electricity × DC share × heat fraction |
| | T2 Heat-pump efficiency (SCOP) | heat out ÷ electricity in, over the year |
| | T4 Demand coverage | % of hourly demand met by recovered heat (not backup) |
| | T7 Pipe route length | distance × 1.3 street factor |
| **Economic** | C1 Capital cost | equipment + pipe + building work, per kW |
| | C2 Cost of heat (LCOH) | (yearly capital + running costs) ÷ heat delivered |
| | C3 Saving vs today | 1 − network cost ÷ current steam/gas cost |
| **Environmental** | N1 Energy Reuse Factor | heat reused ÷ data-center IT energy |
| | N2 CO₂ avoided | old fuel × LL97 factor − new electricity × LL97 factor |
| | N4 Local combustion avoided | gas no longer burned next to the block (+ NOx) |
| | N6 Winter grid peak | peak electricity vs air-source heat pumps at −10.5 °C (can be negative) |
| **Social** | S1 Low-income homes served | apartments connected in disadvantaged tracts |
| | S3 Environmental-justice exposure | DAC percentile; local PM2.5 vs city (9.5 vs 6.3) |
| | S5 Acceptance & governance | 0–4 rubric from documented evidence |
| | S6 Fit with the rebuild | 0–2 rubric: are new buildings heat-ready at move-in? |
| | S7 Value to the data center | heat sales − extra electricity and upkeep |

**Not scored, to avoid counting the same thing twice:** payback, bill $, carbon intensity, 1/SCOP and similar. They are shown on screen only.

**Pass/fail rules.** A design that breaks any of these is reported as infeasible and never scored:

| Rule | Requirement |
|---|---|
| H1 | The data center's cooling never depends on the network (its towers stay) |
| H2 | Backup heat covers the coldest hour; no home goes without heat |
| H3 | We never use more heat than the data center gives |
| H4 | Hot water ≥ 60 °C |
| H5 | The energy balance adds up every hour |
| H6 | NYCHA residents never pay more than today. This is the hard one: the pilot only saves Fulton about $1k a year |
| H7 | No low-temperature heat into old steam radiators unless they're retrofitted |

---

## 3. How the models work

| Model | Input | What it does | Output |
|---|---|---|---|
| **A: Heat simulation** | Weather, demand, DC heat, equipment, scenario | For each of 8,760 hours: data-center heat → heat pumps → storage → backup. Simple rules, no optimiser. Sizes are picked by trying a few options | Hourly heat, electricity, backup use, peaks |
| **B: Accounting** | Model A results, costs, prices, emission factors | Adds up capital cost, running cost, cost of heat, CO₂, NOx and money for each stakeholder | One row of indicators per scenario |
| **C: Decision** | Model B indicators | 1) check rules H1–H7; 2) score each indicator from **0 = today** to **1 = a documented target**; 3) weighted average (default 25% per dimension); 4) test robustness | Composite score + sensitivity |

**Check against reality:** we rerun the Con Ed pilot through Model A. It should give the pilot's own numbers (about 1.8 units of heat per unit of electricity, 1.5 GWh/yr of extra electricity).

**Two separate evaluations:**
- **Which buildings to connect** (offtaker screening): rank the 895 buildings by demand, distance, temperature needs, fuel and equity.
- **Which system design is best** (system evaluation): compare scenarios with Models A → B → C.

**No machine learning is needed.** We have no past outcomes to learn from and only one site, and the physics and accounting formulas are already known. Transparent formulas are easier to defend to judges.

**Sensitivity:**
- Set each unknown to its Low and High value (tornado chart).
- Shuffle the weights 1,000 times and report how often each design comes out on top.

---

## 4. Scenarios (same models, different buildings connected)

| Scenario | What's connected | Heating fuel today |
|---|---|---|
| **S0 Today** | Nothing: steam and gas boilers as now; data-center heat goes to the cooling towers | — |
| **S1 Self-use** | 111 8th Ave heats its own building | 11.5 GWh |
| **S2 Commercial block** | S1 + Chelsea Market, two hotels, a school, 61 9th Ave (all within 300 m) | ≈ 50 GWh |
| **S3 Community network** | S1 + Fulton (joining Con Ed's pilot loop) + Elliott-Chelsea + NYCHA Chelsea, then the rebuilt towers | ≈ 67 GWh, growing with the rebuild |

**Composite score:** the share of the way from today's system to the targets. For example, "S3 gets 0.6 of the way and beats today in 90% of weight choices". It is always shown next to the raw numbers and the rule checks.

---

## 5. Website (React + TypeScript + D3; Python stays the engine)

Python writes CSV/JSON files into `outputs/` and the website only reads them, so the demo works offline.

| Page | Question it answers | Main visuals | Files it reads |
|---|---|---|---|
| **1. Where** | Which buildings, and why here? | Map with buildings sized by heat demand, disadvantaged tracts shaded, distance rings; ranking bar chart | `offtaker_scores.csv` |
| **2. How** | Does the heat really match, every hour and season? | Energy-flow (Sankey) diagram; hourly supply vs demand for a winter, spring and summer week; monthly bars; rule pass/fail badges | `hourly_<S>.json`, `sankey_<S>.json`, `scenarios.json` |
| **3. Why** | Is it worth it, and for whom? | Indicator cards vs today; four-dimension radar; composite bar with a weight slider; value split (data center / residents / community); tornado and robustness charts | `kpis.csv`, `scores.csv`, `sensitivity.csv` |

`variable_network.html` becomes a "How we calculated this" panel on page 3.

---

## 6. Next steps
1. Build `features.py` and `scenarios.yaml`, including removing duplicate buildings in the LL84 list.
2. Build Model A (and check it against the pilot), then Model B, then Model C.
3. Export to `outputs/`, then build the three pages.

**Team decisions needed first:**
- the base data-center share and heat price;
- the indicator targets;
- the default weights;
- whether S3 also includes the commercial buildings.
