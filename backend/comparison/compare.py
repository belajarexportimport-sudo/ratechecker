"""
Comparison Engine — Phase 1: FedEx Publish vs Commercial
=========================================================
Menerima satu RateRequest dasar, memanggil beberapa kombinasi
(carrier, rate_type), dan mengembalikan list RateResult beserta ringkasan selisih.

Comparison layer TIDAK mengetahui internal FedEx maupun UPS.
Ia hanya menerima RateResult dan menyusun perbandingan dari field-field
yang ada di kontrak bersama (core/schemas.py).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from backend.core.schemas import RateRequest, RateResult
from backend.pricing.router import calculate, CARRIER_REGISTRY


@dataclass
class ComparisonResult:
    request_summary: dict
    results: list[RateResult] = field(default_factory=list)
    unavailable: list[dict] = field(default_factory=list)  # {carrier, rate_type, reason}
    cheapest: Optional[RateResult] = None


def compare(
    base_request: RateRequest,
    combinations: list[tuple[str, str]] | None = None,
) -> ComparisonResult:
    """
    Bandingkan beberapa kombinasi (carrier, rate_type) untuk satu shipment.

    Parameters
    ----------
    base_request : RateRequest
        Request dasar berisi info shipment (negara, berat, dll).
        Field `carrier` dan `rate_type` akan di-override per kombinasi.
    combinations : list of (carrier, rate_type)
        Contoh: [("fedex", "publish"), ("fedex", "commercial")]
        Default: semua rate_type untuk semua carrier yang tersedia di CARRIER_REGISTRY.

    Returns
    -------
    ComparisonResult
        Berisi list RateResult yang berhasil, list yang N/A, dan pointer ke termurah.
    """
    if combinations is None:
        # Default Phase 1: FedEx publish vs commercial
        combinations = [
            ("fedex", "publish"),
            ("fedex", "commercial"),
        ]

    results: list[RateResult] = []
    unavailable: list[dict] = []

    # base carrier to derive service mappings from
    base_carrier = base_request.carrier.lower()
    base_service  = base_request.service

    for carrier, rate_type in combinations:
        import copy
        from backend.comparison.service_mapping import map_service
        req = copy.copy(base_request)
        req.carrier = carrier
        req.rate_type = rate_type

        # Resolve service jika cross-carrier
        if carrier.lower() != base_carrier:
            mapped = map_service(base_carrier, carrier, base_service)
            if mapped is None:
                unavailable.append({
                    "carrier":   carrier,
                    "rate_type": rate_type,
                    "reason":    (
                        f"Tidak ada service mapping dari {base_carrier.upper()} "
                        f"'{base_service}' ke {carrier.upper()}. "
                        f"Update backend/comparison/service_mapping.py."
                    ),
                })
                continue
            req.service = mapped

        try:
            result = calculate(req)
            results.append(result)
        except Exception as e:
            unavailable.append({
                "carrier":   carrier,
                "rate_type": rate_type,
                "reason":    str(e),
            })

    # Cari yang termurah
    cheapest = min(results, key=lambda r: r.total) if results else None

    return ComparisonResult(
        request_summary={
            "service": base_request.service,
            "direction": base_request.direction,
            "origin_country": base_request.origin_country,
            "destination_country": base_request.destination_country,
            "weight_kg": base_request.weight_kg,
        },
        results=results,
        unavailable=unavailable,
        cheapest=cheapest,
    )


def format_comparison(cr: ComparisonResult) -> str:
    """Format ComparisonResult menjadi tabel teks sederhana."""
    lines = [
        "=" * 60,
        "COMPARISON RESULT",
        "=" * 60,
        f"Service   : {cr.request_summary['service']} ({cr.request_summary['direction'].upper()})",
        f"Tujuan    : {cr.request_summary['destination_country']}",
        f"Berat     : {cr.request_summary['weight_kg']} kg",
        "",
    ]

    if not cr.results and not cr.unavailable:
        lines.append("Tidak ada hasil.")
        return "\n".join(lines)

    # Header tabel
    col_w = 22
    headers = [f"{'Item':<20}"] + [
        f"{r.carrier.upper()} {r.rate_type.capitalize():>{col_w - len(r.carrier) - 1}}"
        for r in cr.results
    ]
    lines.append("  ".join(headers))
    lines.append("-" * (len("  ".join(headers)) + 4))

    # Kumpulkan semua label surcharge
    all_surcharge_keys: list[str] = []
    for r in cr.results:
        for k in r.surcharges:
            if k not in all_surcharge_keys:
                all_surcharge_keys.append(k)

    def _fmt(val) -> str:
        return f"IDR {val:>13,.0f}"

    def _row(label, values):
        cells = [f"{label:<20}"] + [_fmt(v) for v in values]
        return "  ".join(cells)

    lines.append(_row("Base Rate", [r.base_price for r in cr.results]))
    for key in all_surcharge_keys:
        lines.append(_row(key, [r.surcharges.get(key, 0) for r in cr.results]))
    lines.append(_row("Discount", [-r.discount for r in cr.results]))
    lines.append("-" * 60)
    lines.append(_row("TOTAL", [r.total for r in cr.results]))

    if len(cr.results) == 2:
        diff = cr.results[1].total - cr.results[0].total
        diff_pct = (diff / cr.results[0].total * 100) if cr.results[0].total else 0
        lines.append("")
        lines.append(f"Selisih   : IDR {diff:,.0f}  ({diff_pct:+.1f}%)")

    if cr.cheapest:
        lines.append(f"Termurah  : {cr.cheapest.carrier.upper()} {cr.cheapest.rate_type.capitalize()}")

    if cr.unavailable:
        lines.append("")
        lines.append("Tidak tersedia:")
        for u in cr.unavailable:
            lines.append(f"  - {u['carrier'].upper()} {u['rate_type']}: {u['reason']}")

    lines.append("=" * 60)
    return "\n".join(lines)
