# Verifikasi & Patch — 3 Prioritas dari AUDIT_UPS_COMMERCIAL.md

Status per prioritas setelah ditelusuri ulang terhadap kode yang di-upload
(`calculator_rate_comparison.zip`, versi dengan `tests/` + git history):

## Prioritas 1 — Named-group override UPS Commercial (A26/B26)
**Sudah diperbaiki di kode yang di-upload** (`backend/carriers/ups/rates/commercial.py`
fungsi `_get_group_key()` + `A26_B26_GROUPS`, dipanggil dari `lookup_rate(..., country=...)`).

Saya verifikasi ULANG secara independen — bukan cuma percaya laporan audit:
- Jalankan langsung `getExtendedGroupKey()`/`lookupExtendedRate()` dari
  `script.js` asli via Node.js untuk dapat ground truth objektif.
- **Catatan:** angka pembanding di `AUDIT_UPS_COMMERCIAL.md` untuk Hong Kong/
  Australia/US/Prancis ternyata salah kutip (pakai tabel *envelope*, bukan
  *saver* yang diklaim) — hanya contoh Jepang (629.400) yang akurat. Ini tidak
  mempengaruhi fix-nya (fix tetap benar), tapi perlu diketahui kalau laporan
  audit itu dipakai lagi sebagai referensi.
- Implementasi di kode sudah cocok 100% dengan ground truth `script.js` untuk
  semua kasus uji (Jepang, Hong Kong, Australia, US, Prancis, Singapura/no-
  override, China vs China South, grup UK yang cuma ada di arah import, WWEF
  yang memang tidak pernah override).
- **Tidak ada perubahan kode dari saya di bagian ini** — sudah benar.

## Prioritas 2 — Bug `packages` FedEx
**Crash-nya sudah diperbaiki** di kode yang di-upload (`_package_surcharge_kwargs()`
di `nonstandard.py`, whitelist key yang valid utk `check_package_surcharge()`).

**Tapi saya temukan REGRESI BARU saat verifikasi ulang**: fix crash itu
membuang key `qty` (dan `packing_type`) secara diam-diam, TANPA memakainya
sebagai pengali. Akibatnya package dengan `qty=2` cuma dihitung sebagai 1
collie di 3 fungsi:
- `summarize_packages()` — total non-standard fee under-charge (hilang 1x lipat)
- `compute_shipment_chargeable_weight()` — CWT under-estimate
- `evaluate_packages_for_service_switch()` — preview forced-fee under-charge

Ini **lebih berbahaya dari crash aslinya**: crash itu fail-fast (langsung
ketahuan), sedangkan silent-drop ini fail-silent (angka keluar, tapi salah,
tidak ada error yang menandakan).

**Sudah saya patch** (`_package_qty()` helper baru + 3 fungsi di atas
dikalikan `qty` yang sesuai) — lihat `backend/carriers/fedex/surcharges/nonstandard.py`.

**Verifikasi double-counting**: karena `calculator.py` SUDAH punya
`_expand_packages_qty()` sendiri yang meng-expand `qty` jadi N dict terpisah
SEBELUM memanggil nonstandard.py (jalur resmi lewat API/RateRequest), saya
pastikan fix saya TIDAK dobel-hitung di jalur itu — sudah dicek end-to-end
(lihat test baru di bawah). Fix saya jadi lapisan pertahanan tambahan untuk
siapa pun yang memanggil fungsi nonstandard.py **langsung** (bukan lewat
`calculate()`), yang tadinya rawan under-billing diam-diam.

**Test baru ditambahkan** di `tests/test_fedex.py`
(`FedExPackageQtyMultiplierRegressionTests`, 3 test) untuk mencegah regresi
ini kambuh lagi. Total test suite: **54 passed** (naik dari 51, semua test
lama tetap hijau).

## Prioritas 3 — Circular import `zones.py` FedEx
**Sudah diperbaiki di kode yang di-upload** (lazy import `publish`/`commercial`
di dalam `calculate_base()`, bukan eager di top-level `rates/__init__.py`).

Saya verifikasi dengan 2 cara:
1. Import 9 entry point berbeda (`zones`, `rates.common`, `rates`,
   `rates.publish`, `rates.commercial`, `calculator`, dst) dalam proses
   Python terpisah-pisah — semua sukses, tidak ada `ImportError`.
2. **Skeptical check**: saya simulasikan versi TANPA fix (eager import) di
   folder terpisah untuk membuktikan bug itu memang nyata (bukan
   pencegahan berlebihan) — hasilnya betul crash dengan
   `ImportError: cannot import name 'ZONES' from partially initialized module`,
   persis seperti yang diprediksi komentar di kode.

**Tidak ada perubahan kode dari saya di bagian ini** — sudah benar.

---

## Lanjutan — full-matrix sweep & pencegahan proaktif bug ke-3

Setelah 3 prioritas di atas, saya jalankan `tests/test_full_matrix_sweep.py`
(iterasi SEMUA negara x service x direction x rate_type, 8 test) — **semua
lulus**, tidak ada exception tak terduga di luar sweep dasar (sweep ini tidak
menyentuh jalur `packages`/`freight_units` karena memang tidak diisi).

Karena komentar di kode eksplisit bilang pola bug `qty`/`packing_type` ini
"sudah 2x kejadian", saya scan seluruh codebase untuk pola `**dict` splat
yang sama rentannya:

- **`summarize_freight_units()` (FedEx)** — ternyata masih memakai pola LAMA
  yang sama (`check_freight_surcharge(**unit)` tanpa whitelist), TIDAK
  crash SAAT INI cuma karena `backend/api/routes.py` belum menormalisasi
  `freight_units` dengan `qty`/`packing_type` (beda dengan `packages` yang
  sudah). Begitu itu ditambahkan (langkah alami berikutnya, persis proses
  yang sama dengan `packages`), ini akan jadi **bug ke-3** dengan pola
  identik. **Saya keraskan sekarang secara proaktif** (whitelist
  `_freight_surcharge_kwargs()` + `qty` multiplier), sebelum jadi bug aktif.
- **UPS (`evaluate_package()`)** — dicek, **kebal secara desain**: field
  diambil satu-satu lewat `pkg.get(...)`, bukan `**pkg` splat, jadi key
  ekstra apa pun otomatis diabaikan dengan aman. Tidak perlu perubahan.
- **`compute_special_handling()` (FedEx)** — dicek, risikonya beda kelas:
  dict `special_handling` dikontrol developer langsung (bukan hasil
  auto-normalize skema API bersama seperti `packages`/`freight_units`),
  jadi tidak termasuk pola bug yang sama. Tidak diubah.

## File yang saya ubah
- `backend/carriers/fedex/surcharges/nonstandard.py`:
  - Fix qty multiplier di `summarize_packages()`, `compute_shipment_chargeable_weight()`,
    `evaluate_packages_for_service_switch()` (Prioritas 2, regresi baru)
  - Whitelist + qty multiplier proaktif di `summarize_freight_units()`
    (pencegahan bug ke-3, belum aktif tapi laten)
- `tests/test_fedex.py` — tambah `FedExPackageQtyMultiplierRegressionTests`
  (3 test) + `FedExFreightUnitsHardeningTests` (2 test)

## Cara verifikasi ulang
```bash
cd "calculator rate comparison"
pip install -r requirements.txt pytest
python3 -m pytest tests/ -q                        # harus: 56 passed
python3 -m pytest tests/test_full_matrix_sweep.py -v  # harus: 8 passed
```
