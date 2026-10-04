"""Streamlit app: data-center waste heat → nearby buildings (111 8th Ave, Manhattan).

Run:  streamlit run app.py

Non-technical users pick a priority (preset buttons or a sentence); every assumption stays
visible and adjustable under "Advanced settings" in the sidebar. Presets only set those
widgets — there is no hidden logic.
"""
from __future__ import annotations

import logging

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from src.config import Config
from src.banner import hero_html
from src.mapviz import network_map
from src.scenario import METHODS, Prepared, Result, evaluate, prepare

logging.basicConfig(level=logging.WARNING)
st.set_page_config(page_title="Waste Heat Network", page_icon="🔥", layout="wide",
                   initial_sidebar_state="collapsed")

# Series colors: reference data-viz palette, fixed slot order (validated for CVD).
C_DC, C_TANK, C_BACKUP = "#2a78d6", "#eb6834", "#1baf7a"
C_DEMAND = "#8a8984"  # mid-gray: legible on both light and dark Streamlit themes
BASE = Config.load()
MAP_HEIGHT_PX = 760
PRESETS: dict = BASE.get("presets")

# ---------------------------------------------------------------------------
# Widget registry: (config path, label, kind, step/options). Presets may only override these.
# ---------------------------------------------------------------------------
PERSPECTIVES = {"project": "Everyone combined (project)", "operator": "Data-center owner (sells heat)"}
WIDGETS: dict[str, list[tuple]] = {
    "Goal": [
        ("objective.perspective", "Whose money does the optimiser maximise?", "select", PERSPECTIVES),
        ("objective.heat_discount", "Heat price discount for buildings", "slider", 0.01),
        ("objective.carbon_price_usd_t", "Value of carbon in the decision ($/tCO₂)", "slider", 2.0),
        ("objective.priority_weight", "Extra weight for public housing & schools (×)", "slider", 0.1),
        ("emissions.ll97_enabled", "Count avoided LL97 penalties", "toggle", None),
        ("objective.water_price_usd_m3", "Water + sewer price ($/m³)", "slider", 0.05),
    ],
    "Supply": [
        ("supply.q_src_mw", "Recoverable data-center heat (MW)", "slider", 0.5),
        ("supply.t_source_c", "Source temperature (°C)", "slider", 1.0),
        ("supply.t_supply_c", "Network supply temperature (°C)", "slider", 1.0),
        ("supply.hx_penalty_k", "Building heat-exchanger penalty (K)", "slider", 1.0),
        ("supply.cop_eta", "Heat-pump Carnot efficiency η", "slider", 0.01),
        ("supply.storage_mwh", "Storage tank (MWh)", "slider", 5.0),
        ("supply.outage_hours", "Outage hours per year", "slider", 12.0),
    ],
    "Prices": [
        ("economics.gas_price_usd_mmbtu", "Gas ($/MMBtu)", "slider", 0.5),
        ("economics.steam_price_usd_mmbtu", "Con Ed steam ($/MMBtu)", "slider", 1.0),
        ("economics.electricity_price_usd_kwh", "Electricity ($/kWh)", "slider", 0.01),
    ],
    "Costs & finance": [
        ("economics.pipe_cost_usd_m", "Pipe cost ($/m of trench)", "slider", 250.0),
        ("economics.hp_capex_usd_kw", "Heat-pump cost ($/kW)", "slider", 50.0),
        ("network.building_connection_usd_per_kw", "Building connection ($/kW peak)", "slider", 10.0),
        ("economics.discount_rate", "Discount rate", "slider", 0.005),
    ],
    "Demand": [
        ("data.radius_m", "Search radius (m)", "slider", 50.0),
        ("demand.dhw_multiplier", "Hot-water share multiplier", "slider", 0.05),
        ("demand.space_smoothing_h", "Building thermal mass smoothing (h)", "choice", [0, 6, 12, 24, 48]),
        ("con_ed_pilot.exclude_pilot_demand", "Don't claim Con Ed pilot buildings", "toggle", None),
    ],
}
ALL_WIDGETS = {path: (label, kind, opt) for group in WIDGETS.values() for path, label, kind, opt in group}
DEMAND_PATHS = ("data.radius_m", "demand.dhw_multiplier", "demand.space_smoothing_h", "con_ed_pilot.exclude_pilot_demand")


def default_value(path: str):
    label, kind, _ = ALL_WIDGETS[path]
    v = BASE.v(path)
    return float(v) if kind == "slider" else v


