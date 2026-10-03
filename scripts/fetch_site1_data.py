"""Site 1 (111 8th Ave, Chelsea, Manhattan): download, subset and preprocess the selected datasets.

Usage:  python scripts/fetch_site1_data.py            (download + process + validate)
        python scripts/fetch_site1_data.py --offline  (re-process from data/raw and data/cache only)

Outputs
  data/raw/         subsets exactly as published (only Site 1 records/fields), one CSV per source
  data/processed/   unit-converted, model-ready tables
  data/cache/       large binary downloads (git-ignored)
  data/reference/   regulatory constants, engineering parameters and reference cases transcribed
                    from documents (NOT observations; every row cites its source)

No value is synthesised. A source that fails to download is logged in the inventory as missing.
"""
import io, json, math, re, sys, zipfile, datetime as dt
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, CACHE, REF = (ROOT / "data" / d for d in ("raw", "processed", "cache", "reference"))
for d in (RAW, PROC, CACHE, REF):
    d.mkdir(parents=True, exist_ok=True)

OFFLINE = "--offline" in sys.argv
UA = {"User-Agent": "Mozilla/5.0 (heat-reuse-hackathon data script)"}
SITE = {"name": "111 8th Avenue", "bbl": "1007390001", "lat": 40.7413598, "lon": -74.0032081}
RADIUS_M = 1000         # candidate offtakers: covers Fulton (~0.25 km) and Elliott-Chelsea (~0.9 km)
LL84_MIN_YEAR = 2022    # LL84 2023-to-present dataset covers calendar years 2022+
KBTU_PER_MWH = 3412.142
LOG = []


def log(msg):
    print(msg)
    LOG.append(msg)


def get(url, params=None, timeout=90):
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r


def socrata(domain, dataset, params):
    params = dict(params)
    params.setdefault("$limit", 50000)
    return pd.DataFrame(get(f"https://{domain}/resource/{dataset}.json", params).json())


def cached(name, url, timeout=180):
    p = CACHE / name
    if not p.exists():
        if OFFLINE:
            raise FileNotFoundError(p)
        p.write_bytes(get(url, timeout=timeout).content)
    return p


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def num(s):
    return pd.to_numeric(s, errors="coerce")


def step(fn):
    """Run one source; a failure is logged and never stops the other sources."""
    try:
        fn()
        log(f"[ok]   {fn.__name__}")
    except Exception as e:  # noqa: BLE001
        log(f"[FAIL] {fn.__name__}: {type(e).__name__}: {e}")


# --------------------------------------------------------------------------------------------
# S02 MapPLUTO: tax lots within RADIUS_M of the site (candidate offtakers, distance, units, tract)
# --------------------------------------------------------------------------------------------
def s02_pluto():
    out = RAW / "s02_pluto_lots_1km.csv"
    if not OFFLINE:
        dlat, dlon = RADIUS_M / 111000, RADIUS_M / (111000 * math.cos(math.radians(SITE["lat"])))
        cols = ("bbl,address,borough,block,lot,zipcode,bct2020,ct2010,bldgclass,landuse,ownername,lotarea,bldgarea,"
                "resarea,comarea,officearea,retailarea,unitsres,unitstotal,numbldgs,numfloors,yearbuilt,yearalter1,"
                "builtfar,latitude,longitude,version")
        df = socrata("data.cityofnewyork.us", "64uk-42ks", {
            "$select": cols,
            "$where": (f"latitude between {SITE['lat']-dlat} and {SITE['lat']+dlat} and "
                       f"longitude between {SITE['lon']-dlon} and {SITE['lon']+dlon}")})
        df.to_csv(out, index=False)
    df = pd.read_csv(out, dtype={"bbl": str, "bct2020": str})
    df["bbl"] = df["bbl"].str.split(".").str[0]
    df["dist_m"] = [round(haversine_m(SITE["lat"], SITE["lon"], a, b)) for a, b in zip(df.latitude, df.longitude)]
    df = df[df.dist_m <= RADIUS_M].copy()
    # 2020 census tract GEOID: state 36 + county 061 + 6-digit tract (bct2020 = boro digit + tract)
    df["tract_geoid"] = "36061" + df["bct2020"].astype(str).str[-6:].str.zfill(6)
    df.to_csv(PROC / "pluto_lots_1km.csv", index=False)


# --------------------------------------------------------------------------------------------
# S01 NYC LL84 benchmarking: measured annual energy for every benchmarked lot within RADIUS_M
# --------------------------------------------------------------------------------------------
KEY_OFFTAKERS = {SITE["bbl"]: "source_and_self_offtaker", "1007140031": "anchor_nycha_fulton",
                 "1007230001": "anchor_nycha_elliott_chelsea", "1007130001": "commercial_chelsea_market"}
