"""Annual heat demand per building and hourly (8,760 h) profiles.

Units: annual energy in MWh_th/yr; hourly demand in MWh per hour (= average MW_th).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .fetch import QualityLog
from .units import FT2_TO_M2, KBTU_TO_MWH, HOURS_PER_YEAR


def annual_heat(df: pd.DataFrame, cfg: Config, qlog: QualityLog | None = None) -> pd.DataFrame:
    """Add annual useful-heat columns (MWh_th/yr) to the building table.

    useful heat by fuel = fuel × conversion efficiency × (1 − non-heating share)
    then split into DHW / space heat with the property-type DHW share.
    Buildings with no heating fuel reported are dropped (logged).
    """
    out = df.copy()
    eff_gas = cfg.v("demand.boiler_efficiency")
    eff_oil = cfg.v("demand.oil_boiler_efficiency")
    eff_steam = cfg.v("demand.steam_utilization_efficiency")
    ptype = out["primary_property_type"].fillna("Other")
    out["non_heating_share"] = ptype.map(lambda t: cfg.by_type("demand.non_heating_share", t))
    keep = 1.0 - out["non_heating_share"]
    out["heat_gas_mwh"] = out["gas_kbtu"] * KBTU_TO_MWH * eff_gas * keep
    out["heat_steam_mwh"] = out["steam_kbtu"] * KBTU_TO_MWH * eff_steam * keep
    out["heat_oil_mwh"] = out["oil_kbtu"] * KBTU_TO_MWH * eff_oil * keep
    out["annual_heat_mwh"] = out[["heat_gas_mwh", "heat_steam_mwh", "heat_oil_mwh"]].sum(axis=1)

    dhw_mult = cfg.v("demand.dhw_multiplier")
    out["dhw_share"] = (ptype.map(lambda t: cfg.by_type("demand.dhw_share", t)) * dhw_mult).clip(0, 1)
    out["annual_dhw_mwh"] = out["annual_heat_mwh"] * out["dhw_share"]
    out["annual_space_mwh"] = out["annual_heat_mwh"] - out["annual_dhw_mwh"]
    out["heat_fuel_kbtu_ft2"] = (out["gas_kbtu"] + out["steam_kbtu"] + out["oil_kbtu"]) / out["gfa_ft2"]
    out["main_fuel"] = out[["heat_gas_mwh", "heat_steam_mwh", "heat_oil_mwh"]].idxmax(axis=1).str.split("_").str[1]

    if qlog is not None:
        for _, r in out[out["annual_heat_mwh"] <= 0].iterrows():
            qlog.add("no heating fuel", r["property_name"],
                     "gas/steam/oil all missing or zero (all-electric, or not reported) → not a candidate")
        lo, hi = cfg.v("demand.heat_intensity_outlier_kbtu_ft2")
        for _, r in out[(out["annual_heat_mwh"] > 0) & ~out["heat_fuel_kbtu_ft2"].between(lo, hi)].iterrows():
            qlog.add("intensity outlier", r["property_name"],
                     f"heating fuel {r['heat_fuel_kbtu_ft2']:.0f} kBtu/ft2/yr outside [{lo}, {hi}]")
    out = out[out["annual_heat_mwh"] > 0].copy()
    return apply_pilot_exclusion(out, cfg, qlog).reset_index(drop=True)


def apply_pilot_exclusion(df: pd.DataFrame, cfg: Config, qlog: QualityLog | None) -> pd.DataFrame:
    """Optionally remove the Con Ed pilot buildings' share of their lot's demand."""
    if not cfg.get("con_ed_pilot.exclude_pilot_demand"):
        return df
    share = cfg.v("con_ed_pilot.pilot_share_of_lot")
    lots = {r["bbl"] for r in cfg.get("con_ed_pilot.receivers")}
    out = df.copy()
    mask = out["bbl"].isin(lots)
    cols = ["heat_gas_mwh", "heat_steam_mwh", "heat_oil_mwh", "annual_heat_mwh", "annual_dhw_mwh", "annual_space_mwh"]
    out.loc[mask, cols] *= (1.0 - share)
    if qlog is not None:
        for _, r in out[mask].iterrows():
            qlog.add("pilot exclusion", r["property_name"], f"removed {share:.0%} of demand (served by Con Ed pilot)")
    return out


def heating_degree_hours(temp_c: np.ndarray, t_base_c: float) -> np.ndarray:
    """HDH_t = max(0, T_base − T_t) in K·h."""
    return np.maximum(0.0, t_base_c - np.asarray(temp_c, dtype=float))


def smooth_circular(x: np.ndarray, window_h: int) -> np.ndarray:
    """Trailing moving average over ``window_h`` hours, wrapping Dec→Jan so the sum is
    preserved exactly (the year is treated as periodic). window_h ≤ 1 returns x."""
    if window_h <= 1:
        return np.asarray(x, dtype=float)
    padded = np.concatenate([x[-(window_h - 1):], x])
    c = np.cumsum(np.insert(padded, 0, 0.0))
    return (c[window_h:] - c[:-window_h]) / window_h


def space_shape(temp_c: np.ndarray, t_base_c: float, smoothing_h: int = 0) -> np.ndarray:
    """Normalised (sums to 1) hourly space-heat shape proportional to HDH.

    ``smoothing_h`` > 1 averages HDH over the trailing window to mimic building thermal
    mass (peak load follows the daily mean, not the coldest single hour). Annual energy
    is unchanged; only the peak and timing move.
    """
    hdh = smooth_circular(heating_degree_hours(temp_c, t_base_c), int(smoothing_h))
    if hdh.sum() <= 0:
        raise ValueError("no heating degree-hours in weather year")
    return hdh / hdh.sum()


def dhw_shape(hours_of_day: np.ndarray, daily_weights: list[float]) -> np.ndarray:
    """Normalised (sums to 1) hourly DHW shape: same daily curve every day."""
    w = np.asarray(daily_weights, dtype=float)
    if w.shape != (24,) or (w < 0).any():
        raise ValueError("dhw daily profile needs 24 non-negative weights")
    s = w[np.asarray(hours_of_day)]
    return s / s.sum()


def hourly_demand(buildings: pd.DataFrame, temp: pd.Series, cfg: Config) -> np.ndarray:
    """Hourly heat demand matrix, shape (n_buildings, 8760), in MWh/h (= MW_th).

    Row sums equal annual_heat_mwh exactly (energy conservation by construction).
    """
    if len(temp) != HOURS_PER_YEAR:
        raise ValueError("temperature series must have 8760 hours")
    s = space_shape(temp.to_numpy(), cfg.v("demand.t_base_c"), int(cfg.v("demand.space_smoothing_h")))
    d = dhw_shape(temp.index.hour.to_numpy(), cfg.get("demand.dhw_daily_profile")["weights"])
    space = buildings["annual_space_mwh"].to_numpy()[:, None] * s[None, :]
    dhw = buildings["annual_dhw_mwh"].to_numpy()[:, None] * d[None, :]
    return space + dhw


def peak_check(buildings: pd.DataFrame, demand: np.ndarray, cfg: Config,
               qlog: QualityLog | None = None) -> pd.DataFrame:
    """Add peak_kw, peak_w_m2, full_load_hours and a sanity flag (outside W/m2 band)."""
    out = buildings.copy()
    out["peak_kw"] = demand.max(axis=1) * 1000.0
    area_m2 = out["gfa_ft2"] * FT2_TO_M2
    out["peak_w_m2"] = out["peak_kw"] * 1000.0 / area_m2
    out["full_load_hours"] = out["annual_heat_mwh"] * 1000.0 / out["peak_kw"]
    lo, hi = cfg.v("demand.peak_intensity_check_w_m2")
    out["peak_flag"] = ~out["peak_w_m2"].between(lo, hi)
    if qlog is not None:
        for _, r in out[out["peak_flag"]].iterrows():
            qlog.add("peak W/m2 out of range", r["property_name"],
                     f"peak {r['peak_w_m2']:.0f} W/m2 outside [{lo}, {hi}] (GFA {r['gfa_ft2']:,.0f} ft2)")
    return out


def screen_outliers(buildings: pd.DataFrame, demand: np.ndarray, cfg: Config,
                    qlog: QualityLog | None = None) -> tuple[pd.DataFrame, np.ndarray]:
    """Remove buildings whose peak intensity is physically implausible for a single building
    (typically a campus central plant or CHP whose fuel serves other lots, or a GFA error).
    Buildings in the merely-unusual band stay in, flagged by ``peak_check``."""
    limit = cfg.v("demand.exclude_peak_w_m2_above")
    bad = (buildings["peak_w_m2"] > limit).to_numpy()
    if qlog is not None:
        for _, r in buildings[bad].iterrows():
            qlog.add("excluded outlier", r["property_name"],
                     f"peak {r['peak_w_m2']:.0f} W/m2 > {limit} → excluded (likely central plant serving other lots, or GFA error)")
    return buildings[~bad].reset_index(drop=True), demand[~bad]


def build_demand(cfg: Config) -> tuple[pd.DataFrame, np.ndarray, pd.Series, QualityLog]:
    """Full demand pipeline: load → annual split → hourly matrix → sanity flags → outlier screen.

    Returns (buildings, demand[n, 8760] in MW, hourly temperature °C, quality log).
    """
    from .fetch import fetch_weather, load_buildings  # local import keeps module deps one-way

    b, qlog = load_buildings(cfg)
    temp = fetch_weather(cfg, qlog)
    b = annual_heat(b, cfg, qlog)
    dem = hourly_demand(b, temp, cfg)
    b = peak_check(b, dem, cfg, qlog)
    b, dem = screen_outliers(b, dem, cfg, qlog)
    return b, dem, temp, qlog
