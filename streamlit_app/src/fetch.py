"""Data acquisition, caching, cleaning and sample-data fallback.

Every loader returns ``(data, provenance)`` where provenance is one of
``"live"`` (downloaded now), ``"cache"`` (from /data), or ``"sample"`` (bundled
fallback in /data/sample). Provenance is logged and shown in the app.

Data-quality issues found while cleaning are appended to a ``QualityLog`` so the
app / CLI can report them (campus-level records, duplicates, missing coordinates…).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .config import ROOT, Config

log = logging.getLogger(__name__)

SAMPLE_DIR = ROOT / "data" / "sample"
CACHE_RADIUS_M = 2000.0  # cache LL84 rows within this distance (≥ max radius slider)
HTTP_TIMEOUT_S = 60
SAME_SITE_M = 30.0  # records geocoded closer than this are 'the same address'
CAMPUS_MARGIN_M = 300.0
JUNK_NAME_PATTERN = r"^copy of|^zzz|^lost |\btest\b|- reporting|^reporting"  # pre-filter margin so multi-lot campuses near the edge are resolved whole

LL84_COLUMNS: list[str] = [
    "report_year", "property_id", "property_name", "parent_property_id", "parent_property_name",
    "nyc_borough_block_and_lot", "nyc_building_identification", "address_1",
    "primary_property_type", "property_gfa_self_reported", "number_of_buildings",
    "natural_gas_use_kbtu", "district_steam_use_kbtu", "fuel_oil_1_use_kbtu",
    "fuel_oil_2_use_kbtu", "fuel_oil_4_use_kbtu", "fuel_oil_5_6_use_kbtu", "diesel_2_use_kbtu",
    "electricity_use_grid_purchase_1", "site_eui_kbtu_ft", "total_location_based_ghg",
    "estimated_data_flag", "latitude", "longitude",
]
NUMERIC_COLUMNS: list[str] = [
    "report_year", "property_gfa_self_reported", "number_of_buildings",
    "natural_gas_use_kbtu", "district_steam_use_kbtu", "fuel_oil_1_use_kbtu",
    "fuel_oil_2_use_kbtu", "fuel_oil_4_use_kbtu", "fuel_oil_5_6_use_kbtu", "diesel_2_use_kbtu",
    "electricity_use_grid_purchase_1", "site_eui_kbtu_ft", "total_location_based_ghg",
    "latitude", "longitude",
]
OIL_COLUMNS: list[str] = [
    "fuel_oil_1_use_kbtu", "fuel_oil_2_use_kbtu", "fuel_oil_4_use_kbtu",
    "fuel_oil_5_6_use_kbtu", "diesel_2_use_kbtu",
]
ENERGY_COLUMNS: list[str] = ["natural_gas_use_kbtu", "district_steam_use_kbtu", *OIL_COLUMNS,
                             "electricity_use_grid_purchase_1"]


@dataclass
class QualityLog:
    """Collects data-quality findings and data provenance."""

    issues: list[dict] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)

    def add(self, kind: str, who: str, detail: str) -> None:
        self.issues.append({"kind": kind, "building": who, "detail": detail})
        log.info("[data-quality] %s | %s | %s", kind, who, detail)

    def source(self, dataset: str, how: str) -> None:
        self.provenance[dataset] = how
        level = logging.WARNING if how == "sample" else logging.INFO
        log.log(level, "[provenance] %s: %s", dataset, how.upper())

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.issues, columns=["kind", "building", "detail"])


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def haversine_m(lat1: float, lon1: float, lat2: np.ndarray | float, lon2: np.ndarray | float) -> np.ndarray:
    """Great-circle distance in metres."""
    r = 6_371_000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def normalize_bbl(raw: str | float | None) -> list[str]:
    """Split an LL84 BBL field into 10-digit BBL strings.

    LL84 mixes formats: '1007390001', '1-00078-7506', and campus lists
    '1007140031;1007150010'. Invalid tokens are dropped.
    """
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return []
    out = []
    for token in str(raw).replace(",", ";").split(";"):
        digits = "".join(ch for ch in token if ch.isdigit())
        if len(digits) == 10:
            out.append(digits)
    return out


def socrata_get(cfg: Config, dataset: str, params: dict[str, str], page: int = 50_000) -> pd.DataFrame:
    """Download all rows of a Socrata SoQL query, paging with $offset."""
    url = f"https://{cfg.get('data.socrata_domain')}/resource/{dataset}.json"
    frames, offset = [], 0
    while True:
        q = {**params, "$limit": str(page), "$offset": str(offset), "$order": ":id"}
        r = requests.get(url, params=q, timeout=HTTP_TIMEOUT_S)
        r.raise_for_status()
        rows = r.json()
        frames.append(pd.DataFrame(rows))
        if len(rows) < page:
            break
        offset += page
    return pd.concat(frames, ignore_index=True)


def _cached(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# ---------------------------------------------------------------------------
# LL84
# ---------------------------------------------------------------------------
def fetch_ll84(cfg: Config, qlog: QualityLog) -> pd.DataFrame:
    """All LL84 report years for Manhattan properties within CACHE_RADIUS_M of the site."""
    path = cfg.cache_dir / "ll84_near_site.csv"
    if _cached(path):
        qlog.source("LL84 energy disclosure", "cache")
        return pd.read_csv(path, dtype={"nyc_borough_block_and_lot": str, "property_id": str,
                                        "parent_property_id": str, "nyc_building_identification": str})
    try:
        df = socrata_get(cfg, cfg.get("data.ll84_dataset_id"), {
            "$select": ",".join(LL84_COLUMNS),
            "$where": "borough='MANHATTAN'",
        })
        df = _coerce_ll84(df)
        d = haversine_m(cfg.v("site.lat"), cfg.v("site.lon"), df["latitude"], df["longitude"])
        # keep rows near the site, plus rows without coordinates (may be resolved via PLUTO)
        df = df[(d <= CACHE_RADIUS_M) | df["latitude"].isna()]
        cfg.cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        qlog.source("LL84 energy disclosure", "live")
        return df
    except Exception as exc:  # network / API failure → bundled snapshot
        log.warning("LL84 fetch failed (%s); using sample snapshot", exc)
        qlog.source("LL84 energy disclosure", "sample")
        return pd.read_csv(SAMPLE_DIR / "ll84_sample.csv", dtype={"nyc_borough_block_and_lot": str,
                                                                    "property_id": str})


def _coerce_ll84(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all columns exist and numeric columns are floats ('Not Available' → NaN)."""
    for c in LL84_COLUMNS:
        if c not in df:
            df[c] = np.nan
    for c in NUMERIC_COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[LL84_COLUMNS].copy()


