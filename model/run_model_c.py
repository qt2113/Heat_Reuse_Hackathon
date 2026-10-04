"""Run Model C: screen candidates, enumerate every building combination for both horizons, evaluate each
with Models A (merit dispatch) and B, apply feasibility checks, score, analyse weight sensitivity,
explain the recommendation and export frontend-ready files to outputs/model_c/.

    python -m model.run_model_c
"""
from __future__ import annotations

import itertools
import json
import time

import numpy as np
import pandas as pd

from . import features as F
from . import model_b as MB
from . import model_c as MC
from .run_model_a import load_bundle

OUT = F.ROOT / "outputs" / "model_c"
DEFAULT = MC.PRESETS["equal (demonstration baseline)"]


def build_ctx(tariff_rule: str = "affordability_cap") -> dict:
    cfg = F.load_config()
    bundle = load_bundle()
    A = F.assumption_values()
    I = MB.load_inputs()
    P = MB.b_params()
    P["nycha_tariff_rule"] = tariff_rule          # Term 4 (default) or "pilot" (comparison)
    ctx = dict(cfg=cfg, bundle=bundle, A=A, I=I, P=P, offt=bundle["offtakers"])
    ctx["dv"] = MC.dispatch_values(I, A)
    return ctx


def horizons(short: pd.DataFrame, cfg: dict) -> dict:
    """Candidate sets of both horizons. A rebuilt campus is a candidate only if its existing NYCHA anchor passed screening."""
    sl = short[short.status == "shortlisted"]
    today = list(sl.property_id)
    anchors = [s["anchor_property_id"] for s in cfg["scenarios"]["S3R"]["rebuild"]["sites"]]
    post = [p for p in today if not bool(sl.set_index("property_id").loc[p, "is_nycha"])] + [f"rebuild:{a}" for a in anchors if a in today]
    return {"today": today, "post_rebuild": post}


def screen(ctx: dict, overrides: dict | None = None) -> tuple[pd.DataFrame, dict]:
    cfg = ctx["cfg"]
    params = MC.screening_params(cfg, overrides)
    short = MC.screen_candidates(ctx["offt"], ctx["A"], ctx["bundle"]["weather"], ctx["bundle"]["q_dhw_apt"], cfg["site"]["property_id"], params)
    return short, params


def enumerate_horizon(name: str, cands: list, ctx: dict) -> tuple[pd.DataFrame, dict]:
    rows, raw = [], {}
    for k in range(len(cands) + 1):
        for combo in itertools.combinations(cands, k):
            r = MC.evaluate_config(tuple(combo), name, ctx)
            r["internal"] = tuple(combo) == (ctx["cfg"]["site"]["property_id"],)
            ind = MC.indicators(r, ctx)
            ind["horizon"] = name
            rows.append(ind)
            raw[ind["config_id"]] = combo
    df = MC.normalise(pd.DataFrame(rows))
    df["pareto"] = MC.pareto(df)
    df["overall_equal_weights"] = MC.overall(df, DEFAULT)
    return df, raw


# ------------------------------------------------------------------ explanations (generated from indicators)
def _row(df, members):
    cid = MC.config_id(df.horizon.iloc[0], tuple(sorted(members, key=lambda m: m)))
    hit = df[df.members.apply(lambda s: set(s.split("|")) if s else set()) == set(members)]
    return hit.iloc[0] if len(hit) else None


