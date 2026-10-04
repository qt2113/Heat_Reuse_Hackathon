"""Stage 3: feature necessity and ablation on the validated Model C configurations (identical A/B results for every variant).

Variants re-normalise (min-max over technically feasible configurations, as Model C does) and re-score with the given
indicator set; feasibility classes are unchanged unless a variant adds hard constraints.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import audit_lib as L

MC = L.MC
OUT = L.HERE
c = pd.read_csv(L.F.ROOT / "outputs" / "model_c" / "c_configurations.csv")
c["members"] = c.members.fillna("")
c["n_external"] = c.members.apply(lambda s: len([m for m in s.split("|") if m and m != L.SITE]))
c["capex_M"] = c.capex_total / 1e6
c["heat_per_MWh_el"] = c.Q_network_MWh / (c.electricity_cost / 222.0).replace(0, np.nan)    # incl. source-side electricity
DIR = {i[0]: i[4] for i in MC.INDICATORS}
DIR.update(Q_network_MWh="max", capex_M="min", heat_per_MWh_el="max")
DIMS = ("T", "E", "N", "S")
FULL = {"T": ["T_cov", "T_lf", "T_bk"], "E": ["E_lcoh", "E_val", "E_fund"], "N": ["N_co2", "N_erf", "N_gas"], "S": ["S_li", "S_aff", "S_eq", "S_fac"]}


def score(df: pd.DataFrame, sets: dict, w=None) -> pd.Series:
    w = w or {d: 0.25 for d in DIMS}
    pool = df[df.tech_ok | (df.n_buildings == 0)]
    dim = {}
    for d, ids in sets.items():
        cols = []
        for i in ids:
            x = pool[i].astype(float)
            lo, hi = np.nanmin(x), np.nanmax(x)
            if not hi > lo:
                continue                                      # constant indicator carries no information
            n = ((df[i].astype(float) - lo) / (hi - lo)).clip(0, 1).fillna(0)
            cols.append(1 - n if DIR[i] == "min" else n)
        dim[d] = pd.concat(cols, axis=1).mean(axis=1) if cols else pd.Series(0.0, index=df.index)
    return sum(w.get(d, 0) * dim[d] for d in dim) / sum(w.get(d, 0) for d in dim)


def choose(df, sc, constraints=None):
    m = (df.n_buildings > 0) & df.tech_ok
    if constraints:
        m &= constraints(df)
    full = m & (df.feasibility == "fully_feasible")
    pool = df[full] if full.any() else df[m & (df.feasibility != "infeasible")]
    return pool.index[sc.loc[pool.index].values.argmax()] if len(pool) else None


VARIANTS = {"full 13 (reference)": FULL}
for d, ids in FULL.items():
    for i in ids:
        VARIANTS[f"drop {i}"] = {dd: [x for x in v if x != i] for dd, v in FULL.items()}
VARIANTS["drop duplicates (T_bk, N_erf, E_fund)"] = {"T": ["T_cov", "T_lf"], "E": ["E_lcoh", "E_val"], "N": ["N_co2", "N_gas"], "S": FULL["S"]}
VARIANTS["drop duplicates + S_eq, S_aff, N_gas, T_cov, E_lcoh"] = {"T": ["T_lf"], "E": ["E_val"], "N": ["N_co2"], "S": ["S_li", "S_fac"]}
VARIANTS["Model S 8 indicators"] = {"T": ["Q_network_MWh", "T_lf"], "E": ["E_val", "capex_M"], "N": ["N_co2", "heat_per_MWh_el"], "S": ["S_li", "S_fac"]}
VARIANTS["minimal (T_lf, E_val, N_co2, S_li + S_fac)"] = {"T": ["T_lf"], "E": ["E_val"], "N": ["N_co2"], "S": ["S_li", "S_fac"]}

CONSTRAINTS = {
    "none": None,
    ">=1 external": lambda d: d.n_external >= 1,
    ">=1 external + net CO2 >= 0": lambda d: (d.n_external >= 1) & (d.N_co2 >= 0),
    ">=1 external + CO2 >= 0 + NYCHA affordability": lambda d: (d.n_external >= 1) & (d.N_co2 >= 0) & (d.H6_affordability.fillna(True).astype(bool)),
}
grid = list(MC.weight_grid(0.1))
rows = []
for h, df in c.groupby("horizon"):
    df = df.reset_index(drop=True)
    ref_sc = score(df, FULL)
    tf = df[(df.n_buildings > 0) & df.tech_ok]
    for vname, sets in VARIANTS.items():
        sc = score(df, sets)
        for cname, cons in CONSTRAINTS.items():
            if cname != "none" and vname not in ("full 13 (reference)", "minimal (T_lf, E_val, N_co2, S_li + S_fac)", "Model S 8 indicators"):
                continue
            win = choose(df, sc, cons)
            winners = set()
            for wt in grid:
                ww = dict(zip(DIMS, (wt[d] for d in MC.DIMS)))
                i = choose(df, score(df, sets, ww), cons) if cname == "none" or True else None
                winners.add(df.config_id[i] if i is not None else None)
            r = df.loc[win] if win is not None else None
            rows.append(dict(horizon=h, variant=vname, constraints=cname, n_indicators=sum(len(v) for v in sets.values()),
                             winner=r.config_id if r is not None else None, winner_n_buildings=int(r.n_buildings) if r is not None else None,
                             winner_n_external=int(r.n_external) if r is not None else None,
                             winner_E_val=float(r.E_val) if r is not None else None, winner_N_co2=float(r.N_co2) if r is not None else None,
                             winner_S_li=float(r.S_li) if r is not None else None, winner_Q_DC_used=float(r.Q_DC_used_MWh) if r is not None else None,
                             distinct_winners_weight_grid=len(winners),
                             spearman_vs_reference=float(pd.Series(sc[tf.index]).corr(pd.Series(ref_sc[tf.index]), method="spearman")),
                             spearman_score_vs_n_buildings=float(pd.Series(sc[tf.index]).corr(tf.n_buildings, method="spearman")),
                             spearman_score_vs_net_value=float(pd.Series(sc[tf.index]).corr(tf.E_val, method="spearman")),
                             same_winner_as_reference=None))
ab = pd.DataFrame(rows)
for h in ab.horizon.unique():
    ref = ab[(ab.horizon == h) & (ab.variant == "full 13 (reference)") & (ab.constraints == "none")].winner.iloc[0]
    ab.loc[ab.horizon == h, "same_winner_as_reference"] = ab.loc[ab.horizon == h, "winner"] == ref
# incremental-ladder rule (no weights, no normalisation): best net value with >= 1 external, CO2 >= 0
for h, df in c.groupby("horizon"):
    tf = df[(df.n_buildings > 0) & df.tech_ok & (df.n_external >= 1) & (df.N_co2 >= 0)]
    r = tf.loc[tf.E_val.idxmax()]
    ab.loc[len(ab)] = dict(horizon=h, variant="no scoring: max net value s.t. >=1 external, CO2 >= 0", constraints="hard constraints", n_indicators=1,
                           winner=r.config_id, winner_n_buildings=int(r.n_buildings), winner_n_external=int(r.n_external), winner_E_val=float(r.E_val),
                           winner_N_co2=float(r.N_co2), winner_S_li=float(r.S_li), winner_Q_DC_used=float(r.Q_DC_used_MWh), distinct_winners_weight_grid=1,
                           spearman_vs_reference=np.nan, spearman_score_vs_n_buildings=float(tf.E_val.corr(tf.n_buildings, method="spearman")),
                           spearman_score_vs_net_value=1.0, same_winner_as_reference=False)
ab.to_csv(OUT / "feature_ablation.csv", index=False)

# redundancy matrix on technically feasible configurations
corr_rows = []
for h, df in c.groupby("horizon"):
    tf = df[(df.n_buildings > 0) & df.tech_ok]
    ids = [i[0] for i in MC.INDICATORS] + ["n_buildings", "Q_network_MWh"]
    cm = tf[ids].astype(float).corr(method="spearman")
    for a, b in itertools.combinations(ids, 2):
        if abs(cm.loc[a, b]) >= 0.85:
            corr_rows.append(dict(horizon=h, a=a, b=b, spearman=round(float(cm.loc[a, b]), 3)))
pd.DataFrame(corr_rows).to_csv(OUT / "03_redundancy_pairs.csv", index=False)
pd.set_option("display.width", 250)
print(ab[["horizon", "variant", "constraints", "n_indicators", "winner_n_buildings", "winner_n_external", "winner_E_val", "winner_N_co2", "winner_S_li",
          "distinct_winners_weight_grid", "spearman_vs_reference", "spearman_score_vs_n_buildings", "spearman_score_vs_net_value", "same_winner_as_reference"]]
      .round(2).to_string(index=False))
print(pd.DataFrame(corr_rows).to_string(index=False))
