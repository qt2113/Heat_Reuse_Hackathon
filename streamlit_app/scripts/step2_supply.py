"""Step 2: heat pump + hourly dispatch for a FIXED building set (all candidates ≤ 300 m)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import Config  # noqa: E402
from src.demand import build_demand  # noqa: E402
from src.supply import dispatch  # noqa: E402

FIXED_SET_RADIUS_M = 300.0  # demo set only; selection comes in step 3


def show(label: str, r, cfg: Config) -> None:
    s = r.summary
    print(f"{label:34s} served {s['demand_mwh']:>8,.0f} | DC {s['share_dc']:6.1%} | tank {s['share_storage']:5.1%} | "
          f"backup {s['share_backup']:6.1%} | HP elec {s['hp_elec_mwh']:>6,.0f} MWh | HP CF {s['hp_capacity_factor']:5.1%} | "
          f"peak backup {s['peak_backup_mw']:4.1f} MW | tank for outage {s['storage_needed_for_outage_mwh']:5.0f} MWh")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    base = Config.load()
    b, dem, temp, _ = build_demand(base)
    sel = (b["distance_m"] <= FIXED_SET_RADIUS_M).to_numpy()
    load = dem[sel].sum(axis=0)
    print(f"Fixed set: {sel.sum()} buildings within {FIXED_SET_RADIUS_M:.0f} m, "
          f"{load.sum():,.0f} MWh/yr, peak {load.max():.1f} MW, mean {load.mean():.1f} MW, min {load.min():.2f} MW")
    print(b.loc[sel, ["property_name", "distance_m", "annual_heat_mwh", "peak_kw"]]
          .sort_values("annual_heat_mwh", ascending=False).head(12).round(0).to_string(index=False))

    r = dispatch(load, base, index=temp.index)
    hp = r.hp
    print(f"\nHeat pump: source {base.v('supply.t_source_c')} °C → sink {base.v('supply.t_supply_c') + base.v('supply.hx_penalty_k')} °C "
          f"(supply {base.v('supply.t_supply_c')} + HX {base.v('supply.hx_penalty_k')} K), eta {base.v('supply.cop_eta')} → "
          f"COP {hp.cop:.2f}; Q_src {hp.q_src_mw:.1f} MW → delivered {hp.q_delivered_mw:.2f} MW_th, elec {hp.p_elec_mw:.2f} MW_e")
    h = r.hourly
    soc_check = h["storage_charge"].sum() - h["storage_discharge"].sum() - h["storage_loss"].sum()
    print(f"Energy balance: max |direct+tank+backup-demand| = "
          f"{np.abs(h.dc_direct + h.storage_discharge + h.backup - h.demand).max():.2e} MW; "
          f"tank Σcharge-Σdischarge-Σloss = {soc_check:.2e} MWh (periodic year → ~0)")

    print("\n=== Scenarios (fixed set) ===")
    scen = {
        "base (5 MW, 20 MWh tank, 0 h out)": {},
        "no storage": {"supply.storage_mwh": 0.0},
        "100 MWh tank": {"supply.storage_mwh": 100.0},
        "168 h outage at peak": {"supply.outage_hours": 168},
        "168 h outage, summer": {"supply.outage_hours": 168, "supply.outage_placement": "summer"},
        "Q_src 10 MW": {"supply.q_src_mw": 10.0},
        "Q_src 2 MW": {"supply.q_src_mw": 2.0},
        "24 h HDH smoothing": {"demand.space_smoothing_h": 24},
    }
    for label, ov in scen.items():
        cfg = base.with_overrides(ov)
        ld = load
        if "demand.space_smoothing_h" in ov:
            b2, d2, _, _ = build_demand(cfg)
            ld = d2[(b2["distance_m"] <= FIXED_SET_RADIUS_M).to_numpy()].sum(axis=0)
        show(label, dispatch(ld, cfg, index=temp.index), cfg)

    m = h.resample("MS").sum(numeric_only=True)[["demand", "dc_direct", "storage_discharge", "backup", "hp_elec"]]
    print("\n=== Monthly (base, MWh) ===")
    print(m.set_index(m.index.strftime("%b")).round(0).to_string())


if __name__ == "__main__":
    main()