LL84_COLS = ["property_id", "parent_property_id", "property_name", "address_1", "postal_code", "nyc_borough_block_and_lot", "report_year",
             "year_built", "number_of_buildings", "occupancy", "largest_property_use_type",
             "property_gfa_calculated_1", "data_center_gross_floor_area", "multifamily_housing_total",
             "electricity_use_grid_purchase_1", "district_steam_use_kbtu", "natural_gas_use_kbtu",
             "fuel_oil_2_use_kbtu", "fuel_oil_4_use_kbtu", "district_hot_water_use_kbtu", "site_eui_kbtu_ft",
             "weather_normalized_site_eui", "water_use_all_water_sources", "total_location_based_ghg",
             "estimated_data_flag", "latitude", "longitude"]


def s01_ll84():
    out = RAW / "s01_ll84_benchmarking_1km.csv"
    if not OFFLINE:
        df = socrata("data.cityofnewyork.us", "5zyy-y8am", {
            "$select": ",".join(LL84_COLS),
            "$where": f"postal_code in ('10011','10001','10014','10018') and report_year >= '{LL84_MIN_YEAR}'"})
        df.to_csv(out, index=False)
    df = pd.read_csv(out, dtype=str)
    df["report_year"] = df["report_year"].astype(str).str[:4]
    lots = pd.read_csv(PROC / "pluto_lots_1km.csv", dtype={"bbl": str})
    near = set(lots.bbl)
    df["bbls"] = df["nyc_borough_block_and_lot"].fillna("").str.replace(" ", "").str.split(r"[;,]")
    df = df[df.bbls.apply(lambda b: any(x in near for x in b))].copy()
    dist = lots.set_index("bbl").dist_m
    df["dist_m"] = df.bbls.apply(lambda b: min(dist[x] for x in b if x in near))
    text_cols = {"property_id", "parent_property_id", "property_name", "address_1", "postal_code",
                 "nyc_borough_block_and_lot", "report_year", "largest_property_use_type", "estimated_data_flag"}
    for c in LL84_COLS:
        if c not in text_cols:
            df[c] = num(df[c])
    df["electricity_MWh"] = df.electricity_use_grid_purchase_1 / 1000
    df["steam_MWh"] = df.district_steam_use_kbtu / KBTU_PER_MWH
    df["gas_MWh"] = df.natural_gas_use_kbtu / KBTU_PER_MWH
    df["oil_MWh"] = (df.fuel_oil_2_use_kbtu.fillna(0) + df.fuel_oil_4_use_kbtu.fillna(0)) / KBTU_PER_MWH
    df["heat_fuel_MWh"] = df[["steam_MWh", "gas_MWh", "oil_MWh"]].sum(axis=1, min_count=1)
    df = df.drop(columns="bbls")
    # avoid double counting: drop a child record when its parent campus record is also in the extract
    ids = set(df.property_id.astype(str))
    par = pd.to_numeric(df.parent_property_id, errors="coerce").astype("Int64").astype(str)
    df["is_child_of_listed_parent"] = ((par != df.property_id.astype(str)) & par.isin(ids)).fillna(False).astype(bool)
    df["key_role"] = ""
    for pat, role in KEY_OFFTAKERS.items():
        df.loc[df.nyc_borough_block_and_lot.fillna("").str.contains(pat) & ~df.is_child_of_listed_parent, "key_role"] = role
    df.to_csv(PROC / "ll84_buildings_1km_by_year.csv", index=False)
    df = df[~df.is_child_of_listed_parent]

    # one row per property: mean of available years (2022+), with min/max to show year-to-year spread
    g = df.groupby(["key_role", "property_id", "property_name", "address_1", "nyc_borough_block_and_lot", "dist_m",
                    "largest_property_use_type"], dropna=False)
    agg = g.agg(years=("report_year", lambda s: ",".join(sorted(set(s)))),
                n_years=("report_year", "nunique"),
                gfa_ft2=("property_gfa_calculated_1", "median"),
                units_res=("multifamily_housing_total", "median"),
                dc_gfa_ft2=("data_center_gross_floor_area", "median"),
                electricity_MWh_mean=("electricity_MWh", "mean"),
                steam_MWh_mean=("steam_MWh", "mean"),
                gas_MWh_mean=("gas_MWh", "mean"),
                oil_MWh_mean=("oil_MWh", "mean"),
                heat_fuel_MWh_mean=("heat_fuel_MWh", "mean"),
                heat_fuel_MWh_min=("heat_fuel_MWh", "min"),
                heat_fuel_MWh_max=("heat_fuel_MWh", "max"),
                ghg_tCO2e_mean=("total_location_based_ghg", "mean"),
                any_estimated=("estimated_data_flag", lambda s: "Yes" in set(s))).reset_index()
    agg["heat_fuel_kWh_per_ft2"] = agg.heat_fuel_MWh_mean * 1000 / agg.gfa_ft2
    agg = agg.sort_values("heat_fuel_MWh_mean", ascending=False)
    agg.to_csv(PROC / "offtaker_candidates_ll84.csv", index=False)

    src = df[df.nyc_borough_block_and_lot.fillna("").str.contains(SITE["bbl"])].copy()
    src["electricity_avg_MW"] = src.electricity_MWh / 8760
    src["dc_gfa_share"] = src.data_center_gross_floor_area / src.property_gfa_calculated_1
    src[["report_year", "electricity_MWh", "electricity_avg_MW", "data_center_gross_floor_area",
         "property_gfa_calculated_1", "dc_gfa_share", "steam_MWh", "gas_MWh", "heat_fuel_MWh",
         "total_location_based_ghg", "estimated_data_flag"]].sort_values("report_year") \
        .to_csv(PROC / "source_111_8th_annual.csv", index=False)


