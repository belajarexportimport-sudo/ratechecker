from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateRequest:
    carrier: str
    rate_type: str
    service: str

    direction: str

    origin_country: str
    destination_country: str

    weight_kg: float

    dimensions_cm: Optional[tuple[float, float, float]] = None

    packages: int = 1

    postal_code_origin: Optional[str] = None
    postal_code_destination: Optional[str] = None

    discount_pct: Optional[float] = None

    extra: dict = field(default_factory=dict)


@dataclass
class RateResult:
    carrier: str
    rate_type: str
    service: str

    zone: str

    base_price: float

    surcharges: dict[str, float] = field(default_factory=dict)

    discount: float = 0

    total: float = 0

    currency: str = "IDR"

    notes: list[str] = field(default_factory=list)

    extra: dict = field(default_factory=dict)
