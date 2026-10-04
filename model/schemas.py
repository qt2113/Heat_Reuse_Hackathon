"""Output contracts for the A -> B -> C pipeline.

Each table lists its columns (unit, meaning) and which later module consumes it. Model A tables are
implemented; Model B and C tables are fixed here so A's outputs are built for them. The registry is
exported to outputs/schema_registry.json for the frontend.
"""
from __future__ import annotations

DIMENSIONS = ("Technical", "Economic + Delivery", "Environmental", "Social + Regenerative")

# KPI -> dimension, producing model, and the Model A columns it needs (data_dictionary.csv shortlist)
KPIS = {
    "T1": ("Technical", "A", "Recoverable heat", "GWh/yr", ["T1_recoverable_heat_GWh"]),
    "T2": ("Technical", "A", "Seasonal heat-pump COP", "-", ["T2_SCOP"]),
    "T4": ("Technical", "A", "Hourly demand coverage", "%", ["T4_coverage_pct"]),
    "T7": ("Technical", "A", "Network route length", "m", ["T7_route_m"]),
    "C1": ("Economic + Delivery", "B", "CAPEX per kW", "$/kWth", ["HP_cap_MW", "HX_cap_MW", "tank_MWh", "route_m", "apartments_connected"]),
    "C2": ("Economic + Delivery", "B", "Levelised cost of heat", "$/MWh", ["Q_network_MWh", "E_network_MWh", "Q_DC_used_MWh", "backup_fuel_*", "HP_cap_MW"]),
    "C3": ("Economic + Delivery", "B", "Saving vs current heat cost", "%", ["a_annual_building: Q_network_MWh, baseline_fuel_MWh, main_fuel"]),
    "N1": ("Environmental", "B", "Energy Reuse Factor", "%", ["Q_DC_used_MWh", "E_IT_MWh"]),
    "N2": ("Environmental", "B", "Net GHG avoided", "tCO2e/yr", ["fuel_displaced_*", "backup_fuel_*", "E_network_MWh", "E_src_MWh"]),
    "N4": ("Environmental", "B", "On-site combustion displaced", "MWh/yr, kg NOx", ["fuel_displaced_gas_MWh"]),
    "N6": ("Environmental", "B", "Winter peak vs all-electric ASHP", "MW", ["P_at_design_hour_MW", "D_peak_design_MW"]),
    "S1": ("Social + Regenerative", "B", "Low-income households served", "households", ["nycha_apartments_connected", "a_annual_building: units, is_nycha"]),
    "S3": ("Social + Regenerative", "B", "EJ exposure of served block", "index", ["a_annual_building: property_id (joined to dac_tracts_1km)"]),
    "S5": ("Social + Regenerative", "B", "Acceptance & governance (rubric)", "0-4", ["scenario"]),
    "S6": ("Social + Regenerative", "B", "Rebuild design-window fit (rubric)", "0-2", ["scenario"]),
    "S7": ("Social + Regenerative", "B", "Net value to the data center", "$/yr", ["Q_DC_used_MWh", "E_src_MWh"]),
}
CONSTRAINTS = {"H1": "A", "H2": "A", "H3": "A", "H4": "A", "H5": "A", "H6": "B", "H7": "A"}

