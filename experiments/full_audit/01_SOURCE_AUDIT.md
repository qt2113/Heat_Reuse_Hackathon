# Stage 1: data source authority and provenance audit

Baseline: commit `9aa63bc` plus 32 uncommitted working-tree changes. These are recorded in `00_baseline/` (git status, config snapshot, SHA-256 of 199 data/output/model files, `baseline_results.csv`).

The registry is `source_registry.csv`: 40 rows, built by `build_source_registry.py`. Every dataset under `data/raw|processed|reference` and every parameter that Models A/B/C read has a row. Authority and applicability are rated separately, then combined into a class:
- **A:** authoritative and applicable;
- **B:** authoritative but transferred;
- **C:** model or literature assumption;
- **D:** weak or inappropriate for the use made of it.

## How the claims were verified (not taken from our own docs)
- **Con Ed pilot filing:** text extracted from the cached PDF (`data/cache/coned_chelsea_uten_stage2.pdf` → `raw_verification/pilot_filing.txt`). Checked: Table 8 (source electricity), Table 11 (costs), pp. 46–51 (scope), pp. 68–70 (operation), pp. 88–90 (cost basis).
- **LL84 monthly data** (NYC Open Data `fvp3-gcb2`), fetched for 5 key buildings → `raw_verification/ll84_monthly_selected.json`.
- **EIA NY No. 2 heating oil weekly price**, fetched → `raw_verification/eia_ny_heating_oil_residential_weekly.csv`.
- **LL97 coefficients:** the statute values in `ll97_emission_coefficients.csv` (5/5 already marked verified against the law text).

## Findings that matter, ranked by potential impact on the external offtaker or net value

| # | Item | Class | What the source supports | What it does **not** support | Action |
|---|---|---|---|---|---|
| 1 | **A17 extra electricity at the source** (pilot-derived 0.25) | B value / **D basis** | 85 10th Ave uses +666 MWh/yr to supply heat (Table 8). The cause is that the building switched to winter free cooling and must run its compressors again to make usable heat (pp. 69–70). | Using 0.25 per MWh **extracted**. The pilot figure is 666 / 2,680 MWh **delivered**. Per MWh injected into the loop (2,680 − 866.5 = 1,813.5 MWh), it is **0.367**. | Correct the base to 0.367 per MWh extracted. A17 is coupled to capture temperature: 30–35 °C in winter requires compressor operation unless servers are liquid-cooled. |
| 2 | **Oil-heated buildings priced and counted as gas** | D (implementation) | LL84 separates fuel oil; LL97 gives oil 0.253 t/MWh vs gas 0.181; EIA NY heating oil ≈ $104/MWh of fuel. | `model_b.py` prices every `gas_or_oil` building at the gas price ($38.85) and gas emission factor. M070 burns about 97% oil (2,445 MWh/yr). | Price and count oil as oil. The EIA residential price is an upper bound, so test −30%. |
| 3 | **NYCHA retrofit cost, $63.8k per apartment** | B, scope mismatch | Pilot customer-side cost for 3 buildings: hot water for all three, plus space heating and cooling (fan coils) for one. | Hot-water-only service. The filing says removing a second building's space heating and cooling saved about $7M (p. 90), so hot-water-only is about $39.8k per apartment. | Correct for hot-water-only existing NYCHA (medium confidence). |
| 4 | **LL84 3-year mean for 363 W 16th St (hotel)** | A data / outlier year | 2022 and 2024: 4,621 and 4,839 MWh. | 2023 is 8,483 MWh; LL84 monthly gas shows spikes in Aug–Sep 2023 (1,591 and 1,548 MWh vs about 300 normally). The mean overstates demand by 26%. | Use the median when one year deviates by more than 50%. |
| 5 | **PLUTO / fuel → heating emitter** | A geometry / D inference | Year built: London Terrace 1932, M440 1931, Chelsea Market 1905. | That gas-heated buildings have hot-water radiators. Pre-war Manhattan buildings are often steam-heated. | Flag as uncertain; scenario only. |
| 6 | **A20 → 111 8th Ave base load 39%** | C for gas buildings / D for 111 8th Ave | LL84 monthly gas shows a summer/winter ratio of 0.16–0.33 for the hotel and Chelsea Market, consistent with A20. | The steam profile of an office building; no monthly steam data are published. | Flag internal reuse as uncertain. |
| 7 | **EIA state-average gas price** | B (transferred) | NY commercial average $11.4/MMBtu. | The Con Ed delivered price in Manhattan, which is likely higher (unverified). | Keep; sensitivity only. |
| 8 | **Electricity $222/MWh** | B | Consistent with Con Ed 2024 weighted all-in of about $210 (EIA-861: bundled commercial $282; delivery-only $110 plus energy). | Customer-specific demand charges. | Keep. |
| 9 | **Pilot cost basis** (pipe, interface, energy centre, soft costs) | B | Manhattan street pipe for 2 × 10" pre-insulated steel; the 15% contingency is excluded from the pilot's line items and applied once; the 25-year life follows NY DPS lifecycle cost guidance (pilot footnote 23). | Repeat-project or 111 8th Ave costs; per-MW scaling of the interface; a full energy centre for a 1 MW spur. The pilot's dollars are escalated (3%/yr plus 10% tariff). | Keep as reference; label alternatives. |
| 10 | **Rebuilt-Fulton counterfactual** (all-electric air-source heat pumps) | C | FEC states the rebuild will be all-electric. | That no utility network serves the rebuild. The pilot's $19M of pipe, pumps and "taps for future connections" are explicitly designed for reuse at the rebuild (p. 15). The pilot uses about 40% more electricity than air-source heat pumps (p. 68). | Keep air-source heat pumps as the baseline; disclose the Con Ed network alternative and the attribution risk. |
| 11 | **DAC tract → equity** | A tract / D as building attribute | Tract designation. | S_eq counts heat to commercial buildings in DAC tracts (Chelsea Market, hotel, 61 9th Ave, M070) as equity heat. | Restrict to NYCHA / affordable units. |
| 12 | **A01 data-center share 0.7** | D | LL84 monthly electricity is flat (July/January 1.10), consistent with a large constant load. | Any specific share. | Keep as a range. It never binds for networks under about 45 GWh. |

**Sources that are fine as used:**
- **Class A:** LL84 fuel inputs, TMYx/ASHRAE, NYCHA data book, LL97 factors (as accounting factors), Con Ed steam tariff, EIA-861 utility averages, CPI/FX, unit conversions (kBtu → MWh ÷ 3,412.142, checked in the fetch script).
- **Context only, never in decisions:** NYISO Zone J, NYCCAS/HVI.

**Not supportable and correctly not used:**
- the teammate's $3k/m pipe;
- 65 °C water into steam radiators;
- LL97 penalties counted as a societal saving.

## What the pilot filing can and cannot carry
- **Measured?** No: it is a 100% engineering design with modelled loads. The pilot is not operating, so no operating data exist.
- **Fits Manhattan street works:** directly applicable to pipe material, diameter and route type, and to a heat-exchanger interface on a commercial cooling plant.
- **Transferred:** source-side electricity, building retrofit costs and the COP calibration describe *that* source plant and *those* NYCHA buildings.
