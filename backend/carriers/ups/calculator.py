"""
UPS Calculator — Orchestrator
==============================
Menerima RateRequest, mengembalikan RateResult.

Flow:
  RateRequest
    -> Validate direction/service
    -> Zone lookup (zones.py)
    -> Per-package: DIM weight, CWT, surcharges (rules.py)
    -> Rate lookup (rates/publish.py atau rates/commercial.py)
    -> FSI (fuel surcharge)
    -> Surge fee
    -> Optional surcharges
    -> Discount (base rate only)
    -> VAT 1.1%
    -> Return RateResult

Perbedaan utama dari FedEx:
  - Zone = integer 1-10
  - Rate bisa flat (<=20kg) atau per-kg (>20kg/WWEF)
  - FSI = % dari (subtotal - brokerage)
  - VAT 1.1% selalu ditambahkan
  - Surge fee per kg (Middle East, Europe, dll.)
  - A26/B26 = commercial rate card (rates/commercial.py)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from backend.core.schemas import RateRequest, RateResult
from backend.carriers.ups.zones import get_zone, UPSZoneError, is_china_southern
from backend.carriers.ups.rules import (
    evaluate_package, PackageResult,
    get_surge_region,
    BROKERAGE_IMPORT, OPTIONAL_COSTS,
    AHS_COST, LPS_COST, OMX_COST,
)
from backend.carriers.ups.rates.publish import lookup_rate, RATES


class UPSRateError(Exception):
    pass


def _get_rate_module(rate_type: str):
    """Return rate module sesuai rate_type."""
    rt = rate_type.lower()
    if rt in ("publish", "standard"):
        from backend.carriers.ups.rates import publish
        return publish
    if rt in ("commercial", "a26", "b26"):
        try:
            from backend.carriers.ups.rates import commercial
            return commercial
        except ImportError:
            from backend.carriers.ups.rates import publish
            return publish
    raise UPSRateError(f"rate_type '{rate_type}' tidak dikenal untuk UPS.")


def calculate(request: RateRequest) -> RateResult:
    """
    Entry point utama UPS engine.
    Menerima RateRequest, mengembalikan RateResult.
    """
    extra = request.extra or {}

    direction = request.direction.lower()
    service   = request.service.lower()   # "saver" | "expedited" | "wwef" | "envelope"
    is_wwef   = service == "wwef"

    # Negara yang relevan (tujuan kalau export, asal kalau import)
    if direction == "export":
        country = request.destination_country
        postal_code = request.postal_code_destination
    else:
        country = request.origin_country
        postal_code = request.postal_code_origin

    # ── 1. Zone lookup ─────────────────────────────────────────────────────
    try:
        zone = get_zone(country, direction, service, postal_code=postal_code)
    except UPSZoneError as e:
        raise UPSRateError(str(e))

    if zone is None:
        raise UPSRateError(
            f"Service '{service}' ({direction}) tidak tersedia untuk {country}. "
            f"Rate N/A."
        )

    # ── 2. Per-package evaluation ──────────────────────────────────────────
    packages = extra.get("packages") or []
    pkg_results: list[PackageResult] = []
    total_chargeable = 0.0
    total_pkg_surcharge = 0.0
    pkg_surcharge_components = []
    notes = []

    if packages:
        for i, pkg in enumerate(packages):
            qty = pkg.get("qty", 1)
            pr = evaluate_package(
                weight_kg    = pkg.get("weight_kg", request.weight_kg),
                length_cm    = pkg.get("length_cm", 0),
                width_cm     = pkg.get("width_cm", 0),
                height_cm    = pkg.get("height_cm", 0),
                packing_type = pkg.get("packing_type", "box"),
                label        = pkg.get("label", f"Pkg #{i+1}"),
                is_wwef      = is_wwef,
            )
            pkg_results.append(pr)
            total_chargeable += pr.chargeable_weight * qty
            if pr.surcharge_cost > 0:
                total_pkg_surcharge += pr.surcharge_cost * qty
                pkg_surcharge_components.append({
                    "label": f"{pr.label} (x{qty}): {pr.surcharge_type} ({', '.join(pr.reasons)})",
                    "amount": pr.surcharge_cost * qty,
                })
    else:
        # Tanpa packages detail: pakai weight_kg langsung
        dim = request.dimensions_cm
        dim_weight = 0.0
        if dim and len(dim) == 3:
            from backend.carriers.ups.rules import DIM_DIVISOR
            dim_weight = (dim[0] * dim[1] * dim[2]) / DIM_DIVISOR
        total_chargeable = max(request.weight_kg, dim_weight)
        notes.append(
            "packages tidak diisi -> DIM weight dihitung dari dimensions_cm jika ada, "
            "AHS/LPS/OMX tidak dicek (bisa under-estimate)."
        )

    # ── 3. Weight rounding ─────────────────────────────────────────────────
    # Flat (<=20kg): round ke 0.5 kg; Per-kg / WWEF: round ke atas 1kg
    if is_wwef or total_chargeable > 20:
        import math
        total_chargeable = math.ceil(total_chargeable)
        rate_mode = "perkg"
    else:
        total_chargeable = round((total_chargeable * 2 + 0.9999) // 1 / 2, 1)
        rate_mode = "flat"

    # ── 4. Rate lookup ─────────────────────────────────────────────────────
    rate_module = _get_rate_module(request.rate_type)
    lookup_kwargs = dict(rate_type=request.rate_type)
    if rate_module.__name__.endswith(".commercial"):
        # A26/B26 punya named-group override per negara (lihat commercial.py) —
        # publish.lookup_rate tidak menerima kwarg ini, jadi hanya dikirim
        # kalau rate_module memang commercial.
        lookup_kwargs["country"] = country
    rate, mode = rate_module.lookup_rate(
        direction, 
        service, 
        zone, 
        total_chargeable, 
        **lookup_kwargs,
    )

    if rate is None:
        raise UPSRateError(
            f"Rate tidak ditemukan untuk {direction}/{service}/zone={zone}/{total_chargeable}kg."
        )

    # Override mode dari lookup (lebih akurat dari heuristic)
    rate_mode = mode

    # ── 5. Base cost ────────────────────────────────────────────────────────
    discount_pct = request.discount_pct or 0.0
    discounted_rate = rate * (1 - discount_pct / 100.0)

    if rate_mode == "flat":
        base_cost = discounted_rate
    else:
        base_cost = discounted_rate * total_chargeable

    # WWEF minimum check
    if is_wwef:
        min_rate = RATES.get(direction, {}).get("wwef", {}).get(zone, {}).get("min")
        if min_rate:
            discounted_min = min_rate * (1 - discount_pct / 100.0)
            if base_cost < discounted_min:
                base_cost = discounted_min
                notes.append(
                    f"WWEF Minimum Charge applied: zone {zone} minimum "
                    f"IDR {min_rate:,.0f} (after {discount_pct}% discount = IDR {discounted_min:,.0f})."
                )

    # ── 6. Brokerage (import) ───────────────────────────────────────────────
    surcharges: dict[str, float] = {}
    brokerage = 0.0
    if direction == "import":
        brokerage = BROKERAGE_IMPORT
        surcharges["Additional Brokerage Import"] = brokerage

    # ── 7. Package surcharges (AHS/LPS/OMX) ────────────────────────────────
    for comp in pkg_surcharge_components:
        surcharges[comp["label"]] = comp["amount"]

    # ── 8. Surge fee ───────────────────────────────────────────────────────
    billing_wt_for_surge = int(total_chargeable + 0.9999)  # ceil ke integer
    surge_region, surge_rate = get_surge_region(country, direction)
    if surge_rate > 0:
        surge_amount = surge_rate * billing_wt_for_surge
        surcharges[f"Surge Fee ({surge_region.replace('_',' ').title()})"] = surge_amount
        notes.append(f"Surge Fee: {surge_region} = IDR {surge_rate:,}/kg x {billing_wt_for_surge}kg.")

    # ── 9. Optional surcharges ─────────────────────────────────────────────
    optional = extra.get("optional") or {}

    if optional.get("extended_area"):
        mult = optional.get("extended_area_multiplier", 1)
        ea_cost = max(
            OPTIONAL_COSTS["extended_area_min"],
            OPTIONAL_COSTS["extended_area_kg"] * total_chargeable,
        ) * mult
        surcharges[f"Extended Area{'(x2)' if mult > 1 else ''}"] = ea_cost

    if optional.get("remote_area"):
        mult = optional.get("remote_area_multiplier", 1)
        ra_cost = max(
            OPTIONAL_COSTS["remote_area_min"],
            OPTIONAL_COSTS["remote_area_kg"] * total_chargeable,
        ) * mult
        surcharges[f"Remote Area{'(x2)' if mult > 1 else ''}"] = ra_cost

    if optional.get("peb"):
        surcharges["PEB"] = OPTIONAL_COSTS["peb"]
    if optional.get("residential"):
        surcharges["Residential (WWEF)" if is_wwef else "Residential"] = (
            OPTIONAL_COSTS["residential_wwef"] if is_wwef else OPTIONAL_COSTS["residential"]
        )
    if optional.get("adult_signature"):
        surcharges["Adult Signature"] = OPTIONAL_COSTS["adult_signature"]
    if optional.get("delivery_confirmation"):
        surcharges["Delivery Confirmation"] = OPTIONAL_COSTS["delivery_confirm"]
    if optional.get("alternate_broker"):
        surcharges["Alternate Broker"] = OPTIONAL_COSTS["alternate_broker"]
    if optional.get("duty_tax_forward"):
        surcharges["Duty Tax Forward"] = OPTIONAL_COSTS["duty_tax_forward"]
    if optional.get("ipf"):
        surcharges["IPF"] = OPTIONAL_COSTS["ipf"]
    if optional.get("paper_invoice"):
        surcharges["Paper Invoice"] = OPTIONAL_COSTS["paper_invoice"]

    # ── 10. FSI (Fuel Surcharge Index) ────────────────────────────────────
    fsi_pct = extra.get("fsi_pct") or 0.0
    fsi_amount = 0.0
    if fsi_pct > 0:
        fsi_base = base_cost + sum(v for k, v in surcharges.items()
                                   if "Brokerage" not in k)
        fsi_amount = fsi_base * (fsi_pct / 100.0)
        surcharges[f"FSI ({fsi_pct}%)"] = fsi_amount
    else:
        notes.append("fsi_pct tidak diisi -> FSI tidak dihitung (cek rate mingguan di ups.com).")

    # ── 11. VAT 1.1% ──────────────────────────────────────────────────────
    subtotal_before_vat = base_cost + sum(surcharges.values())
    vat_amount = subtotal_before_vat * 0.011
    surcharges["VAT (1.1%)"] = round(vat_amount)

    total = base_cost + sum(surcharges.values())

    # ── 12. Bangun RateResult ──────────────────────────────────────────────
    return RateResult(
        carrier="ups",
        rate_type=request.rate_type,
        service=service,
        zone=str(zone),
        base_price=round(base_cost),
        surcharges={k: round(v) for k, v in surcharges.items()},
        discount=round(rate * (discount_pct / 100.0) * (total_chargeable if rate_mode == "perkg" else 1)),
        total=round(total),
        currency="IDR",
        notes=notes,
        extra={
            "direction":          direction,
            "country":            country,
            "zone_int":           zone,
            "rate_mode":          rate_mode,
            "list_rate":          rate,
            "discount_pct":       discount_pct,
            "total_chargeable_kg": total_chargeable,
            "billing_wt_surge":   billing_wt_for_surge,
            "pkg_details":        [
                {
                    "label":            pr.label,
                    "actual_kg":        pr.actual_weight,
                    "dim_kg":           pr.dim_weight,
                    "chargeable_kg":    pr.chargeable_weight,
                    "surcharge_type":   pr.surcharge_type,
                }
                for pr in pkg_results
            ],
        },
    )
