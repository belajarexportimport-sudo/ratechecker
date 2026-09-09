# Audit: `backend/carriers/fedex/surcharges/oda_opa.py` + `oda_opa_tiers.csv`

**Item terakhir yang belum diaudit** menurut `AUDIT_FEDEX_SURCHARGES.md` bagian
4 — beda jenis validasi dari audit sebelumnya (nominal/kriteria kecil): ini
validasi **DATA MASIF** (67.608 baris, 112 kode negara), jadi dilakukan lewat
sampling terprogram (Python) terhadap `oda_opa_tiers.csv` itu sendiri, BUKAN
cross-check ke `ODA_OPA_tiers_codes.xlsx` asli (file itu tidak ada di upload
ini — hanya hasil ekstraksinya). Artinya audit ini membuktikan **konsistensi
internal & logika lookup**, bukan "apakah CSV cocok dengan XLSX sumber".
Kalau butuh kepastian penuh soal akurasi ekstraksi CSV vs XLSX, itu tetap
perlu file XLSX aslinya.

**Catatan penting:** file ini sebelumnya SUDAH dirujuk di docstring
`oda_opa.py` (`_merge_tiers()`) sebagai sumber detail temuan, tapi filenya
sendiri ternyata tidak pernah benar-benar dibuat/di-commit — jadi referensi
itu dangling. File ini mengisi gap tersebut sekaligus menambah temuan baru.

---

## 1. Validitas nilai & format — bersih

Dicek terhadap seluruh 67.608 baris:

| Cek | Hasil |
|---|---|
| Nilai tier di luar {No, A, B, C, kosong} | **0 ditemukan** |
| Range numerik dengan begin > end | **0 ditemukan** |
| Range non-numerik (huruf) dengan begin > end | **0 ditemukan** |
| Baris tanpa postal range DAN tanpa city (orphan) | **0 ditemukan** |
| Range dengan begin/end campur numerik+huruf dalam 1 baris | **0 ditemukan** |
| Baris cuma salah satu dari begin/end terisi | **0 ditemukan** |

## 2. Overlap range numerik — diverifikasi ULANG secara independen

Klaim di docstring kode (*"7131 pasang range tumpang-tindih (7066 US, 58 CN,
7 PH), semuanya saling melengkapi"*) **tidak langsung dipercaya** — dijalankan
ulang pakai algoritma sweep-line independen (bukan baca kode yang sama):

- **Total pasangan overlap: 7131** (US 7066, CN 58, PH 7) — **persis cocok**
  dengan klaim di kode. ✅
- **Konflik nilai nyata** (2 range overlap, kolom tier yang sama, dua-duanya
  bukan "No", tapi beda nilai) — **0 ditemukan**. Artinya semua overlap memang
  aman digabung (`_merge_tiers`) seperti yang diklaim. ✅

## 3. Overlap range non-numerik (CA, GB) — belum pernah dicek sebelumnya, temuan baru

Docstring kode cuma membahas overlap range numerik. Overlap range alfabet
(Canada 356 baris, UK 168 baris) **belum pernah diverifikasi** — dicek
sekarang pakai perbandingan pairwise per negara:

- **Total overlap: 0** (baik CA maupun GB). ✅ Tidak ada risiko under-charge
  dari sisi ini.
- Semua baris CA panjang string begin/end konsisten 6 karakter (aman untuk
  perbandingan leksikografis). Baris GB ada campuran panjang 3 & 4 karakter,
  tapi **semua row GB adalah titik tunggal** (`begin == end`, mis. `GY1`-`GY1`,
  `HS1X`-`HS1X`) — bukan rentang yang membentang lintas-panjang, jadi
  perbandingan string tidak salah pasang. Tidak ada perubahan diperlukan.

## 4. Baris duplikat & anomali SX — cocok dengan yang sudah didisclose

- **6 baris duplikat exact** ditemukan — semuanya kota SX (Saint
  Martin/Sint Maarten): Banda Aboa, Bandaabow, Grand Case, La Habitacion,
  Mijnmaatshappij, Orient Bay. **Persis** sesuai catatan di docstring
  (*"6 entri kota duplikat (SX)"*) — tidak ada duplikat baru di luar itu. ✅
