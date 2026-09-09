"""
Exception dasar bersama untuk seluruh rate engine.

Kenapa ini perlu: setiap carrier punya exception class sendiri
(FedExRateError, UPSZoneError, UPSRateError, dst -- nanti DHL juga akan
punya punya sendiri). Tanpa base class bersama, layer di luar carriers/
(terutama api/routes.py) HARUS tahu & import semua exception class dari
setiap carrier satu-satu supaya bisa membalas HTTP 4xx yang benar (bukan
500) untuk error "input tidak valid / rate tidak tersedia" -- ini
melanggar prinsip carrier isolation di PRD (api/routes.py semestinya tidak
perlu tahu carrier apa saja yang ada).

Dengan base class ini, tiap carrier cukup inherit dari RateEngineError, dan
routes.py cukup catch SATU class ini untuk seluruh carrier, sekarang maupun
yang ditambahkan nanti (UPS, DHL, dst) -- tidak perlu diubah lagi.
"""


class RateEngineError(Exception):
    """
    Base exception untuk error 'business logic' yang disebabkan INPUT tidak
    valid atau rate memang tidak tersedia (negara/service/kombinasi tidak
    dikenal, dll) -- BUKAN bug internal. Di layer API, ini harus dibalas
    sebagai HTTP 400, bukan 500.

    Carrier-specific error class (FedExRateError, UPSZoneError,
    UPSRateError, dst) HARUS inherit dari class ini.
    """
