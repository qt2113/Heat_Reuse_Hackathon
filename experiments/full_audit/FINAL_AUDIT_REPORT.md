# Final audit report: Site 1 data-center heat reuse (111 Eighth Avenue)

**Scope:** an end-to-end audit, from source documents through cleaning, features, physics and costs to the decision. All of it ran in `experiments/full_audit/`.
- **Baseline:** commit `9aa63bc` plus the uncommitted working tree, recorded in `00_baseline/`.
- **Isolation:** after the audit, all 199 data, output and model files hash identically to the baseline, and no file was added. Models A/B/C and their outputs are untouched.
- **Reproduce:** `python build_source_registry.py`, then `02_data_quality.py`, `03_feature_ablation.py`, `04_physical_tests.py`, `05_cost_audit.py`, `06_final_eval.py`.

**Bottom line:** the physics and the cost basis are sound. **The original −$9.46M/yr headline was mostly a decision-layer artefact.** The weighted score picked a large network; $8.3M of the deficit comes from that choice, not from data, physics or costs.

After every justified correction, **no network with an external offtaker is financially viable at Site 1** on the evidence. The best defensible external network needs about **$0.6–1.1M/yr** of support, or **$0.4–0.7M/yr** with repeat-project costs. Break-even depends on one unmeasured fact: whether 111 8th Ave can supply warm heat without extra cooling electricity.

---

## Q1. Can we trust our datasets and sources?
**Mostly yes, with three inputs to correct and four to mark uncertain.** See `01_SOURCE_AUDIT.md` and `source_registry.csv` (40 rows, authority and applicability rated separately).

- **Authoritative and applicable (A):**
  - LL84 annual fuel use;
  - TMYx and ASHRAE design conditions;
  - NYCHA data book;
  - LL97 factors (as accounting factors);
  - Con Ed steam tariff;
  - EIA-861 utility averages;
  - unit conversions (verified: 0 mismatches in 5,000+ values).
- **Authoritative but transferred (B), and acceptable:**
  - The Con Ed pilot filing. Its pipe, energy-centre, interface, contingency and lifetime basis apply to Manhattan street works (verified against filing pp. 46–51 and 88–90).
  - EIA electricity price, consistent with Con Ed's weighted all-in price of about $210/MWh.
  - DEA heat-pump costs.
- **Correct:**
  - **A17:** right source, wrong basis.
  - **Oil** priced as gas.
  - **NYCHA retrofit cost** scope.
- **Mark uncertain:**
  - A01 data-center share;
  - heating emitter type inferred from fuel;
  - A20 base-load share for 111 8th Ave (an office, no monthly steam data);
  - EIA *state* gas price for NYC.

## Q2. Are we cleaning and combining the data correctly?
**The pipeline is correct; four steps introduced bias.** See `02_DATA_QUALITY.md` and `cleaning_audit.csv` (23 checks).
- **Pilot overlap:** 291 Fulton apartments already served by Con Ed's pilot were counted as new demand.
- **Oil buildings** (134, including M070 at 97% oil) were priced and emission-factored as gas.
- **Isolated anomalous LL84 years** inflated the 3-year mean. For the hotel, 2023 = 8,483 vs 4,621 / 4,839 MWh, confirmed by monthly spikes.
- **Single-year records were excluded rather than flagged.** That dropped the steam-heated Dream Hotel, from the only fuel class with a positive energy margin. Together with the 2 GWh and per-type rules, the screen **favoured large gas buildings**, which have a negative margin.

Correcting all four improves affected networks by $0.16–1.9M/yr and **changes no sign**. No double counting of buildings or households was found in any recommended network (32 same-lot record pairs exist, none used).

