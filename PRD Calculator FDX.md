# PRD — FedEx Indonesia Rate Calculator

**Status:** Tahap 6 (aktif dikembangkan) | **Terakhir diupdate:** 7 September 2026

## 1. Latar Belakang & Tujuan

Tim operasional/sales butuh cara cepat & konsisten untuk menghitung estimasi
biaya pengiriman FedEx dari/ke Indonesia — mencakup base rate, ODA/OPA
surcharge, demand surcharge, non-standard shipment fee, dan special handling
fee — tanpa harus membuka banyak PDF rate card FedEx secara manual setiap
kali kasih quote ke customer.

**Tujuan produk:**
- Satu sumber kebenaran (single source of truth) untuk semua komponen biaya
  yang bisa dihitung dari data resmi FedEx (PDF rate card + Excel ODA/OPA).
- Bisa dipakai dua cara: sebagai **library Python** (untuk integrasi/automasi)
  dan sebagai **UI interaktif** (untuk dipakai langsung oleh non-engineer).
- Transparan soal apa yang **belum** bisa dihitung otomatis (lihat §7), supaya
  tidak ada asumsi salah yang dipakai untuk keputusan bisnis/quote ke customer.

## 2. Cakupan Service & Arah

- Service: **IP, IE, IPF, IEF** (IPE sengaja tidak dicakup).
- Arah: **export** (dari Indonesia) & **import** (ImportOne, ke Indonesia).

## 3. Arsitektur & Dua Implementasi

Produk ini punya **dua implementasi paralel** dari logika kalkulasi yang sama,
untuk dua use case berbeda. Keduanya **tidak saling generate otomatis** —
perubahan logika di satu sisi harus di-porting manual ke sisi lain kalau
ingin tetap sinkron.

| | **Backend Python** | **Kalkulator standalone** |
|---|---|---|
| File utama | `calculator.py` (orkestrator) + `app.py` (UI Streamlit), rate engine di `rates.py`/`rate_common.py`/`rates_promotional.py`/`rates_commercial.py` (§4.3) | `index.html` (single-file, semua logic di JS inline) |
| Target user | Integrasi/automasi, atau siapapun yang bisa `pip install streamlit` | Siapapun — tinggal buka file di browser, tanpa install apapun |
| Distribusi | Perlu Python + `streamlit run app.py` | 1 file HTML (~2.3MB karena data ODA/OPA di-embed langsung) |
| Cakupan ODA/OPA | Lihat §5.2 (built-in lookup engine `oda_opa.py` sebenarnya generik, tapi wrapper `calculate()` cuma expose sisi Indonesia — lihat known limitation §7.1) | Lihat §5.2 — **sudah** cek kedua sisi (Indonesia & negara lawan) sejak update Tahap 4b |

**Modul-modul di backend Python:**
- `rates.py` — **façade tipis** (dispatcher), TIDAK berisi data/logic sendiri
  lagi sejak refactor Tahap 6 (lihat §4.3). Titik masuk tunggal yang dipanggil
  `calculator.py`/`app.py` lewat `rates.calculate_base(..., rate_type=...)`;
  dispatch ke modul rate_type yang sesuai + re-export nama-nama publik lama
  (`ZONES`, `ZONE_INDEX`, `RATES`, `COMMERCIAL_ZONES`, dst) supaya kompatibel
  ke belakang.
- `rate_common.py` — util & **pricing engine generik** yang dipakai bareng
  SEMUA rate_type: parser tabel rate (`parse_doc_table`/`parse_band_table`/
  `parse_flat_table`), `resolve_china_zone()`, `price_from_table()` (logic
  pemilihan Envelope/Pak/tabel bertahap/band per-kg — sama persis utk semua
  rate_type, cuma beda tabel & zone yang dikirim caller).
- `rates_promotional.py` — data & lookup khusus **rate_type="promotional"**
  (default): zone index A-G (`ZONE_INDEX`), tabel rate dari
  `fedex-rates-exp/imp-en-id-2026.pdf` (Envelope, Pak, IP/IE bertahap 0.5kg,
  band per-kg IP/IE >20kg, 4 varian leg IPF/IEF).
- `rates_commercial.py` — data & lookup khusus **rate_type="commercial"**
  (lihat §4.3 utk detail lengkap): zone index 20-huruf (`COMMERCIAL_ZONE_INDEX`),
  tabel rate dari `Rate_FDX_Exsis_Export.xls`/`Rate_FDX_Exsis_Import.xls`,
  alias & daftar negara unavailable.
