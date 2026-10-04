"""Greedy selection on toy graphs with hand-checkable answers."""
import networkx as nx
import numpy as np
import pytest

from src.network import Prizes, greedy_select, segmentize

H = 8760


def _graph() -> nx.Graph:
    # root(0) —100 m— 1 —100 m— 2 —1000 m— 3
    g = nx.Graph()
    for n in range(4):
        g.add_node(n, lat=0.0, lon=n * 0.001)
    for u, v, L in [(0, 1, 100.0), (1, 2, 100.0), (2, 3, 1000.0)]:
        g.add_edge(u, v, length=L, coords=[(u * 0.001, 0.0), (v * 0.001, 0.0)])
    return g


def _prizes(mw: list[float], margin: list[float], node: list[int], q_cap: float = 100.0) -> Prizes:
    n = len(mw)
    return Prizes(demand=np.array([[m] * H for m in mw]), margin=np.array(margin, float),
                  co2_cut=np.zeros(n), ll97_excess=np.zeros(n), penalty=0.0, fixed_cost=np.zeros(n),
                  node=np.array(node), q_cap=q_cap)


def test_greedy_picks_profitable_and_skips_far():
    # building at node 2: 1 MW × 8760 h × $10 = $87,600/yr vs 200 m × $100 = $20,000 → take
    # building at node 3: same prize, but extra 1,000 m × $100 = $100,000 → skip
    p = _prizes([1.0, 1.0], [10.0, 10.0], [2, 3])
    s = greedy_select(_graph(), 0, p, service_m=np.zeros(2), cost_m=100.0)
    assert s.selected == [0]
    assert s.street_m == pytest.approx(200.0)
    assert s.objective == pytest.approx(87_600 - 20_000)


def test_shared_path_is_paid_once():
    # two buildings on node 2: second one's path cost is zero once the first is connected
    p = _prizes([1.0, 0.1], [10.0, 10.0], [2, 2])
    s = greedy_select(_graph(), 0, p, service_m=np.zeros(2), cost_m=100.0)
    assert sorted(s.selected) == [0, 1] and s.street_m == pytest.approx(200.0)


def test_capacity_cap_makes_value_non_additive():
    # capacity 1 MW, each building needs 1 MW: the second adds no heat, so it is not connected
    p = _prizes([1.0, 1.0], [10.0, 10.0], [1, 1], q_cap=1.0)
    p.fixed_cost = np.array([1.0, 1.0])
    s = greedy_select(_graph(), 0, p, service_m=np.zeros(2), cost_m=1.0)
    assert len(s.selected) == 1


def test_negative_margin_never_connected():
    p = _prizes([5.0], [-1.0], [1])
    assert greedy_select(_graph(), 0, p, service_m=np.zeros(1), cost_m=0.0).selected == []


def test_segmentize_preserves_length():
    g = segmentize(_graph(), 40.0)
    assert sum(d["length"] for *_, d in g.edges(data=True)) == pytest.approx(1200.0)
    assert max(d["length"] for *_, d in g.edges(data=True)) <= 40.0
    assert nx.shortest_path_length(g, 0, 3, weight="length") == pytest.approx(1200.0)
