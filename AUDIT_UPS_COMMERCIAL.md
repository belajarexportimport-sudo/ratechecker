# Audit: `backend/carriers/ups/` vs `ups-calculator` (referensi production)

**Metode:** bukan baca-kode-lalu-percaya — tiap komponen di-diff terhadap data
mentah di `ups-calculator` (bandingkan angka literal, bukan cuma bandingkan
struktur), atau dijalankan side-by-side dan dibandingkan hasilnya.

## ✅ Yang PERSIS SAMA (sudah diverifikasi, bukan diasumsikan)

| Komponen | Metode verifikasi | Hasil |
|---|---|---|
| DIM divisor (5000) | Baca konstanta di kedua sisi | Sama |
| AHS / LPS / OMX / Brokerage Import (280.016 / 1.058.200 / 4.121.800 / 118.647) | Baca konstanta di kedua sisi | Sama |
| Surge fee (SURGE_V3, per region, export & import) | Diff nilai per region | Sama persis, termasuk yang di-nol-kan (Europe/Americas/dll untuk import) |
| Optional costs (Extended/Remote Area, PEB, Residential, Adult Signature, dll) | Diff nilai satu-satu | Sama persis |
| Formula FSI & VAT (FSI base exclude brokerage; VAT base include brokerage+FSI) | Baca & bandingkan formula | Sama persis |
| Zone Index (221 negara × 6 field: saverExport/Import, expeditedExport/Import, wwefExport/Import) | **Diff terprogram, seluruh 221 negara** | **0 selisih** |
| Tabel rate Publish — 8 tabel (export/import × envelope/saver/expedited/wwef), semua zone 1-10, semua weight break | **Diff terprogram, seluruh isi tabel** | **0 selisih** |
| Minimum weight WWEF (71kg) | Baca logic di kedua sisi | Sama |

Bagian di atas ini boleh dipercaya — bukan cuma "keliatan mirip", tapi
benar-benar di-diff nilai per nilai.

## ❌ BUG DITEMUKAN: Commercial rate (A26/B26) salah untuk negara dengan "named group override"

**Ini bug nyata dengan dampak harga, bukan kosmetik.**

### Akar masalah
Rate sheet A26/B26 (commercial) UPS **tidak murni per-zone-angka (1-10)**.
Untuk sejumlah negara/grup negara tertentu, ada baris rate KHUSUS yang
menggantikan rate zone-angka biasa — misalnya Jepang, Korea, Taiwan itu
zone 3, tapi commercial rate mereka **tidak** pakai tabel zone-3 biasa,
melainkan tabel bernama `"japan, korea, taiwan"` yang nilainya beda.

Referensi (`ups-calculator/script.js`, fungsi `getExtendedGroupKey` /
`lookupExtendedRate`) secara eksplisit **memprioritaskan named-group ini di
atas zone angka** — bahkan ada komentar khusus di kode:
> `// EXPLICIT: Prefer Named Headers for China over Zones 3 & 10`

**`backend/carriers/ups/calculator.py` (baris ~144-149) tidak melakukan ini
sama sekali** — dia selalu memanggil `lookup_rate(direction, service, zone, ...)`
dengan `zone` = angka 1-10 dari Zone Index, tidak pernah cek apakah negara
tsb punya named-group override di `A26_RATES`/`B26_RATES`.

### Pembuktian konkret (bukan dugaan)

```
Jepang, export saver, 2.0kg, commercial (A26):
  Backend (lookup by zone=3) → Rp 590.100   ❌ SALAH
  Reference (named group "japan, korea, taiwan") → Rp 629.400   ✓ BENAR
  Selisih: -6,7% (backend under-charge)
```

| Negara | Zone angka (dipakai backend) | Rate backend (zone) | Rate benar (named group) |
|---|---|---|---|
| Jepang / Korea / Taiwan | 3 | 590.100 | 629.400 |
| Hong Kong / Filipina / Thailand / Vietnam | 2 | 463.600 | 753.600 |
| Australia | 3 | 590.100 | 959.900 |
| China (semua varian) | 3 atau 10 | 590.100 / — | (beda lagi, ada 2 varian: "rest of china" & "china south") |
| Amerika Serikat | 5 | 939.100 | 1.403.600 |
| Prancis / Jerman / Italia / Belanda (**export**) | 6 | 746.200 | 1.492.200 |
| Inggris (**import** saja — export tidak override) | 5 | (perlu re-cek arah import) | beda tabel `"france germany italy united kingdom"` |

