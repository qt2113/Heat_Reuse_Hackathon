"""Targeted gap-fill sources for the Site 1 data layer (run from fetch_site1_data.py, or alone).

S13 Con Edison Chelsea UTEN pilot - Stage 2 filing (PSC Case 22-M-0429, 9 Jul 2025): scope, loads, costs, prices
S14 Con Edison steam tariff PSC No. 4 - SC 2 Rate II + monthly fuel adjustments
S15 EIA-861 (2024) utility-level revenue/sales: Con Edison and NYPA
S16 BLS CPI-U and FRB EUR/USD (FRED AEXUSEU) for cost escalation / currency
S17 EPA AP-42 Section 1.4 natural-gas combustion factors
S18 Rebuild facts (Fulton/Elliott-Chelsea FAQ, NYCHA press release) + NIST Handbook 135 discount rates
S19 Unit constants (ENERGY STAR thermal conversions) + ENERGY STAR cold-climate ASHP criterion (via EIA 2023)

Transcribed values carry the page and a verbatim snippet; `verified` is True only when the snippet is found
in the downloaded document's text (whitespace-normalised). Nothing is estimated here except rows marked
basis='derived', whose formula is written out in the row.
"""
import io, re, zipfile
import pandas as pd

from fetch_site1_data import RAW, PROC, REF, CACHE, cached, get, log, OFFLINE, KBTU_PER_MWH

MMBTU_PER_MWH = 3.412142


