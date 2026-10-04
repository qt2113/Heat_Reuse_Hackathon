"""Physical unit conversions (constants, not assumptions)."""
from __future__ import annotations

KBTU_TO_MWH: float = 0.000293071      # 1 kBtu = 0.293071 kWh
MMBTU_TO_MWH: float = 0.293071        # 1 MMBtu = 293.071 kWh
MWH_TO_MMBTU: float = 1.0 / MMBTU_TO_MWH
FT2_TO_M2: float = 0.09290304
KWH_PER_MWH: float = 1000.0
C_TO_K: float = 273.15
HOURS_PER_YEAR: int = 8760


def c_to_k(t_c: float) -> float:
    """Celsius → kelvin."""
    return t_c + C_TO_K
