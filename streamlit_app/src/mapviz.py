"""Folium map of the network. Colors: reference data-viz palette slots 1-3 (validated
all-pairs for CVD in light & dark), neutral gray for 'not connected'."""
from __future__ import annotations

import html

import folium
import networkx as nx
from folium.plugins import AntPath
import numpy as np
import pandas as pd

from .config import Config

COLORS = {
    "connected": "#2a78d6",    # slot 1 blue
    "pipe": "#eb6834",         # slot 2 orange
    "pilot": "#1baf7a",        # slot 3 aqua (+ dashed ring = secondary encoding)
    "candidate": "#8a8984",    # neutral gray
    "source": "#0b0b0b",
}


# Esri light-gray canvas: no API key (CARTO basemaps now require one)
TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
TILES_ATTR = "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors"


def _radius(mwh: float) -> float:
    """Marker radius (px) ∝ sqrt(annual heat) so area ∝ demand; min 3 px."""
    return float(max(3.0, np.sqrt(max(mwh, 0.0)) / 6.0))


def _edge_latlon(g: nx.Graph, a, b) -> list[tuple[float, float]]:
    """Edge geometry as (lat, lon) oriented from node a to node b (stored order is arbitrary)."""
    coords = g[a][b]["coords"]
    na = (g.nodes[a]["lon"], g.nodes[a]["lat"])
    if (coords[-1][0] - na[0]) ** 2 + (coords[-1][1] - na[1]) ** 2 < (coords[0][0] - na[0]) ** 2 + (coords[0][1] - na[1]) ** 2:
        coords = coords[::-1]
    return [(la, lo) for lo, la in coords]


def pipe_branches(g: nx.Graph, tree_edges, lat0: float, lon0: float) -> list[list[tuple[float, float]]]:
    """Split the pipe tree into polylines oriented away from the root (the tree node nearest the
    data center), breaking at junctions, so the animation flows data center → buildings."""
    t = nx.Graph()
    t.add_edges_from(tree_edges)
    if t.number_of_nodes() == 0:
        return []
    root = min(t.nodes, key=lambda n: (g.nodes[n]["lat"] - lat0) ** 2 + (g.nodes[n]["lon"] - lon0) ** 2)
    children: dict = {}
    for parent, child in nx.bfs_edges(t, root):
        children.setdefault(parent, []).append(child)
    branches, stack = [], [(root, c) for c in children.get(root, [])]
    while stack:
        a, b = stack.pop()
        line = _edge_latlon(g, a, b)
        while len(children.get(b, [])) == 1:
            a, b = b, children[b][0]
            line += _edge_latlon(g, a, b)[1:]
        branches.append(line)
        stack += [(b, c) for c in children.get(b, [])]
    return branches


def _tip(r: pd.Series) -> str:
    rows = [
        ("", f"<b>{html.escape(str(r['property_name']))}</b>"),
        ("Address", html.escape(str(r.get("address_1", "")))),
        ("Type", html.escape(str(r.get("primary_property_type", "")))),
        ("Heat demand", f"{r['annual_heat_mwh']:,.0f} MWh/yr · peak {r['peak_kw']:,.0f} kW"),
        ("Main fuel", str(r.get("main_fuel", ""))),
        ("Margin", f"${r.get('margin_usd_mwh', np.nan):,.0f}/MWh served"),
    ]
    if "served_mwh" in r and pd.notna(r["served_mwh"]):
        rows.append(("Served", f"{r['served_mwh']:,.0f} MWh/yr"))
    if "value_usd_yr" in r and pd.notna(r["value_usd_yr"]):
        rows.append(("Net value", f"${r['value_usd_yr']:,.0f}/yr"))
    return "<br>".join(f"{k + ': ' if k else ''}{v}" for k, v in rows)


def zoom_for_radius(radius_m: float, lat: float, height_px: int, margin: float = 1.15) -> float:
    """Web-Mercator zoom (quarter steps) at which the search circle just fits the map height
    (st_folium ignores fit_bounds, so the zoom is computed)."""
    m_per_px_z0 = 156_543.03 * np.cos(np.radians(lat))
    z = np.log2(m_per_px_z0 * height_px / (2 * radius_m * margin))
    return float(np.floor(z * 4) / 4)