# ---------------------------------------------------------------------------
# PLUTO
# ---------------------------------------------------------------------------
def fetch_pluto(cfg: Config, qlog: QualityLog) -> pd.DataFrame:
    """PLUTO tax lots (bbl, centroid, building area) in a box around the site."""
    path = cfg.cache_dir / "pluto_near_site.csv"
    if _cached(path):
        qlog.source("MapPLUTO", "cache")
        return pd.read_csv(path, dtype={"bbl": str})
    lat, lon = cfg.v("site.lat"), cfg.v("site.lon")
    dlat = CACHE_RADIUS_M / 111_000.0
    dlon = CACHE_RADIUS_M / (111_000.0 * math.cos(math.radians(lat)))
    try:
        df = socrata_get(cfg, cfg.get("data.pluto_dataset_id"), {
            "$select": "bbl,address,latitude,longitude,bldgarea,numbldgs,bldgclass,ownername",
            "$where": (f"latitude between {lat - dlat} and {lat + dlat} and "
                       f"longitude between {lon - dlon} and {lon + dlon}"),
        })
        df["bbl"] = df["bbl"].astype(str).str.split(".").str[0]
        for c in ["latitude", "longitude", "bldgarea", "numbldgs"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        cfg.cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        qlog.source("MapPLUTO", "live")
        return df
    except Exception as exc:
        log.warning("PLUTO fetch failed (%s); continuing without it", exc)
        qlog.source("MapPLUTO", "sample")
        sample = SAMPLE_DIR / "pluto_sample.csv"
        return pd.read_csv(sample, dtype={"bbl": str}) if sample.exists() else pd.DataFrame(
            columns=["bbl", "address", "latitude", "longitude", "bldgarea", "numbldgs"])


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
def fetch_weather(cfg: Config, qlog: QualityLog) -> pd.Series:
    """Hourly 2 m air temperature (°C) for the weather year, local time, 8,760 values."""
    year = int(cfg.v("data.weather_year"))
    path = cfg.cache_dir / f"weather_{year}.csv"
    if _cached(path):
        qlog.source("Open-Meteo weather", "cache")
        return _as_year(pd.read_csv(path, index_col=0, parse_dates=True)["temp_c"])
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": cfg.v("site.lat"), "longitude": cfg.v("site.lon"),
            "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
            "hourly": "temperature_2m", "timezone": "America/New_York",
        }, timeout=HTTP_TIMEOUT_S)
        r.raise_for_status()
        h = r.json()["hourly"]
        s = pd.Series(h["temperature_2m"], index=pd.to_datetime(h["time"]), name="temp_c", dtype=float)
        s = s.interpolate(limit_direction="both")
        cfg.cache_dir.mkdir(parents=True, exist_ok=True)
        s.to_frame().to_csv(path)
        qlog.source("Open-Meteo weather", "live")
        return _as_year(s)
    except Exception as exc:
        log.warning("Weather fetch failed (%s); using synthetic NYC year", exc)
        qlog.source("Open-Meteo weather", "sample")
        return synthetic_weather(year)