- **Country code `SX` dipakai untuk 2 nama berbeda** (Saint Martin & Sint
  Marteen) — dikonfirmasi ulang: total 12 baris SX, dan **semuanya** punya
  tier identik (B/B/B/B) — jadi hasil hitung surcharge tidak terpengaruh,
  cuma nama negara yang ditampilkan ke user bisa salah (tergantung baris
  mana yang ke-load duluan untuk `country_names[cc]`). Status: **known
  limitation, tidak berubah** — tetap butuh XLSX asli untuk pisahkan MF vs
  SX dengan benar.

## 5. Temuan baru — kolom `city` "bocor" pada baris Israel

**311 baris** (semuanya negara Israel) punya **postal range TERISI** *dan*
kolom `city` terisi dengan nilai `"Israel"` (bukan nama kota asli). Karena
`_load()` mengecek `if begin or end: ... elif city: ...` (postal range
prioritas), kolom city ini **diam-diam diabaikan sepenuhnya** — tidak masuk
`city_index` sama sekali.

- **Dampak saat ini: tidak ada.** Lookup untuk Israel tetap benar lewat
  `postal_code`, dan tidak ada satupun baris Israel lain yang murni
  city-only (jadi tidak ada kasus "harusnya bisa dicari by city tapi
  hilang").
- **Bukan bug**, tapi didokumentasikan karena polanya sama seperti bug
  `packages`/`freight_units` yang sudah 2x terjadi di modul FedEx lain
  (data double-purpose yang sebagian silently dibuang oleh cabang if/elif).
  Kalau data ODA/OPA di-update dan versi baru punya negara lain dengan pola
  serupa (postal range + city yang BEDA/bermakna di baris yang sama), ini
  perlu direvisit.

## 6. Ketidaksesuaian jumlah negara — 112 vs 114 di docstring

Docstring `oda_opa.py` menyebut *"114 negara"*. Dihitung ulang dari CSV:
**hanya 112 kode negara unik**. Kemungkinan penyebab: 2 "negara" versi XLSX
sumber (mis. Saint Martin & Sint Maarten) berbagi 1 kode (`SX`) sehingga
turun jadi 1 saat dihitung per `country_code` — tapi ini cuma dugaan, **butuh
XLSX asli untuk dipastikan** (di luar jangkauan audit berbasis CSV ini).
Tidak mempengaruhi hasil hitung (bukan bug logika), tapi angka "114" di
komentar sebaiknya dikoreksi jadi "112 kode negara (114 di sumber XLSX,
lihat catatan SX)" supaya tidak menyesatkan pembaca kode berikutnya.

---

## Ringkasan

| Cek | Hasil |
|---|---|
| Validitas nilai tier & format range | ✅ 0 masalah |
| Overlap numerik (re-verifikasi independen) | ✅ cocok persis klaim lama, 0 konflik nilai |
| Overlap alfabet (CA/GB) — belum pernah dicek | ✅ 0 overlap (temuan baru, bersih) |
| Duplikat baris & anomali SX | ✅ cocok dengan yang sudah didisclose, tidak ada yang baru |
| Kolom `city` "Israel" yang terbuang | ℹ️ tidak berdampak, didokumentasikan (temuan baru) |
| Jumlah negara 112 vs "114" di komentar | ℹ️ ketidaksesuaian dokumentasi, bukan bug (temuan baru) |

**Total: 0 bug fungsional ditemukan.** Dua catatan informasional baru (poin 5
dan 6) didokumentasikan untuk sesi berikutnya. Audit ini **tidak** memvalidasi
akurasi ekstraksi CSV terhadap XLSX asli — itu tetap item terbuka kalau
dibutuhkan kepastian 100% terhadap sumber resmi FedEx.

## Cara verifikasi ulang
Script audit dijalankan langsung terhadap
`backend/carriers/fedex/surcharges/oda_opa_tiers.csv` (bukan disimpan sebagai
file terpisah di repo ini — cukup pendek untuk dijalankan ad-hoc):
- Cek validitas nilai tier & range: iterasi semua baris, cek keanggotaan set
  `{No,A,B,C,""}` dan `begin<=end`.
- Cek overlap numerik: sweep-line per `country_code`, bandingkan pasangan
  yang overlap pada kolom tier yang sama.
- Cek overlap alfabet: pairwise per `country_code` untuk CA & GB (jumlah baris
  kecil, aman O(n²)).
