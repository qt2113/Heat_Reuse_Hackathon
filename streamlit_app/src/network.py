"""Street graph, building snapping and connection selection (prize-collecting Steiner tree).

Pipes follow streets. The tree is rooted at the data center's street node. Each building
connects with a straight service pipe from its centroid to its snapped street node.

Value model used during selection (no storage — that is added in the dispatch afterwards):
hourly network capacity Q (MW) is shared pro rata, i.e. every connected building receives
the same fraction f_t = min(1, Q / L_t) of its hourly load L_t. This mirrors a hydraulically
balanced network whose buildings top up with their own boilers. Because f_t falls as more
load is connected, value is NOT additive — greedy evaluates each candidate's exact marginal
value against the current set.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
import pandas as pd

from .config import Config
from .fetch import haversine_m
from .metrics import crf

M_PER_DEG_LAT = 111_000.0


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
def to_simple_graph(g_raw) -> nx.Graph:
    """Undirected simple graph: node attrs lat/lon, edge attrs length (m) and coords
    [(lon, lat), …] ordered from the lower to the higher node id."""
    g = nx.Graph()
    for n, d in g_raw.nodes(data=True):
        g.add_node(n, lat=float(d["y"]), lon=float(d["x"]))
    for u, v, d in g_raw.edges(data=True):
        if u == v:
            continue
        length = float(d["length"])
        if g.has_edge(u, v) and g[u][v]["length"] <= length:
            continue
        geom = d.get("geometry")
        if geom is not None:
            coords = [(float(x), float(y)) for x, y in geom.coords]
            pu = (g.nodes[u]["lon"], g.nodes[u]["lat"])
            if _deg_dist(coords[0], pu) > _deg_dist(coords[-1], pu):
                coords = coords[::-1]
        else:
            coords = [(g.nodes[u]["lon"], g.nodes[u]["lat"]), (g.nodes[v]["lon"], g.nodes[v]["lat"])]
        g.add_edge(u, v, length=length, coords=coords if u < v else coords[::-1])
    return g


def _deg_dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def segmentize(g: nx.Graph, max_seg_m: float) -> nx.Graph:
    """Split every edge longer than ``max_seg_m`` into equal sub-edges with new nodes
    interpolated along its geometry, so buildings can attach mid-block."""
    from shapely.geometry import LineString

    out = nx.Graph()
    out.add_nodes_from(g.nodes(data=True))
    next_id = -1
    for u, v, d in g.edges(data=True):
        a, b = (u, v) if u < v else (v, u)
        k = max(1, math.ceil(d["length"] / max_seg_m))
        if k == 1:
            out.add_edge(a, b, length=d["length"], coords=d["coords"])
            continue
        line = LineString(d["coords"])
        chain = [a]
        pts = [line.interpolate(i / k, normalized=True) for i in range(1, k)]
        for p in pts:
            out.add_node(next_id, lat=p.y, lon=p.x)
            chain.append(next_id)
            next_id -= 1
        chain.append(b)
        fr = [0.0] + [i / k for i in range(1, k)] + [1.0]
        for i in range(k):
            sub = _substring(line, fr[i], fr[i + 1])
            out.add_edge(chain[i], chain[i + 1], length=d["length"] / k, coords=sub)
    return out


def _substring(line, f0: float, f1: float) -> list[tuple[float, float]]:
    from shapely.ops import substring
    seg = substring(line, f0, f1, normalized=True)
    return [(float(x), float(y)) for x, y in seg.coords]


def build_graph(g_raw, cfg: Config) -> nx.Graph:
    """Simple undirected street graph, segmentised, largest connected component only."""
    g = segmentize(to_simple_graph(g_raw), cfg.v("network.max_segment_m"))
    largest = max(nx.connected_components(g), key=len)
    return g.subgraph(largest).copy()


def snap(g: nx.Graph, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Nearest graph node for each point → (node ids, straight-line distance m)."""
    nodes = np.array(list(g.nodes))
    nlat = np.array([g.nodes[n]["lat"] for n in nodes])
    nlon = np.array([g.nodes[n]["lon"] for n in nodes])
    ids, dists = [], []
    for la, lo in zip(np.asarray(lat), np.asarray(lon)):
        d = haversine_m(la, lo, nlat, nlon)
        j = int(np.argmin(d))
        ids.append(nodes[j])
        dists.append(float(d[j]))
    return np.array(ids), np.array(dists)


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------
@dataclass
class Prizes:
    """Per-building arrays used by the selection algorithms (same order as the econ table)."""

    demand: np.ndarray       # (n, 8760) MW
    margin: np.ndarray       # USD per MWh served
    co2_cut: np.ndarray      # tCO2e per MWh served (≥ 0)
    ll97_excess: np.ndarray  # tCO2e/yr over cap
    penalty: float           # USD/tCO2e (0 if LL97 off)
    fixed_cost: np.ndarray   # USD/yr: substation + service pipe
    node: np.ndarray         # snapped street node
    q_cap: float             # MW network capacity (heat-pump output)

    @classmethod
    def build(cls, econ: pd.DataFrame, demand: np.ndarray, node: np.ndarray, service_m: np.ndarray,
              cost_per_m: float, q_cap: float, cfg: Config) -> "Prizes":
        pen = cfg.v("emissions.ll97_penalty_usd_t") if cfg.get("emissions.ll97_enabled") else 0.0
        # objective columns (perspective, carbon value and priority weighting already applied)
        return cls(demand=demand, margin=econ["obj_margin_usd_mwh"].to_numpy(),
                   co2_cut=np.clip(econ["co2_cut_t_mwh"].to_numpy(), 0, None),
                   ll97_excess=np.asarray(econ["obj_ll97_t"], dtype=float) * (1 if pen else 0),
                   penalty=pen, fixed_cost=econ["conn_usd_yr"].to_numpy() + service_m * cost_per_m,
                   node=node, q_cap=q_cap)

    def value(self, idx: np.ndarray, served: np.ndarray) -> np.ndarray:
        """USD/yr for buildings ``idx`` receiving ``served`` MWh (served may be (len(idx), k))."""
        shape = (-1,) + (1,) * (served.ndim - 1)
        m, k, e = (a[idx].reshape(shape) for a in (self.margin, self.co2_cut, self.ll97_excess))
        return served * m + self.penalty * np.minimum(e, k * served)

    def set_value(self, sel: list[int]) -> tuple[float, np.ndarray]:
        """Operating value (USD/yr) and served MWh per building for a set, pro-rata sharing."""
        if not sel:
            return 0.0, np.zeros(0)
        d = self.demand[sel]
        load = d.sum(axis=0)
        f = np.minimum(1.0, self.q_cap / np.maximum(load, 1e-12))
        served = d @ f
        return float(self.value(np.array(sel), served).sum()), served

    def marginal_values(self, sel: list[int], load: np.ndarray, cand: np.ndarray) -> np.ndarray:
        """Total operating value of sel ∪ {c} for every candidate c (vectorised)."""
        dc = self.demand[cand]                                   # (k, 8760)
        f = np.minimum(1.0, self.q_cap / np.maximum(load[None, :] + dc, 1e-12))
        v = self.value(cand, (dc * f).sum(axis=1))
        if sel:
            served_s = self.demand[sel] @ f.T                    # (|S|, k)
            v = v + self.value(np.array(sel), served_s).sum(axis=0)
        return v


