# Stage 3: feature necessity and four-dimension audit

Script: `03_feature_ablation.py`. It runs on the validated `c_configurations.csv` (1,536 configurations), so every variant uses identical A/B physics and economics. Outputs:
- `feature_ablation.csv`;
- `03_redundancy_pairs.csv`;
- `recommended_minimal_features.csv`: every feature with its definition, source, evidence quality, duplicates, ablation effect and recommendation.

## 1. Redundancy (Spearman correlation on technically feasible configurations, |ρ| ≥ 0.85)

| Pair | Today | After rebuild | Meaning |
|---|---|---|---|
| T_lf ↔ T_bk | **−1.000** | – | Load factor and backup dependency are the same information |
| E_val ↔ E_fund | **−0.995** | −0.952 | Funding gap = −net value + transfers: economics counted twice |
| N_co2 ↔ N_erf | **0.997** | – | CO₂ and energy reuse are the same quantity |
| N_erf ↔ heat delivered | **1.000** | 0.999 | The energy reuse factor is a heat-volume measure |
| N_co2 ↔ number of buildings | 0.89 | – | The environmental dimension is a **size proxy** |
| E_fund ↔ S_li | 0.96 | 0.90 | Social and funding move together (NYCHA) |

## 2. Ablation results

| Test | Result |
|---|---|
| Drop any single indicator (13 runs per horizon) | Winner changes in **8/13 today** and **4/13 after the rebuild** → the recommendation is fragile |
| Weight grid (286 weight vectors) | 18–38 different winning networks |
| Size bias of the full 13-indicator score | ρ(score, number of buildings) = **+0.55 / +0.72**; ρ(score, net value) = **−0.07 / −0.39** |
| Drop duplicates (T_bk, N_erf, E_fund) | Winner changes in both horizons |
| Model S, 8 indicators (min-max, equal weights) | Still picks a 10-building network today (−$25.4M); after the rebuild, a 6-building network with **negative CO₂** |
| Minimal 5 indicators (min-max) | Still picks 10 buildings today; picks 111 8th alone after the rebuild |
| **Hard constraints + maximise net value** (≥ 1 external, technically feasible, CO₂ ≥ 0) | Picks the single cheapest external (M070, −$1.14M/yr). One quantity decides; weights play no role |

**Interpretation:** the size bias and fragility come from **min-max normalisation plus compensatory summing**, not from the number of indicators.
- Min-max rescales "least negative" to 1.
- Size-correlated indicators (CO₂, energy reuse, households) then dominate.
- Removing indicators only changes which size proxy wins.

The only robust decision rule we found takes the value-relevant quantities as reported outcomes and the binary requirements as constraints.

**A necessary feature that reveals an inconvenient constraint:** S_aff (NYCHA bill change). Dropping it today flips the winner to a 10-building network that loses $25.4M/yr and raises NYCHA bills. It is not noise. It is the affordability constraint, and it belongs in feasibility, not in a weighted average.

## 3. Recommended framework (simplest defensible)

**Hard constraints (pass/fail, never weighted):**

| ID | Constraint | Source |
|---|---|---|
| HC0 | At least 1 external offtaker | Challenge rule |
| HC1 | Data-center cooling independence: towers retained; network takes no more than the available heat in each hour | Model A H1/H3 |
| HC2 | Backup at 100% of the served peak; 0 MWh unserved, including the 72 h data-center outage | Model A H2, M2–M4 |
| HC4/5 | Hot water ≥ 60 °C; no low-temperature heat into steam radiators | Model A H4/H7 |
| HC6 | Net CO₂ ≥ 0 against the stated baseline (existing fuel; all-electric air-source heat pumps for rebuilt towers) | Model B |
| HC7 | NYCHA households no worse off (tariff ≤ break-even) | Model B H6 / Term 4 |

**Reported outcomes, one or two per dimension, shown in physical units and not normalised:**
- **Technical:** heat recovered (MWh), heat delivered (MWh), recovery-plant load factor (%)
- **Economic:** net annual societal value ($/yr) and, separately, the funding gap (a transfer view)
- **Environmental:** net CO₂ (t/yr), with its baseline stated
- **Social:** low-income households (NYCHA / affordable units only); community facilities

**Removed or merged:** T_bk (duplicate of T_lf → HC2), T_cov, E_lcoh, E_fund, N_erf and N_gas (reported only), S_eq (it counts commercial heat in a disadvantaged tract as equity), S_aff (→ HC7).

**Decision rule:** among networks that pass HC0–HC7, pick the one with the **lowest public support per unit of measurable community and CO₂ benefit**. Dimension weights stay in the frontend as a *sensitivity view* only; they don't select the recommendation.