- `oda_opa.py` — engine lookup tier ODA/OPA generik per negara, mendukung
  pencarian by kode pos (numerik maupun alfanumerik) atau by nama kota,
  tergantung format data negara tsb.
- `oda_opa_tiers.csv` — hasil ekstraksi dari `ODA_OPA_tiers_codes.xlsx`
  (67.608 baris, 114 negara).
- `surcharges.py` — nominal IDR per tier ODA/OPA, tabel Demand Surcharge
  (efektif 21 Sep 2026) + mapping negara→region.
- `nonstandard_fees.py` — Non-Standard Shipment Fees per package (IP/IE) dan
  per freight handling unit (IPF/IEF), termasuk aturan kombinasi.
- `special_handling_fees.py` — Special Handling Fees berbasis flag/pilihan
  shipper.
- `calculator.py` — orkestrator: `calculate()` menggabungkan semua komponen
  di atas + fuel surcharge (manual) jadi satu breakdown + subtotal.
- `app.py` — UI web Streamlit di atas `calculator.py` (tidak ada logika yang
  diduplikasi, semua panggil modul yang sama).

**Cara nambah rate_type baru (misal ada kontrak/rate sheet lain lagi ke
depan):** bikin 1 file `rates_<nama>.py` yang import util dari
`rate_common.py` (parser tabel + `price_from_table()`), definisikan zone
index & tabel rate sendiri, lalu fungsi `calculate_base(...)` dengan shape
return yang sama seperti `rates_promotional.py`/`rates_commercial.py`.
Daftarkan di `_RATE_TYPE_MODULES` (satu baris) dalam `rates.py`. **Tidak
perlu** sentuh `rates_promotional.py`, `rates_commercial.py`, `calculator.py`,
atau `app.py` sama sekali — inilah alasan utama refactor Tahap 6 (§10).

## 4. Fitur — Base Rate

- Lookup zone per negara & service dari `RATES_DATA`/`rates.py`.
- China dipecah otomatis jadi 3 baris zone berdasar kode pos (Fujian &
  Guangdong → Zone B, selain itu → Zone C default), sesuai
  `fedex-rates-zi-en-id-2026.pdf`.
- Mode harga: flat per-kg step (Envelope/Pak/Doc <0.5–20.5kg), atau band
  per-kg untuk berat besar/freight, tergantung service & leg type (freight).
- Hasil dibulatkan ke atas ke kelipatan 1.000 (`roundUp1000`).

### 4.3 Rate Type: Commercial (Exsis) — baru, 6-7 Sep 2026

Selain rate promosi standar (`rate_type="promotional"`, default), kalkulator
sekarang mendukung **rate net/list khusus customer** — dipanggil "Commercial"
di UI — lewat parameter `rate_type="commercial"` di `calculate_base()`/
`calculate()`.

**Sumber data:** `Rate_FDX_Exsis_Export.xls` & `Rate_FDX_Exsis_Import.xls`
(customer EXPRESSINDO SYSTEM NETWORK, akun 206071531, Proposal No. 16802977 /
16803019, efektif 05 September 2026). File `.xls` ini sebenarnya format XML
SpreadsheetML (bukan biner Excel asli) — diparse pakai `xml.etree.ElementTree`,
bukan `openpyxl`/`xlrd`.

**Perbedaan dari rate promosi (bukan cuma beda angka):**
- **Zone letter beda & lebih banyak**: 20 huruf (`COMMERCIAL_ZONES` = B, C, D,
  E, F, G, K, M, N, O, P, Q, R, S, U, V, W, X, Y, Z), bukan 7 huruf A-G.
- **Availability per service dicek terpisah per negara** — promotional cuma
  bedakan grup IP+IPF vs IE+IEF (1 zone letter dipakai berdua); commercial
  simpan 4 kolom sendiri-sendiri (IP/IE/IPF/IEF bisa beda zone, atau salah
  satu `None`/tidak tersedia sama sekali untuk negara tsb).
- **Zone chart export & import tidak identik** — beberapa negara servicenya
  tersedia di satu arah tapi tidak di arah lain (2 tabel zone terpisah).
- **Cakupan negara beda**: 207 negara/wilayah (vs 229 di promotional) —
  konsekuensinya 2 hal berikut:
  - **34 alias negara** (`COMMERCIAL_ALIASES`) — ejaan/penamaan beda antara
    dua rate sheet meski negaranya sama, contoh: "Bahamas"→"Bahama",
    "Moldova"→"Republic of Moldova", "Ivory Coast"→"Côte D'ivoire (Ivory
    Coast)", "United States (Rest of Country)"→"U.S.A.", "Philippines"→
    "Phillipines" (typo asli di rate sheet Exsis, bukan typo kita).
  - **8 negara unavailable** (`COMMERCIAL_UNAVAILABLE_COUNTRIES`): Canary
    Islands, Channel Islands, Norfolk Island, San Marino, St. Barthelemy,
    St. Eustatius, Vatican City, Saba — memang tidak ada rate commercial-nya
    sama sekali di rate sheet customer ini. Kalau dipilih,
    `calculate_base()` **raise `FedExRateError` dengan pesan jelas**
    (bukan silent fallback ke promotional atau angka kosong).
