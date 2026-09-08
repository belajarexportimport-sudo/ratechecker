"""
FastAPI Routes for Rate Engine
==============================
Menerima request POST /api/rates/calculate
Menerima request POST /api/rates/compare

TIDAK MENGGUNAKAN PYDANTIC (PRD Master §8.1 / §27 / Rule 4 - larangan ini
berlaku ke SELURUH project, termasuk lapisan API, bukan cuma core/schemas.py).
Parsing & validasi input JSON dilakukan manual dengan Python standar
(fungsi `_field()` di bawah) - FastAPI di sini murni transport layer (terima
`Request` mentah, baca `.json()`, balikin dict/dataclass lewat `dataclasses.asdict()`).
"""
import dataclasses
from fastapi import APIRouter, HTTPException, Request

from backend.core.schemas import RateRequest, RateResult
from backend.pricing.router import calculate as calculate_rate
from backend.comparison.compare import compare, ComparisonResult

router = APIRouter()


class ApiValidationError(ValueError):
    """Raised oleh _field() kalau input JSON tidak valid -> jadi HTTP 422."""


_MISSING = object()


def _field(data, key, expected_type=str, default=_MISSING, required=False):
    """
    Ambil & validasi 1 field dari dict JSON mentah, tanpa Pydantic.
    - required=True & key tidak ada -> ApiValidationError.
    - Type mismatch -> ApiValidationError dengan pesan jelas (nama field & tipe
      yang diharapkan), meniru pesan error Pydantic tapi tanpa dependency-nya.
    - expected_type boleh tuple (mis. (int, float)) untuk terima beberapa tipe.
    """
    if key not in data or data[key] is None:
        if required:
            raise ApiValidationError(f"Field '{key}' wajib diisi.")
        return default if default is not _MISSING else None
    value = data[key]
    if expected_type is not None and not isinstance(value, expected_type):
        type_name = (expected_type.__name__ if isinstance(expected_type, type)
                     else " | ".join(t.__name__ for t in expected_type))
        raise ApiValidationError(
            f"Field '{key}' harus bertipe {type_name}, dapat {type(value).__name__}."
        )
    return value


def _normalize_package(item, index):
    """Validasi 1 baris package (dict) tanpa Pydantic. Return dict siap pakai."""
    if not isinstance(item, dict):
        raise ApiValidationError(f"packages[{index}] harus berupa object/dict.")
    return {
        "qty": _field(item, "qty", int, default=1),
        "weight_kg": _field(item, "weight_kg", (int, float), required=True),
        "length_cm": _field(item, "length_cm", (int, float), default=0),
        "width_cm": _field(item, "width_cm", (int, float), default=0),
        "height_cm": _field(item, "height_cm", (int, float), default=0),
        "packing_type": _field(item, "packing_type", str, default="box"),
        "label": _field(item, "label", str, default=""),
    }


def _parse_rate_request(data):
    """
    Parse & validasi body JSON mentah (dict) jadi RateRequest (dataclass).
    Pengganti manual utk skema class berbasis library validasi eksternal yang lama.
    """
    if not isinstance(data, dict):
        raise ApiValidationError("Body request harus berupa JSON object.")

    carrier = _field(data, "carrier", str, required=True)
    rate_type = _field(data, "rate_type", str, default="publish")
    service = _field(data, "service", str, required=True)
    direction = _field(data, "direction", str, required=True)
    origin_country = _field(data, "origin_country", str, required=True)
    destination_country = _field(data, "destination_country", str, required=True)
    weight_kg = _field(data, "weight_kg", (int, float), default=0.0)

    postal_code_origin = _field(data, "postal_code_origin", str, default="")
    postal_code_destination = _field(data, "postal_code_destination", str, default="")
    city_origin = _field(data, "city_origin", str, default="")
    city_destination = _field(data, "city_destination", str, default="")

    dimensions_cm = _field(data, "dimensions_cm", list, default=None)
    if dimensions_cm is not None:
        if len(dimensions_cm) != 3 or not all(isinstance(v, (int, float)) for v in dimensions_cm):
            raise ApiValidationError("Field 'dimensions_cm' harus list 3 angka [panjang, lebar, tinggi].")
        dimensions_cm = tuple(dimensions_cm)

    discount_pct = _field(data, "discount_pct", (int, float), default=0.0)
    extra = _field(data, "extra", dict, default={})
    extra = dict(extra)  # copy, jangan mutate input asli

    packages_raw = _field(data, "packages", list, default=None)
    if packages_raw is not None:
        extra["packages"] = [_normalize_package(p, i) for i, p in enumerate(packages_raw)]

    if city_origin:
        extra.setdefault("city_origin", city_origin)
    if city_destination:
        extra.setdefault("city_destination", city_destination)

    return RateRequest(
        carrier=carrier,
        rate_type=rate_type,
        service=service,
        direction=direction,
        origin_country=origin_country,
        destination_country=destination_country,
        weight_kg=weight_kg,
        postal_code_origin=postal_code_origin,
        postal_code_destination=postal_code_destination,
        dimensions_cm=dimensions_cm,
        discount_pct=discount_pct,
        extra=extra,
    )


def _parse_combinations(data):
    """
    Parse field 'combinations' (list of [carrier, rate_type]) tanpa Pydantic.
    Return None kalau tidak diisi (biar compare() pakai default-nya).
    """
    raw = _field(data, "combinations", list, default=None)
    if raw is None:
        return None
    combos = []
    for i, item in enumerate(raw):
        if not isinstance(item, list) or len(item) != 2:
            raise ApiValidationError(
                f"combinations[{i}] harus list 2 elemen [carrier, rate_type]."
            )
        combos.append((str(item[0]), str(item[1])))
    return combos


@router.post("/calculate")
async def calculate_endpoint(request: Request):
    try:
        data = await request.json()
        core_req = _parse_rate_request(data)
    except ApiValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Body request bukan JSON yang valid.")

    try:
        result = calculate_rate(core_req)
        return dataclasses.asdict(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_endpoint(request: Request):
    try:
        data = await request.json()
        base_data = _field(data, "base_request", dict, required=True)
        core_req = _parse_rate_request(base_data)
        combos = _parse_combinations(data)
    except ApiValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Body request bukan JSON yang valid.")

    try:
        comp_result = compare(core_req, combos)
        return dataclasses.asdict(comp_result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
