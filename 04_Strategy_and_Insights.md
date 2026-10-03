# 04: Strategy, Insights and How to Win, v3 (Site 1)

> v3 is based on the organizers' full source pack (`sources/`, 23 documents) plus the earlier peer review.
> Rubric: Technology, Presentation, Innovation/Creativity, Execution, Theme, each 1–4, **20 points total**.

---

## 1. Site choice: **Site 1 (111 8th Ave, Chelsea)**

### Evidence from the organizers' documents
| Source | Finding | Favours |
|---|---|---|
| **[SP-LH]** HDR site pack, Lake Hawkeye | "There are also **no disadvantaged communities nearby**"; poverty 28th percentile; air quality excellent | Site 1. A Site 2 equity story has no support |
| **[SP-111]** HDR site pack, 111 8th Ave | The block just west (Fulton Houses): poverty **83rd** pct, minority **79th**, **PM2.5 92nd**, ozone **83rd** (pack suspects nearby diesel backup generators). Social vulnerability **79th**. Nearest power plants are gas cogeneration, "one right next to a disadvantaged community" | **Site 1**. A documented environmental-justice need, which scores on Theme |
| **[DH]** DATA HEAT market guide | Favourable segments include new data centers "near areas with potential **high density new construction**, or near **steam DE systems** (for boiler feedwater pre-heat and future hot water conversion potential)" | **Site 1**: the rebuild + the Con Ed steam system |
| **[CBS]** district-heating white paper | "Multi-kilometre connections can have a significant impact on the total investment cost" | Site 1 (one-block run) |
| **[HDR]** HDR heat-reuse deck | HDR's own research: thermal energy networks where buildings are **both source and sink** | Site 1 (an urban network, the judges' own topic) |
| **[T5]**, CenTrio | Communities increasingly block data centers ($150B delayed in 2025); heat reuse "enables faster approvals, stronger community positioning" | Both |
| **[RII]** data centers + greenhouses | ~2 acres of greenhouse per MW; best when designed in from the start | Site 2 (not used) |