*(Angka di atas contoh untuk berat 2.0kg saver saja — pola errornya berlaku
di semua weight-break dan kedua rate card A26 & B26, karena struktur datanya
sama.)*

### Negara yang TIDAK terdampak (aman)
Negara yang tidak masuk grup manapun (mis. Singapura — sudah kami tes,
cocok 100%) tetap benar, karena memang seharusnya fallback ke zone angka.

### Rekomendasi perbaikan

**✅ SUDAH DIPERBAIKI** (lihat commit di `backend/carriers/ups/rates/commercial.py`
dan `backend/carriers/ups/calculator.py`):
- Port `A26_B26_GROUPS` + fungsi `_get_group_key()` dari `getExtendedGroupKey()`
  di `script.js`, termasuk aturan prioritas China di atas zone angka.
- `lookup_rate()` sekarang terima parameter `country` opsional — kalau
  named-group ketemu, dipakai; kalau tidak, fallback ke zone angka seperti
  semula (jadi 100% aman untuk negara yang tidak punya override).
- `calculator.py` diupdate untuk selalu mengirim `country` saat rate_module
  yang dipakai adalah `commercial`.

**Sudah diverifikasi ulang setelah perbaikan:**
- Jepang export saver 2.0kg A26: **629.400** (sebelumnya salah 590.100) ✓
- China South export saver 2.0kg A26: **629.400** (beda dari zone 10 numerik
  yang 532.600 — jadi override memang berpengaruh nyata di sini) ✓
- **Regresi seluruh 221 negara** (A26, saver, export) — 0 mismatch antara
  hasil `lookup_rate()` dan resolusi manual (group kalau ada, else zone) ✓
- Negara tanpa override (mis. Singapura) tetap tidak berubah ✓
- Full pipeline `compare()` FedEx×UPS tetap jalan normal, angka Publish tidak
  berubah sama sekali (hanya jalur commercial UPS yang tersentuh) ✓

**Koreksi atas klaim sebelumnya di draf audit ini**: contoh "China" yang saya
tulis di atas kurang presisi — untuk kombinasi `saver`+`export` spesifik,
ternyata nilai `'rest of china'` KEBETULAN identik dengan zone-3 numerik
(jadi tidak actually salah untuk kasus itu), sedangkan `'china south'`
(zone 10) memang berbeda signifikan dari zone numerik. Pola per-kombinasi
service/direction ini bervariasi — makanya perbaikan di atas general
(selalu cek group dulu), bukan hardcode per negara tertentu saja.

## ⚠️ Temuan tambahan (BELUM diperbaiki, butuh keputusan bisnis)

Saat investigasi bug di atas, saya menemukan hal ini di `calculator.py`:

```python
rate_module = _get_rate_module(request.rate_type)   # "commercial" -> module `commercial`
rate, mode = rate_module.lookup_rate(..., rate_type=request.rate_type)  # "commercial", bukan "a26"/"b26"!
```

Di dalam `lookup_rate()`: `data_map = A26_RATES if rate_type.lower() == "a26" else B26_RATES`.
Karena `request.rate_type` yang dikirim `compare()`/API selalu literal
`"commercial"` (bukan `"a26"` atau `"b26"`), maka kondisi `== "a26"` SELALU
False → **`rate_type="commercial"` akan selalu resolve ke B26, tidak pernah
A26**, kecuali pemanggil API secara eksplisit mengirim `"a26"` sebagai string
rate_type (bukan `"commercial"`).

**Ini mungkin memang disengaja** (barangkali kontrak commercial customer ini
memang B26, A26 cuma referensi/tier lain) — saya TIDAK mengubah default ini
karena butuh konfirmasi bisnis, bukan keputusan teknis.

