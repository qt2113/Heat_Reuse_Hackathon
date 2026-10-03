# NYU Hackathon: Data Center Heat Reuse Prep Pack (v2)

**Challenge:** "Data Center Heat Reuse: Turning Waste Heat into Community Value" (Grundfos + HDR, Regenerative Design Data Centers track)
**Team:** 3 people | **Time:** 1 day | **Prepared:** 2026-10-03, v2 after a 3-round peer review + the full judging rubric

---

## The challenge in one paragraph
Data centers turn almost all their electricity into low-temperature heat, and most of it is thrown away. Design a system that **captures**, **upgrades** and **delivers** that heat to the best local users. It must be **reliable** (the DC's cooling never depends on the heat customer), **economically viable** and **community-centered**. Pick one site: Site 1, 111 8th Ave in Manhattan (existing), or Site 2, Lake Hawkeye / TeraWulf in Lansing NY (proposed).

## Judging rubric (each 1–4, 20 total)
**Technology** · **Presentation** · **Innovation/Creativity** · **Execution** (how well the project *functions*) · **Theme**
→ 12 of 20 points are judged mostly on a **working artifact**. Build a tool; the deck wraps it.

## Our strategy in 3 lines
1. **Site 2 (Lansing).** Greenfield design freedom, the gas-hookup moratorium and the coal → clean-heat story. (Site 1 = "scale the Con Ed pilot", which would score as derivative.)
2. **"From Moratorium to Mandate":** a working 8760-hour simulation + Streamlit app that turns a DC application into **heat-reuse conditions of approval**, demoed on the **Lansing Thermal Commons** (greenhouse via direct heat exchanger + school + town + Phase 2 housing).
3. **Honest, like-for-like economics:** network ~$95/MWh vs per-home ASHP ~$160–230 vs propane $125 (fuel only).

## Files
| # | File | Read it when |
|---|---|---|
| 5 | [05_Cheat_Sheet.md](05_Cheat_Sheet.md) | **First.** One page: idea, numbers, gates, owners |
| 1 | [01_Background_Briefing.md](01_Background_Briefing.md) | Night before: concepts, both sites, policy, precedents, data sources |
| 2 | [02_Team_Workflow.md](02_Team_Workflow.md) | Kickoff: timeline with gates, the rubric checklist, deck outline |
| 3 | [03_Individual_Roles.md](03_Individual_Roles.md) | After roles: A (model/app), B (economics/carbon), C (place/story/deck) |
| 4 | [04_Strategy_and_Insights.md](04_Strategy_and_Insights.md) | Site rationale, the big idea, rubric plan, judge Q&A, pitfalls |

## Do tonight
- [ ] Check the rules: is pre-written code allowed? Pitch length? Submission format?
- [ ] A: Python env + repo + Streamlit Cloud account (+ skeleton if allowed)
- [ ] B: download an hourly typical-year weather file for Ithaca/Lansing; fill price/emission table
- [ ] C: map layers; measure the **plant → Lansing school** distance

> ⚠️ Items marked **(verify)** and all costs are assumptions or come from secondary sources. Check them against the organizers' packet.
