"""
Pricing Router
==============
Satu-satunya tempat yang tahu daftar carrier yang tersedia.
Nambah carrier baru = tambah 1 baris di CARRIER_REGISTRY + 1 entry di __init__.py carriers.

Percabangan carrier HANYA boleh ada di sini.
"""

from backend.core.schemas import RateRequest, RateResult
from backend.carriers.fedex import calculator as fedex_calculator
from backend.carriers.ups import calculator as ups_calculator

CARRIER_REGISTRY = {
    "fedex": fedex_calculator,
    "ups":   ups_calculator,
}



def calculate(request: RateRequest) -> RateResult:
    """
    Route request ke calculator carrier yang sesuai.
    Satu-satunya titik percabangan carrier di seluruh codebase.
    """
    carrier = request.carrier.lower()
    calculator = CARRIER_REGISTRY.get(carrier)
    if calculator is None:
        supported = ", ".join(repr(k) for k in CARRIER_REGISTRY)
        raise ValueError(f"Carrier {carrier!r} belum didukung. Carrier tersedia: {supported}.")
    return calculator.calculate(request)