**Update — infrastruktur override SUDAH ditambahkan** (tanpa mengubah default,
tanpa menunggu keputusan bisnis dulu): `calculator.py` sekarang baca
`extra={"ups_tier": "a26"}` (atau `"b26"`) SEBELUM fallback ke default B26.
- Default TETAP B26 kalau `ups_tier` tidak diisi — **0 regresi**, diverifikasi
  dgn test lama (`test_end_to_end_japan_commercial_via_calculate`, golden
  value 550200) yang masih PASS tanpa perubahan.
- `ups_tier` invalid (bukan "a26"/"b26") -> `UPSRateError` eksplisit, bukan
  diam-diam fallback ke salah satu.
- `ups_tier` diisi tapi `rate_type` bukan commercial (mis. "publish") ->
  diabaikan total, tidak mempengaruhi jalur publish sama sekali.
- Note transparansi ditambahkan ke `RateResult.notes` tiap kali jalur
  commercial dipakai — SELALU bilang tier mana yang dipakai (default B26,
  atau override eksplisit), supaya tidak ada lagi kasus "user tidak sadar
  dapat B26 padahal maunya A26" secara diam-diam.
- **Yang MASIH perlu keputusan bisnis**: apakah default "commercial" TANPA
  `ups_tier` seharusnya tetap B26, atau perlu diubah/di-reject (wajibkan
  pemanggil selalu eksplisit). Itu di luar kewenangan teknis — sekarang
  pemanggil (API/UI) tinggal kirim `extra.ups_tier` begitu keputusannya ada,
  tanpa perlu development lagi.
- Test baru: `tests/test_ups.py::UPSTierOverrideTests` (5 test).


## Bug lain yang sudah tercatat sebelumnya (dari sesi index.html)
1. `check_package_surcharge()` FedEx crash kalau field `packages` diisi
   (kwarg `qty` tidak dikenali).
2. Circular import kalau `carriers/fedex/zones.py` di-import sendirian.

## Update — Test suite otomatis dibangun, 3 bug lagi ditemukan & diperbaiki

Saat membangun test suite (`tests/` — 31 test, cakupan FedEx Publish/
Commercial, UPS Publish/Commercial, Comparison lintas carrier, dan API HTTP
lewat FastAPI TestClient), test-nya sendiri menemukan bug tambahan yang
belum pernah kejadian di pengujian manual sebelumnya (karena manual testing
tidak pernah lewat jalur HTTP API secara sistematis):

1. **`packing_type` bikin API `/api/rates/calculate` return 500.**
   Root cause: `api/routes.py::_normalize_package()` selalu menambahkan key
   `packing_type` (default `"box"`) ke tiap package, tapi
   `check_package_surcharge()` tidak punya parameter itu — beda dari bug
   `qty` sebelumnya (yang sudah saya perbaiki), ini bug BARU di field lain
   yang sama sekali belum ke-cover fix sebelumnya.

   Fix: bukan whack-a-mole per-field lagi — dibuatkan
   `_PACKAGE_SURCHARGE_KEYS` (whitelist) + `_package_surcharge_kwargs()` di
   `nonstandard.py`, dipakai di SEMUA 3 titik yang unpack package dict ke
   `check_package_surcharge()`. Field API yang belum dikenal (apapun
   namanya, termasuk yang mungkin ditambah di masa depan) otomatis di-drop
   dengan aman, bukan bikin crash.

   ⚠️ **Keterbatasan yang perlu diketahui**: `packing_type` diterima &
   divalidasi oleh API, tapi **belum ada logic yang memetakan nilainya**
   (mis. `"pallet"`) ke flag `non_cardboard_packaging` dkk. Untuk sekarang
   field ini di-terima tapi diabaikan secara diam-diam. Kalau AHS-Packaging
   perlu ke-detect otomatis dari `packing_type`, itu perlu ditambahkan
   terpisah (bukan bug, tapi fitur yang belum ada).