def apply_preset() -> None:
    """Callback: copy a preset's values into every widget (unlisted widgets → base defaults)."""
    key = st.session_state.get("preset")
    if not key:
        return
    preset = PRESETS[key]
    for path in ALL_WIDGETS:
        v = preset["overrides"].get(path, default_value(path))
        st.session_state[path] = float(v) if ALL_WIDGETS[path][1] == "slider" else v
    st.session_state["lock"] = bool(preset.get("lock_base_network", False))


def match_text() -> None:
    """Callback: map a free-text priority to the preset with the most keyword hits (no AI, no cost)."""
    text = st.session_state.get("ask", "").lower()
    scores = {k: sum(kw in text for kw in p.get("keywords", [])) for k, p in PRESETS.items()}
    best = max(scores, key=scores.get)
    if text and scores[best] > 0:
        st.session_state["preset"] = best
        st.session_state["match_msg"] = f"Matched your request to **{PRESETS[best]['icon']} {PRESETS[best]['label']}**."
        apply_preset()
    elif text:
        st.session_state["match_msg"] = "I couldn't match that — try words like *community*, *profit*, *climate*, *worst case*, or pick a button."


if "preset" not in st.session_state:
    st.session_state["preset"] = "base"
    apply_preset()


# ---------------------------------------------------------------------------
# Cached heavy steps
# ---------------------------------------------------------------------------
def demand_overrides(vals: dict) -> dict:
    return {p: vals[p] for p in DEMAND_PATHS}


@st.cache_resource(show_spinner="Loading buildings, weather and streets…")
def cached_prepare(radius: float, dhw: float, smoothing: int, excl_pilot: bool) -> Prepared:
    ov = dict(zip(DEMAND_PATHS, (radius, dhw, smoothing, excl_pilot)))
    return prepare(BASE.with_overrides(ov))


@st.cache_resource(show_spinner="Computing the base-case network…")
def cached_base(radius: float, dhw: float, smoothing: int, excl_pilot: bool, method: str) -> Result:
    """Base-case result with the same demand settings: used for 'vs base' deltas and stress tests."""
    ov = dict(zip(DEMAND_PATHS, (radius, dhw, smoothing, excl_pilot)))
    return evaluate(cached_prepare(radius, dhw, smoothing, excl_pilot), BASE.with_overrides(ov), method)


# ---------------------------------------------------------------------------
# Sidebar: advanced settings (collapsed by default)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Advanced settings")
    st.caption("Presets set these values. Change anything to explore; every value is documented in the "
               "assumptions table at the bottom of the page.")
    method = st.selectbox("Connection-selection method", list(METHODS), format_func=METHODS.get,
                          help="Greedy adds the building with the best value-minus-pipe-cost until none pays. "
                               "Local search then re-routes pipes and tries dropping/adding buildings.")
    st.toggle("Keep the base-case network (stress test)", key="lock",
              help="Best/Worst case: same buildings and pipes as the base case, re-costed under different assumptions.")
    for group, items in WIDGETS.items():
        st.subheader(group)
        for path, label, kind, opt in items:
            node = BASE.get(path)
            helptext = node.get("source") if isinstance(node, dict) else None
            if kind == "slider":
                lo, hi = (float(x) for x in node["range"])
                st.slider(label, lo, hi, step=opt, key=path, help=helptext)
            elif kind == "toggle":
                st.toggle(label, key=path)
            elif kind == "select":
                st.selectbox(label, list(opt), format_func=opt.get, key=path)
            elif kind == "choice":
                st.select_slider(label, opt, key=path, help=helptext)

vals = {path: st.session_state[path] for path in ALL_WIDGETS}
vals["supply.outage_hours"] = int(vals["supply.outage_hours"])
cfg = BASE.with_overrides(vals)
dkey = (vals["data.radius_m"], vals["demand.dhw_multiplier"], int(vals["demand.space_smoothing_h"]),
        bool(vals["con_ed_pilot.exclude_pilot_demand"]))

# ---------------------------------------------------------------------------
# What differs from the base case (computed before anything renders)
# ---------------------------------------------------------------------------
active = st.session_state.get("preset")
changes = []
for path, (label, kind, opt) in ALL_WIDGETS.items():
    base_v, cur_v = default_value(path), vals[path]
    if (float(base_v) != float(cur_v)) if kind == "slider" else (base_v != cur_v):
        fmt = (lambda v: opt.get(v, v)) if kind == "select" else (lambda v: "on" if v is True else "off" if v is False
                                                                  else f"{v:,.0f}" if abs(float(v)) >= 100 else f"{v:g}")
        changes.append(f"{label}: {fmt(base_v)} → **{fmt(cur_v)}**")