## Q3. Are all features necessary? What is the simplest defensible framework?
**No.** See `03_FEATURE_AUDIT.md`, `feature_ablation.csv` and `recommended_minimal_features.csv`.
- **Exact duplicates:** T_lf/T_bk (ρ = −1.000), E_val/E_fund (−0.995), N_co2/N_erf (0.997), N_erf/heat (1.000).
- **Size bias:** the 13-indicator score rewards size (ρ with building count +0.55 / +0.72) and ignores value (ρ with net value −0.07 / −0.39). Removing any single indicator changes the winner in 8/13 cases.
- **Fewer indicators don't fix it.** An 8- or 5-indicator min-max score still picks a 10-building network. **The cause is normalisation plus compensatory summing.**
- **Simplest defensible framework:**
  - **Hard constraints:** at least 1 external; cooling independence; 100% backup and 0 unserved; temperature compatibility; **net CO₂ ≥ 0** against a stated baseline; **NYCHA no worse off**.
  - **Reported in physical units:** heat recovered and delivered, net societal value (funding gap shown separately), CO₂, low-income households (NYCHA/affordable only) and community facilities.
  - **Decision rule:** least public support per unit of benefit. Weights only as a sensitivity view.
  - **Removed:** S_eq (it counts commercial heat in a disadvantaged tract as equity), T_bk, T_cov, E_lcoh, E_fund, N_erf, N_gas.
  - **S_aff becomes a constraint.** Dropping it picks a −$25.4M network, so it is a real constraint, not noise.

## Q4. Is the economic model accounting for real costs correctly?
**Yes, with one misapplied cost and two omissions.** See `05_COST_AUDIT.md`, `cost_registry.csv` (26 lines), `cost_corrections.csv` and `reconciled_cashflow.csv`.
- **Valid and applied once:**
  - pipe $29.3k/route-m, including civil works;
  - energy centre (pump room);
  - source interface (heat exchangers);
  - building heat pumps;
  - 15% contingency (pilot line items exclude it);
  - 29% soft costs;
  - 25-year life (NY DPS lifecycle cost convention, as the pilot uses).
  - $39M of non-recurring pilot spending (administration, outreach, SCADA, monitoring) is **correctly excluded**.
  - Rebuilt Fulton correctly carries **no** retrofit cost.
- **Misapplied:** the $63.8k/apartment NYCHA retrofit includes one building's heating and cooling retrofit. Hot-water-only service costs about $39.8k/apartment, so existing-Fulton options were overstated by **$1.6M/yr**.
- **Omitted:**
  - backup boilers in the rebuilt towers (+$68k/yr), now added;
  - 2-hour storage, which was sized but never costed (now removed; worth ≤ $5k/yr);
  - electrical upgrades in commercial buildings: understated, but no NYC source to quantify them.
- **Legitimately reducible (labelled alternatives, not corrections):**
  - pipe at 0.6× the pilot cost;
  - 15% soft costs;
  - 40-year pipe life.
  - Together they cut deficits by **$0.1–0.7M/yr** without flipping any sign.
  - Interface economies of scale *raise* the cost of small networks.
- **Ledger:** reconciles to $0 against Model B. The stakeholder positions (data center, users, operator) sum to the societal value; tariffs and LL97 penalties are transfers.

## Q5. After correcting everything, what is the best defensible external-offtaker proposal?
Every step used the same 27 networks (`final_comparison.csv`, `final_recommendation_by_step.csv`). **No external network is positive in any step**, including the future liquid-cooling case with repeat-project costs, where the best is −$66k.

**Recommended network: 111 8th Ave in-building reuse + M070 public school (153 m), with Dream Hotel (60 m, steam) as a near-free add-on once its data is confirmed.**

