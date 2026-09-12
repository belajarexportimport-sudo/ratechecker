"""
UPS Business Rules
==================
Aturan-aturan bisnis UPS yang BERBEDA dari FedEx:
  - DIM divisor: 5000 (sama)
  - Weight rounding: nearest 0.5kg (flat) atau nearest 1kg (per-kg/WWEF)
  - WWEF minimum per package: 71kg
  - AHS trigger: berat >25kg (bukan >32kg seperti blueprint lama), L>122cm, W>76cm, non-standard packing
  - LPS trigger: girth (L + 2W + 2H) > 300cm
  - OMX trigger: weight>70kg OR L>274cm OR (L+G)>400cm
  - LPS/OMX: minimum chargeable weight 40kg
  - Diskon hanya dari base rate (bukan dari surcharge)

Semua konstanta surcharge per 2026 (COSTS_MAY_24_2026).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

DIM_DIVISOR = 5000

# ── Surcharge cost (efektif Mei 2026) ────────────────────────────────────────
AHS_COST      = 280016   # per package
LPS_COST      = 1058200  # per package
OMX_COST      = 4121800  # per package (+ LPS juga berlaku)
BROKERAGE_IMPORT = 118647  # per shipment (import only)

# Surge fee (COSTS_MAY_24_2026 / SURGE_V3) — per kg, export & import beda
SURGE_EXPORT = {
    "uae_israel":   48840,
    "middle_east":  43660,
    "europe":        7400,
    "americas":      7400,
    "asia_pacific":  1480,
    "rest_ismea":    7400,
    "others":        7400,
}
SURGE_IMPORT = {
    "uae_israel":   48840,
    "middle_east":  43660,
    "us":            7400,
    "asia_pacific":  1480,
    "europe":           0,
    "americas":         0,
    "rest_ismea":       0,
    "others":           0,
}

# Optional surcharge costs (Mei 2026)
OPTIONAL_COSTS = {
    "extended_area_min": 429792,
    "extended_area_kg":    8288,
    "remote_area_min":   479964,
    "remote_area_kg":      9472,
    "peb":               190189,
    "residential":        58312,   # Saver/Expedited
    "residential_wwef": 1879600,   # Per AWB
    "adult_signature":    71040,
    "delivery_confirm":   37740,
    "alternate_broker":  429502,
    "duty_tax_forward":  310060,
    "ipf":                37000,
    "paper_invoice":     370000,
    "insurance_free_limit": 1480000,
    "insurance_unit_rate":    32710,
    # Ditambahkan 12 Sep 2026 (UPS Rate & Service Guide Indonesia, efektif
    # 7 Jun 2026) -- sebelumnya checkbox "UPS Carbon Offsets" di frontend
    # sudah ada tapi belum ada datanya sama sekali di backend manapun.
    "carbon_offset_package": 11690,     # per package (non-freight)
    "carbon_offset_pallet":  311980,    # per pallet (UPS Worldwide Express Freight)
}

# ── Region classification ─────────────────────────────────────────────────────
UAE_ISRAEL = {"israel", "united arab emirates", "uae"}

MIDDLE_EAST_COUNTRIES = {
    "afghanistan", "bahrain", "bangladesh", "egypt", "iraq",
    "jordan", "kuwait", "lebanon", "nepal", "oman",
    "pakistan", "qatar", "saudi arabia", "sri lanka",
}

ASIA_PACIFIC = {
    "american samoa", "australia", "brunei", "cambodia", "china mainland",
    "china", "cn southern", "fiji", "french polynesia", "guam", "hong kong sar",
    "hong kong", "india", "indonesia", "japan", "south korea", "korea",
    "laos", "malaysia", "myanmar", "mongolia", "macau sar", "macau",
    "new caledonia", "new zealand", "northern mariana islands", "philippines",
    "singapore", "samoa", "thailand", "taiwan", "vietnam",
}

EUROPE = {
    "albania", "andorra", "armenia", "austria", "belarus", "belgium",
    "bosnia and herzegovina", "bulgaria", "croatia", "cyprus", "czech republic",
    "denmark", "estonia", "finland", "france", "georgia", "germany",
    "gibraltar", "greece", "guernsey", "hungary", "iceland", "ireland",
    "italy", "jersey", "channel islands", "kosovo", "latvia", "lithuania",
    "luxembourg", "malta", "moldova", "montenegro", "netherlands",
    "north macedonia", "norway", "poland", "portugal", "romania", "russia",
    "san marino", "serbia", "slovakia", "slovenia", "spain", "sweden",
    "switzerland", "turkey", "ukraine", "united kingdom", "uk",
}

AMERICAS = {
    "anguilla", "antigua and barbuda", "argentina", "aruba", "bahamas",
    "barbados", "belize", "bermuda", "bolivia", "brazil", "british virgin islands",
    "canada", "cayman islands", "chile", "colombia", "costa rica", "cuba",
    "curacao", "dominica", "dominican republic", "ecuador", "el salvador",
    "french guiana", "grenada", "guadeloupe", "guatemala", "guyana", "haiti",
    "honduras", "jamaica", "martinique", "mexico", "montserrat", "nicaragua",
    "panama", "paraguay", "peru", "puerto rico", "st. lucia", "st. martin",
    "st. maarten", "st. vincent and the grenadines", "suriname",
    "trinidad and tobago", "turks and caicos islands", "u.s. virgin islands",
    "united states", "usa", "us", "uruguay", "venezuela",
}

REST_ISMEA = {
    "angola", "azerbaijan", "burkina faso", "burundi", "benin", "botswana",
    "congo", "ivory coast", "cameroon", "cape verde", "djibouti", "algeria",
    "eritrea", "ethiopia", "gabon", "ghana", "gambia", "guinea", "kenya",
    "kyrgyzstan", "liberia", "lesotho", "libya", "morocco", "madagascar",
    "mali", "mauritania", "mauritius", "maldives", "malawi", "mozambique",
    "namibia", "niger", "nigeria", "reunion", "rwanda", "seychelles",
    "senegal", "south africa", "swaziland", "chad", "togo", "tajikistan",
    "tanzania", "uganda", "uzbekistan", "yemen", "zambia", "zimbabwe",
}


def get_surge_region(country: str, direction: str) -> tuple[str, int]:
    """
    Tentukan nama region surge dan rate-nya (IDR/kg) berdasarkan negara & direction.
    Return (region_name, rate_idr_per_kg).
    """
    key = country.strip().lower()
    config = SURGE_EXPORT if direction == "export" else SURGE_IMPORT

    if key in UAE_ISRAEL:
        return "uae_israel", config["uae_israel"]
    if key in MIDDLE_EAST_COUNTRIES:
        return "middle_east", config["middle_east"]
    if key in ASIA_PACIFIC:
        return "asia_pacific", config["asia_pacific"]
    if direction == "import" and key in {"united states", "usa", "us"}:
        return "us", config.get("us", 0)
    if key in EUROPE:
        return "europe", config.get("europe", 0)
    if key in AMERICAS:
        return "americas", config.get("americas", 0)
    if key in REST_ISMEA:
        return "rest_ismea", config.get("rest_ismea", 0)

    return "others", config.get("others", 0)


# ── Per-package surcharge evaluation ─────────────────────────────────────────
@dataclass
class PackageResult:
    label: str
    actual_weight: float
    dim_weight: float
    chargeable_weight: float   # setelah max(actual, dim)
    surcharge_type: str        # "" | "AHS" | "LPS" | "OMX"
    surcharge_cost: float
    reasons: list[str] = field(default_factory=list)
    weight_bumped_to_40: bool = False


def evaluate_package(
    weight_kg: float,
    length_cm: float = 0,
    width_cm: float = 0,
    height_cm: float = 0,
    packing_type: str = "box",   # "box" | "envelope" | "non_standard"
    label: str = "",
    is_wwef: bool = False,
) -> PackageResult:
    """
    Hitung chargeable weight dan surcharge untuk 1 package.
    WWEF: AHS/LPS/OMX diabaikan (diwaive).
    """
    dim_weight = (length_cm * width_cm * height_cm) / DIM_DIVISOR if (length_cm and width_cm and height_cm) else 0
    chargeable = max(weight_kg, dim_weight)

    # Round ke 0.5kg
    chargeable = round((chargeable * 2 + 0.9999) // 1 / 2, 1)

    girth = (2 * width_cm) + (2 * height_cm)
    total_dim = length_cm + girth

    surcharge_type = ""
    surcharge_cost = 0.0
    reasons = []
    weight_bumped = False

    if is_wwef:
        # WWEF: waive AHS, LPS, OMX; minimum 71kg per package
        if chargeable < 71:
            chargeable = 71.0
        return PackageResult(
            label=label,
            actual_weight=weight_kg,
            dim_weight=round(dim_weight, 3),
            chargeable_weight=chargeable,
            surcharge_type="",
            surcharge_cost=0.0,
        )

    # Tentukan OMX/LPS/AHS
    is_special_length = length_cm > 274 and total_dim < 400
    is_omx = is_special_length or length_cm > 274 or total_dim > 400 or weight_kg > 70
    is_lps = not is_omx and total_dim > 300

    if is_omx:
        surcharge_type = "OMX"
        surcharge_cost = OMX_COST + LPS_COST
        if chargeable < 40:
            chargeable = 40.0
            weight_bumped = True
        reasons.append("OMX+LPS")
    elif is_lps:
        surcharge_type = "LPS"
        surcharge_cost = LPS_COST
        if chargeable < 40:
            chargeable = 40.0
            weight_bumped = True
        reasons.append("LPS")
    else:
        # AHS check
        ahs_reasons = []
        if 25 < weight_kg < 71:
            ahs_reasons.append("Weight > 25kg")
        if packing_type not in ("box", "envelope"):
            ahs_reasons.append("Non-standard packaging")
        if (length_cm > 122 or width_cm > 76) and total_dim <= 300:
            ahs_reasons.append("Dimensions (L>122cm or W>76cm)")
        if ahs_reasons:
            surcharge_type = "AHS"
            surcharge_cost = AHS_COST
            reasons.extend(ahs_reasons)

    return PackageResult(
        label=label,
        actual_weight=weight_kg,
        dim_weight=round(dim_weight, 3),
        chargeable_weight=chargeable,
        surcharge_type=surcharge_type,
        surcharge_cost=surcharge_cost,
        reasons=reasons,
        weight_bumped_to_40=weight_bumped,
    )