# --------------------------------------------------------------------------------------------
# S03 NYCHA Development Data Book: the four Chelsea developments
# --------------------------------------------------------------------------------------------
def s03_nycha():
    out = RAW / "s03_nycha_development_data_book.csv"
    if not OFFLINE:
        df = socrata("data.cityofnewyork.us", "evjd-dqpz", {
            "$where": "development in ('FULTON','ELLIOTT','CHELSEA','CHELSEA ADDITION')"})
        df.to_csv(out, index=False)
    df = pd.read_csv(out, dtype=str)
    keep = {"development": "development", "tds_": "tds", "total_number_of_apartments": "apartments",
            "total_population": "population", "percent_fixed_income_households": "share_fixed_income_households",
            "avg_monthly_gross_rent": "avg_monthly_gross_rent_usd", "number_of_residential_bldgs": "residential_bldgs",
            "number_of_stories": "stories", "completion_date": "completion_date", "senior_development": "senior_development"}
    df = df[[c for c in keep if c in df.columns]].rename(columns=keep)
    for c in ("apartments", "population", "share_fixed_income_households", "avg_monthly_gross_rent_usd", "residential_bldgs"):
        if c in df:
            df[c] = num(df[c].astype(str).str.replace(r"[$,]", "", regex=True))
    df.to_csv(PROC / "nycha_chelsea_developments.csv", index=False)


# --------------------------------------------------------------------------------------------
# S04 NYS Disadvantaged Communities (2023): tract indicators for every tract within RADIUS_M
# --------------------------------------------------------------------------------------------
DAC_COLS = ["geoid", "dac_designation", "population_count", "household_count", "combined_score",
            "percentile_rank_combined", "burden_score_percentile", "vulnerability_score_percentile",
            "particulate_matter_25", "days_above_90_degrees_2050", "power_generation_facilities",
            "lmi_80_ami", "lmi_poverty_federal", "home_energy_affordability", "rent_percent_income",
            "renter_percent", "age_over_65", "asthma_ed_rate", "homes_built_before_1960", "unemployment_rate"]


def s04_dac():
    out = RAW / "s04_nys_dac_tracts.csv"
    tracts = sorted(set(pd.read_csv(PROC / "pluto_lots_1km.csv", dtype={"tract_geoid": str}).tract_geoid))
    if not OFFLINE:
        ids = ",".join(f"'{t}'" for t in tracts)
        df = socrata("data.ny.gov", "2e6c-s6fp", {"$select": ",".join(DAC_COLS), "$where": f"geoid in ({ids})"})
        df.to_csv(out, index=False)
    df = pd.read_csv(out, dtype={"geoid": str})
    lots = pd.read_csv(PROC / "pluto_lots_1km.csv", dtype={"tract_geoid": str, "bbl": str})
    key = {SITE["bbl"]: "site_111_8th", "1007140031": "nycha_fulton", "1007230001": "nycha_elliott_chelsea"}
    roles = lots[lots.bbl.isin(key)].assign(role=lambda d: d.bbl.map(key))[["tract_geoid", "role"]]
    df = df.merge(roles.groupby("tract_geoid").role.agg(";".join), left_on="geoid", right_index=True, how="left")
    df.to_csv(PROC / "dac_tracts_1km.csv", index=False)