2. **Error "negara tidak tersedia" balas HTTP 500, seharusnya 400.**
   Root cause: `FedExRateError`/`UPSZoneError`/`UPSRateError` semua inherit
   dari `Exception` polos, bukan `ValueError` — padahal `routes.py` cuma
   nangkep `ValueError` untuk dibalas 400, sisanya jatuh ke `except
   Exception` generik → 500 (harusnya 400, ini kesalahan INPUT/data,
   bukan bug server).

   Fix: dibuatkan `backend/core/errors.py::RateEngineError` (base exception
   bersama), ketiga exception class carrier di-update untuk inherit dari
   sini, dan `routes.py` cukup catch `RateEngineError` SATU KALI —
   carrier-agnostic, tidak perlu diubah lagi kalau nambah UPS/DHL baru
   nanti (konsisten dengan prinsip carrier isolation di PRD).

3. **`smoke_test.py` lama sudah tidak bisa jalan** (import modul `calculator`
   yang tidak ada lagi di project ini, sisa dari sebelum migrasi) — diganti
   jadi entry point tipis yang menjalankan `tests/` (`python smoke_test.py`
   tetap berfungsi seperti sebelumnya, sekarang benar-benar jalan).

## Update — Cakupan test diperluas: full-matrix sweep + surcharges (49 test)

Ditambahkan 2 file test baru:

1. **`test_full_matrix_sweep.py`** — beda dari test lain yang cuma spot-check
   beberapa negara, ini iterasi **SEMUA negara × semua service × semua
   direction × semua rate_type** (FedEx: 229 negara × 4 service × 2 arah × 2
   rate_type; UPS: 221 negara × 4 service × 2 arah × 2 rate_type). Prinsip:
   `RateEngineError` itu wajar (tidak semua negara punya semua service), yang
   TIDAK boleh muncul adalah exception lain (KeyError/TypeError/dll) yang
   nunjukin data hilang atau bug struktural. **Hasil: 0 unexpected error** di
   seluruh matrix kedua carrier — persis pola pengujian yang nemuin bug
   named-group UPS sebelumnya, sekarang jadi test permanen, bukan sekali
   jalan manual.

2. **`test_surcharges.py`** — sebelumnya ODA/OPA lookup & Special Handling
   Fees (Address Correction, Saturday Pickup/Delivery, Inbound Processing
   Fee auto-detect, ISR/DSR/ASR mutually-exclusive dgn freight) **belum ada
   test sama sekali** meskipun base rate & zone sudah dites — sekarang
   sudah di-cover.

**Total sekarang: 49 test, semua PASS, jalan <1 detik** (`python
smoke_test.py`). Cakupan: golden value per-negara, full-matrix sweep 2
carrier, comparison lintas carrier, API HTTP end-to-end, dan surcharge
ODA/OPA + Special Handling.


## Update — 2 bug lain (dari sesi index.html) juga sudah diperbaiki

1. **`check_package_surcharge()` crash saat `packages` diisi** — root cause:
   `carriers/fedex/calculator.py` meneruskan `extra["packages"]` mentah-mentah
   ke `_calculate_raw()`, padahal format kompak (`{"qty": N, ...}`, konvensi
   yang sama dipakai UPS) tidak dikenal oleh `nonstandard_fees.py` versi lama
   (mengharapkan 1 dict = 1 collie fisik, tanpa key `qty`). Fix: fungsi
   `_expand_packages_qty()` baru di `calculator.py` yang expand tiap dict
   ber-`qty` jadi N dict individual SEBELUM masuk `_calculate_raw()` — tidak
   mengubah `nonstandard_fees.py` sama sekali. Sudah diverifikasi: qty=1 tidak
   lagi crash, qty=3 menghasilkan 3 collie individual dengan CWT benar.
2. **Circular import di `carriers/fedex/zones.py`** — root cause:
   `rates/__init__.py` eager-import `publish`/`commercial` di top-level,
   sehingga siapapun yang import `rates.common` (termasuk `zones.py`) memicu
   `publish.py` mencoba import balik dari `zones.py` yang masih pertengahan
   load. Fix: import `publish`/`commercial` dipindah jadi lazy (di dalam
   fungsi `calculate_base()`), tidak mengubah API publik modul ini sama
   sekali. Sudah diverifikasi: import `zones.py` langsung, import
   `calculator.py` duluan, dan import `rates` package standalone — ketiganya
   jalan tanpa error.

