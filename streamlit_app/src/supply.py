"""Heat-pump supply and hourly dispatch: data center → storage tank → backup boilers.

Units: power in MW (= MWh per hour step), energy in MWh, temperatures in °C (converted to K
for the Carnot term). One time step = 1 hour.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config
from .units import c_to_k

BALANCE_TOL_MW = 1e-9


def heat_pump_cop(t_source_c: float, t_sink_c: float, eta: float) -> float:
    """COP = eta × T_hot / (T_hot − T_cold), temperatures in kelvin.

    Raises if the sink is not hotter than the source (no lift → formula invalid).
    """
    t_hot, t_cold = c_to_k(t_sink_c), c_to_k(t_source_c)
    if t_hot <= t_cold:
        raise ValueError(f"sink {t_sink_c} °C must exceed source {t_source_c} °C")
    return eta * t_hot / (t_hot - t_cold)


def required_sink_temp_c(cfg: Config) -> float:
    """Heat-pump condenser temperature = network supply temperature + building HX penalty."""
    return cfg.v("supply.t_supply_c") + cfg.v("supply.hx_penalty_k")


@dataclass(frozen=True)
class HeatPump:
    """Steady-state heat-pump operating point for a given recoverable source heat."""

    q_src_mw: float       # heat extracted from the data center (evaporator), MW_th
    cop: float
    q_delivered_mw: float  # condenser output = q_src × COP/(COP−1), MW_th
    p_elec_mw: float       # compressor electricity = q_delivered / COP, MW_e

    @classmethod
    def from_config(cls, cfg: Config) -> "HeatPump":
        cop = heat_pump_cop(cfg.v("supply.t_source_c"), required_sink_temp_c(cfg), cfg.v("supply.cop_eta"))
        if cop <= 1.0:
            raise ValueError(f"COP {cop:.2f} ≤ 1: heat pump cannot deliver more than its electricity")
        q_src = float(cfg.v("supply.q_src_mw"))
        q_del = q_src * cop / (cop - 1.0)
        return cls(q_src_mw=q_src, cop=cop, q_delivered_mw=q_del, p_elec_mw=q_del / cop)


def outage_mask(demand_mw: np.ndarray, hours: int, placement: str) -> np.ndarray:
    """Boolean mask of outage hours: one contiguous block (wrapping the year end)."""
    n = len(demand_mw)
    mask = np.zeros(n, dtype=bool)
    hours = int(min(max(hours, 0), n))
    if hours == 0:
        return mask
    if placement == "peak":
        centre = int(np.argmax(demand_mw))
    elif placement == "summer":
        centre = 212 * 24  # 1 Aug 00:00
    else:
        raise ValueError(f"unknown outage placement {placement!r}")
    mask[(np.arange(hours) + centre - hours // 2) % n] = True
    return mask


@dataclass
class DispatchResult:
    hourly: pd.DataFrame   # columns in MW (per hour) / MWh (soc)
    hp: HeatPump
    summary: dict[str, float]


def dispatch(demand_mw: np.ndarray, cfg: Config, index: pd.DatetimeIndex | None = None,
             network_loss_mw: float = 0.0) -> DispatchResult:
    """Hourly merit-order dispatch for an aggregate load.

    Order each hour: (1) heat pump serves load directly up to its capacity; (2) surplus
    capacity charges the tank; (3) remaining load is met from the tank, then (4) backup
    boilers. The tank loses a fixed fraction per hour. The year is run twice and the
    second pass starts from the first pass's final state of charge (periodic steady state).

    ``network_loss_mw`` is a constant distribution heat loss added to the load.
    """
    hp = HeatPump.from_config(cfg)
    load = np.asarray(demand_mw, dtype=float) + network_loss_mw
    n = len(load)
    out_mask = outage_mask(load, int(cfg.v("supply.outage_hours")), cfg.get("supply.outage_placement"))
    avail = np.where(out_mask, 0.0, hp.q_delivered_mw)
    cap = float(cfg.v("supply.storage_mwh"))
    p_max = float(cfg.v("supply.storage_max_power_mw"))
    loss = float(cfg.v("supply.storage_loss_per_h"))

    soc0 = 0.0
    for _ in range(2):
        cols = _simulate(load, avail, cap, p_max, loss, soc0)
        soc0 = cols["soc_end"][-1]

    direct, charge, discharge, backup = cols["direct"], cols["charge"], cols["discharge"], cols["backup"]
    err = np.abs(direct + discharge + backup - load).max()
    assert err < BALANCE_TOL_MW, f"hourly energy balance violated by {err} MW"

    hp_heat = direct + charge
    pump_mw = (direct + discharge) * cfg.v("supply.pumping_kwh_per_mwh") / 1000.0
    hourly = pd.DataFrame({
        "demand": load, "available": avail, "dc_direct": direct, "storage_charge": charge,
        "storage_discharge": discharge, "backup": backup, "soc": cols["soc_end"],
        "storage_loss": cols["loss"], "hp_heat": hp_heat, "hp_elec": hp_heat / hp.cop,
        "pump_elec": pump_mw, "outage": out_mask,
    }, index=index if index is not None else pd.RangeIndex(n))
    return DispatchResult(hourly=hourly, hp=hp, summary=_summarise(hourly, hp, cap, network_loss_mw))


def _simulate(load: np.ndarray, avail: np.ndarray, cap: float, p_max: float, loss: float,
              soc0: float) -> dict[str, np.ndarray]:
    """Single pass of the hourly storage loop (plain Python floats: ~10 ms for 8,760 h)."""
    n = len(load)
    direct, charge, discharge, backup, soc_end, lost = (np.zeros(n) for _ in range(6))
    soc = soc0
    for t in range(n):
        lt = soc * loss
        soc -= lt
        d = min(load[t], avail[t])
        c = min(avail[t] - d, p_max, cap - soc)
        deficit = load[t] - d
        x = min(deficit, p_max, soc)
        soc += c - x
        direct[t], charge[t], discharge[t], backup[t] = d, c, x, deficit - x
        soc_end[t], lost[t] = soc, lt
    return {"direct": direct, "charge": charge, "discharge": discharge, "backup": backup,
            "soc_end": soc_end, "loss": lost}


def _summarise(h: pd.DataFrame, hp: HeatPump, cap: float, network_loss_mw: float) -> dict[str, float]:
    """Annual totals (MWh/yr) and shares. 'Served' = heat delivered to buildings (net of losses)."""
    demand = h["demand"].sum()
    from_dc = h["dc_direct"].sum()
    from_storage = h["storage_discharge"].sum()
    backup = h["backup"].sum()
    outage = h["outage"].to_numpy()
    # heat the DC would have supplied directly during the outage = tank size needed to ride through
    storage_for_outage = float(np.minimum(h["demand"].to_numpy()[outage], hp.q_delivered_mw).sum())
    return {
        "demand_mwh": demand,
        "network_loss_mwh": network_loss_mw * len(h),
        "dc_direct_mwh": from_dc,
        "storage_discharge_mwh": from_storage,
        "backup_mwh": backup,
        "recovered_heat_mwh": h["hp_heat"].sum() * (1 - 1 / hp.cop),   # taken from the DC loop
        "hp_heat_mwh": h["hp_heat"].sum(),
        "hp_elec_mwh": h["hp_elec"].sum(),
        "pump_elec_mwh": h["pump_elec"].sum(),
        "storage_loss_mwh": h["storage_loss"].sum(),
        "share_dc": from_dc / demand if demand else 0.0,
        "share_storage": from_storage / demand if demand else 0.0,
        "share_backup": backup / demand if demand else 0.0,
        "hp_capacity_factor": h["hp_heat"].sum() / (hp.q_delivered_mw * len(h)),
        "peak_demand_mw": h["demand"].max(),
        "peak_backup_mw": h["backup"].max(),
        "storage_needed_for_outage_mwh": storage_for_outage,
        "storage_capacity_mwh": cap,
    }
