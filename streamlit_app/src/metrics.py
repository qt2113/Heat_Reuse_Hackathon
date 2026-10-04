"""Economics, emissions, water and headline KPIs.

Conventions: heat in MWh_th, electricity in MWh_e, money in USD/yr (capex annualised with a
capital recovery factor), emissions in tCO2e/yr. "Served" heat = heat delivered to buildings by
the network (data center direct + storage). Unserved heat is still met by each building's
existing boilers, so it changes neither cost nor emissions relative to today.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .supply import DispatchResult, HeatPump
from .units import MMBTU_TO_MWH

FUELS = ("gas", "steam", "oil")


def crf(rate: float, years: float) -> float:
    """Capital recovery factor: annual payment per $ of capex."""
    if rate == 0:
        return 1.0 / years
    f = (1 + rate) ** years
    return rate * f / (f - 1)


def _fuel_efficiency(cfg: Config) -> dict[str, float]:
    return {"gas": cfg.v("demand.boiler_efficiency"), "steam": cfg.v("demand.steam_utilization_efficiency"),
            "oil": cfg.v("demand.oil_boiler_efficiency")}


def fuel_cost_per_mwh_heat(cfg: Config) -> dict[str, float]:
    """USD per MWh of useful heat produced by each building's current system."""
    price = {"gas": cfg.v("economics.gas_price_usd_mmbtu"), "steam": cfg.v("economics.steam_price_usd_mmbtu"),
             "oil": cfg.v("economics.oil_price_usd_mmbtu")}
    eff = _fuel_efficiency(cfg)
    return {f: price[f] / MMBTU_TO_MWH / eff[f] for f in FUELS}


def fuel_co2_per_mwh_heat(cfg: Config) -> dict[str, float]:
    """tCO2e per MWh of useful heat from each current fuel (fuel factor / efficiency)."""
    ef = {"gas": cfg.v("emissions.gas_tco2_per_mmbtu"), "steam": cfg.v("emissions.steam_tco2_per_mmbtu"),
          "oil": cfg.v("emissions.oil_tco2_per_mmbtu")}
    eff = _fuel_efficiency(cfg)
    return {f: ef[f] / MMBTU_TO_MWH / eff[f] for f in FUELS}


def network_heat_cost_per_mwh(cfg: Config, hp: HeatPump) -> float:
    """Electricity cost (USD) per MWh_th delivered: heat-pump compressor + distribution pumps."""
    mwh_e = 1.0 / hp.cop + cfg.v("supply.pumping_kwh_per_mwh") / 1000.0
    return mwh_e * cfg.v("economics.electricity_price_usd_kwh") * 1000.0


def network_co2_per_mwh(cfg: Config, hp: HeatPump) -> float:
    """tCO2e per MWh_th delivered (grid electricity for HP + pumps)."""
    mwh_e = 1.0 / hp.cop + cfg.v("supply.pumping_kwh_per_mwh") / 1000.0
    return mwh_e * 1000.0 * cfg.v("emissions.grid_tco2_per_kwh")


def ll97_excess(b: pd.DataFrame, cfg: Config) -> pd.Series:
    """tCO2e/yr each building emits above its LL97 2024-29 limit (0 if under, exempt or no limit)."""
    em = (b["gas_kbtu"] / 1000 * cfg.v("emissions.gas_tco2_per_mmbtu")
          + b["steam_kbtu"] / 1000 * cfg.v("emissions.steam_tco2_per_mmbtu")
          + b["oil_kbtu"] / 1000 * cfg.v("emissions.oil_tco2_per_mmbtu")
          + b["elec_kwh"] * cfg.v("emissions.grid_tco2_per_kwh"))
    limits = cfg.get("emissions.ll97_limits_2024_tco2e_ft2")
    lim = b["primary_property_type"].map(lambda t: limits["by_type"].get(t, limits["default"]))
    cap = pd.to_numeric(lim, errors="coerce") * b["gfa_ft2"]
    pattern = "|".join(cfg.get("emissions.ll97_exempt_name_patterns"))
    exempt = b["property_name"].fillna("").str.upper().str.contains(pattern, regex=True)
    excess = (em - cap).clip(lower=0).fillna(0.0)
    return excess.where(~exempt, 0.0)


def water_usd_per_mwh(cfg: Config, hp: HeatPump) -> float:
    """Cooling-tower water cost avoided per MWh delivered (data-center owner's saving).
    Recovered DC heat per MWh delivered = 1 − 1/COP."""
    return (1 - 1 / hp.cop) * cfg.v("emissions.water_m3_per_mwh") * cfg.v("objective.water_price_usd_m3")


