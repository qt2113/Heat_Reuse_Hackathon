# Independent review + simplified model ("Model S") — Site 1, 111 8th Avenue

Isolated experiment. It reads `data/` and `outputs/features|model_c` read-only and writes only to this folder.
Test V12 hashes all 263 files outside `experiments/` before and after each run; none changed.

```
cd experiments/simplified_model
python run_experiment.py        # ~20-40 s, writes outputs/, runs 12 validation tests
```

| File | Content |
|---|---|
| `config.yaml` | Every parameter, tagged measured / engineering estimate / assumption. `register:Axx` = the same Low/Base/High register Models A/B/C use |
| `smodel.py` | The whole model (~330 lines): buildings → temperature-bin energy balance → economics → 8 indicators + 6 hard constraints |
| `run_experiment.py` | Screening, configuration ladder, incremental analysis, sensitivity, break-even, controlled comparison, ABC indicator audit |
| `validate.py` | Tests V1–V11 (V12 isolation in the runner) |
| `feature_audit.csv` | Every data item classed A essential / B supporting / C sensitivity / D redundant, with the question it answers |
| `outputs/` | `s_*.csv` results (listed in §9) |

---

## 1. Methodological review (starting from the brief, not from Models A/B/C)

The design question is "how can the data center become a *reliable thermal energy hub* for the *most suitable* offtakers?" That requires three things:

1. **Physics that can say no.** Finite heat, temperature lift, heat-pump and source-side electricity, backup, and seasonal mismatch.
2. **Money separated from transfers.** Use a resource view; tariffs and fence prices are transfers.
3. **A transparent rule for how big the network should be.**

The existing pipeline gets (1) and (2) right. Its physics and accounting are sound: Model S reproduces them to 0.002% (V4). **The problems are in the decision layer and in a few inputs**:

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| R1 | **Every one of the 1,536 enumerated configurations has negative net system value** (100%, both horizons). The equal-weight MCDA still recommends the 7-building, −$9.5M/yr network. | `s_abc_indicator_audit.json` | Min–max normalisation rescales "least negative" to 1, so the composite rewards size. Spearman ρ(score, n_buildings) = +0.55 / +0.67 (today / post-rebuild); ρ(score, net value) = −0.07 / −0.30. |
| R2 | **Several indicators are near-duplicates.** T_lf~T_bk ρ = −1.00, N_co2~N_erf +1.00, E_val~E_fund −0.99, N_co2~N_gas +0.92, T_cov~T_bk +0.94. S_aff is constant after the rebuild. | `s_abc_indicator_correlation.csv` | Environment is counted about 3×, and economics as value + funding gap. Equal dimension weights are not equal in substance. |
| R3 | **CO₂ is a weighted indicator, not a constraint.** The team's phase-2 proposal (rebuilt Fulton) *increases* emissions vs. the all-electric counterfactual at base A17 (−50 t in ABC, −58 t here). It is still recommended. | `s_configurations.csv` R2/R3 | In Model S this is infeasible (HC6) until A17 is verified ≤ 0.17. |
| R4 | **291 Fulton apartments are already served** by the Con Ed pilot loop (85 10th Ave). The existing model counts their hot water as new demand. | pilot filing, `chelsea_uten_pilot_stage2.csv` | Existing Fulton option: heat −2,328 MWh, low-income households −291, cost +$1.87M/yr (`s_difference_decomposition.csv`). |
| R5 | **A17 basis.** The pilot gives 666 MWh_e for 2,680 MWh *delivered* = 0.25 per MWh delivered = **0.37 per MWh extracted**. The models apply 0.25 per MWh *extracted*, i.e. about ⅓ below the cited evidence. | pilot Table 6/8 | A17 alone sets the sign of rebuild CO₂ (break-even 0.17). |
| R6 | **Office "base load" = 39 % of heat.** A20 (a district-network summer/winter ratio) is applied to an office building. All of 111 8th Ave's internal reuse (3.5 GWh) rests on it. | `smodel.nonres_base_share` | With A20 low, C1 CO₂ falls from 198 t to 60 t. Needs 111 8th monthly steam data. |
| R7 | **Route geometry.** 111 8th Ave and Chelsea Market are adjacent full blocks across 9th Ave. Centroid-L1 gives 195–274 m of trench for a ~30–60 m crossing. | PLUTO lot areas | Material for adjacent buildings only. Tested as a sensitivity ("facade" route); it changes no conclusion. |
| R8 | **Storage, 8,760-h chronology and the 13-indicator MCDA add little.** The 2 h tank changes heat by < 0.3%. | V5 | They can be removed without changing any number that matters. |