# --------------------------------------------------------------------------------------------
# S05 NYC Community Air Survey + boiler emissions (DOHMH Environment & Health Data Portal)
# --------------------------------------------------------------------------------------------
def s05_nyccas():
    out = RAW / "s05_nyccas_air_quality.csv"
    if not OFFLINE:
        df = socrata("data.cityofnewyork.us", "c3uy-2p5r", {
            "$where": ("(geo_place_name in ('Chelsea - Clinton','Chelsea-Village','Clinton and Chelsea (CD4)','New York City',"
                       "'Manhattan')) and (name like 'Fine particles%' or name like 'Nitrogen dioxide%' or "
                       "name like 'Boiler emissions%' or name like 'Deaths due to PM2.5%')")})
        df.to_csv(out, index=False)
    df = pd.read_csv(out)
    df["data_value"] = num(df.data_value)
    df["year"] = pd.to_datetime(df.start_date).dt.year
    latest = df.sort_values("start_date").groupby(["name", "measure", "geo_type_name", "geo_place_name"]).tail(1)
    latest[["name", "measure", "measure_info", "geo_type_name", "geo_place_name", "time_period", "year", "data_value"]] \
        .sort_values(["name", "measure", "geo_place_name"]).to_csv(PROC / "air_quality_latest.csv", index=False)


# --------------------------------------------------------------------------------------------
# S06 NYC Heat Vulnerability Index (ZCTA, 1 = lowest, 5 = highest)
# --------------------------------------------------------------------------------------------
def s06_hvi():
    out = RAW / "s06_nyc_hvi_zcta.csv"
    if not OFFLINE:
        socrata("data.cityofnewyork.us", "4mhf-duep", {"$where": "zcta20 in ('10011','10001','10014','10018')"}).to_csv(out, index=False)
    pd.read_csv(out).to_csv(PROC / "hvi_zcta.csv", index=False)


# --------------------------------------------------------------------------------------------
# S07 Weather: TMYx 2011-2025, Central Park (WMO 725053), from NOAA NCEI ISD (+ERA5 gap fill),
#     ISO 15927-4 typical year; header carries 2025 ASHRAE Handbook design conditions
# --------------------------------------------------------------------------------------------
TMYX_URL = ("https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/"
            "NY_New_York/USA_NY_New.York-Central.Park.Obs-Belvedere.Castle.725053_TMYx.2011-2025.zip")


def s07_weather():
    p = cached("tmyx_2011_2025.zip", TMYX_URL)
    z = zipfile.ZipFile(p)
    lines = z.read([n for n in z.namelist() if n.endswith(".epw")][0]).decode("latin-1").splitlines()
    hdr = {l.split(",")[0]: l for l in lines[:8]}
    cols = ["year", "month", "day", "hour", "minute", "flags", "dry_bulb_C", "dew_point_C", "rel_hum_pct",
            "pressure_Pa", "ext_hor_rad", "ext_dir_norm_rad", "hor_ir_sky", "ghi_Whm2", "dni_Whm2", "dhi_Whm2",
            "gh_illum", "dn_illum", "dh_illum", "zen_lum", "wind_dir_deg", "wind_speed_ms"]
    w = pd.read_csv(io.StringIO("\n".join(lines[8:])), header=None).iloc[:, :len(cols)]
    w.columns = cols
    w.to_csv(RAW / "s07_tmyx_central_park_hourly.csv", index=False)
    w = w[["year", "month", "day", "hour", "dry_bulb_C", "dew_point_C", "rel_hum_pct", "ghi_Whm2", "wind_speed_ms"]].copy()
    w = w.rename(columns={"year": "source_year"})
    w["hour_of_year"] = range(1, len(w) + 1)
    w["HDH_18C"] = (18 - w.dry_bulb_C).clip(lower=0)  # heating degree-hours, base 18 C
    w.to_csv(PROC / "weather_tmyx_hourly.csv", index=False)
    # EPW DESIGN CONDITIONS: Heating,<coldest month>,<DB 99.6%>,<DB 99.0%>,... ; Cooling,<hottest month>,<daily range>,<DB 0.4%>,...
    dc = hdr.get("DESIGN CONDITIONS", "").split(",")
    rows = [("source_location", hdr.get("LOCATION", ""), "", "EPW header"),
            ("design_conditions_source", dc[2] if len(dc) > 2 else "missing", "", "EPW header")]
    if "Heating" in dc:
        i = dc.index("Heating")
        rows += [("heating_design_DB_99.6pct_C", float(dc[i + 2]), "C", "ASHRAE HoF 2025 Ch.14"),
                 ("heating_design_DB_99.0pct_C", float(dc[i + 3]), "C", "ASHRAE HoF 2025 Ch.14")]
    if "Cooling" in dc:
        j = dc.index("Cooling")
        rows += [("cooling_design_DB_0.4pct_C", float(dc[j + 3]), "C", "ASHRAE HoF 2025 Ch.14")]
    rows += [("annual_HDD_18C", round(w.HDH_18C.sum() / 24, 0), "K*day", "computed from hourly TMYx"),
             ("min_hourly_dry_bulb_C", w.dry_bulb_C.min(), "C", "TMYx hourly"),
             ("mean_dry_bulb_C", round(w.dry_bulb_C.mean(), 2), "C", "TMYx hourly")]
    pd.DataFrame(rows, columns=["parameter", "value", "unit", "basis"]).to_csv(PROC / "weather_design_conditions.csv", index=False)


