"""Stage 2: raw-data quality and cleaning audit (reads data/ and outputs/features read-only).

Writes cleaning_audit.csv (one row per check, with affected records), cleaning_impact_summary.csv (BEFORE vs AFTER on a
fixed set of networks) and the affected-record listings in 02_records/.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import audit_lib as L

OUT = L.HERE
REC = OUT / "02_records"
REC.mkdir(exist_ok=True)
F = L.F

raw = pd.read_csv(F.DATA / "raw" / "s01_ll84_benchmarking_1km.csv", dtype=str, low_memory=False)
y = pd.read_csv(F.DATA / "processed" / "ll84_buildings_1km_by_year.csv", dtype={"property_id": str, "report_year": str})
o = pd.read_csv(F.ROOT / "outputs" / "features" / "offtakers_features.csv", dtype={"property_id": str})
dropped = pd.read_csv(F.ROOT / "outputs" / "features" / "offtakers_dropped_duplicates.csv", dtype=str)
cand = pd.read_csv(F.ROOT / "outputs" / "model_c" / "c_candidates.csv", dtype={"property_id": str})
pluto = pd.read_csv(F.DATA / "processed" / "pluto_lots_1km.csv", dtype=str)
rows = []


def add(cid, check, n, total, problem, recommendation, material, records=None):
    if records is not None and len(records):
        records.to_csv(REC / f"{cid}.csv", index=False)
    rows.append(dict(check_id=cid, check=check, affected=n, out_of=total, problem=problem, recommendation=recommendation,
                     material_downstream=material, records_file=f"02_records/{cid}.csv" if records is not None and len(records) else ""))


# Q1 unit conversion kBtu -> MWh
for c_k, c_m in (("district_steam_use_kbtu", "steam_MWh"), ("natural_gas_use_kbtu", "gas_MWh"), ("electricity_use_grid_purchase_1", "electricity_MWh")):
    kb = pd.to_numeric(y[c_k], errors="coerce")
    mw = pd.to_numeric(y[c_m], errors="coerce")
    bad = ((kb / 3412.142 - mw).abs() > 1e-6 * kb.abs().clip(lower=1)) & kb.notna()
    if c_k.startswith("electricity"):                          # electricity reported in kWh in LL84
        bad = ((kb / 1000 - mw).abs() > 1e-6 * kb.abs().clip(lower=1)) & kb.notna()
    add(f"Q1_{c_m}", f"unit conversion {c_k} -> {c_m}", int(bad.sum()), int(kb.notna().sum()), "conversion mismatch" if bad.any() else "none",
        "keep" if not bad.any() else "correct", "no" if not bad.any() else "yes")
oil = pd.to_numeric(y.fuel_oil_2_use_kbtu, errors="coerce").fillna(0) + pd.to_numeric(y.fuel_oil_4_use_kbtu, errors="coerce").fillna(0)
badoil = ((oil / 3412.142 - pd.to_numeric(y.oil_MWh, errors="coerce").fillna(0)).abs() > 1e-3)
add("Q1_oil_MWh", "unit conversion oil #2 + #4 kBtu -> MWh", int(badoil.sum()), len(y), "none" if not badoil.any() else "mismatch", "keep", "no")
dhw = pd.to_numeric(y.district_hot_water_use_kbtu, errors="coerce").fillna(0)
add("Q1b_district_hot_water", "district hot water excluded from heat fuel", int((dhw > 0).sum()), len(y),
    "district hot water not part of heat_fuel_MWh" if (dhw > 0).any() else "no property uses district hot water", "keep", "no")

# Q2 raw vs processed row counts
add("Q2_rows", "raw LL84 rows vs processed property-years", len(raw) - len(y), len(raw),
    f"raw {len(raw)} rows -> processed {len(y)} property-years (filtering documented in fetch script: 1 km, years 2022-24)", "keep (documented)", "no")

# Q3 duplicates: same BBL kept twice with non-overlapping years (temporal duplicates)
o["bbl1"] = o.bbl.astype(str).str.split(";").str[0].str.strip()
dup = o[o.duplicated("bbl1", keep=False)].sort_values("bbl1")
dup_big = dup[dup.groupby("bbl1").heat_fuel_MWh.transform("max") >= 500]
add("Q3_same_lot_multiple_records", "same tax lot kept as >1 property (non-overlapping years or separate filings)", int(dup_big.bbl1.nunique()), int(o.bbl1.nunique()),
    "possible double counting of a building across years (e.g. The Greenwich Lane parent 2024 vs child 2022-23)",
    "flag; none is in the shortlist or any recommended network", "no (verified: no recommended network contains such a pair)",
    dup_big[["property_id", "property_name", "bbl1", "years", "heat_fuel_MWh", "dist_m"]])
add("Q3b_dropped_duplicates", "same-lot overlapping-year filings dropped", len(dropped), len(dropped) + len(o),
    "86 filings removed (keep record with more years, then more heat)", "keep (documented in features.py)", "no")

# Q4 outlier years (property-years > 50 % away from median of other years)
yy = L.yearly()
ol = L.outlier_years(yy)
ol = ol.merge(o[["property_id", "property_name", "dist_m"]], on="property_id", how="left")
ol["in_shortlist"] = ol.property_id.isin(cand.loc[cand.status == "shortlisted", "property_id"])
add("Q4_outlier_years", "LL84 zero years, or isolated year > 50 % from the other (mutually consistent) years", len(ol), int((yy.groupby('property_id').size() >= 3).sum()),
    "3-yr mean inflated/deflated by one anomalous filing (hotel 2023: 8,483 vs 4,621/4,839 MWh; LL84 monthly confirms Aug-Sep spike)",
    "correct: use mean of the remaining years for flagged properties", "yes for 363 W 16th St (phase-1 offtaker)", ol)

# Q5 oil-heated buildings priced as gas
o["oil_share"] = o.oil_MWh / (o.gas_MWh + o.oil_MWh).replace(0, np.nan)
oil_b = o[(o.main_fuel == "gas_or_oil") & (o.oil_share > 0.5)]
add("Q5_oil_as_gas", "buildings mainly heated by fuel oil but priced/emission-factored as gas", len(oil_b), int((o.main_fuel == "gas_or_oil").sum()),
    "model_b.py uses I['gas_price'] and LL97 natural-gas factor for every 'gas_or_oil' building (oil ~$104 vs gas $38.9 per MWh fuel; 0.253 vs 0.181 t/MWh)",
    "correct (price and factor by fuel share)", "yes: M070 (min-cost external network) is 97 % oil",
    oil_b[["property_id", "property_name", "use_type", "dist_m", "gas_MWh", "oil_MWh", "oil_share", "n_years"]].sort_values("dist_m"))

# Q6 coordinates / distance recomputation
site = (40.7413598, -74.0032081)


def hav(a, b, c, d):
    p = math.pi / 180
    h = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


oo = o.dropna(subset=["lat", "lon"]).copy()
oo["dist_recomputed"] = [hav(site[0], site[1], a, b) for a, b in zip(oo.lat, oo.lon)]
oo["diff"] = oo.dist_recomputed - oo.dist_m
bigd = oo[oo["diff"].abs() > 100]
add("Q6_distance", "LL84 dist_m vs haversine from mean coordinates", len(bigd), len(oo),
    "dist_m is the nearest-lot distance (multi-lot campuses); route uses mean coordinates",
    "keep; note multi-lot campuses (Fulton, Elliott-Chelsea)", "no (route length uses coordinates consistently)",
    bigd[["property_id", "property_name", "dist_m", "dist_recomputed", "diff"]])
add("Q6b_missing_coordinates", "records without coordinates", int(o.lat.isna().sum()), len(o), "cannot be routed", "exclude (already)", "no")

# Q7 estimated data flags
add("Q7_estimated", "properties with any 'estimated' LL84 month", int(o.any_estimated.sum()), len(o),
    "self-reported estimates (incl. 111 8th 2024, Chelsea Market 2023-24, London Terrace 2023-24, hotel 2024)", "flag (keep)", "uncertainty only")

# Q8 screening exclusions by fuel (bias check)
cc = cand.merge(o[["property_id", "main_fuel"]], on="property_id", how="left", suffixes=("", "_o"))
one_year = cc[cc.exclusion_reason.fillna("").str.contains("1 year")]
steam_excl = one_year[one_year.main_fuel == "steam"]
add("Q8_single_year_exclusion", "candidates excluded only for having one LL84 year", len(one_year), len(cc),
    f"{len(steam_excl)} steam-heated buildings (the only fuel class with a positive energy margin) excluded, incl. Dream Hotel 105 m",
    "flag instead of exclude (data-quality flag, not a filter)", "possible: Dream Hotel is the best-ranked external in the independent screen",
    one_year[["property_id", "property_name", "use_type", "main_fuel", "dist_m", "heat_fuel_MWh"]].sort_values("dist_m"))
small = cc[cc.exclusion_reason.fillna("").str.contains("below 2 GWh") & (cc.dist_m <= 150)]
add("Q8b_size_threshold_near", "buildings within 150 m excluded by the 2 GWh threshold", len(small), len(cc),
    "threshold favours large buildings; small adjacent buildings (335 W 16th college 65 m) never tested",
    "test explicitly (threshold experiment done: all negative)", "no (verified)", small[["property_id", "property_name", "use_type", "dist_m", "heat_fuel_MWh"]])

# Q9 classification checks
res_no_units = o[o.is_residential & o.units_res.isna()]
add("Q9_residential_without_units", "Multifamily records without unit count (DHW share falls back to non-residential rule)", len(res_no_units), int(o.is_residential.sum()),
    "DHW share computed with A20 instead of per-apartment", "flag", "no (none in shortlist)", res_no_units[["property_id", "property_name", "dist_m", "heat_fuel_MWh"]])
nycha_dev = pd.read_csv(F.DATA / "processed" / "nycha_chelsea_developments.csv")
add("Q9b_nycha_ids", "NYCHA flag set by 3 hard-coded property IDs", 3, int(o.is_nycha.sum()), "hard-coded but matches the NYCHA data book (Fulton, Elliott-Chelsea, Chelsea)",
    "keep", "no", nycha_dev)
pl = pluto.set_index("bbl").yearbuilt
o["year_built"] = pd.to_numeric(o.bbl1.map(pl), errors="coerce")
prewar = o[(o.main_fuel == "gas_or_oil") & ~o.is_nycha & (o.year_built > 0) & (o.year_built < 1940)]
add("Q9c_prewar_gas_as_hydronic", "pre-1940 gas/oil buildings assumed hydronic (emitter unverified)", len(prewar), int((o.main_fuel == "gas_or_oil").sum()),
    "hydronic_assumed for every gas building; pre-war Manhattan stock is often steam (incl. London Terrace 1932, M440 1931, Chelsea Market 1905)",
    "flag as uncertain; scenario 'prewar_steam'", "yes for balanced/community networks (scenario)",
    prewar[["property_id", "property_name", "use_type", "year_built", "dist_m", "heat_fuel_MWh"]].sort_values("dist_m"))

# Q10 physical plausibility of heating intensity
o["kbtu_ft2"] = o.heat_fuel_MWh * 3412.142 / o.gfa_ft2
imp = o[(o.kbtu_ft2 > 150) | ((o.kbtu_ft2 < 5) & (o.heat_fuel_MWh > 0))]
add("Q10_intensity", "heating-fuel intensity outside 5-150 kBtu/ft2", len(imp), int(o.gfa_ft2.notna().sum()),
    "implausible intensity (campus records, partial filings, central plants)", "flag; check if in shortlist", "no (none in shortlist)" if not imp.property_id.isin(cand.loc[cand.status == 'shortlisted', 'property_id']).any() else "check",
    imp[["property_id", "property_name", "use_type", "kbtu_ft2", "heat_fuel_MWh", "gfa_ft2", "dist_m"]])

hot = o[o.property_id == "19906892"]
add("Q10b_hotel_intensity", "363 W 16th St heating-fuel intensity", 1, 1,
    f"{float(hot.kbtu_ft2.iloc[0]):.0f} kBtu/ft2 (146 without 2023): gas includes kitchen/laundry that a heat network cannot serve",
    "flag: servable demand of the hotel is uncertain (likely overstated)", "yes for the phase-1 proposal (hotel)")

# Q11 pilot overlap
add("Q11_pilot_overlap", "Fulton apartments already served by the Con Ed pilot counted as new demand", 291, 944,
    "2,333 MWh DHW + 348 MWh space heat of 3 Fulton buildings served from 85 10th Ave (S13)", "correct (subtract)", "yes for existing-Fulton networks")

# Q12 gas includes non-heating end uses
add("Q12_gas_end_uses", "LL84 natural gas includes cooking/laundry/process", int(((o.main_fuel == 'gas_or_oil') & o.is_residential).sum()), int((o.main_fuel == "gas_or_oil").sum()),
    "heat demand of gas multifamily buildings overstated by the non-heating share (typically a few %); unquantifiable from LL84", "flag (uncertain)", "small; makes connections look slightly larger")

audit = pd.DataFrame(rows)
audit.to_csv(OUT / "cleaning_audit.csv", index=False)
print(audit[["check_id", "affected", "out_of", "recommendation", "material_downstream"]].to_string(index=False))

# ---------------- BEFORE vs AFTER on fixed networks (data corrections only)
NETS = [(["7536925"], "today"), (["7536925", "19906892"], "today"), (["7536925", "1634606"], "today"), (["7536925", "2831044"], "today"),
        (["7536925", "4978579"], "today"), (["7536925", "19906892", "rebuild:2831044"], "post_rebuild"),
        (["1633052", "1634606", "19906892", "4040951", "4769672", "7536925", "8899918"], "today")]
ctx = L.base_ctx()
steps = [("original", set()), ("+ outlier years", {"outlier_years"}), ("+ pilot overlap", {"outlier_years", "pilot_overlap"}),
         ("+ oil priced as oil", {"outlier_years", "pilot_overlap", "oil_fuel"}),
         ("scenario: pre-war gas = steam", {"outlier_years", "pilot_overlap", "oil_fuel", "prewar_steam"})]
imp_rows = []
for label, fl in steps:
    c = L.ctx_for(ctx, fl)
    for mem, h in NETS:
        r = L.evaluate(mem, h, c, fl)
        imp_rows.append(dict(step=label, **{k: r[k] for k in ("members", "horizon", "heat_recovered_MWh", "heat_delivered_MWh", "net_societal_value",
                                                              "co2_avoided_t", "low_income_households_strict")}))
imp = pd.DataFrame(imp_rows)
base = imp[imp.step == "original"].set_index("members")
imp["d_net_value_vs_original"] = imp.net_societal_value - imp.members.map(base.net_societal_value)
imp["d_co2_vs_original"] = imp.co2_avoided_t - imp.members.map(base.co2_avoided_t)
imp.to_csv(OUT / "cleaning_impact_summary.csv", index=False)
print(imp.pivot(index="members", columns="step", values="net_societal_value").round(0).to_string())