if st.session_state.get("lock"):
    changes.insert(0, "Network fixed to the **base-case design** (same buildings and pipes)")
show_delta = bool(changes)

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------
try:
    prep = cached_prepare(*dkey)
    # network to keep fixed in stress tests: base economics on the SAME demand data (indices must match)
    lock_res = cached_base(*dkey, method)
    # reference for the "vs base case" deltas: the true base case (default demand settings too)
    base_res = cached_base(*(default_value(p_) for p_ in DEMAND_PATHS), method)
    res = evaluate(prep, cfg, method, locked=lock_res.selection if st.session_state.get("lock") else None)
except ValueError as exc:   # e.g. supply temperature not above source temperature
    st.error(f"Invalid combination of settings: {exc}")
    st.stop()
k, kb = res.kpi, base_res.kpi


def delta(key: str, scale: float = 1.0, fmt: str = "{:+,.0f}", suffix: str = "") -> str | None:
    if not show_delta:
        return None
    d = (k[key] - kb[key]) * scale
    text = fmt.format(d)
    return None if text.lstrip("+-−").replace("0", "").replace(".", "").replace(",", "") == "" else text + suffix


# ---------------------------------------------------------------------------
# 1. Banner  2. Map (full width)  3. Priority picker  4. Results  5. Detail tabs
# ---------------------------------------------------------------------------
st.html(hero_html(PRESETS[active]["label"] if active else "Custom settings", res.kpi,
                  res.econ.loc[res.econ["connected"], "property_name"].tolist(),
                  getattr(st.context.theme, "type", None) or "dark"))
if res.note:
    st.info(res.note)

fmap = network_map(cfg, prep.graph, res.econ, res.selection.selected, res.selection.tree_edges, prep.node,
                   height_px=MAP_HEIGHT_PX)
with st.container(border=True):
    st_folium(fmap, height=MAP_HEIGHT_PX, use_container_width=True, returned_objects=[])

st.text_input("Describe your priority in your own words", key="ask", on_change=match_text,
              placeholder="e.g. “help the neighbourhood”, “make the most money”, “what if everything goes wrong?”")
if st.session_state.get("match_msg"):
    st.caption(st.session_state["match_msg"])
st.pills("Or pick one", list(PRESETS), key="preset", on_change=apply_preset,
         format_func=lambda k_: f"{PRESETS[k_]['icon']} {PRESETS[k_]['label']}", label_visibility="collapsed")
if active:
    p = PRESETS[active]
    st.info(f"**{p['icon']} {p['label']}** — {p['summary']}")
if changes:
    with st.expander(f"What this changes vs the base case ({len(changes)})", expanded=False):
        st.markdown("\n".join(f"- {c}" for c in changes))

st.subheader("Results" + (" (change vs base case in small print)" if show_delta else ""))
cards = [
    ("Heat delivered", f"{k['served_mwh'] / 1000:,.1f} GWh/yr", delta("served_mwh", 1e-3, "{:+,.1f}", " GWh"),
     f"heat pump COP {k['hp_cop']:.2f} · {k['hp_delivered_mw']:.1f} MW"),
    ("Demand covered", f"{k['coverage']:.0%}", delta("coverage", 100, "{:+.0f}", " pts"),
     f"data center {k['share_dc']:.0%} · tank {k['share_storage']:.0%} · building boilers {k['share_backup']:.0%}"),
    ("Net CO₂ cut", f"{k['co2_net_t']:,.0f} t/yr", delta("co2_net_t", 1, "{:+,.0f}", " t"),
     f"fuel −{k['co2_fuel_avoided_t']:,.0f} t · grid power +{k['co2_grid_added_t']:,.0f} t"),
    ("Net value", f"${k['net_usd'] / 1e6:,.2f}M/yr", delta("net_usd", 1e-6, "{:+,.2f}", "M"),
     f"after ${k['capex_total_usd'] / 1e6:,.2f}M/yr of annualised capital cost"),
    ("Water saved", f"{k['water_m3']:,.0f} m³/yr", delta("water_m3"), "less cooling-tower evaporation"),
    ("Buildings connected", f"{k['buildings']}", delta("buildings"),
     f"{k['priority_buildings']} public housing / school · of {len(res.econ)} candidates"),
    ("Pipe", f"{k['pipe_km']:.2f} km", delta("pipe_km", 1, "{:+.2f}", " km"), "under streets + building services"),
]
NEUTRAL = {"Buildings connected", "Pipe"}   # more is not better or worse in itself
for row in (cards[:4], cards[4:]):
    for col, (label, value, d, sub) in zip(st.columns(4), row):
        with col.container(border=True):
            st.metric(label, value, delta=d, delta_color="off" if label in NEUTRAL else "normal")
            st.caption(sub)


