# 01: Background Briefing

> Goal: everyone on the team can explain the problem, the vocabulary, both sites and the policy context in plain words, and knows where to find data.
> Format: each item says **what it is**, then **why it matters for us (function/meaning)**.

---

## 1. The challenge in plain words

**What they are asking:** Design a system that takes heat a data center would otherwise throw away and turns it into something useful for the neighbors: space heating, hot water, community facilities and so on. Then **defend** it with numbers.

**What a winning proposal contains** (straight from the brief):

| Required element | Plain meaning |
|---|---|
| Network architecture | A diagram showing where heat is captured, upgraded, piped and used |
| Heat source + most suitable users | Which part of the data center gives heat, and **who** receives it, with reasons |
| Required infrastructure | Heat exchangers, heat pumps, pipes, storage tanks, backup boilers and so on |
| Operating approach | How it runs day and night, summer and winter, and what happens when something breaks |
| Environmental + community impact | CO₂ saved, energy saved, and who benefits and how much |
| Supply–demand match on **temperature, capacity, timing, seasonality, continuity** | The core technical test, covered in section 2 |
| Cooling reliability + heat continuity protected | The data center never overheats because of us, and homes never go cold because of the data center |
| Measurable value for DC, users, community | $ and tCO₂ figures for each stakeholder |
| Costs, risks, ownership shared | Who pays, who owns, who carries which risk |

**Scoring lenses** (the four boxes in the brief), which make a good slide-checklist:

- **Technical:** capture point, temperature, capacity; heat pumps; reliability, timing, continuity
- **Economic + Delivery:** CAPEX/OPEX; revenue/connection model; ownership, risks, responsibilities
- **Environmental:** carbon reduction; energy efficiency; resource optimization
- **Social + Regenerative:** measurable stakeholder value; equity and public acceptance; local-context fit

**"Regenerative design"** (HDR framework): going beyond "less harm" (sustainable) toward "net positive" (the project leaves the place better than before). For us this means the data center becomes a **community asset** and not just a neighbor that takes power, water and land.

---

## 2. Core concepts glossary

### 2.1 Waste heat and its "grade"
- **What:** Almost 100% of the electricity a server uses turns into heat. The **grade** of that heat is its temperature: higher means more useful.
- **Why it matters:** The temperature you capture at determines how much upgrading (heat-pump electricity) you need. This is the first number on your technical slide.

### 2.2 Where the heat comes from: cooling types and typical temperatures

| Cooling type | Typical heat-recovery temperature | Notes |
|---|---|---|
| Air cooling (CRAC/CRAH, hot aisle) | Exhaust air ~25–35 °C. **Chilled-water return ~12–18 °C** (up to ~20–24 °C in modern elevated chilled-water designs). **Condenser water ~30–35 °C** (the usual recovery point, often via a heat-recovery chiller) | Most common in older and colocation sites; low grade. Don't mix up the chilled-water and condenser loops: technical judges will notice |
| Rear-door heat exchanger | up to ~37 °C | Retrofit option |
| Direct-to-chip liquid cooling (cold plate) | ~40–65 °C | Standard for new AI/HPC racks; much better for reuse |
| Immersion cooling | ~50–65 °C | Highest grade |

*Source: Open Compute Project, Heat Reuse 101 and Reference Designs for Heat Reuse (2023/2025).*

- **Why it matters:**
  - **Site 1** (existing multi-tenant carrier hotel) is probably mostly **air-cooled**, so the heat is low grade (~25–35 °C). You will need heat pumps, or an ambient loop where each building upgrades the heat itself.
  - **Site 2** (new campus) can be **designed for liquid cooling from day 1**, giving 45–60 °C heat. That can feed low-temperature heating almost directly, or a heat pump with a very high COP. ⚠️ TeraWulf's history is bitcoin mining; Lake Hawkeye is marketed for HPC/AI, but the tenants and the cooling design are not public. Present liquid cooling as a **"design condition we require"**, not as a fact.

### 2.3 Capture point
- **What:** The physical spot where you take the heat: the chilled-water return, the condenser-water loop, the CDU (coolant distribution unit) secondary loop, or the exhaust air.
- **Why:** It sets both the temperature and the **interface risk**. Tapping the condenser-water loop through a heat exchanger keeps the DC's loop hydraulically separate, which is the safest option.