- China tetap dipecah "South"/"Excluding South" berdasar kode pos
  Fujian/Guangdong (sama seperti promotional), tapi diterjemahkan ke zone
  letter commercial yang beda (K untuk South, W untuk Excluding South —
  vs B/C di promotional).

**Disclaimer penting** (ditampilkan di setiap hasil commercial rate): rate ini
adalah **net rate, TIDAK legally binding** — kalau beda dengan invoice resmi
FedEx, invoice yang berlaku. Exclude pajak, surcharge, ancillary fee,
duty/tax, dan special handling fee (surcharge lain di kalkulator ini —
ODA/OPA, demand surcharge, non-standard fee, dll — tetap dihitung normal,
lihat §7 poin baru soal ini).

**UI:** toggle "Promotional / Commercial (Exsis)" di sidebar `app.py`.
**Belum ada di `index.html`** — lihat §7 & §11.

## 5. Fitur — ODA/OPA Surcharge

### 5.1 Aturan dasar
- **Export**: sisi **pickup** (Indonesia) dicek OPA, sisi **delivery**
  (negara tujuan) dicek ODA.
- **Import**: sisi **pickup** (negara asal) dicek OPA, sisi **delivery**
  (Indonesia) dicek ODA.
- Tarif per tier (No/A/B/C) diambil dari `OPA_TARIFF`/`ODA_TARIFF` —
  charge = `max(per_shipment, per_kg × billed_weight)`.

### 5.2 Cakupan data & mekanisme lookup (114 negara di `oda_opa_tiers.csv`)
Data ODA/OPA FedEx tidak seragam formatnya per negara — jadi mekanisme
lookup-nya juga berbeda 3 jenis:

1. **Rentang kode pos numerik** (42 negara termasuk Indonesia, China, US,
   Jerman, Jepang, dll) — cek `begin_postal ≤ kode_pos ≤ end_postal`.
2. **Rentang kode pos alfanumerik** (2 negara: **Kanada** & **Inggris/GB**,
   format kode pos "K1A", "AB37" dsb) — perbandingan string, bukan angka.
3. **Nama kota exact-match** (70 negara: Argentina, UEA, Vietnam, Selandia
   Baru, Ukraina, dll — negara-negara ini TIDAK punya data rentang kode pos
   sama sekali di sumber FedEx) — dicocokkan case-insensitive tapi ejaan
   harus sama persis dengan yang ada di data.

Status implementasi per sisi:
- **Indonesia** (kode pos, selalu tersedia di form): numerik, 3.140 baris.
- **China** (kode pos, field khusus): numerik, 4.068 baris — sekaligus
  dipakai untuk auto-detect Zone B/C (lihat §4).
- **40 negara lain berbasis kode pos numerik**: didukung di `index.html`
  lewat field generik "Kode pos negara lawan" yang otomatis muncul & ganti
  label sesuai negara yang dipilih.
- **Kanada & Inggris (alfanumerik)**: didukung lewat mekanisme yang sama,
  perbandingan string bukan integer.
- **70 negara berbasis kota**: field yang sama otomatis berubah jadi input
  nama kota (dengan `<datalist>` saran kota) begitu negara yang dipilih
  termasuk grup ini.

⚠️ **Perbedaan implementasi backend vs standalone (lihat §7.1):** engine
`oda_opa.py` di backend Python sebenarnya sudah generik (bisa lookup negara
manapun by kode pos/kota), tapi wrapper `calculator.calculate()` saat ini
hanya expose parameter `indonesia_postal_code` — sisi negara lawan **belum**
dicek otomatis di backend/Streamlit. Sebaliknya, `index.html` sudah
mem-porting ulang seluruh mekanisme di atas secara manual dalam JS dan
**sudah** mengecek kedua sisi untuk ke-112 negara (semua kecuali yang tidak
match nama negara sama sekali).

### 5.3 Validasi
Setiap penambahan data lookup baru divalidasi silang: sample acak diambil
dari `oda_opa_tiers.csv`, dijalankan lewat `oda_opa.py` (Python, sumber
rujukan) dan lewat implementasi JS di `index.html`, hasilnya dibandingkan
harus identik 100% sebelum dianggap selesai.

