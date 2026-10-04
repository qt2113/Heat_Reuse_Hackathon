"""Export every preset's results to JSON and build the shareable React/D3 page.

    python scripts/export_web.py   →  web/data.json  and  web/index.html (template + data inlined)

The web page cannot run the Python model, so it shows these precomputed preset scenarios.
"""
from __future__ import annotations

import json
import re
import logging
import sys
from pathlib import Path

import networkx as nx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT, Config  # noqa: E402
from src.fetch import fetch_streets  # noqa: E402
from src.mapviz import pipe_branches  # noqa: E402
from src.metrics import fuel_cost_per_mwh_heat, network_heat_cost_per_mwh, water_usd_per_mwh  # noqa: E402
from src.network import Prizes, cost_per_m_yr, to_simple_graph  # noqa: E402
from src.scenario import evaluate, prepare  # noqa: E402

WEB = ROOT / "web"
STANDALONE_HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                   '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body style="margin:0">\n')
PREP_PREFIXES = ("data.", "demand.", "con_ed_pilot.")
LABELS = {  # human labels for the "what this changes" list
    "objective.perspective": "Whose money is maximised", "objective.heat_discount": "Heat price discount",
    "objective.carbon_price_usd_t": "Value of carbon ($/t)", "objective.priority_weight": "Weight for public housing & schools",
    "emissions.ll97_enabled": "Count LL97 penalties", "supply.q_src_mw": "Recoverable data-center heat (MW)",
    "supply.t_source_c": "Source temperature (°C)", "supply.cop_eta": "Heat-pump efficiency η",
    "supply.hx_penalty_k": "Building heat-exchanger penalty (K)", "supply.outage_hours": "Outage hours / yr",
    "economics.steam_price_usd_mmbtu": "Steam price ($/MMBtu)", "economics.gas_price_usd_mmbtu": "Gas price ($/MMBtu)",
    "economics.electricity_price_usd_kwh": "Electricity ($/kWh)", "economics.pipe_cost_usd_m": "Pipe cost ($/m)",
    "economics.hp_capex_usd_kw": "Heat-pump cost ($/kW)", "economics.discount_rate": "Discount rate",
    "network.building_connection_usd_per_kw": "Building connection ($/kW)",
    "demand.space_smoothing_h": "Thermal-mass smoothing (h)", "con_ed_pilot.exclude_pilot_demand": "Don't claim Con Ed pilot buildings",
}
KPI_KEYS = ["served_mwh", "coverage", "share_dc", "share_storage", "share_backup", "co2_net_t", "co2_fuel_avoided_t",
            "co2_grid_added_t", "net_usd", "capex_total_usd", "water_m3", "buildings", "priority_buildings", "pipe_km",
            "hp_cop", "hp_delivered_mw", "operator_profit_usd", "building_savings_usd", "avoided_fuel_usd",
            "avoided_ll97_usd", "water_usd", "electricity_usd", "capex_pipes_usd", "capex_connections_usd",
            "capex_heat_pump_usd", "capex_storage_usd", "recovered_heat_mwh", "hp_elec_mwh",
            "storage_needed_for_outage_mwh", "carbon_value_usd"]


def fmt(v) -> str:
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, str):
        return {"project": "everyone combined", "operator": "data-center owner"}.get(v, v)
    return f"{v:,.0f}" if abs(float(v)) >= 100 else f"{v:g}"


def r(x, nd=1):
    return [round(float(v), nd) for v in x]