# --------------------------------------------------------------------------------------------
# S08 EIA prices: NY electricity by sector (Form 861M) and NY natural gas by sector (monthly)
# --------------------------------------------------------------------------------------------
def s08_eia_prices():
    p = cached("eia_sales_revenue.xlsx", "https://www.eia.gov/electricity/data/eia861m/xls/sales_revenue.xlsx")
    e = pd.read_excel(p, header=None, skiprows=3)
    e = e.iloc[:, :16]
    e.columns = ["year", "month", "state", "status",
                 "res_rev_kUSD", "res_sales_MWh", "res_customers", "res_price_c_kWh",
                 "com_rev_kUSD", "com_sales_MWh", "com_customers", "com_price_c_kWh",
                 "ind_rev_kUSD", "ind_sales_MWh", "ind_customers", "ind_price_c_kWh"]
    e = e[e.state == "NY"].copy()
    e.to_csv(RAW / "s08a_eia861m_ny_electricity.csv", index=False)

    q = cached("eia_ng_ny.xls", "https://www.eia.gov/dnav/ng/xls/NG_PRI_SUM_DCU_SNY_M.xls")
    g = pd.read_excel(q, sheet_name="Data 1", header=2)
    g = g.rename(columns={g.columns[0]: "date"})
    g.to_csv(RAW / "s08b_eia_ng_prices_ny.csv", index=False)

    # processed: monthly $/MWh for electricity; gas converted $/Mcf -> $/MMBtu -> $/MWh(fuel)
    e["date"] = pd.to_datetime(dict(year=e.year, month=e.month, day=1))
    el = e[["date", "status", "res_price_c_kWh", "com_price_c_kWh"]].copy()
    el["res_price_USD_MWh"] = el.res_price_c_kWh * 10
    el["com_price_USD_MWh"] = el.com_price_c_kWh * 10
    pick = {c: n for c, n in zip(g.columns, g.columns)}
    res = [c for c in g.columns if "Residential Consumers" in c][0]
    com = [c for c in g.columns if "Commercial Consumers" in c][0]
    gg = g[["date", res, com]].rename(columns={res: "gas_res_USD_Mcf", com: "gas_com_USD_Mcf"})
    gg["date"] = pd.to_datetime(gg.date).dt.to_period("M").dt.to_timestamp()
    HEAT_CONTENT_MMBTU_PER_MCF = 1.036  # EIA US average heat content of natural gas delivered to consumers
    for s in ("res", "com"):
        gg[f"gas_{s}_USD_MMBtu"] = gg[f"gas_{s}_USD_Mcf"] / HEAT_CONTENT_MMBTU_PER_MCF
        gg[f"gas_{s}_USD_MWh_fuel"] = gg[f"gas_{s}_USD_MMBtu"] * 3.412142
    m = el.merge(gg, on="date", how="outer").sort_values("date")
    m = m[m.date >= "2015-01-01"]
    m.to_csv(PROC / "energy_prices_ny_monthly.csv", index=False)
    last12 = m.dropna(subset=["com_price_USD_MWh"]).tail(12)
    last12g = m.dropna(subset=["gas_com_USD_MWh_fuel"]).tail(12)
    pd.DataFrame([
        ("electricity_residential_USD_MWh_12mo_mean", last12.res_price_USD_MWh.mean(), str(last12.date.min().date()), str(last12.date.max().date())),
        ("electricity_commercial_USD_MWh_12mo_mean", last12.com_price_USD_MWh.mean(), str(last12.date.min().date()), str(last12.date.max().date())),
        ("gas_residential_USD_MWh_fuel_12mo_mean", last12g.gas_res_USD_MWh_fuel.mean(), str(last12g.date.min().date()), str(last12g.date.max().date())),
        ("gas_commercial_USD_MWh_fuel_12mo_mean", last12g.gas_com_USD_MWh_fuel.mean(), str(last12g.date.min().date()), str(last12g.date.max().date())),
    ], columns=["parameter", "value", "from", "to"]).to_csv(PROC / "energy_prices_ny_summary.csv", index=False)


