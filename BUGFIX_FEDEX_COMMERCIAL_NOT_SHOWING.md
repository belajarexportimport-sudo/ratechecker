# Bug: "Rate Commercial FDX (Exsis) belum muncul" — Root Cause & Fix

## Ringkasan
**Bukan bug di calculator/comparison engine** — logic hitungnya sudah benar
dari awal (diverifikasi: Singapore commercial = Rp324.676, cocok 100% dgn
golden value dari audit sebelumnya). Masalahnya ada di **`zones.js`**:
tabel alias nama negara utk Commercial Zone Index (yang sebelumnya sudah
pernah dibangun di versi Python) **tidak ikut ter-port ke JS**.

## Dampak
Tanpa tabel alias ini, kombinasi `['fedex','commercial']` gagal (masuk daftar
`unavailable`, bukan tampil sbg card) untuk hampir semua negara yang sering
dites:
- **United States** — tidak ketemu sama sekali (Zone Index Exsis pakai
  ejaan "U.S.A.", bukan "United States")
- **Philippines** — tidak ketemu (Exsis salah ketik "Phillipines")
- **China** — malah **ambigu** (cocok substring ke 4 negara sekaligus:
  "China (Excluding China South)", "China (South)", "Hong Kong SAR, China",
  "Macau SAR, China")
- **Korea, UK, UAE, Moldova, Tanzania, Ivory Coast, dan ~20 negara lain**
  — pola yang sama

Hanya negara yang ejaannya PERSIS sama antara 2 sumber data (mis. Singapore,
Japan, Germany) yang berhasil — itu sebabnya kelihatannya "kadang muncul
kadang tidak", padahal sebenarnya pola gagalnya konsisten & bisa ditebak.

## Fix yang diterapkan (`src/carriers/fedex/zones.js`)

1. **`COMMERCIAL_ALIASES`** — tabel 30 mapping ejaan (dipulihkan dari audit
   Python sebelumnya) ditambahkan kembali: Philippines→Phillipines, United
   States→U.S.A., Korea→South Korea, UK→United Kingdom (Great Britain), dst.
2. **`COMMERCIAL_UNAVAILABLE_COUNTRIES`** — 8 negara yang memang tidak ada
   rate commercial-nya (Vatican City, San Marino, dll) sekarang balas error
   jelas ("pakai rate_type='publish' saja"), bukan silent fail generik.
3. **China ditangani eksplisit** (bukan lewat fuzzy-match yang ambigu) —
   cek `nameKey === 'china'` dulu, baru pilih label
   `'china (south)'`/`'china (excluding china south)'` berdasarkan kode pos.
4. **Bonus fix (ditemukan saat investigasi, bukan yang dilaporkan)**:
   - Range kode pos Guangdong sebelumnya pakai prefix 2-digit `"51","52","53"`
     (mencakup 510000-539999) — salah, kemasukan 530000-539999 yang BUKAN
     Guangdong. Diganti range persis `510000-529999`.
   - Fallback China untuk rate **publish** sebelumnya mengganti nama negara
     jadi `'fujian'`/`'guangdong'` lalu cari ulang ke Zone Index publish —
     yang tidak punya baris itu sama sekali (Zone Index publish cuma 1 baris
     "China"), jadi SELALU gagal kalau ada kode pos China diisi. Diganti jadi
     langsung override huruf zone ke `'B'`.
   - **"United States" ambigu di rate publish juga** (Zone Index punya 2
     baris: "Rest of Country" & "Western Region") — ditambahkan default alias
     (aman, karena zone huruf keduanya identik: "D").

## Verifikasi
Sweep 17 negara langsung ke `calculator.js`, lalu full end-to-end lewat Hono
app (`app.fetch()`, simulasi HTTP request sungguhan) untuk 6 negara paling
umum (Singapore, US, China, Philippines, Japan, Australia) — **semua
berhasil**, FedEx Publish & Commercial dua-duanya tampil dengan zone &
harga yang benar.

## File yang berubah
`src/carriers/fedex/zones.js` — file lengkap terlampir
(`fedex_zones_FIXED.js`), tinggal timpa file yang sama di project.
