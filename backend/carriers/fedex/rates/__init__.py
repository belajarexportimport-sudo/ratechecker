"""
FedEx rate tables package.
"""
from backend.carriers.fedex.rates.common import FedExRateError


def calculate_base(service, direction, country, weight_kg,
                   leg_type="door_to_door", apply_minimum=True,
                   round_invoice=True, postal_code=None,
                   rate_type="publish"):
    rate_type = (rate_type or "publish").lower()

    # Import publish/commercial di SINI (lazy), BUKAN eager di top-level modul
    # ini. Keduanya import balik `from backend.carriers.fedex.zones import
    # ...`, dan zones.py sendiri import FedExRateError/resolve_china_zone dari
    # rates.common. Kalau publish/commercial di-import eager di top-level
    # __init__.py package ini, maka SIAPAPUN yang import
    # backend.carriers.fedex.rates.common (termasuk zones.py) otomatis
    # memicu eksekusi __init__.py package rates -> import publish.py ->
    # publish.py butuh zones.py -> tapi zones.py masih pertengahan load (baru
    # sampai baris yang men-trigger ini) -> ImportError partially-initialized
    # module. Lazy import di sini memutus siklusnya tanpa mengubah behavior
    # publik modul ini sama sekali.
    from backend.carriers.fedex.rates import publish, commercial

    rate_type_modules = {
        "publish":    publish,
        "promotional": publish,   # alias lama
        "commercial": commercial,
    }
    module = rate_type_modules.get(rate_type)
    if module is None:
        choices = ", ".join(repr(k) for k in rate_type_modules)
        raise FedExRateError(f"rate_type {rate_type!r} tidak dikenal. Pilihan: {choices}.")
    return module.calculate_base(
        service=service, direction=direction, country=country, weight_kg=weight_kg,
        leg_type=leg_type, apply_minimum=apply_minimum, round_invoice=round_invoice,
        postal_code=postal_code,
    )