| Fully audited (evidence-supported reference) | 111 8th + M070 | + Dream Hotel |
|---|---|---|
| External offtaker(s) | M070 (NYC public school, oil-heated) | M070 + Dream Hotel (steam, hot water only) |
| Heat recovered / delivered | 3.82 / 5.63 GWh | 4.28 / 6.29 GWh |
| Energy cost per MWh delivered | $130 | $129 |
| LCOH | $328/MWh | $311/MWh |
| CAPEX (annualised) | $13.7M ($0.97M/yr) | $14.0M ($0.99M/yr) |
| OPEX (O&M + electricity + backup) | $0.88M/yr | $0.96M/yr |
| **Net annual societal value** | **−$1.10M** | **−$1.12M** |
| Funding gap (operator at pilot tariffs / minimum with all parties no worse off) | $1.07M / $1.10M | $1.09M / $1.12M |
| CO₂ avoided (LL97 2024–29; baseline = existing fuel) | 384 t (228 t if M070 has steam radiators) | 406 t |
| Community beneficiaries | 1 public school (fuel-oil boiler displaced at a school); 0 low-income households | same |
| Cost per tonne of CO₂ | $2,868 | **$2,751 (lowest of all 27 networks)** |
| Repeat-project costs | −$0.70M/yr | −$0.72M/yr |
| Future liquid cooling (45 °C, A17 = 0) | −$0.69M/yr, 949 t | −$0.65M/yr, 1,038 t |

**Why this network:**
- **Constraints:** it passes every hard constraint.
- **Cost per tonne:** it has the lowest cost per tonne of CO₂ among networks that do.
- **Community benefit:** it replaces combustion of fuel oil at a public school, a visible local-air and community benefit.
- **Governance:** the owners are public (NYC DOE).
- **Small risk:** CAPEX is $14M.

Dream Hotel alone is cheaper (−$0.62M) but has no community value, only 139 t of CO₂, and a single year of LL84 data.

**Rebuilt Fulton fails the CO₂ constraint** on evidence: −926 t at A17 = 0.367, and the pilot itself uses about 40% more electricity than air-source heat pumps. It becomes the best option (+1,427 t, 1,335 low-income households, −$0.07M to −$0.68M/yr) **only** if the data center supplies heat at about 45 °C without chillers, i.e. warm-water liquid cooling.

**Break-even of the recommended network** (`break_even_recommended.csv`): none is reachable with a single realistic change.
- Needs any one of: A17 ≤ −0.93, electricity < $0/MWh, oil price ≥ $552/MWh, or a carbon value of $2,750/t.
- Or a capital grant of about **$15.5M upfront**, which is more than the CAPEX, because operations alone barely break even (gross energy saving +$19–27k/yr).

**What caused the original negative results** (`decomposition.csv`):

| Cause | Effect on the reported result |
|---|---|
| **Decision layer / feature weighting** (score picked a 7-building network) | **−$8.30M/yr**, the dominant cause |
| Data quality and interpretation (outlier years, pilot overlap, oil as gas) | +$0.16M (recommended network); +$0.32M (7-building) |
| Misapplied or missing costs | ≈ $0 (recommended); +$1.6M only for existing-NYCHA options |
| Engineering assumption corrected (A17 basis) | −$0.10M (recommended); −$0.66M (7-building) |
| **Genuine economic barrier remaining** | **−$1.10M/yr** (recommended); −$9.79M (7-building) |

The genuine barrier is physical and price-driven. With the pilot's evidence for source electricity, delivered heat costs about **$127–130/MWh in electricity alone**. Steam ($140/MWh of heat) only just beats that, gas (about $46) is far cheaper, and oil (about $123) comes close. Nothing is left over to pay for street connections.

---

## Corrections ranked by material impact