def cost_per_m_yr(cfg: Config, network_heat_cost_usd_mwh: float) -> float:
    """Annual cost per metre of trench: annualised capex + heat loss valued at network heat cost."""
    capex = cfg.v("economics.pipe_cost_usd_m") * crf(cfg.v("economics.discount_rate"), cfg.v("economics.pipe_life_yr"))
    loss_mwh = cfg.v("network.heat_loss_w_per_m") * 8760 / 1e6
    return capex + loss_mwh * network_heat_cost_usd_mwh


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------
@dataclass
class Selection:
    method: str
    selected: list[int]                          # indices into the econ table, in order added
    tree_edges: set[tuple] = field(default_factory=set)
    street_m: float = 0.0
    service_m: float = 0.0
    operating_value: float = 0.0                 # USD/yr (pro-rata, no storage)
    network_cost: float = 0.0                    # USD/yr: street pipes + services + substations
    log: list[dict] = field(default_factory=list)
    greedy_objective: float | None = None        # set by refine_select for comparison

    @property
    def pipe_m(self) -> float:
        return self.street_m + self.service_m

    @property
    def objective(self) -> float:
        return self.operating_value - self.network_cost


def _edge_key(u, v) -> tuple:
    return (u, v) if u <= v else (v, u)


def steiner_tree(g: nx.Graph, root, terminals: set) -> set[tuple]:
    """Shortest-path Steiner tree heuristic (Takahashi–Matsuyama): starting from the root,
    repeatedly connect the terminal nearest to the current tree along its shortest path."""
    tree_nodes, edges = {root}, set()
    remaining = set(terminals) - tree_nodes
    while remaining:
        dist, paths = nx.multi_source_dijkstra(g, tree_nodes, weight="length")
        t = min(remaining, key=lambda n: dist.get(n, math.inf))
        if t not in dist:
            raise ValueError(f"terminal {t} not reachable from the network")
        path = paths[t]
        edges.update(_edge_key(u, v) for u, v in zip(path[:-1], path[1:]))
        tree_nodes.update(path)
        remaining -= set(path)
    return edges


