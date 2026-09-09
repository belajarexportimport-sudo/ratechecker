"""
FedEx Calculator — Orkestrator (New Architecture)
==================================================
Menerima RateRequest, mengembalikan RateResult.

Semua business logic TIDAK BERUBAH dari calculator.py lama.
Perubahan hanya pada:
  - Signature: terima RateRequest, return RateResult (bukan dict)
  - Import path: menggunakan backend.carriers.fedex.*
  - Data surcharge detail masuk ke RateResult.extra / RateResult.notes

Kalau ada kebutuhan memanggil engine lama secara langsung (misal dari app.py
selama masa transisi), gunakan _calculate_raw() yang tetap mengembalikan dict.
"""

import os
import sys

# agar bisa dijalankan langsung (python calculator.py) tanpa PYTHONPATH khusus
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from backend.core.schemas import RateRequest, RateResult
from backend.carriers.fedex.rates import calculate_base, FedExRateError
from backend.carriers.fedex.surcharges.oda_opa import ODAOPALookup
from backend.carriers.fedex.surcharges.core import compute_oda_opa_charge, compute_demand_surcharge
import backend.carriers.fedex.surcharges.nonstandard as nonstandard_fees
import backend.carriers.fedex.surcharges.special_handling as special_handling_fees
from backend.carriers.fedex.rates.common import round_up_1000

_oda_opa_lookup = None


def _get_oda_opa_lookup():
    global _oda_opa_lookup
    if _oda_opa_lookup is None:
        _oda_opa_lookup = ODAOPALookup()
    return _oda_opa_lookup