## 6. Fitur Lain

### 6.1 Demand Surcharge (efektif 21 Sep 2026)
- Tarif per region (Asia, Europe, LAC, MEISA Group 1/2, dll) × arah × tipe
  service (priority/economy), minimum per-shipment Rp4.200.
- Mapping negara→region lengkap **228 dari 231 negara** di Zone Index,
  mengikuti footnote resmi di `demand_surcharge_update_4_sep_2026.pdf`.
  3 negara (Norfolk Island, Syria, Yemen) sengaja dibiarkan tidak terpetakan
  — **dikonfirmasi user (7 Sep 2026): memang FedEx tidak ada service ke 3
  negara ini**, jadi ini bukan gap data yang perlu diperbaiki. Kalau
  dipilih, demand surcharge TIDAK dihitung & muncul catatan eksplisit
  (perilaku ini sudah benar, dipertahankan apa adanya).

### 6.2 Non-Standard Shipment Fees
- Per package/collie (IP/IE): AHS-Dimension/Weight/Packaging, Oversize,
  Unauthorized Package.
- Per freight handling unit (IPF/IEF): AHS-Freight, Non-Stackable,
  Unauthorized Freight.
- Aturan kombinasi (ambil tertinggi vs dijumlah) mengikuti
  `fedex-rates-sur-en-id-2026.pdf`.

**Formula Length + Girth (revisi, 7 Sep 2026):** `length_cm` dipakai **apa
adanya** sebagai "Length" (field yang diisi user, BUKAN hasil sortir 3 sisi),
dan `Girth = 2×width_cm + 2×height_cm` (dua field lain, juga apa adanya, tidak
disortir). Jadi:

```
Length + Girth = length_cm + 2×width_cm + 2×height_cm
```

Asumsi lama (3 sisi diurutkan, sisi terbesar dianggap "Length", girth dari 2
sisi sisanya) **SALAH** dan sudah dikoreksi user di
`aturan_rumus_rate_fedex.txt` — jangan dikembalikan ke logika sortir.
Implementasi: fungsi `_longest_and_length_plus_girth()` di
`nonstandard_fees.py` (satu fungsi ini dipakai semua caller — cek AHS/
Oversize/Unauthorized package & freight, plus auto-switch §6.5 — jadi
perbaikannya otomatis merambat ke semua tempat tanpa perlu ubah lokasi lain).
**Konsekuensi:** urutan input Length/Width/Height dari user sekarang penting
— form harus punya label jelas & user harus isi sesuai definisi FedEx (Length
= sisi yang mereka anggap "panjang"), karena tidak ada lagi sortir otomatis
yang "memaafkan" input asal-asalan seperti sebelumnya.

### 6.3 Special Handling Fees
Address Correction, Third Party Consignee, Third Party Billing (2,5%),
FedEx International Broker Select, Saturday Pick Up/Delivery, Inbound
Processing Fee (auto-detect US/EU untuk arah export), ISR/DSR/ASR,
Residential Delivery (mutually exclusive dengan ODA), Accessible/
Inaccessible Dangerous Goods, Dry Ice (mutually exclusive dengan Dangerous
Goods).

### 6.4 Fuel Surcharge
Manual — user isi sendiri persentase mingguan dari
`https://www.fedex.com/en-id/shipping/surcharges.html` (tidak ada API resmi
untuk ini).

### 6.5 Auto-switch IP/IE → IPF/IEF & wajib-split (baru, 6 Sep 2026)
Per collie, kalau salah satu kriteria berikut terpenuhi, collie itu **wajib**
dikirim sebagai freight (IPF/IEF), tidak boleh lagi sebagai IP/IE:
1. Berat aktual **≥ 68 kg**/collie.
2. `length_cm` + Girth (2×width_cm + 2×height_cm) **> 330 cm**/collie — lihat
   formula revisi di §6.2 (kalau dipaksakan tetap IP/IE, kena Oversize Charge
   Rp1.072.000/collie atau Unauthorized Package Charge Rp4.447.000/collie,
   tergantung seberapa jauh melebihi batas).
3. `length_cm` (field "Length" apa adanya, **bukan** hasil sortir — lihat
   §6.2) **≥ 274 cm**/collie.

Perilaku:
- **Semua** collie dalam shipment melebihi batas → service **otomatis**
  dialihkan ke IPF/IEF, packages dikonversi jadi freight_units (Python:
  `calculator.calculate()` parameter `auto_switch_service=True`, default
  aktif; JS: `index.html` menampilkan popup notifikasi lalu lanjut hitung).