def _as_year(s: pd.Series) -> pd.Series:
    """Force exactly 8,760 hourly values (drop Feb 29 in leap years)."""
    s = s[~((s.index.month == 2) & (s.index.day == 29))]
    if len(s) != 8760:
        raise ValueError(f"weather series has {len(s)} hours, expected 8760")
    return s.rename("temp_c")


def synthetic_weather(year: int) -> pd.Series:
    """Clearly-labelled synthetic NYC year: NOAA 1991-2020 Central Park normals
    (annual mean 13.2 °C, Jan 0.9 °C, Jul 25.3 °C) as a sinusoid + 4 K diurnal swing."""
    idx = pd.date_range(f"{year}-01-01", periods=8760, freq="h")
    doy = idx.dayofyear.to_numpy()
    hour = idx.hour.to_numpy()
    seasonal = 13.2 - 12.2 * np.cos(2 * np.pi * (doy - 20) / 365.0)
    diurnal = -4.0 * np.cos(2 * np.pi * (hour - 3) / 24.0)
    return pd.Series(seasonal + diurnal, index=idx, name="temp_c")


# ---------------------------------------------------------------------------
# Building table assembly
# ---------------------------------------------------------------------------
def resolve_campus_records(df: pd.DataFrame, pluto: pd.DataFrame, qlog: QualityLog) -> pd.DataFrame:
    """Handle LL84 records that cover several tax lots (e.g. NYCHA campuses).

    For each multi-BBL record in a report year:
      * if single-lot child records exist and their fuel sums to the parent's (±5 %),
        the children are genuine → drop the parent;
      * otherwise allocate the parent's energy to the children (or to PLUTO lots if no
        children) by floor area, and drop the parent. Children's own values are discarded
        because they are typically missing or duplicate the campus total.
    """
    df = df.copy()
    df["bbls"] = df["nyc_borough_block_and_lot"].map(normalize_bbl)
    df["bbl"] = df["bbls"].map(lambda b: b[0] if b else None)
    df["campus_note"] = ""
    multi = df[df["bbls"].map(len) > 1]
    drop_idx: list[int] = []
    new_rows: list[pd.Series] = []
    for idx, parent in multi.iterrows():
        yr, lots = parent["report_year"], set(parent["bbls"])
        kids = df[(df["report_year"] == yr) & (df["bbls"].map(len) == 1) & df["bbl"].isin(lots)]
        name = f"{parent['property_name']} ({int(yr)})"
        p_fuel = parent[ENERGY_COLUMNS[:-1]].fillna(0).sum()
        k_fuel = kids[ENERGY_COLUMNS[:-1]].fillna(0).sum().sum() if len(kids) else 0.0
        dup = len(kids) and any(np.isclose(kids[ENERGY_COLUMNS[:-1]].fillna(0).sum(axis=1), p_fuel, rtol=0.01))
        if len(kids) and p_fuel > 0 and abs(k_fuel - p_fuel) / p_fuel < 0.05 and not dup:
            qlog.add("campus record", name, f"{len(lots)} lots; children sum to campus total → kept children")
            drop_idx.append(idx)
            continue
        if len(kids):
            weights = kids["property_gfa_self_reported"].fillna(0)
            targets = kids
        else:
            targets = _pluto_children(parent, pluto)
            weights = targets["property_gfa_self_reported"].fillna(0) if len(targets) else pd.Series(dtype=float)
        if len(targets) == 0 or weights.sum() <= 0:
            qlog.add("campus record", name, f"{len(lots)} lots, no children/PLUTO lots → kept as one node")
            continue
        share = weights / weights.sum()
        for t_idx, t in targets.iterrows():
            row = t.copy()
            for c in ENERGY_COLUMNS:
                row[c] = parent[c] * share.loc[t_idx] if pd.notna(parent[c]) else np.nan
            row["campus_note"] = f"allocated {share.loc[t_idx]:.0%} of campus '{parent['property_name']}' by GFA"
            if pd.isna(row.get("latitude")):
                row["latitude"], row["longitude"] = t.get("latitude"), t.get("longitude")
            new_rows.append(row)
        drop_idx.extend([idx, *kids.index.tolist()])
        detail = (f"{len(lots)} lots / {int(parent['number_of_buildings'] or 0)} bldgs reported as one record; "
                  f"{'children duplicate or omit the total' if len(kids) else 'no child records'} → "
                  f"allocated to {len(targets)} {'child records' if len(kids) else 'PLUTO lots'} by floor area")
        qlog.add("campus record", name, detail)
    out = df.drop(index=drop_idx)
    if new_rows:
        out = pd.concat([out, pd.DataFrame(new_rows)], ignore_index=True)
    return out.reset_index(drop=True)


