"""
FedEx rate tables package.
"""
from backend.carriers.fedex.rates import publish, commercial
from backend.carriers.fedex.rates.common import FedExRateError

_RATE_TYPE_MODULES = {
    "publish":    publish,
    "promotional": publish,   # alias lama
    "commercial": commercial,
}

def calculate_base(service, direction, country, weight_kg,
                   leg_type="door_to_door", apply_minimum=True,
                   round_invoice=True, postal_code=None,
                   rate_type="publish"):
    rate_type = (rate_type or "publish").lower()
    module = _RATE_TYPE_MODULES.get(rate_type)
    if module is None:
        choices = ", ".join(repr(k) for k in _RATE_TYPE_MODULES)
        raise FedExRateError(f"rate_type {rate_type!r} tidak dikenal. Pilihan: {choices}.")
    return module.calculate_base(
        service=service, direction=direction, country=country, weight_kg=weight_kg,
        leg_type=leg_type, apply_minimum=apply_minimum, round_invoice=round_invoice,
        postal_code=postal_code,
    )
