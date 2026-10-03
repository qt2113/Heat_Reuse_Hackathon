# 02: Whole-Team Workflow (1 day, 3 people), v2

> **v2 changes (after the peer review and the full rubric):** the deliverable is now a **working tool + a short deck**, not a deck alone. Technology + Innovation + Execution = **12 of 20 points** and are judged mostly on the artifact. The deck wraps the tool.
>
> Times assume a 9:00 start and a ~21:00 submission. Shift the blocks if needed; **keep the gates**.
>
> Roles (details in `03_Individual_Roles.md`):
> - **A**: Model and app builder (Python simulation + Streamlit)
> - **B**: Economics, carbon and data. Owns the numbers/config and helps A with the optimizer after 14:30
> - **C**: Place, story and deck. Owns the map, offtakers, conditions-of-approval text, the hook and the deck

---

## 0. Before the day (night before, ~1 h each; high impact)

| Who | Task |
|---|---|
| All | Read `05_Cheat_Sheet.md` (1 page), then `01_Background_Briefing.md` |
| All | **Check the rules:** is pre-written code allowed? What is the pitch length? What is the submission format (link, video, PDF)? Ask the organizers, or ask at 09:00 |
| A | Install Python, `streamlit`, `pandas`, `numpy`, `plotly`, `pydeck`/`folium`. Create a GitHub repo + Streamlit Community Cloud account. **If allowed:** write the ~50-line skeleton (load weather → hourly demand → storage loop). **If not:** prepare formulas only |
| B | **Download a typical-year hourly weather file for Ithaca/Lansing** (NREL TMY3 or a NOAA hourly CSV) into the repo. Collect the price and emission-factor table (03 → B, Step 1) |
| C | Pre-load map layers: Lansing parcels/zoning (Tompkins County GIS), Lansing school campus, hamlets, ACS heating-fuel data. Measure **plant site → school** distance (verify, may be several km) |

### Shared workspace
```
/HeatReuse_Hackathon
  app/                ← Streamlit app (A)  → hosted on Streamlit Community Cloud
    data/weather.csv  ← offline, no live API calls in the demo
    data/offtakers.csv← from C: name, lat, lon, type, annual MWh, peak kW, supply T, distance, equity flag
    config.yaml       ← from B: prices, emission factors, costs, discount rate (= the "numbers sheet")
  research/           ← one notes doc per person, with sources
  deck/               ← 8–10 slides (C edits)
  README.md           ← screenshots + how to run (A, at the end)
  backup_video.mp4    ← recorded 18:00
```
**Rules:**
- Every number lives in `config.yaml` or `offtakers.csv`, each with a source or an ASSUMPTION note.
- Use power units (kW/MW) and energy units (MWh/GWh) correctly.

---

## 1. Timeline overview

```
09:00 Kickoff (confirm Site 2, pitch length, rules) ─ 09:30 Sprint 1 ─ ✔G0 10:30 data contracts fixed
10:30 Build sprint ─ ✔G1 13:00 MVP simulation runs end-to-end (or fall back) ─ 13:00 lunch at desks
13:15 Sprint 3: app + economics + deck ─ ✔G2 15:30 app v2 works ─ ✔G3 16:00 FEATURE FREEZE
16:00 Polish + optimizer stretch + deck ─ ✔G4 17:30 full draft ─ 18:00 record backup video + deploy
18:15 Rehearsal ×2 with live demo ─ 19:45 buffer ─ 20:30 submit
```

---

## 2. Block by block

### 09:00–09:30 | Kickoff (all)
- Re-read the brief + rubric (5 categories × 4 points).
- **Confirm site: Site 2 (Lansing) is the default.** Run the scoring table in file 04 §1 in 5 minutes. Only switch if the team finds a decisive reason. **The decision is final at 09:30.**
- Confirm the pitch length → set the slide count (5 min ≈ 6 slides + demo; 10 min ≈ 9 slides + demo).
- Read the **one-line pitch** aloud (file 04) and agree on it.

### 09:30–10:30 | Sprint 1: fix the data contracts
| A | B | C |
|---|---|---|
| Skeleton runs on the weather file: hourly temperature → degree-hours | `config.yaml` v1: prices, emission factors, unit costs, discount rate | `offtakers.csv` v1: greenhouse (hypothetical tenant), school, town facilities, moratorium-area housing (Phase 2), hamlets. Columns as above |

**✔ Gate G0 (10:30):** the CSV/YAML columns are frozen. After this, B and C change **values**, not **structure**.

### 10:30–13:00 | Build sprint
| A | B | C |
|---|---|---|
| Hourly simulation: demand per offtaker → cascade (greenhouse direct HX, heat pump for the rest) → storage state of charge → backup → KPIs + **energy-balance check** | LCOH function, ASHP and propane like-for-like comparison, carbon function. Hand A pure Python functions | Map figure; offtaker scoring; stakeholder list; draft **conditions-of-approval language** (5 lines); deck skeleton |

Stand-up at **11:45** (5 min).

**✔ Gate G1 (13:00): does the MVP run end-to-end and print coverage %, LCOH, tCO₂, ERF and a balance-check pass?**
- **Yes →** continue to the app.
- **No →** **fallback:** freeze the model at monthly resolution, export charts from what works, and put effort into the deck. Keep any simulation charts that do work.

