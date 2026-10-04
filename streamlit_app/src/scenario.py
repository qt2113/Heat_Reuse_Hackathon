"""End-to-end scenario: selection → hourly dispatch → KPIs. Shared by the app and scripts.

Heavy, slider-independent pieces (buildings, demand matrix, street graph, snapping) are built
once by ``prepare``; ``evaluate`` is the fast part re-run on every slider change.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import numpy as np
import pandas as pd

from .config import Config
from .demand import build_demand
from .fetch import QualityLog, fetch_streets
from .metrics import building_economics, cash_value, kpis, network_heat_cost_per_mwh
from .network import (Prizes, Selection, build_graph, cost_per_m_yr, greedy_select, locked_selection,
                      refine_select, served_by_building, snap)
from .supply import DispatchResult, HeatPump, dispatch

STREET_MARGIN_M = 200.0  # street graph extends this far beyond the building radius


@dataclass
class Prepared:
    buildings: pd.DataFrame
    demand: np.ndarray          # (n, 8760) MW
    temp: pd.Series
    qlog: QualityLog
    graph: nx.Graph
    node: np.ndarray            # snapped node per building
    service_m: np.ndarray       # service pipe length per building
    root: object                # data center street node
    root_service_m: float


@dataclass
class Result:
    cfg: Config
    method_used: str
    note: str
    selection: Selection
    econ: pd.DataFrame          # all candidates with economics (+ served/value for selected)
    dispatch: DispatchResult
    kpi: dict[str, float]


def street_dist_m(cfg: Config) -> int:
    """Street graph half-width: config value or radius + margin, rounded up to 100 m."""
    need = max(cfg.v("data.street_graph_dist_m"), cfg.v("data.radius_m") + STREET_MARGIN_M)
    return int(np.ceil(need / 100.0) * 100)


def prepare(cfg: Config) -> Prepared:
    """Build everything that does not depend on prices / supply sliders."""
    b, dem, temp, qlog = build_demand(cfg)
    cfg_streets = cfg.with_overrides({"data.street_graph_dist_m": street_dist_m(cfg)})
    g = build_graph(fetch_streets(cfg_streets, qlog), cfg)
    node, service = snap(g, b["latitude"].to_numpy(), b["longitude"].to_numpy())
    root, root_d = snap(g, np.array([cfg.v("site.lat")]), np.array([cfg.v("site.lon")]))
    return Prepared(b, dem, temp, qlog, g, node, service, root[0], float(root_d[0]))


METHODS = {
    "recommended": "Greedy + local search (recommended)",
    "greedy": "Greedy only (fastest)",
}


def select(p: Prepared, prizes: Prizes, cost_m: float, method: str) -> tuple[Selection, str, str]:
    """Run a selection method. 'recommended' = greedy followed by local search."""
    if method == "recommended":
        return refine_select(p.graph, p.root, prizes, p.service_m, cost_m), method, ""
    if method == "greedy":
        return greedy_select(p.graph, p.root, prizes, p.service_m, cost_m), method, ""
    sel = refine_select(p.graph, p.root, prizes, p.service_m, cost_m)
    return sel, "recommended", f"Method '{method}' is not available — showing the recommended method."


def evaluate(p: Prepared, cfg: Config, method: str = "recommended", locked: Selection | None = None) -> Result:
    """Selection + hourly dispatch + KPIs for one parameter set.

    ``locked``: keep this network (buildings + pipes) and only re-cost it — used for
    best/worst-case stress tests of the base-case design.
    """
    hp = HeatPump.from_config(cfg)
    econ = building_economics(p.buildings, cfg, hp)
    cost_m = cost_per_m_yr(cfg, network_heat_cost_per_mwh(cfg, hp))
    prizes = Prizes.build(econ, p.demand, p.node, p.service_m, cost_m, hp.q_delivered_mw, cfg)
    if locked is not None:
        sel, used, note = locked_selection(p.graph, locked, prizes, p.service_m, cost_m), "locked", ""
    else:
        sel, used, note = select(p, prizes, cost_m, method)
    idx = sel.selected
    loss_mw = sel.pipe_m * cfg.v("network.heat_loss_w_per_m") / 1e6 if idx else 0.0
    load = p.demand[idx].sum(axis=0) if idx else np.zeros(p.demand.shape[1])
    disp = dispatch(load, cfg, index=p.temp.index, network_loss_mw=loss_mw)
    served = served_by_building(p.demand[idx], disp.hourly) if idx else np.zeros(0)
    econ["connected"] = False
    econ["served_mwh"] = np.nan
    econ["value_usd_yr"] = np.nan
    if idx:
        econ.loc[idx, "connected"] = True
        econ.loc[idx, "served_mwh"] = served
        # cash value to the project (not the weighted objective), net of the building's own connection
        econ.loc[idx, "value_usd_yr"] = cash_value(served, econ.loc[idx], cfg) - prizes.fixed_cost[idx]
    k = kpis(econ.loc[idx], served, disp, sel.pipe_m, cfg)
    return Result(cfg, used, note, sel, econ, disp, k)
