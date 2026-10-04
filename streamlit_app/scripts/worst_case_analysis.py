"""Why the Worst case loses money: one-at-a-time impact of each pessimistic input on the base
network, break-even values, and what the optimiser would build if it knew the worst case."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import Config  # noqa: E402
from src.scenario import evaluate, prepare  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    base = Config.load()
    p = prepare(base)
    base_res = evaluate(p, base)
    sel = base_res.selection
    net0 = base_res.kpi["net_usd"]
    worst = base.get("presets")["worst"]["overrides"]
    print(f"Base network: {base_res.kpi['buildings']} buildings, net ${net0/1e6:.2f}M/yr")
    print("\nOne input at a time at its worst value (base network fixed):")
    rows = []
    for k, v in worst.items():
        r = evaluate(p, base.with_overrides({k: v}), locked=sel)
        rows.append((r.kpi["net_usd"] - net0, k, base.v(k), v))
    for d, k, b0, v in sorted(rows):
        print(f"  {k:42s} {str(b0):>8s} -> {str(v):<8s} change ${d/1e6:+.2f}M/yr")
    rw = evaluate(p, base.with_overrides(worst), locked=sel)
    print(f"  sum of single effects ${sum(r[0] for r in rows)/1e6:+.2f}M vs all together ${(rw.kpi['net_usd']-net0)/1e6:+.2f}M")
    k = rw.kpi
    print(f"\nWorst case money: fuel {k['avoided_fuel_usd']/1e6:.2f} + LL97 {k['avoided_ll97_usd']/1e6:.2f} + water {k['water_usd']/1e6:.2f} "
          f"- elec {k['electricity_usd']/1e6:.2f} - capex {k['capex_total_usd']/1e6:.2f} "
          f"(pipes {k['capex_pipes_usd']/1e6:.2f}, conn {k['capex_connections_usd']/1e6:.2f}, HP {k['capex_heat_pump_usd']/1e6:.2f}) "
          f"= {k['net_usd']/1e6:.2f}; COP {k['hp_cop']:.2f}")

    print("\nBreak-even (base network, all other inputs at base):")
    for key, lo, hi in [("economics.electricity_price_usd_kwh", 0.15, 0.60), ("economics.pipe_cost_usd_m", 1000, 30000),
                        ("economics.steam_price_usd_mmbtu", 10, 60), ("supply.cop_eta", 0.15, 0.6),
                        ("economics.hp_capex_usd_kw", 600, 10000)]:
        f = lambda x: evaluate(p, base.with_overrides({key: x}), locked=sel).kpi["net_usd"]
        flo, fhi = f(lo), f(hi)
        if flo * fhi > 0:
            print(f"  {key}: no sign change in [{lo}, {hi}] (net {flo/1e6:.2f} .. {fhi/1e6:.2f})")
            continue
        for _ in range(30):
            mid = (lo + hi) / 2
            if f(mid) * flo > 0:
                lo = mid
            else:
                hi = mid
        print(f"  {key}: net = 0 at {lo:.4g} (base {base.v(key)})")

    ro = evaluate(p, base.with_overrides(worst))
    print(f"\nIf the worst case were known before building (re-optimised): {ro.kpi['buildings']} buildings, "
          f"{ro.kpi['pipe_km']:.2f} km, net ${ro.kpi['net_usd']/1e6:.2f}M/yr, buildings save ${ro.kpi['building_savings_usd']/1e6:.2f}M")


if __name__ == "__main__":
    main()