def _pdf_text(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    norm = lambda s: re.sub(r"\s+", " ", s.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-"))
    return [norm(p) for p in pages], norm(" ".join(pages))


def _verify(rows, full_text, key="quote"):
    for r in rows:
        q = re.sub(r"\s+", " ", str(r[key]))
        r["verified"] = bool(q) and q in full_text
    return rows


# --------------------------------------------------------------------------------------------
# S13 Con Edison Chelsea UTEN pilot, Stage 2 filing
# --------------------------------------------------------------------------------------------
UTEN_URL = ("https://www.coned.com/-/media/files/coned/documents/our-energy-future/our-energy-vision/"
            "where-we-are-going/thermal-energy-networks/chelsea-uten-cecony-stage-2-filing.pdf")
UTEN = [  # section, metric, value, unit, page, quote
    ("scope", "heat_source_building", "85 10th Avenue (commercial office with data center; Related/Vornado)", "", 7, "recover and repurpose thermal energy from the commercial office building housing a data center at 85 10th Avenue"),
    ("scope", "apartments_served", 291, "apartments", 7, "serving a total of 291 apartments"),
    ("scope", "residential_floor_area", 262000, "ft2", 8, "approximately 262,000 square feet"),
    ("scope", "google_111_8th_status", "expressed interest in potentially joining", "", 66, "most notably one owned by Google-have expressed interest in potentially joining the UTEN"),
    ("technical", "source_low_grade_capacity", 5000, "MBH", 20, "approximately 5,000 MBH of low-grade thermal energy"),
    ("technical", "source_cooling_tower_backup_capacity", 4800, "tons", 20, "combined capacity of 4,800 tons"),
    ("technical", "pipe_installed_total", 2500, "ft (supply+return)", 20, "approximately 2,500 linear feet of underground piping"),
    ("technical", "route_length_one_way", 1250, "ft", 48, "approximately 1,250 feet in length"),
    ("technical", "dhw_delivery_capacity", 1492, "MBH", 20, "up to 1,492 MBH of domestic hot water"),
    ("technical", "space_heating_delivery_capacity", 1201, "MBH", 20, "1,201 MBH of heating"),
    ("technical", "cooling_delivery_capacity", 948, "MBH", 20, "948 MBH (~79 tons) of cooling"),
    ("technical", "source_chilled_water_supply_temp", 48, "degF", 36, "provides 48°F chilled water"),
    ("technical", "source_chilled_water_return_temp", 60, "degF", 36, "return chilled water temperature of 60°F"),
    ("technical", "loop_supply_temp_heating_mode_min", 54, "degF", 46, "UDS supply temperatures ranging from 54 °F to 97 °F during heating mode"),
    ("technical", "loop_supply_temp_heating_mode_max", 97, "degF", 46, "UDS supply temperatures ranging from 54 °F to 97 °F during heating mode"),
    ("technical", "loop_temp_range_all_modes_min", 46, "degF", 51, "temperature range (46 - 126 °F)"),
    ("technical", "loop_temp_range_all_modes_max", 126, "degF", 51, "temperature range (46 - 126 °F)"),
    ("technical", "loop_min_flow", 386, "GPM", 51, "minimum flow (386 GPM)"),
    ("technical", "dhw_design_temperature", 140, "degF", 37, "The domestic hot water temperature was designed to be 140 °F"),
    ("technical", "design_day_heating_dry_bulb", 17.9, "degF", 38, "a dry bulb high of 17.9 °F was used"),
    ("technical", "hours_per_year_rejecting_heat_to_source", 10, "h/yr", 44, "only need to reject heat to 85 10th Avenue ~10 hours of the year"),
    ("technical", "backup_heat", "new Con Ed steam service to a shell-and-tube HX at 401 W 16th St; existing steam radiators retained", "", 23, "Incorporating a new steam-to-hot water heat exchanger in 401 W 16th Street"),
    ("technical", "redundancy", "n+1 UDS distribution pumps", "", 23, "Providing an \"n+1 redundancy\""),
    ("loads", "dhw_load_401_W_16th", 1769, "MMBtu/yr", 66, "401 W 16th St. 1,769 1,186 1.20 956 0.92"),
    ("loads", "space_heating_load_401_W_16th", 1186, "MMBtu/yr", 66, "401 W 16th St. 1,769 1,186 1.20 956 0.92"),
    ("loads", "space_heating_peak_401_W_16th", 1.20, "MMBtu/h", 66, "401 W 16th St. 1,769 1,186 1.20 956 0.92"),
    ("loads", "space_cooling_load_401_W_16th", 956, "MMBtu/yr", 66, "401 W 16th St. 1,769 1,186 1.20 956 0.92"),
    ("loads", "dhw_load_410_W_17th", 4422, "MMBtu/yr", 66, "410 W 17th St. 4,422"),
    ("loads", "dhw_load_420_W_17th", 1769, "MMBtu/yr", 66, "420 W 17th St. 1,769"),
    ("energy", "customer_electricity_pre", 2923517, "kWh/yr", 67, "2,923,517"),
    ("energy", "customer_electricity_during", 3771007, "kWh/yr", 67, "3,771,007"),
    ("energy", "customer_winter_peak_pre", 362, "kW", 67, "Pre-UTEN 2,923,517 362"),
    ("energy", "customer_winter_peak_during", 682, "kW", 67, "3,771,007 682"),
    ("energy", "customer_steam_pre", 23093, "Mlb/yr", 67, "23,093"),
    ("energy", "customer_steam_during", 13132, "Mlb/yr", 67, "13,132"),
    ("energy", "customer_steam_peak_pre", 16, "Mlb/h", 67, "23,093 16"),
    ("energy", "customer_steam_peak_during", 13, "Mlb/h", 67, "13,132 13"),
    ("energy", "source_building_electricity_delta", 666060, "kWh/yr", 68, "Delta 666,060"),
    ("energy", "source_building_january_peak_delta", -8, "kW", 68, "Delta 666,060 688,719 -22,658 -8 -24"),
    ("energy", "pilot_vs_ASHP_annual_electricity", "about 40% more electricity throughout the year (10-15% more on peak days)", "", 68, "use about 40% more electricity throughout the year"),
    ("carbon", "lifetime_GHG_reduction_claim", 15000, "tCO2e (lifetime)", 14, "15,000 metric tons of lifetime Greenhouse Gas (GHG) emissions equivalent"),
    ("cost", "UDS_construction", 11.17, "MUSD", 90, "UDS - - 11.17 - - 11.17"),
    ("cost", "thermal_resource_construction", 2.56, "MUSD", 90, "Resource - - 2.56 - - 2.56"),
    ("cost", "energy_center_construction", 2.69, "MUSD", 90, "- - 2.69 - - 2.69"),
    ("cost", "customer_building_construction", 18.57, "MUSD", 90, "Building - - 18.57 - - 18.57"),
    ("cost", "administrative", 16.26, "MUSD", 90, "Administrative 0.35 0.89 4.92 10.00 0.10 16.26"),
    ("cost", "design", 10.08, "MUSD", 90, "Design 0.13 6.66 3.19 0.10 - 10.08"),
    ("cost", "outreach_education", 0.78, "MUSD", 90, "- - 0.73 0.05 - 0.78"),
    ("cost", "operational_5yr", 18.37, "MUSD", 90, "Operational - - - 18.37 - 18.37"),
    ("cost", "scada_data_collection", 3.64, "MUSD", 90, "- - 1.70 1.93 - 3.64"),
    ("cost", "total_excl_contingency", 84.12, "MUSD", 90, "Total 0.48 7.55 45.53 30.45 0.10 84.12"),
    ("cost", "construction_stage3_excl_contingency", 45.53, "MUSD", 90, "Total 0.48 7.55 45.53 30.45 0.10 84.12"),
    ("cost", "contingency", 11.41, "MUSD", 90, "Contingency - - 6.83 4.57 0.02 11.41"),
    ("cost", "total_incl_contingency", 95.53, "MUSD", 90, "0.48 7.55 52.36 35.02 0.12 95.53"),
    ("cost", "decommissioning", 13.3, "MUSD", 92, "approximately $13.3 million"),
    ("cost", "reusable_for_rebuild", 19, "MUSD", 15, "This equipment eligible for reuse represents $19 million"),
    ("cost", "cost_assumptions", "10% tariff on construction materials; 3% annual inflation; 15% contingency", "", 89, "assume a 10% tariff on all material related to construction costs and 3% annual inflation"),
    ("price", "heat_purchase_price_paid_to_source", 26.0, "USD/MMBtu", 101, "The draft $/MMBtu price for heat injection and heat dissipation are $26/MMBtu"),
    ("price", "customer_thermal_rate", 26.63, "USD/MMBtu", 102, "MMBtu will be $26.63 for thermal heating and cooling"),
    ("price", "customer_fixed_connection_charge", 5000, "USD/yr", 102, "fixed connection charge is set at $5,000 a year"),
    ("price", "cost_based_rate_vs_pilot_rate", "151.93 vs 0.12", "USD per MBH of HX capacity", 103, "$0.12 per MBH of heat exchanger capacity vs. $151.93 per MBH heat exchanger capacity"),
    ("revenue", "source_thermal_revenues_yr1", 132, "kUSD/yr", 101, "$132"),
    ("revenue", "source_incremental_electricity_cost_yr1", -97, "kUSD/yr", 101, "($97)"),
    ("revenue", "source_incremental_om_yr1", -30, "kUSD/yr", 101, "($30)"),
    ("revenue", "source_net_thermal_revenues_yr1_as_published", 538, "kUSD/yr", 101, "$538"),
    ("customer_bill", "steam_savings", 375, "kUSD/yr", 102, "Steam Savings $375"),
    ("customer_bill", "thermal_usage_cost", -146, "kUSD/yr", 102, "Thermal Usage Cost ($146)"),
    ("customer_bill", "thermal_connection_cost", -5, "kUSD/yr", 102, "Thermal Connection Cost ($5)"),
    ("customer_bill", "incremental_electricity_cost", -193, "kUSD/yr", 102, "Incremental Electricity Costs ($193)"),
    ("customer_bill", "incremental_om_cost", -30, "kUSD/yr", 102, "Incremental O&M Costs ($30)"),
    ("customer_bill", "net_annual_savings", 1, "kUSD/yr", 102, "Net Annual Savings $1"),
    ("governance", "owner_operator", "Con Edison (regulated utility) owns UDS and Energy Center; NYCHA owns buildings; PACT partners manage", "", 7, "The Chelsea Pilot's participants include NYCHA, which owns the Fulton Houses campus"),
    ("governance", "pilot_and_contract_term", 5, "years", 104, "Limiting Customer Agreements to the duration of the 5-year Pilot period"),
    ("governance", "risk_sharing_supply", "85 10th Ave commits a monthly minimum of heat; revenue reduced for shortfall", "", 108, "85 10th Avenue will need to commit to providing each month a to be negotiated minimum"),
    ("governance", "risk_sharing_offtake", "customer guaranteed minimum purchase; shortfall compensation up to a cap", "", 108, "up to a set cap"),
    ("governance", "ITC_eligibility", "ITC does not apply to non-geothermal projects (Company's finding)", "", 93, "the ITC does not apply to non-geothermal projects"),
    ("governance", "customer_electric_supplier", "Fulton Houses is a NYPA electric customer", "", 100, "Fulton Houses is a NYPA electric customer"),
    ("governance", "LL97_applicability_NYCHA", "NYCHA not subject to LL97 fines (per filing)", "", 102, "NYCHA is not subject to them"),
    ("governance", "ratepayer_bill_impact_electric", "0.06% / 0.05%", "", 95, "Electric Customers 0.06% 0.05%"),
    ("context", "fulton_rebuild_start", "late 2028; UTEN-connected block rebuilt last", "", 15, "The rebuild, targeted to begin in late 2028"),
]


def s13_chelsea_uten():
    p = cached("coned_chelsea_uten_stage2.pdf", UTEN_URL, timeout=300)
    pages, full = _pdf_text(p)
    rows = [dict(section=s, metric=m, value=v, unit=u, page=pg, quote=q) for s, m, v, u, pg, q in UTEN]
    rows = _verify(rows, full)
    df = pd.DataFrame(rows)
    df["source"] = "Con Edison, Chelsea UTEN Pilot Stage 2 Filing, PSC Case 22-M-0429, 2025-07-09"
    df["url"] = UTEN_URL
    df["note"] = ""
    df.loc[df.metric == "source_net_thermal_revenues_yr1_as_published", "note"] = \
        "As published; inconsistent with components (132-97-30 = 5). Do not use without clarification."
    df.loc[df.unit.isin(["MUSD"]), "note"] = "Nominal USD incl. 10% material tariff and 3%/yr inflation assumptions of the filing"
    df.to_csv(REF / "chelsea_uten_pilot_stage2.csv", index=False)

    v = {r["metric"]: r["value"] for r in rows}
    useful_mmbtu = v["dhw_load_401_W_16th"] + v["dhw_load_410_W_17th"] + v["dhw_load_420_W_17th"] + v["space_heating_load_401_W_16th"]
    steam_saved_mlb = v["customer_steam_pre"] - v["customer_steam_during"]
    el_added_kwh = v["customer_electricity_during"] - v["customer_electricity_pre"] + v["source_building_electricity_delta"]
    d = [
        ("useful_heat_supplied_by_UTEN", useful_mmbtu / MMBTU_PER_MWH, "MWh/yr", "sum(Table 5 DHW + 401 W 16th space heating) / 3.412"),
        ("steam_saved", steam_saved_mlb, "Mlb/yr", "Table 6 steam pre - during"),
        ("steam_to_useful_heat_efficiency", useful_mmbtu / (steam_saved_mlb * 1.194), "-", "useful MMBtu / (steam saved Mlb x 1.194 MMBtu/Mlb)"),
        ("implied_marginal_steam_cost_per_Mlb", v["steam_savings"] * 1000 / steam_saved_mlb, "USD/Mlb", "Table 14 steam savings / steam saved"),
        ("implied_marginal_steam_cost_per_MWh_steam", v["steam_savings"] * 1000 / (steam_saved_mlb * 1.194 / MMBTU_PER_MWH), "USD/MWh(steam energy)", "steam savings / (Mlb x 1.194 / 3.412)"),
        ("implied_steam_cost_per_MWh_useful_heat", v["steam_savings"] * 1000 / (useful_mmbtu / MMBTU_PER_MWH), "USD/MWh(useful)", "steam savings / useful MWh"),
        ("heat_purchase_price_per_MWh", v["heat_purchase_price_paid_to_source"] * MMBTU_PER_MWH, "USD/MWh", "26 USD/MMBtu x 3.412"),
        ("customer_thermal_rate_per_MWh", v["customer_thermal_rate"] * MMBTU_PER_MWH, "USD/MWh", "26.63 USD/MMBtu x 3.412"),
        ("electricity_added_customer_plus_source", el_added_kwh / 1000, "MWh/yr", "Table 6 delta + Table 8 delta"),
        ("system_heat_per_electricity_added", (useful_mmbtu / MMBTU_PER_MWH) / (el_added_kwh / 1000), "MWh_th/MWh_e", "useful heat / all added electricity (cooling of 401 W 16th also served; approximate system COP)"),
        ("construction_cost_per_apartment", v["construction_stage3_excl_contingency"] * 1e6 / v["apartments_served"], "USD/apartment", "45.53 M / 291"),
        ("all_stage_cost_per_apartment", v["total_incl_contingency"] * 1e6 / v["apartments_served"], "USD/apartment", "95.53 M / 291"),
        ("UDS_cost_per_route_ft", v["UDS_construction"] * 1e6 / v["route_length_one_way"], "USD/route-ft", "11.17 M / 1,250 ft (two pipes)"),
        ("UDS_cost_per_route_m", v["UDS_construction"] * 1e6 / (v["route_length_one_way"] * 0.3048), "USD/route-m", "11.17 M / 381 m"),
        ("customer_building_cost_per_apartment", v["customer_building_construction"] * 1e6 / v["apartments_served"], "USD/apartment", "18.57 M / 291"),
        ("annual_GHG_change_LL97_factors", (steam_saved_mlb * 1194 * 0.00004493) - (el_added_kwh * 0.000288962), "tCO2e/yr", "steam saved x 1,194 kBtu/Mlb x 4.493e-5 - added kWh x 2.88962e-4 (LL97 2024-29)"),
    ]
    out = pd.DataFrame(d, columns=["metric", "value", "unit", "formula"])
    out["basis"] = "derived from chelsea_uten_pilot_stage2.csv"
    out.to_csv(PROC / "chelsea_uten_benchmarks.csv", index=False)
    log(f"       S13 verified {df.verified.sum()}/{len(df)} transcribed rows")


# --------------------------------------------------------------------------------------------
# S14 Con Edison steam tariff (PSC No. 4) - SC 2 Rate II + fuel adjustment history
# --------------------------------------------------------------------------------------------
STEAM_TARIFF_URL = ("https://edge-e-dcxprod-web-bechbkdqagefb9ge.a03.azurefd.net/-/media/files/coned/documents/rates/steam/"
                    "steam-tariff.pdf?rev=9a02fe01a86a46dfbd421d21d1a91298&hash=C472A38696542EF6542E66DD4355FD82")
STEAM_FADJ_URL = "https://www.coned.com/-/media/files/coned/documents/rates/steam/fuel-adjustments/fadj-2024-current.pdf"
SC2_RATE2 = [  # season, block_from_Mlb, block_to_Mlb, charge, unit, quote
    ("May-Oct", 0, 250, 23.057, "USD/Mlb", "For the first 250 Mlb $23.057 / Mlb"),
    ("May-Oct", 250, 1000, 19.065, "USD/Mlb", "For the next 750 Mlb $19.065 / Mlb"),
    ("May-Oct", 1000, None, 16.799, "USD/Mlb", "For excess over 1,000 Mlb $16.799 / Mlb"),
    ("Dec-Mar", 0, 250, 39.411, "USD/Mlb", "For the first 250 Mlb $39.411 / Mlb"),
    ("Dec-Mar", 250, 1500, 38.084, "USD/Mlb", "For the next 1,250 Mlb $38.084 / Mlb"),
    ("Dec-Mar", 1500, 5000, 34.444, "USD/Mlb", "For the next 3,500 Mlb $34.444 / Mlb"),
    ("Dec-Mar", 5000, 25000, 31.782, "USD/Mlb", "For the next 20,000 Mlb $31.782 / Mlb"),
    ("Dec-Mar", 25000, None, 26.974, "USD/Mlb", "For excess over 25,000 Mlb $26.974 / Mlb"),
    ("Nov+Apr", 0, 250, 49.562, "USD/Mlb", "For the first 250 Mlb $49.562 / Mlb"),
    ("Nov+Apr", 250, 1500, 48.232, "USD/Mlb", "For the next 1,250 Mlb $48.232 / Mlb"),
    ("Nov+Apr", 1500, 5000, 42.067, "USD/Mlb", "For the next 3,500 Mlb $42.067 / Mlb"),
    ("Nov+Apr", 5000, 25000, 38.997, "USD/Mlb", "For the next 20,000 Mlb $38.997 / Mlb"),
    ("Nov+Apr", 25000, None, 28.083, "USD/Mlb", "For excess over 25,000 Mlb $28.083 / Mlb"),
    ("Dec-Mar demand, weekdays 6-11 am", None, None, 2577.96, "USD per Mlb/hr of max demand", "$2,577.96 / Mlb/hr"),
    ("Dec-Mar demand, all hours", None, None, 267.80, "USD per Mlb/hr of max demand", "$267.80 / Mlb/hr"),
    ("customer charge", None, None, 7527.43, "USD/month", "$7,527.43 per month"),
]


def s14_coned_steam():
    p = cached("coned_steam_tariff.pdf", STEAM_TARIFF_URL, timeout=300)
    _, full = _pdf_text(p)
    rows = [dict(component=s, block_from_Mlb=a, block_to_Mlb=b, charge=c, unit=u, quote=q) for s, a, b, c, u, q in SC2_RATE2]
    df = pd.DataFrame(_verify(rows, full))
    df["tariff"] = "Con Edison PSC No. 4 - Steam, Service Classification No. 2 (Annual Power Service) Rate II, leaves 73-75, effective 11/01/2025"
    df["applicability"] = "Customers with >= 14,000 Mlb over the 12 billing periods ending August (Fulton LL84 ~84,000 Mlb/yr qualifies)"
    df["excludes"] = "Fuel adjustment, increase in rates and charges (GRT etc.), monthly adjustments/surcharges, sales tax"
    df["url"] = "https://www.coned.com/en/rates-tariffs/rates/steam"
    df.to_csv(RAW / "s14_coned_steam_tariff_sc2_rate2.csv", index=False)

    q = cached("coned_steam_fuel_adjustment.pdf", STEAM_FADJ_URL)
    pages, full = _pdf_text(q)
    fa = [(m.group(1), m.group(2)) for m in re.finditer(r"(\d{2}/\d{2}/\d{4})\s+(\(?-?[\d.]+\)?)", full)]
    fdf = pd.DataFrame(fa, columns=["effective_date", "fuel_adjustment_cents_per_Mlb"])
    fdf["fuel_adjustment_cents_per_Mlb"] = fdf.fuel_adjustment_cents_per_Mlb.str.replace(r"^\((.*)\)$", r"-\1", regex=True).astype(float)
    fdf["effective_date"] = pd.to_datetime(fdf.effective_date, format="%m/%d/%Y")
    base = re.search(r"base cost of fuel is ([\d.]+) cents per 1,000 pounds", full)
    fdf["base_cost_of_fuel_cents_per_Mlb"] = float(base.group(1)) if base else None
    fdf["url"] = STEAM_FADJ_URL
    fdf.to_csv(RAW / "s14_coned_steam_fuel_adjustment.csv", index=False)

    # processed: indicative energy-only cost for a Fulton-sized customer, using LL84 annual steam and an
    # HDD-shaped monthly split (method, not observation); fuel adjustment = mean of the last 12 values
    fa12 = fdf.sort_values("effective_date").tail(12).fuel_adjustment_cents_per_Mlb.mean() / 100
    out = [("fuel_adjustment_last12_mean", fa12, "USD/Mlb", "mean of last 12 monthly statements"),
           ("SC2_RateII_winter_tail_block", 26.974, "USD/Mlb", "Dec-Mar >25,000 Mlb block"),
           ("SC2_RateII_winter_5000_25000_block", 31.782, "USD/Mlb", "Dec-Mar 5,000-25,000 Mlb block"),
           ("SC2_RateII_summer_tail_block", 16.799, "USD/Mlb", "May-Oct >1,000 Mlb block"),
           ("steam_energy_content", 1.194, "MMBtu/Mlb", "ENERGY STAR Portfolio Manager conversion (S19)")]
    pd.DataFrame(out, columns=["parameter", "value", "unit", "basis"]).to_csv(PROC / "steam_tariff_summary.csv", index=False)
    log(f"       S14 tariff rows verified {df.verified.sum()}/{len(df)}; fuel adjustments parsed {len(fdf)}")


# --------------------------------------------------------------------------------------------
# S15 EIA-861 2024: utility-level average revenue per MWh (Con Edison, NYPA)
# --------------------------------------------------------------------------------------------
def s15_eia861():
    p = cached("f8612024.zip", "https://www.eia.gov/electricity/data/eia861/zip/f8612024.zip", timeout=300)
    d = pd.read_excel(zipfile.ZipFile(p).open("Sales_Ult_Cust_2024.xlsx"), header=None, skiprows=3)
    d = d.iloc[:, :24]
    d.columns = ["year", "utility_number", "utility_name", "part", "service_type", "data_type", "state", "ownership", "ba",
                 "res_rev_kUSD", "res_MWh", "res_cust", "com_rev_kUSD", "com_MWh", "com_cust", "ind_rev_kUSD", "ind_MWh",
                 "ind_cust", "tra_rev_kUSD", "tra_MWh", "tra_cust", "tot_rev_kUSD", "tot_MWh", "tot_cust"]
    d = d[(d.state == "NY") & d.utility_number.isin([4226, 15296])].copy()
    d.to_csv(RAW / "s15_eia861_2024_coned_nypa.csv", index=False)
    rows = []
    for _, r in d.iterrows():
        for s in ("res", "com", "ind"):
            rev, mwh = pd.to_numeric(r[f"{s}_rev_kUSD"], errors="coerce"), pd.to_numeric(r[f"{s}_MWh"], errors="coerce")
            if pd.notna(rev) and pd.notna(mwh) and mwh > 0:
                rows.append(dict(year=2024, utility=r.utility_name, part=r.part, service_type=r.service_type, sector=s,
                                 revenue_kUSD=rev, sales_MWh=mwh, avg_USD_per_MWh=round(rev * 1000 / mwh, 1)))
    out = pd.DataFrame(rows)
    out["note"] = ("Bundled = energy+delivery; Delivery = delivery-only customers (energy bought elsewhere, e.g. NYPA); "
                   "NYPA Energy = energy-only. Averages include fixed and demand charges.")
    out.to_csv(PROC / "utility_avg_prices_2024.csv", index=False)


# --------------------------------------------------------------------------------------------
# S16 BLS CPI-U (US city average, all items) annual averages + FRB EUR/USD annual (FRED AEXUSEU)
# --------------------------------------------------------------------------------------------
def s16_macro():
    out_cpi, out_fx = RAW / "s16_bls_cpi_u.csv", RAW / "s16_fred_aexuseu.csv"
    if not OFFLINE:
        import requests
        j = requests.post("https://api.bls.gov/publicAPI/v1/timeseries/data/",
                          json={"seriesid": ["CUUR0000SA0"], "startyear": "2017", "endyear": "2026"},
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=60).json()
        cpi = pd.DataFrame(j["Results"]["series"][0]["data"])[["year", "period", "value"]]
        cpi.to_csv(out_cpi, index=False)
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=AEXUSEU"
        try:
            out_fx.write_text(get(url, timeout=60).text)
        except Exception:  # noqa: BLE001  FRED sometimes drops python clients; curl is accepted
            import subprocess
            out_fx.write_text(subprocess.run(["curl", "-s", "-L", "-m", "60", url], capture_output=True, text=True, check=True).stdout)
    cpi = pd.read_csv(out_cpi)
    cpi["year"] = pd.to_numeric(cpi.year)
    cpi["value"] = pd.to_numeric(cpi.value, errors="coerce")
    ann = cpi[cpi.period == "M13"] if (cpi.period == "M13").any() else None
    if ann is None or ann.empty:  # v1 API returns monthly only: compute calendar-year means of complete years
        m = cpi[cpi.period.str.match(r"M(0[1-9]|1[0-2])")]
        cnt = m.groupby("year").value.count()  # BLS published no Oct-2025 value ("-"): allow 11 of 12 months
        ok = cnt[cnt >= 11].index
        ann = m[m.year.isin(ok)].groupby("year").value.mean().reset_index()
        ann["cpi_months_used"] = ann.year.map(cnt)
    else:
        ann = ann[["year", "value"]]
    fx = pd.read_csv(out_fx)
    fx.columns = ["date", "usd_per_eur"]
    fx["usd_per_eur"] = pd.to_numeric(fx.usd_per_eur, errors="coerce")
    fx["year"] = pd.to_datetime(fx.date).dt.year
    t = ann.rename(columns={"value": "cpi_u_annual_avg"}).merge(fx[["year", "usd_per_eur"]], on="year", how="outer").sort_values("year")
    latest = t.dropna(subset=["cpi_u_annual_avg"]).iloc[-1]
    t["cpi_factor_to_latest_full_year"] = latest.cpi_u_annual_avg / t.cpi_u_annual_avg
    t["latest_full_year"] = int(latest.year)
    t.to_csv(PROC / "macro_cpi_fx.csv", index=False)


# --------------------------------------------------------------------------------------------
# S17 EPA AP-42 Section 1.4 (natural gas combustion), Tables 1.4-1 and 1.4-2
# --------------------------------------------------------------------------------------------
AP42_URL = "https://www.epa.gov/sites/default/files/2020-09/documents/1.4_natural_gas_combustion.pdf"
AP42 = [  # pollutant, boiler class, control, lb_per_1e6_scf, quote
    ("NOx", "small boilers (<100 MMBtu/h)", "uncontrolled", 100, "Small Boilers (<100) Uncontrolled 100 B 84 B"),
    ("NOx", "small boilers (<100 MMBtu/h)", "low NOx burners", 50, "Small Boilers (<100) Low NO burners 50 D 84 B"),
    ("NOx", "small boilers (<100 MMBtu/h)", "low NOx burners / flue gas recirculation", 32, "Small Boilers (<100) Low NO burners/Flue gas recirculation 32 C 84 B"),
    ("CO", "small boilers (<100 MMBtu/h)", "any", 84, "84"),
    ("PM total", "all", "any", 7.6, "PM (Total)c 7.6"),
    ("PM condensable", "all", "any", 5.7, "PM (Condensable)c 5.7"),
    ("HHV basis", "all", "", 1020, "1,020 British thermal units per standard cubic foot"),
]


def s17_ap42():
    p = cached("ap42_1-4_natural_gas.pdf", AP42_URL)
    _, full = _pdf_text(p)
    rows = [dict(pollutant=a, boiler_class=b, control=c, lb_per_1e6_scf=v, quote=q) for a, b, c, v, q in AP42]
    df = pd.DataFrame(_verify(rows, full))
    df["lb_per_MMBtu"] = df.lb_per_1e6_scf / 1020
    df.loc[df.pollutant == "HHV basis", "lb_per_MMBtu"] = None
    df["kg_per_MWh_fuel"] = df.lb_per_MMBtu * 0.45359237 * MMBTU_PER_MWH
    df["source"] = "US EPA AP-42 5th ed., Section 1.4 Natural Gas Combustion (07/98), Tables 1.4-1/1.4-2"
    df["url"] = AP42_URL
    df.to_csv(REF / "ap42_natural_gas_boilers.csv", index=False)


# --------------------------------------------------------------------------------------------
# S18 Rebuild facts + NIST Handbook 135 discount rates; S19 constants + cold-climate ASHP criterion
# --------------------------------------------------------------------------------------------
FEC_FAQ = "https://www.fultonelliottchelsea.com/faqs"
NYCHA_PR = "https://www.nyc.gov/site/nycha/about/press/pr-2025/pr-20250328.page"
NIST_URL = "https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957696"
ES_URL = "https://portfoliomanager.energystar.gov/pdf/reference/Thermal%20Conversions.pdf"
FEC_ROWS = [  # metric, value, unit, url, quote
    ("existing_NYCHA_apartments_replaced", 2056, "apartments", NYCHA_PR, "rebuild all 2,056 existing units"),
    ("new_mixed_income_units_up_to", 3454, "units", NYCHA_PR, "up to 3,454 new mixed-income units"),
    ("new_affordable_apartments_approx", 875, "apartments", NYCHA_PR, "approximately 875 new affordable apartments"),
    ("households_staying_during_construction", 0.94, "share", NYCHA_PR, "94 percent of all households"),
    ("first_demolition", "Chelsea Addition and Fulton 11, summer 2025 (subject to EIS)", "", FEC_FAQ, "Demolition of Chelsea Addition and Fulton 11 is currently scheduled for summer of 2025"),
    ("first_move_ins", "end of 2028", "", FEC_FAQ, "The anticipated start for the first move-ins is the end of 2028"),
    ("phase_sequence", "Phase 2 commences once Phase 1 completes", "", FEC_FAQ, "Phase 2 shall commence once Phase 1 completes"),
    ("new_building_heating", "move from gas and steam towards electric and renewable powered heating and cooling", "", FEC_FAQ, "The new buildings will move from gas and steam heating systems towards electric and renewable powered heating and cooling systems"),
    ("in_unit_controls", "each new unit has controllable heating and cooling", "", FEC_FAQ, "controllable heating and cooling"),
    ("jobs", "4,000 construction + 300 property management", "jobs", FEC_FAQ, "An estimated 4,000 construction and 300 property management jobs"),
]


def s18_context_and_rates():
    faq_text = ""
    try:
        h = get(FEC_FAQ).text
        faq_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", h)))
        faq_text = faq_text.replace("&#39;", "'").replace("’", "'")
    except Exception as e:  # noqa: BLE001
        log(f"       FEC FAQ not reachable ({e})")
    rows = []
    for m, v, u, url, q in FEC_ROWS:
        ver = (q in faq_text) if url == FEC_FAQ else None  # nyc.gov blocks scripted requests: verified manually 2026-10-03
        rows.append(dict(metric=m, value=v, unit=u, url=url, quote=q, verified=ver,
                         accessed="2026-10-03", note="" if url == FEC_FAQ else "transcribed via browser fetch; nyc.gov refuses scripted downloads"))
    pd.DataFrame(rows).to_csv(REF / "fec_rebuild_facts.csv", index=False)

    p = cached("nist_ir_85-3273-39.pdf", NIST_URL)
    _, full = _pdf_text(p)
    nist = [("DOE_FEMP_real_discount_rate", 0.030, "Real rate (excluding general price inflation): 3.0 %"),
            ("DOE_FEMP_nominal_discount_rate", 0.042, "Nominal rate (including general price inflation): 4.2 %")]
    r = [dict(parameter=a, value=b, unit="fraction/yr", quote=q) for a, b, q in nist]
    r = _verify(r, full)
    df = pd.DataFrame(r)
    df["source"] = "NIST IR 85-3273-39, Energy Price Indices and Discount Factors for LCC Analysis - 2024 Annual Supplement to NIST Handbook 135"
    df["url"] = NIST_URL
    df.to_csv(REF / "discount_rates_nist135.csv", index=False)


def s19_constants():
    rows = []
    try:
        p = cached("energystar_thermal_conversions.pdf", ES_URL)
        _, full = _pdf_text(p)
        ok = "1,194" in full
    except Exception as e:  # noqa: BLE001
        ok, full = None, ""
        log(f"       ENERGY STAR conversions unavailable ({e})")
    rows.append(dict(constant="district_steam_energy_content", value=1194, unit="kBtu per Mlb (Btu/lb)", verified=ok,
                     source="ENERGY STAR Portfolio Manager Technical Reference: Thermal Energy Conversions", url=ES_URL))
    rows.append(dict(constant="kBtu_per_MWh", value=KBTU_PER_MWH, unit="kBtu/MWh", verified=True, source="definition", url=""))
    try:
        eia = cached("eia_equipcosts_2023.pdf", "https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/full.pdf", timeout=300)
        _, full = _pdf_text(eia)
        ok = "Coefficient of Performance (COP) at 5 degrees Fahrenheit" in full
    except Exception:  # noqa: BLE001
        ok = None
    rows.append(dict(constant="ENERGY_STAR_cold_climate_ASHP_min_COP_at_5F", value=1.75, unit="COP at 5 F (-15 C)", verified=ok,
                     source="EIA Updated Buildings Sector Equipment Costs (2023), Residential ASHP section, citing ENERGY STAR cold-climate criteria",
                     url="https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/full.pdf"))
    pd.DataFrame(rows).to_csv(REF / "unit_constants.csv", index=False)


STEPS = [s13_chelsea_uten, s14_coned_steam, s15_eia861, s16_macro, s17_ap42, s18_context_and_rates, s19_constants]

if __name__ == "__main__":
    from fetch_site1_data import step, validate
    for fn in STEPS:
        step(fn)
    validate()
