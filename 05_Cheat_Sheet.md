# 05: One-Page Cheat Sheet (v3, Site 1, print this)

**Site:** 111 8th Avenue, Chelsea, Manhattan. An existing multi-tenant carrier hotel (~80 MW total, verify), one block from NYCHA Fulton Houses.
**Idea:** **Chelsea Thermal Hub.** A working tool that plans a phased heat-export hub from the carrier hotel's cooling loops to the **Fulton/Elliott-Chelsea rebuild**, timed to its design window, and outputs **5 heat-export agreement terms**. Con Ed's pilot is **Phase 0**; we design Phases 1–3.
**Pitch:** *"The building that carries Manhattan's internet throws its heat into the sky, one block from homes in the 83rd percentile for poverty that are about to be rebuilt. We make sure the rebuild is designed to use it."*

## Why Site 1 (the organizers' evidence)
- **[SP-111]** Block to the west: poverty 83rd pct, minority 79th, **PM2.5 92nd**, ozone 83rd (likely diesel generators), social vulnerability 79th.
- **[DH]** Favourable segment: DCs "near high-density new construction or steam district energy" = this site. **[SP-LH]** Lansing: "no disadvantaged communities nearby".
- **[CBS]** Multi-km pipes hurt economics. Here the run is **one block**.

## Rubric (20 pts) → our answer
| Tech | Innovation | Execution | Theme | Presentation |
|---|---|---|---|---|
| 8760-h sim, multi-tenant heat recovery chillers, ambient loop + building heat pumps, storage, optimizer | Design-window timing; multi-tenant standard heat contract; city-wide carrier-hotel screen | Offline app, balance ✔, hosted, video | EJ block next door; HDR "buildings as source and sink"; DC / users / community tiles | Hook, live demo mid-pitch, 8–10 slides |

## System
`Tenant condenser loops 30–35 °C → heat-recovery chillers (DC keeps its cooling towers) → ambient loop 15–25 °C, one block → building heat pumps → hot water 60 °C + low-temperature space heat 45 °C in the rebuilt towers → tanks in new basements → backup: existing steam/boilers during transition, electric later`

## The 5 dimensions (use the brief's words)
- **Temperature:** 30–35 °C source; heat pumps lift in each building; rebuilt towers designed for 45 °C space heat.
- **Capacity:** ~5–10 MWth from 1–2 tenants' plants vs ~80 MW total (verify). Right-size; don't claim the whole building.
- **Timing:** hot water is the 24/7 base; space heat in winter; storage covers morning and evening peaks.
- **Seasonality:** summer = hot water only; surplus goes to the DC's towers as today.
- **Continuity:** the DC never depends on us (bypass to its towers); backup covers the full peak.

## Key numbers (ASSUMPTIONS, the app recomputes them; verify)
| | |
|---|---|
| Phase 0 (Con Ed pilot) | 372 apartments, hot water (credit it; verify) |
| Full rebuild demand | ~5,500 efficient units × 6–9 MWh ≈ **35–50 GWh/yr** |
| DC heat needed | **~5–10 MWth**, a small slice of the building |
| Grid factor (LL97 2024–29) | 0.289 t/MWh; steam ≈ 0.15 t/MWh heat; gas ≈ 0.20 t/MWh heat |
| Carbon per MWh heat | building heat pump on DC loop (COP ~4) ≈ 0.07 t vs per-building ASHP (COP ~2.8) ≈ 0.10 t vs gas ≈ 0.20 t |
| ERF | ~5% (assumption) vs ~1.7% at Lansing; Germany's bar is 10% |

## 5 heat-export agreement terms (the tool fills in X, Y, Z)
1. **Readiness:** heat-recovery chillers on ≥ X MW of tenant condenser loops at ≥ Y °C
2. **Standard heat contract:** any tenant can sell heat at the fence at a capped price $Z/MWh (Stockholm model)
3. **Design-window offtake:** rebuild phases built for 45 °C heat and connection-ready
4. **Affordability:** NYCHA tariff ≤ the all-electric alternative; free connection; no rent pass-through
5. **Continuity + transparency:** full-peak backup; public dashboard (heat, CO₂, air quality)

## Gates (switch-over day)
**G1** 16:00 MVP runs on Site 1 (else monthly fallback) · **G2** 17:30 app v2 · **G3** 18:00 FEATURE FREEZE · 18:45 video + deploy · 19:00 rehearsal ×2 · 20:30 submit

## Owners
**A** app/sim/demo driver · **B** config, LCOH, carbon, steam/ASHP comparison · **C** LL84 offtakers, map, EJ story, agreement terms, deck, narrator

## Don'ts
MW≠MWh · don't call it our invention (credit Con Ed) · no LL97 penalty claim for NYCHA (Article 321) · chilled water ≠ condenser · don't claim to fix the diesel generators · don't promise the HUD timeline · no "first tool"