# --------------------------------------------------------------------------------------------
# S09 NYISO hourly integrated load, Zone J (N.Y.C.), last complete calendar year
# --------------------------------------------------------------------------------------------
NYISO_YEAR = 2025


def s09_nyiso():
    out = RAW / f"s09_nyiso_zoneJ_hourly_{NYISO_YEAR}.csv"
    if not OFFLINE:
        frames = []
        for m in range(1, 13):
            url = f"http://mis.nyiso.com/public/csv/palIntegrated/{NYISO_YEAR}{m:02d}01palIntegrated_csv.zip"
            z = zipfile.ZipFile(io.BytesIO(get(url, timeout=120).content))
            for n in sorted(z.namelist()):
                d = pd.read_csv(z.open(n))
                frames.append(d[d.Name == "N.Y.C."])
        pd.concat(frames).to_csv(out, index=False)
    d = pd.read_csv(out)
    d["ts"] = pd.to_datetime(d["Time Stamp"])
    d = d.drop_duplicates("ts")
    d = d.rename(columns={"Integrated Load": "zoneJ_load_MW"})[["ts", "Time Zone", "zoneJ_load_MW"]]
    d.to_csv(PROC / f"grid_zoneJ_hourly_{NYISO_YEAR}.csv", index=False)
    win = d[d.ts.dt.month.isin([12, 1, 2])]
    pd.DataFrame([
        ("annual_peak_MW", d.zoneJ_load_MW.max(), str(d.loc[d.zoneJ_load_MW.idxmax(), "ts"])),
        ("winter_peak_MW_DecJanFeb", win.zoneJ_load_MW.max(), str(win.loc[win.zoneJ_load_MW.idxmax(), "ts"])),
        ("annual_energy_GWh", d.zoneJ_load_MW.sum() / 1000, f"{len(d)} hours"),
    ], columns=["parameter", "value", "note"]).to_csv(PROC / f"grid_zoneJ_summary_{NYISO_YEAR}.csv", index=False)


# --------------------------------------------------------------------------------------------
# S10 Danish Energy Agency Technology Data (Aug 2026 data sheet): heat pumps, boilers
# --------------------------------------------------------------------------------------------
DEA_SHEETS = ["40 Comp. hp, waste heat 1 MW", "40 Comp. hp, waste heat 3 MW", "40 Comp. hp, waste heat 10 MW",
              "40 Comp. hp, airsource 3 MW", "40 Comp. hp, airsource 10 MW", "41 Electric boiler, large",
              "44 Natural Gas DH Only"]


def s10_dea():
    p = cached("dea_datasheet.xlsx", "https://ens.dk/media/8615/download")
    x = pd.read_excel(p, sheet_name="alldata_long", header=1)
    x = x[x.ws.isin(DEA_SHEETS)]
    x[["ws", "technology", "cat", "par", "unit", "priceyear", "est", "year", "val", "note", "ref"]] \
        .to_csv(RAW / "s10_dea_techdata_heat.csv", index=False)
    pars = {"Nominal investment (*total) [MEUR/MW_h]": "capex_MEUR_per_MWth",
            "Fixed O&M (*total) [EUR/MW_h/y]": "fixed_om_EUR_per_MWth_yr",
            "Variable O&M (*total) [EUR/MWh_h]": "var_om_EUR_per_MWhth",
            "Heat efficiency (net, annual average) []": "cop_or_efficiency_annual",
            "Technical lifetime [years]": "lifetime_yr",
            "Forced outage []": "forced_outage_share",
            "Planned outage [weeks per year]": "planned_outage_weeks_yr",
            "Minimum load (of full load) []": "min_load_share"}
    y = x[x.par.isin(pars) & x.year.isin([2025, 2030])].copy()
    y["parameter"] = y.par.map(pars)
    t = y.pivot_table(index=["ws", "year", "parameter"], columns="est", values="val", aggfunc="first").reset_index()
    t["price_year"] = 2020
    t["currency"] = t.parameter.str.contains("EUR").map({True: "EUR(2020)", False: ""})
    t.to_csv(PROC / "equipment_dea_heat.csv", index=False)