tab_money, tab_hours, tab_bldg, tab_data = st.tabs(["💰 Money", "⏱️ Hour by hour", "🏢 Buildings", "📋 Assumptions & data"])

with tab_money:
    st.subheader("Who gets what (per year)")
    disc = cfg.v("objective.heat_discount")
    c1, c2 = st.columns(2)
    c1.metric("Data-center owner", f"${k['operator_profit_usd'] / 1e6:,.2f}M",
              delta=delta("operator_profit_usd", 1e-6, "{:+,.2f}", "M"))
    c1.caption(f"sells heat at {disc:.0%} below today's price, pays all costs")
    c2.metric("Building owners", f"${k['building_savings_usd'] / 1e6:,.2f}M",
              delta=delta("building_savings_usd", 1e-6, "{:+,.2f}", "M"))
    c2.caption("cheaper heat + avoided LL97 penalties")
    st.subheader("Money breakdown (USD/yr)")
    money = pd.DataFrame({
        "item": ["Fuel no longer bought", "LL97 penalties avoided", "Cooling-tower water saved",
                 "Electricity (heat pump + pumps)", "Pipes (annualised)", "Building connections",
                 "Heat pump", "Storage tank", "Net"],
        "USD/yr": [k["avoided_fuel_usd"], k["avoided_ll97_usd"], k["water_usd"], -k["electricity_usd"],
                   -k["capex_pipes_usd"], -k["capex_connections_usd"], -k["capex_heat_pump_usd"],
                   -k["capex_storage_usd"], k["net_usd"]],
    })
    money["USD/yr"] = money["USD/yr"].map(lambda v: f"{'−' if v < 0 else ''}${abs(v):,.0f}")
    st.dataframe(money, hide_index=True, width="stretch")
    notes = [f"Recovered data-center heat **{k['recovered_heat_mwh']:,.0f} MWh/yr**; heat-pump electricity "
             f"**{k['hp_elec_mwh']:,.0f} MWh/yr**",
             f"Storage needed to ride through the outage hours: **{k['storage_needed_for_outage_mwh']:,.0f} MWh** "
             f"(tank: {cfg.v('supply.storage_mwh'):.0f} MWh)"]
    if cfg.v("objective.carbon_price_usd_t") > 0:
        notes.append(f"Climate benefit at ${cfg.v('objective.carbon_price_usd_t'):.0f}/t: "
                     f"**${k['carbon_value_usd'] / 1e6:,.2f}M/yr** (not in the cash total)")
    sel = res.selection
    if sel.greedy_objective is not None:
        notes.append(f"Local search improved on greedy by **${sel.objective - sel.greedy_objective:,.0f}/yr**")
    st.markdown("\n".join(f"- {n}" for n in notes))


