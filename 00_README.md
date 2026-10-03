# NYU Hackathon: Data Center Heat Reuse Prep Pack (v3, Site 1)

**Challenge:** "Data Center Heat Reuse: Turning Waste Heat into Community Value" (Grundfos + HDR, Regenerative Design Data Centers track)
**Team:** 3 people | **Time:** 1 day | **Updated:** 2026-10-03, v3, after reading the organizers' full source pack (`sources/`)

> **v3 switches the site from Lansing (Site 2) to 111 8th Ave (Site 1).** The Site 2 version is kept in `archive_v2_site2/`.
> **Why we switched:** the organizers' own documents favor Site 1. See file 04 §1 for the evidence table.

---

## The challenge in one paragraph
Data centers turn almost all their electricity into low-temperature heat, and most of it is thrown away. Design a system that **captures**, **upgrades** and **delivers** that heat to the best local users. It must be **reliable** (the DC's cooling never depends on the heat customer), **economically viable** and **community-centered**. We pick **Site 1: 111 8th Avenue, Manhattan**, an existing multi-tenant carrier hotel.

## Judging rubric (each 1–4, 20 total)
**Technology** · **Presentation** · **Innovation/Creativity** · **Execution** (how well the project *functions*) · **Theme**
→ 12 of 20 points are judged mostly on a **working artifact**. Build a tool; the deck wraps it.

## Our strategy in 3 lines
1. **Site 1 (Chelsea).** The organizers' site pack shows the block just west of 111 8th Ave (Fulton Houses) in the **83rd percentile for poverty and the 92nd for PM2.5**. The organizers' market guide names data centers "near high-density new construction or steam district energy" as a **favourable segment**, and that describes this site exactly. The Lansing pack says "no disadvantaged communities nearby".
2. **"Chelsea Thermal Hub"**, beyond the Con Ed pilot: a working 8,760-hour model + Streamlit app that plans a **phased heat-export hub** from the carrier hotel's condenser loops to the **Fulton/Elliott-Chelsea rebuild** (~5,500 homes), timed to the rebuild's design window. It outputs **5 heat-export agreement terms**. Con Ed's pilot (hot water for 372 apartments) is credited as **Phase 0**.
3. **Honest, like-for-like economics** against what the rebuild would otherwise install: per-building air-source heat pumps, plus steam and gas for commercial users. The app computes the numbers; file 03 lists the assumptions.

## Files
| # | File | Read it when |
|---|---|---|
| 5 | [05_Cheat_Sheet.md](05_Cheat_Sheet.md) | **First.** One page: idea, numbers, gates, owners |
| 1 | [01_Background_Briefing.md](01_Background_Briefing.md) | Concepts, Site 1 facts, the organizers' source-pack findings, policy, data |
| 2 | [02_Team_Workflow.md](02_Team_Workflow.md) | **Switch-over plan for the rest of today**, gates, rubric checklist, deck outline |
| 3 | [03_Individual_Roles.md](03_Individual_Roles.md) | A (model/app), B (economics/carbon), C (place/story/deck) |
| 4 | [04_Strategy_and_Insights.md](04_Strategy_and_Insights.md) | Evidence for Site 1, the big idea, rubric plan, judge Q&A, pitfalls |
| – | `sources/` | The organizers' 23 documents (PDFs, decks) + `sources/txt/` extracted text |
| – | `variable_network.html` | Interactive model graph. **Still uses Site 2 values**; the structure carries over (see 02 §0) |

## Do now (switch-over)
- [ ] All: read 05 (1 page) and 04 §1–2 (10 min). Agree on the one-line pitch.
- [ ] A: re-point the model to Site 1 (source 30–35 °C, building heat pumps on an ambient loop, NYC weather). See 03 → A.
- [ ] B: NYC prices and factors: Con Ed steam tariff, Con Ed electricity, LL97 factors, NYC per-building ASHP costs.
- [ ] C: offtakers from **NYC LL84 + PLUTO** (Fulton, Elliott-Chelsea, Chelsea Market, 111 8th offices, schools); EJ facts from the site pack.
- [ ] Verify: the **HUD Aug-2026 rebuild approval**, the **372-apartment pilot** and its heat source (PSC Case 22-M-0429), and which DC tenants use cooling towers.

> ⚠️ Items marked **(verify)** and all costs are assumptions or come from secondary sources. Organizer documents are cited as **[SP-111]** (111 8th Ave site pack), **[SP-LH]** (Lake Hawkeye site pack), **[DH]** (DATA HEAT market guide), **[HDR]** (HDR heat-reuse deck), **[T5]** (Topic 5 deck), **[CBS]**, **[RII]**, **[DGA]**. File names are listed in file 01 §8.