def set_objective(g: nx.Graph, root, prizes: Prizes, sel: list[int], cost_m: float) -> tuple[float, set]:
    """Objective (operating value − street pipe − fixed connection costs) of a set, re-routed."""
    if not sel:
        return 0.0, set()
    edges = steiner_tree(g, root, {prizes.node[i] for i in sel})
    street = sum(g[u][v]["length"] for u, v in edges)
    value, _ = prizes.set_value(sel)
    return value - street * cost_m - float(prizes.fixed_cost[sel].sum()), edges


def greedy_select(g: nx.Graph, root, prizes: Prizes, service_m: np.ndarray, cost_m: float,
                  max_iter: int = 500, initial: list[int] | None = None,
                  initial_edges: set | None = None) -> Selection:
    """Greedy PCST heuristic.

    Repeat: for every unconnected building, gain = Δ(operating value of the set) − cost of the
    shortest street path from the current tree − its fixed connection cost. Add the best
    building and its path; stop when no gain is positive. ``initial`` continues from an
    existing set (used by the local-search refinement).
    """
    n = len(prizes.margin)
    sel: list[int] = list(initial or [])
    res = Selection(method="greedy", selected=sel, tree_edges=set(initial_edges or set()))
    tree_nodes = {root} | {x for e in res.tree_edges for x in e}
    load = prizes.demand[sel].sum(axis=0) if sel else np.zeros(prizes.demand.shape[1])
    current = prizes.set_value(sel)[0]
    # standalone value bounds the marginal value when margins are positive: prune hopeless ones
    standalone = prizes.marginal_values([], np.zeros_like(load), np.arange(n))
    remaining = set(np.flatnonzero(standalone - prizes.fixed_cost > 0).tolist()) - set(sel)
    for _ in range(max_iter):
        if not remaining:
            break
        dist, paths = nx.multi_source_dijkstra(g, tree_nodes, weight="length")
        cand = np.array(sorted(i for i in remaining if prizes.node[i] in dist))
        if len(cand) == 0:
            break
        street = np.array([dist[prizes.node[i]] for i in cand])
        cost = street * cost_m + prizes.fixed_cost[cand]
        total = prizes.marginal_values(sel, load, cand)
        gain = total - current - cost
        j = int(np.argmax(gain))
        if gain[j] <= 0:
            break
        b = int(cand[j])
        path = paths[prizes.node[b]]
        res.tree_edges.update(_edge_key(u, v) for u, v in zip(path[:-1], path[1:]))
        tree_nodes.update(path)
        sel.append(b)
        remaining.discard(b)
        load = load + prizes.demand[b]
        res.log.append({"step": len(sel), "building": b, "gain_usd_yr": float(gain[j]),
                        "street_m_added": float(street[j]), "value_after": float(total[j])})
        current = float(total[j])
    return finalize(g, res, prizes, service_m, cost_m)


