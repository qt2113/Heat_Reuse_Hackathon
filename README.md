# Data-center heat reuse: Site 1 (111 Eighth Avenue, Manhattan)

NYU heat-reuse hackathon. Question: can heat from the 111 8th Ave data center serve nearby buildings reliably, affordably and with measurable community value?

## Result in one paragraph
**No network with an external offtaker breaks even on current evidence.** With the extra data-center electricity measured in the Con Ed Chelsea pilot, network heat costs about $127–130/MWh in electricity alone. That only just beats steam and is far above gas-boiler heat.

**Best defensible external network:** 111 8th Ave in-building reuse + the **M070 public school** (+ Dream Hotel).
- 4.3 GWh/yr of data-center heat reused;
- about 400 t CO₂/yr avoided;
- one oil-heated school converted;
- about **$1.1M/yr of support needed** (about $0.7M with repeat-project costs).

**Rebuilt Fulton (1,335 low-income households) becomes worthwhile only if** source electricity is near zero, e.g. warm-water liquid cooling at about 45 °C.

The full evidence trail is in [`experiments/full_audit/FINAL_AUDIT_REPORT.md`](experiments/full_audit/FINAL_AUDIT_REPORT.md).

## Repository
| Path | Content |
|---|---|
| `scripts/` | Data download and processing (`fetch_site1_data.py`, `fetch_site1_gapfill.py`) |
| `data/` | Raw, processed and reference datasets (S01–S19), assumption register, data readiness audit |
| `model/` | A → B → C pipeline:<br>**A** hourly heat physics;<br>**B** costs, carbon and stakeholder value;<br>**C** offtaker selection and heat allocation.<br>Each has a validation script. See `model/README.md` |
| `outputs/` | Validated model outputs; `final/frontend/` = data bundle and `CONTRACT.md` for the interactive map |
| `experiments/full_audit/` | End-to-end audit (sources, cleaning, features, physics, costs, final evaluation) and the review of the teammate model |
| `experiments/simplified_model/` | Independent simplified model ("Model S") used as a cross-check |

## Run
```bash
python scripts/fetch_site1_data.py --offline   # rebuild processed data from data/raw
python -m model.run_model_a                     # hourly physics, 21 tests
python -m model.run_model_b                     # economics, 13 tests
python -m model.run_model_c                     # selection + allocation, 19 tests (~2 min)
python -m model.run_final_analysis --stage frontend
cd experiments/full_audit && python 06_final_eval.py
```
Organizer source documents (`sources/`, 223 MB) and download caches are not in the repository.
