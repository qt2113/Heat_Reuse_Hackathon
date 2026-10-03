# 04: Strategy, Insights and How to Win, v2

> v2 reflects a 3-round peer review (a second Claude session acting as skeptical judge) and the **full rubric**:
> Technology, Presentation, Innovation/Creativity, Execution, Theme, each 1–4, **20 points total**.

---

## 1. Site choice: **Site 2 (Lake Hawkeye, Lansing)**

### Why Site 2
| Reason | Rubric effect |
|---|---|
| Greenfield: **we can design the capture** (a liquid-cooling requirement, 45–60 °C), so the cascade and direct greenhouse HX become possible | Technology |
| **Gas-hookup moratorium since 2017**: a documented local pain that heat reuse directly solves | Theme, Innovation |
| **Coal plant → data center → clean heat commons** is the regenerative story HDR's framework wants | Theme |
| Lansing's moratorium vote on large developments gives a natural decision-maker (the town board) for our **conditions-of-approval** idea | Innovation |
| Cleaner upstate grid + propane/oil baseline → **much larger net CO₂ savings** than Site 1 | Theme |

### Why not Site 1 (keep as a ½-page fallback only)
- "Scale up Con Edison's Chelsea pilot" is the **most obvious idea in the room**, and the rubric's Innovation score of 2 literally says "**derivative**".
- LL97 penalties **don't apply** to the NYCHA anchor (Article 321 prescriptive path; verify).
- Net carbon vs steam is small (~0.05 t/MWh).
- Low-grade, multi-tenant source with unknowable Manhattan pipe costs.
- *Fallback angle if forced:* a 5G ambient-loop "thermal hub" for commercial offtakers, not a NYCHA pilot extension.

### Site 2 risks to handle honestly
- **Thin data:** use labeled assumptions plus the tool's sliders.
- **Contested project:** stay neutral ("*if* approved, these are the conditions").
- **Tenants/cooling not public; bitcoin history:** liquid cooling is a **condition we require**.
- **Greenhouse grower hypothetical:** a tenant recruited under the community benefit agreement.
- **School distance:** measure it, and show pipe km as a slider.

---

## 2. The big idea: "From Moratorium to Mandate"

> **One-line pitch:** *"Lansing can't stop data-center applications from arriving, but it can make them heat the town. Our tool turns a 150 MW application into enforceable heat-reuse conditions, sized hour by hour, and here's what that means for Lansing."*

**What it is:** a working tool + policy design.
- **Input:** a DC application (MW, cooling type and source temperature), a CSV of candidate offtakers, a weather file.
- **Output:**
  1. the optimal offtaker set and sizing (8760-hour simulation + grid-search optimizer)
  2. a phased reuse obligation (ERF targets by year, benchmarked against Germany's EnEfG 10/15/20%)
  3. a costed heat recovery station the DC funds under the community benefit agreement
  4. an affordability guarantee (tariff ≤ X% of the like-for-like ASHP/propane cost)
  5. continuity requirements (backup MW, storage hours)
- **Worked case:** the **Lansing Thermal Commons**: greenhouse via direct HX + school + town facilities + moratorium-area housing (Phase 2).

**Why it's novel (and why the plain version isn't):** open heat-planning tools already exist in the EU (Hotmaps, Heat Roadmap Europe / sEEnergies, ReUseHeat), so "an open siting tool" alone would score "common solution". What is new is aiming at the **actual decision-maker at the actual moment of leverage**: the local **approval** of a DC. To our knowledge, no US town has a tool for local heat-reuse conditions (say "to our knowledge").

**Guardrails:**
- Demo on Lansing only. Claim generality only for what the inputs support.
- Say "model condition-of-approval language", **never** "legally binding".
- Stay neutral on whether the DC should be built.

### Sharpest insight to surface: the ERF reality check
- A 150 MW campus (facility power at full load all year, an upper bound) rejects ~1,300 GWh/yr, the heat-equivalent of ~65,000 homes. Lansing's realistic offtakers use ~28 GWh at full build-out, so only ~22 GWh of DC heat is used (**ERF ≈ 1.7%**).
- Co-location is an obligation to **offer** heat and land at a capped price, not a guarantee that growers will come. AppHarvest's ~24 ha greenhouse in Kentucky went bankrupt in 2023 (verify), and a judge may raise it.
- Germany would demand 10–20%. A rural town **can't** absorb that, so a naive "% mandate" fails.
- Our conditions therefore combine:
  - **readiness** (heat recovery interface built in)
  - an **availability offer** (heat at the fence at a capped price)
  - a **co-location obligation** (host heat-intensive users such as a greenhouse/agri park, aquaculture or drying)
  - **ERF targets that rise as offtakers connect**
- This is the "creative problem-solving" the rubric asks for: the tool shows why the simple rule fails and designs a better one.

---

## 3. Rubric game plan (target 18–20 of 20)

| Category | Target | How |
|---|---|---|
| **Technology** | 4 | 8760-hour simulation; temperature-dependent COP; **temperature cascade with a direct greenhouse HX**; storage dispatch; backup sized to the full peak; grid-search optimizer; like-for-like economics |
| **Innovation** | 4 | From moratorium to mandate (policy-tech hybrid); ERF reality check → redesigned obligation |
| **Execution** | 4 | Narrow, offline, validated app; **energy-balance ✔**; hosted link; README; backup video; no new features after 16:00 |
| **Theme** | 4 | Regenerative arc; the brief's **5 dimensions labeled in the app**; KPI tiles for **DC / users / community**; continuity and cooling reliability explicit |
| **Presentation** | 4 | 30-s hook; **live demo in the middle**; 8–10 slides with takeaway titles; one master diagram; three closing numbers |