def refine_select(g: nx.Graph, root, prizes: Prizes, service_m: np.ndarray, cost_m: float,
                  max_rounds: int = 10) -> Selection:
    """Recommended method: greedy, then local search until no single move improves.

    Moves: (1) re-route the chosen set with a nearest-first Steiner tree (greedy adds in
    value order, which can leave detours); (2) drop the building whose removal raises the
    objective most; (3) continue greedy additions from the new tree. Never worse than greedy.
    """
    g0 = greedy_select(g, root, prizes, service_m, cost_m)
    g0 = finalize(g, g0, prizes, service_m, cost_m)
    best_sel, best_edges = list(g0.selected), set(g0.tree_edges)
    best_obj = g0.objective
    log = list(g0.log)
    for rnd in range(max_rounds):
        improved = False
        obj, edges = set_objective(g, root, prizes, best_sel, cost_m)          # re-route
        if obj > best_obj + 1e-6:
            log.append({"step": f"reroute r{rnd}", "gain_usd_yr": obj - best_obj})
            best_obj, best_edges, improved = obj, edges, True
        drops = [(set_objective(g, root, prizes, [x for x in best_sel if x != i], cost_m), i) for i in best_sel]
        if drops:
            (obj, edges), i = max(drops, key=lambda t: t[0][0])
            if obj > best_obj + 1e-6:
                log.append({"step": f"drop r{rnd}", "building": i, "gain_usd_yr": obj - best_obj})
                best_sel = [x for x in best_sel if x != i]
                best_obj, best_edges, improved = obj, edges, True
        more = greedy_select(g, root, prizes, service_m, cost_m, initial=best_sel, initial_edges=best_edges)
        more = finalize(g, more, prizes, service_m, cost_m)
        if more.objective > best_obj + 1e-6:
            log.append({"step": f"add r{rnd}", "added": more.selected[len(best_sel):],
                        "gain_usd_yr": more.objective - best_obj})
            best_sel, best_edges, best_obj, improved = list(more.selected), set(more.tree_edges), more.objective, True
        if not improved:
            break
    res = Selection(method="recommended", selected=best_sel, tree_edges=best_edges, log=log)
    res = finalize(g, res, prizes, service_m, cost_m)
    res.greedy_objective = g0.objective
    return res


def locked_selection(g: nx.Graph, base: Selection, prizes: Prizes, service_m: np.ndarray,
                     cost_m: float) -> Selection:
    """Re-cost a fixed network (same buildings, same pipes) under different assumptions."""
    res = Selection(method="locked", selected=list(base.selected), tree_edges=set(base.tree_edges))
    return finalize(g, res, prizes, service_m, cost_m)


def finalize(g: nx.Graph, res: Selection, prizes: Prizes, service_m: np.ndarray, cost_m: float) -> Selection:
    """Fill lengths, value and cost for a selection (shared by all methods)."""
    res.street_m = float(sum(g[u][v]["length"] for u, v in res.tree_edges))
    res.service_m = float(service_m[res.selected].sum()) if res.selected else 0.0
    res.operating_value, _ = prizes.set_value(res.selected)
    res.network_cost = res.street_m * cost_m + float(prizes.fixed_cost[res.selected].sum())
    return res


def served_by_building(demand_sel: np.ndarray, hourly) -> np.ndarray:
    """Split dispatched network supply (direct + storage) to buildings pro rata to hourly load.
    Network losses take their pro-rata share too, so buildings receive slightly less."""
    supply = (hourly["dc_direct"] + hourly["storage_discharge"]).to_numpy()
    load = hourly["demand"].to_numpy()
    f = np.where(load > 0, supply / np.maximum(load, 1e-12), 0.0)
    return demand_sel @ f