TABLES = {
    # ------------------------------------------------------------ Model A (implemented)
    "model_a/a_runs.csv": dict(producer="A", status="implemented", consumers=["B", "C", "frontend"],
        key=["run_id"], description="One row per run: scenario x design x assumption set, with every resolved parameter."),
    "model_a/a_annual_system.csv": dict(producer="A", status="implemented", consumers=["B", "C", "frontend page 2"],
        key=["run_id"], description="Annual physical totals per run (MWh, MW), sizing, COPs, technical indicators T1/T2/T4/T7 (not scored)."),
    "model_a/a_annual_building.csv": dict(producer="A", status="implemented", consumers=["B (bills, carbon, equity)", "frontend page 1"],
        key=["run_id", "property_id"], description="Per connected building: useful demand, heat from network, backup heat/fuel, fuel displaced, baseline fuel, HP electricity."),
    "model_a/a_monthly.csv": dict(producer="A", status="implemented", consumers=["frontend page 2"],
        key=["run_id", "month"], description="Monthly demand, network heat, backup, electricity, data-center heat used."),
    "model_a/a_constraints.csv": dict(producer="A", status="implemented", consumers=["C (feasibility gate)"],
        key=["run_id", "constraint_id"], description="H1-H5, H7 pass/fail with metric; H6 marked pending_model_B."),
    "model_a/hourly/<run_id>.csv.gz": dict(producer="A", status="implemented", consumers=["frontend page 2", "B (peak, time-of-use)"],
        key=["run_id", "hour_of_year"], description="8,760-hour series for reference-design base runs."),
    "model_a/a_operating_modes.csv": dict(producer="A", status="implemented", consumers=["C (evaluation report)", "frontend page 2"],
        key=["scenario", "mode"], description="Stress tests: normal year, DC outage 72 h, heat-pump maintenance, network outage 72 h, summer; unserved heat, backup peak, share of DC heat still rejected by towers."),
    "config/delivery_governance.csv": dict(producer="team (evidence register)", status="implemented", consumers=["B (b_delivery_assessment)", "C (evaluation report)", "frontend page 3"],
        key=["item_id"], description="Unscored structured assessment: revenue/connection model, ownership, responsibilities, risk allocation, public acceptance, local-context fit, stakeholder-value structure; each item with evidence level and source."),
    "config/scenarios.yaml": dict(producer="team", status="implemented", consumers=["A", "B", "C", "frontend"],
        key=["scenario"], description="Scenario connection sets, physics constants, design grid, operating modes, sensitivity list."),
    "config/requirements_coverage.csv": dict(producer="team", status="implemented", consumers=["validation", "README"],
        key=["req_id"], description="Every official challenge requirement mapped to pipeline stage, output and frontend page."),
    "model_a/a_validation.csv": dict(producer="A", status="implemented", consumers=["README / judges"],
        key=["test_id"], description="Calibration against the Con Ed pilot and internal consistency tests."),
    # ------------------------------------------------------------ Model B (planned; inputs fixed above)
    "model_b/b_kpis.csv": dict(producer="B", status="implemented", consumers=["C"],
        key=["run_id", "kpi_id"], description="Raw values of all 16 KPIs (T* copied from A; C*, N*, S* computed) with unit and dimension."),
    "model_b/b_building_bills.csv": dict(producer="B", status="implemented", consumers=["C (H6)", "frontend page 3"],
        key=["run_id", "property_id"], description="Baseline vs network heating cost per building and per apartment."),
    "model_b/b_stakeholder_value.csv": dict(producer="B", status="implemented", consumers=["C (evaluation report)", "frontend page 3"],
        key=["run_id", "stakeholder", "item"], description=(
            "Separate value per stakeholder. data_center: heat revenue (A06 x Q_DC_used) - added electricity (E_src x A07) - O&M "
            "+ own steam/gas displaced (S1). heat_users: baseline cost - (tariff x heat + connection) per building and per apartment; "
            "continuity (Q_unserved = 0). community: tCO2e avoided, kg NOx avoided, low-income households served, winter peak change.")),
    "model_b/b_delivery_assessment.csv": dict(producer="B", status="implemented", consumers=["C (evaluation report)", "frontend page 3"],
        key=["run_id", "item_id"], description="delivery_governance.csv items applicable to each scenario, joined to the quantitative values they reference (unscored)."),
    "model_b/b_constraints.csv": dict(producer="B", status="implemented", consumers=["C"],
        key=["run_id", "b_set", "constraint_id"], description="H6 affordability (NYCHA bill vs today at the pilot tariff) and financial checks F1 society gains, F2 operator self-financing, F3 data-center participation, F4 payback <= 25 yr."),
    "model_b/b_economics.csv": dict(producer="B", status="implemented", consumers=["C", "frontend page 3"],
        key=["run_id", "b_set"], description="CAPEX by component, OPEX, LCOH (system), baseline cost, annual savings, payback, transfers, actor positions, CO2, NOx, ERF, peak."),
    "model_b/b_validation.csv": dict(producer="B", status="implemented", consumers=["README / judges"],
        key=["test_id"], description="Transfers cancel, one baseline per building, carbon bookkeeping, sensitivity directions, pilot cross-check."),
    "model_b/b_kpi_comparison.csv": dict(producer="B", status="implemented", consumers=["review", "frontend page 3"],
        key=["KPI"], description="Reference design, base values with one-at-a-time sensitivity range, S1-S3R."),
    # ------------------------------------------------------------ Model C (planned)
    "model_c/c_candidates.csv": dict(producer="C (screening)", status="implemented", consumers=["frontend EXPLORE"],
        key=["property_id"], description="All 695 de-duplicated LL84 properties with screening status, reason, useful and servable demand; 10 shortlisted."),
    "model_c/c_candidates.geojson": dict(producer="C", status="implemented", consumers=["frontend map"],
        key=["id"], description="Map layer: source + candidates with measured energy, status and reasons."),
    "model_c/c_configurations.csv": dict(producer="C", status="implemented", consumers=["frontend OPTIMIZE / EVALUATE"],
        key=["config_id"], description="Every building combination of both horizons: 13 indicators (raw + normalised), feasibility class, failed checks, conditional levers, dimension scores T/E/N/S, Pareto flag."),
    "model_c/c_recommendations.json": dict(producer="C", status="implemented", consumers=["frontend EVALUATE", "slides"],
        key=["horizon", "preset"], description="Preferred configuration per weight preset and horizon, feasibility message, explanations for selected and non-selected buildings."),
    "model_c/c_weight_sensitivity.csv": dict(producer="C", status="implemented", consumers=["frontend"],
        key=["horizon", "T", "E", "N", "S"], description="Winner for every weight set on a 10% simplex grid."),
    "model_c/c_pareto.csv": dict(producer="C", status="implemented", consumers=["frontend"],
        key=["config_id"], description="Non-dominated configurations on the four dimension scores."),
    "model_c/c_allocation_<horizon>.json": dict(producer="C (Model A merit dispatch)", status="implemented", consumers=["frontend seasonal/hourly view"],
        key=["config_id"], description="Monthly and representative-week heat allocation per building for the preferred configuration."),
    "model_c/c_recommendations_pilot_tariff.csv": dict(producer="C", status="implemented", consumers=["review"],
        key=["horizon", "preset"], description="Same optimisation without the Term 4 affordability cap (pilot tariff for NYCHA)."),
    "model_c/frontend_manifest.json": dict(producer="C", status="implemented", consumers=["frontend"],
        key=[], description="Indicator definitions, normalisation, weights rule, file index."),
    "model_c/c_validation.csv": dict(producer="C", status="implemented", consumers=["README / judges"],
        key=["test_id"], description="18 tests incl. A/B re-check, physics in every configuration, transfers, feasibility, weights."),
}


def assert_composite_ready(kpi_ids: list[str]) -> None:
    """Model C guard: a composite score may only be built when every dimension has at least one KPI.
    Model A alone (Technical only) must never produce a score."""
    present = {KPIS[k][0] for k in kpi_ids if k in KPIS}
    missing = [d for d in DIMENSIONS if d not in present]
    if missing:
        raise ValueError(f"Composite refused: no KPI yet for {missing}. Run Model B first.")


def registry() -> dict:
    return dict(
        pipeline=["features", "A: hourly heat simulation", "B: cost, carbon, value", "C: constraints + MCDA"],
        dimensions=list(DIMENSIONS),
        kpis={k: dict(dimension=v[0], model=v[1], name=v[2], unit=v[3], model_a_inputs=v[4]) for k, v in KPIS.items()},
        constraints=CONSTRAINTS,
        tables=TABLES,
        governance_aspects=["revenue_connection_model", "ownership", "responsibilities", "risk_allocation",
                            "public_acceptance", "local_context_fit", "stakeholder_value"],
        stakeholders=["data_center", "heat_users", "community"],
        requirements_coverage="model/config/requirements_coverage.csv",
    )
