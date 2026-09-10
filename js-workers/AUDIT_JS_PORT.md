# Audit: Port backend/ (Python) -> Cloudflare Workers (JS vanilla)

Keputusan (lihat riwayat percakapan): pindah dari Python ke JS **server-side**
lewat Cloudflare Workers -- BUKAN client-side statis. Alasan: rate card
komersial (UPS A26/B26, FedEx commercial+markup, dst) harus tetap tersembunyi
dari browser; kalau full client-side JS, semua rate & logic otomatis
ke-bundle ke file yg dikirim ke browser dan bisa dibaca siapa saja lewat
"View Source" -- itu risiko bisnis, bukan cuma soal bahasa pemrograman.

## Kenapa Cloudflare Workers
- Free tier 100rb request/hari, tidak minta CC utk sign up (beda dgn add-on
  spt R2 storage yg minta CC) -- **cek lagi saat sign up**, kebijakan platform
  bisa berubah kapan saja, ini bukan jaminan permanen.
- Kalkulator ini murni komputasi (lookup tabel + aritmatika), tidak butuh
  filesystem/database -> cocok dgn model Workers (V8 isolate, tanpa
  Node.js API spt `fs`).
- CPU time 10ms/request di free tier lebih dari cukup utk perhitungan rate
  (lookup dict + beberapa operasi aritmatika, bukan loop berat).

## Constraint teknis sesi audit ini
Sandbox tools TIDAK ada akses jaringan -> tidak bisa `npm install` apapun
(sudah dicoba, 403 dari registry.npmjs.org). Konsekuensi desain:
- Semua kode ditulis **vanilla JS, zero dependency**, ES modules murni.
  Ini justru cocok dgn Workers (tidak perlu build step/bundler utk project
  sesederhana ini -- `wrangler deploy` bisa langsung deploy modul ES).
- Testing dijalankan pakai `node --test` (bawaan Node.js 22, zero install)
  -- BUKAN `vitest` + `@cloudflare/vitest-pool-workers` (tooling resmi utk
  test Workers yg jalan di runtime Workers asli). Node.js != runtime
  Workers persis (V8 isolate Workers tidak expose semua global Node.js),
  tapi karena kode ini vanilla JS tanpa API Node-only (tidak pakai `fs`,
  `path`, dll di source -- cuma testnya yg pakai `node:fs` utk baca
  fixture), risiko perbedaan perilaku kecil. **Tetap perlu di-run ulang via
  `wrangler dev` + idealnya migrasi test ke `vitest-pool-workers` di
  environment yg ada akses npm**, sebelum production.
- `wrangler` sendiri (CLI deploy) TIDAK di-install di sini -- `package.json`
  cuma mencantumkannya sbg `devDependencies` referensi. Jalankan
  `npm install` lalu `npx wrangler dev`/`deploy` di komputer Anda sendiri.

## Risiko teknis #1 yg SUDAH ditangani: pembulatan
Python `round()` = round-half-to-even (banker's rounding) + correctly-rounded
thd representasi desimal sebenarnya. JS `Math.round()` = round-half-up, dan
tidak ada versi built-in utk `ndigits > 0`. Kode Python asli manggil
`round()` polos persis di titik paling sensitif: `base_price`, tiap nilai
`surcharges`, `discount`, `total`, `VAT` (lihat grep di riwayat audit).
Port naif ke `Math.round()` akan KADANG (bukan selalu, makanya berbahaya)
selisih dari golden value yg sudah divalidasi 86 test Python.

**Sudah dibuat & divalidasi**: `src/core/pyround.js` -- di-cross-check
langsung terhadap Python 3 asli (bukan cuma asumsi teori) lewat 4.472 kasus
(tie `.5` eksplisit + nilai IDR realistis dari base_price/pct yg dipakai di
kalkulator ini) -> **0 mismatch**. Lihat `test/pyround.crosscheck.test.js` +
`test/fixtures/pyround_cases.json` (fixture-nya digenerate dari Python asli,
jangan diedit manual -- regenerate ulang kalau perlu nambah kasus).

## Progress sejauh ini
- [x] `src/core/pyround.js` -- port `round()` Python, tervalidasi.
- [x] `src/core/errors.js` -- `RateEngineError`, `UPSRateError`,
      `FedExRateError`, `ValidationError`.
- [x] `src/core/schemas.js` -- `makeRateRequest()`, `cloneRateRequest()`,
      `makeRateResult()` (plain object, bukan class -- lebih gampang
      di-JSON.stringify apa adanya utk response HTTP Workers).
- [ ] **UPS**: `zones.js` (termasuk `effective_country_for_zone()` -- ada
      catatan penting soal China Southern/postal code di komentar Python
      asli, JANGAN dilewat saat port), `rates/publish.js`,
      `rates/commercial.js` (named-group override per negara + A26/B26),
      `calculator.js` (termasuk logic tier eksplisit yg baru saja diaudit --
      B26 tidak lagi default diam-diam, `calculateCommercialTiers()`).
- [ ] **FedEx**: `calculator.js` (dimensional weight, discount_pct,
      **markup_pct baru**, ODA/OPA, dll), `surcharges/nonstandard.js`
      (AHS-Dimension floor 18kg -- lihat AUDIT note yg baru dikoreksi),
      `surcharges/fuel.js`, demand surcharge date-gating (2026-09-21).
- [ ] `pricing/router.js` -- dispatch carrier -> calculator.
- [ ] `comparison/compare.js` + `service_mapping.js` -- termasuk logic
      auto-expand UPS commercial jadi A26+B26 yg baru diaudit.
- [ ] `api/index.js` -- Workers `fetch` handler (routing manual/tanpa
      framework, mapping `RateEngineError`/`ValidationError` -> HTTP 400,
      lainnya -> 500 -- padanan `routes.py`).
- [ ] `wrangler.toml` -- konfigurasi deploy.
- [ ] Port `tests/test_*.py` (86 test) -> `test/*.test.js`, plus
      idealnya cross-validation lebih lanjut spt pyRound (jalankan Python
      & JS side-by-side atas kombinasi carrier/rate_type/negara/berat yg
      sama, bandingkan `base_price`/`total`/`surcharges` -- pendekatan yg
      sama spt `test_full_matrix_sweep.py` tapi lintas-bahasa).

## Urutan lanjutan yg disarankan
1. UPS zones + publish (paling sederhana, tanpa named-group override).
2. UPS commercial (named-group override + A26/B26 tier logic) + calculator.
3. Port `test_ups.py` -> JS, verifikasi golden value sama persis.
4. FedEx calculator + surcharges (lebih kompleks -- banyak modul).
5. Port `test_fedex.py` -> JS.
6. `pricing/router.js` + `comparison/compare.js`.
7. Port `test_comparison.py` -> JS.
8. `api/index.js` (Workers fetch handler) + `wrangler.toml`.
9. Port `test_api.py` -> JS (test HTTP end-to-end, bisa pakai
   `workerd`/`wrangler dev` lokal atau `unstable_dev` API wrangler).
10. Cross-validation akhir: jalankan Python & JS side-by-side atas ribuan
    kombinasi acak (spt full_matrix_sweep), pastikan 100% identik sebelum
    Python di-decommission.

Jangan skip langkah cross-validation di tiap tahap -- ini proyek dgn rate
card bisnis riil, selisih 1 rupiah yg lolos = data quote salah ke customer.