with tab_hours:
    h = res.dispatch.hourly
    st.subheader("Supply vs demand")
    tab_year, tab_week = st.tabs(["Year (daily totals)", "Week (hourly)"])


    def stacked(df: pd.DataFrame, unit: str) -> go.Figure:
        fig = go.Figure()
        for col, name, color in [("dc_direct", "Data center (heat pump)", C_DC),
                                 ("storage_discharge", "Storage tank", C_TANK),
                                 ("backup", "Backup (building boilers)", C_BACKUP)]:
            fig.add_trace(go.Scatter(x=df.index, y=df[col], name=name, stackgroup="s", mode="lines",
                                     line=dict(width=0.5, color=color), fillcolor=color,
                                     hovertemplate=f"%{{y:,.1f}} {unit}<extra>{name}</extra>"))
        fig.add_trace(go.Scatter(x=df.index, y=df["demand"], name="Demand (incl. network loss)", mode="lines",
                                 line=dict(width=2, color=C_DEMAND), hovertemplate=f"%{{y:,.1f}} {unit}<extra>Demand</extra>"))
        fig.add_hline(y=res.dispatch.hp.q_delivered_mw * (24 if unit == "MWh/day" else 1), line_dash="dot",
                      line_color=C_DEMAND, annotation_text="heat-pump capacity", annotation_position="top left")
        fig.update_layout(height=380, hovermode="x unified", margin=dict(l=10, r=10, t=10, b=10),
                          yaxis_title=unit, legend=dict(orientation="h", y=1.08, x=0, traceorder="normal"))
        return fig


    with tab_year:
        daily = h[["dc_direct", "storage_discharge", "backup", "demand"]].resample("D").sum()
        st.plotly_chart(stacked(daily, "MWh/day"), width="stretch", theme="streamlit")
    with tab_week:
        peak_week = int(min(51, h["demand"].to_numpy().argmax() // 168))
        week = st.slider("Week of year", 1, 52, peak_week + 1, help="Defaults to the week with peak demand.")
        wk = h.iloc[(week - 1) * 168: week * 168]
        st.plotly_chart(stacked(wk[["dc_direct", "storage_discharge", "backup", "demand"]], "MW"),
                        width="stretch", theme="streamlit")


with tab_bldg:
    st.subheader("Connected buildings")
    table = res.econ[res.econ["connected"]].copy()
    if table.empty:
        st.warning("No building is worth connecting with these settings (its value is less than the pipe and connection cost).")
    else:
        table["coverage"] = 100 * table["served_mwh"] / table["annual_heat_mwh"]
        num = ["distance_m", "annual_heat_mwh", "peak_kw", "served_mwh", "margin_usd_mwh", "ll97_excess_t", "value_usd_yr"]
        table[num] = table[num].round(0)
        table = table.sort_values("value_usd_yr", ascending=False)[
            ["property_name", "address_1", "primary_property_type", "priority", "main_fuel", "distance_m",
             "annual_heat_mwh", "served_mwh", "coverage", "margin_usd_mwh", "ll97_excess_t", "value_usd_yr", "campus_note"]]
        st.dataframe(table, hide_index=True, width="stretch", column_config={
            "property_name": "Building", "address_1": "Address", "primary_property_type": "Type",
            "priority": st.column_config.CheckboxColumn("Public housing / school"), "main_fuel": "Heated by",
            "distance_m": st.column_config.NumberColumn("Distance (m)", format="localized"),
            "annual_heat_mwh": st.column_config.NumberColumn("Heat need MWh/yr", format="localized"),
            "served_mwh": st.column_config.NumberColumn("Served MWh/yr", format="localized"),
            "coverage": st.column_config.ProgressColumn("Covered", format="%.0f%%", min_value=0, max_value=100),
            "margin_usd_mwh": st.column_config.NumberColumn("Saving $/MWh", format="dollar"),
            "ll97_excess_t": st.column_config.NumberColumn("Over LL97 cap t/yr", format="localized"),
            "value_usd_yr": st.column_config.NumberColumn("Net cash value $/yr", format="dollar",
                                                          help="Fuel + LL97 + water saved − electricity − this building's own connection. Street mains are shared, not allocated."),
            "campus_note": "Data note",
        })


with tab_data:
    def assumptions_table(c: Config) -> pd.DataFrame:
        rows = []

        def walk(node, path):
            if isinstance(node, dict) and "value" in node:
                rows.append({"parameter": path, "value": node["value"], "unit": node.get("unit", ""),
                             "range": node.get("range", ""), "source": node.get("source", "")})
            elif isinstance(node, dict) and path != "presets":
                for key, v in node.items():
                    walk(v, f"{path}.{key}" if path else key)
        walk(c.raw, "")
        df = pd.DataFrame(rows)
        df["value"] = df["value"].astype(str)
        df["range"] = df["range"].astype(str)
        return df


    with st.expander("All assumptions (current values, units, ranges, sources)"):
        st.dataframe(assumptions_table(cfg), hide_index=True, width="stretch")
        st.caption("Lookup tables (hot-water share, non-heating share, LL97 limits by property type) and the preset "
                   "definitions are in config.yaml.")

    with st.expander("Data provenance & quality log"):
        for name, how in prep.qlog.provenance.items():
            badge = {"live": "🟢 LIVE", "cache": "🔵 CACHED (real data)", "sample": "🟠 SAMPLE / FALLBACK"}[how]
            st.markdown(f"- **{name}**: {badge}")
        q = prep.qlog.frame()
        st.markdown(f"**{len(q)} data-quality findings** (campus records, duplicates, outliers…)")
        kinds = st.multiselect("Filter", sorted(q["kind"].unique()), default=[])
        st.dataframe(q[q["kind"].isin(kinds)] if kinds else q, hide_index=True, width="stretch")
        st.download_button("Download candidate buildings (CSV)", res.econ.drop(columns=["bbls"], errors="ignore")
                           .to_csv(index=False), "buildings.csv", "text/csv")