def _pluto_children(parent: pd.Series, pluto: pd.DataFrame) -> pd.DataFrame:
    """Synthesize child rows from PLUTO lots of a campus record."""
    lots = pluto[pluto["bbl"].isin(parent["bbls"])]
    rows = []
    for _, lot in lots.iterrows():
        r = parent.copy()
        r["bbl"], r["bbls"] = lot["bbl"], [lot["bbl"]]
        r["property_name"] = f"{parent['property_name']} – lot {lot['bbl']}"
        r["address_1"] = lot["address"]
        r["property_gfa_self_reported"] = lot["bldgarea"]
        r["latitude"], r["longitude"] = lot["latitude"], lot["longitude"]
        rows.append(r)
    return pd.DataFrame(rows).reset_index(drop=True)


def select_report_year(df: pd.DataFrame, year: int, qlog: QualityLog) -> pd.DataFrame:
    """Pick ONE report year per tax lot (BBL): the preferred year, else the nearest
    (ties → later year), and keep every record of that lot from that year.

    Selecting per BBL rather than per property_id matters: the same building is often
    re-registered under a new name/property_id between years, which would otherwise
    count it two or three times.
    """
    df = df.copy()
    df["site_key"] = df["bbl"].where(df["bbl"].notna(), "pid:" + df["property_id"].astype(str))
    df["_dist"] = (df["report_year"] - year).abs() * 2 + (df["report_year"] < year)
    best = df.groupby("site_key")["_dist"].transform("min")
    dropped = df[df["_dist"] != best]
    df = df[df["_dist"] == best]
    log.info("report-year selection: dropped %d other-year rows, kept %d", len(dropped), len(df))
    dups = df.duplicated(subset=["property_id", "report_year", "property_name"], keep="first")
    for _, r in df[dups].iterrows():
        qlog.add("duplicate", r["property_name"], f"property_id {r['property_id']} repeated in {int(r['report_year'])} -> dropped")
    df = df[~dups]
    for key, g in df[df["report_year"] != year].groupby("site_key"):
        qlog.add("year fallback", str(g["property_name"].iloc[0]), f"lot {key}: no {year} record -> used {int(g['report_year'].iloc[0])}")
    return df.drop(columns=["_dist"])


