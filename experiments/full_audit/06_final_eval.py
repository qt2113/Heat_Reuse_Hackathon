"""Stage 6: controlled before/after comparison on ONE fixed set of networks, decomposition of the original result,
recommended external-offtaker network and its break-even conditions."""
from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

import audit_lib as L

OUT = L.HERE
S = L.SITE
EXT_TODAY = ["4978579", "2440154", "1634606", "19906892", "1633052", "8899918", "4040951", "4769672", "2831044"]   # Dream Hotel, 335 W 16 (college), ...
NETS = [([S], "today")] + [([S, e], "today") for e in EXT_TODAY] + [([S, "rebuild:2831044"], "post_rebuild")]
FOCUS = ["4978579", "2440154", "1634606", "19906892", "2831044"]
NETS += [([S, a, b], "today") for a, b in itertools.combinations(FOCUS, 2)]
NETS += [([S, "1634606", "rebuild:2831044"], "post_rebuild"), ([S, "4978579", "rebuild:2831044"], "post_rebuild"),
         ([S, "19906892", "rebuild:2831044"], "post_rebuild"),
         (["1633052", "1634606", "19906892", "4040951", "4769672", "7536925", "8899918"], "today"),                    # original equal-weights pick
         (["1633052", "1634606", "19906892", "4040951", "7536925", "8899918", "rebuild:2831044"], "post_rebuild")]
DATA = {"outlier_years", "pilot_overlap", "oil_fuel"}
COST = {"nycha_dhw_cost", "backup_boiler", "no_storage"}
STEPS = [("S0 original validated ABC", set(), {}, {}),
         ("S1 data-cleaned", DATA, {}, {}),
         ("S3 + corrected costs", DATA | COST, {}, {}),
         ("S4 FULLY AUDITED (evidence-supported reference)", DATA | COST | {"A17_basis"}, {}, {}),
         ("S5a alternative: repeat-project costs", DATA | COST | {"A17_basis"}, {}, {"A05": 17590.0, "A21": 0.15, "network_life": 40}),
         ("S5b advanced (future): warm-water liquid cooling 45 C, A17 = 0", DATA | COST, {"A02": 45.0, "A17": 0.0}, {}),
         ("S5c advanced + repeat-project costs", DATA | COST, {"A02": 45.0, "A17": 0.0}, {"A05": 17590.0, "A21": 0.15, "network_life": 40})]
NAMES = {"7536925": "111 8th", "4978579": "Dream Hotel", "2440154": "335 W 16th (college)", "1634606": "M070 school", "19906892": "363 W 16th hotel",
         "1633052": "M440 school", "8899918": "61 9th Ave", "4040951": "Chelsea Market", "4769672": "London Terrace", "2831044": "Fulton (existing, DHW)",
         "rebuild:2831044": "Rebuilt Fulton"}

ctx = L.base_ctx()
rows = []
for sname, fl, A, P in STEPS:
    c = L.ctx_for(ctx, fl, A=A, P=P)
    for mem, h in NETS:
        r = L.evaluate(mem, h, c, fl)
        r.update(step=sname, label=" + ".join(NAMES.get(m, m) for m in mem), ext_label=" + ".join(NAMES.get(m, m) for m in mem if m != S) or "(internal only)")
        rows.append(r)
d = pd.DataFrame(rows)
d["cost_per_t_co2"] = np.where((d.net_societal_value < 0) & (d.co2_avoided_t > 0), -d.net_societal_value / d.co2_avoided_t, np.nan)
d["support_per_li_household"] = np.where(d.low_income_households_strict > 0, d.minimum_support / d.low_income_households_strict, np.nan)
d.to_csv(OUT / "final_comparison.csv", index=False)


def recommend(g: pd.DataFrame) -> dict:
    """Hard constraints HC0 (>=1 external), HC1-5 (tech_ok), HC6 (CO2 >= 0). Then: least public support; tie-break cost per tCO2."""
    ok = g[(g.n_external >= 1) & g.tech_ok & (g.co2_avoided_t >= 0)]
    best_value = ok.loc[ok.net_societal_value.idxmax()]
    best_ct = ok.loc[ok.cost_per_t_co2.fillna(np.inf).idxmin()] if ok.cost_per_t_co2.notna().any() else best_value
    comm = ok[(ok.low_income_households_strict > 0) | (ok.community_facilities > 0)]
    best_comm = comm.loc[comm.net_societal_value.idxmax()] if len(comm) else None
    li = ok[ok.low_income_households_strict > 0]
    best_li = li.loc[li.support_per_li_household.idxmin()] if len(li) else None
    return dict(n_pass=len(ok), best_value=best_value.label, best_value_net=best_value.net_societal_value, best_value_co2=best_value.co2_avoided_t,
                best_cost_per_t=best_ct.label, best_cost_per_t_value=best_ct.cost_per_t_co2,
                best_community=best_comm.label if best_comm is not None else None,
                best_community_net=best_comm.net_societal_value if best_comm is not None else None,
                best_low_income=best_li.label if best_li is not None else "none passes HC6",
                best_low_income_support_per_hh=best_li.support_per_li_household if best_li is not None else None,
                rebuilt_fulton_co2=float(g[g.label == "111 8th + Rebuilt Fulton"].co2_avoided_t.iloc[0]),
                any_positive_external=bool((g[(g.n_external >= 1)].net_societal_value > 0).any()))


