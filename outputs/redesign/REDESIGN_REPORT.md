# Site 1: external-network redesign experiment

Run with `python -m model.run_redesign --stage all`; outputs in `outputs/redesign/`. Models A/B/C and their outputs are unchanged.

## 1. Reconciliation with the teammate's visualizer (same buildings)
The teammate's 10 base-case buildings map to 6 of our LL84 records. Fulton's 4 child filings are our single Fulton record, and "200 W. 18th St." (870 MWh) has no record in our 1 km table. The decomposition is Shapley over 8 factors, 256 runs (`reconciliation.csv`):

| | $/yr |
|---|---|
| Our model, their buildings, our assumptions | **−11.97M** (14.4 GWh delivered: steam buildings get hot water only) |
| Building retrofit at $1.2k/kW instead of the pilot's $63.8k per NYCHA apartment | +5.38M |
| Pipe $3k/m instead of $29.3k/m | +4.01M |
| No contingency or soft costs | +2.33M |
| A17 = 0 | +1.06M |
| No energy centre or source interface (their $150/kW connection instead) | +0.87M |
| No heat-pump or network O&M | +0.54M |
| Steam radiators fed 65 °C water (full space heat) | **−0.73M**: serving that space heat with heat pumps loses money |
| Their prices, finance and efficiency (gas $14, steam $35, 6%, eta 0.40) | −1.04M |
| **Our model with all their choices** | **+0.46M** (47.5 GWh delivered) |
| Residual vs their resource value of $1.19M (demand data, dispatch, central heat pumps, the missing building) | +0.74M |
| Their LL97 penalty avoided + cooling water (a transfer and an unverified item) | +0.39M → their reported +1.58M |

**Why the results differ:** about 85% of the gap is cost basis (retrofit, pipe, markups), plus A17. Physics and prices account for little, and they work against the teammate's result.

## 2–5. Design cases
111 8th Ave plus 1–3 external offtakers, all 221 networks in each case. Every network is tested across hot-water-only versus full service, heat-pump size and storage (`networks_best_design.csv`).

| Best network, at least 1 external | Reference (NYC-calibrated) | Optimised urban retrofit | Advanced heat recovery | Liquid cooling (speculative) |
|---|---|---|---|---|
| External offtaker | M070 school | 363 W 16th hotel (hot water only) | Rebuilt Fulton | Rebuilt Fulton |
| Heat recovered / delivered (GWh) | 3.8 / 5.6 | 3.8 / 5.5 | 16.9 / 21.6 | 18.2 / 21.6 |
| CAPEX (annualised) | $13.7M ($0.97M) | $7.1M ($0.43M) | $22.2M ($1.39M) | $22.7M ($1.43M) |
| OPEX per year | $0.78M | $0.68M | $1.50M | $1.22M |
| Gross energy savings | −$0.04M | −$0.02M | +$1.60M | +$1.89M |
| **Net societal value** | **−$1.16M** | **−$0.53M** | **−$0.045M** | **+$0.21M** |
| CO₂ avoided (t/yr) | 336 | 340 | 1,012 | 1,388 |
| Low-income households / facilities | 0 / 1 | 0 / 0 | 1,335 / 0 | 1,335 / 0 |
| Minimum support per year (everyone no worse off) | $1.16M | $0.53M | $0.045M | 0 |
| Operator gap at pilot prices (transfers) | $1.07M | $0.47M | $1.51M | $1.40M |

In the optimised case, Rebuilt Fulton costs −$1.16M/yr and its CO₂ is −479 t at A17 = 0.25, so it delivers social value only.

**Key engineering finding:** only offtakers whose alternative is **electric** heating have positive gross energy savings. That means the rebuilt, all-electric Fulton towers, where the network replaces air-source heat pumps. Existing gas-heated buildings lose money in every case, because gas heat (about $46/MWh) is cheaper than heat-pump heat from grid electricity (about $55–75/MWh). For Rebuilt Fulton, the incremental cost under advanced recovery is $164 per household per year, or $377 per tonne of CO₂.

## 6. Break-even of the best small external network
111 8th Ave + Rebuilt Fulton, advanced case (`break_even.csv`). Any **one** of these closes the remaining $45k/yr:
- pipe cost ≤ $14,900/m (assumed $17,590; pilot $29,318);
- A17 ≤ −0.01, i.e. recovery slightly reduces data-center cooling energy;
- electricity ≤ $213/MWh (NYPA + Con Ed delivery rate for NYCHA: $182);
- heat-pump efficiency ≥ 0.53 × Carnot (seasonal COP about 4.9);
- capture temperature ≥ 36.8 °C;
- carbon value ≥ $44/t;
- a 3% capital grant (about $0.72M upfront).

The advanced case already assumes 35 °C capture, efficiency 0.50 and A17 = 0. With evidence-supported levers alone (optimised case), no single lever within physical bounds closes the gap:
- **Hotel:** would need A17 = −0.38 or electricity at $24/MWh.
- **Rebuilt Fulton:** would need A17 = −0.08 or electricity at $107/MWh.

## 7. Evidence
`evidence_classification.csv` classifies every lever.
- **Corrections** (pre-war gas buildings as steam-heated, pilot overlap removed, backup-boiler cost) make the results *more* conservative.
- **Advanced case:** its three levers (35 °C capture, efficiency 0.50, A17 = 0) are inside the register's ranges, but none is measured at 111 8th Ave. **A17 is decisive.**
- **Liquid cooling** at 45 °C is speculative.

## Answer
- **Can a credible, financially viable external network exist?**
  - Under evidence-supported improvements alone: **no**.
  - The cheapest external network (hotel, hot water only) needs **$0.53M/yr**.
  - Reaching **1,335 low-income households** (Rebuilt Fulton) needs **$1.16M/yr** (about $870 per household).
- **Break-even path:** if tenant metering confirms near-zero extra electricity and ≥ 35 °C capture, **111 8th Ave + Rebuilt Fulton** reaches break-even (−$45k/yr). It then avoids about 1,000 t CO₂/yr and serves 1,335 low-income households.
  - This depends on the internal-reuse surplus (+$174k) offsetting the external connection (−$219k).
  - Each heat user must be priced at no more than its own avoided cost.
