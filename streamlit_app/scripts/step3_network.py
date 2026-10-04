"""Step 3: street graph, snapping, greedy selection, dispatch on the chosen set, plain map."""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT, Config  # noqa: E402
from src.demand import build_demand  # noqa: E402
from src.fetch import fetch_streets  # noqa: E402
from src.mapviz import network_map  # noqa: E402
from src.metrics import (building_economics, fuel_cost_per_mwh_heat, kpis,  # noqa: E402
                         network_heat_cost_per_mwh)
from src.network import (Prizes, build_graph, cost_per_m_yr, greedy_select,  # noqa: E402
                         served_by_building, snap)
from src.supply import HeatPump, dispatch  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    cfg = Config.load()
    b, dem, temp, qlog = build_demand(cfg)
    g = build_graph(fetch_streets(cfg, qlog), cfg)
    print(f"Street graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges, "
          f"{sum(d['length'] for *_, d in g.edges(data=True)) / 1000:.1f} km (segments ≤ {cfg.v('network.max_segment_m'):.0f} m)")
    node, service = snap(g, b["latitude"].to_numpy(), b["longitude"].to_numpy())
    root, root_d = snap(g, np.array([cfg.v("site.lat")]), np.array([cfg.v("site.lon")]))
    print(f"Data center snapped {root_d[0]:.0f} m to street; building service runs median {np.median(service):.0f} m, "
          f"max {service.max():.0f} m")

    hp = HeatPump.from_config(cfg)
    econ = building_economics(b, cfg, hp)
    nh = network_heat_cost_per_mwh(cfg, hp)
    print(f"\nHeat cost per MWh_th: network (HP elec + pumps) ${nh:.1f}; current fuels "
          + ", ".join(f"{k} ${v:.1f}" for k, v in fuel_cost_per_mwh_heat(cfg).items()))
    print(f"Buildings with positive fuel margin: {(econ.margin_usd_mwh > 0).sum()} of {len(econ)}; "
          f"over LL97 cap: {(econ.ll97_excess_t > 0).sum()}")

    cm = cost_per_m_yr(cfg, nh)
    prizes = Prizes.build(econ, dem, node, service, cm, hp.q_delivered_mw, cfg)
    t = time.perf_counter()
    sel = greedy_select(g, root[0], prizes, service, cm)
    print(f"\nGreedy: {len(sel.selected)} buildings in {time.perf_counter() - t:.2f} s; street {sel.street_m:,.0f} m + "
          f"service {sel.service_m:,.0f} m; operating value ${sel.operating_value:,.0f}/yr − network cost "
          f"${sel.network_cost:,.0f}/yr = ${sel.objective:,.0f}/yr (pipe ${cm:.0f}/m/yr)")
    order = pd.DataFrame(sel.log)
    order["name"] = econ.loc[order.building, "property_name"].str.slice(0, 40).to_numpy()
    order["fuel"] = econ.loc[order.building, "main_fuel"].to_numpy()
    order["MWh"] = econ.loc[order.building, "annual_heat_mwh"].round(0).to_numpy()
    print(order[["step", "name", "fuel", "MWh", "street_m_added", "gain_usd_yr"]].round(0).to_string(index=False))

    idx = sel.selected
    loss_mw = sel.pipe_m * cfg.v("network.heat_loss_w_per_m") / 1e6
    disp = dispatch(dem[idx].sum(axis=0), cfg, index=temp.index, network_loss_mw=loss_mw)
    served = served_by_building(dem[idx], disp.hourly)
    k = kpis(econ.loc[idx], served, disp, sel.pipe_m, cfg)
    print("\n=== KPIs after hourly dispatch (20 MWh tank) ===")
    for key, v in k.items():
        print(f"  {key:32s} {v:,.3f}" if abs(v) < 10 else f"  {key:32s} {v:,.0f}")

    for label, ov in {"no LL97": {"emissions.ll97_enabled": False}, "Q_src 10 MW": {"supply.q_src_mw": 10.0},
                      "pipe $1,000/m": {"economics.pipe_cost_usd_m": 1000.0},
                      "pipe $8,000/m": {"economics.pipe_cost_usd_m": 8000.0},
                      "gas $18/MMBtu": {"economics.gas_price_usd_mmbtu": 18.0},
                      "elec $0.15/kWh": {"economics.electricity_price_usd_kwh": 0.15}}.items():
        c = cfg.with_overrides(ov)
        hp2 = HeatPump.from_config(c)
        e2 = building_economics(b, c, hp2)
        cm2 = cost_per_m_yr(c, network_heat_cost_per_mwh(c, hp2))
        s2 = greedy_select(g, root[0], Prizes.build(e2, dem, node, service, cm2, hp2.q_delivered_mw, c), service, cm2)
        print(f"  sensitivity {label:16s}: {len(s2.selected):3d} bldgs, {s2.pipe_m:6,.0f} m pipe, "
              f"objective ${s2.objective:,.0f}/yr")

    econ_out = econ.copy()
    econ_out.loc[idx, "served_mwh"] = served
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    network_map(cfg, g, econ_out, idx, sel.tree_edges, node).save(out / "step3_map.html")
    print(f"\nMap written to {out / 'step3_map.html'}")


if __name__ == "__main__":
    main()
