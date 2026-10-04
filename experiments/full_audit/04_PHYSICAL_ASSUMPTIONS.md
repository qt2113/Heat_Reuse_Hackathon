# Stage 4: physical model and assumption audit

Script: `04_physical_tests.py`. Outputs:
- `physical_tests.csv`: 23 targeted tests × 6 fixed networks;
- `energy_balance_checks.csv`.

All tests apply the Stage 2 data corrections and use reference costs. Models A and S were reviewed, not rebuilt.

## Energy conservation: verified
For all six networks:
- heat-pump output = heat extracted from the data center + heat-pump electricity;
- delivered heat = heat-pump output − storage charge + storage discharge;
- served demand = delivered + backup + unserved.

All residuals are 0.000 MWh (`energy_balance_checks.csv`). Model A's own balance test (≤ 1e-6) and Model S's independent reproduction (0.002%) agree.

## Assumption evidence levels and measured influence (net value in $/yr and CO₂ in t/yr, for "+ Rebuilt Fulton" unless stated)

| Assumption | Current value | Evidence level | Test | Effect | Verdict |
|---|---|---|---|---|---|
| **A17 extra data-center electricity** | 0.25 per MWh extracted | Transferred from another NYC project (pilot), applied on the **wrong basis** | 0 / 0.367 | Value −0.99M / −2.31M (base −1.89M); **CO₂ +795 / −920 t** | **Decisive. Correct the base to 0.367**; 0 needs evidence |
| A02 capture temperature | 30 °C | Literature / assumption; pilot loop 12–36 °C | 27 / 35 °C | ±$0.09M; CO₂ −469 / −212 | Coupled with A17 (below) |
| A10 heat-pump efficiency | 0.45 × Carnot | Calibrated to the pilot (hot-water COP 2.99 vs 3.01) | 0.40 / 0.50 | ±$0.08M | Keep. Extrapolating to other temperatures is uncertain |
| A20 non-residential base-load share | ratio 0.2 → 39% for 111 8th Ave | Literature; matches LL84 monthly *gas* for the hotel and Chelsea Market | 0.05 / 0.30 | Internal-reuse CO₂ **60 / 265 t** (base 198); value ≤ $15k | Flag. 111 8th Ave's steam profile is unmeasured |
| A03 / A19 rebuilt demand | 7.5 MWh/apt, 50% hot water | Pure assumption (design not public) | 6 / 9 | ±$0.18M; CO₂ −259 / −487 | Keep as a range |
| A04 steam efficiency | 0.77 | Derived from the pilot | 0.85 | −$0.05M (more demand at a negative margin) | Keep |
| A18 hydronic temperature | 70 °C | Pure assumption | 60 / 80 °C | ≤ $12k | Low influence |
| A01 data-center share | 0.7 | Pure assumption | 0.5 | 0 | Never binds for these networks |
| Storage (2 h) | in sizing | Design choice; **no capital cost in Model B** | 0 h | ≤ $5k; CO₂ −7 t | Remove (uncosted, no value) |
| Heat-pump sizing | 75% of space-heat peak | Design choice | 50% / 100% | +$0.26M / −$0.34M; CO₂ −128 / +11 | A design trade-off, not an error |
| Hourly profiles | degree-hour space heat, flat hot water | Generic | – | Annual totals unaffected (supply in surplus: network uses ≤ 43% of data-center heat) | Flag for peak sizing only |
| Pipe heat loss | none on the ambient loop | Literature 0.5–1.5%/km for 70–80 °C pipe | Model S | ≤ $32k | Negligible for routes under 300 m |
| Backup | existing plant at 100% of peak; electric boilers in rebuilt towers | Design rule (H2) | M2–M4 | 0 unserved | Keep. Rebuilt-tower boilers need capital cost (Stage 5) |

## Physically consistent capture cases (replacing the earlier "advanced" case)
The pilot filing (pp. 69–70) states the coupling. A source that free-cools in winter must run its compressors to deliver heat warm enough to use, and that is where the source-side electricity comes from. A **high capture temperature and A17 = 0 cannot be combined** unless the servers are liquid-cooled.

| Case | A02 / A17 / A10 | 111 8th only | + Rebuilt Fulton | Phase 2 |
|---|---|---|---|---|
| **Pilot-like (evidence)** | 30 °C / 0.367 / 0.45 | −83k, 117 t | −2.31M, **−920 t** | −3.11M, −755 t |
| Register base (current) | 30 °C / 0.25 / 0.45 | −21k, 198 t | −1.89M, −373 t | −2.62M, −118 t |
| Warm-water liquid cooling (future; needs tenant DLC) | 45 °C / 0 / 0.45 | +180k, 470 t | −0.60M, +1,439 t | −1.13M, +1,996 t |
| *Previous "advanced" (inconsistent)* | *35 °C / 0 / 0.50* | *+154k* | *−0.77M* | *−1.31M* |

**Conclusion:** the network physics are sound and conserve energy. **One assumption, A17 together with how heat is captured, decides both the CO₂ sign and most of the value** of any network that includes the rebuilt towers. The most defensible evidence (the pilot) points the unfavourable way. Everything else changes results by less than $0.35M/yr and flips no sign.
