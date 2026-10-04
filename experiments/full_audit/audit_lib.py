"""Shared helpers for the full audit. Reads the validated Models A/B/C read-only; every correction is a switch.

Corrections (flags):
  data      pilot_overlap   remove the 291 Fulton apartments already served by the Con Ed pilot (S13 loads)
            outlier_years   LL84 property-years deviating > 50 % from the median of the other years are dropped (>= 3 years)
            oil_fuel        oil share of 'gas_or_oil' buildings priced at the EIA NY heating-oil price and LL97 oil factor
  physics   A17_basis       A17 = 0.367 MWh_e per MWh EXTRACTED (pilot 666 MWh / 1,813.5 MWh injected) instead of 0.25
            no_storage      remove the uncosted 2 h storage tank (it is in Model A sizing but has no capex in Model B)
  cost      nycha_dhw_cost  existing-NYCHA hot-water-only retrofit (18.57 - 7) M$ / 291 apts instead of 18.57 M$ / 291
            backup_boiler   capital + fixed O&M of the electric backup boilers of rebuilt towers (DEA)
  scenario  prewar_steam    gas buildings built before 1940 treated as steam-radiator (hot water only) - uncertainty test
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model import features as F  # noqa: E402
from model import model_b as MB  # noqa: E402
from model import model_c as MC  # noqa: E402
from model.run_redesign import electric_boiler_cost, make_ctx, prewar_gas_as_steam, remove_pilot_overlap  # noqa: E402

HERE = pathlib.Path(__file__).parent
SITE = "7536925"
_oil = pd.read_csv(HERE / "raw_verification" / "eia_ny_heating_oil_residential_weekly.csv", parse_dates=["date"])
_last = _oil[_oil.date >= _oil.date.max() - pd.Timedelta(days=365)]
OIL_PRICE = float(_last.usd_per_gal.mean()) / 0.1387 * 3.412142          # $/MWh fuel (EIA NY residential No.2, 12-mo)
_ll97 = pd.read_csv(F.DATA / "reference" / "ll97_emission_coefficients.csv").set_index("fuel").tCO2e_per_MWh
EF_OIL, EF_GAS = float(_ll97["fuel_oil_2"]), float(_ll97["natural_gas"])
APT_DHW_ONLY = (18.57 - 7.0) / 291 * 1e6                                # S13 p.90: removing one building's HVAC saved ~$7M
A17_PILOT_EXTRACTED = 666.060 / (2680.0 - (91.721 + 774.824))             # 0.367


def base_ctx():
    from model.run_model_c import build_ctx
    return build_ctx()


def yearly() -> pd.DataFrame:
    y = pd.read_csv(F.DATA / "processed" / "ll84_buildings_1km_by_year.csv", dtype={"property_id": str, "report_year": str})
    y = y[~y.is_child_of_listed_parent.astype(bool)].copy()
    for c in ("steam_MWh", "gas_MWh", "oil_MWh", "heat_fuel_MWh"):
        y[c] = pd.to_numeric(y[c], errors="coerce").fillna(0.0)
    return y


def outlier_years(y: pd.DataFrame) -> pd.DataFrame:
    """Property-years that are (a) zero while other years are not (missing filing), or (b) > 50 % away from the median of the
    other years while those other years agree within 25 % (an isolated anomaly, not a trend). Needs >= 3 years."""
    out = []
    for pid, g in y.groupby("property_id"):
        if len(g) < 3:
            continue
        for i, r in g.iterrows():
            others = g.drop(i).heat_fuel_MWh
            med = float(others.median())
            if med <= 0:
                continue
            agree = (others.max() - others.min()) / med <= 0.25
            zero = r.heat_fuel_MWh <= 0
            if zero or (agree and abs(r.heat_fuel_MWh - med) / med > 0.5):
                out.append(dict(property_id=pid, report_year=r.report_year, heat_fuel_MWh=r.heat_fuel_MWh, median_other_years=med,
                                deviation=(r.heat_fuel_MWh - med) / med, kind="zero year" if zero else "isolated anomaly"))
    return pd.DataFrame(out, columns=["property_id", "report_year", "heat_fuel_MWh", "median_other_years", "deviation", "kind"])


def clean_offtakers(o: pd.DataFrame, flags: set) -> pd.DataFrame:
    o = o.copy()
    if "outlier_years" in flags:
        y = yearly()
        bad = outlier_years(y)
        if len(bad):
            keep = y.merge(bad[["property_id", "report_year"]], how="left", indicator=True)
            keep = keep[keep._merge == "left_only"]
            agg = keep.groupby("property_id")[["steam_MWh", "gas_MWh", "oil_MWh", "heat_fuel_MWh"]].mean()
            ids = set(bad.property_id)
            m = o.property_id.isin(ids)
            for c in ("steam_MWh", "gas_MWh", "oil_MWh", "heat_fuel_MWh"):
                o.loc[m, c] = o.loc[m, "property_id"].map(agg[c]).values
    if "pilot_overlap" in flags:
        o = remove_pilot_overlap(o)
    if "prewar_steam" in flags:
        o = prewar_gas_as_steam(o)
    return o


def ctx_for(ctx: dict, flags: set, A=None, P=None, I=None, design=None) -> dict:
    A = dict(A or {})
    if "A17_basis" in flags and "A17" not in A:
        A["A17"] = A17_PILOT_EXTRACTED
    d = dict(design or {})
    if "no_storage" in flags:
        d["tank_hours"] = 0
    fn = (lambda o: clean_offtakers(o, flags)) if flags & {"outlier_years", "pilot_overlap", "prewar_steam"} else None
    return make_ctx(ctx, A=A, P=P, I=I, offt_fn=fn, design=d or None)


def evaluate(members: list, horizon: str, ctx: dict, flags: set) -> dict:
    """One network -> reconciled ledger + outcomes. Post-processing only adds/removes clearly identified lines."""
    r = MC.evaluate_config(tuple(members), horizon, ctx)
    r["internal"] = tuple(members) == (SITE,)
    ind = MC.indicators(r, ctx)
    s, e, b = r["summary"], r["econ"], r["buildings"]
    markup = 1 + ctx["I"]["contingency"] + ctx["P"]["A21"]
    k = MB.crf(ctx["P"]["A08"], ctx["I"]["life"])
    base, backup = e["baseline_cost_annual"], e["backup_fuel_cost"]
    capex, capex_ann, om, fund, co2 = e["capex_total"], e["capex_annualised"], e["om_annual"], e["public_funding_need"], e["co2_avoided"]
    if "oil_fuel" in flags and len(b):
        o = ctx["offt"].set_index("property_id")
        ex = (~b.rebuilt.astype(bool) & (b.main_fuel == "gas_or_oil")).astype(float)
        s_oil = b.property_id.map(lambda p: float(o.loc[p, "oil_MWh"]) / max(float(o.loc[p, "gas_MWh"] + o.loc[p, "oil_MWh"]), 1e-9)
                                  if p in o.index else 0.0) * ex
        dp = OIL_PRICE - ctx["I"]["gas_price"]
        base += float((b.base_fuel_MWh * s_oil).sum()) * dp
        backup += float((b.backup_fuel_MWh * s_oil).sum()) * dp
        co2 += float(((b.base_fuel_MWh - b.backup_fuel_MWh) * s_oil).sum()) * (EF_OIL - EF_GAS)
    if "nycha_dhw_cost" in flags and len(b):
        ny = b[b.is_nycha.astype(bool) & ~b.rebuilt.astype(bool)]
        dc = float((ny.units * (ctx["I"]["apt_capex"] - APT_DHW_ONLY)).sum()) * markup
        capex -= dc
        capex_ann -= dc * k
        fund = max(0.0, fund - dc * k)
    if "backup_boiler" in flags:
        xc, xa = electric_boiler_cost(r, ctx)
        capex += xc
        capex_ann += xa
    elec = e["electricity_cost"]
    val = base - (capex_ann + om + elec + backup)
    reb = b.rebuilt.astype(bool) if len(b) else pd.Series(dtype=bool)
    li_strict = float((b.units * (b.is_nycha.astype(bool) & ~reb)).sum() + b.loc[reb, "low_income_hh"].sum()) if len(b) else 0.0
    Q = s.Q_network_MWh
    return dict(
        config_id=ind["config_id"], members="|".join(members), horizon=horizon, n_external=sum(m != SITE for m in members),
        heat_recovered_MWh=s.Q_DC_used_MWh, heat_delivered_MWh=Q, backup_MWh=s.Q_backup_MWh,
        baseline_cost=base, electricity_hp_pump=elec - e["source_electricity_cost"], electricity_source_A17=e["source_electricity_cost"],
        backup_fuel=backup, om=om, capex_total=capex, capex_annualised=capex_ann,
        gross_energy_savings=base - elec - backup, net_societal_value=val, check_vs_model_b=val - e["annual_savings"],
        co2_avoided_t=co2, energy_cost_per_MWh_delivered=(elec + backup) / Q if Q else np.nan,
        lcoh=(capex_ann + om + elec) / Q if Q else np.nan,
        low_income_households_strict=li_strict, community_facilities=ind["S_fac"],
        funding_gap_at_tariff=fund, minimum_support=max(0.0, -val), dc_net=e["dc_net"], tech_ok=ind["tech_ok"],
        scop=s.T2_SCOP, route_m=s.route_m)
