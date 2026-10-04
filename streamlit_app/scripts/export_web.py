"""Export every preset's results to JSON and build the shareable React/D3 page.

    python scripts/export_web.py   →  web/data.json  and  web/index.html (template + data inlined)

The web page cannot run the Python model, so it shows these precomputed preset scenarios.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT, Config  # noqa: E402
from src.fetch import fetch_streets  # noqa: E402
from src.mapviz import pipe_branches  # noqa: E402
from src.network import to_simple_graph  # noqa: E402
from src.scenario import evaluate, prepare  # noqa: E402

WEB = ROOT / "web"
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


def scenario_payload(key: str, preset: dict, base: Config, preps: dict, base_sel_cache: dict) -> dict:
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
                       "ll97": round(float(x.ll97_excess_t))} for i, x in sel.iterrows()],
        "pipes": pipes, "services": services,
        "daily": {"t": [d.strftime("%Y-%m-%d") for d in daily.index], "dc": r(daily.dc_direct), "tank": r(daily.storage_discharge),
                  "backup": r(daily.backup), "demand": r(daily.demand)},
        "week": {"start": week.index[0].strftime("%Y-%m-%d"), "dc": r(week.dc_direct, 2), "tank": r(week.storage_discharge, 2),
                 "backup": r(week.backup, 2), "demand": r(week.demand, 2)},
        "hp_mw": round(res.dispatch.hp.q_delivered_mw, 3),
    }


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
    scenarios = [scenario_payload(k, pr, base, preps, base_sel) for k, pr in base.get("presets").items()]
    p0 = preps[()]
    b = p0.buildings
    pat = "|".join(base.get("objective.priority_name_patterns"))
    prio = (b["property_name"].str.upper().str.contains(pat, regex=True)
            | b["primary_property_type"].isin(base.get("objective.priority_property_types")))
    buildings = [{"n": str(x.property_name), "a": str(x.address_1), "t": str(x.primary_property_type), "f": str(x.main_fuel),
                  "lat": round(float(x.latitude), 5), "lon": round(float(x.longitude), 5), "d": round(float(x.distance_m)),
                  "mwh": round(float(x.annual_heat_mwh)), "pk": round(float(x.peak_kw)), "pr": bool(prio[i])}
                 for i, x in b.iterrows()]
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
    }
    WEB.mkdir(exist_ok=True)
    js = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    (WEB / "data.json").write_text(js)
    template = (WEB / "template.html").read_text()
    page = template.replace("/*__DATA__*/null", js.replace("</", "<\\/"))
    (WEB / "index.html").write_text(page)
    print(f"{len(scenarios)} scenarios, {len(buildings)} buildings, {len(streets)} street edges; "
          f"data {len(js) / 1024:.0f} KB, page {len(page) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