def scenario_payload(key: str, preset: dict, base: Config, preps: dict, base_sel_cache: dict) -> tuple[dict, object]:
    cfg = base.with_overrides(preset["overrides"])
    prep_ov = tuple(sorted((k, v) for k, v in preset["overrides"].items() if k.startswith(PREP_PREFIXES)))
    if prep_ov not in preps:
        preps[prep_ov] = prepare(cfg)
    p = preps[prep_ov]
    locked = None
    if preset.get("lock_base_network"):
        if prep_ov not in base_sel_cache:
            base_sel_cache[prep_ov] = evaluate(p, base.with_overrides(dict(prep_ov))).selection
        locked = base_sel_cache[prep_ov]
    res = evaluate(p, cfg, locked=locked)
    h = res.dispatch.hourly
    daily = h[["dc_direct", "storage_discharge", "backup", "demand"]].resample("D").sum()
    wk = int(min(51, h["demand"].to_numpy().argmax() // 168))
    week = h.iloc[wk * 168:(wk + 1) * 168]
    sel = res.econ[res.econ["connected"]].sort_values("value_usd_yr", ascending=False)
    services = []
    for i in sel.index:
        n = p.graph.nodes[p.node[i]]
        services.append([round(sel.at[i, "latitude"], 5), round(sel.at[i, "longitude"], 5),
                         round(n["lat"], 5), round(n["lon"], 5)])
    pipes = [[[round(a, 5), round(b, 5)] for a, b in line]
             for line in pipe_branches(p.graph, res.selection.tree_edges, base.v("site.lat"), base.v("site.lon"))]
    scores = candidate_scores(p, res, cfg, locked is not None)
    fuel_cost = fuel_cost_per_mwh_heat(cfg)
    pen = cfg.v("emissions.ll97_penalty_usd_t") if cfg.get("emissions.ll97_enabled") else 0.0
    d = cfg.v("objective.heat_discount")
    changes = [f"{LABELS.get(k_, k_)}: {fmt(base.v(k_))} → {fmt(v)}" for k_, v in preset["overrides"].items()]
    if locked is not None:
        changes.insert(0, "Network fixed to the base-case design (same buildings and pipes)")
    return {
        "key": key, "label": preset["label"], "icon": preset["icon"], "summary": preset["summary"],
        "keywords": preset.get("keywords", []), "changes": changes, "locked": locked is not None,
        "kpi": {k_: round(float(res.kpi[k_]), 4) for k_ in KPI_KEYS},
        "heat_discount": cfg.v("objective.heat_discount"), "carbon_price": cfg.v("objective.carbon_price_usd_t"),
        "connected": [{"i": int(i), "mwh": round(float(x.annual_heat_mwh)), "served": round(float(x.served_mwh)),
                       "value": round(float(x.value_usd_yr)), "margin": round(float(x.margin_usd_mwh)),
                       "ll97": round(float(x.ll97_excess_t)),
                       # what the heat delivered is worth at the building's current price, and the owner's saving
                       "worth": round(float(x.served_mwh * x.fuel_cost_usd_mwh)),
                       "save": round(float(x.served_mwh * x.fuel_cost_usd_mwh * d
                                           + pen * min(x.ll97_excess_t, max(x.co2_cut_t_mwh, 0) * x.served_mwh)))}
                      for i, x in sel.iterrows()],
        "scores": scores,
        "prices": {"network": round(network_heat_cost_per_mwh(cfg, res.dispatch.hp), 1),
                   "water_per_mwh": round(water_usd_per_mwh(cfg, res.dispatch.hp), 1),
                   **{f: round(v, 1) for f, v in fuel_cost.items()}},
        "q_src": cfg.v("supply.q_src_mw"), "t_source": cfg.v("supply.t_source_c"),
        "t_sink": cfg.v("supply.t_supply_c") + cfg.v("supply.hx_penalty_k"),
        "perspective": cfg.get("objective.perspective"), "priority_weight": cfg.v("objective.priority_weight"),
        "ll97_on": bool(cfg.get("emissions.ll97_enabled")),
        "pipes": pipes, "services": services,
        "daily": {"t": [d.strftime("%Y-%m-%d") for d in daily.index], "dc": r(daily.dc_direct), "tank": r(daily.storage_discharge),
                  "backup": r(daily.backup), "demand": r(daily.demand)},
        "week": {"start": week.index[0].strftime("%Y-%m-%d"), "dc": r(week.dc_direct, 2), "tank": r(week.storage_discharge, 2),
                 "backup": r(week.backup, 2), "demand": r(week.demand, 2)},
        "hp_mw": round(res.dispatch.hp.q_delivered_mw, 3),
    }, p


# Why a building is not connected (shown on the map and in "How we choose the route")
REASON_CONNECTED, REASON_CHEAPER, REASON_TOO_COSTLY, REASON_SUPPLY, REASON_LOCKED = 0, 1, 2, 3, 4


def candidate_scores(p, res, cfg: Config, locked: bool) -> dict:
    """Stand-alone score of every candidate, exactly as the optimiser values it ($/yr):
    value of the heat it would take if it were the only building connected (capped by the
    heat pump), minus its connection cost, minus the street pipe from the data center.
    Arrays are in candidate order; money in $k/yr."""
    hp = res.dispatch.hp
    cost_m = cost_per_m_yr(cfg, network_heat_cost_per_mwh(cfg, hp))
    prizes = Prizes.build(res.econ, p.demand, p.node, p.service_m, cost_m, hp.q_delivered_mw, cfg)
    n = len(res.econ)
    value = prizes.marginal_values([], np.zeros(p.demand.shape[1]), np.arange(n))
    served_alone = np.minimum(p.demand, hp.q_delivered_mw).sum(axis=1)
    dist = nx.single_source_dijkstra_path_length(p.graph, p.root, weight="length")
    street_m = np.array([dist.get(p.node[i], np.nan) for i in range(n)])
    pipe = np.nan_to_num(street_m * cost_m, nan=1e9)
    fixed = prizes.fixed_cost
    score = value - fixed - pipe
    connected = res.econ["connected"].to_numpy()
    reason = np.where(connected, REASON_CONNECTED,
             np.where(value <= 0, REASON_CHEAPER,
             np.where(score <= 0, REASON_TOO_COSTLY, REASON_LOCKED if locked else REASON_SUPPLY)))
    k = lambda a: [int(round(x / 1000)) for x in a]
    return {"score": k(score), "value": k(value), "pipe": k(pipe), "conn": k(fixed),
            "heat": [int(round(x)) for x in served_alone], "street_m": [int(x) if x == x else -1 for x in street_m],
            "margin": [int(round(x)) for x in prizes.margin], "reason": [int(x) for x in reason]}


def assumptions(c: Config) -> list[dict]:
    rows = []

    def walk(node, path):
        if isinstance(node, dict) and "value" in node:
            rows.append({"p": path, "v": str(node["value"]), "u": node.get("unit", ""),
                         "r": str(node.get("range", "")), "s": node.get("source", "")})
        elif isinstance(node, dict) and path != "presets":
            for k_, v in node.items():
                walk(v, f"{path}.{k_}" if path else k_)
    walk(c.raw, "")
    return rows


def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    base = Config.load()
    preps, base_sel = {}, {}
    raw = [scenario_payload(k, pr, base, preps, base_sel) for k, pr in base.get("presets").items()]
    p0 = preps[()]
    # Scenarios can have slightly different candidate lists (e.g. smoothing lowers peaks, so fewer
    # buildings fail the outlier screen). Build ONE master list keyed by building identity and
    # translate every scenario's indices into it.
    pat = "|".join(base.get("objective.priority_name_patterns"))
    key_of = lambda r: f"{r.property_id}|{r.bbl}|{r.property_name}"
    master, index = [], {}
    for prep in [p0] + [pp for _, pp in raw if pp is not p0]:
        for r in prep.buildings.itertuples():
            k = key_of(r)
            if k not in index:
                index[k] = len(master)
                prio = bool(re.search(pat, str(r.property_name).upper())) or r.primary_property_type in base.get("objective.priority_property_types")
                master.append({"n": str(r.property_name), "a": str(r.address_1), "t": str(r.primary_property_type), "f": str(r.main_fuel),
                               "lat": round(float(r.latitude), 5), "lon": round(float(r.longitude), 5), "d": round(float(r.distance_m)),
                               "mwh": round(float(r.annual_heat_mwh)), "pk": round(float(r.peak_kw)), "pr": prio})
    scenarios = []
    for payload, prep in raw:
        to_master = [index[key_of(r)] for r in prep.buildings.itertuples()]
        for c in payload["connected"]:
            c["i"] = to_master[c["i"]]
        sc = payload["scores"]
        for name, arr in list(sc.items()):
            full = [None] * len(master)
            for local, v in enumerate(arr):
                full[to_master[local]] = v
            if name == "reason":   # 5 = not a candidate in this scenario (screened out as an outlier)
                full = [5 if v is None else v for v in full]
            sc[name] = full
        scenarios.append(payload)
    buildings = master
    g = to_simple_graph(fetch_streets(base, p0.qlog))
    streets = [[[round(lo, 5), round(la, 5)] for lo, la in d["coords"]] for *_, d in g.edges(data=True)]
    q = p0.qlog.frame()
    data = {
        "site": {"lat": base.v("site.lat"), "lon": base.v("site.lon"), "radius_m": base.v("data.radius_m"),
                 "name": base.get("site.name")},
        "pilot": base.get("con_ed_pilot"),
        "buildings": buildings, "streets": streets, "scenarios": scenarios,
        "assumptions": assumptions(base),
        "provenance": p0.qlog.provenance,
        "quality": q["kind"].value_counts().to_dict(),
        "generated": "2026-10-03",
        "consts": {"car_t": base.v("communication.car_tco2_per_year"), "pool_m3": base.v("communication.olympic_pool_m3"),
                   "residential_types": base.get("communication.residential_types")},
    }
    WEB.mkdir(exist_ok=True)
    js = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    (WEB / "data.json").write_text(js)
    template = (WEB / "template.html").read_text()
    page = template.replace("/*__DATA__*/null", js.replace("</", "<\\/"))
    (WEB / "index.html").write_text(page)          # what is published as the claude.ai artifact
    # standalone copy for hosting anywhere (GitHub Pages, Netlify, opened from disk): the artifact
    # viewer normally adds the document skeleton, so add it here
    (WEB / "standalone.html").write_text(STANDALONE_HEAD + page + "\n</body>\n</html>\n")
    print(f"{len(scenarios)} scenarios, {len(buildings)} buildings, {len(streets)} street edges; "
          f"data {len(js) / 1024:.0f} KB, page {len(page) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
