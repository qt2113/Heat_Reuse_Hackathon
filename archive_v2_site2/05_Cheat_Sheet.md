# 05: One-Page Cheat Sheet (print this)

**Site:** Lake Hawkeye (TeraWulf), Lansing NY: the former Cayuga coal plant, ~150 MW Phase I → ~300 MW.
**Idea:** **From Moratorium to Mandate.** A working tool that turns a data-center application into heat-reuse **conditions of approval**, demoed on the **Lansing Thermal Commons**.
**Pitch:** *"Lansing can't stop data-center applications from arriving, but it can make them heat the town."*

## Rubric (20 pts) → our answer
| Tech | Innovation | Execution | Theme | Presentation |
|---|---|---|---|---|
| 8760-h sim, temperature-dependent COP, cascade, storage, optimizer | Application → conditions; ERF reality check | Offline app, balance ✔, hosted, video | Regenerative arc; 5 dimensions + 3 stakeholders in the app | Hook, live demo mid-pitch, 8–10 slides |

## System (left → right)
`DC liquid loop 45–50 °C → Heat Recovery Station (HX + bypass to the DC's own dry coolers) → [direct HX → greenhouse 30–45 °C] + [heat pump (N+1) → school/town 60–70 °C, homes 45–55 °C] → storage → backup boiler (full peak)`

## The 5 dimensions (use the brief's words)
- **Temperature:** cascade.
- **Capacity:** HP 3 MW delivered / 4 MW installed; peak ~13 MW.
- **Timing:** hourly dispatch + storage.
- **Seasonality:** monthly chart; winter-weighted.
- **Continuity:** backup = full peak; the DC never depends on the network.

## Key numbers: full build-out, Phase 1 + 2 (ASSUMPTIONS, the app recomputes them; Phase 1 alone ≈ 22 GWh)
| | |
|---|---|
| Demand | ~28 GWh/yr: greenhouse ~16, school ~4, town ~2, Phase 2 homes ~6 |
| CAPEX | ~$21M |
| LCOH | **~$95/MWh** (~$77 with the 30% credit, if still available) |
| Per-home cold-climate ASHP (all-in) | ~$160–230/MWh |
| Propane (fuel only) | ~$125/MWh |
| DC heat used | ~22 GWh of ~1,300 (150 MW facility at full load: an upper bound) → **ERF ≈ 1.7%**, so we use readiness + an **offer** of heat/land for co-location instead of a flat % mandate |
| Hook number | ~1,300 GWh ≈ **heat-equivalent of ~65,000 homes**, more than 10× Lansing's ~4–5k households (verify) |

## 5 model conditions
1. Heat-recovery readiness (≥ X MW at ≥ Y °C)
2. Applicant-funded heat recovery station + capped heat price at the fence
3. Phased ERF targets + co-location of heat-intensive users
4. Affordability guarantee (≤ X% of the ASHP/propane cost)
5. Continuity (full-peak backup) + public dashboard

## Gates
**G0** 10:30 data columns frozen · **G1** 13:00 MVP runs (else monthly fallback) · **G2** 15:30 app v2 · **G3** 16:00 FEATURE FREEZE · **G4** 17:30 full draft · 18:00 video + deploy · 20:30 submit

## Owners
**A** app/sim/demo driver · **B** config, LCOH, carbon, ASHP comparison, optimizer · **C** offtakers, map, conditions, hook, deck, narrator

## Don'ts
MW≠MWh · no water-savings claim · chilled water ≠ condenser · greenhouse demand isn't flat · no "legally binding" · no "first tool" · neutral on the DC itself
