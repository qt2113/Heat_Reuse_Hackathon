# Full audit (isolated experiment)

Start with `FINAL_AUDIT_REPORT.md`. This experiment reads `data/`, `outputs/` and `model/` read-only. A SHA-256 check after the run (`00_baseline/file_hashes.json`) found all 199 files unchanged and none added.

| Stage | Script | Report | Data |
|---|---|---|---|
| 0 Baseline | (inline) | – | `00_baseline/` (git commit, uncommitted status, config snapshot, hashes, baseline results) |
| 1 Sources | `build_source_registry.py` | `01_SOURCE_AUDIT.md` | `source_registry.csv`, `raw_verification/` (pilot filing text, LL84 monthly, EIA heating oil) |
| 2 Data quality | `02_data_quality.py` | `02_DATA_QUALITY.md` | `cleaning_audit.csv`, `cleaning_impact_summary.csv`, `02_records/` |
| 3 Features | `03_feature_ablation.py` | `03_FEATURE_AUDIT.md` | `feature_ablation.csv`, `recommended_minimal_features.csv`, `03_redundancy_pairs.csv` |
| 4 Physics | `04_physical_tests.py` | `04_PHYSICAL_ASSUMPTIONS.md` | `physical_tests.csv`, `energy_balance_checks.csv` |
| 5 Costs | `05_cost_audit.py` | `05_COST_AUDIT.md` | `cost_registry.csv`, `cost_corrections.csv`, `reconciled_cashflow.csv` |
| 6 Final | `06_final_eval.py` | `FINAL_AUDIT_REPORT.md` | `final_comparison.csv`, `final_recommendation_by_step.csv`, `decomposition.csv`, `break_even_recommended.csv` |

`audit_lib.py` holds the shared helpers. Every correction is a named switch, and with no switches on, results reproduce Model B to $0.

Run the scripts in order from this folder (about 10 min in total; stage 3 is about 5 min).
