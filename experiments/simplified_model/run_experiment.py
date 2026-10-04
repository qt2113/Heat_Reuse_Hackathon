"""Run the simplified-model experiment end to end and write experiments/simplified_model/outputs/.

    cd experiments/simplified_model && python run_experiment.py

Stages: screening -> configuration ladder -> incremental analysis -> stakeholders -> sensitivity ->
break-even -> controlled comparison with Models A/B/C -> ABC indicator audit -> temporal-accuracy check ->
governance table -> validation tests -> isolation check (nothing outside this folder changed).
Models A/B/C are imported read-only for the controlled comparison; none of their run_* entry points is called.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time

import numpy as np
import pandas as pd

import smodel as S

OUT = S.HERE / "outputs"
SITE = "7536925"
REBUILD_F, REBUILD_E = "rebuild:2831044", "rebuild:4473909"
ABC_LARGE_TODAY = ["1633052", "1634606", "19906892", "4040951", "4769672", SITE, "8899918"]
ABC_LARGE_POST = ["1633052", "1634606", "19906892", "4040951", SITE, "8899918", REBUILD_F]
ABC_PHASE1 = [SITE, "19906892"]
ABC_PHASE2 = [SITE, "19906892", REBUILD_F]
ABC_S2 = [SITE, "4040951", "19906892", "4978579", "1633052", "8899918"]


def protected_hashes() -> dict:
    h = {}
    for p in sorted(S.ROOT.rglob("*")):
        rel = p.relative_to(S.ROOT).as_posix()
        if p.is_file() and not rel.startswith((".git/", "experiments/")) and "__pycache__" not in rel:
            h[rel] = hashlib.md5(p.read_bytes()).hexdigest()
    return h


def sv(r: dict, P: dict) -> float:
    """Societal value used only to rank additions: net system value + CO2 valued at the LL97 benchmark."""
    return r["econ"]["net_value"] + P["carbon_benchmark_per_t"] * r["econ"]["co2_avoided"]


# ------------------------------------------------------------------ 1 screening (every LL84 building, standalone)
def screening(P: dict) -> pd.DataFrame:
    o = S.data()["offt"]
    base = S.evaluate([SITE], P)
    e0, s0 = base["econ"], base["sim"]
    rows = []
    for pid in o.property_id:
        if pid == SITE:
            continue
        r = o.loc[pid]
        row = dict(property_id=pid, name=r.property_name, use_type=r.use_type, main_fuel=r.main_fuel, heating=r.sh_system,
                   dist_m=r.dist_m, n_years=r.n_years, heat_fuel_MWh=r.heat_fuel_MWh, units=r.units_res, nycha=r.is_nycha,
                   dac_tract=r.dac, community=r.community)
        if not (r.heat_fuel_MWh > 0) or pd.isna(r.lat):
            row.update(status="excluded", reason="no LL84 heating fuel or no coordinates")
            rows.append(row)
            continue
        ev = S.evaluate([SITE, pid], P)
        e, s = ev["econ"], ev["sim"]
        dQ = s["Q_del"] - s0["Q_del"]
        b = e["b"].set_index("pid").loc[pid]
        price = S.data()["price"]["steam"] if r.main_fuel == "steam" else S.data()["price"]["gas"]
        # energy margin per MWh delivered: displaced fuel value - added electricity (HP + pumps + source side)
        e_per = (b.E_HP + b.E_pump + b.E_src) / b.Q_del if b.Q_del > 0 else np.nan
        row.update(status="evaluated", reason="", servable_MWh=float(b.D_dhw + b.D_sh_served), dQ_delivered_MWh=dQ,
                   route_m=s["route_m"], d_net_value=e["net_value"] - e0["net_value"], d_co2=e["co2_avoided"] - e0["co2_avoided"],
                   d_capex=e["capex_total"] - e0["capex_total"], d_li=e["li_households"] - e0["li_households"],
                   energy_margin_per_MWh=price / b.eta - e_per * P["elec_price"],
                   d_societal_value=sv(ev, P) - sv(base, P), temperature_class="DHW only (steam radiators)" if b.sh_class == "none" else b.sh_class)
        row["abatement_cost_per_t"] = -row["d_net_value"] / row["d_co2"] if row["d_co2"] > 0 else np.nan
        rows.append(row)
    d = pd.DataFrame(rows)
    d["data_quality_flag"] = np.where(d.n_years < 2, "single LL84 year", "")
    return d.sort_values("d_societal_value", ascending=False, na_position="last")


def greedy(start: list, pool: list, P: dict, steps: int) -> list[dict]:
    cur, path = list(start), []
    cur_r = S.evaluate(cur, P)
    for _ in range(steps):
        best = None
        for pid in pool:
            if pid in cur:
                continue
            r = S.evaluate(cur + [pid], P)
            if not r["feasible"]:
                continue
            gain = sv(r, P) - sv(cur_r, P)
            if best is None or gain > best[0]:
                best = (gain, pid, r)
        if best is None:
            break
        cur.append(best[1])
        path.append(dict(added=best[1], d_societal_value=best[0], members=list(cur)))
        cur_r = best[2]
    return path


# ------------------------------------------------------------------ 3 incremental analysis
def incremental(rows: pd.DataFrame, ladder: list[tuple[str, str]]) -> pd.DataFrame:
    r = rows.set_index("config")
    out = []
    for frm, to in ladder:
        a, b = r.loc[frm], r.loc[to]
        d = {k: b[k] - a[k] for k in ("I1", "I3", "I4", "I5", "I7", "I8", "net_value", "co2_avoided", "capex_total", "heat_delivered_MWh")}
        out.append(dict(step=f"{frm} -> {to}", from_config=frm, to_config=to, **{f"d_{k}": v for k, v in d.items()},
                        incr_abatement_cost_per_t=(-d["net_value"] / d["co2_avoided"]) if d["co2_avoided"] > 0 else np.nan,
                        incr_cost_per_MWh_delivered=(-d["net_value"] / d["heat_delivered_MWh"]) if d["heat_delivered_MWh"] > 0 else np.nan,
                        incr_cost_per_li_household=(-d["net_value"] / d["I7"]) if d["I7"] > 0 else np.nan,
                        co2_increases=d["co2_avoided"] < 0, both_feasible=bool(a.feasible and b.feasible)))
    return pd.DataFrame(out)


# ------------------------------------------------------------------ 5 sensitivity
SENS = [  # label, overrides, register levels, family
    ("pipe cost low (A05 0.6x pilot)", {}, {"A05": "low"}, "pipe"),
    ("pipe cost high (A05 1.3x pilot)", {}, {"A05": "high"}, "pipe"),
    ("route facade-to-facade", {"route_mode": "facade"}, {}, "pipe"),
    ("building interface capex x0.5", {"bld_capex_scale": 0.5, "nycha_apt_capex_scale": 0.5}, {}, "retrofit"),
    ("building interface capex x1.5", {"bld_capex_scale": 1.5, "nycha_apt_capex_scale": 1.5}, {}, "retrofit"),
    ("hydronic retrofit to 60 C (A18 low)", {}, {"A18": "low"}, "retrofit"),
    ("hydronic at 80 C (A18 high)", {}, {"A18": "high"}, "retrofit"),
    ("A17 = 0 (no source-side electricity)", {"source_elec_per_MWh_src": 0.0}, {}, "A17"),
    ("A17 = 0.367 (pilot, per MWh extracted)", {"source_elec_per_MWh_src": 0.367}, {}, "A17"),
    ("electricity $182/MWh (A07 low)", {}, {"A07": "low"}, "prices"),
    ("electricity $282/MWh (A07 high)", {}, {"A07": "high"}, "prices"),
    ("gas + steam prices x0.7", {"price_scale_gas": 0.7, "price_scale_steam": 0.7}, {}, "prices"),
    ("gas + steam prices x1.3", {"price_scale_gas": 1.3, "price_scale_steam": 1.3}, {}, "prices"),
    ("source 27 C (A02 low)", {}, {"A02": "low"}, "source temperature"),
    ("source 35 C (A02 high)", {}, {"A02": "high"}, "source temperature"),
    ("source 45 C (direct liquid cooling, E04; indicative)", {"loop_temp_C": 45.0}, {}, "source temperature"),
    ("DC share 0.5 (A01 low)", {}, {"A01": "low"}, "supply"),
    ("DC share 0.9 (A01 high)", {}, {"A01": "high"}, "supply"),
    ("office/commercial base share low (A20 0.05)", {}, {"A20": "low"}, "demand"),
    ("office/commercial base share high (A20 0.3)", {}, {"A20": "high"}, "demand"),
    ("grid EF -50% (illustrative post-2030)", {"grid_ef_scale": 0.5}, {}, "carbon"),
    ("discount 3% (A08 low)", {}, {"A08": "low"}, "finance"),
    ("discount 7% (A08 high)", {}, {"A08": "high"}, "finance"),
    ("soft costs 15% (A21 low)", {}, {"A21": "low"}, "finance"),
    ("no distribution loss", {"dist_loss_per_km": 0.0}, {}, "physics"),
    ("HP sized to 100% of space-heat peak", {"hp_frac_sh": 1.0}, {}, "physics"),
]


def sensitivity(configs: dict) -> pd.DataFrame:
    rows = []
    for lab, ov, lv, fam in [("base", {}, {}, "base")] + SENS:
        P = S.params(ov, lv)
        for cname, mem in configs.items():
            if not mem:
                continue
            r = S.evaluate(mem, P)
            row = S.summary_row(cname, r)
            rows.append(dict(sensitivity=lab, family=fam, config=cname, net_value=row["net_value"], co2_avoided=row["co2_avoided"],
                             heat_delivered_MWh=row["heat_delivered_MWh"], capex_total=row["capex_total"], I6=row["I6"],
                             abatement_cost_per_t=row["abatement_cost_per_t"], feasible=row["feasible"]))
    d = pd.DataFrame(rows)
    base = d[d.sensitivity == "base"].set_index("config")
    d["d_net_vs_base"] = d.net_value - d.config.map(base.net_value)
    d["d_co2_vs_base"] = d.co2_avoided - d.config.map(base.co2_avoided)
    d["net_positive"] = d.net_value > 0
    return d


def breakeven(configs: dict) -> pd.DataFrame:
    """Value of one lever at which net system value = 0 (others at base). Linear levers solved exactly."""
    rows = []
    P0 = S.params()
    for cname, mem in configs.items():
        if not mem:
            continue
        r = S.evaluate(mem, P0)
        e, s = r["econ"], r["sim"]
        net, k, mk = e["net_value"], e["crf"], e["markup"]
        out = dict(config=cname, net_value=net, co2_avoided=e["co2_avoided"])
        # A17 (linear: E_src = A17 * Q_src); also the A17 at which CO2 avoided = 0
        out["A17_for_net_zero"] = P0["source_elec_per_MWh_src"] + net / (s["Q_src"] * P0["elec_price"]) if s["Q_src"] > 0 else np.nan
        ef = S.data()["ef"]["grid"]
        out["A17_for_co2_zero"] = P0["source_elec_per_MWh_src"] + e["co2_avoided"] / (s["Q_src"] * ef) if s["Q_src"] > 0 else np.nan
        # pipe cost per route-m (linear)
        out["pipe_cost_per_m_for_net_zero"] = (P0["pipe_cost_per_route_m"] + net / (s["route_m"] * mk * k * (1 + P0["network_om_frac"] / k))) if s["route_m"] > 0 else np.nan
        out["carbon_price_for_net_zero"] = -net / e["co2_avoided"] if e["co2_avoided"] > 0 and net < 0 else np.nan
        # electricity price (bisection: dispatch order depends on it)
        f = lambda p: S.evaluate(mem, dict(P0, elec_price=p))["econ"]["net_value"]
        lo, hi = 0.0, P0["elec_price"]
        if f(lo) > 0 > f(hi):
            for _ in range(40):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
            out["elec_price_for_net_zero"] = (lo + hi) / 2
        else:
            out["elec_price_for_net_zero"] = np.nan if f(lo) <= 0 else P0["elec_price"]
        # combined favourable case: A17 = 0, facade route, pipe A05 low, building capex x0.5
        fav = S.evaluate(mem, S.params({"source_elec_per_MWh_src": 0.0, "route_mode": "facade", "bld_capex_scale": 0.5,
                                        "nycha_apt_capex_scale": 0.5}, {"A05": "low"}))
        out["net_value_all_favourable"] = fav["econ"]["net_value"]
        out["co2_avoided_all_favourable"] = fav["econ"]["co2_avoided"]
        rows.append(out)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 7 controlled comparison with Models A/B/C
def controlled_comparison(P: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    sys.path.insert(0, str(S.ROOT))
    from model import model_a as MA                      # read-only imports; nothing is written
    from model import model_b as MB
    from model.run_model_c import build_ctx
    ctx = build_ctx()
    stored = pd.read_csv(S.ROOT / "outputs" / "model_c" / "c_configurations.csv").set_index("config_id")
    cases = {"C1 internal": ("today", [SITE]), "ABC phase 1 (111 8th + 363 W 16th hotel)": ("today", ABC_PHASE1),
             "ABC S2 commercial block": ("today", ABC_S2), "ABC equal-weights, today (7 bldgs)": ("today", ABC_LARGE_TODAY),
             "Existing Fulton + internal": ("today", [SITE, "2831044"]), "ABC phase 2 (post-rebuild)": ("post_rebuild", ABC_PHASE2)}
    Peq = S.abc_equivalent(P)
    rows, deco = [], []
    for name, (hz, mem) in cases.items():
        cid = f"{hz}|" + "+".join(sorted(m.replace("rebuild:", "R") for m in mem))
        st = stored.loc[cid] if cid in stored.index else None
        # Model A hourly (merit dispatch) with and without the 2 h tank, priced by Model B
        res = {}
        for tank in (2, 0):
            existing = [m for m in mem if not m.startswith("rebuild:")]
            rb = [m for m in mem if m.startswith("rebuild:")]
            scen = {"members": existing}
            if rb:
                r0 = ctx["cfg"]["scenarios"]["S3R"]["rebuild"]
                scen["rebuild"] = dict(r0, sites=[s for s in r0["sites"] if f"rebuild:{s['anchor_property_id']}" in rb])
            fuel = ctx["offt"].set_index("property_id").main_fuel
            dv = {m: ctx["dv"][fuel.get(m, "gas_or_oil")] for m in existing}
            dv.update({m: ctx["dv"]["new_electric"] for m in rb})
            spec = MA.RunSpec(cid, cid, 0.75, tank)
            a = MA.simulate(spec, ctx["cfg"], ctx["bundle"], ctx["A"], scen_override=scen, policy="merit", dispatch_value=dv)
            srs = pd.Series(a["summary"])
            run = pd.Series(dict(run_id=cid, scenario=cid, hp_frac=0.75, tank_hours=tank, assumption_set="base", internal=(mem == [SITE])))
            ev = MB.evaluate(run, srs, a["buildings"], ctx["P"], ctx["I"])["econ"]
            res[tank] = dict(Q=srs.Q_network_MWh, net=ev["annual_savings"], co2=ev["co2_avoided"], capex=ev["capex_total"], li=ev["low_income_households"])
        seq = S.evaluate(mem, Peq)
        sb = S.evaluate(mem, P)
        for lab, Q, net, co2, capex, li in [
                ("ABC stored (Model C output)", st.Q_network_MWh if st is not None else np.nan, st.E_val if st is not None else np.nan,
                 st.N_co2 if st is not None else np.nan, st.capex_total if st is not None else np.nan, st.S_li if st is not None else np.nan),
                ("Model A hourly + B, tank 2 h (rerun)", res[2]["Q"], res[2]["net"], res[2]["co2"], res[2]["capex"], res[2]["li"]),
                ("Model A hourly + B, no storage (rerun)", res[0]["Q"], res[0]["net"], res[0]["co2"], res[0]["capex"], res[0]["li"]),
                ("Model S, ABC-equivalent settings", seq["sim"]["Q_del"], seq["econ"]["net_value"], seq["econ"]["co2_avoided"], seq["econ"]["capex_total"], seq["econ"]["li_households"]),
                ("Model S, review base case", sb["sim"]["Q_del"], sb["econ"]["net_value"], sb["econ"]["co2_avoided"], sb["econ"]["capex_total"], sb["econ"]["li_households"])]:
            rows.append(dict(case=name, members="|".join(mem), model=lab, heat_delivered_MWh=Q, net_value=net, co2_avoided=co2, capex_total=capex, low_income_households=li))
        # decomposition: ABC stored -> S base, one cause at a time
        steps = [("storage (2 h tank -> none; temporal model)", None),
                 ("Fulton apartments already on the Con Ed pilot excluded", dict(exclude_pilot_served=True)),
                 ("low-income = NYCHA only (DAC-tract market-rate units removed)", dict(li_definition="strict")),
                 ("distribution loss 1%/km added", dict(dist_loss_per_km=P["dist_loss_per_km"]))]
        prev = dict(Q=res[2]["Q"], net=res[2]["net"], co2=res[2]["co2"], li=res[2]["li"])
        cur = dict(Peq)
        for lab, ch in steps:
            if ch is None:
                r_ = seq
            else:
                cur.update(ch)
                r_ = S.evaluate(mem, cur)
            now = dict(Q=r_["sim"]["Q_del"], net=r_["econ"]["net_value"], co2=r_["econ"]["co2_avoided"], li=r_["econ"]["li_households"])
            deco.append(dict(case=name, cause=lab, d_heat_MWh=now["Q"] - prev["Q"], d_net_value=now["net"] - prev["net"],
                             d_co2=now["co2"] - prev["co2"], d_li=now["li"] - prev["li"]))
            prev = now
    return pd.DataFrame(rows), pd.DataFrame(deco)


# ------------------------------------------------------------------ 8 audit of the 13 ABC indicators
def abc_indicator_audit() -> tuple[pd.DataFrame, dict]:
    c = pd.read_csv(S.ROOT / "outputs" / "model_c" / "c_configurations.csv")
    ids = ["T_cov", "T_lf", "T_bk", "E_lcoh", "E_val", "E_fund", "N_co2", "N_erf", "N_gas", "S_li", "S_aff", "S_eq", "S_fac"]
    out = {}
    for hz, g in c.groupby("horizon"):
        g = g[g.n_buildings > 0]
        cm = g[ids + ["Q_network_MWh", "capex_total"]].corr(method="spearman")
        pairs = [(a, b, cm.loc[a, b]) for i, a in enumerate(ids) for b in ids[i + 1:] if abs(cm.loc[a, b]) >= 0.9]
        out[hz] = dict(
            high_corr_pairs=[f"{a}~{b} ({v:+.2f})" for a, b, v in pairs],
            constant_indicators=[i for i in ids if g[i].nunique() <= 1],
            spearman_overall_vs_heat=float(g[["overall_equal_weights", "Q_network_MWh"]].corr(method="spearman").iloc[0, 1]),
            spearman_overall_vs_net_value=float(g[["overall_equal_weights", "E_val"]].corr(method="spearman").iloc[0, 1]),
            spearman_overall_vs_n_buildings=float(g[["overall_equal_weights", "n_buildings"]].corr(method="spearman").iloc[0, 1]),
            top_config_by_score=g.sort_values("overall_equal_weights").iloc[-1][["config_id", "E_val", "N_co2", "Q_network_MWh"]].to_dict(),
            share_with_negative_net_value=float((g.E_val < 0).mean()),
        )
    corr_today = c[(c.horizon == "today") & (c.n_buildings > 0)][ids].corr(method="spearman")
    return corr_today, out


# ------------------------------------------------------------------ 9 temporal accuracy
def temporal_accuracy(configs: dict, P: dict) -> pd.DataFrame:
    rows = []
    for cname, mem in configs.items():
        if not mem:
            continue
        ref = S.evaluate(mem, dict(P, bin_width_C=1.0))
        for wdt, lab in ((0.5, "0.5 C bins"), (1.0, "1 C bins (used)"), (2.0, "2 C bins"), (5.0, "5 C bins"), (100.0, "monthly averages (12 rows)")):
            r = S.evaluate(mem, dict(P, bin_width_C=wdt))
            rows.append(dict(config=cname, temporal_model=lab, rows=len(S.bins(P["availability"], wdt)),
                             heat_delivered_MWh=r["sim"]["Q_del"], backup_MWh=r["sim"]["Q_backup"], net_value=r["econ"]["net_value"],
                             err_heat_pct=100 * (r["sim"]["Q_del"] / ref["sim"]["Q_del"] - 1),
                             err_backup_pct=100 * (r["sim"]["Q_backup"] / ref["sim"]["Q_backup"] - 1) if ref["sim"]["Q_backup"] > 0 else 0.0))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 10 governance (qualitative, unscored)
GOVERNANCE = [
    dict(config="C1 Internal reuse", owner_operator="111 8th Ave owner (Google) with tenant cooling plants", revenue_model="none (internal cost saving)",
         capex_bearer="building owner", key_risks="tenant loop temperature and source-side electricity (A17) unverified; office hot-water share (A20) uncertain",
         contract_risk="low: single owner, no street works", stranded_asset_risk="low", public_acceptance="neutral (invisible)", delivery_risk="Low",
         evidence="LL84 metered; pilot COP; A17/A20 assumptions"),
    dict(config="C2 Internal + 1 community offtaker", owner_operator="utility (Con Ed UTEN model) or building owner via a heat agreement",
         revenue_model="fence price to DC + cost-reflective tariff; subsidy to keep the community user no worse off",
         capex_bearer="operator (pipe, interface) + grant", key_risks="DC heat contracts usually <=10 yr (E26) vs 25-yr pipe life; small load carries full fixed costs",
         contract_risk="medium: two parties, street-opening permit", stranded_asset_risk="medium", public_acceptance="positive if bills fall", delivery_risk="Medium",
         evidence="pilot tariff/fence (S13); E26"),
    dict(config="C3 Small network (2-4 offtakers)", owner_operator="regulated utility (UTEN) or ESCO", revenue_model="usage tariff + connection charge; ratepayer recovery (pilot +0.06%)",
         capex_bearer="utility rate base / grants", key_risks="gas-heated users lose money per MWh at current prices; multiple building interfaces; street works",
         contract_risk="medium-high", stranded_asset_risk="medium", public_acceptance="mixed: street works, cost recovery from ratepayers", delivery_risk="Medium-High",
         evidence="pilot cost structure (S13)"),
    dict(config="R2 Internal + rebuilt Fulton (heat-ready rebuild)", owner_operator="PACT developer builds low-temperature plant; utility owns loop",
         revenue_model="heat tariff benchmarked to the all-electric ASHP alternative", capex_bearer="developer (in-building) + utility (loop)",
         key_risks="only beneficial if A17 is low (DC can deliver 30 C heat without extra chiller energy); rebuild timing (A15 2028-2030)",
         contract_risk="medium: design window must be used before plant rooms are fixed", stranded_asset_risk="low (new 60-yr buildings)",
         public_acceptance="high if tied to resident benefits", delivery_risk="Medium", evidence="FEC FAQ (S18); A17 pilot anchor"),
    dict(config="C4 Large network (ABC equal-weights)", owner_operator="utility", revenue_model="tariffs + large public funding need",
         capex_bearer="ratepayers / public", key_risks="$ millions/yr net cost; long route through dense streets; many gas users with negative energy margin",
         contract_risk="high", stranded_asset_risk="medium-high", public_acceptance="uncertain (cost recovery)", delivery_risk="High", evidence="Model C outputs"),
]


# ------------------------------------------------------------------ main
def main() -> None:
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    before = protected_hashes()
    P = S.params()

    scr = screening(P)
    scr.to_csv(OUT / "s_screening.csv", index=False)
    ev = scr[scr.status == "evaluated"]
    pool = list(ev.head(40).property_id)
    community = ev[(ev.community | ev.nycha)]
    best_comm = community.iloc[0].property_id
    g_today = greedy([SITE], pool, P, 4)
    g_post = greedy([SITE, REBUILD_F], pool + [REBUILD_E], P, 3)
    small = g_today[2]["members"] if len(g_today) >= 3 else g_today[-1]["members"]       # 3 external offtakers

    configs = {
        "C0 Today (no network)": [],
        "C1 Internal reuse": [SITE],
        "C2 Internal + 1 community offtaker": [SITE, best_comm],
        "C3 Small network (2-4 offtakers)": small,
        "C4 Large network (ABC equal-weights, today)": ABC_LARGE_TODAY,
        "R2 Internal + rebuilt Fulton (2029+)": [SITE, REBUILD_F],
        "R3 Internal + full rebuild campus (2029+)": [SITE, REBUILD_F, REBUILD_E],
        "R4 Large network (ABC equal-weights, post-rebuild)": ABC_LARGE_POST,
        "ref ABC phase 1 (111 8th + 363 W 16th hotel)": ABC_PHASE1,
    }
    results = {k: S.evaluate(v, P) for k, v in configs.items()}
    rows = pd.DataFrame([S.summary_row(k, r) for k, r in results.items()])
    rows.to_csv(OUT / "s_configurations.csv", index=False)
    pd.concat([r["sim"]["monthly"].assign(config=k) for k, r in results.items() if r["sim"]["streams"]]).to_csv(OUT / "s_monthly.csv", index=False)
    pd.DataFrame([dict(horizon=h, step=i + 1, added=p["added"], name=S.data()["offt"].property_name.get(p["added"], p["added"]),
                       d_societal_value=p["d_societal_value"], members="|".join(p["members"]))
                  for h, g in (("today", g_today), ("post_rebuild", g_post)) for i, p in enumerate(g)]).to_csv(OUT / "s_greedy_path.csv", index=False)

    inc = incremental(rows, [("C0 Today (no network)", "C1 Internal reuse"), ("C1 Internal reuse", "C2 Internal + 1 community offtaker"),
                             ("C1 Internal reuse", "C3 Small network (2-4 offtakers)"),
                             ("C3 Small network (2-4 offtakers)", "C4 Large network (ABC equal-weights, today)"),
                             ("C1 Internal reuse", "R2 Internal + rebuilt Fulton (2029+)"),
                             ("R2 Internal + rebuilt Fulton (2029+)", "R3 Internal + full rebuild campus (2029+)"),
                             ("R2 Internal + rebuilt Fulton (2029+)", "R4 Large network (ABC equal-weights, post-rebuild)")])
    inc.to_csv(OUT / "s_incremental.csv", index=False)

    stake = pd.DataFrame([dict(config=k, **{x: r["stake"].get(x, np.nan) for x in ("dc_net", "users_net", "operator_net", "transfer_check",
                          "user_breakeven_tariff", "operator_breakeven_tariff", "pilot_tariff", "fence_price", "subsidy_needed", "loop_heat_MWh")},
                          net_value=r["econ"]["net_value"], gross_savings=r["econ"]["gross_savings"], avoided_conv_capex_ann=r["econ"]["avoided_conv_capex_ann"],
                          new_opex=r["econ"]["new_opex"], capex_ann=r["econ"]["capex_ann"]) for k, r in results.items()])
    stake.to_csv(OUT / "s_economics_stakeholders.csv", index=False)

    head = {k: v for k, v in configs.items() if k.startswith(("C1", "C2", "C3", "C4", "R2", "R3"))}
    sens = sensitivity(head)
    sens.to_csv(OUT / "s_sensitivity.csv", index=False)
    be = breakeven(head)
    be.to_csv(OUT / "s_breakeven.csv", index=False)

    comp, deco = controlled_comparison(P)
    comp.to_csv(OUT / "s_controlled_comparison.csv", index=False)
    deco.to_csv(OUT / "s_difference_decomposition.csv", index=False)

    corr, audit = abc_indicator_audit()
    corr.to_csv(OUT / "s_abc_indicator_correlation.csv")
    (OUT / "s_abc_indicator_audit.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    temporal_accuracy({k: configs[k] for k in ("C1 Internal reuse", "C3 Small network (2-4 offtakers)", "C4 Large network (ABC equal-weights, today)",
                                                "R3 Internal + full rebuild campus (2029+)")}, P).to_csv(OUT / "s_temporal_accuracy.csv", index=False)
    pd.DataFrame(GOVERNANCE).to_csv(OUT / "s_governance.csv", index=False)

    import validate
    val = validate.run_all(P, configs, comp)
    after = protected_hashes()
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    val = pd.concat([val, pd.DataFrame([dict(test="V12", name="Isolation: no file outside experiments/ changed during the run",
                                             passed=not changed, detail=f"{len(before)} files hashed; changed: {changed[:5]}")])])
    val.to_csv(OUT / "s_validation.csv", index=False)
    (OUT / "run_manifest.json").write_text(json.dumps(dict(
        seconds=round(time.time() - t0, 1), configurations={k: v for k, v in configs.items()},
        best_community_offtaker=best_comm, greedy_today=[p["added"] for p in g_today], greedy_post=[p["added"] for p in g_post],
        tests_passed=int(val.passed.sum()), tests_total=len(val)), indent=2), encoding="utf-8")
    print(rows[["config", "I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "feasible"]].round(2).to_string(index=False))
    print(val[["test", "name", "passed"]].to_string(index=False))
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
