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

# UPS commercial (lihat AUDIT_UPS_COMMERCIAL.md): B26 tidak lagi default
# diam-diam. Kalau caller minta combo ("ups", "commercial") TANPA tier
# eksplisit (rate_type literal "a26"/"b26", atau extra["ups_tier"]), compare()
# meng-expand combo itu jadi 2 baris hasil (A26 & B26) supaya keduanya SELALU
# muncul berdampingan -- bukan salah satu "menang" diam-diam sbg default.
_UPS_COMMERCIAL_TIERS = ("a26", "b26")


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
    combinations : list of (carrier, rate_type) atau (carrier, rate_type, extra)
        Contoh: [("fedex", "publish"), ("fedex", "commercial")]
        Elemen ke-3 (dict) opsional berisi override untuk RateRequest.extra,
        mis. ("ups", "commercial", {"ups_tier": "a26"}) untuk memilih tier
        eksplisit. Kalau combo UPS commercial TIDAK menyertakan tier eksplisit
        (baik lewat elemen ke-3 maupun rate_type="a26"/"b26" langsung),
        combo itu di-expand otomatis jadi 2 baris hasil (A26 & B26) -- lihat
        AUDIT_UPS_COMMERCIAL.md, B26 tidak lagi default diam-diam.
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

    import copy
    from backend.comparison.service_mapping import map_service

    def _build_request(carrier, rate_type, extra_override):
        req = copy.copy(base_request)
        req.carrier = carrier
        req.rate_type = rate_type
        if extra_override:
            req.extra = dict(base_request.extra or {})
            req.extra.update(extra_override)

        if carrier.lower() != base_carrier:
            mapped = map_service(base_carrier, carrier, base_service)
            if mapped is None:
                return None, (
                    f"Tidak ada service mapping dari {base_carrier.upper()} "
                    f"'{base_service}' ke {carrier.upper()}. "
                    f"Update backend/comparison/service_mapping.py."
                )
            req.service = mapped
        return req, None

    def _run(carrier, rate_type, extra_override=None, label=None):
        """Hitung 1 combo, append ke results/unavailable. `label` (opsional)
        dipakai utk override rate_type yang ditampilkan di RateResult, supaya
        combo yang di-expand (A26 vs B26) tetap bisa dibedakan pemanggil."""
        req, err = _build_request(carrier, rate_type, extra_override)
        if err:
            unavailable.append({"carrier": carrier, "rate_type": label or rate_type, "reason": err})
            return
        try:
            result = calculate(req)
            if label:
                result.rate_type = label
            results.append(result)
        except Exception as e:
            unavailable.append({
                "carrier":   carrier,
                "rate_type": label or rate_type,
                "reason":    str(e),
            })

    for combo in combinations:
        carrier, rate_type = combo[0], combo[1]
        combo_extra = combo[2] if len(combo) > 2 else None

        is_generic_ups_commercial = (
            carrier.lower() == "ups"
            and rate_type.lower() == "commercial"
            and not (combo_extra and combo_extra.get("ups_tier"))
        )
        if is_generic_ups_commercial:
            # Tidak ada tier eksplisit -> tampilkan A26 & B26 berdampingan,
            # bukan salah satu jadi default diam-diam.
            for tier in _UPS_COMMERCIAL_TIERS:
                _run(carrier, tier, combo_extra, label=f"commercial_{tier}")
        else:
            _run(carrier, rate_type, combo_extra)

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