def is_priority(b: pd.DataFrame, cfg: Config) -> pd.Series:
    """NYCHA / Mitchell-Lama housing (by name) and public schools (by property type)."""
    pattern = "|".join(cfg.get("objective.priority_name_patterns"))
    by_name = b["property_name"].fillna("").str.upper().str.contains(pattern, regex=True)
    by_type = b["primary_property_type"].isin(cfg.get("objective.priority_property_types"))
    return by_name | by_type


def building_economics(b: pd.DataFrame, cfg: Config, hp: HeatPump) -> pd.DataFrame:
    """Per-building value parameters.

    Cash (always reported):
      fuel_cost_usd_mwh  what the building pays today per MWh of useful heat
      margin_usd_mwh     project cash margin per MWh served: fuel saved − network electricity + water saved
      co2_cut_t_mwh      net tCO2e avoided per MWh served (fuel displaced − grid electricity)
      ll97_excess_t      tCO2e/yr over the LL97 cap (avoided penalty is capped by this)
      conn_usd_yr        annualised building-substation cost (sized on building peak)
    Objective (what the optimiser maximises, set by config 'objective'):
      obj_margin_usd_mwh, obj_ll97_t   perspective margin + carbon value, × priority weight
    """
    out = b.copy()
    total = out["annual_heat_mwh"].replace(0, np.nan)
    shares = {f: out[f"heat_{f}_mwh"] / total for f in FUELS}
    cost = fuel_cost_per_mwh_heat(cfg)
    co2 = fuel_co2_per_mwh_heat(cfg)
    nh = network_heat_cost_per_mwh(cfg, hp)
    water = water_usd_per_mwh(cfg, hp)
    out["fuel_cost_usd_mwh"] = sum(shares[f] * cost[f] for f in FUELS)
    out["margin_usd_mwh"] = out["fuel_cost_usd_mwh"] - nh + water
    out["co2_cut_t_mwh"] = sum(shares[f] * co2[f] for f in FUELS) - network_co2_per_mwh(cfg, hp)
    out["ll97_excess_t"] = ll97_excess(out, cfg) if cfg.get("emissions.ll97_enabled") else 0.0
    out["conn_usd_yr"] = (out["peak_kw"] * cfg.v("network.building_connection_usd_per_kw")
                          * crf(cfg.v("economics.discount_rate"), cfg.v("network.connection_life_yr")))
    out["priority"] = is_priority(out, cfg)

    perspective = cfg.get("objective.perspective")
    if perspective == "project":
        obj, obj_ll97 = out["margin_usd_mwh"], out["ll97_excess_t"]
    elif perspective == "operator":
        d = cfg.v("objective.heat_discount")
        obj, obj_ll97 = out["fuel_cost_usd_mwh"] * (1 - d) - nh + water, 0.0 * out["ll97_excess_t"]
    else:
        raise ValueError(f"unknown objective perspective {perspective!r}")
    weight = np.where(out["priority"], cfg.v("objective.priority_weight"), 1.0)
    out["obj_margin_usd_mwh"] = (obj + cfg.v("objective.carbon_price_usd_t") * out["co2_cut_t_mwh"]) * weight
    out["obj_ll97_t"] = obj_ll97 * weight
    return out


def cash_value(served_mwh: np.ndarray, econ: pd.DataFrame, cfg: Config) -> np.ndarray:
    """Project cash value (USD/yr) of serving each building, before its connection cost."""
    pen = cfg.v("emissions.ll97_penalty_usd_t") if cfg.get("emissions.ll97_enabled") else 0.0
    k = np.clip(econ["co2_cut_t_mwh"].to_numpy(), 0, None)
    s = np.asarray(served_mwh, dtype=float)
    return s * econ["margin_usd_mwh"].to_numpy() + pen * np.minimum(econ["ll97_excess_t"].to_numpy(), k * s)


def annualised_capex(cfg: Config, pipe_m: float, conn_usd_yr: float, hp: HeatPump) -> dict[str, float]:
    """Annualised capital cost components (USD/yr)."""
    r = cfg.v("economics.discount_rate")
    return {
        "pipes": pipe_m * cfg.v("economics.pipe_cost_usd_m") * crf(r, cfg.v("economics.pipe_life_yr")),
        "connections": conn_usd_yr,
        "heat_pump": hp.q_delivered_mw * 1000 * cfg.v("economics.hp_capex_usd_kw") * crf(r, cfg.v("economics.hp_life_yr")),
        "storage": cfg.v("supply.storage_mwh") * cfg.v("economics.storage_capex_usd_mwh") * crf(r, cfg.v("economics.hp_life_yr")),
    }