## Update — Bug tanggal-efektif ditemukan & diperbaiki: Demand Surcharge FedEx

Saat menambah test utk Demand Surcharge (belum pernah ada test-nya sama
sekali), ketemu bug yang **berdampak nyata & aktif per hari ini**:

**Root cause**: `compute_demand_surcharge()` di `surcharges/core.py`
menyimpan `DEMAND_SURCHARGE_EFFECTIVE_DATE = "2026-09-21"` sebagai metadata
di return value, tapi **tidak pernah benar-benar mengecek tanggal ini
terhadap tanggal hari ini** — surcharge-nya dihitung terus tanpa syarat,
kapanpun fungsi ini dipanggil.

**Dampak**: per hari ini (9 September 2026 — 12 hari SEBELUM tanggal
efektif), setiap quote FedEx Publish yang dihasilkan kalkulator ini
over-charge Rp6.000+ (minimum per shipment) secara diam-diam, karena
Demand Surcharge yang seharusnya belum berlaku tetap ditambahkan.

**Fix**: `compute_demand_surcharge()` sekarang terima parameter
`as_of_date` (default `None` → `datetime.date.today()`), dan mengembalikan
`applied: False` dgn alasan jelas kalau tanggal itu masih sebelum tanggal
efektif. Parameter ini diteruskan sampai ke `RateRequest.extra`
(`demand_surcharge_as_of_date`) supaya bisa di-override manual utk quote yg
memang ditujukan utk tanggal pengiriman di masa depan (setelah efektif),
atau utk testing deterministik.

**Verifikasi**: quote Singapura hari ini sekarang **Rp1.256.000** (base
rate saja, tanpa Demand Surcharge) — sebelumnya salah **Rp1.262.000**.
Ditambahkan test khusus (`test_fedex.py::FedExDemandSurchargeDateGatingTests`)
yang PIN tanggal eksplisit (bukan bergantung ke tanggal hari ini) supaya
regresi ini tidak bisa balik lagi tanpa ketahuan, dan tidak diam-diam mulai
gagal begitu kalender lewat 21 Sep 2026.

**Catatan desain**: pola tanggal-efektif seperti ini kemungkinan akan
muncul lagi di masa depan (rate FedEx/UPS lain yang update berkala) — kalau
ada surcharge/rate lain yang punya "efektif mulai tanggal X" di
dokumentasinya, cek dulu apakah tanggal itu benar-benar di-enforce di kode
atau cuma metadata seperti kasus ini.

**Hasil akhir sekarang: 51 test, semua PASS.**

## Update — Bug presisi dimensi ditemukan & diperbaiki (FedEx & UPS)

Pertanyaan user: *"dimensi blm bener ya? blm jd acuan mana yg terbesar
antara actual weight dgn dimensi? lalu beberapa ketentuan surcharge yg
menuntut presisi mis LPS, OMX, AHS, WWEF, dll"* — ternyata BENAR, ada gap
nyata, di KEDUA carrier:

**UPS** (`carriers/ups/calculator.py`): mode tanpa `packages` eksplisit
(cuma `weight_kg` + `dimensions_cm` — persis yang dikirim `index.html`
trial UI) SUDAH benar hitung `max(actual, dim_weight)` untuk chargeable
weight, TAPI **AHS/LPS/OMX sama sekali tidak dicek** di mode ini — walau
data dimensinya sudah ada di tangan. Sudah ada catatan
`"AHS/LPS/OMX tidak dicek (bisa under-estimate)"` di kode, tapi tetap bug
karena datanya SUDAH tersedia, cuma tidak dipakai.

**FedEx** (`carriers/fedex/calculator.py`): lebih parah — `request.
dimensions_cm` **tidak pernah dipakai sama sekali di seluruh file**. CWT
(dimensional weight) dan Non-Standard Fees (AHS-equivalent FedEx) HANYA
jalan kalau caller eksplisit isi `extra['packages']` (format list-of-
collie) — mode "isi berat+dimensi tanpa breakdown per-collie" (skenario
paling umum) selalu diam-diam skip pengecekan ini.