def explain(df: pd.DataFrame, sel_id: str, w: dict, short: pd.DataFrame, ctx: dict) -> dict:
    sc = MC.overall(df, w)
    df = df.assign(_score=sc)
    sel = df[df.config_id == sel_id].iloc[0]
    members = set(sel.members.split("|")) if sel.members else set()
    info = short.set_index("property_id")
    detail = MC.evaluate_config(tuple(sorted(members)), sel.horizon, ctx)
    bt = detail["buildings"].set_index("property_id")
    dims = [MC.DIM_KEY[d] for d in MC.DIMS]

    def bldg_facts(pid):
        if pid.startswith("rebuild:"):
            a = info.loc[pid.split(":")[1]]
            return dict(property_id=pid, name=("Rebuilt Fulton" if pid.endswith("2831044") else "Rebuilt Elliott-Chelsea"),
                        lat=float(a.lat), lon=float(a.lon), use_type="Multifamily Housing (rebuilt, modeled)", dist_m=float(a.dist_m),
                        measured={"note": "future building: demand modeled from A03 x units (S18)"})
        a = info.loc[pid]
        return dict(property_id=pid, name=a.property_name, lat=float(a.lat), lon=float(a.lon), use_type=a.use_type,
                    dist_m=float(a.dist_m), measured=dict(steam_MWh=round(float(a.steam_MWh), 0), gas_MWh=round(float(a.gas_MWh), 0),
                    oil_MWh=round(float(a.oil_MWh), 0), heat_fuel_MWh=round(float(a.heat_fuel_MWh), 0), years=a.years,
                    estimated_months=bool(a.any_estimated)),
                    useful_demand_MWh=round(float(a.D_useful_MWh), 0), servable_share=round(float(a.servable_share), 2),
                    heating_system=a.sh_system)

    def delta(other, base):
        d = {k: float(other[k] - base[k]) for k in ("Q_network_MWh", "E_val", "N_co2", "S_li", "E_fund", "capex_total", "capex_pipe", "route_m", "T_lf")}
        d["overall"] = float(other._score - base._score)
        d.update({f"score_{x}": float(other[f"score_{x}"] - base[f"score_{x}"]) for x in dims})
        return d

    selected = []
    for pid in sorted(members):
        loo = _row(df, members - {pid})
        f = bldg_facts(pid)
        reasons, limits = [], []
        if loo is not None:
            d = delta(sel, loo)
            if d["Q_network_MWh"] > 0:
                reasons.append(f"adds {d['Q_network_MWh'] / 1000:.1f} GWh/yr of recovered heat to the network")
            if d["N_co2"] > 0:
                reasons.append(f"adds {d['N_co2']:,.0f} tCO2e/yr avoided")
            if d["S_li"] > 0:
                reasons.append(f"serves {d['S_li']:,.0f} low-income households")
            if d["E_val"] > 0:
                reasons.append(f"improves annual net value by ${d['E_val'] / 1e6:.2f} M")
            reasons.append(f"raises the overall score by {d['overall']:+.3f} versus the same network without it")
        else:
            d = {}
        if pid in bt.index:
            r = bt.loc[pid]
            f.update(network_heat_MWh=round(float(r.Q_network_MWh), 0), backup_heat_MWh=round(float(r.Q_backup_MWh), 0),
                     share_heat_from_network=round(float(r.share_heat_from_network), 3),
                     bill_change_per_year=round(float(r.user_net), 0), heat_pump_MW=round(float(r.HP_cap_MW), 2))
            if r.sh_system == "steam_radiators":
                limits.append("steam radiators: only hot water / base load is served (H7)")
            if float(r.share_heat_from_network) < 0.5:
                limits.append(f"only {100 * float(r.share_heat_from_network):.0f}% of its heat comes from the network")
            if float(r.user_net) < 0:
                limits.append(f"its heat users pay ${-float(r.user_net) / 1e3:,.0f} k/yr more than today at the applied tariff "
                              f"({'Term 4 cap' if bool(r.is_nycha) else 'pilot rate'})")
        if f.get("measured", {}).get("estimated_months"):
            limits.append("LL84 data include estimated months")
        if pid.startswith("rebuild:"):
            limits.append("future building: demand from assumptions A03 / A19")
        selected.append(dict(**f, incremental=d, reasons=reasons, limitations=limits))

    not_selected = []
    pool = [p for p in df.members.iloc[-1].split("|")] if len(df) else []
    for pid in pool:
        if pid in members:
            continue
        add = _row(df, members | {pid})
        f = bldg_facts(pid)
        reasons = []
        if add is None:
            reasons.append("combination not evaluated")
        else:
            d = delta(add, sel)
            if add.feasibility == "infeasible":
                reasons.append(f"adding it makes the network technically infeasible ({add.failed_checks})")
            if pid in info.index and float(info.loc[pid, "servable_share"]) < 0.5:
                reasons.append(f"temperature incompatibility: only {100 * float(info.loc[pid, 'servable_share']):.0f}% of its heat can be served (steam radiators, H7)")
            if d["capex_total"] > 0 and d["capex_pipe"] / d["capex_total"] > 0.5 and d["route_m"] > 150:
                reasons.append(f"high connection cost: +{d['route_m']:.0f} m of route, +${d['capex_pipe'] / 1e6:.1f} M pipe")
            if d["E_val"] < 0:
                reasons.append(f"reduces annual net value by ${-d['E_val'] / 1e6:.2f} M (its network heat costs more than its current heat)")
            if d["T_lf"] < 0:
                reasons.append("weak seasonal matching: lowers the interface load factor (mostly winter demand)")
            order = {"fully_feasible": 0, "conditionally_feasible": 1, "infeasible": 2}
            if order[add.feasibility] > order[sel.feasibility]:
                reasons.append(f"worsens feasibility to {add.feasibility} ({add.failed_checks})")
            if d["overall"] < 0:
                worst = min(dims, key=lambda x: d[f"score_{x}"])
                reasons.append(f"lowers the overall score by {d['overall']:.3f} (largest drop: {dict(zip(dims, MC.DIMS))[worst]})")
            elif not reasons:
                reasons.append(f"would raise the overall score by {d['overall']:+.3f}, but the resulting network is {add.feasibility}")
            f["incremental_if_added"] = d
        not_selected.append(dict(**f, reasons=reasons))
    return dict(config_id=sel_id, selected=selected, not_selected=not_selected)