### 2.4 Heat pump and COP
- **What:** A heat pump uses electricity to "lift" heat from a lower to a higher temperature. **COP** (coefficient of performance) = heat delivered ÷ electricity used.
- **Rule of thumb:** a smaller lift gives a higher COP.
  - 30 °C → 70 °C (lift of 40 K): COP ≈ 3
  - 45 °C → 70 °C (lift of 25 K): COP ≈ 4.5–5
  - 30 °C → 55 °C: COP ≈ 4–5
- **Why:** COP drives OPEX (the electricity bill) and the CO₂ math. Heat delivered = source heat × COP/(COP−1).
- **Bonus effect:** a heat pump that pulls heat out of the DC loop is also **doing cooling**, so the DC can run its chillers, cooling towers and dry coolers less. That is value to the DC: lower cooling power. **Water savings apply only where the DC uses evaporative cooling towers** (possibly Site 1). Site 2 uses a closed glycol loop with dry coolers, so **don't claim water savings there**.

### 2.4b The real competitor: an air-source heat pump in each building
- **What:** The alternative to a heat network is not only propane or gas. It is also a **cold-climate air-source heat pump (ASHP) in every building**, with no network at all.
- **Why it matters:** A Grundfos/HDR judge will ask "why not just ASHPs?". Compare them **like for like (including capex)**:
  - An ASHP retrofit costs ~$15–25k per home and lasts ~15 years. That is ~$1.5–2.6k/yr, or **+$100–170 per MWh** on 15 MWh/yr, on top of electricity at a seasonal COP of ~2.5 (~$60–80/MWh). **All-in: ~$160–230/MWh (verify install costs).**
  - A network home needs only a substation/heat interface unit (~$5–8k).
  - The network also wins on: grid peak relief on the coldest days (the ASHP's COP falls toward ~1.5–2 at −15 °C, while the DC source stays at a constant 45 °C); no panel or service upgrades; and the DC gets free cooling.

### 2.5 District heating generations
| Generation | Supply temperature | Fit |
|---|---|---|
| 3G (classic hot water) | 80–120 °C | Old buildings and steam/radiator systems; needs a big lift |
| **4G (low temperature)** | 50–70 °C, return ~25 °C | New or retrofitted buildings; good match for liquid-cooled DC heat plus a modest heat pump |
| **5G (ambient loop)** | 10–30 °C | Each building has its own small heat pump; the loop can share **both heating and cooling**. Good for air-cooled DC heat and mixed-use urban blocks |

- **Why:** Choosing the network generation is your architecture decision. Low-grade source + existing buildings → 5G ambient loop. High-grade source + new or low-temperature buildings → 4G.

### 2.6 Offtaker (heat user)
- **What:** Whoever buys or receives the heat: housing, schools, hospitals, pools, greenhouses, laundries, industry.
- **Why:** The "most suitable" offtaker has (a) **steady, year-round demand** (hot water, pools, greenhouses, hospitals), (b) a **compatible temperature**, (c) **short distance** (pipes are expensive), (d) **one decision-maker** (easy contracts) and (e) **community value** (equity, bill relief).

### 2.7 Baseload vs. seasonal demand
- **What:** A data center produces heat **24/7/365 at a nearly flat rate**. Space heating demand is **winter-only and peaky**, while domestic hot water (DHW) is year-round but small.
- **Why:** This is **the** central mismatch. Typical solutions:
  - Anchor on **year-round loads**: DHW, pools, greenhouses, hospitals.
  - **Size** the system to winter base load rather than peak.
  - **Store** heat in tanks for daily swings, and in boreholes or pits for seasonal storage.
  - **Reject** surplus heat in summer through the DC's normal cooling.

### 2.8 Thermal storage
- **What:** Insulated hot-water tanks (hours to days), or borehole/pit storage (seasonal).
- **Why:** It buffers DC outages and maintenance and covers peak hours. It is your **continuity** answer.

### 2.9 Backup / continuity
- **What:** Two directions:
  - (1) If the heat user stops taking heat, the DC must still be cooled, so it keeps 100% of its own heat rejection.
  - (2) If the DC goes down, users must still get heat, from storage, backup electric boilers or heat pumps, or existing boilers kept as standby.
- **Why:** The brief asks for this explicitly ("without compromising data-center cooling reliability"). It needs its own slide.

### 2.10 Efficiency metrics
| Metric | Formula | Meaning |
|---|---|---|
| **PUE** | Total facility energy ÷ IT energy | DC overhead; 1.1–1.6 typical |
| **ERF** (Energy Reuse Factor) | Reused energy ÷ total facility energy | Share of energy reused (0–1) |
| **ERE** (Energy Reuse Effectiveness) | (Total − Reused) ÷ IT energy | PUE with credit for reuse; can drop below 1 |
| **LCOH** | Lifetime cost ÷ lifetime heat delivered ($/MWh) | Compare with gas, oil, propane and steam heat cost |

- **Why:** These turn "good idea" into "measurable value". Put ERF, ERE and LCOH on the results slide.

### 2.11 Heating degree days (HDD)
- **What:** A measure of how cold a place is over a year (base 65 °F).
  - **NYC:** ~4,500–4,800 HDD
  - **Ithaca/Lansing:** ~6,800–7,200 HDD **(verify with NOAA)**
- **Why:** Use it to estimate building heat demand and its seasonal shape. Lansing needs about 1.5× more heating per home than NYC.

---

## 3. Site 1: 111 8th Avenue, Manhattan (existing)

### 3.1 Facts
| Item | Fact | Function / meaning for us |
|---|---|---|
| Building | 2.9 million sq ft full-block building (8th–9th Ave, 15th–16th St); bought by Google in 2010 for ~$1.9B; Google NYC office **plus** one of NYC's main **carrier hotels** (100+ telecom carriers) | Mixed office + data use, so the building **itself** is a potential first heat user (offices need heat) |
| Power | ~80 MW estimated total; tenants include Digital Realty (~18 MW) and Equinix NY9 (~1 MW) **(verify; tracker estimates)** | Order-of-magnitude for heat available. Recoverable heat is only a fraction, because many tenants and air cooling make capture harder |
| Cooling | Likely legacy air cooling with chilled-water plants **(verify)** | Low-grade heat (~25–35 °C), which points to heat pumps or a 5G ambient loop |
| Ownership | Multi-tenant, so many decision-makers | Big governance challenge: who "owns" the heat? This is a key point in the Economics section |

### 3.2 The neighborhood and potential offtakers (verify on map)
| Candidate | Location | Why suitable / not |
|---|---|---|
| **NYCHA Robert Fulton Houses** | Directly west/north-west (9th–10th Ave, W 16th–19th St), about one block | Large, year-round DHW demand; disadvantaged community; **already in a Con Ed pilot using DC heat** (see 3.3) |
| **NYCHA Elliott-Chelsea Houses** | W 25th–27th St, 9th–10th Ave | Same owner (NYCHA), part of the redevelopment |
| **Fulton/Elliott-Chelsea redevelopment** | Both campuses | HUD approved (Aug 2026) demolishing and rebuilding all 2,056 public units plus ~3,454 new mixed-income units. The new buildings move away from gas and steam toward electric heating. **New buildings can be designed for low-temperature heat, which makes them an ideal offtaker** |
| Chelsea Market (75 9th Ave) | Across 9th Ave | Food halls and offices: hot water and kitchens; single owner (Google bought it in 2018 **(verify)**) |
| Google offices in 111 8th itself | On site | Zero pipe distance; easiest first phase |
| Schools, pools, hospitals | e.g., PS 11 (W 21st St), Lenox Health Greenwich Village (7th Ave/12th St), rec-center pools **(verify)** | Steady loads; public value |

### 3.3 Existing precedent next door ★
- **Con Edison "Chelsea" Utility Thermal Energy Network (UTEN) pilot:** collects excess heat from **data center and office cooling** and sends it through a **one-block-long thermal main** to a heat-pump central plant at a **NYCHA** community.
  - Phase 1 serves **372 units with domestic hot water** through basement heat pumps and storage.
  - 36 apartments also get upgraded space heating.
  - Advanced to Stage 2 (engineering) in April 2024.
- **Function for us:** This is **proof of feasibility on this exact block.** A strong proposal **builds on and scales it**, for example "Phase 2/3: grow the pilot into a neighborhood thermal network serving the rebuilt Fulton/Elliott-Chelsea campus". Don't present it as your own invention. **Credit it and extend it.** Find which building is the heat source in PSC Case 22-M-0429 filings.

### 3.4 Urban energy context
| Item | Fact | Meaning |
|---|---|---|
| **Con Edison steam system** | Largest district steam system in North America: ~1,500 customers, 105 miles of pipe, Battery to W 96th St; ~99% natural gas fuel, ~60% from cogeneration; net-zero goal 2050 | Many Chelsea buildings already use steam (high temperature, ~180 °C+). DC heat **can't feed steam directly**, but it can displace steam for DHW or preheat |
| **Local Law 97 (LL97)** | Buildings over 25,000 sq ft must cut emissions 40% by 2030 and 80% by 2050; penalty **$268 per tCO₂e** over the limit; compliance periods 2024–29 and 2030–34 | The money argument for **commercial** offtakers (Chelsea Market, offices). ⚠️ **NYCHA and rent-regulated buildings follow Article 321 prescriptive measures, not the emission caps (verify)**, so LL97 penalties do **not** motivate the NYCHA anchor |
| LL97 emission factors (2024–29) | Electricity ≈ 0.000289 tCO₂e/kWh; natural gas ≈ 0.0000531 tCO₂e/kBtu; steam ≈ 0.0000449 tCO₂e/kBtu (2030+: ~0.0000432) **(verify in NYC rules)** | Use these in the carbon calculation for Site 1 |
| Utility Thermal Energy Network & Jobs Act (2022) | Lets NY utilities own and sell thermal energy through networks, like gas; includes labor standards and pilots | Gives a **ready-made ownership model**: the utility owns the pipes |

### 3.5 Site 1 challenges
- Manhattan street excavation is extremely expensive and slow, so keep pipe runs short (one to three blocks).
- Many tenants mean complex agreements.
- Low-grade, air-cooled heat.
- Roof and basement space for heat pumps and tanks is scarce.

---

## 4. Site 2: Lake Hawkeye, Lansing NY (proposed)

### 4.1 Facts
| Item | Fact | Function / meaning |
|---|---|---|
| Site | Former **Cayuga coal power plant** (~300 MW) on the east shore of Cayuga Lake, Town of Lansing, north of Ithaca | Brownfield reuse; existing transmission and substation; industrial zoning |
| Developer | **TeraWulf**; 80-year ground lease | Long horizon, so long-term heat contracts are credible |
| Size | Project site: ~300 MW at full build. Phase I: 3 buildings, ~150 MW; Phase II reaches ~300 MW; ~80 acres initially. *Press figures vary (300 / 400 / 500 MW+): state your assumption* | Heat is enormous compared with local demand. **Right-size**: only a small slice is needed |
| Cooling | "Fully closed-loop" system with propylene-glycol coolant; water from Bolton Point system, not the lake | Closed loop means a clean, defined capture point. Proposing **liquid cooling (45–60 °C)** fits AI/HPC |
| Power | Central NY grid, "predominantly zero-carbon" | Heat-pump electricity is low-carbon, so the CO₂ savings are large |
| Community benefits promised | Property tax, annual community fund (schools, parks), jobs | Heat could be a **concrete** community benefit, which is more tangible than a fund |

### 4.2 Local context
| Item | Fact | Meaning |
|---|---|---|
| Population | Town of Lansing ~11,000 residents | Small, dispersed demand, so focus on **clusters** |
| **NYSEG gas hookup moratorium (since 2017)** | No new gas connections in parts of Town and Village of Lansing. It blocked a medical facility expansion and new restaurants. The **school district has considered converting to electric/geothermal HVAC** | **This is the community's pain point.** New buildings can't get gas, so a heat network solves a real local problem |
| Tax base | The old plant was ≥10% of the Lansing School District tax base | The school district is a natural partner and a likely anchor offtaker |
| Community concerns | Electricity rates, noise, lake water, property values; packed public meetings; moratorium vote on large developments (Nov 2025) | Acceptance is **not** guaranteed. Heat reuse plus affordability can help earn the social license |
| Climate | Cold, about 1.5× the heating degree days of NYC | High winter heat value; summer surplus problem |
| Nearby precedent | **NYSEG UTEN pilot in Ithaca** (Northside neighborhood; networked geothermal, ~39 buildings) | Shows the utility and regulators already accept thermal networks locally |

### 4.3 Candidate offtakers (verify distances on map)
| Candidate | Why |
|---|---|
| **Lansing Central School District campus** | Large, single owner; already considering electrification; daytime and school-year load; public value |
| Town facilities (town hall, library, community center, pools/rinks) | Public anchor loads |
| **New housing / mixed-use subdivisions blocked by the gas moratorium** | Greenfield, so they can be designed for low-temperature heat and serve as a 4G network "seed" |
| **Greenhouses / controlled-environment agriculture / aquaculture** on or next to the DC site | **Large heat demand at LOW temperature (30–45 °C)**, so it can be served **directly through a heat exchanger with no heat pump** from a liquid-cooled source. Demand is **winter-weighted** (~2,000 full-load hours, with dehumidification/ventilation load in summer), so don't call it "flat". Jobs and local food. ⚠️ Hypothetical: present the grower as a **tenant recruited under the community benefit agreement**, and cite precedent types (greenhouses next to power plants or DCs) **(verify examples)** |
| Hamlets near the site (Ludlowville, Myers Point area) | Closest residential clusters |
| Cornell/Ithaca uses | Probably too far for the first phase (~8–10 mi); a future option |

### 4.4 Site 2 challenges
- Low density means long pipes per home served, so the economics are harder. Cluster the users or co-locate them (greenhouses, new housing).
- The project is still in permitting, with local opposition.
- Big surplus in summer.

---

## 5. Policy and funding (New York + international precedent)

| Item | What it is | Function for us |
|---|---|---|
| **NY Utility Thermal Energy Network & Jobs Act (2022, S9422)** | Lets utilities (Con Ed, NYSEG…) build, own and sell thermal energy through networks; requires pilots; sets labor standards | Ownership model: the **utility owns the network** and recovers costs through rates; the DC sells heat at the fence |
| **NYSERDA Large-Scale Thermal Program (PON 5614)** | Up to $750k for **design studies** of large thermal systems (heat recovery, thermal networks, storage) | Pays for the next step of our proposal |
| **NYSERDA Heat Recovery program / roundtable** | NYSERDA work on recovering waste heat | Shows the state's interest in heat recovery |
| **Federal tax credits (§48 ITC / §48C)** | Investment credits for clean energy equipment, including industrial heat pumps under 48C, up to 30%. **Check the current status after the 2025 federal changes (verify)** | Lowers CAPEX in the economic model; show with and without credit |
| **NYC Local Law 97** | Emissions caps + $268/t penalty | Offtaker willingness to pay (Site 1) |
| **NY Climate Act (CLCPA)** | 85% GHG cut by 2050; ≥35% (goal 40%) of benefits to **disadvantaged communities** | Equity framing; use the NYSERDA DAC map |
| **EU Energy Efficiency Directive (2023/1791)** | Requires large DCs to report and assess waste-heat reuse | International norm, so the US is behind and this is a leadership story |
| **Germany Energy Efficiency Act (EnEfG)** | New DCs (>300 kW) must reuse **10% of heat from July 2026, 15% from 2027, 20% from 2028** | Benchmark: "our design reuses X%, beating the German legal requirement" |

---

## 6. Precedents (cite 2–3 in the pitch)

| Case | Key facts | Lesson |
|---|---|---|
| **Stockholm Data Parks / Open District Heating** (Sweden) | Heat bought from 30+ data centers (16 providers) under standard, temperature-indexed contracts; one DC park meets winter heat needs of ~2,500 homes | **Standard contracts** make heat a tradable product, which is your revenue model |
| **Meta Odense** (Denmark) | DC heat upgraded by heat pumps feeds the Fjernvarme Fyn district heating network (~10,000+ homes) **(verify)** | DC owner pays for the heat pumps; the utility operates them |
| **Microsoft + Fortum, Helsinki region** (Finland) | Large DC region planned to supply a major share of district heating **(verify)** | Scale is possible with a big utility partner |
| **Con Edison Chelsea UTEN pilot** (NYC) | DC heat → one-block thermal main → NYCHA heat-pump plant (372 units of DHW) | **Local proof; directly relevant to Site 1** |
| **NYSEG Ithaca UTEN pilot** | Networked geothermal for ~39 buildings in a disadvantaged neighborhood | Local regulator and utility acceptance (Site 2) |
| Grundfos claim | A 100 MW DC on a 5G ambient loop could provide baseline heat for >20,000 homes | Order-of-magnitude framing (vendor claim, so cite as such) |
| **EU open planning tools**: Hotmaps, Heat Roadmap Europe / sEEnergies atlases, ReUseHeat | Open-source heat-demand and waste-heat mapping/planning | **Know they exist.** Our tool must not claim "first open siting tool". Our novelty is turning a DC **application** into **conditions of approval** (see file 04) |

---

## 7. Data sources: what to use for what

| Source | What it has | Use it for |
|---|---|---|
| **Organizer-provided packet** (Grundfos/HDR slides, GIS list, site info) | Official figures | **First priority**. Judges trust their own numbers |
| **NYC MapPLUTO / PLUTO** (NYC Planning) | Every lot: building area, use, year built, owner | Find big buildings within 1–3 blocks; estimate heat demand from floor area |
| **NYC LL84 Energy & Water Benchmarking** (NYC Open Data) | Annual energy use, fuel mix and EUI per large building | **Actual heat demand of candidate offtakers** (Site 1) |
| **NYC Open Data, NYCHA development data** | Units, buildings, heating type | Fulton/Elliott-Chelsea sizing |
| **Con Ed / PSC Case 22-M-0429** (NY DMM) | UTEN pilot filings | Chelsea pilot details |
| **US Census / ACS** (data.census.gov) | Population, income, housing age, heating fuel by tract | Equity metrics; how many Lansing homes use propane/oil |
| **NYSERDA Disadvantaged Communities map** / CEJST | DAC designation | Equity justification |
| **Tompkins County GIS / Town of Lansing zoning** | Parcels, land use | Site 2 offtaker mapping, distances |
| **NOAA Climate Normals / degree-days.net** | HDD by month | Seasonal demand curve |
| **EIA RECS / CBECS** | Typical heat use per home or building type | Demand when there is no metered data |
| **EPA eGRID** | Grid CO₂ intensity by region (NYC vs NYUP) | Heat-pump electricity emissions |
| **EPA emission factors** | Natural gas ~53.1 kgCO₂/MMBtu; heating oil ~74; propane ~62.9 | Avoided-emissions calculation |
| **OCP Heat Reuse papers** | Temperatures, reference designs, heat recovery station design | Technical credibility |
| **Grundfos District Energy Application Guide** | Pumps, substations, network design | Infrastructure list |

---

## 8. Sources

- Challenge brief: *NYU Hackathon, Data Center Heat Reuse Challenge R1* (local PDF)
- [OCP: Data Center Heat Reuse 101](https://www.opencompute.org/documents/20230623-data-centers-heatreuse-101-3-2-docx-pdf)
- [OCP: Reference Designs for Data Center Heat Reuse](https://www.opencompute.org/documents/2025-03-18-ocp-heatreuse-wp-referencedesigns-v0-1-pdf)
- [OCP wiki: Cooling Environments / Heat Reuse](https://www.opencompute.org/wiki/Cooling_Environments/Heat_Reuse)
- [Review: Data center waste heat for district heating networks (RSER 2025)](https://www.sciencedirect.com/science/article/pii/S1364032125005362)
- [Grundfos District Energy Application Guide](https://directsensors.grundfos.com/campaigns/download-the-district-energy-application-guide.html)
- [Grundfos written evidence to UK Parliament (DCU0053)](https://committees.parliament.uk/writtenevidence/164819/html/)
- [Eurelectric: Stockholm Exergi Data Parks](https://www.eurelectric.org/stories/stockholm-exergi-data-parks-shows-the-potential-for-scaling-the-reuse-of-waste-heat-when-it-becomes-a-tradable-product/)
- [111 Eighth Avenue, data center tracker](https://morethanjustparks.com/data-center-tracker/111-eighth-avenue-google-chelsea-ny--fc3ac993-b901-4e19-90f4-c7e773e6f9e1)
- [Digital Realty 111 8th Ave](https://morethanjustparks.com/data-center-tracker/digital-realty-new-york-111-8th-avenue-campus-ny--c383d8ae-f885-4c0f-9aa4-7f270072e005)
- [Upgrade NY: Nine UTEN pilots advance](https://www.upgradeny.org/nine-utility-thermal-energy-network-pilot-projects-advance)
- [WSP: Con Edison TEN pilots](https://www.wsp.com/en-us/projects/con-edison-thermal-energy-network-pilots-in-new-york-city)
- [Con Edison: Thermal Energy Networks](https://www.coned.com/en/our-energy-future/our-energy-vision/where-we-are-going/thermal-energy-networks)
- [Con Edison: How we source our steam](https://www.coned.com/en/about-us/how-we-source-our-energy/steam)
- [IDEA: Con Edison steam decarbonization](https://www.districtenergy.org/blogs/district-energy/2025/06/11/driving-decarbonization-through-district-steam-con)
- [NY YIMBY: HUD approves Fulton & Elliott-Chelsea redevelopment](https://newyorkyimby.com/2026/08/hud-approves-redevelopment-of-fulton-and-elliott-chelsea-houses-in-chelsea-manhattan.html)
- [Fulton & Elliott-Chelsea FAQs](https://www.fultonelliottchelsea.com/faqs)
- [NYC Accelerator: Climate Mobilization Act brief (LL97)](https://www.nyc.gov/assets/nycaccelerator/downloads/pdf/ClimateMobilizationAct_Brief.pdf)
- [NY Senate S9422: Utility Thermal Energy Network & Jobs Act](https://www.nysenate.gov/legislation/bills/2021/S9422)
- [Governor Hochul: UTENJA implementation](https://www.governor.ny.gov/news/governor-hochul-announces-progress-toward-implementing-utility-thermal-energy-network-and-jobs)
- [Lake Hawkeye Data: Project Overview](https://www.lakehawkeyedata.com/project-overview)
- [TeraWulf: Our Sites](https://www.terawulf.com/our-sites)
- [Inside Climate News: Lansing data center](https://insideclimatenews.org/news/08112025/lansing-new-york-data-center-development/)
- [Tompkins Weekly: Power plant to become data center](https://www.tompkinsweekly.com/news/lansing-at-large-power-plant-to-become-data-center-5560)
- [NY PSC filing on the Lansing gas moratorium impacts](https://documents.dps.ny.gov/public/Common/ViewDoc.aspx?DocRefId=%7BF5645BEB-93DD-4D5A-8882-ABB9DB65B9D8%7D)
- [NYSEG Ithaca UTEN pilot](https://www.nyseg.com/w/nyseg-s-proposed-utility-thermal-energy-network-pilot-advances-to-key-phase-in-ithaca)
- [NYSERDA Large-Scale Thermal $10M announcement](https://www.nyserda.ny.gov/About/Newsroom/2024-Announcements/2024_06_25-Governor-Hochul-Announces-10-Million-Is-Now-Available-For-Large-Scale-Thermal)
- [NYSERDA Heat Recovery Roundtable](https://www.nyserda.ny.gov/-/media/Project/Nyserda/Files/Programs/Heat-Recovery/Heat-Recovery-Roundtable-52025.pdf)
- [White & Case: German Energy Efficiency Act and data centers](https://www.whitecase.com/insight-alert/data-center-requirements-under-new-german-energy-efficiency-act)
- [Columbia Climate Law Blog: Germany DC regulation](https://blogs.law.columbia.edu/climatechange/2025/10/24/from-eu-framework-to-national-action-how-germany-regulates-data-center-energy-use/)