### 13:15–16:00 | Sprint 3: app + economics + deck
| A | B | C |
|---|---|---|
| Streamlit app v2: map, sliders (heat pump MW, tank MWh, pipe km, electricity price, heat-recovery funding by DC on/off, offtaker checkboxes), KPI tiles for **DC / users / community**, the 5 match dimensions labeled with the brief's words, input validation | Feed real values; sensitivity runs; from **14:30** help A with the **grid-search optimizer** (stretch) | Deck v1 (8–10 slides); decide which slides the **demo replaces**; write the hook |

**✔ Gate G2 (15:30):** app v2 runs locally with the preloaded Lansing scenario.
**✔ Gate G3 (16:00): FEATURE FREEZE.** Only bug fixes and polish after this.

### 16:00–17:30 | Polish
- **A:** bug fixes, no-NaN guards, deploy to Streamlit Cloud, README with screenshots.
- **B:** final numbers, assumptions + sources appendix; optimizer results if done (else skip).
- **C:** deck finished; sample "condition of approval" slide; speaker notes.

**✔ Gate G4 (17:30):** full draft deck + hosted app link work.

### 17:30–18:15 | Backup
- Record a **2–3 min screen video** of the demo (the safety net if the Wi-Fi or app dies).
- Export the deck to PDF.

### 18:15–19:45 | Rehearsal ×2 (with live demo)
- Run 1, timed → 10 min feedback → Run 2, timed.
- Demo driver = A, narrator = C, numbers/Q&A on cost = B.
- Practice the **demo script**:
  1. Default scenario.
  2. Move one slider (e.g., "DC funds the heat recovery station: off → on") and show LCOH drop.
  3. Show the balance check ✔.
  4. Show the conditions output.

### 19:45–20:30 | Buffer → submit early

---

## 3. Communication rules
1. Configs are the truth. Announce value changes in chat.
2. Stand-ups are 5 minutes, blockers only (11:45, 14:30, 16:00).
3. **20-minute rule:** if a number or bug blocks you for 20 minutes, use a labeled assumption or drop the feature.
4. C owns the deck file; A owns the app repo; B owns `config.yaml`.
5. No new features after 16:00. Ideas go to "future work".

---

## 4. Rubric checklist (20 points)

| Category | What earns a 4 | Where we deliver it | Owner |
|---|---|---|---|
| **Technology** | Cutting-edge or superbly applied, sophisticated | Hourly 8760 simulation, temperature-dependent COP, temperature cascade (greenhouse direct HX), storage dispatch, grid-search optimizer | A (+B) |
| **Innovation** | Novel approach, exceptional outcomes | **"From moratorium to mandate"**: the tool turns a DC application into heat-reuse conditions of approval | C (+A) |
| **Execution** | Works flawlessly, polished | Narrow, offline, validated app; energy-balance ✔; hosted link; README; backup video | A |
| **Theme** | Theme is integral | Regenerative framing (coal plant → clean heat commons); the brief's 5 match dimensions + 3 stakeholders inside the app | C |
| **Presentation** | Clear, engaging, professional | 30-s hook, live demo replacing chart slides, takeaway titles, 8–10 slides | C |

### Brief requirements (keep for Theme)
- [ ] Site + local-context justification
- [ ] Architecture diagram
- [ ] Capture point / temperature / capacity
- [ ] Offtakers + selection criteria
- [ ] Infrastructure
- [ ] Operating approach
- [ ] Temperature / capacity / timing / seasonality / continuity
- [ ] Cooling reliability protected
- [ ] Heat continuity (backup sized to the **full peak**)
- [ ] Value for DC / users / community
- [ ] CAPEX/OPEX
- [ ] Revenue/connection model
- [ ] Ownership/risks (backup slide)
- [ ] Carbon / efficiency / resources
- [ ] Equity / acceptance

### Deck outline (8–10 slides)
1. **Hook + one-line pitch**
2. Lansing context: coal plant, gas moratorium, data-center application, community concerns
3. Our idea: **from moratorium to mandate** (tool → conditions)
4. System architecture + temperature cascade (diagram)
5. **LIVE DEMO** (replaces the matching, sizing and economics slides)
6. Economics, like for like: network vs ASHP vs propane
7. Reliability & continuity: the DC is never dependent; backup covers the full peak
8. Value for DC / users / community + regenerative framing
9. Sample condition of approval (5 lines) + phasing
10. Close: three numbers + one line

Backup slides: RACI, risk register, sensitivity, assumptions/sources, Site 1 fallback, rejected offtakers.

---

## 5. Risk plan for the day
| Risk | Mitigation |
|---|---|
| Simulation not working by 13:00 | Fall back to monthly resolution (G1) |
| App breaks during the pitch | Backup video + PDF screenshots |
| Wi-Fi down | App runs locally; data is offline |
| Numbers inconsistent | Energy-balance check in the app; B's sanity checks |
| Scope creep | Feature freeze at 16:00 |
| Team member stuck | Stand-ups; the person furthest ahead takes one task |