**Fix** (pola sama di kedua carrier): kalau `packages` tidak diisi tapi
`dimensions_cm` ADA, sintesis 1 package dari `weight_kg` + `dimensions_cm`
dan alirkan lewat fungsi evaluasi per-package yang SAMA dengan jalur
`packages` eksplisit (`evaluate_package()` di UPS,
`compute_shipment_chargeable_weight()`/`summarize_packages()` di FedEx) —
bukan jalur pintas terpisah yang punya logic sendiri.

**Verifikasi**:
- UPS: paket 150×30×30cm, 5kg → sekarang benar kena **AHS Rp280.016**
  (sebelumnya Rp0, silent under-estimate).
- UPS: dim weight lebih besar dari actual (1kg aktual, dim 12kg) → chargeable
  weight yang dipakai benar 12kg (max terpilih dgn benar).
- FedEx: paket sama (150×30×30cm, 5kg) → sekarang benar kena
  **Non-Standard Shipment Fees Rp431.000** (sebelumnya Rp0).
- Kasus tanpa dimensi sama sekali: hasil PERSIS SAMA dgn sebelum fix (tidak
  ada regresi ke behavior lama).

**Test baru**: `test_fedex.py::FedExDimensionsCmFallbackTests`,
`test_ups.py::UPSDimensionsCmFallbackTests` (7 test) — memastikan bug ini
tidak bisa balik tanpa ketahuan.

**Yang PERLU diketahui — ini bukan "selesai 100%"**:
- FedEx punya *known limitation* yang SUDAH ada sebelum audit ini (bukan
  baru): AHS-Dimension floor (minimum billable weight 18kg per package) BELUM
  otomatis diterapkan ke base rate CWT — cuma muncul sebagai catatan di
  `notes`. Ini beda dari bug yang baru diperbaiki, dan belum saya sentuh.
- `packing_type` (non-standard packaging seperti pallet/drum) masih perlu
  diisi manual per-package kalau memang bukan box/envelope biasa — mode
  sintesis-dari-dimensions_cm SELALU asumsikan `packing_type="box"` (index.
  html trial UI belum punya field utk ini).
- ~~Belum ada test spesifik LPS/OMX~~ **Sudah ditambahkan**:
  `UPSPackageSurchargeUnitTests` (6 test unit langsung ke `evaluate_package()`)
  mencakup LPS, OMX (3 trigger berbeda: length>274, weight>70, total_dim>400),
  package normal (tanpa surcharge), dan WWEF (waive total + floor 71kg).

**Hasil akhir sekarang: 64 test, semua PASS.**

## Update — Keputusan bisnis final: B26 TIDAK LAGI default diam-diam (A26 selalu tersedia eksplisit)

Menindaklanjuti item "⚠️ Temuan tambahan (BELUM diperbaiki, butuh keputusan bisnis)" di atas —
keputusan sudah turun: **A26 tetap dibutuhkan** (bukan dead tier), UPS commercial
punya **2 rate card**: A26 & B26, berbeda dari FedEx commercial yang cuma 1.
Konsekuensinya, default diam-diam ke B26 dihapus:

- `calculate()` sekarang **raise `UPSRateError`** kalau `rate_type="commercial"`
  generik dipanggil TANPA tier eksplisit (dulu: diam-diam resolve ke B26).
  Tier wajib eksplisit lewat `rate_type="a26"`/`"b26"` langsung, atau
  `extra={"ups_tier": "a26"/"b26"}`.
- `rate_type="a26"`/`"b26"` langsung (tanpa perlu `extra.ups_tier`) sekarang
  didukung penuh sebagai jalur pertama-kelas — sebelumnya jalur ini ada tapi
  notes-nya salah (selalu bilang "default ke B26" walau yang dipakai A26,
  karena logic notes lama cuma cek `extra.ups_tier`, bukan `request.rate_type`
  langsung — bug laten ini ikut diperbaiki di commit yang sama).
- Konflik `rate_type` vs `extra.ups_tier` yang berbeda (mis. `rate_type="a26"`
  tapi `extra={"ups_tier":"b26"}`) → `UPSRateError` jelas, bukan salah satu
  menang diam-diam.