- **Sebagian** (bukan semua) collie melebihi batas, sementara collie lain
  masih dalam batas IP/IE → **wajib split** jadi 2 pengiriman terpisah (satu
  AWB tidak boleh campur service). Python: raise
  `nonstandard_fees.ShipmentSplitRequired` (harus ditangani caller — `app.py`
  menangkapnya dan menampilkan error box detail per collie). JS: popup
  notifikasi, perhitungan dibatalkan.
- Diimplementasikan **identik** di kedua sisi (Python & `index.html`), sudah
  diverifikasi paritas hasil via Node.js.

### 6.6 Chargeable Weight / CWT (baru, 6 Sep 2026; **diperluas ke IPF/IEF 7 Sep 2026**)
Utk shipment dengan `packages`/`freight_units` diisi, billed weight yang
dipakai utk base rate **bukan lagi** cuma actual weight, tapi **Chargeable
Weight (CWT)** = jumlah, per piece, dari yang PALING BESAR antara:
- Actual weight (kg)
- Dimensional/volumetric weight = Panjang × Lebar × Tinggi (cm) / 5.000
- **Khusus IP/IE**: 18kg (floor), **kalau** collie itu juga kena kriteria
  AHS-Dimension (lihat §6.2) — ini otomatis mengisi limitasi lama soal
  minimum billable weight.

Sesuai `fedex-rates-sur-en-id-2026.pdf`: *"invoice weight will be the sum of
the higher actual weight or dimensional weight of each individual package"*.

**Berlaku utk KEDUA jenis service:**
- **IP/IE (non-freight)**, `packages` diisi: per-package, PLUS floor 18kg
  kalau kena AHS-Dimension. Python: `nonstandard_fees.compute_shipment_chargeable_weight()`.
- **IPF/IEF (freight)**, `freight_units` diisi: per-unit, **TANPA** floor
  18kg (floor itu murni aturan AHS-Dimension yang cuma berlaku utk IP/IE).
  Python: `nonstandard_fees.compute_freight_chargeable_weight()`. Kalau
  `width_cm`/`height_cm` sebuah unit tidak diisi (opsional utk freight),
  dimensional weight unit itu di-skip, cuma pakai actual weight.
  **Divisor 5.000 SAMA dengan IP/IE** — dikonfirmasi user (7 Sep 2026), tidak
  ada divisor freight yang berbeda. Ini menyelesaikan roadmap poin lama soal
  "cek ke FedEx CS apakah IPF/IEF punya divisor sendiri" (§11 versi lama).
  Berlaku juga otomatis kalau shipment kena auto-switch IP/IE→IPF/IEF (§6.5)
  — `freight_units` hasil konversi tetap dihitung CWT-nya.

Parameter `apply_dimensional_weight=True` (default aktif) di `calculate()`
mengaktifkan ini utk kedua kasus sekaligus; hasil breakdown per piece ada di
`result["chargeable_weight"]`. Set `False` utk kembali ke actual weight apa
adanya (perilaku lama) — berlaku ke keduanya juga.

