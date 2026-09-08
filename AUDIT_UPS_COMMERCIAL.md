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
Port fungsi `getExtendedGroupKey()` dari `script.js` (baris ~551-573) ke
Python di `backend/carriers/ups/rates/commercial.py`, dipanggil SEBELUM
fallback ke zone angka di `lookup_rate()`. Perlu bawa juga:
- Tabel `A26_B26_GROUPS` (alias nama negara → nama grup) dari `script.js`.
- Logic khusus China ("prefer named header over zone 3 & 10").
- Perbedaan grup export vs import (grup UK cuma ada di import, misalnya) —
  jangan asumsikan grup yang sama berlaku di kedua arah.

**Saya belum memperbaiki ini** (fokus audit dulu sesuai arahan) — tinggal
bilang kalau mau saya lanjutkan perbaikannya.

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