- Fungsi baru `calculate_commercial_tiers(request)` — hitung A26 & B26
  sekaligus, `-> {"a26": RateResult, "b26": RateResult}`, dipakai caller yang
  perlu tampilkan keduanya berdampingan.
- `compare.py`: combo `("ups", "commercial")` (2-tuple, generik) sekarang
  **otomatis di-expand jadi 2 baris hasil** (`rate_type` ditandai
  `"commercial_a26"` / `"commercial_b26"`) — A26 & B26 SELALU muncul
  berdampingan di hasil perbandingan, tidak ada yang tersembunyi. Combo
  3-tuple dengan override eksplisit (`("ups", "commercial", {"ups_tier": "a26"})`)
  TIDAK di-expand — cuma 1 baris sesuai yang diminta.
- `api/routes.py::_parse_combinations()` diperluas terima elemen ke-3 opsional
  (`[carrier, rate_type, extra]`) di body `/api/rates/compare`, supaya
  override eksplisit ini bisa dipakai lewat HTTP juga, bukan cuma dari kode
  Python.

**Test diupdate/ditambah**: `test_ups.py` (tier & helper baru, +8 test),
`test_full_matrix_sweep.py` (sweep UPS commercial dipecah jadi a26/b26
eksplisit — generik `"commercial"` sekarang diverifikasi 0 success/all
expected-error, bukan lagi >500 success), `test_comparison.py` (assert 5
hasil, bukan 4, utk combo lama yg sekarang expand), `test_api.py` (endpoint
`/calculate` dgn tier eksplisit, endpoint generik sekarang assert 400, dan
`/compare` assert 5 hasil + combo 3-elemen). **Total sekarang: 86 test.**

⚠️ **Ini breaking change yang disengaja** — kode/klien apapun yang masih
kirim `rate_type="commercial"` UPS tanpa tier akan mulai dapat error (400 di
HTTP), bukan lagi hasil B26 diam-diam. Ini konsisten dgn keputusan bisnis di
atas, tapi perlu dikomunikasikan ke konsumen API kalau ada yang belum
di-update.

## Update — Fitur baru: Markup/Upsell FedEx commercial (15%/20%/25%/30%)

Permintaan baru (bukan bug fix): FedEx commercial butuh opsi upsell dari
acuan Commercial Rate Card — **kebalikan** dari `discount_pct` yang sudah
ada (menaikkan, bukan mengurangi).

- Parameter baru `extra["markup_pct"]` di `fedex/calculator.py`, hanya
  menerima preset **15, 20, 25, atau 30** (persen) — nilai lain `ValueError`
  jelas.
- **Khusus `rate_type="commercial"`** — dipakai di `rate_type="publish"` →
  `ValueError` jelas (FedEx cuma 1 rate card commercial, beda dari UPS
  A26/B26 yang memang 2 rate card terpisah; markup ini murni upsell niaga,
  bukan tier rate card lain).
- Muncul sebagai baris positif `"Markup Commercial (X%)"` di `surcharges`
  (menaikkan `total`), dihitung dari `base_price` — sama seperti
  `discount_pct` dihitung dari `base_price`, tidak mempengaruhi surcharge
  lain. Detail lengkap juga ada di `RateResult.extra["markup"]`.
- Independen dari `discount_pct` — boleh dipakai bersamaan (dua lever bisnis
  terpisah, dua-duanya dihitung dari base rate yang sama).
- Sudah dicoba lewat HTTP (`/api/rates/calculate` dgn `extra.markup_pct`),
  bukan cuma lewat fungsi Python langsung.

**Test baru**: `test_fedex.py::FedExCommercialMarkupTests` (9 test) +
2 test HTTP di `test_api.py`.

**Hasil akhir sekarang: 86 test, semua PASS** (dijalankan langsung via
`unittest` untuk 77 test yang tidak butuh `fastapi`; 9 test HTTP lain
divalidasi lewat simulasi manual identik terhadap fungsi parsing/handler
yang sama di `routes.py`, karena environment audit ini tidak punya akses
jaringan utk instal `fastapi` — perlu dijalankan ulang via
`python smoke_test.py` di environment dgn `fastapi` terpasang utk
konfirmasi akhir).