def network_map(cfg: Config, g: nx.Graph, econ: pd.DataFrame, selected: list[int], tree_edges,
                node_of: np.ndarray, height_px: int = 560) -> folium.Map:
    lat0, lon0 = cfg.v("site.lat"), cfg.v("site.lon")
    # scroll-wheel zoom off: page scrolling over the map must not zoom it (use +/- or pinch)
    m = folium.Map(location=[lat0, lon0], zoom_start=zoom_for_radius(cfg.v("data.radius_m"), lat0, height_px),
                   zoom_snap=0.25, tiles=None, control_scale=True, scrollWheelZoom=False)
    folium.TileLayer(tiles=TILES, attr=TILES_ATTR, name="Esri light gray").add_to(m)
    folium.Circle([lat0, lon0], radius=cfg.v("data.radius_m"), color="#8a8984", weight=1,
                  fill=False, dash_array="4 6").add_to(m)
    sel = set(selected)

    # candidate buildings first (beneath), connected on top
    for i, r in econ.iterrows():
        if i in sel:
            continue
        folium.CircleMarker([r["latitude"], r["longitude"]], radius=_radius(r["annual_heat_mwh"]),
                            color="#fcfcfb", weight=1, fill=True, fill_color=COLORS["candidate"],
                            fill_opacity=0.55, tooltip=_tip(r)).add_to(m)
    # street mains as animated "marching ants" flowing outward from the data center
    for branch in pipe_branches(g, tree_edges, lat0, lon0):
        AntPath(branch, color=COLORS["pipe"], pulse_color="#ffe1d1", weight=5, opacity=0.95,
                delay=900, dash_array=[12, 18], tooltip="Heat main").add_to(m)
    for i in selected:
        r = econ.loc[i]
        n = g.nodes[node_of[i]]
        folium.PolyLine([(r["latitude"], r["longitude"]), (n["lat"], n["lon"])], color=COLORS["pipe"],
                        weight=2, opacity=0.9).add_to(m)
        folium.CircleMarker([r["latitude"], r["longitude"]], radius=_radius(r["annual_heat_mwh"]),
                            color="#fcfcfb", weight=2, fill=True, fill_color=COLORS["connected"],
                            fill_opacity=0.9, tooltip=_tip(r)).add_to(m)

    pilot = cfg.get("con_ed_pilot")
    for rcv in pilot["receivers"]:
        folium.CircleMarker([rcv["lat"], rcv["lon"]], radius=11, color=COLORS["pilot"], weight=3,
                            dash_array="3 3", fill=False, tooltip=f"Con Ed pilot receiver: {rcv['name']}").add_to(m)
    s = pilot["source"]
    folium.Marker([s["lat"], s["lon"]], tooltip=s["name"],
                  icon=folium.DivIcon(html=f'<div style="font:600 11px sans-serif;color:{COLORS["pilot"]};'
                                           f'white-space:nowrap;transform:translate(calc(-100% + 6px),-50%)">Con Ed pilot source ◆</div>')).add_to(m)
    folium.Marker([lat0, lon0], tooltip=cfg.get("site.name"),
                  icon=folium.DivIcon(html='<div style="font:700 12px sans-serif;color:#0b0b0b;white-space:nowrap;'
                                           'transform:translate(-8px,-50%)">★ 111 8th Ave data center</div>')).add_to(m)
    m.get_root().html.add_child(folium.Element(_legend()))
    return m


def _legend() -> str:
    item = '<div style="display:flex;align-items:center;gap:6px;margin:2px 0">{}<span>{}</span></div>'
    dot = '<span style="width:10px;height:10px;border-radius:50%;background:{}"></span>'
    return (
        '<div style="position:fixed;bottom:24px;left:12px;z-index:9999;background:#fcfcfbee;padding:8px 10px;'
        'border-radius:6px;font:12px sans-serif;color:#0b0b0b;box-shadow:0 1px 4px #0003">'
        + item.format(dot.format(COLORS["connected"]), "Connected building (area ∝ demand)")
        + item.format(dot.format(COLORS["candidate"]), "Not connected")
        + item.format(f'<span style="width:14px;height:3px;background:{COLORS["pipe"]}"></span>', "Pipe (street main / service)")
        + item.format(f'<span style="width:10px;height:10px;border-radius:50%;border:2px dashed {COLORS["pilot"]}"></span>',
                      "Con Ed Chelsea pilot (85 10th Ave → Fulton)")
        + "</div>")