# ------------------------------------------------------------------ allocation export
def allocation_json(sel_members: tuple, horizon: str, ctx: dict) -> dict:
    r = MC.evaluate_config(sel_members, horizon, ctx, return_streams=True)
    st, b, h = r["streams"], r["buildings"].reset_index(drop=True), r["hourly"]
    month = ctx["bundle"]["weather"].month.to_numpy()
    T = ctx["bundle"]["weather"].dry_bulb_C.to_numpy()
    wk = int(np.argmin(np.convolve(T, np.ones(168) / 168, mode="valid")))
    weeks = {"coldest_week": wk, "april_week": int(np.where(month == 4)[0][0]) + 7 * 24, "july_week": int(np.where(month == 7)[0][0]) + 7 * 24}
    per_b = []
    for i, row in b.iterrows():
        m = st["bidx"] == i
        net = (st["load"][m] + st["dis"][m]).sum(axis=0)
        bk = st["backup"][m].sum(axis=0)
        loop = st["src"][m].sum(axis=0)
        per_b.append(dict(property_id=row.property_id, name=row["name"],
                          monthly_network_MWh=[round(float(net[month == mm].sum()), 1) for mm in range(1, 13)],
                          monthly_backup_MWh=[round(float(bk[month == mm].sum()), 1) for mm in range(1, 13)],
                          monthly_loop_heat_MWh=[round(float(loop[month == mm].sum()), 1) for mm in range(1, 13)],
                          weeks={k: dict(network_MW=[round(float(x), 3) for x in net[s:s + 168]], backup_MW=[round(float(x), 3) for x in bk[s:s + 168]])
                                 for k, s in weeks.items()},
                          merit_rank=int(np.min(np.where(np.isin(st["order"], np.where(m)[0]))[0])) + 1 if m.any() else None))
    sysw = {k: dict(start_hour=s + 1, T_out_C=[round(float(x), 1) for x in T[s:s + 168]],
                    dc_heat_available_MW=[round(float(x), 3) for x in h.Q_DC_avail_MW.values[s:s + 168]],
                    dc_heat_used_MW=[round(float(x), 3) for x in h.Q_DC_used_MW.values[s:s + 168]],
                    demand_MW=[round(float(x), 3) for x in h.D_total_MW.values[s:s + 168]]) for k, s in weeks.items()}
    return dict(config_id=r["id"], policy="merit: building streams served in order of net value per MWh of source heat",
                monthly_system=dict(dc_heat_available_MWh=[round(float(h.Q_DC_avail_MW[month == mm].sum()), 1) for mm in range(1, 13)],
                                    dc_heat_used_MWh=[round(float(h.Q_DC_used_MW[month == mm].sum()), 1) for mm in range(1, 13)],
                                    demand_MWh=[round(float(h.D_total_MW[month == mm].sum()), 1) for mm in range(1, 13)]),
                weeks=sysw, buildings=per_b, source="Model A merit dispatch (model/dispatch_kernel.py)")


def geojson(short: pd.DataFrame, site: dict) -> dict:
    feats = [dict(type="Feature", geometry=dict(type="Point", coordinates=[site["lon"], site["lat"]]),
                  properties=dict(id="source:111_8th", name="111 8th Avenue (heat source)", role="source"))]
    for r in short.itertuples():
        if pd.isna(r.lat):
            continue
        feats.append(dict(type="Feature", geometry=dict(type="Point", coordinates=[float(r.lon), float(r.lat)]),
                          properties=dict(id=r.property_id, name=r.property_name, use_type=r.use_type, dist_m=float(r.dist_m),
                                          status=r.status, reason=r.exclusion_reason, heat_fuel_MWh=round(float(r.heat_fuel_MWh), 0),
                                          steam_MWh=round(float(r.steam_MWh), 0), gas_MWh=round(float(r.gas_MWh), 0),
                                          useful_demand_MWh=round(float(r.D_useful_MWh), 0) if pd.notna(r.D_useful_MWh) else None,
                                          servable_share=round(float(r.servable_share), 2) if pd.notna(r.servable_share) else None,
                                          heating_system=r.sh_system, nycha=bool(r.is_nycha), n_years=int(r.n_years),
                                          source="LL84 (S01) via outputs/features/offtakers_features.csv")))
    return dict(type="FeatureCollection", features=feats)


