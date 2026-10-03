# 02: Whole-Team Workflow, v3 (Site 1 switch-over)

> **v3:** we switched to **Site 1 (111 8th Ave)** mid-day after reading the organizers' source pack (file 04 §1).
> The deliverable is still a **working tool + a short deck**: Technology + Innovation + Execution = 12 of 20 points.
> Times below assume we restart around **14:00** with a ~21:00 deadline. Shift them if needed; **keep the gates**.
>
> Roles (details in `03_Individual_Roles.md`):
> - **A**: Model and app (Python simulation + Streamlit)
> - **B**: Economics, carbon and data (`config.yaml`; helps A with the optimizer)
> - **C**: Place, story and deck (`offtakers.csv`, map, EJ facts, agreement terms, hook, deck)

---

## 0. What carries over from the Site 2 work

| Asset | Carries over? | Change needed |
|---|---|---|
| Simulation engine (hourly demand, storage, backup, balance check) | **Yes** | Source 30–35 °C; heat pumps in each building on an ambient loop; phase selector |
| `variable_network.html` (model graph) | **Mostly** | Re-label the supply and offtaker blocks for Site 1 (done in v3 of the page) |
| Economics functions (LCOH, CRF, carbon) | **Yes** | NYC prices, steam baseline, LL97 factors |
| Weather loader | Yes | NYC TMY instead of Ithaca |
| "Conditions of approval" panel | **Reuse the code** | Text becomes "heat-export agreement terms" |
| Lansing offtakers, greenhouse, moratorium story | No | Archived in `archive_v2_site2/` |

### Shared workspace
```
/HeatReuse_Hackathon
  app/                 ← Streamlit app (A) → Streamlit Community Cloud
    data/weather.csv   ← NYC hourly typical year (offline)
    data/offtakers.csv ← from C (LL84 + PLUTO)
    config.yaml        ← from B (the "numbers sheet")
  sources/             ← organizer documents + extracted text
  deck/                ← 8–10 slides (C)
  README.md            ← screenshots + how to run (A)
  backup_video.mp4     ← recorded 18:45
```

---

## 1. Timeline for the rest of today

```
14:00 Switch-over huddle (15 min) ─ 14:15 Sprint: re-point model + data ─ ✔G0 14:45 data columns fixed
14:45 Build ─ ✔G1 16:00 MVP runs on Site 1 (or fall back) ─ ✔G2 17:30 app v2 ─ ✔G3 18:00 FEATURE FREEZE
18:00 Polish + deploy ─ 18:45 backup video ─ 19:00 Rehearsal ×2 ─ 20:15 buffer ─ 20:30 submit
```

---

## 2. Block by block

### 14:00–14:15 | Switch-over huddle (all)
- Read file 05 (1 page) and file 04 §1–2.
- Agree on the **one-line pitch** and the **phases** (0 = Con Ed pilot, 1 = existing Fulton hot water + 111 8th offices, 2 = rebuild towers, 3 = Chelsea Market + more tenants).
- Confirm the pitch length → slide count (5 min ≈ 6 slides + demo; 10 min ≈ 9 slides + demo).

### 14:15–14:45 | Sprint: fix the data contracts
| A | B | C |
|---|---|---|
| Swap weather to NYC; add the phase column and the ambient-loop COP function | `config.yaml` v1: Con Ed electricity + steam, gas, LL97 factors, unit costs | `offtakers.csv` v1 from LL84/PLUTO: Fulton, rebuild phases, 111 8th offices, Chelsea Market, a school |

**✔ G0 (14:45):** CSV/YAML columns frozen. After this, change values, not structure.

### 14:45–16:00 | Build
| A | B | C |
|---|---|---|
| Dispatch on Site 1: loop source → building heat pumps → storage → backup; KPIs; **balance ✔** | LCOH; comparison vs central air-source heat pump, steam, gas; net carbon; combustion displaced; winter peak avoided | Map; offtaker scoring; EJ slide from [SP-111]; draft 5 agreement terms; deck skeleton |

**✔ G1 (16:00): does the MVP run end-to-end on Site 1?**
- **Yes →** app.
- **No →** monthly-resolution fallback; charts from what works; more effort on the deck.

### 16:00–18:00 | App + economics + deck
| A | B | C |
|---|---|---|
| Streamlit v2: site/phase selector, sliders, KPI tiles (DC / users / community), 5 dimensions labeled, agreement-terms tab, EJ context tab | Real values; sensitivity; help A with the optimizer (stretch) | Deck v1; decide which slides the demo replaces; write the hook |