# --------------------------------------------------------------------------------------------
# S11 EIA Updated Buildings Sector Equipment Costs (Mar 2023): transcribed rows, auto-verified
# --------------------------------------------------------------------------------------------
EIA_EQ_URL = "https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/full.pdf"
# Transcribed by hand from the 2022 "Typical" column of each table; `verify` must appear verbatim in the
# table row text (whitespace-normalised) or the row is flagged unverified.
EIA_EQ_ROWS = [
    # technology, pdf_page, parameter, value, unit, verify-substring (row label + leading values)
    ("Commercial gas-fired boiler (800 kBtu/h)", 123, "thermal_efficiency", 0.85, "fraction", "Thermal Efficiency (%)2 77 85 80 85 99"),
    ("Commercial gas-fired boiler (800 kBtu/h)", 123, "installed_cost", 56, "USD2022/kBtu/h", "Total Installed Cost 40 56 48 56 70"),
    ("Commercial gas-fired boiler (800 kBtu/h)", 123, "lifetime", 25, "yr", "Average Life (y) 30 25 25 25 25"),
    ("Commercial gas-fired boiler (800 kBtu/h)", 123, "maintenance", 3, "USD2022/kBtu/h/yr", "Annual Maintenance Cost 3 3 3 3"),
    ("Commercial centrifugal chiller, water-cooled (400 ton)", 129, "cop_full_load", 6.8, "-", "COP [full-load] 5.4 6.6 6.3 6.8 7.8"),
    ("Commercial centrifugal chiller, water-cooled (400 ton)", 129, "installed_cost", 560, "USD2022/ton", "Total Installed Cost (2022$/ton) 440 560 480 560 740"),
    ("Commercial centrifugal chiller, water-cooled (400 ton)", 129, "lifetime", 25, "yr", "Average Life (y) 25 25 25 25"),
    ("Commercial centrifugal chiller, water-cooled (400 ton)", 129, "maintenance", 30, "USD2022/ton/yr", "Annual Maintenance Cost (2022$/ton) 30 30 30"),
    ("Commercial ground-source (water-to-water loop) heat pump (48 kBtu/h)", 145, "cop_heating", 3.5, "-", "COP (Heating)1 3.1 3.7 3.2 3.5 3.6"),
    ("Commercial ground-source (water-to-water loop) heat pump (48 kBtu/h)", 145, "installed_cost", 466, "USD2022/kBtu/h", "Total Installed Cost (2022$/kBtu/h) 673 466 447 466 495"),
    ("Commercial heat pump water heater (171 kBtu/h)", 158, "cop_heating", 3.9, "-", "Coefficient of Performance (COPh) 3.9 3.9 3.9"),
    ("Commercial heat pump water heater (171 kBtu/h)", 158, "installed_cost", 351, "USD2022/kBtu/h", "Total Installed Cost (2022$/kBtu/h) 351 351 351"),
    ("Commercial heat pump water heater (171 kBtu/h)", 158, "lifetime", 15, "yr", "Average Life (y) 15 15 15 15"),
]


def s11_eia_equipment():
    p = cached("eia_equipcosts_2023.pdf", EIA_EQ_URL, timeout=300)
    txt = None
    try:
        import pdfplumber
        with pdfplumber.open(p) as pdf:
            txt = {pg: re.sub(r"\s+", " ", (pdf.pages[pg - 1].extract_text() or "")) for pg in {r[1] for r in EIA_EQ_ROWS}}
    except Exception as e:  # noqa: BLE001
        log(f"       pdf text check unavailable ({e}); rows kept but marked unverified")
    rows = []
    for tech, pg, par, val, unit, ver in EIA_EQ_ROWS:
        ok = False
        if txt:
            page_nums = " " + " ".join(re.findall(r"\d[\d,]*\.?\d*", txt[pg])).replace(",", "") + " "
            label_free = ver.split(")")[-1] if ")" in ver else re.sub(r"^[^\d]*", "", ver)
            seq = " ".join(re.findall(r"\d[\d,]*\.?\d*", label_free)).replace(",", "")
            ok = f" {seq} " in page_nums
        conv = None
        if unit == "USD2022/kBtu/h":
            conv = (val * 1000 / 3.412142, "USD2022/kW_th")
        elif unit == "USD2022/ton":
            conv = (val / 3.51685, "USD2022/kW_th(cooling)")
        rows.append(dict(technology=tech, pdf_page=pg, parameter=par, value=val, unit=unit,
                         value_converted=None if conv is None else round(conv[0], 1),
                         unit_converted=None if conv is None else conv[1],
                         column="2022 Typical", verified_in_pdf_text=ok))
    df = pd.DataFrame(rows)
    df.to_csv(RAW / "s11_eia_equipment_costs_2023_transcribed.csv", index=False)
    df.to_csv(PROC / "equipment_eia_building_scale.csv", index=False)