def _calculate_raw(
    service, direction, country, weight_kg,
    leg_type="door_to_door",
    indonesia_postal_code=None, indonesia_city=None,
    foreign_postal_code=None,
    fuel_surcharge_pct=None,
    apply_demand_surcharge=True,
    apply_oda_opa=True,
    apply_minimum=True, round_invoice=True,
    packages=None, freight_units=None,
    special_handling=None,
    auto_switch_service=True,
    apply_dimensional_weight=True,
    discount_pct=None,
    rate_type="publish",
    demand_surcharge_as_of_date=None,
):
    """
    Logic IDENTIK dengan calculator.py lama.
    Mengembalikan dict (raw result) — digunakan oleh calculate() untuk
    membungkus ke RateResult.

    demand_surcharge_as_of_date : tanggal (datetime.date) utk cek apakah
        Demand Surcharge sudah efektif (2026-09-21) -> default None berarti
        pakai tanggal hari ini. Isi manual kalau mau quote utk tanggal
        pengiriman tertentu di masa depan.
    """
    service = service.upper()
    is_freight = service in ("IPF", "IEF")
    pre_notes = []
    switch_info = None
    cwt_detail = None
    input_weight_kg = weight_kg

    # ---- Auto-switch IP/IE -> IPF/IEF ----
    if not is_freight and packages and auto_switch_service:
        switch_info = nonstandard_fees.evaluate_packages_for_service_switch(service, packages)
        if switch_info["action"] == "switch":
            new_service = switch_info["new_service"]
            forced_lines = []
            for f in switch_info["forced_fee_preview"]:
                extra = ""
                if f["forced_label"]:
                    extra = (f" Kalau dipaksakan tetap {service}, akan kena "
                             f"{f['forced_label']} (IDR {f['forced_charge']:,.0f}/collie).")
                forced_lines.append(f"{f['label']}: {', '.join(f['reasons'])}.{extra}")
            pre_notes.append(
                f"Semua collie melebihi batas maksimum {service} -> service "
                f"OTOMATIS dialihkan dari {service} ke {new_service}. "
                + " | ".join(forced_lines)
            )
            freight_units = [
                {
                    "label": p.get("label", f"Collie {i + 1}"),
                    "length_cm": p["length_cm"],
                    "width_cm": p.get("width_cm"),
                    "height_cm": p.get("height_cm"),
                    "weight_kg": p["weight_kg"],
                    "non_stackable": False,
                }
                for i, p in enumerate(packages)
            ]
            weight_kg = sum(p["weight_kg"] for p in packages)
            packages = None
            service = new_service
            is_freight = True

    # ---- CWT / Dimensional Weight (IP/IE) ----
    if not is_freight and packages and apply_dimensional_weight:
        cwt_detail = nonstandard_fees.compute_shipment_chargeable_weight(packages)
        actual_sum = sum(p["weight_kg"] for p in packages)
        if abs(actual_sum - weight_kg) > 0.01:
            pre_notes.append(
                f"weight_kg input ({weight_kg}kg) berbeda dari total actual weight "
                f"packages ({actual_sum:.2f}kg) -> packages dipakai."
            )
        weight_kg = cwt_detail["total_chargeable_weight_kg"]
        pre_notes.append(
            f"Chargeable Weight (CWT) = {weight_kg:.2f}kg (per-package: "
            f"max(actual, DIM L*W*H/5000, floor 18kg jika AHS-Dimension))."
        )

    # ---- CWT / Dimensional Weight (IPF/IEF) ----
    elif is_freight and freight_units and apply_dimensional_weight:
        cwt_detail = nonstandard_fees.compute_freight_chargeable_weight(freight_units)
        actual_sum = sum(u["weight_kg"] for u in freight_units)
        if abs(actual_sum - weight_kg) > 0.01:
            pre_notes.append(
                f"weight_kg input ({weight_kg}kg) berbeda dari total freight_units "
                f"({actual_sum:.2f}kg) -> freight_units dipakai."
            )
        weight_kg = cwt_detail["total_chargeable_weight_kg"]
        pre_notes.append(
            f"Chargeable Weight (CWT) freight = {weight_kg:.2f}kg "
            f"(per-unit: max(actual, DIM L*W*H/5000), tanpa floor 18kg)."
        )

    base = calculate_base(
        service=service, direction=direction, country=country, weight_kg=weight_kg,
        leg_type=leg_type, apply_minimum=apply_minimum, round_invoice=False,
        postal_code=foreign_postal_code, rate_type=rate_type,
    )
    billed_weight = base["billed_weight_kg"]

    components = [{"label": "Base rate", "amount": base["price"]}]
    notes = pre_notes + list(base["notes"])

    # ---- Diskon (dari base rate saja) ----
    discount_detail = None
    if discount_pct:
        if not (0 < discount_pct < 100):
            raise ValueError("discount_pct harus di antara 0 dan 100 (eksklusif).")
        discount_amount = base["price"] * (discount_pct / 100.0)
        components.append({
            "label": f"Diskon Base Rate ({discount_pct}%)",
            "amount": -discount_amount,
        })
        discount_detail = {"pct": discount_pct, "amount": discount_amount}
        notes.append(
            f"Diskon {discount_pct}% dari Base Rate (IDR {base['price']:,.0f}) "
            f"= -IDR {discount_amount:,.0f}. Tidak berlaku ke surcharge."
        )

    # ---- ODA / OPA ----
    oda_opa_detail = None
    if apply_oda_opa:
        if indonesia_postal_code or indonesia_city:
            lookup = _get_oda_opa_lookup()
            res = lookup.lookup("Indonesia", postal_code=indonesia_postal_code, city=indonesia_city)
            if res["found"]:
                if direction == "export":
                    tier = res["tiers"]["freight_pickup" if is_freight else "parcel_pickup"]
                    charge_detail = compute_oda_opa_charge("opa", tier, billed_weight)
                else:
                    tier = res["tiers"]["freight_delivery" if is_freight else "parcel_delivery"]
                    charge_detail = compute_oda_opa_charge("oda", tier, billed_weight)
                oda_opa_detail = charge_detail
                if charge_detail["charge"] > 0:
                    components.append({
                        "label": f"{charge_detail['kind']} Surcharge (Tier {charge_detail['tier']})",
                        "amount": charge_detail["charge"],
                    })
            else:
                notes.append("Kode pos/kota Indonesia tidak ketemu di data ODA/OPA -> diasumsikan Rp0.")
        else:
            notes.append("indonesia_postal_code/city tidak diisi -> ODA/OPA tidak dicek (bisa under-estimate).")

        if foreign_postal_code:
            lookup = _get_oda_opa_lookup()
            res_f = lookup.lookup(country, postal_code=foreign_postal_code)
            if res_f["found"]:
                if direction == "export":
                    tier_f = res_f["tiers"]["freight_delivery" if is_freight else "parcel_delivery"]
                    charge_detail_f = compute_oda_opa_charge("oda", tier_f, billed_weight)
                else:
                    tier_f = res_f["tiers"]["freight_pickup" if is_freight else "parcel_pickup"]
                    charge_detail_f = compute_oda_opa_charge("opa", tier_f, billed_weight)
                if charge_detail_f["charge"] > 0:
                    components.append({
                        "label": f"{charge_detail_f['kind']} Surcharge - {res_f['country']} "
                                 f"(Tier {charge_detail_f['tier']})",
                        "amount": charge_detail_f["charge"],
                    })
            elif res_f["match_by"] == "country_not_listed":
                pass
            else:
                notes.append(
                    f"Kode pos '{foreign_postal_code}' di {country} tidak ketemu di data ODA/OPA."
                )
        else:
            notes.append(
                "foreign_postal_code tidak diisi -> ODA/OPA sisi tujuan/asal TIDAK dicek."
            )

    # ---- Demand Surcharge ----
    demand_detail = None
    if apply_demand_surcharge:
        demand_detail = compute_demand_surcharge(
            direction=direction, service=service,
            country_display_name=base["country"], weight_kg=billed_weight,
            as_of_date=demand_surcharge_as_of_date,
        )
        if demand_detail["applied"]:
            components.append({"label": "Demand Surcharge", "amount": demand_detail["charge"]})
        else:
            notes.append(demand_detail["reason"])

    # ---- Non-Standard Shipment Fees ----
    nonstandard_detail = None
    if is_freight:
        if freight_units:
            nonstandard_detail = nonstandard_fees.summarize_freight_units(freight_units)
    else:
        if packages:
            nonstandard_detail = nonstandard_fees.summarize_packages(packages)
    if nonstandard_detail:
        if nonstandard_detail["total_charge"] > 0:
            components.append({
                "label": "Non-Standard Shipment Fees",
                "amount": nonstandard_detail["total_charge"],
            })
        notes.extend(nonstandard_detail["notes"])
    else:
        notes.append(
            "packages/freight_units tidak diisi -> Non-Standard Fees tidak dicek (bisa under-estimate)."
        )

    # ---- Special Handling Fees ----
    special_handling_detail = None
    if special_handling:
        sh_kwargs = dict(special_handling)
        third_party_billing = sh_kwargs.pop("third_party_billing", False)
        oda_applied = bool(
            oda_opa_detail and oda_opa_detail.get("kind") == "ODA"
            and oda_opa_detail.get("charge", 0) > 0
        )
        special_handling_detail = special_handling_fees.compute_special_handling(
            service=service, direction=direction, country=base["country"],
            billed_weight_kg=billed_weight, oda_applied=oda_applied, **sh_kwargs,
        )
        for c in special_handling_detail["components"]:
            components.append(c)
        notes.extend(special_handling_detail["notes"])

        if third_party_billing:
            subtotal_before_tpb = sum(c["amount"] for c in components)
            tpb_charge = subtotal_before_tpb * (special_handling_fees.THIRD_PARTY_BILLING_PCT / 100.0)
            components.append({
                "label": f"Third Party Billing Surcharge ({special_handling_fees.THIRD_PARTY_BILLING_PCT}%)",
                "amount": tpb_charge,
            })

    # ---- Fuel Surcharge ----
    fuel_detail = None
    if fuel_surcharge_pct is not None:
        fuel_amount = base["price"] * (fuel_surcharge_pct / 100.0)
        fuel_detail = {"pct": fuel_surcharge_pct, "amount": fuel_amount}
        components.append({"label": f"Fuel Surcharge ({fuel_surcharge_pct}%)", "amount": fuel_amount})
    else:
        notes.append("fuel_surcharge_pct tidak diisi -> Fuel Surcharge tidak dihitung.")

    subtotal = sum(c["amount"] for c in components)

    return {
        "service": service,
        "direction": direction,
        "country": base["country"],
        "zone": base["zone"],
        "rate_type": base.get("rate_type", rate_type),
        "leg_type": base.get("leg_type"),
        "input_weight_kg": input_weight_kg,
        "billed_weight_kg": billed_weight,
        "base_rate_mode": base["mode"],
        "components": components,
        "subtotal": subtotal,
        "subtotal_invoice": round_up_1000(subtotal) if round_invoice else None,
        "oda_opa": oda_opa_detail,
        "demand_surcharge": demand_detail,
        "nonstandard_fees": nonstandard_detail,
        "special_handling_fees": special_handling_detail,
        "service_switch": switch_info,
        "chargeable_weight": cwt_detail,
        "discount": discount_detail,
        "fuel_surcharge": fuel_detail,
        "notes": notes,
        "currency": "IDR",
    }