What is **not** wrong: the cost basis (pilot-anchored, not cherry-picked), H7 (no low-temperature heat into steam radiators), 100% backup, the resource/stakeholder split, and the pilot COP calibration.

## 2. Simplified model architecture

```
LL84 fuel × η ──► useful demand ──► split by temperature class (DHW 60 °C | existing hydronic A18 | new 45 °C | steam radiators → DHW only)
TMYx hours ─────► 290 rows = month × 1 °C outdoor bin × source-outage flag
111 8th electricity × A01 × 0.95 × 0.85 ──► flat available DC heat (18 outage h in the coldest hours)
                     │
     per bin: streams in merit order ($/MWh of source heat), each limited by HP capacity and remaining DC heat
                     │                    (DHW HP = 100% of load; space heat = 75% of design peak; backup = 100% of peak)
                     ▼
  heat delivered, DC heat extracted (+1 %/km loop loss), HP + pump + source-side electricity, backup
                     ▼
  resource economics (4 separated lines) · CO₂ (LL97) · households · stakeholder transfers (cancel)
                     ▼
  6 hard constraints → 8 indicators → incremental ladder (no weights, no normalisation)
```

**Why bins, and what is lost vs. 8,760 h.** Space heat ∝ degree-hours and hot water is flat (as in Model A, since no measured profiles exist). So *without storage*, every hour in a bin is dispatched identically, and the bin balance equals the hourly balance. It matches an independent hourly loop to 0.002% (V3), including a case where supply binds (V2).

Lost:
- **Storage chronology.** < 0.3% of heat (V5).
- **Intra-day hot-water peaks.** These are not modelled by Model A either.
- **Hour-specific outage placement** beyond "coldest hours".

Going coarser is *not* safe. With monthly averages (12 rows), heat delivered stays within 0.3%, but backup heat is **under-estimated by 22–38%** in networks with partial-peak heat pumps (`s_temporal_accuracy.csv`). Peak-hour clipping disappears in the average.

## 3. Essential features and indicators

Full classification: `feature_audit.csv`.

- **Essential inputs (A):** source electricity, A01, A02, A17, LL84 fuel and fuel type, heating-system class, units, coordinates, TMYx + design temperature, steam/gas/electricity prices, pipe/interface/energy-centre/HP/NYCHA-retrofit costs, LL97 factors, NYCHA/FEC facts, pilot calibration.
- **Supporting context (B):** DAC tract, PM2.5/HVI, NOx, governance register, grid Zone J. These do not discriminate between nearby options.
- **Redundant (D):** ERF, E_fund, T_bk (becomes a constraint), T_cov, N_gas, S_eq, S_aff (becomes a constraint), LCOH, DC net (a transfer), storage dispatch.

**Hard constraints (pass/fail, never weighted):**

| ID | Rule |
|---|---|
| HC1 | Cooling independence: extracted ≤ available DC heat in every bin; towers retained |
| HC2 | Backup = 100% of served design peak, 0 MWh unserved (incl. DC outage hours) |
| HC3 | Energy balance closes |
| HC4 | Hot water ≥ 60 °C |
| HC5 | No low-temperature space heat into steam radiators |
| HC6 | **No connected building emits more than its counterfactual** (energy conservation; checked per building so a bad connection cannot hide in a portfolio) |

Affordability for vulnerable users is enforced *by tariff design*. The tariff is capped at the user break-even, and the gap appears as a subsidy line.

**8 indicators (2 per dimension):**

