# Stage 5: complete economic and cost audit

Script: `05_cost_audit.py`. Outputs:
- `cost_registry.csv`: 26 lines (15 CAPEX, 8 OPEX, 2 transfer rows, 1 escalation note);
- `cost_corrections.csv`: corrections and alternatives on 7 fixed networks;
- `reconciled_cashflow.csv`: one ledger per network, with stakeholder split and checks.

Every pilot-derived line was compared with the scope text of the Con Ed filing (pp. 46–51, 88–90).

## A. CAPEX: valid, duplicated, misapplied, omitted

| Line | Verdict | Evidence |
|---|---|---|
| Pipe, $29,318 per route-m (includes excavation and restoration) | **Valid reference.** Same street type, utility and pipe class (2 × 10" pre-insulated steel). Civil works are inside this line and correctly not added again | S13 pp. 48–51 |
| Energy centre, $2.69M fixed | **Valid.** It is the pump room (3 × 125 HP pumps, expansion, controls), not the heat exchanger and not building equipment, so there is no duplication. Oversized for a ~1 MW spur (alternative) | S13 p. 51 |
| Source interface, $1.75M per MW | **Valid.** 3 heat exchangers plus condenser pumps and metering. Linear scaling is approximate; an economies-of-scale exponent of 0.7 makes small networks *more* expensive | S13 pp. 46–47 |
| Building heat pumps (DEA) | Valid, with a caveat: DEA's "installed" cost plus 29% soft costs may partly double count (tested as alternative J5) | DEA |
| **Existing-NYCHA retrofit, $63.8k per apartment** | **Misapplied scope.** It includes one building's hydronic heating and cooling retrofit; our model serves hot water only. **Correct to $39.8k per apartment** | S13 p. 90 ("~$7M") |
| Rebuilt-Fulton building side | **Valid.** New construction carries no retrofit cost (heat pump only, with the air-source baseline capex credited) | model_b L113–117 |
| Contingency 15% and soft costs 29% | **Applied once** per line (verified). The pilot's line items exclude contingency | S13 p. 88–89 |
| Pilot admin, outreach, SCADA/data, 5-year monitoring and evaluation | **Correctly excluded** (non-recurring pilot or research spending, $39M) | S13 Table 11 |
| **Backup boilers in rebuilt towers** | **Omitted → added** (DEA electric boiler: +$68k/yr for Rebuilt Fulton) | DEA |
| **Thermal storage** | **Sized but never costed → removed**; worth ≤ $5k/yr | Stage 4 |
| Electrical upgrades in commercial buildings | **Omitted.** Not quantifiable without a NYC source, so it is flagged. Commercial connections are therefore *understated* | S13 includes them for NYCHA |
| Escalation (3%/yr + 10% tariff) in pilot dollars | About 3% overstatement; immaterial, not corrected | S13 p. 88 |
| Annualisation (25 years, 5%) | **Valid.** Same 25-year life the pilot uses per NY DPS lifecycle cost guidance | S13 fn. 23 |

## B. OPEX
- **Heat-pump electricity:** $222/MWh is consistent with Con Ed's weighted 2024 all-in price (about $210).
- **Source electricity (A17):** **corrected** to 0.367 per MWh extracted.
- **Backup fuel:** valid, with oil now priced as oil.
- **Maintenance:** DEA rates plus 1% of network capital per year; valid.
- **Existing boilers:** kept in both cases, so their costs cancel (correct).
- **Data-center cooling savings:** none credited. The pilot shows +666 MWh of extra electricity, so crediting savings would be unsupported.
- **Tariffs, fence payments and LL97 penalties:** transfers, kept out of societal value.

## C. Corrections vs labelled alternatives (net $/yr; 111 8th Ave plus the external building)

| Case | Dream Hotel | M070 | Hotel | Existing Fulton | Rebuilt Fulton | Phase 2 |
|---|---|---|---|---|---|---|
| Data-corrected reference | −544k | −1,002k | −1,148k | −5,180k | −1,890k | −2,624k |
| + NYCHA hot-water-only cost (accepted) | = | = | = | **−3,575k** | = | = |
| + rebuilt-tower boilers (accepted) | = | = | = | = | −1,958k | −2,692k |
| + remove uncosted storage (accepted) | = | −1,002k | −1,147k | = | −1,963k | −2,696k |
| **+ A17 on the extracted-heat basis = CORRECTED** | **−618k** | **−1,101k** | **−1,277k** | **−3,732k** | **−2,382k** | **−3,184k** |
| Alternative: repeat-project costs (pipe 0.6×, soft costs 15%, 40-year pipe life, interface exponent 0.7) | −438k | −733k | −1,033k | −3,040k | −1,651k | −2,272k |

## D. Reconciled ledger (corrected evidence case; $k/yr)

| Line | Dream Hotel | M070 | Rebuilt Fulton |
|---|---|---|---|
| A avoided baseline heating cost | 578 | 749 | 2,938 |
| B heat-pump + pumping electricity | −292 | −415 | −1,384 |
| C extra data-center electricity (A17) | −233 | −312 | −1,314 |
| D backup fuel | −1 | −4 | −38 |
| **Gross energy saving (A−D)** | **+52** | **+18** | **+202** |
| E maintenance | −92 | −146 | −324 |
| F annualised CAPEX | −579 | −974 | −2,261 |
| **= Net annual societal value** | **−618** | **−1,101** | **−2,382** |
| Data center / users / operator (transfers cancel) | +20 / −4 / −635 | +27 / −54 / −1,074 | +116 / −68 / −2,430 |
| CO₂ avoided (LL97 2024–29; baseline = existing fuel, or air-source heat pumps for rebuilt towers) | 139 t | 384 t | **−926 t** |

The ledger matches the audit evaluator and Model B to $0; the stakeholder positions sum to the societal value.

**Conclusion:** cost misapplication explains **$1.6M/yr, only for existing-NYCHA options**; it does not affect the proposal. The pilot cost basis is applicable, and nothing is double counted. Defensible repeat-project reductions cut deficits by $0.1–0.7M/yr but flip no sign.

The binding problem is **line A minus lines B–D**: with the evidence-based A17, the energy margin before capital is $18–202k/yr for the best options. That is far too small to pay for any street connection.
