# Audit: `backend/carriers/fedex/surcharges/` vs sumber resmi (PDF)

**Metode:** sama seperti `AUDIT_UPS_COMMERCIAL.md` — bukan baca-kode-lalu-percaya.
Tiap kriteria & nominal di-cross-check manual terhadap teks PDF sumber, LALU
dibuktikan lewat test numerik yang benar-benar dijalankan (bukan cuma dibaca).
Semua test di bawah **PASS** saat audit ini dijalankan.

**Sumber resmi yang dipakai sebagai pembanding:**
- `fedex-rates-sur-en-id-2026.pdf` ("Surcharge and Other Information — Indonesia",
  efektif berlaku sejak dokumen ini pertama diberikan ke asisten)
- `demand_surcharge_update_4_sep_2026.pdf` (efektif 21 September 2026)
- `aturan_rumus_rate_fedex.txt` (klarifikasi rumus dari user, termasuk revisi
  formula Length+Girth)

**Cakupan modul yang diaudit:** `surcharges/nonstandard.py`,
`surcharges/special_handling.py`, `surcharges/core.py` (OPA/ODA fee +
Demand Surcharge). **Belum diaudit di sesi ini:** `surcharges/oda_opa.py`
(engine lookup tier ODA/OPA per kode pos/kota — beda jenis validasi, lihat
bagian akhir dokumen ini).

---

## 1. `nonstandard.py` — Non-Standard Shipment Fees (AHS/Oversize/Unauthorized)

### ✅ Kriteria & nominal — cocok persis dengan PDF

| Surcharge | Nominal | Kriteria trigger | Status |
|---|---|---|---|
| AHS - Dimension | Rp431.000/package | longest>121cm OR 2nd-longest>76cm OR length+girth>266cm OR volume>169.901cm³ | ✅ cocok |
| AHS - Weight | Rp431.000/package | actual weight>25kg | ✅ cocok |
| AHS - Packaging | Rp431.000/package | flag manual (bentuk kemasan) | ✅ cocok |
| Oversize Charge | Rp1.072.000/package | longest>243cm OR length+girth>330cm OR weight>50kg OR volume>283.168cm³ | ✅ cocok |
| Unauthorized Package Charge | Rp4.447.000/package | longest>274cm OR length+girth>419cm OR weight>68kg | ✅ cocok |
| AHS - Freight | Rp2.944.000/unit | longest>157cm | ✅ cocok |
| Non-Stackable Surcharge | Rp3.700.000/unit | flag manual | ✅ cocok |
| Unauthorized Freight Charge | Rp7.306.000/unit | longest>302cm OR length+girth>762cm OR weight>1.995kg | ✅ cocok |

### ✅ Formula Length + Girth — sesuai revisi user (BUKAN sortir)

`Length + Girth = length_cm + 2×width_cm + 2×height_cm`, field apa adanya,
tanpa sortir 3 sisi. Dikonfirmasi sudah diterapkan benar di
`_longest_and_length_plus_girth()`.

### ✅ Aturan kombinasi — dibuktikan lewat test, bukan cuma dibaca

**Package (IP/IE):** PDF eksplisit — *"the highest charge after the discount
will be assessed"* → SELALU ambil TERBESAR, tidak pernah dijumlah.