| Dim. | ID | Indicator | Replaces |
|---|---|---|---|
| Technical | I1 | Useful heat delivered (GWh/yr) | T1, N1 |
| Technical | I2 | Recovery-plant load factor (%) — seasonal match / continuity | T_lf, T_bk, T_cov |
| Economic + Delivery | I3 | Net annual system value ($/yr) | E_val, E_fund, E_lcoh |
| Economic + Delivery | I4 | Up-front capital ($M) — financing/delivery risk | C1 |
| Environmental | I5 | Net CO₂ avoided (t/yr) | N_co2, N_erf, N_gas |
| Environmental | I6 | Heat delivered per MWh of added electricity, incl. source side | T2 SCOP |
| Social + Regenerative | I7 | Low-income households served (NYCHA / affordable units only) | S_li, S_eq, S_aff |
| Social + Regenerative | I8 | Community facilities served | S_fac |

Ownership, acceptance and risk allocation are handled in an unscored governance table (`s_governance.csv`).

**Decision rule.** Use the configurations that pass the hard constraints. Grow the network one step at a time. Accept a step only if its incremental abatement cost is ≤ $268/t (LL97 penalty rate, the City's own price signal), *or* if stakeholders explicitly fund its stated cost per low-income household.

## 4. Formulas

All formulas are in `smodel.py`.

- **COP** = 0.45 × T_cond / (T_cond − T_evap), with T_cond = supply + 5 K and T_evap = A02 − 2 − 5 − 5 K. This reproduces the pilot DHW COP: 2.99 vs 3.01 (V7).
- **Per bin, per stream:**
  - q = min(load, HP cap, DC heat left / [(1 − 1/COP)(1 + λL)]), with λ = 1%/km.
  - backup = load − q.
- **Electricity** = q/COP + 1% × q (pumping) + A17 × extracted heat.
- **Net value** = gross conventional savings + avoided conventional capex (ASHP for rebuilt towers) − new opex (all electricity + O&M) − CRF(5%, 25 y) × capex. Capex carries a 1.44 markup (15% contingency + 29% soft costs).
- **CO₂** = baseline fuel × LL97 EF − (all added electricity × 0.289 + backup fuel × EF).
- **Stakeholders:** DC = fence × heat extracted − A17 cost; users = savings − own costs − tariff; operator = tariff − fence − network capex/O&M. The three sum to the net value exactly (V8).

## 5. Representative configurations (review base case)

Base case = register Base values + R4 (Fulton pilot overlap removed) + strict low-income definition + 1%/km loss.

| Config | Members | I1 heat GWh | I2 LF % | I3 net $k/yr | I4 capex $M | I5 CO₂ t/yr | I6 | I7 households | I8 | Feasible |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 Today | – | 0 | – | 0 | 0 | 0 | – | 0 | 0 | ✓ |
| **C1 Internal reuse** | 111 8th DHW/base | 3.47 | 99.8 | **−21** | 1.5 | 198 | 2.03 | 0 | 0 | ✓ |
| C2 + 1 community offtaker | + 335 W 16th (college, 65 m, gas) | 4.28 | 80 | −634 | 8.4 | 250 | 2.01 | 0 | 1 | ✓ |
| C3 Small network (3 ext.) | + Dream Hotel (steam), 335 W 16th, 305 W 16th | 5.45 | 78 | −1,169 | 14.8 | 321 | 2.01 | 0 | 1 | ✓ |
| C4 Large (ABC equal weights) | 7 buildings | 39.3 | 47 | −9,483 | 87.8 | 2,486 | 1.94 | 0 | 2 | ✓ |
| R2 Internal + rebuilt Fulton (2029+) | 111 8th + 2,509 new units | 22.1 | 49 | −1,898 | 30.9 | **−382** | 2.15 | 1,335 | 0 | ✗ HC6 |
| R3 + full rebuild campus | + rebuilt Elliott-Chelsea | 44.4 | 47 | −7,244 | 104 | −1,103 | 2.16 | 2,931 | 0 | ✗ HC6 |

Configurations were chosen by an independent screen of all 649 LL84 buildings with heating fuel and coordinates (`s_screening.csv`, no thresholds or per-type caps). Additions were greedy, ranked by net value + $268/t × CO₂ (`s_greedy_path.csv`).

**The structural finding behind every row:** the energy margin per MWh delivered, *before any capital*, is:
- **+$30/MWh** for the 18 steam-heated buildings (hot water only, under HC5);
- **−$64 to −$73/MWh** for all 631 gas-heated buildings.

The gas/electricity price ratio is 5.7, so a COP of about 3 heat pump cannot beat an 85% boiler. **No external building has positive incremental value**, even with:
- carbon at $268/t;
- A17 = 0, low pipe cost, facade route and building capex halved, all at once (`s_breakeven.csv`).

The cheapest external CO₂ costs about $11,900–14,000/t.

**Internal reuse is the only near-break-even option.** It is net-positive if any one of these holds:
- A17 < 0.21;
- electricity < $210/MWh;
- steam/gas prices +30%;
- 45 °C liquid-cooling return.

Its abatement cost is $105/t, which is below the $268/t benchmark.

## 6. Economics (C1, R2 shown; all configs in `s_economics_stakeholders.csv`)

| $/yr | C1 | R2 |
|---|---|---|
| Gross conventional-energy savings | 485k | 1,981k |
| Avoided conventional capex (ASHP, annualised) | 0 | 919k |
| New operating costs (incl. A17 electricity 133k / 896k) | −402k | −2,604k |
| Annualised infrastructure | −104k | −2,195k |
| **Net project value** | **−21k** | **−1,898k** |
| Transfers: DC / users / operator at pilot tariff | single owner | +536k / −702k / −1,733k |
| User break-even vs operator break-even tariff ($/MWh loop heat) | – | 48 vs 199 → subsidy 1.9M |

**Sensitivity** (`s_sensitivity.csv`, 26 one-at-a-time cases × 6 configurations):
- **Pipe cost (A05 ±):** moves C4 by ±$1.6M but never changes a sign.
- **Building retrofit:** A18 and building capex ×0.5/×1.5 never change a sign.
- **A17:** the most decisive lever. R2 CO₂ goes from +785 t (A17 = 0) to −928 t (A17 = 0.37).
- **Energy prices:** the only levers that flip C1.
- **Source temperature:** a 45 °C liquid-cooling return makes R2 CO₂ positive (+100 t).
- **Grid emission factor:** −50% makes R2 positive (+155 t).

## 7. Controlled comparison with Models A/B/C (`s_controlled_comparison.csv`)

Same buildings, same assumption register, same cost basis:

| Case | ABC stored | Model A rerun, no tank | **Model S, ABC settings** | Model S, review base |
|---|---|---|---|---|
| C1 internal, net $/yr | −20,788 | −20,788 | −20,788 | −20,788 |
| ABC phase 1, net | −1,304,003 | −1,302,440 | −1,302,564 | −1,302,926 |
| ABC 7-building, net | −9,461,191 | −9,450,953 | −9,451,132 | −9,482,780 |
| Existing Fulton + internal, net | −7,054,660 | −7,054,660 | −7,054,650 | **−5,180,957** |
| ABC phase 2, net | −2,780,329 | −2,783,898 | −2,783,973 | −2,788,614 |

**Where the differences come from** (`s_difference_decomposition.csv`):

| Source | Effect |
|---|---|
| Input features | Fulton pilot overlap (R4): the only material change, $1.87M/yr and 291 households on one case |
| Demand estimation | Identical (same LL84 table and A20). R6 is flagged, not changed |
| Heat allocation | Storage omission: < 0.3% heat, ≤ $10k/yr |
| Distribution loss | ≤ $32k/yr |
| Cost assumptions | Identical |
| Optimisation objective / indicator normalisation | **Decisive.** Same physics and money; different recommendation (C4 vs C1) |
| Candidate screening | ABC's ≥ 2 GWh, ≥ 2 years, ≤ 2 per type, 10-building shortlist excludes the steam-heated Dream Hotel (1 LL84 year), the cheapest external connection. This does not change the conclusion, because it too is negative |

**Smaller vs. larger network.** C3 delivers 14% of C4's heat and 13% of its CO₂ at 12% of its net cost. Going C3 → C4 costs $3,840/t incrementally, so neither size is justified on carbon. The team's own phase 1 (hotel at 65 m) adds $1.28M/yr for 322 t (**$3,990/t**). Adding the hotel to phase 2 costs $2,780/t.

## 7b. Does simplification change the substantive conclusions?

**The numbers: no.** Model S reproduces A+B to 0.01%, and the conclusions survive every sensitivity.

**The recommendation: yes.** The shift comes from the decision layer:
- **Under ABC:** the composite picks a large network; the team's report picks phase 1 + hotel → phase 2 + rebuilt Fulton.
- **Under hard constraints + incremental cost-effectiveness:**
  - only internal reuse is justified today;
  - the hotel has no technical role that justifies $1.3M/yr;
  - the rebuild connection becomes **conditional**. It is feasible only if A17 ≤ 0.17 (CO₂ break-even, `s_breakeven.csv`), and it then needs about $0.8–1.1k per low-income household per year of external funding (A17 = 0 → 0.10).

## 8. Recommendation: combine

**Keep from the original:**
- Model A/B physics and cost basis (validated; Model S confirms them);
- the H7 temperature rule;
- the operating-mode stress tests;
- the governance register;
- the 8,760-h model as the *verification* run for the final design.

**Adopt from Model S:**
1. The 6 hard constraints, including **HC6, no building emits more than its counterfactual**, replacing CO₂-as-weight.
2. The 8 indicators, replacing 13. Drop min–max normalisation and the weighted composite; use the incremental ladder with a stated carbon benchmark.
3. Three input corrections:
   - remove the 291 pilot-served Fulton apartments;
   - restate A17 on a consistent basis (0.25 per delivered = 0.37 per extracted);
   - flag the 39% office base-load share (A20) for data.
4. Screening by energy margin and incremental value, instead of size thresholds and per-type caps.
5. The temperature-bin model for fast what-ifs and the frontend (20 ms per configuration). Do not use monthly averages.

**System proposal this implies:**
- **Phase 1 (now):** internal reuse at 111 8th Ave. A heat-recovery interface on the tenant condenser loop feeds building heat pumps for hot water and base load. It is a no-regret step: −$21k/yr, positive under any one favourable lever, $105/t.
- **Phase 1b:** meter A17, A02 and 111 8th's monthly steam use. These three measurements decide everything else.
- **Phase 2 (rebuild design window, 2028–30):** make rebuilt Fulton plant rooms *heat-ready* (45 °C distribution, a stub to 9th/10th Ave). Connect only if measured A17 ≤ ~0.17, or if liquid-cooled racks deliver ≥ 45 °C, and only with a funding instrument (about $1k per household per year, 1,335 households).
- **Do not build** the hotel spur or a commercial network on gas buildings at current prices. Revisit if the gas/electricity price ratio falls below ~3 or the grid factor halves.
- **Reliability:** the DC keeps 100% of its towers (HC1), and buildings keep 100% backup (HC2). In the rebuilt towers that backup is electric boilers. A DC outage on the design day therefore raises rebuilt Fulton's electric demand from about 2 MW (heat pumps) to 5.8 MW (12.8 MW for the full campus). Con Ed must plan for that coincident peak.

## 9. Outputs

| File | Content |
|---|---|
| `s_screening.csv` | All 695 buildings; 649 evaluated standalone (energy margin, incremental value, abatement cost, data-quality flag) |
| `s_configurations.csv`, `s_monthly.csv`, `s_greedy_path.csv` | Configurations: indicators, constraints, monthly balance, how they were built |
| `s_incremental.csv`, `s_economics_stakeholders.csv`, `s_breakeven.csv`, `s_sensitivity.csv` | Decision analysis |
| `s_controlled_comparison.csv`, `s_difference_decomposition.csv` | Comparison with ABC |
| `s_abc_indicator_correlation.csv`, `s_abc_indicator_audit.json` | Audit of the 13 ABC indicators |
| `s_temporal_accuracy.csv` | Bin width vs accuracy |
| `s_governance.csv` | Unscored governance table |
| `s_validation.csv` | 12/12 tests pass |
| `run_manifest.json` | Run metadata |

**Limitations:** same as Model A for demand shapes (flat hot water, degree-hour space heat), the hydronic assumption for gas buildings, and the rebuild demand (A03/A19). The facade route uses a lot-area approximation. The 45 °C liquid-cooling case uses Carnot-fraction COPs, which are optimistic at low lift (indicative only).