def _expand_packages_qty(packages):
    """
    `packages` dari RateRequest.extra boleh pakai format kompak dengan key
    'qty' (N buah identik) — konvensi yang sama dipakai UPS calculator.py.
    Tapi `_calculate_raw()`/`nonstandard_fees.py` (kode lama, sebelum
    migrasi) mengasumsikan 1 dict = 1 collie fisik TANPA key 'qty' — kalau
    'qty' ikut ke-unpack ke check_package_surcharge(**pkg), itu crash
    (TypeError: unexpected keyword argument 'qty').

    Fungsi ini expand tiap dict ber-qty>1 jadi N dict individual (tanpa key
    'qty'), supaya kontrak lama tetap terpenuhi tanpa mengubah
    nonstandard_fees.py sama sekali.
    """
    if not packages:
        return packages
    expanded = []
    for i, pkg in enumerate(packages):
        pkg = dict(pkg)
        qty = int(pkg.pop("qty", 1) or 1)
        base_label = pkg.get("label", f"Collie {i + 1}")
        for n in range(qty):
            item = dict(pkg)
            if qty > 1:
                item["label"] = f"{base_label} ({n + 1}/{qty})"
            expanded.append(item)
    return expanded


def _synthesize_packages(request: RateRequest, extra: dict):
    """
    Kalau `extra['packages']` tidak diisi tapi `request.dimensions_cm` ADA,
    bangun 1 package sintetis dari weight_kg + dimensions_cm supaya CWT/
    dimensional-weight dan Non-Standard Fees tetap dicek -- BUKAN diam-diam
    di-skip.

    SEBELUM FIX INI: `request.dimensions_cm` TIDAK PERNAH dipakai sama
    sekali di seluruh calculator.py ini -- CWT & Non-Standard Fees (AHS-
    equivalent FedEx: oversize/overweight/non-cardboard packaging dkk) cuma
    jalan kalau caller eksplisit isi `extra['packages']` (format list-of-
    collie). Skenario paling umum (isi berat+dimensi 1 paket tanpa
    breakdown per-collie -- persis yang dikirim index.html trial UI)
    akan SELALU under-estimate. Pola bug yang sama juga ditemukan &
    diperbaiki di UPS (lihat AUDIT_UPS_COMMERCIAL.md).
    """
    packages = _expand_packages_qty(extra.get("packages"))
    if packages:
        return packages
    dim = request.dimensions_cm
    if dim and len(dim) == 3 and all(dim):
        return [{
            "weight_kg": request.weight_kg,
            "length_cm": dim[0],
            "width_cm": dim[1],
            "height_cm": dim[2],
            "label": "Pkg #1",
        }]
    return None


