"""Units, COP and dispatch energy balance."""
import numpy as np
import pytest

from src.config import Config
from src.supply import HeatPump, dispatch, heat_pump_cop, outage_mask


@pytest.fixture
def cfg() -> Config:
    return Config.load()


def test_cop_uses_kelvin():
    # 30 °C → 75 °C, eta 0.4: 0.4 × 348.15 / 45 = 3.0947
    assert heat_pump_cop(30.0, 75.0, 0.40) == pytest.approx(0.4 * 348.15 / 45.0)


def test_cop_calibration_matches_grundfos_case():
    # Grundfos reference: 16–25 °C source → 60–75 °C, measured COP 2.95. With mid-range
    # temperatures, eta = 0.40 must reproduce it within ±5 %.
    cop = heat_pump_cop((16 + 25) / 2, (60 + 75) / 2, 0.40)
    assert cop == pytest.approx(2.95, rel=0.05)


def test_cop_rejects_no_lift():
    with pytest.raises(ValueError):
        heat_pump_cop(60.0, 50.0, 0.4)


def test_heat_pump_first_law(cfg):
    hp = HeatPump.from_config(cfg)
    # condenser heat = evaporator heat + compressor work
    assert hp.q_delivered_mw == pytest.approx(hp.q_src_mw + hp.p_elec_mw)
    assert hp.q_delivered_mw / hp.p_elec_mw == pytest.approx(hp.cop)


def _profile() -> np.ndarray:
    t = np.arange(8760)
    return 6.0 + 4.0 * np.cos(2 * np.pi * t / 8760) + 1.5 * np.sin(2 * np.pi * t / 24)


@pytest.mark.parametrize("ov", [
    {}, {"supply.storage_mwh": 0.0}, {"supply.storage_mwh": 200.0},
    {"supply.outage_hours": 300}, {"supply.q_src_mw": 1.0}, {"supply.q_src_mw": 20.0},
])
def test_dispatch_energy_balance_every_hour(cfg, ov):
    c = cfg.with_overrides(ov)
    load = _profile()
    r = dispatch(load, c, network_loss_mw=0.2)
    h = r.hourly
    np.testing.assert_allclose(h.dc_direct + h.storage_discharge + h.backup, load + 0.2, atol=1e-9)
    assert (h[["dc_direct", "storage_charge", "storage_discharge", "backup", "soc"]] >= -1e-12).all().all()
    assert (h.dc_direct + h.storage_charge <= h.available + 1e-9).all()       # HP capacity
    assert (h.soc <= c.v("supply.storage_mwh") + 1e-9).all()                   # tank capacity
    # periodic year: what goes into the tank comes out or is lost
    assert h.storage_charge.sum() - h.storage_discharge.sum() - h.storage_loss.sum() == pytest.approx(0, abs=1e-6)


def test_no_supply_during_outage(cfg):
    r = dispatch(_profile(), cfg.with_overrides({"supply.outage_hours": 100, "supply.storage_mwh": 0.0}))
    h = r.hourly
    assert h.outage.sum() == 100
    assert (h.loc[h.outage, "dc_direct"] == 0).all()


def test_outage_mask_wraps_year_end():
    load = np.zeros(8760); load[5] = 1.0                     # peak in hour 5
    m = outage_mask(load, 24, "peak")
    assert m.sum() == 24 and m[0] and m[-1]


def test_storage_helps_when_capacity_exceeds_night_load(cfg):
    c0 = cfg.with_overrides({"supply.storage_mwh": 0.0, "supply.q_src_mw": 4.0})
    c1 = cfg.with_overrides({"supply.storage_mwh": 50.0, "supply.q_src_mw": 4.0})
    load = _profile()
    assert dispatch(load, c1).summary["backup_mwh"] < dispatch(load, c0).summary["backup_mwh"]
