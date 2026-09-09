"""
Service Equivalence Mapping
============================
Mapping eksplisit antara service antar carrier.
Sesuai PRD §24: jangan asumsikan FedEx IP == UPS Saver secara otomatis.

Mapping ini hanya boleh diisi setelah service equivalence dikonfirmasi
berdasarkan kebutuhan bisnis / definisi resmi carrier.

Format:
    SERVICE_MAP[carrier_asal][service_asal] = {carrier_tujuan: service_tujuan}

None = belum ada equivalence yang dikonfirmasi.
"""

# Mapping FedEx -> UPS (berdasarkan kesamaan tier layanan, bukan nama)
# FedEx IP (International Priority) ~ UPS Worldwide Saver (Express)
# FedEx IE (International Economy) ~ UPS Worldwide Expedited
# FedEx IPF (International Priority Freight) ~ UPS WWEF (Worldwide Economy Freight)
# Catatan: ini berdasarkan tier layanan umum, konfirmasi final dari bisnis masih diperlukan

FEDEX_TO_UPS: dict[str, str | None] = {
    "IP":  "saver",       # FedEx Intl Priority -> UPS Worldwide Saver
    "IPF": "wwef",        # FedEx Intl Priority Freight -> UPS WWEF
    "IE":  "expedited",   # FedEx Intl Economy -> UPS Worldwide Expedited
    "IEF": "wwef",        # FedEx Intl Economy Freight -> UPS WWEF
}

UPS_TO_FEDEX: dict[str, str | None] = {
    "saver":     "IP",
    "expedited": "IE",
    "wwef":      "IPF",
    "envelope":  "IE",   # dokumen ringan
}


def map_service(from_carrier: str, to_carrier: str, service: str) -> str | None:
    """
    Dapatkan service equivalent di carrier tujuan.
    Return None jika belum ada mapping yang dikonfirmasi.
    """
    fc = from_carrier.lower()
    tc = to_carrier.lower()

    if fc == "fedex" and tc == "ups":
        return FEDEX_TO_UPS.get(service.upper())
    if fc == "ups" and tc == "fedex":
        return UPS_TO_FEDEX.get(service.lower())

    return None
