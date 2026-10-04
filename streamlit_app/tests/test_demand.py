"""Demand profiles: energy conservation and unit conversions."""
import numpy as np
import pandas as pd
import pytest

from src.config import Config
from src.demand import annual_heat, dhw_shape, hourly_demand, smooth_circular, space_shape
from src.fetch import normalize_bbl, synthetic_weather
from src.units import KBTU_TO_MWH, MMBTU_TO_MWH


def test_unit_constants():
    assert KBTU_TO_MWH * 1000 == pytest.approx(MMBTU_TO_MWH)
    assert 1_000_000 * KBTU_TO_MWH == pytest.approx(293.071)      # 1 billion Btu = 293 MWh


def test_shapes_sum_to_one():
    temp = synthetic_weather(2023)
    assert space_shape(temp.to_numpy(), 18.0).sum() == pytest.approx(1.0)
    assert space_shape(temp.to_numpy(), 18.0, 24).sum() == pytest.approx(1.0)
    assert dhw_shape(temp.index.hour.to_numpy(), list(range(1, 25))).sum() == pytest.approx(1.0)


def test_smoothing_preserves_energy_and_lowers_peak():
    x = np.zeros(8760); x[100] = 24.0
    y = smooth_circular(x, 24)
    assert y.sum() == pytest.approx(24.0) and y.max() == pytest.approx(1.0)


def test_no_space_heat_above_base_temperature():
    temp = np.full(8760, 25.0); temp[0] = 10.0
    s = space_shape(temp, 18.0)
    assert s[0] == pytest.approx(1.0) and s[1:].sum() == 0


def _toy_buildings() -> pd.DataFrame:
    return pd.DataFrame({
        "property_name": ["A", "B", "C"], "primary_property_type": ["Multifamily Housing", "Office", "Hotel"],
        "gas_kbtu": [1e6, 0.0, 5e5], "steam_kbtu": [0.0, 2e6, 0.0], "oil_kbtu": [0.0, 0.0, 1e5],
        "gfa_ft2": [1e5, 2e5, 5e4], "bbl": ["1", "2", "3"],
    })


def test_annual_split_conserves_energy():
    cfg = Config.load()
    b = annual_heat(_toy_buildings(), cfg)
    np.testing.assert_allclose(b.annual_dhw_mwh + b.annual_space_mwh, b.annual_heat_mwh)
    # multifamily gas: 1e6 kBtu × 0.293071e-3 × 0.80 × (1 − 0.05)
    assert b.loc[0, "annual_heat_mwh"] == pytest.approx(1e6 * KBTU_TO_MWH * 0.80 * 0.95)
    assert b.loc[0, "annual_dhw_mwh"] / b.loc[0, "annual_heat_mwh"] == pytest.approx(0.28)


def test_hourly_rows_sum_to_annual():
    cfg = Config.load()
    b = annual_heat(_toy_buildings(), cfg)
    d = hourly_demand(b, synthetic_weather(2023), cfg)
    assert d.shape == (3, 8760)
    np.testing.assert_allclose(d.sum(axis=1), b.annual_heat_mwh, rtol=1e-12)


@pytest.mark.parametrize("raw,expected", [
    ("1007390001", ["1007390001"]), ("1-00078-7506", ["1000787506"]),
    ("1007140031;1007150010", ["1007140031", "1007150010"]), (None, []), ("junk", []),
])
def test_normalize_bbl(raw, expected):
    assert normalize_bbl(raw) == expected
