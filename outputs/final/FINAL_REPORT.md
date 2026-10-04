# Site 1: final analysis report

Run with `python -m model.run_final_analysis --stage all` (outputs in `outputs/final/`); about 15 minutes, nearly all of it the combined sensitivity. The reference outputs in `outputs/model_a|b|c/` were not regenerated.

## 1. Final screening audit
| Run | Eligible | Shortlist | Result |
|---|---|---|---|
| 1 km, 10 buildings, ≥ 2 GWh (reference) | 49 | 10 | 0 fully feasible |
| ≥ 1 GWh, 10 or 12 buildings | 107 | 10 / 12 | identical shortlists and results |
| ≥ 0.5 GWh, 10 or 12 buildings | 235 | 10 / 12 | identical shortlists and results |

- **Small buildings never reach the shortlist.** It ranks by servable heat per metre, not by consumption, and the best small building ranks 20th.
- **Direct test** (`small_building_check.csv`): the 10 small buildings within 300 m with consistent demand (≥ 2 years of data, year-to-year range ≤ 25%).
  - Each adds $1.0–1.8M/yr of cost for 40–70 t CO₂.
  - All 10 together: −$6.7M/yr (−$6.0M/yr with hot-water-only service).
- **Conclusion:** no smaller-building opportunity was missed.

## 2. Model integrity audit
- **Heat definitions** (reference today network):
  - recoverable: 79.6 GWh;
  - heat reused = heat extracted: **26.1 GWh** (the ERF numerator);
  - heat delivered: **39.4 GWh** = 26.1 reused + 13.3 heat-pump electricity.
  - The earlier "30 GWh" was a reporting error; no model quantity equals 30 GWh.
- **Cost boundary:**
  - Transfers cancel (test C5).
  - Pilot costs exclude the pilot's own contingency, so applying 15% contingency plus A21 soft costs does not double-count.
  - Biases found and tested:
    - one asset life (25 yr) for pipes as well as heat pumps;
    - interface cost scaled linearly from a 1.5 MW pilot;
    - pilot costs carry 3%/yr escalation;
    - rebuilt towers' electric backup boilers have no capital cost;
    - Con Ed pilot hot water (about 2,333 MWh/yr) is not netted out of existing Fulton.
- **Economics in one line:** every multi-building network loses money **before any capital cost** (balanced: −$1.9M/yr). Electricity at $222/MWh ÷ COP about 3 costs more than gas heat at about $46/MWh. Only 111 8th Ave heating itself (steam at about $140/MWh of heat) has a positive operating margin.
- **A17 (0.25 MWh of electricity per MWh of heat):** the only empirical value we have, but it is measured at 85 10th Ave, not at 111 8th Ave. It is the most influential single parameter, and it decides the sign of phase-2 CO₂.
- **Normalisation:**
  - After the rebuild, S_aff is the same for every network, which caps Social at 0.74. Removing it changes **no** recommendation.
  - Min-max stretches trivial ranges (backup dependency 0.2–0.7%).
  - The overall score barely tracks net value (Spearman −0.07 today, −0.30 after the rebuild).
- **Fixed design:** hot-water-only service for commercial buildings saves $0.24–3.6M/yr but loses CO₂ (space heat abates at about $3,000/t). No design makes a network positive.
- **Operating modes M1–M5** on all 8 portfolios: all pass, 0 MWh unserved.

## 3. Combined sensitivity
Full factorial of 69,984 combinations per portfolio:
- **From the register:** A02, A10, A18, A17, A05, A07, A21, A08.
- **Extra factors:**
  - gas price up to the EIA residential level;
  - steam price at the Con Ed SC2 tariff;
  - interface cost exponent 0.7;
  - pipe life 40 years.

| Portfolio | Base $/yr | Best case $/yr | Combinations > 0 |
|---|---|---|---|
| 111 8th Ave heating itself | −21k | +229k | 43.5% (A17 = 0 alone gives +$112k) |
| Proposal phase 1 | −1.30M | −130k | 0 |
| Proposal phase 2 | −2.78M | +57k | 5 (needs ≥ 9 favourable changes at once) |
| Balanced | −7.15M | −521k | 0 |
| Community | −10.9M | −1.35M | 0 |

- **Biggest effects on mean value:** A17, discount rate, soft costs, pipe cost, electricity price, gas price.
- **Phase-2 CO₂:** −431 to +328 t at A17 = 0.25; +849 to +1,861 t at A17 = 0.

## 4. Proposal (`proposal_portfolios.json`)

| | Min cost: 111 8th self-use | **Proposal ph1:** 111 8th + 363 W 16th hotel | **Proposal ph2:** + Rebuilt Fulton | Balanced (equal weights) | Community (social-first) |
|---|---|---|---|---|---|
| Heat reused / delivered (GWh) | 2.4 / 3.5 | 5.7 / 8.5 | 19.5 / 27.2 | 33.3 / 48.2 | 45.6 / 64.2 |
| Net value ($/yr) | −0.02M | −1.30M | −2.78M | −7.15M | −10.9M |
| CO₂ avoided (t/yr) | 198 | 520 | −50 (A17 = 0: up to +1,861) | 1,289 | 213 |
| Low-income households / facilities | 0 / 0 | 0 / 0 | 1,335 / 0 | 1,335 / 2 | 2,931 / 2 |
| Funding gap (users no worse off) | 0.02M | 1.30–1.49M | 2.78–3.43M | 7.15–8.25M | 10.9–12.4M |
| CAPEX | $1.5M | $13.0M | $37.6M | $73.7M | $133M |
| Winter peak cut vs all-electric | 0 | 1.0 MW | 3.6 MW | 6.9 MW | – |

- **Architecture:**
  - heat exchanger on the tenant condenser loop (about 28 °C loop);
  - ambient two-pipe loop (65 m, then 229 m);
  - decentralised building heat pumps (COP 3.2 hot water, 4.5 at 45 °C, 2.75 at 70 °C);
  - storage, and backup at 100% of design peak (existing steam/boilers; electric boilers in the rebuilt towers).
- **Cooling independence:** the data center keeps all its towers, and the network takes at most 43% of DC heat in any hour.
- **Why this proposal:**
  1. Phase 0/1 starts with near-break-even in-building reuse at 111 8th Ave.
  2. It then adds the nearest year-round commercial load (65 m) to prove the street loop.
  3. It uses the rebuild design window to supply 45 °C heat to Rebuilt Fulton, at about $1.1k per household per year, against $3.7k for the community option and $5.4k for the balanced one.

## 5. Frontend
`outputs/final/frontend/` holds the data files and `CONTRACT.md`. Checks FE1–FE5 pass.

## 6. Challenge coverage (`challenge_coverage.csv`)
Every Consider item is covered except R11 and R25 (partial). Still missing before the presentation:
- operator and funding instrument;
- tenant data A01/A02/A17/A14 and LL97 status of 111 8th Ave;
- hotel heating system (A18);
- coordination with the Con Ed pilot;
- an engineered pipe route;
- building-specific hourly profiles;
- integration into the teammate's map.
