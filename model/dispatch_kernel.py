"""Building-level hourly dispatch kernel (operational allocation) used by Model A's `policy="merit"`.

Each stream = one building x one temperature class, with its own demand, heat-pump capacity, storage
and backup. Each hour, available data-center heat is allocated to streams in a fixed merit order
(highest net value per MWh of source heat first). Without storage this greedy rule is the exact
optimum of the hourly single-resource allocation problem (fractional knapsack); storage charging
uses any heat left after all loads are served (myopic rule, stated in model/README.md).
"""
import numpy as np
from numba import njit


@njit(cache=True)
def dispatch(D, cap, tank, cop, bcap, order, src_avail, hp_scale):
    S, H = D.shape
    load = np.zeros((S, H)); ch = np.zeros((S, H)); dis = np.zeros((S, H)); soc_t = np.zeros((S, H))
    bk = np.zeros((S, H)); uns = np.zeros((S, H)); E = np.zeros((S, H)); src = np.zeros((S, H))
    soc = np.zeros(S)
    for h in range(H):
        left = src_avail[h]
        # pass 1: serve loads in merit order
        for k in range(S):
            s = order[k]
            c = cop[s]
            cap_h = cap[s] * hp_scale[h]
            qmax = min(cap_h, left * c / (c - 1.0)) if cap_h > 0 else 0.0
            l = min(D[s, h], qmax)
            load[s, h] = l
            left -= l * (1.0 - 1.0 / c)
        # pass 2: charge storage with remaining heat (same order), then discharge / backup
        for k in range(S):
            s = order[k]
            c = cop[s]
            cap_h = cap[s] * hp_scale[h]
            q = 0.0
            if tank[s] > 0:
                qmax = min(cap_h - load[s, h], left * c / (c - 1.0)) if cap_h > load[s, h] else 0.0
                q = min(qmax, tank[s] - soc[s])
                if q < 0:
                    q = 0.0
            ch[s, h] = q
            left -= q * (1.0 - 1.0 / c)
            need = D[s, h] - load[s, h]
            d = min(need, soc[s])
            dis[s, h] = d
            soc[s] += q - d
            soc_t[s, h] = soc[s]
            b = need - d
            u = b - bcap[s] if b > bcap[s] else 0.0
            bk[s, h] = b - u
            uns[s, h] = u
            qo = load[s, h] + q
            E[s, h] = qo / c
            src[s, h] = qo * (1.0 - 1.0 / c)
    return load, ch, dis, soc_t, bk, uns, E, src