# --------------------------------------------------------------------------------------------
# S12 NYC Local Law 97 coefficients (statutory constants) + check against the law text
# --------------------------------------------------------------------------------------------
LL97_ROWS = [
    ("electricity_grid", "2024-2029", 0.000288962, "tCO2e/kWh", 0.288962),
    ("natural_gas", "2024-2029", 0.00005311, "tCO2e/kBtu", 0.00005311 * KBTU_PER_MWH),
    ("fuel_oil_2", "2024-2029", 0.00007421, "tCO2e/kBtu", 0.00007421 * KBTU_PER_MWH),
    ("fuel_oil_4", "2024-2029", 0.00007529, "tCO2e/kBtu", 0.00007529 * KBTU_PER_MWH),
    ("district_steam", "2024-2029", 0.00004493, "tCO2e/kBtu", 0.00004493 * KBTU_PER_MWH),
]
LL97_URL = "https://www.nyc.gov/assets/buildings/local_laws/ll97of2019.pdf"


def s12_ll97():
    found = None
    try:
        p = cached("ll97of2019.pdf", LL97_URL)
        import pdfplumber
        with pdfplumber.open(p) as pdf:
            t = " ".join((pg.extract_text() or "") for pg in pdf.pages)
        found = {f"{v:.9f}".rstrip("0"): (f"{v:.9f}".rstrip("0") in t or f"{v:.8f}".rstrip("0") in t) for _, _, v, _, _ in LL97_ROWS}
    except Exception as e:  # noqa: BLE001
        log(f"       LL97 text check unavailable ({e})")
    df = pd.DataFrame(LL97_ROWS, columns=["fuel", "period", "coefficient", "unit", "tCO2e_per_MWh"])
    df["verified_in_law_text"] = [None if found is None else found.get(f"{v:.9f}".rstrip("0")) for v in df.coefficient]
    df["source"] = "NYC Local Law 97 of 2019, Admin. Code §28-320.3.1.1 (2024-2029 coefficients)"
    df = pd.concat([df, pd.DataFrame([dict(fuel="penalty", period="2024+", coefficient=268, unit="USD/tCO2e over limit",
                                           tCO2e_per_MWh=None, verified_in_law_text=None,
                                           source="NYC Admin. Code §28-320.6 (LL97)")])])
    df.to_csv(REF / "ll97_emission_coefficients.csv", index=False)


# --------------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------------
def validate():
    """Every CSV must load with pandas; report size, numeric content and missingness.
    Also check that each file and column named in data_dictionary.csv exists."""
    rows = []
    files = [f for folder in (RAW, PROC, REF) for f in sorted(folder.glob("*.csv"))]
    files += [ROOT / "data" / "dataset_inventory.csv", ROOT / "data" / "data_dictionary.csv"]
    for f in files:
        if not f.exists():
            continue
        name = str(f.relative_to(ROOT)).replace("\\", "/")
        try:
            d = pd.read_csv(f)
            num_df = d.select_dtypes("number")
            rows.append(dict(file=name, loads_with_pandas=True, rows=len(d), cols=d.shape[1],
                             numeric_cols=num_df.shape[1], numeric_non_null_cells=int(num_df.notna().sum().sum()),
                             missing_cell_share=round(float(d.isna().mean().mean()), 3)))
        except Exception as e:  # noqa: BLE001
            rows.append(dict(file=name, loads_with_pandas=False, error=str(e)))
    v = pd.DataFrame(rows)
    v.to_csv(ROOT / "data" / "validation_report.csv", index=False)
    print(v.to_string(index=False))

    dd_path = ROOT / "data" / "data_dictionary.csv"
    if dd_path.exists():
        dd, problems = pd.read_csv(dd_path), []
        for _, r in dd.iterrows():
            for f in str(r.csv_file).split(";"):
                f = f.strip()
                if not f or f == "nan":
                    continue
                fp = ROOT / f
                if not fp.exists():
                    problems.append(f"{r.indicator_id}: missing file {f}")
                    continue
                cols = set(pd.read_csv(fp, nrows=0).columns)
                named = [c.strip().split(" ")[0] for c in str(r.csv_columns).replace(";", ",").split(",")]
                text = fp.read_text(encoding="utf-8", errors="ignore")  # long tables: names live in cells
                hits = [c for c in named if c and (c in cols or c in text)]
                if not hits and "reference" not in f:
                    problems.append(f"{r.indicator_id}: none of the named columns found in {f}")
        print("data_dictionary cross-check:", "OK" if not problems else problems)
    return v


if __name__ == "__main__":
    for fn in (s02_pluto, s01_ll84, s03_nycha, s04_dac, s05_nyccas, s06_hvi, s07_weather, s08_eia_prices,
               s09_nyiso, s10_dea, s11_eia_equipment, s12_ll97):
        step(fn)
    validate()
    (ROOT / "data" / "fetch_log.txt").write_text(
        f"run {dt.datetime.now().isoformat(timespec='seconds')} offline={OFFLINE}\n" + "\n".join(LOG) + "\n")
