"""ABC Results Viewer: shows the final A -> B -> C results (outputs/final_integration/abc_results.json).

Reads ONE exported file. It never calls the teammate's optimiser (`prepare` / `evaluate`) and never recomputes a number: every figure on
the page is a field of the JSON. Buildings are keyed by their LL84 property id, never by position in an array.

Reuse of the teammate's Streamlit app (heat-reuse-network, branch heat-usage / streamlit_app):
  * hero banner + skyline  -> vendor/teammate_banner.py (unchanged copy, called through a small kpi adapter)
  * theme, fonts, colours  -> .streamlit/config.toml (unchanged copy), same series colours
  * layout                 -> hero, scenario picker, KPI cards, full-width map, Money / Hour-by-hour / Buildings / Assumptions tabs
Not reused (needs his optimiser or packages that are not installed): his sliders, folium map and Steiner-tree selection.

    streamlit run viewer/abc_viewer.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
DEFAULT_JSON = HERE.parent / "outputs" / "final_integration" / "abc_results.json"
sys.path.insert(0, str(HERE / "vendor"))
try:
    from teammate_banner import hero_html          # unchanged copy of the teammate's src/banner.py
except Exception:                                  # banner is cosmetic: fall back to plain text
    hero_html = None

C_RECOVERED, C_DELIVERED, C_BACKUP, C_DEMAND = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"   # teammate's palette

st.set_page_config(page_title="ABC Results Viewer", page_icon="🔥", layout="wide", initial_sidebar_state="collapsed")


@st.cache_data
def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def usd(v, m=True) -> str:
    if v is None:
        return "n/a"
    s = f"${abs(v) / 1e6:,.2f}M" if m else f"${abs(v):,.0f}"
    return ("−" if v < 0 else "") + s


def num(v, unit="", nd=0) -> str:
    return "n/a" if v is None else f"{v:,.{nd}f}{unit}"


with st.sidebar:
    path = st.text_input("Results file", str(DEFAULT_JSON))
if not Path(path).exists():
    st.error(f"Results file not found: {path}\n\nCreate it with `python -m model.export_abc_results`.")
    st.stop()
D = load(path)
SC = {s["key"]: s for s in D["scenarios"]}

# ------------------------------------------------------------------ scenario picker
st.session_state.setdefault("scenario", D["recommended_scenario"])
labels = {k: ("★ " if k == D["recommended_scenario"] else "") + s["label"] for k, s in SC.items()}
key = st.session_state["scenario"]
S = SC[key]
P, Q = S["primary"], S["secondary"]
conn = [b for b in S["buildings"]]

if hero_html:
    try:
        kpi = dict(served_mwh=P["useful_heat_delivered_MWh_per_year"], co2_net_t=P["net_co2_avoided_t_per_year"],
                   net_usd=P["net_annual_societal_value_usd_per_year"], buildings=len(conn))
        st.html(hero_html(S["status"], kpi, [b["name"] for b in conn], getattr(st.context.theme, "type", None) or "dark"))
    except Exception:
        st.title("Heat reuse network: ABC results")
else:
    st.title("Heat reuse network: ABC results")
st.caption(f"Corrected Models A → B → C · generated {D['generated']} · {D['site']['name']} · schema {D['schema']}")

st.radio("Scenario", list(SC), format_func=lambda k: labels[k], horizontal=False, key="scenario")
key = st.session_state["scenario"]
S = SC[key]
P, Q = S["primary"], S["secondary"]
st.markdown(f"**{S['label']}**: {S['description']}")
for n in S["notes"]:
    st.info(n)

# ------------------------------------------------------------------ primary KPIs
cb = P["community_beneficiaries"]
c = st.columns(5)
c[0].metric("Waste heat recovered", f"{P['waste_heat_recovered_MWh_per_year'] / 1000:,.1f} GWh/yr")
c[0].caption("taken from the data center's cooling loop (not 'savings')")
c[1].metric("Useful heat delivered", f"{P['useful_heat_delivered_MWh_per_year'] / 1000:,.1f} GWh/yr")
c[1].caption("received by connected buildings (recovered heat + compressor input)")
c[2].metric("Net CO₂ avoided", f"{P['net_co2_avoided_t_per_year']:,.0f} t/yr")
c[2].caption("after extra electricity (heat pumps, pumps, source side)")
c[3].metric("Net annual societal value", usd(P["net_annual_societal_value_usd_per_year"]) + "/yr")
c[3].caption("all resource costs; negative = needs public support")
who = f"{cb['households_served']:,.0f} households" if cb["households_served"] else "no households"
c[4].metric("Community beneficiaries", who)
c[4].caption(f"{cb['low_income_households']:,.0f} low-income · {cb['community_facilities']} community facilit"
             f"{'y' if cb['community_facilities'] == 1 else 'ies'}" + (f" ({', '.join(cb['community_facility_names'])})" if cb["community_facility_names"] else ""))

c = st.columns(6)
c[0].metric("COP (seasonal)", num(Q["cop_seasonal"], nd=2))
c[1].metric("LCOH", num(Q["lcoh_usd_per_MWh"], " $/MWh"))
c[2].metric("CAPEX", usd(Q["capex_total_usd"]))
c[3].metric("OPEX", usd(Q["opex_usd_per_year"]) + "/yr")
c[4].metric("Funding gap", usd(Q["funding_gap_usd_per_year"]["minimum_public_support"]) + "/yr")
c[5].metric("Fuel displaced", f"{Q['fuel_displaced_MWh_per_year']['total'] / 1000:,.1f} GWh/yr")
c = st.columns(4)
c[0].metric("Coverage of connected demand", f"{Q['coverage']['recovered_heat_share_of_connected_demand_pct']:.0f}%")
c[1].metric("Backup dependency", f"{Q['backup_reliability']['backup_share_of_served_demand_pct']:.1f}%")
c[2].metric("Unserved heat", f"{Q['backup_reliability']['unserved_heat_MWh']:.0f} MWh")
c[3].metric("Pipeline", f"{S['pipeline']['route_length_m']:,.0f} m")

# ------------------------------------------------------------------ map (keyed by building id)
site = D["site"]
fig = go.Figure()
for pl in S["pipeline"]["polylines"]:
    ll = pl["latlon"]
    fig.add_trace(go.Scattermap(lat=[p[0] for p in ll], lon=[p[1] for p in ll], mode="lines", line=dict(width=4, color=C_DELIVERED),
                                name="pipeline (schematic)", showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scattermap(lat=[site["lat"]], lon=[site["lon"]], mode="markers", marker=dict(size=18, color=C_RECOVERED),
                            name="111 8th Ave (heat source)", text=["111 8th Avenue: heat source"], hoverinfo="text"))
ext = [b for b in conn if b["lat"] is not None and b["id"] != "7536925"]
if ext:
    fig.add_trace(go.Scattermap(
        lat=[b["lat"] for b in ext], lon=[b["lon"] for b in ext], mode="markers",
        marker=dict(size=[max(10, min(34, 8 + (b["heat_from_network_MWh"] or 0) / 700)) for b in ext], color=C_DELIVERED), name="connected buildings",
        text=[f"<b>{b['name']}</b><br>{b['use_type']}<br>{b['heat_from_network_MWh']:,.0f} MWh/yr from network"
              f"<br>{b['households']:,.0f} households · bill change {usd(b['annual_bill_change_usd'], False)}/yr" for b in ext], hoverinfo="text"))
fig.update_layout(map=dict(style="carto-positron", center=dict(lat=site["lat"], lon=site["lon"]), zoom=14.3), height=520,
                  margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, width="stretch")
st.caption(S["pipeline"]["method"])

# ------------------------------------------------------------------ tabs
t_money, t_hours, t_bld, t_all, t_data = st.tabs(["💰 Money", "⏱️ Month by month", "🏢 Buildings", "⚖️ Compare scenarios", "📋 Assumptions & definitions"])

with t_money:
    ob = Q["opex_breakdown_usd_per_year"]
    st.subheader("Net annual societal value (USD/yr)")
    rows = [("Heat bought today (baseline cost of the served heat)", Q["baseline_heat_cost_usd_per_year"]),
            ("Electricity: heat pumps and pumps", -ob["electricity_heat_pumps_pumps"]),
            ("Electricity: extra at the data center (source side)", -ob["electricity_source_side"]),
            ("Backup energy", -ob["backup_energy"]), ("O&M", -ob["om"]), ("CAPEX, annualised", -Q["capex_annualised_usd_per_year"]),
            ("Net annual societal value", P["net_annual_societal_value_usd_per_year"])]
    st.dataframe(pd.DataFrame({"item": [r[0] for r in rows], "USD/yr": [usd(r[1], False) for r in rows]}), hide_index=True, width="stretch")
    st.caption("Recovered heat has no price of its own: the value of the project is the heat it replaces minus everything it costs. LL97 fines, tariffs, "
               "heat-sale payments and subsidies are transfers and are not counted.")
    a, b_, c_ = st.columns(3)
    a.metric("Data center", usd(Q["net_value_to_data_center_usd"]) + "/yr")
    b_.metric("Heat users", usd(Q["net_value_to_heat_users_usd"]) + "/yr")
    c_.metric("Network operator", usd(Q["net_value_to_operator_usd"]) + "/yr")
    if Q["cost_per_tCO2_avoided_usd"]:
        st.metric("Public support per tCO₂ avoided", f"${Q['cost_per_tCO2_avoided_usd']:,.0f}")

with t_hours:
    m = S["monthly"]
    fig = go.Figure()
    mo = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fig.add_bar(x=mo, y=m["heat_recovered_MWh"], name="Waste heat recovered", marker_color=C_RECOVERED)
    fig.add_bar(x=mo, y=m["heat_delivered_MWh"], name="Useful heat delivered", marker_color=C_DELIVERED)
    fig.add_bar(x=mo, y=m["backup_heat_MWh"], name="Backup heat", marker_color=C_BACKUP)
    fig.add_scatter(x=mo, y=m["building_heat_demand_MWh"], name="Connected demand", mode="lines+markers", line=dict(color=C_DEMAND))
    fig.update_layout(barmode="group", yaxis_title="MWh per month", height=380, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch", theme="streamlit")
    st.caption("Monthly totals from the hourly Model A allocation. Hourly series are not exported (a fallback to monthly resolution).")

with t_bld:
    df = pd.DataFrame(S["buildings"]).set_index("id")
    show = df[["name", "role", "use_type", "households", "low_income_households", "community_facility", "heating_system", "backup",
               "heat_from_network_MWh", "backup_heat_MWh", "share_of_served_heat_from_network", "annual_bill_change_usd", "distance_to_source_m"]]
    st.dataframe(show, width="stretch")
    st.caption("Rows are keyed by LL84 property id (`rebuild:<id>` = modelled future building on that campus). Fields the data do not have are shown as empty.")

with t_all:
    rows = []
    for k, s in SC.items():
        p, q = s["primary"], s["secondary"]
        rows.append({"scenario": labels[k], "status": s["status"], "recovered GWh": round(p["waste_heat_recovered_MWh_per_year"] / 1000, 1),
                     "delivered GWh": round(p["useful_heat_delivered_MWh_per_year"] / 1000, 1), "net CO₂ t": p["net_co2_avoided_t_per_year"],
                     "net value $M/yr": round(p["net_annual_societal_value_usd_per_year"] / 1e6, 2),
                     "households": p["community_beneficiaries"]["households_served"], "facilities": p["community_beneficiaries"]["community_facilities"],
                     "CAPEX $M": round(q["capex_total_usd"] / 1e6, 1), "LCOH $/MWh": q["lcoh_usd_per_MWh"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

with t_data:
    st.subheader("Definitions")
    for k, v in D["definitions"].items():
        st.markdown(f"- **{k.replace('_', ' ')}**: {v}")
    st.subheader("Decision rule")
    st.markdown(f"{D['decision_rule']['rule'].capitalize()}. " + "; ".join(f"**{k}** {v}" for k, v in D["decision_rule"]["constraints"].items()))
    st.caption(D["decision_rule"]["weights"])
    st.subheader("Corrections applied")
    st.markdown("\n".join(f"- {c}" for c in D["corrections_applied"]))
    st.subheader("Assumptions of this scenario")
    st.json(S["assumptions"], expanded=False)
    st.subheader("Not available in this viewer")
    st.markdown("- The teammate's sliders and optimiser (his model is not re-run; the results come from Models A/B/C).\n"
                "- Street-graph routing: the pipeline is the grid-rotated minimum spanning tree used for the cost, drawn schematically.\n"
                "- Hourly time series, LL97-penalty and cooling-water lines (not part of the system-resource value).")