| # | Change | File / location | Original | Issue | Evidence | Correction | Impact | Confidence |
|---|---|---|---|---|---|---|---|---|
| 1 | **Decision rule** | `model/model_c.py` `normalise()` L254, `choose()` L278; frontend CONTRACT rule 3 | 13 min-max indicators, weighted sum | Rewards size, ignores value; duplicates; fragile | ρ = +0.55 / +0.72 with size; winner changes in 8/13 single drops | Hard constraints + least-support rule; weights for sensitivity only | **$8.3M/yr** of the headline deficit; changes the recommended network | High |
| 2 | **A17 basis + A02 coupling** | `model/model_a.py` L159, L199; `data/reference/assumptions_scenarios.csv` A17 | 0.25 × heat extracted; "advanced" = 35 °C + A17 0 | Pilot 666 MWh is per MWh *delivered*; high capture temperature needs compressors unless liquid cooling | S13 Table 8, pp. 69–70 | 0.367 per MWh extracted; advanced case = 45 °C liquid cooling only | −$0.06 to −0.66M/yr; **Rebuilt Fulton CO₂ −373 → −926 t (fails CO₂ ≥ 0)** | High |
| 3 | **NYCHA retrofit scope** | `model/model_b.py` L66 `apt_capex` | $63.8k/apt | Includes one building's heating and cooling retrofit; model serves hot water only | S13 p. 90 ("~$7M") | $39.8k/apt for hot-water-only existing NYCHA | +$1.6M/yr on existing-Fulton options | Medium |
| 4 | **Data cleaning** | `model/features.py` L83 (mean), `model/model_b.py` L108/L117/L123–126 (price and emission factor by fuel), `remove_pilot_overlap` | Mean of all years; oil = gas; pilot apartments counted | Outlier years; oil mispriced (CO₂ understated about 40%); double-claimed demand | LL84 monthly; LL97 oil factor; EIA oil; S13 loads | Median rule for isolated anomalies; price and factor by fuel share; subtract pilot loads | +$0.16M per affected network; +$1.87M existing Fulton; +178 t for M070 | High |
| 5 | **Screening flags** | `model/model_c.py` L98 (`n_years < 2` excludes) | Exclude single-year records | Drops the steam-heated Dream Hotel | Independent screen; positive steam margin | Flag, don't exclude | Changes the cheapest external offtaker | High |
| 6 | Missing costs | `model/model_b.py` (no storage or boiler capex); `config/scenarios.yaml` L32 `tank_hours: 2` | Storage sized, not costed; rebuilt boilers not costed | Uncosted components | DEA electric boiler | Tank 0 h; add boiler capex | −$73k/yr on Rebuilt Fulton | High |
| 7 | S_eq | `model/model_c.py` L189 | Commercial heat in a DAC tract counts as equity | Misattribution | DAC is a tract property | Remove; low-income = NYCHA/affordable only | Scoring only | High |
| 8 | Emitter and base-load uncertainty | `model/features.py` L109; `nonres_base_share` | All gas buildings hydronic; 39% base load for 111 8th | Unverified | PLUTO year built; LL84 monthly (gas only) | Flag; survey M070 / Dream Hotel / 111 8th | M070: −$0.94M to −1.10M; 228–384 t | — (uncertainty) |

## Top five changes to implement before submitting
1. **Replace the weighted MCDA selection with hard constraints plus a least-support rule.** Keep weights only as an interactive sensitivity view. This removes the $8.3M artefact and makes the recommendation stable.
2. **Correct A17 to 0.367 per MWh extracted and tie it to capture temperature.** Present Rebuilt Fulton as *conditional* on measured source electricity and capture temperature, or on liquid cooling. Do not present it as the base proposal: it fails the CO₂ constraint on current evidence.
3. **Apply the four data fixes:** price and count oil as oil; median rule for anomalous years; subtract the Con Ed pilot's Fulton loads; flag, don't exclude, single-year records.
4. **Fix the cost lines:** NYCHA hot-water-only retrofit at $39.8k/apt; cost or remove storage; cost the rebuilt-tower backup boilers. Show repeat-project costs as a labelled alternative only.
5. **Restate the proposal honestly:** 111 8th Ave reuse + **M070 school** (+ Dream Hotel). About $1.1M/yr of support (about $0.7M with repeat-project costs), 380–410 t CO₂/yr, one public school. Two measurements decide whether Site 1 can go further:
   - metered source-side electricity and capture temperature at 111 8th Ave;
   - heating-system surveys of M070, Dream Hotel and 111 8th Ave.