**✔ G2 (17:30):** app v2 runs locally with the preloaded Chelsea scenario.
**✔ G3 (18:00): FEATURE FREEZE.** Bug fixes and polish only. The city-wide screen ships only if it already works.

### 18:00–18:45 | Polish + deploy
- **A:** no-NaN guards; deploy; README with screenshots.
- **B:** final numbers; assumptions + sources appendix (cite organizer docs by tag).
- **C:** final deck; sample agreement-terms slide; speaker notes.

### 18:45–19:00 | Backup video (2–3 min) + PDF export

### 19:00–20:15 | Rehearsal ×2 with the live demo
- Demo driver = A, narrator = C, cost Q&A = B.
- Demo script:
  1. Phase 1 default.
  2. Switch to Phase 2: rebuild towers connect; coverage and peak update.
  3. Toggle "DC outage": backup covers the full peak.
  4. Show the balance ✔ and the agreement-terms tab.
  5. (If built) switch to another carrier hotel.

### 20:15–20:30 | Buffer → submit early

---

## 3. Communication rules
1. Configs are the truth. Announce value changes in chat.
2. Stand-ups (5 min, blockers only): 14:45, 16:00, 17:30.
3. **20-minute rule:** if a number or bug blocks you for 20 minutes, use a labeled assumption or drop the feature.
4. C owns the deck; A owns the app repo; B owns `config.yaml`.
5. No new features after 18:00.

---

## 4. Rubric checklist (20 points)

| Category | What earns a 4 | Where we deliver it | Owner |
|---|---|---|---|
| **Technology** | Sophisticated, superbly applied | 8760-hour simulation; condenser-loop recovery; ambient loop + building heat pumps with temperature-dependent COP; storage; optimizer | A (+B) |
| **Innovation** | Novel approach | Design-window phasing; standard multi-tenant heat contract; city-wide carrier-hotel screen | C (+A) |
| **Execution** | Works flawlessly | Offline, validated app; balance ✔; hosted link; README; backup video | A |
| **Theme** | Theme is integral | EJ evidence from [SP-111]; HDR "buildings as source and sink"; 3-stakeholder tiles; 5 dimensions labeled | C |
| **Presentation** | Clear, engaging | 30-s hook; live demo mid-pitch; takeaway titles; 8–10 slides | C |

### Brief requirements (keep for Theme)
- [ ] Site + local-context justification (site-pack EJ facts)
- [ ] Architecture diagram
- [ ] Capture point / temperature / capacity (condenser loops, 30–35 °C, ~5–10 MWth)
- [ ] Offtakers + selection criteria (scoring)
- [ ] Infrastructure (HX/heat-recovery chillers, loop, building heat pumps, tanks, backup)
- [ ] Operating approach (winter / summer / DC outage / maintenance)
- [ ] Temperature / capacity / timing / seasonality / continuity
- [ ] Cooling reliability protected (towers kept, bypass)
- [ ] Heat continuity (backup to the full peak)
- [ ] Value for DC / users / community
- [ ] CAPEX/OPEX; revenue/connection model; ownership/risks (backup slide)
- [ ] Carbon / efficiency / water / air quality
- [ ] Equity / acceptance

### Deck outline (8–10 slides)
1. **Hook + one-line pitch**
2. The place: carrier hotel + Fulton Houses + the rebuild; site-pack EJ facts
3. Phase 0 credit (Con Ed pilot) → what we add
4. Architecture: condenser loops → ambient loop → building heat pumps
5. **LIVE DEMO** (replaces matching, sizing and economics slides)
6. Economics, like for like: loop vs central ASHP vs steam vs gas
7. Reliability & continuity
8. Value for DC / residents / community + regenerative arc
9. The 5 agreement terms + phasing to the rebuild
10. Close: three numbers + one line

Backup slides: RACI, risk register, sensitivity, assumptions/sources, Site 2 comparison (why not Lansing), rejected offtakers.

---

## 5. Risk plan for the rest of the day
| Risk | Mitigation |
|---|---|
| Switching costs more time than planned | G1 at 16:00 with monthly fallback; reuse the Site 2 engine |
| LL84 data slow to find | Floor area × intensity, labeled; LL84 only for the 3 biggest offtakers |
| Manhattan pipe cost unknown | Slider + "high uncertainty" label |
| App breaks during the pitch | Backup video + PDF screenshots |
| Judges say "that's Con Ed's pilot" | Slide 3 answers it before they ask |
