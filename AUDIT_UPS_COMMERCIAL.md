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
memang B26, A26 cuma referensi/tier lain) — saya TIDAK mengubah ini karena
butuh konfirmasi bisnis, bukan keputusan teknis. Kalau yang dimaksud
"commercial" itu seharusnya bisa pilih A26 ATAU B26 (bukan selalu B26),
perlu ditambahkan field/opsi eksplisit di `RateRequest` (mis.
`extra={"ups_tier": "a26"}`) yang dibaca `calculator.py` sebelum fallback ke
default.


## Bug lain yang sudah tercatat sebelumnya (dari sesi index.html)
1. `check_package_surcharge()` FedEx crash kalau field `packages` diisi
   (kwarg `qty` tidak dikenali).
2. Circular import kalau `carriers/fedex/zones.py` di-import sendirian.

## Ringkasan prioritas
1. **Prioritas tinggi**: fix named-group override UPS commercial (A26/B26) —
   ini bikin salah HARGA ke customer untuk negara-negara volume tinggi
   (China, Jepang, US, HK, negara-negara Eropa besar).
2. **Prioritas sedang**: fix bug `packages` FedEx (nonstandard.py).
3. **Prioritas rendah**: rapikan urutan import `carriers/fedex/zones.py`.


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
