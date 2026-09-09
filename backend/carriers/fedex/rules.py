"""
FedEx Business Rules
=====================
Berisi aturan-aturan bisnis FedEx yang dipakai oleh calculator.py:
  - Konstanta batas berat/dimensi IP/IE vs IPF/IEF
  - Dimensional weight divisor (5000)
  - Minimum weight
  - CWT calculation delegation (ke surcharges.nonstandard)
  - Service auto-switch (IP->IPF, IE->IEF)

Logic sebenarnya tetap di nonstandard.py (agar tidak ada duplikasi),
rules.py hanya re-export konstanta dan menyediakan helper level-tinggi.
"""

from backend.carriers.fedex.surcharges.nonstandard import (
    IPIE_MAX_WEIGHT_KG,
    IPIE_MAX_LENGTH_CM,
    IPIE_MAX_LENGTH_PLUS_GIRTH_CM,
    ShipmentSplitRequired,
    evaluate_packages_for_service_switch,
    compute_shipment_chargeable_weight,
    compute_freight_chargeable_weight,
)

DIM_DIVISOR = 5000          # berlaku untuk IP/IE dan IPF/IEF (dikonfirmasi 7 Sep 2026)
MINIMUM_BILLED_WEIGHT_KG = 0.5  # minimum billable weight FedEx

FREIGHT_SERVICES = {"IPF", "IEF"}
PARCEL_SERVICES  = {"IP", "IE"}

def is_freight(service: str) -> bool:
    return service.upper() in FREIGHT_SERVICES
