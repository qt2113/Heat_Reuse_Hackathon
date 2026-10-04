"""Run every preset in config.yaml and print the headline results (used for the README/pitch)."""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import Config  # noqa: E402
from src.scenario import evaluate, prepare  # noqa: E402

PREP_KEYS = ("data.", "demand.", "con_ed_pilot.")  # overrides that change the prepared demand


def run_presets(base: Config) -> list[dict]:
    rows, preps = [], {}
    for key, preset in base.get("presets").items():
        cfg = base.with_overrides(preset["overrides"])
        prep_ov = tuple(sorted((k, v) for k, v in preset["overrides"].items() if k.startswith(PREP_KEYS)))
        if prep_ov not in preps:
            preps[prep_ov] = prepare(cfg)
        p = preps[prep_ov]
        t = time.perf_counter()
        locked = evaluate(p, base).selection if preset.get("lock_base_network") else None
        r = evaluate(p, cfg, locked=locked)
        k = r.kpi
        rows.append({"preset": key, "s": time.perf_counter() - t, **k})
    return rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    for r in run_presets(Config.load()):
        print(f"{r['preset']:15s} {r['s']:4.1f}s | {r['buildings']:3d} bldgs ({r['priority_buildings']} priority) "
              f"{r['pipe_km']:4.1f} km | {r['served_mwh'] / 1000:5.1f} GWh {r['coverage']:4.0%} | "
              f"CO2 {r['co2_net_t']:6,.0f} t | net ${r['net_usd'] / 1e6:5.2f}M | operator ${r['operator_profit_usd'] / 1e6:5.2f}M "
              f"| buildings save ${r['building_savings_usd'] / 1e6:4.2f}M | COP {r['hp_cop']:.2f}")
