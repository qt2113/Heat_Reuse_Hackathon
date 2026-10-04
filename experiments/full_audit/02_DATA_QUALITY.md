# Stage 2: raw data quality and cleaning audit

Script: `02_data_quality.py`, which uses `audit_lib.py`. Outputs:
- `cleaning_audit.csv`: 23 checks;
- `02_records/*.csv`: the affected records;
- `cleaning_impact_summary.csv`: before vs after on 7 fixed networks.

Pipeline traced: `scripts/fetch_site1_data.py` (download, 1 km filter, kBtu → MWh) → `data/processed/ll84_buildings_1km_by_year.csv` → `features.build_offtakers()` (child records dropped, same-lot duplicates dropped, multi-year mean, fuel class, NYCHA flag, heating-system rule) → `offtakers_features.csv` → Models A/B/C.

## What is correct (verified, no action)
- **Unit conversions:**
  - steam, gas and oil: kBtu ÷ 3,412.142;
  - electricity: kWh ÷ 1,000;
  - 0 mismatches in 1,343–1,520 values each.
- **District hot water:** used by no property, so excluding it from heat fuel changes nothing.
- **Parent/child filings** are handled: e.g. Fulton's 4 child records carry 0 and the parent is kept. 86 same-lot, overlapping-year duplicates are dropped by a documented rule.
- **Distances:**
  - 10 of 682 records differ by more than 100 m from a haversine recomputation; these are multi-lot campuses, because `dist_m` is the nearest lot.
  - Routes use mean coordinates consistently.
  - 13 records without coordinates are excluded.
- **NYCHA flag:** set by 3 hard-coded IDs, which match the NYCHA data book.

## Problems found, ranked by downstream impact

| # | Problem | Records | Evidence | Recommendation | Impact on fixed networks ($/yr) |
|---|---|---|---|---|---|
| 1 | **Con Ed pilot apartments counted as new demand** | Fulton (291 of 944 apartments; 2,681 MWh) | S13 loads | **Correct** (subtract) | Existing Fulton + 111 8th: −7.05M → −5.18M |
| 2 | **Oil heat priced and emission-factored as gas** | 134 buildings mostly on oil, incl. M070 (97% oil) | LL84 oil fields; LL97 oil factor; EIA oil price | **Correct** | 111 8th + M070: −1.16M → −1.00M (+162k); +115 t CO₂ |
| 3 | **Isolated anomalous LL84 year in the 3-year mean** | 42 property-years (36 anomalies, 6 zero years); shortlist: hotel 2023, Chelsea Houses 2023 | Hotel 8,483 vs 4,621 / 4,839 MWh; LL84 monthly gas spike in Aug–Sep 2023 | **Correct**: mean of remaining years (only when the other years agree within 25%) | Hotel networks +156k (smaller and cheaper); 7-building +156k |
| 4 | **Single-year records excluded instead of flagged** | 293 records, incl. 4 steam-heated (Dream Hotel, 105 m) | Steam is the only fuel class with a positive energy margin | **Flag, don't exclude** | Dream Hotel + 111 8th: −0.54M/yr, the cheapest external connection after correction |
| 5 | **Hotel gas includes kitchen and laundry** | 363 W 16th St: 185 kBtu/ft² (146 without 2023) | High intensity for a hotel | **Flag**: servable demand likely overstated | Hotel phase 1 is uncertain by a further ±30% of its demand |
| 6 | **Gas building assumed to have hot-water radiators** | 430 pre-1940 gas/oil buildings, incl. London Terrace 1932, M440 1931, Chelsea Market 1905 | PLUTO year built | **Flag as uncertain** (scenario) | Balanced network: −9.14M → −6.74M if hot water only. It improves because uneconomic space heat is dropped. |
| 7 | **Same lot kept as two properties** (non-overlapping years) | 32 lots ≥ 0.5 GWh, e.g. The Greenwich Lane parent/child | Same BBL | **Flag** | None is in the shortlist or any recommended network |
| 8 | **Size threshold excludes adjacent small buildings** | 7 within 150 m (335 W 16th college, 65 m) | – | Tested explicitly | All negative (−0.6M/yr or worse) |
| 9 | **Gas includes cooking and laundry in multifamily** | 434 | LL84 is whole-building | Flag | Small; slightly overstates demand |
| 10 | **Estimated LL84 months** | 240 properties, incl. 111 8th Ave 2024 and Chelsea Market 2023–24 | LL84 flag | Flag | Uncertainty only |

**Bias in the filtering rules:** the original screen (≥ 2 years, ≥ 2 GWh, ≤ 2 per building type) systematically favoured **large gas-heated buildings**, which have a negative energy margin (−$64 to −$73/MWh). It also dropped **small steam-heated neighbours**, the only fuel class with a positive margin, along with oil-heated buildings that were mispriced as gas. The correction (flag, don't exclude; price oil as oil) changes *which* external offtaker is cheapest. It does not change the sign of any network.

## Before and after (data corrections only; same networks, same cost and physics)

| Network | Original | + outlier years | + pilot overlap | + oil as oil | Scenario: pre-war gas buildings steam-heated |
|---|---|---|---|---|---|
| 111 8th only | −21k | −21k | −21k | −21k | −21k |
| + hotel (phase 1) | −1.304M | −1.148M | −1.148M | −1.148M | −1.148M |
| + M070 | −1.164M | −1.164M | −1.164M | −1.002M | −1.002M |
| + Dream Hotel | −0.544M | −0.544M | −0.544M | −0.544M | −0.544M |
| + existing Fulton | −7.05M | −7.05M | −5.18M | −5.18M | −5.18M |
| Phase 2 (hotel + Rebuilt Fulton) | −2.780M | −2.624M | −2.624M | −2.624M | −2.624M |
| 7-building balanced | −9.46M | −9.30M | −9.30M | −9.14M | −6.74M |

**Conclusion:** cleaning improves every affected network by $0.16–1.9M/yr. **No network changes sign**, and the order of the small external options changes: Dream Hotel, then M070, then the hotel.