rec = pd.DataFrame([dict(step=s, **recommend(g)) for s, g in d.groupby("step", sort=False)])
rec.to_csv(OUT / "final_recommendation_by_step.csv", index=False)

# decomposition of the originally reported result and of the recommended network
orig = "1633052 + ..."
key = lambda lab: d[d.label == lab].set_index("step").net_societal_value
big = key("M440 school + M070 school + 363 W 16th hotel + Chelsea Market + London Terrace + 111 8th + 61 9th Ave")
m070 = key("111 8th + M070 school")
dec = pd.DataFrame([
    dict(component="decision layer: 13-indicator MCDA picked a 7-building network instead of the cheapest external network (S0 numbers)",
         usd_per_year=big["S0 original validated ABC"] - m070["S0 original validated ABC"]),
    dict(component="data quality / interpretation (outlier years, pilot overlap, oil priced as gas) - on the recommended network",
         usd_per_year=m070["S1 data-cleaned"] - m070["S0 original validated ABC"]),
    dict(component="misapplied / missing costs (NYCHA scope, boilers, uncosted storage) - recommended network",
         usd_per_year=m070["S3 + corrected costs"] - m070["S1 data-cleaned"]),
    dict(component="engineering assumption corrected (A17 on extracted basis) - recommended network",
         usd_per_year=m070["S4 FULLY AUDITED (evidence-supported reference)"] - m070["S3 + corrected costs"]),
    dict(component="REMAINING genuine economic barrier (fully audited recommended network)", usd_per_year=m070["S4 FULLY AUDITED (evidence-supported reference)"]),
    dict(component="memo: same decomposition for the original 7-building network - data", usd_per_year=big["S1 data-cleaned"] - big["S0 original validated ABC"]),
    dict(component="memo: 7-building network - costs", usd_per_year=big["S3 + corrected costs"] - big["S1 data-cleaned"]),
    dict(component="memo: 7-building network - A17 basis", usd_per_year=big["S4 FULLY AUDITED (evidence-supported reference)"] - big["S3 + corrected costs"]),
    dict(component="memo: 7-building network fully audited", usd_per_year=big["S4 FULLY AUDITED (evidence-supported reference)"]),
])
dec.to_csv(OUT / "decomposition.csv", index=False)

# break-even of the recommended network (fully audited)
fl = DATA | COST | {"A17_basis"}
c = L.ctx_for(ctx, fl)
be = []
for lab, mem in (("111 8th + M070 school", [S, "1634606"]), ("111 8th + Dream Hotel", [S, "4978579"]), ("111 8th + Rebuilt Fulton", [S, "rebuild:2831044"])):
    h = "post_rebuild" if any(m.startswith("rebuild") for m in mem) else "today"
    r = L.evaluate(mem, h, c, fl)
    raw = L.MC.evaluate_config(tuple(mem), h, c)
    s_, e, b = raw["summary"], raw["econ"], raw["buildings"]
    v = r["net_societal_value"]
    markup = 1 + c["I"]["contingency"] + c["P"]["A21"]
    k = L.MB.crf(c["P"]["A08"], c["I"]["life"])
    o = c["offt"].set_index("property_id")
    s_oil = b.property_id.map(lambda p: float(o.loc[p, "oil_MWh"]) / max(float(o.loc[p, "gas_MWh"] + o.loc[p, "oil_MWh"]), 1e-9) if p in o.index else 0.0)
    oil_net = float(((b.base_fuel_MWh - b.backup_fuel_MWh) * s_oil * (b.main_fuel == "gas_or_oil") * ~b.rebuilt.astype(bool)).sum())
    el_mwh = (r["electricity_hp_pump"] + r["electricity_source_A17"]) / c["P"]["A07"]
    be.append(dict(network=lab, net_value=v, co2=r["co2_avoided_t"], route_m=s_.route_m,
                   A17_needed=c["A"]["A17"] + v / (s_.Q_DC_used_MWh * c["P"]["A07"]),
                   electricity_price_needed=c["P"]["A07"] + v / el_mwh,
                   pipe_cost_needed=(c["P"]["A05"] + v / (s_.route_m * markup * (k + c["P"]["A22"]))) if s_.route_m else None,
                   oil_price_needed=(L.OIL_PRICE - v / oil_net) if oil_net > 0 else None,
                   carbon_price_needed=(-v / r["co2_avoided_t"]) if r["co2_avoided_t"] > 0 else None,
                   capital_grant_share=min(1.0, -v / r["capex_annualised"]), capex=r["capex_total"],
                   upfront_grant_equivalent=-v / (r["capex_annualised"] / r["capex_total"])))
pd.DataFrame(be).to_csv(OUT / "break_even_recommended.csv", index=False)

pd.set_option("display.width", 260)
pd.set_option("display.max_colwidth", 70)
print(rec.round(0).to_string(index=False))
print(dec.round(0).to_string(index=False))
print(pd.DataFrame(be).round(2).T.to_string())
piv = d.pivot_table(index="label", columns="step", values="net_societal_value").round(0)
print(piv[[s[0] for s in STEPS]].to_string())
print(d.pivot_table(index="label", columns="step", values="co2_avoided_t").round(0)[[s[0] for s in STEPS]].to_string())