def drop_near_duplicates(df: pd.DataFrame, qlog: QualityLog, max_dist_m: float = 250.0) -> pd.DataFrame:
    """Drop records that repeat another nearby record: same floor area (±1 %) and fuel
    (±10 %) at the same geocode (< SAME_SITE_M), or the same non-zero fuel (±0.01 % at the
    same geocode; exact within ``max_dist_m``). Twin buildings on one lot (e.g. Penn South 2 & 3) survive
    because they are geocoded apart and their meters differ. Typical cause: a building reported by both
    the owner and the managing agent, or once per condo lot."""
    # keep the cleanly-named record of each duplicate pair ('Copy of …', 'zzzz…' sort last)
    junk = df["property_name"].fillna("").str.contains(JUNK_NAME_PATTERN, case=False, regex=True)
    df = df.assign(_junk=junk).sort_values("_junk", kind="stable").drop(columns="_junk").reset_index(drop=True)
    fuel = df[ENERGY_COLUMNS[:-1]].fillna(0).sum(axis=1).to_numpy()
    gfa = df["property_gfa_self_reported"].fillna(-1).to_numpy()
    lat, lon = df["latitude"].to_numpy(), df["longitude"].to_numpy()
    allocated = df["campus_note"].fillna("").str.len().to_numpy() > 0
    drop: set[int] = set()
    for i in range(len(df)):
        if i in drop:
            continue
        d = haversine_m(lat[i], lon[i], lat, lon)
        valid = (fuel > 0) & (gfa > 0) & (fuel[i] > 0) & (gfa[i] > 0)
        # same geocode, same floor area, similar fuel → same building reported twice
        same_gfa = valid & ~allocated & ~allocated[i] & (d < SAME_SITE_M) & np.isclose(gfa, gfa[i], rtol=0.01) & np.isclose(fuel, fuel[i], rtol=0.10)
        # byte-identical fuel totals are never a coincidence, even if GFA was re-measured / re-geocoded
        same_fuel = (fuel[i] > 0) & (((d < max_dist_m) & np.isclose(fuel, fuel[i], rtol=1e-6, atol=0))
                                     | ((d < SAME_SITE_M) & np.isclose(fuel, fuel[i], rtol=1e-4, atol=0)))
        same_fuel &= ~allocated & ~allocated[i]  # campus-allocated rows share fuel by construction
        same = same_gfa | same_fuel
        for j in np.flatnonzero(same):
            if j > i and j not in drop:
                drop.add(j)
                qlog.add("duplicate", str(df.at[j, "property_name"]),
                         f"same GFA & fuel as '{df.at[i, 'property_name']}' ({d[j]:.0f} m away) -> dropped")
    return df.drop(index=sorted(drop)).reset_index(drop=True)


def fill_coordinates(df: pd.DataFrame, pluto: pd.DataFrame, qlog: QualityLog) -> pd.DataFrame:
    """Use PLUTO lot centroids where LL84 lat/lon is missing; drop rows still missing."""
    df = df.copy()
    pl = pluto.drop_duplicates("bbl").set_index("bbl")
    miss = df["latitude"].isna() | df["longitude"].isna()
    for idx in df[miss].index:
        bbl = df.at[idx, "bbl"]
        if bbl in pl.index:
            df.at[idx, "latitude"], df.at[idx, "longitude"] = pl.at[bbl, "latitude"], pl.at[bbl, "longitude"]
            df.at[idx, "coord_source"] = "PLUTO"
        else:
            qlog.add("missing coordinates", str(df.at[idx, "property_name"]),
                     f"BBL {bbl or 'missing'} not in LL84 coords or PLUTO → dropped")
    df["coord_source"] = df.get("coord_source", pd.Series(index=df.index, dtype=object)).fillna("LL84")
    return df.dropna(subset=["latitude", "longitude"])


