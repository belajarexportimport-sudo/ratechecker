# Cara Trial — Rate Compare (FedEx × UPS)

## 1. Jalankan backend

```bash
pip install -r requirements.txt   # atau requirements_comparison.txt kalau itu yang lengkap
python run.py
```

Backend jalan di `http://127.0.0.1:8000`. Cek dengan buka
`http://127.0.0.1:8000` di browser → harus muncul
`{"message":"Multi-Carrier Rate Engine is running."}`.

## 2. Buka `index.html`

Double-click `index.html` (atau buka lewat browser). Karena backend sudah
mengizinkan CORS dari semua origin, `index.html` bisa dibuka langsung dari
folder (`file://`) — tidak perlu web server terpisah untuk frontend-nya.

Pastikan kotak "API" di kanan atas menunjuk ke alamat backend yang benar
(default `http://127.0.0.1:8000`). Titik hijau/merah di sebelahnya menandakan
status koneksi ke backend.

## 3. Isi form & bandingkan

- **Arah**: Export / Import.
- **Negara asal / tujuan**: ketik nama negara (ada autocomplete, gabungan
  daftar negara FedEx + UPS).
- **Service acuan**: pilih carrier & service yang jadi acuan (mis. FedEx IP).
  Kalau kamu centang kombinasi carrier lain (mis. UPS), service-nya otomatis
  dipetakan lewat `backend/comparison/service_mapping.py` — TIDAK diasumsikan
  otomatis 1:1, ini tabel eksplisit yang sudah kamu isi sebelumnya.
- **Berat & dimensi**: dimensi opsional, dipakai untuk DIM weight (lebih
  relevan di UPS saat ini).
- **Bandingkan**: centang kombinasi carrier×rate_type yang mau ditampilkan
  berdampingan (default: FedEx Publish, FedEx Commercial, UPS Publish, UPS
  Commercial).

Klik **Bandingkan Rate** → tabel muncul di kanan, kolom termurah ditandai
hijau "Termurah". Baris "Tidak tersedia" (kalau ada) menjelaskan kombinasi
yang gagal dihitung & alasannya (mis. negara tidak ada rate commercial-nya).

## Catatan / hal yang saya temukan saat uji coba

1. **Bug ditemukan**: `compare()` untuk kombinasi FedEx gagal kalau field
   `packages` (multi-package detail) diisi di request — error
   `check_package_surcharge() got an unexpected keyword argument 'qty'`
   di `backend/carriers/fedex/surcharges/nonstandard.py` (atau modul terkait).
   **Frontend ini SENGAJA tidak mengirim `packages`** (hanya `weight_kg` +
   `dimensions_cm` single-box) supaya tidak kena bug ini — jadi trial di sini
   aman, tapi kalau nanti mau presisi CWT multi-package / AHS-LPS-OMX UPS
   lewat form, bug ini perlu diperbaiki dulu.
2. Import langsung `backend.carriers.fedex.zones` sendirian (tanpa lewat
   `backend.carriers.fedex.calculator` dulu) kena circular import error.
   Tidak masalah untuk pemakaian normal (lewat API), tapi kalau ada script
   lain yang import `zones.py` duluan, akan error. Perlu dirapikan urutan
   importnya di `backend/carriers/fedex/rates/__init__.py` /
   `backend/carriers/fedex/zones.py`.
3. Comparison endpoint & schema semuanya sudah sesuai kontrak PRD (
   `RateRequest`/`RateResult`, tanpa Pydantic, sesuai aturan yang sudah
   ditetapkan) — tidak saya ubah.