def calculate(request: RateRequest) -> RateResult:
    """
    Entry point utama (interface baru).
    Terima RateRequest, kembalikan RateResult.
    """
    # Ambil parameter FedEx-specific dari request.extra
    extra = request.extra or {}

    raw = _calculate_raw(
        service=request.service,
        direction=request.direction,
        country=request.destination_country if request.direction == "export" else request.origin_country,
        weight_kg=request.weight_kg,
        leg_type=extra.get("leg_type", "door_to_door"),
        indonesia_postal_code=extra.get("indonesia_postal_code"),
        indonesia_city=extra.get("indonesia_city"),
        foreign_postal_code=(
            request.postal_code_destination if request.direction == "export"
            else request.postal_code_origin
        ),
        fuel_surcharge_pct=extra.get("fuel_surcharge_pct"),
        apply_demand_surcharge=extra.get("apply_demand_surcharge", True),
        demand_surcharge_as_of_date=extra.get("demand_surcharge_as_of_date"),
        apply_oda_opa=extra.get("apply_oda_opa", True),
        apply_minimum=extra.get("apply_minimum", True),
        round_invoice=extra.get("round_invoice", True),
        packages=_synthesize_packages(request, extra),
        freight_units=extra.get("freight_units"),
        special_handling=extra.get("special_handling"),
        auto_switch_service=extra.get("auto_switch_service", True),
        apply_dimensional_weight=extra.get("apply_dimensional_weight", True),
        discount_pct=request.discount_pct,
        rate_type=request.rate_type,
    )

    # Bangun surcharges dict dari components (kecuali base rate & diskon)
    surcharges = {}
    discount_amount = 0.0
    base_price = 0.0
    for c in raw["components"]:
        lbl = c["label"]
        amt = c["amount"]
        if lbl == "Base rate":
            base_price = amt
        elif lbl.startswith("Diskon"):
            discount_amount = abs(amt)
        else:
            surcharges[lbl] = amt

    total = raw["subtotal_invoice"] if raw["subtotal_invoice"] is not None else raw["subtotal"]

    return RateResult(
        carrier="fedex",
        rate_type=raw["rate_type"],
        service=raw["service"],
        zone=str(raw["zone"]),
        base_price=base_price,
        surcharges=surcharges,
        discount=discount_amount,
        total=total,
        currency=raw["currency"],
        notes=raw["notes"],
        extra={
            "direction": raw["direction"],
            "country": raw["country"],
            "leg_type": raw["leg_type"],
            "input_weight_kg": raw["input_weight_kg"],
            "billed_weight_kg": raw["billed_weight_kg"],
            "base_rate_mode": raw["base_rate_mode"],
            "components": raw["components"],
            "subtotal": raw["subtotal"],
            "subtotal_invoice": raw["subtotal_invoice"],
            "chargeable_weight": raw["chargeable_weight"],
            "service_switch": raw["service_switch"],
        },
    )