### 6.7 Diskon Base Rate (baru, 6 Sep 2026)
Dropdown pilihan diskon **5% s.d. 90%, kelipatan 5%** (plus "Tidak ada
diskon"), dipotong **dari Base Rate saja** — TIDAK dari ODA/OPA, demand
surcharge, non-standard/special handling fees, atau fuel surcharge (fuel
surcharge tetap dihitung dari Base Rate ASLI/sebelum diskon, sesuai perilaku
`fuel_surcharge_pct` yang sudah ada sebelumnya).

Ditampilkan sbg baris terpisah "Diskon Base Rate (X%)" dengan nominal negatif
di breakdown, supaya tetap transparan (bukan diam-diam mengubah angka Base
Rate). Python: parameter `discount_pct` di `calculate()` (contoh: `15` utk
15%), hasil di `result["discount"]`. Streamlit (`app.py`): dropdown "Diskon
dari Base Rate" di sidebar. JS (`index.html`): dropdown `#discount_pct` di
sidebar form. Sudah diverifikasi paritas hasil Python ↔ JS via Node.js.

Kalau ke depan diskon kontrak FedEx ternyata TIDAK persis kelipatan 5% (mis.
12,5% atau custom per pelanggan), dropdown ini perlu diganti/ditambah opsi
input manual — saat ini hanya preset kelipatan 5% sesuai permintaan.

## 7. Known Limitations (baca sebelum pakai untuk keputusan bisnis)

1. **Backend Python (`calculator.py`/`app.py`) hanya cek ODA/OPA di satu
   sisi** sesuai arah pengiriman (Indonesia). Sisi negara lawan belum
   di-expose di wrapper `calculate()` — meskipun engine `oda_opa.py` di
   baliknya sudah mendukung lookup negara manapun. *(Standalone
   `index.html` sudah tidak punya limitasi ini sejak Tahap 4b — lihat §5.2.)*
2. **Fuel surcharge** wajib diisi manual.
3. **Demand surcharge**: 3 negara (Norfolk Island, Syria, Yemen) belum
   terpetakan ke region manapun (lihat §6.1).
4. **Non-Standard Shipment Fees** — ~~18kg minimum billable weight & dimensional
   weight belum dihitung~~ **SUDAH DISELESAIKAN** lewat fitur CWT (§6.6, sejak
   6 Sep 2026). Sisa limitasi: flag AHS-Packaging tetap manual (tidak ada cara
   otomatis mendeteksi bentuk kemasan dari data numerik).
5. **Special Handling Fees**:
   - ISR/DSR/ASR: kriteria resmi "declared value for Carriage" (< / ≥
     USD500/CAD500) & residential-ness tidak divalidasi otomatis — flag
     murni keputusan manual shipper (hanya divalidasi non-freight IP/IE).
   - Accessible/Inaccessible Dangerous Goods & Dry Ice hanya berlaku untuk
     shipment dengan origin/destination Great Jakarta atau Batam — tidak
     divalidasi otomatis (kalkulator tidak melacak kota asal/tujuan secara
     umum).
   - Residential Delivery Surcharge & Inbound Processing Fee tidak
     memvalidasi status "FedEx 10kg/25kg Box shipment".
6. **Pajak/PPN dan duty/tax tidak dihitung.**
7. **Footnote ketersediaan service per negara** (superscript 1/2 di Zone
   Index PDF) belum diterapkan sebagai flag — semua negara dianggap
   tersedia.
8. **Data ODA/OPA per negara tidak lengkap** untuk semua kombinasi kode
   pos/kota yang mungkin ada di dunia nyata — kalau tidak ketemu match
   persis, diasumsikan "No surcharge", dengan catatan eksplisit untuk selalu
   dicek manual ke FedEx CS kalau ragu.
9. **Kota harus dieja persis sama** dengan data sumber untuk 70 negara
   berbasis kota (§5.2) — tidak ada fuzzy matching atau normalisasi ejaan
   selain lowercase + trim spasi.
10. ~~**Freight (IPF/IEF) belum punya CWT/dimensional weight sendiri**~~
    **SUDAH DISELESAIKAN di backend Python** (7 Sep 2026, lihat §6.6) —
    divisor 5.000 dikonfirmasi user sama dengan IP/IE, tanpa floor 18kg.
    **Belum di-porting ke `index.html`** (JS) — `computeShipmentChargeableWeight()`
    di sana masih cuma cover IP/IE, freight_units belum dapat CWT di sisi JS.
11. **Commercial Rate (§4.3) belum ada di `index.html`** — standalone masih
    cuma dukung `rate_type="promotional"`. Kalau `index.html` dipakai aktif
    utk quote yang butuh rate Commercial, HARUS pakai `app.py`/Python dulu
    sampai porting selesai (lihat §11).
12. **Surcharge lain (ODA/OPA, demand surcharge, non-standard/special
    handling fees) TIDAK punya versi khusus per rate_type** — dihitung sama
    persis terlepas dari `rate_type="promotional"` atau `"commercial"` yang
    dipilih. Ini asumsi implisit (belum dikonfirmasi ke FedEx CS) bahwa
    surcharge-surcharge itu tidak berubah karena beda rate sheet/kontrak
    customer — kalau ternyata rate sheet Commercial juga punya
    surcharge/tarif ODA-OPA sendiri yang beda dari yang dipakai sekarang,
    ini perlu direvisi.
13. **Commercial Rate net rates tidak legally binding** — sesuai disclaimer
    resmi di rate sheet sumber (`Rate_FDX_Exsis_Export/Import.xls`): kalau
    beda dengan invoice resmi FedEx, invoice yang berlaku. Jangan dipakai
    sebagai angka final tanpa konfirmasi ke FedEx Representative/CS untuk
    quote bernilai besar.

## 8. Sumber Data Resmi

- `fedex-rates-zi-en-id-2026.pdf` — Zone Index.
- `fedex-rates-exp-en-id-2026.pdf` / `fedex-rates-imp-en-id-2026.pdf` —
  rate dasar export/import.
- `fedex-rates-sur-en-id-2026.pdf` — Surcharge & Other Information
  (Non-Standard Shipment Fees + Special Handling Fees).
- `demand surcharge update 4 sep 2026.pdf` — Demand Surcharge & mapping
  region.
- `ODA_OPA_tiers_codes.xlsx` → diekstrak jadi `oda_opa_tiers.csv`.
- `aturan_rumus_rate_fedex.txt` — ringkasan kriteria dimensi/berat (referensi
  sekunder; nominal & detail final tetap dari PDF resmi). **Sudah direvisi
  7 Sep 2026** soal formula Length + Girth (lihat §6.2) — versi lama di file
  ini (kalau masih ada salinan lama beredar) sudah tidak berlaku.
- `Rate_FDX_Exsis_Export.xls` / `Rate_FDX_Exsis_Import.xls` — sumber
  **Commercial Rate** (§4.3), customer EXPRESSINDO SYSTEM NETWORK, Proposal
  No. 16802977/16803019, efektif 05 Sep 2026. Format XML SpreadsheetML,
  bukan biner Excel asli.

## 9. Cara Pakai

### Library Python
```python
from calculator import calculate, format_result

r = calculate(
    service="IP", direction="export", country="Singapore", weight_kg=2.0,
    indonesia_postal_code="14510",
    fuel_surcharge_pct=15,
)
print(format_result(r))

# Rate Commercial (Exsis) - lihat §4.3, ejaan negara ikuti alias/zone chart
# commercial (bisa beda dari promotional, contoh "U.S.A." bukan "United
# States (Rest of Country)")
r2 = calculate(
    service="IP", direction="export", country="Singapore", weight_kg=2.0,
    rate_type="commercial",
)
print(format_result(r2))
```

### UI Streamlit
```bash
pip install streamlit --break-system-packages
streamlit run app.py
```
Buka `http://localhost:8501`. UI berisi: sidebar (service, arah, negara,
berat, leg type, ODA/OPA Indonesia, fuel surcharge), tab Non-Standard
Shipment Fees, tab Special Handling Fees, dan tombol Hitung Rate dengan
breakdown + catatan lengkap.

### Kalkulator standalone
Buka `index.html` langsung di browser — tidak perlu install apapun. Semua
data (termasuk 3 mekanisme lookup ODA/OPA di §5.2) sudah ter-embed di
dalam file.

## 10. Riwayat Perubahan (ringkas)

- **Tahap 1–3**: base rate, ODA/OPA sisi Indonesia, non-standard shipment
  fees, demand surcharge.
- **Tahap 4**: Special Handling Fees + UI Streamlit (`app.py`).
- **Tahap 4b (6 Sep 2026)**: `index.html` di-upgrade untuk cek ODA/OPA di
  **kedua sisi** pengiriman, mencakup seluruh 112 dari 114 negara di
  `oda_opa_tiers.csv` (numerik, alfanumerik Kanada/Inggris, dan kota untuk
  70 negara). "Netherlands Antilles" tidak dipetakan karena bukan opsi
  negara yang valid di daftar negara kalkulator (wilayah sudah bubar).
  Bug kode pos alfanumerik Kanada/Inggris (sempat 0 data karena filter
  numerik-only) ditemukan & diperbaiki di tahap ini juga.
- **Tahap 4c (6 Sep 2026)**: Auto-switch IP/IE → IPF/IEF & wajib-split
  (§6.5) di-port dari `index.html` (sudah ada duluan) ke backend Python
  (`nonstandard_fees.py`/`calculator.py`/`app.py`) — sebelumnya HANYA ada di
  JS, sekarang identik di kedua sisi (diverifikasi paritas via Node.js).
  Fitur baru **Chargeable Weight/CWT** (§6.6) ditambahkan ke KEDUA sisi
  sekaligus (sebelumnya belum ada sama sekali) — menyelesaikan limitasi lama
  soal dimensional weight & minimum 18kg billable weight.
- **Tahap 4d (6 Sep 2026)**: Fitur **Diskon Base Rate** (§6.7) — dropdown
  preset 5% s.d. 90% (kelipatan 5%) ditambahkan ke Python (`calculate()`),
  Streamlit (`app.py`), dan JS (`index.html`) sekaligus.
- **Tahap 5 (6-7 Sep 2026)**: Fitur **Rate Type: Commercial (Exsis)** (§4.3)
  — base rate kedua (net rate customer EXPRESSINDO SYSTEM NETWORK) dari
  `Rate_FDX_Exsis_Export/Import.xls`, dipilih lewat parameter
  `rate_type="commercial"`. Semua base rate dicocokkan manual terhadap XLS
  sumber sebelum dianggap selesai (100% match). Ditambahkan ke `rates.py`,
  `calculator.py`, `app.py` (toggle sidebar). **Belum** di-porting ke
  `index.html` (lihat §7 poin 11 & §11).
- **Revisi formula Length + Girth (7 Sep 2026)**: koreksi dari user —
  `Length + Girth = length_cm + 2×width_cm + 2×height_cm` **tanpa sortir 3
  sisi** (asumsi lama yang mengurutkan sisi terbesar sbg "Length" ternyata
  salah). Diperbaiki di `nonstandard_fees.py` — merambat otomatis ke semua
  fitur yang bergantung (AHS/Oversize/Unauthorized §6.2, auto-switch §6.5).
- **Tahap 6 (7 Sep 2026) — Refactor modular `rates.py`**: file `rates.py`
  yang tadinya 1 file besar (~2000 baris, promotional + commercial
  digabung) dipecah jadi `rate_common.py` (util & pricing engine bersama),
  `rates_promotional.py`, `rates_commercial.py`, dan `rates.py` jadi façade
  tipis yang dispatch by `rate_type` (lihat §3 & §4.3). Tujuan: **scalable**
  — nambah rate_type baru ke depan cukup 1 file baru + 1 baris registrasi,
  tanpa sentuh kode yang sudah ada/teruji. Tidak ada perubahan behavior/
  angka (diverifikasi hasil sebelum & sesudah refactor identik utk semua
  kombinasi service/direction/rate_type yang dites, termasuk lewat
  `calculator.py` & `app.py`/Streamlit langsung).
- **Konfirmasi & CWT freight (7 Sep 2026)**: user mengonfirmasi 2 hal yang
  sebelumnya jadi open question — (1) 3 negara tanpa mapping demand
  surcharge (Norfolk Island, Syria, Yemen) memang tidak ada service FedEx,
  bukan gap data (§6.1); (2) divisor dimensional weight IPF/IEF **sama**
  dengan IP/IE (5.000, tanpa floor 18kg). Poin (2) diimplementasikan sbg
  fitur baru `nonstandard_fees.compute_freight_chargeable_weight()` +
  wiring di `calculator.py` (§6.6) — CWT sekarang berlaku utk `freight_units`
  juga (langsung maupun hasil auto-switch §6.5), belum di-porting ke
  `index.html` (§11 poin 8).

## 11. Rencana Lanjutan (Roadmap)

1. Samakan cakupan ODA/OPA dua-sisi dari `index.html` ke backend Python
   (`calculator.py`) supaya tidak divergen.
2. Validasi otomatis lokasi Jakarta/Batam & US/Canada declared value untuk
   Special Handling Fees (butuh data tambahan yang belum ada).
3. ~~Konfirmasi ke FedEx CS soal 3 negara yang belum ada di tabel demand
   surcharge (Norfolk Island, Syria, Yemen).~~ **SUDAH DIKONFIRMASI (7 Sep
   2026): memang tidak ada service FedEx ke 3 negara ini** — bukan gap data,
   tidak perlu tindakan lanjutan (lihat §6.1).
4. Pertimbangkan fuzzy-match / normalisasi ejaan kota untuk 70 negara
   berbasis kota, supaya tidak gagal match hanya karena typo kecil.
5. ~~Cek ke FedEx CS apakah IPF/IEF (freight) juga punya aturan dimensional
   weight sendiri (divisor mungkin beda dari 5.000)~~ **SUDAH DIKONFIRMASI
   (7 Sep 2026): divisor SAMA (5.000), sudah diimplementasikan di Python
   (§6.6)** — sisa kerjaan cuma porting ke `index.html` (lihat poin 8).
6. **Porting Rate Type Commercial (§4.3) ke `index.html`** — termasuk zone
   index 20-huruf, tabel rate Exsis, alias & unavailable-countries list.
   Prioritas tergantung apakah `index.html` dipakai aktif untuk quote yang
   butuh rate Commercial (§7 poin 11) — konfirmasi ke user dulu sebelum
   dikerjakan, karena porting `index.html` selalu effort besar (semua data
   ter-embed sbg 1 file JS, termasuk tabel ODA/OPA ~2.2MB yang sudah ada).
7. Konfirmasi ke FedEx CS apakah surcharge lain (ODA/OPA, demand surcharge,
   dll) punya tarif berbeda utk rate sheet Commercial vs promotional (§7
   poin 12) — saat ini diasumsikan sama.
8. **Porting CWT freight (IPF/IEF, §6.6) ke `index.html`** — saat ini cuma
   ada di backend Python, `computeShipmentChargeableWeight()` di JS masih
   IP/IE-only.
