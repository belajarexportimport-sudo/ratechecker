"""
FedEx Insurance / Declared Value Surcharge
=============================================
Ported dari "Calculate insurance UPS & FedEx.xlsx" (sheet "insurance"),
formula Excel:
    =IF(B2 <= MAX(B4, (B3*2.20462)*B5), 0,
        CEILING((B2 - MAX(B4, (B3*2.20462)*B5)) / B4, 1) * B6)
    B2 = Nilai Barang (IDR)
    B3 = Berat Barang (kg)
    B4 = Batas Minimum (IDR)        -- juga dipakai sebagai step CEILING
    B5 = Rate Berat per Lbs (IDR)
    B6 = Biaya Premi per Kelipatan (IDR)
    FreeCoverage = MAX(B4, berat_lbs x B5)

Belum ada modul insurance FedEx sebelumnya sama sekali (beda dari UPS yang
setidaknya sudah punya konstanta tak terpakai) -- modul ini baru.
"""
from __future__ import annotations
import math

KG_TO_LBS = 2.20462

INSURANCE_MIN_LIMIT_IDR = 1_375_000
INSURANCE_RATE_PER_LBS_IDR = 125_000
INSURANCE_UNIT_RATE_IDR = 34_000


def compute_insurance_surcharge(declared_value_idr: float, weight_kg: float,
                                 min_limit: float = None,
                                 rate_per_lbs: float = None,
                                 unit_rate: float = None) -> dict:
    """
    Hitung FedEx Insurance / Declared Value surcharge.

    declared_value_idr : nilai barang yang diasuransikan (IDR).
    weight_kg           : berat aktual shipment (kg).
    min_limit / rate_per_lbs / unit_rate : override manual (default: konstanta
        resmi di atas, dari Calculate insurance UPS & FedEx.xlsx).

    Return: {"fee": int, "free_coverage": float, "note": str}
    """
    min_limit = min_limit if min_limit is not None else INSURANCE_MIN_LIMIT_IDR
    rate_per_lbs = rate_per_lbs if rate_per_lbs is not None else INSURANCE_RATE_PER_LBS_IDR
    unit_rate = unit_rate if unit_rate is not None else INSURANCE_UNIT_RATE_IDR

    weight_kg = weight_kg if weight_kg and weight_kg > 0 else 0
    weight_coverage = weight_kg * KG_TO_LBS * rate_per_lbs
    free_coverage = max(min_limit, weight_coverage)

    if declared_value_idr <= free_coverage:
        return {
            "fee": 0,
            "free_coverage": free_coverage,
            "note": f"Nilai barang IDR {declared_value_idr:,.0f} <= MAX(batas minimum "
                    f"IDR {min_limit:,.0f}, {weight_kg}kg x {KG_TO_LBS} x IDR "
                    f"{rate_per_lbs:,.0f}) = IDR {free_coverage:,.0f} -> Insurance gratis.",
        }

    units = math.ceil((declared_value_idr - free_coverage) / min_limit)
    fee = units * unit_rate
    return {
        "fee": fee,
        "free_coverage": free_coverage,
        "note": f"Insurance: ceil((IDR {declared_value_idr:,.0f} - IDR {free_coverage:,.0f}) "
                f"/ IDR {min_limit:,.0f}) = {units} unit x IDR {unit_rate:,.0f} = IDR {fee:,.0f}.",
    }