def main() -> None:
    t0 = time.time()
    ctx = build_ctx()
    cfg = ctx["cfg"]
    OUT.mkdir(parents=True, exist_ok=True)
    short, screening = screen(ctx)
    short.to_csv(OUT / "c_candidates.csv", index=False)
    H = horizons(short, cfg)
    tables, recs, sens_rows, alloc = [], {}, [], {}
    for hname, cands in H.items():
        df, raw = enumerate_horizon(hname, cands, ctx)
        tables.append(df)
        recs[hname] = {}
        for pname, w in MC.PRESETS.items():
            ch = MC.choose(df, w)
            recs[hname][pname] = dict(weights=w, **ch)
        dch = recs[hname]["equal (demonstration baseline)"]
        if dch["config_id"]:
            recs[hname]["explanation_equal_weights"] = explain(df, dch["config_id"], DEFAULT, short, ctx)
            sel_members = tuple(sorted(df.loc[df.config_id == dch["config_id"], "members"].iloc[0].split("|")))
            alloc[hname] = allocation_json(sel_members, hname, ctx)
            (OUT / f"c_allocation_{hname}.json").write_text(json.dumps(alloc[hname]), encoding="utf-8")
        for w in MC.weight_grid(0.1):
            ch = MC.choose(df, w)
            sens_rows.append(dict(horizon=hname, **{MC.DIM_KEY[d]: round(w[d], 2) for d in MC.DIMS}, winner=ch["config_id"], status=ch["status"]))
    # comparison: same enumeration under the pilot tariff for NYCHA (no Term 4 cap)
    ctx_p = dict(ctx, P=dict(ctx["P"], nycha_tariff_rule="pilot"))
    comp = []
    for hname, cands in H.items():
        dfp, _ = enumerate_horizon(hname, cands, ctx_p)
        dfp.to_csv(OUT / f"c_configurations_pilot_tariff_{hname}.csv", index=False)
        for pname, w in MC.PRESETS.items():
            ch = MC.choose(dfp, w)
            nm = dfp.loc[dfp.config_id == ch["config_id"], "names"].iloc[0] if ch["config_id"] else ""
            comp.append(dict(horizon=hname, preset=pname, tariff_rule="pilot", **ch, names=nm))
    pd.DataFrame(comp).to_csv(OUT / "c_recommendations_pilot_tariff.csv", index=False)
    allc = pd.concat(tables, ignore_index=True)
    allc.to_csv(OUT / "c_configurations.csv", index=False)
    sens = pd.DataFrame(sens_rows)
    sens.to_csv(OUT / "c_weight_sensitivity.csv", index=False)
    allc[allc.pareto].to_csv(OUT / "c_pareto.csv", index=False)
    (OUT / "c_recommendations.json").write_text(json.dumps(recs, indent=2, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else (bool(o) if isinstance(o, np.bool_) else float(o))), encoding="utf-8")
    (OUT / "c_candidates.geojson").write_text(json.dumps(geojson(short, cfg["site"])), encoding="utf-8")
    ind_def = [dict(id=i[0], dimension=i[1], name=i[2], unit=i[3], direction=i[4], level=i[5], formula=i[6], source=i[7],
                    normalisation="min-max over technically feasible configurations of the horizon (incl. today = no network); inverted for 'min'")
               for i in MC.INDICATORS]
    gov = pd.read_csv(F.ROOT / "model" / "config" / "delivery_governance.csv")
    manifest = dict(
        model="C", seconds=round(time.time() - t0, 1), screening=screening, horizons=H, n_configurations={h: int((allc.horizon == h).sum()) for h in H},
        indicators=ind_def, dimensions=list(MC.DIMS),
        tariff_rule="Term 4 affordability cap: NYCHA pays at most its break-even loop-heat rate, no connection charge (comparison under the pilot tariff in c_recommendations_pilot_tariff.csv)",
        overall_score="sum_d w_d x score_d; frontend may recompute from score_T/E/N/S columns of c_configurations.csv with user weights (sum 100%)",
        default_weights="equal 25% each: a demonstration baseline, not prescribed by the organizers",
        feasibility_classes=["fully_feasible", "conditionally_feasible", "infeasible"],
        files=dict(candidates_geojson="c_candidates.geojson", candidates_table="c_candidates.csv", configurations="c_configurations.csv",
                   recommendations="c_recommendations.json", weight_sensitivity="c_weight_sensitivity.csv", pareto="c_pareto.csv",
                   allocation={h: f"c_allocation_{h}.json" for h in alloc}, governance_panels="../../model/config/delivery_governance.csv",
                   validation="c_validation.csv"),
        governance_note=f"{len(gov)} unscored governance/delivery items are shown next to the recommendation; no numeric score is given to them.",
    )
    (OUT / "frontend_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Model C: {len(allc)} configurations in {time.time() - t0:.1f} s -> {OUT}")
    from .validate_model_c import validate
    validate(ctx)


if __name__ == "__main__":
    main()