### Site 1 risks to handle honestly
| Risk | How we handle it |
|---|---|
| **Looks derivative** (Con Ed's Chelsea pilot already exists) | Credit it as **Phase 0**. Our contribution is Phases 1–3: the rebuild design window, a multi-tenant standard contract, the tool, and a city-wide screen of carrier hotels |
| Multi-tenant governance (who owns the heat?) | Term 2: a **standard heat-purchase contract** any tenant can sign (Stockholm Data Parks model) |
| Low-grade heat (air-cooled, 30–35 °C condenser water) | Ambient loop + building heat pumps (5G). Heat-recovery chillers on tenant loops. Rebuilt towers designed for 45 °C space heat |
| LL97 doesn't push NYCHA (Article 321, verify) | Use LL97 only for **commercial** offtakers (Chelsea Market, 111 8th offices). For NYCHA the drivers are affordability, grid peak and air quality |
| The rebuild is contested; the HUD timeline may slip | Neutral on the rebuild itself: "*whatever* gets built should be heat-ready". Phase 1 works with the existing buildings' hot water |
| Small carbon margin vs an all-electric rebuild | Show it honestly. The bigger wins are **grid peak relief** in Manhattan, higher COP and DC cooling savings |

---

## 2. The big idea: "Chelsea Thermal Hub"

> **One-line pitch:** *"The building that carries Manhattan's internet throws its heat into the sky, one block from homes in the 83rd percentile for poverty that are about to be rebuilt. Our tool makes sure the rebuild is designed to use it, and shows every carrier hotel in New York how to do the same."*

**What it is:** a working tool + a delivery design.
- **Input:** DC tenants (MW, cooling-loop temperature), candidate offtakers from **NYC LL84 + PLUTO** (floor area, fuel, energy use), NYC hourly weather, prices.
- **Output:**
  1. a phased hub plan: Phase 0 (Con Ed pilot) → Phase 1 (hot water for existing Fulton buildings + 111 8th offices) → Phase 2 (each rebuild tower as it opens) → Phase 3 (Chelsea Market, schools, more tenants)
  2. hourly supply–demand matching on the brief's 5 dimensions, with an energy-balance check
  3. like-for-like economics vs the alternatives (per-building ASHP, steam, gas)
  4. **5 heat-export agreement terms** with the numbers filled in (file 05)
- **Reusable:** the same inputs work for any NYC carrier hotel (60 Hudson St, 32 Avenue of the Americas, 375 Pearl St; verify), so the demo ends with a **city-wide screen**.

**Why it's novel:**
1. **The design-window insight.** The rebuild is the only moment in ~50 years when ~5,500 homes can be designed for 45 °C heat and a connection at almost no extra cost. After the designs freeze, the chance is gone. Our phasing is tied to the rebuild schedule, not to the DC.
2. **Multi-tenant heat as a tradable product.** A carrier hotel has 100+ tenants. Instead of one bespoke deal, a **standard heat contract** lets any tenant's cooling plant sell heat (as Stockholm does across 30+ data centers).
3. **Air quality as a design input.** The tool reports the on-site combustion it displaces (boilers and steam load), next to the block with 92nd-percentile PM2.5.
- Guardrail: open heat-planning tools exist (Hotmaps, sEEnergies, ReUseHeat). Don't claim "first tool"; claim the **application** (carrier hotel + rebuild + standard contract).

---

## 3. Rubric game plan (target 18–20 of 20)

| Category | Target | How |
|---|---|---|
| **Technology** | 4 | 8760-hour simulation; heat-recovery chillers on condenser loops; ambient loop with building heat pumps (temperature-dependent COP); storage; backup to full peak; grid-search optimizer; like-for-like economics |
| **Innovation** | 4 | Design-window timing; standard multi-tenant heat contract; city-wide carrier-hotel screen |
| **Execution** | 4 | Narrow, offline, validated app; **energy-balance ✔**; hosted link; README; backup video; feature freeze 18:00 |
| **Theme** | 4 | EJ block documented by the organizers' own site pack; HDR's "buildings as source and sink"; KPI tiles for **DC / users / community**; continuity explicit |
| **Presentation** | 4 | 30-s hook; **live demo in the middle**; 8–10 slides; one master diagram; three closing numbers |

---

## 4. Ten insights

1. **Heat is a by-product, never a dependency.** Heat-recovery chillers sit in parallel; the DC keeps its cooling towers and an automatic bypass.
2. **Credit, then extend.** "Con Ed proved it works on this block (Phase 0). We show how it becomes a neighborhood utility."
3. **Timing beats technology.** The rebuild's design window is the leverage point. Build-ready 45 °C heating costs little now and a lot later.
4. **Use the low-grade heat where it is cheapest to lift.** An ambient loop at 15–25 °C loses little heat and needs cheap uninsulated pipe; each building lifts only what it needs.
5. **Compare like for like.** The rebuild's real alternative is all-electric (per-building ASHP or VRF). Our advantages: COP ~4 from a 25 °C loop vs ~2–2.8 from winter air, **lower winter peak on Manhattan's constrained grid**, no rooftop units, and the DC gets cooling.
6. **Carbon, honestly.** Per MWh of heat: ~0.07 t (loop) vs ~0.10 t (ASHP) vs ~0.15 t (steam) vs ~0.20 t (gas), using LL97 factors. The largest gains are vs gas and steam in Phase 1 and Phase 3.
7. **Water is a real benefit here, if verified.** Carrier-hotel cooling towers evaporate water; every MWh the network removes is water not evaporated. Confirm the tenants use evaporative towers before claiming it.
8. **Right-size.** We need ~5–10 MWth of ~80 MW. The rest is rejected as today.
9. **Source-agnostic network.** The loop can later take heat from sewers, the High Line area's other buildings, or geothermal. No stranded asset if a tenant leaves.
10. **Speak the judges' language.** Grundfos: variable-speed pumps, ΔT management, hydraulic separation, substations. HDR: regenerative = net-positive for the place; buildings as source and sink.

---

## 5. Likely judge questions

| Question | Answer skeleton | Who |
|---|---|---|
| Isn't this just Con Ed's pilot? | The pilot is Phase 0 (hot water, 372 apartments). We add the rebuild design window, a standard multi-tenant contract, the tool and a city-wide screen | C |
| Why not just put heat pumps in each new building? | Like-for-like table: COP from a 25 °C loop vs winter air; grid peak; no rooftop units; DC cooling + water benefit | B |
| Does this risk DC cooling? | Heat-recovery chillers in parallel; hydraulic separation; automatic bypass to the towers; DC keeps N+1 rejection | A |
| What if a tenant leaves or load drops? | Many tenants feed a standard contract; storage; backup to full peak; source-agnostic loop | A/B |
| Who owns it? | Con Ed under the UTENJA thermal-network law owns the loop; tenants sell heat at the fence; NYCHA/developer builds heat-ready towers | B |
| What if the rebuild is delayed? | Phase 1 serves existing buildings' hot water; the terms bind *whatever* is built | C |
| Does LL97 help? | For commercial offtakers yes; for NYCHA no (Article 321, verify). We don't rely on it for the anchor | B |
| Manhattan digging costs? | One-block run along W 16th St; ambient pipe is uninsulated HDPE; slider in the app | A/B |
| Are your numbers right? | Energy-balance ✔; LL84 data for offtakers; assumptions appendix; sensitivity sliders | A/B |
| Do you fix the air quality? | We displace combustion for heat and report it. We don't claim to fix the generators; we flag them for the operator's community plan | C |

---

## 6. Pitfalls
- ❌ Presenting the Con Ed pilot as our idea.
- ❌ Claiming LL97 penalties motivate NYCHA.
- ❌ Confusing chilled-water (12–18 °C) and condenser (30–35 °C) loops.
- ❌ Claiming the whole ~80 MW is recoverable.
- ❌ Claiming water savings before confirming evaporative towers.
- ❌ Promising the HUD rebuild timeline.
- ❌ Mixing MW and MWh; comparing LCOH with fuel-only prices without saying so.
- ❌ Live API calls in the demo; untested sliders; no backup video.
- ❌ 15 table-heavy slides.

---

## 7. Presentation flow (≈ 7–10 min)
1. **Hook** (30 s): the internet's backbone, the heat, the block next door.
2. Place (45 s): the site-pack EJ facts; the rebuild; Con Ed's pilot as Phase 0.
3. The idea (45 s): Chelsea Thermal Hub; the design window.
4. Architecture (60 s): condenser loops → heat-recovery chillers → ambient loop → building heat pumps.
5. **Live demo** (2–3 min):
   1. Default scenario (Phase 1).
   2. Turn on rebuild Phase 2 towers; watch coverage and peak.
   3. Toggle "DC outage"; backup covers the peak.
   4. Show the balance ✔ and the agreement terms tab.
   5. Switch the site to another carrier hotel (city-wide screen).
6. Economics, like for like (45 s)
7. Value for DC / NYCHA residents / community + regenerative arc (45 s)
8. Close: **three numbers + one line**

**Closing line:** *"Every carrier hotel is a heat plant. Chelsea can be the first neighborhood that's designed to use it."*

---

## 8. Minimal logic chain
```
[Carrier hotel: tenant condenser loops, 30–35 °C] →(heat-recovery chillers, DC cooling protected)→ [Ambient loop, one block]
   →(building heat pumps + storage + full-peak backup)→ [Fulton/Elliott-Chelsea, designed heat-ready during the rebuild]
   →(standard heat contract · affordability · continuity)→ [tCO₂ and grid peak avoided · combustion displaced next to an EJ block · bills held ≤ all-electric]
```
**Central claim:** *The rebuild is a once-in-50-years window. Designing it around the data center's waste heat turns the internet's backbone into the neighborhood's heat source.*
