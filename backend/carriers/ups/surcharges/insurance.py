"""
UPS Insurance / Declared Value Surcharge
=========================================
Ported dari "Calculate insurance UPS & FedEx.xlsx" (sheet "insurance"),
formula Excel:
    =IF(E2 <= E4, 0, CEILING((E2 - E4) / E4, 1) * E5)
    E2 = Nilai Barang (IDR)
    E4 = Batas Gratis UPS (IDR)  -- juga dipakai sebagai step CEILING
    E5 = Biaya Premi per Kelipatan (IDR)

Konstanta default (1.480.000 / 32.710) SUDAH ADA sebelumnya di
backend/carriers/ups/rules.py (OPTIONAL_COSTS["insurance_free_limit"] /
["insurance_unit_rate"]) tapi TIDAK PERNAH DIPAKAI di mana pun -- modul ini
menyambungkannya.
"""
from __future__ import annotations
import math

from backend.carriers.ups.rules import OPTIONAL_COSTS

INSURANCE_FREE_LIMIT_IDR = OPTIONAL_COSTS["insurance_free_limit"]  # 1,480,000
INSURANCE_UNIT_RATE_IDR = OPTIONAL_COSTS["insurance_unit_rate"]    # 32,710


def compute_insurance_surcharge(declared_value_idr: float,
                                 free_limit: float = None,
                                 unit_rate: float = None) -> dict:
    """
    Hitung UPS Insurance / Declared Value surcharge.

    declared_value_idr : nilai barang yang diasuransikan (IDR).
    free_limit / unit_rate : override manual (default: konstanta resmi di atas).

    Return: {"fee": int, "free_limit": float, "note": str}
    """
    free_limit = free_limit if free_limit is not None else INSURANCE_FREE_LIMIT_IDR
    unit_rate = unit_rate if unit_rate is not None else INSURANCE_UNIT_RATE_IDR

    if declared_value_idr <= free_limit:
        return {
            "fee": 0,
            "free_limit": free_limit,
            "note": f"Nilai barang IDR {declared_value_idr:,.0f} <= batas gratis "
                    f"IDR {free_limit:,.0f} -> Insurance gratis.",
        }

    units = math.ceil((declared_value_idr - free_limit) / free_limit)
    fee = units * unit_rate
    return {
        "fee": fee,
        "free_limit": free_limit,
        "note": f"Insurance: ceil((IDR {declared_value_idr:,.0f} - IDR {free_limit:,.0f}) "
                f"/ IDR {free_limit:,.0f}) = {units} unit x IDR {unit_rate:,.0f} = IDR {fee:,.0f}.",
    }