def load_buildings(cfg: Config, qlog: QualityLog | None = None) -> tuple[pd.DataFrame, QualityLog]:
    """Cleaned building table within the configured radius of the site.

    Columns added: bbl, distance_m, gas/steam/oil kBtu (NaN→0), campus_note, coord_source.
    """
    qlog = qlog or QualityLog()
    raw = fetch_ll84(cfg, qlog)
    raw = _coerce_ll84(raw)
    pluto = fetch_pluto(cfg, qlog)
    raw["bbls"] = raw["nyc_borough_block_and_lot"].map(normalize_bbl)
    raw["bbl"] = raw["bbls"].map(lambda b: b[0] if b else None)
    raw = fill_coordinates(raw, pluto, qlog)
    radius = cfg.v("data.radius_m")
    site = (cfg.v("site.lat"), cfg.v("site.lon"))
    # pre-filter with a margin so campus records straddling the circle are resolved whole
    raw = raw[haversine_m(*site, raw["latitude"], raw["longitude"]) <= radius + CAMPUS_MARGIN_M].copy()
    for _, r in raw[raw["bbl"].isna()].drop_duplicates("property_id").iterrows():
        qlog.add("missing BBL", str(r["property_name"]), "no valid BBL reported (kept, keyed by property_id)")
    df = resolve_campus_records(raw, pluto, qlog)
    df = select_report_year(df, int(cfg.v("data.ll84_report_year")), qlog)
    df = drop_near_duplicates(df, qlog)
    df["distance_m"] = haversine_m(*site, df["latitude"], df["longitude"])
    df = df[df["distance_m"] <= radius].copy()
    if cfg.get("site.exclude_source_building"):
        src = df["bbl"] == cfg.get("site.bbl")
        for _, r in df[src].iterrows():
            qlog.add("excluded", r["property_name"], "source building (data center) excluded from candidates")
        df = df[~src]
    df["oil_kbtu"] = df[OIL_COLUMNS].fillna(0).sum(axis=1)
    df["gas_kbtu"] = df["natural_gas_use_kbtu"].fillna(0)
    df["steam_kbtu"] = df["district_steam_use_kbtu"].fillna(0)
    df["elec_kwh"] = df["electricity_use_grid_purchase_1"].fillna(0)
    df["gfa_ft2"] = df["property_gfa_self_reported"]
    df["campus_note"] = df["campus_note"].fillna("")
    return df.reset_index(drop=True), qlog


# ---------------------------------------------------------------------------
# Streets
# ---------------------------------------------------------------------------
def fetch_streets(cfg: Config, qlog: QualityLog):
    """OSM street graph (osmnx MultiDiGraph, unprojected) around the site, cached as GraphML.

    Falls back to a synthetic Manhattan grid (networkx Graph with the same node/edge
    attributes: x=lon, y=lat, length=m) if OSM is unreachable.
    """
    import osmnx as ox

    dist = int(cfg.v("data.street_graph_dist_m"))
    ntype = cfg.get("data.street_network_type")
    path = cfg.cache_dir / f"streets_{ntype}_{dist}m.graphml"
    if _cached(path):
        qlog.source("OSM streets", "cache")
        return ox.load_graphml(path)
    try:
        g = ox.graph_from_point((cfg.v("site.lat"), cfg.v("site.lon")), dist=dist, network_type=ntype)
        cfg.cache_dir.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(g, path)
        qlog.source("OSM streets", "live")
        return g
    except Exception as exc:
        log.warning("OSM fetch failed (%s); using synthetic Manhattan grid", exc)
        qlog.source("OSM streets", "sample")
        return synthetic_grid(cfg.v("site.lat"), cfg.v("site.lon"), dist)


def synthetic_grid(lat0: float, lon0: float, dist_m: float):
    """Synthetic Manhattan street grid: avenues every 260 m, streets every 80 m, rotated
    29° (Manhattan grid bearing). Clearly a stand-in — used only when OSM is unreachable."""
    import networkx as nx

    theta = math.radians(29.0)
    m_per_deg_lat = 111_000.0
    m_per_deg_lon = 111_000.0 * math.cos(math.radians(lat0))
    xs = np.arange(-dist_m, dist_m + 1, 260.0)   # along streets (cross-town)
    ys = np.arange(-dist_m, dist_m + 1, 80.0)    # along avenues
    g = nx.Graph()
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            e = x * math.cos(theta) - y * math.sin(theta)
            n = x * math.sin(theta) + y * math.cos(theta)
            g.add_node((i, j), x=lon0 + e / m_per_deg_lon, y=lat0 + n / m_per_deg_lat)
    for i in range(len(xs)):
        for j in range(len(ys)):
            if i + 1 < len(xs):
                g.add_edge((i, j), (i + 1, j), length=260.0)
            if j + 1 < len(ys):
                g.add_edge((i, j), (i, j + 1), length=80.0)
    return nx.convert_node_labels_to_integers(g)