def kpis(econ_sel: pd.DataFrame, served_by_bldg: np.ndarray, disp: DispatchResult, pipe_m: float,
         cfg: Config) -> dict[str, float]:
    """Headline KPIs for a connected set after hourly dispatch.

    served_by_bldg: MWh/yr each selected building receives from the network.
    """
    s = disp.summary
    hp = disp.hp
    served = float(served_by_bldg.sum())
    cost = fuel_cost_per_mwh_heat(cfg)
    co2 = fuel_co2_per_mwh_heat(cfg)
    total = econ_sel["annual_heat_mwh"].replace(0, np.nan)
    fuel_mix = {f: (econ_sel[f"heat_{f}_mwh"] / total).fillna(0).to_numpy() for f in FUELS}
    displaced_heat = {f: float((served_by_bldg * fuel_mix[f]).sum()) for f in FUELS}
    avoided_fuel_usd = sum(displaced_heat[f] * cost[f] for f in FUELS)
    co2_fuel = sum(displaced_heat[f] * co2[f] for f in FUELS)
    elec_mwh = s["hp_elec_mwh"] + s["pump_elec_mwh"]
    co2_grid = elec_mwh * 1000 * cfg.v("emissions.grid_tco2_per_kwh")
    elec_usd = elec_mwh * 1000 * cfg.v("economics.electricity_price_usd_kwh")
    water_m3 = s["recovered_heat_mwh"] * cfg.v("emissions.water_m3_per_mwh")
    water_usd = water_m3 * cfg.v("objective.water_price_usd_m3")
    pen = cfg.v("emissions.ll97_penalty_usd_t") if cfg.get("emissions.ll97_enabled") else 0.0
    k = np.clip(econ_sel["co2_cut_t_mwh"].to_numpy(), 0, None)
    ll97_usd = float(pen * np.minimum(econ_sel["ll97_excess_t"].to_numpy(), k * served_by_bldg).sum())
    capex = annualised_capex(cfg, pipe_m, float(econ_sel["conn_usd_yr"].sum()), hp)
    capex_total = sum(capex.values())
    demand = float(econ_sel["annual_heat_mwh"].sum())
    # who gets what, at the configured heat discount
    d = cfg.v("objective.heat_discount")
    heat_bill_usd = avoided_fuel_usd * (1 - d)          # paid by buildings to the operator
    prio = econ_sel["priority"].to_numpy() if "priority" in econ_sel else np.zeros(len(econ_sel), bool)
    net = avoided_fuel_usd + ll97_usd + water_usd - elec_usd - capex_total
    return {
        "buildings": len(econ_sel),
        "pipe_km": pipe_m / 1000,
        "connected_demand_mwh": demand,
        "served_mwh": served,
        "coverage": served / demand if demand else 0.0,
        "share_dc": s["share_dc"], "share_storage": s["share_storage"], "share_backup": s["share_backup"],
        "recovered_heat_mwh": s["recovered_heat_mwh"],
        "hp_elec_mwh": s["hp_elec_mwh"], "pump_elec_mwh": s["pump_elec_mwh"],
        "network_loss_mwh": s["network_loss_mwh"],
        "co2_fuel_avoided_t": co2_fuel, "co2_grid_added_t": co2_grid, "co2_net_t": co2_fuel - co2_grid,
        "carbon_value_usd": (co2_fuel - co2_grid) * cfg.v("objective.carbon_price_usd_t"),
        "avoided_fuel_usd": avoided_fuel_usd, "avoided_ll97_usd": ll97_usd, "electricity_usd": elec_usd,
        "water_usd": water_usd,
        **{f"capex_{k_}_usd": v for k_, v in capex.items()},
        "capex_total_usd": capex_total,
        "net_usd": net,
        "operator_profit_usd": heat_bill_usd + water_usd - elec_usd - capex_total,
        "building_savings_usd": avoided_fuel_usd * d + ll97_usd,
        "priority_buildings": int(prio.sum()),
        "priority_served_mwh": float(served_by_bldg[prio].sum()) if len(prio) else 0.0,
        "water_m3": water_m3,
        "storage_needed_for_outage_mwh": s["storage_needed_for_outage_mwh"],
        "hp_cop": hp.cop, "hp_delivered_mw": hp.q_delivered_mw,
    }