---

## 4. Ten insights (updated)

1. **Heat is a by-product, never a dependency.** The DC keeps 100% of its own heat rejection; the recovery loop runs in parallel with automatic bypass.
2. **Use a temperature cascade.** Liquid-cooled 45–50 °C goes **directly** to the greenhouse (no heat pump); the heat pump lifts only what needs 60–70 °C. This cut our LCOH from ~$116 to ~$95/MWh.
3. **Compare like for like.** Include equipment capex for alternatives: network ~$95 vs per-home cold-climate ASHP ~$160–230 vs propane $125 fuel-only.
4. **Answer "why not just ASHPs?"** before it's asked:
   - a higher COP from a 45 °C source than from −15 °C air
   - grid peak relief on the coldest days
   - no panel or service upgrades
   - DC cooling benefit
5. **Right-size, and say what happens to the rest.** We use ~2% of the heat in Phase 1; the rest is rejected as normal. Growth comes through co-location.
6. **Size backup to the full peak.** Continuity can't rely on the DC.
7. **Don't overclaim.** No water savings at Site 2 (dry coolers); the greenhouse is winter-weighted, not flat; the grower is hypothetical; liquid cooling is a condition.
8. **Make it source-agnostic.** The network can later take heat from wastewater, geothermal or other sources, so there are no stranded assets if the DC leaves.
9. **Phase it to real milestones.** TeraWulf Phase I (~150 MW) → school + town + greenhouse; Phase II (~300 MW) → housing + agri park.
10. **Speak the judges' language.**
    - **Grundfos:** variable-speed pumps, ΔT management, substations, hydraulic separation.
    - **HDR:** regenerative = net-positive for the place.

---

## 5. Likely judge questions

| Question | Answer skeleton | Who |
|---|---|---|
| Why not just air-source heat pumps? | Like-for-like table + COP at −15 °C + grid peak + DC cooling benefit | B |
| What if the DC shuts down or isn't built? | Backup sized to the full peak; source-agnostic network; conditions bind only *if* approved | A/C |
| Does this risk DC cooling? | Hydraulic separation; parallel loop; automatic bypass; DC keeps N+1 heat rejection | A |
| Summer? | DHW + greenhouse dehumidification base load; surplus rejected as today; ERF reported | A |
| Who pays? Why would TeraWulf agree? | The heat recovery station (~$1.2M) is tiny vs the project; it's the cost of social license in a town that held a moratorium vote; the community fund becomes tangible heat | B/C |
| Is the greenhouse real? | A hypothetical tenant recruited under the community benefit agreement; precedent type cited; the app shows results with and without it | C |
| Isn't 1.7% reuse tiny? | Yes, and that's our point. A rural % mandate fails, so we designed readiness + availability + co-location conditions | C |
| Is your model right? | Energy-balance ✔; sources in the appendix; sensitivity sliders | A/B |
| How is this different from existing tools (Hotmaps etc.)? | They map heat. Ours converts a **DC application into approval conditions** for a US town | C |
| Is the DC crypto or AI? | Unknown publicly; liquid cooling is a **condition**; the tool takes source temperature as an input | A |

---

## 6. Pitfalls (updated)
- ❌ Mixing MW and MWh.
- ❌ Comparing LCOH with fuel-only prices without saying so.
- ❌ Claiming water savings for closed-loop dry coolers.
- ❌ Confusing chilled-water (12–18 °C) and condenser (30–35 °C) loops.
- ❌ Calling greenhouse demand "flat" or "year-round".
- ❌ Backup smaller than the peak.
- ❌ A live demo with live API calls, untested sliders or no backup video.
- ❌ 15 table-heavy slides. Use 8–10 plus the demo; tables go to backup slides.
- ❌ Claiming "first open tool" or "legally binding".
- ❌ Taking sides on whether the DC should exist.

---

## 7. Presentation flow (≈ 7–10 min)
1. **Hook** (30 s)
2. Lansing context (45 s)
3. The idea: moratorium → mandate (45 s)
4. Architecture + cascade (60 s)
5. **Live demo** (2–3 min):
   1. Default scenario.
   2. Toggle "DC funds the heat recovery station" and watch LCOH drop.
   3. Toggle "DC outage" and watch backup cover the peak.
   4. Show the balance ✔.
   5. Open the conditions tab.
6. Economics, like for like (45 s)
7. Value for DC / users / community + regenerative arc (45 s)
8. Close: **three numbers + one line**

**Closing line:** *"Every data center is a heat plant. We give towns the tool to make it a neighbor."*

---

## 8. Minimal logic chain
```
[DC application] →(tool: 8760-h sim + optimizer)→ [Right-sized cascade: direct HX + heat pump + storage + full-peak backup]
   →(conditions of approval: readiness · availability · co-location · affordability · continuity)→
   [Lansing Thermal Commons: $/MWh below ASHP & propane · tCO₂ avoided · public buildings + homes served]
```
**Central claim:** *A town can't stop the data center from coming, but with the right conditions it can turn the data center's waste heat into a shared community utility.*