- **Test 1** (AHS-Dimension only, longest=130cm) → charge=431.000 ✓
- **Test 2** (AHS-Weight only, 30kg) → charge=431.000 ✓
- **Test 3** (Oversize+AHS-Dim bareng, longest=250cm) → ambil TERBESAR
  (Oversize, 1.072.000), **DAN** floor 18kg tetap berlaku karena AHS-Dim
  juga terpenuhi (sesuai catatan PDF: *"If subject to Oversize Charge, and
  also meets AHS-Dimension criteria, the 18kg minimum will still apply"*) ✓
- **Test 4** (Unauthorized+Oversize+AHS-Dim bareng, longest=280cm) → ambil
  TERBESAR (Unauthorized, 4.447.000), floor 18kg tetap berlaku ✓

**Freight (IPF/IEF):** PDF eksplisit HANYA untuk kombinasi yang melibatkan
Unauthorized Freight Charge — *"if...also meets the criteria for either
AHS-Freight or Non-Stackable...only the highest charge will apply"*.

- **Test 5** (AHS-Freight+Non-Stackable, TANPA Unauthorized) → **DIJUMLAH**
  (6.644.000). Kode secara eksplisit memberi catatan bahwa ini ASUMSI karena
  PDF tidak mengatur kombinasi spesifik ini — transparan, bukan diam-diam
  ditebak. **Perlu konfirmasi ke FedEx CS** kalau butuh kepastian 100%. ⚠️
- **Test 6** (Unauthorized+AHS-Freight+Non-Stackable bareng) → ambil
  TERBESAR (7.306.000) ✓

### ✅ Chargeable Weight (CWT) / Dimensional Weight

- **Test 7**: package actual=2kg, dimensional=10,4kg, TAPI AHS-Dimension
  floor 18kg menang → CWT=18kg. Sesuai PDF: *"invoice weight will be the
  sum of the higher actual weight or dimensional weight"* + floor 18kg
  kalau kena AHS-Dimension ✓
- Divisor 5.000 sesuai PDF (*"5,000 for centimeters"*) ✓
- CWT freight (IPF/IEF): TANPA floor 18kg (floor itu murni aturan IP/IE) —
  sudah dikonfirmasi user sebelumnya (7 Sep 2026) ✓

**Kesimpulan bagian ini: 0 bug ditemukan.** Satu-satunya area abu-abu (Test 5,
AHS-Freight+Non-Stackable tanpa Unauthorized) sudah ditandai eksplisit
sebagai asumsi di kode, bukan bug tersembunyi.

---

## 2. `special_handling.py` — Address Correction, ISR/DSR/ASR, dll

### ✅ Nominal — cocok persis

| Fee | Nominal | Status |
|---|---|---|
| Address Correction | Rp187.000/shipment | ✅ |
| Third Party Consignee | Rp163.000/shipment | ✅ |
| FedEx Intl Broker Select | Rp163.000 atau Rp19.000/kg, mana lebih besar | ✅ |
| Saturday Pick Up / Delivery | Rp250.000 masing-masing | ✅ |
| Inbound Processing Fee | Rp44.000, tujuan US atau 27 negara EU | ✅ |
| ISR / DSR / ASR | Rp53.000 / Rp59.000 / Rp75.000, non-freight saja | ✅ |
| Residential Delivery | Rp55.000 (non-freight) / Rp1.772.000 (freight), US & Canada saja | ✅ |
| Accessible/Inaccessible DG | Rp1.890.000 atau Rp34.000/kg / Rp885.000 atau Rp13.000/kg | ✅ |
| Dry Ice | Rp82.000/shipment | ✅ |

### ✅ Aturan interaksi — dibuktikan lewat test

- **Test 1**: Broker Select 20kg → `max(163000, 19000×20)=380.000` (per-kg
  menang) ✓
- **Test 2**: Residential + ODA bareng (Canada) → Residential **dibatalkan
  total** (mutually exclusive sesuai PDF: *"If the ODA Surcharge is applied
  to a shipment, the Residential Delivery Surcharge will not apply"*) ✓
- **Test 3**: Residential ke Singapura (bukan US/Canada) → diabaikan ✓
- **Test 4**: Dangerous Goods + Dry Ice bareng → Dry Ice **dibatalkan**,
  cuma DG yang charge (sesuai PDF: *"If a shipment contains both dry ice and
  dangerous goods...only dangerous goods surcharge applies"*) ✓
- **Test 5**: **Semua 27 negara EU** dari PDF (Austria s.d. Sweden, PERSIS
  sesuai footnote resmi) dicek satu-satu → semua kena Inbound Processing Fee
  saat export. Dites juga bahwa ini HANYA berlaku arah export (bukan import)
  ✓
- **Test 6**: ISR di service freight (IPF) → diabaikan dengan catatan jelas
  ("hanya berlaku non-freight") ✓

**Kesimpulan bagian ini: 0 bug ditemukan.** Known limitations yang di-disclose
sendiri di kode (declared value ISR/DSR tidak divalidasi, lokasi Jakarta/Batam
utk DG tidak divalidasi otomatis) itu keterbatasan DATA yang memang belum ada
di kalkulator ini, bukan salah implementasi dari yang SUDAH ada datanya.

---

## 3. `core.py` — OPA/ODA Tariff & Demand Surcharge

### ✅ Nominal — cocok persis

- OPA: Tier A n/a, Tier B Rp339.000/6.000 per kg, Tier C Rp442.000/8.000 per
  kg (whichever greater) ✅
- ODA: Tier A Rp52.000 flat (TIDAK ada opsi per-kg), Tier B & C sama seperti
  OPA ✅
- Demand Surcharge: semua nilai per region (Export & Import, Priority vs
  Economy) di `DEMAND_SURCHARGE_TABLE` cocok persis dengan
  `demand_surcharge_update_4_sep_2026.pdf` ✅
- Minimum Rp4.200/shipment (demand surcharge) ✅

### ✅ Dibuktikan lewat test

- OPA Tier B, 100kg → `max(339000, 6000×100=600000)` → per-kg menang,
  charge=600.000 ✓
- ODA Tier A, 1000kg → tetap flat 52.000 (TIDAK ikut per-kg meski beratnya
  besar) ✓
- Demand surcharge Vietnam (rate 0/kg) → minimum Rp4.200 tetap berlaku ✓
- US export: Priority(IP)=26.800/kg vs Economy(IE)=20.100/kg — beda kolom
  terbukti kepakai sesuai service ✓
- 3 negara tanpa service (Norfolk Island/Syria/Yemen, dikonfirmasi user 7 Sep
  2026 bahwa ini bukan gap data) → `applied: False`, TIDAK menebak region
  sembarangan ✓

**Kesimpulan bagian ini: 0 bug ditemukan.**

---

## 4. Belum diaudit di sesi ini

- **`oda_opa.py`** (engine lookup tier ODA/OPA dari database 67.600 kode
  pos/kota, 114 negara) — ini validasi DATA MASIF (bukan logic kecil kayak
  di atas), butuh pendekatan beda (sampling terprogram dari raw source
  Excel/CSV, bukan baca kode). Belum dikerjakan.
- **Fuel Surcharge** — sengaja tidak di-hardcode (berubah tiap Senin),
  jadi tidak ada "nilai resmi" untuk diaudit; parameter input manual.
- **Duty & Tax, Declared Value Charge for Carriage** — belum diimplementasikan
  di kalkulator ini sama sekali (lihat known_limitations calculator.py lama).

---

## Ringkasan

| Modul | Item diaudit | Bug ditemukan | Status |
|---|---|---|---|
| `nonstandard.py` | 8 surcharge + CWT + formula girth | 0 | ✅ Semua cocok, 7 test PASS |
| `special_handling.py` | 9 fee + 4 aturan interaksi | 0 | ✅ Semua cocok, 6 test PASS |
| `core.py` | OPA/ODA (3 tier) + Demand Surcharge (12 region × 2 arah) | 0 | ✅ Semua cocok, 5 test PASS |
| `oda_opa.py` | — | — | ⏳ Belum diaudit |

**Total: 18 test numerik dijalankan, 18 PASS, 0 bug.** Beda dengan audit UPS
Commercial (yang menemukan bug nyata soal named-group override A26/B26),
audit FedEx surcharge kali ini **tidak menemukan bug** — kemungkinan besar
karena modul ini memang sudah dikerjakan & diperbaiki bertahap sepanjang
sesi-sesi sebelumnya (termasuk fix formula girth), bukan migrasi
sekali-jadi seperti UPS.
