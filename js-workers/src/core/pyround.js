/**
 * pyRound(value, ndigits = 0)
 *
 * Port dari Python 3 round() -- BUKAN Math.round() JS.
 *
 * KENAPA INI PENTING (baca sebelum menghapus/menyederhanakan fungsi ini):
 * Python round() pakai "round half to even" (banker's rounding) DAN
 * membulatkan berdasarkan representasi desimal yang paling dekat dengan
 * nilai float sebenarnya (bukan representasi biner mentahnya) -- lihat
 * https://docs.python.org/3/library/functions.html#round dan PEP mengenai
 * implementasi round() yang "correctly rounded".
 *
 * JS Math.round() SELALU round half UP (0.5 -> 1, 2.5 -> 3, dst), dan tidak
 * ada round() bawaan buat ndigits > 0. Kalau kode Python asli (lihat
 * backend/carriers/.../calculator.py) manggil round(x) atau round(x, 1) di
 * base_price/surcharges/discount/total/VAT, port naif ke Math.round() akan
 * KADANG (bukan selalu -- makanya berbahaya, lolos dari testing sekilas)
 * menghasilkan selisih 1 rupiah/1 unit dari golden value yang sudah
 * divalidasi di 86 test Python.
 *
 * Implementasi ini pakai pendekatan "format ke string desimal dgn presisi
 * tinggi, baca digit penentu, terapkan half-to-even" -- supaya PERSIS sama
 * dgn CPython utk kasus uang/IDR yang relevan di kalkulator ini. Sudah
 * di-cross-validate langsung terhadap Python 3 asli lewat
 * test/pyround.crosscheck.test.js (lihat file itu utk cara re-run
 * validasinya kalau Anda ubah fungsi ini).
 *
 * @param {number} value
 * @param {number} [ndigits=0]
 * @returns {number}
 */
export function pyRound(value, ndigits = 0) {
  if (!Number.isFinite(value)) return value;
  if (value === 0) return 0; // hindari "-0"

  const neg = value < 0;
  const abs = Math.abs(value);

  // toPrecision(17) -> representasi desimal yang cukup presisi utk
  // membedakan nilai float yg sebenarnya (double punya ~15-17 digit
  // signifikan desimal), lalu kita re-parse sbg desimal string supaya bisa
  // menentukan digit "penentu" pembulatan secara eksak (bukan biner).
  const precise = abs.toPrecision(17);

  // Pecah jadi bagian integer & desimal dari representasi presisi-tinggi.
  let [intPart, fracPart = ""] = precise.split(".");

  // Handle notasi eksponensial (utk angka sangat kecil/besar) -- di
  // kalkulator ini nilainya selalu IDR skala wajar (puluhan ribu - jutaan),
  // jadi ini jalur pengaman, bukan jalur utama.
  if (precise.includes("e") || precise.includes("E")) {
    // Fallback aman: pembulatan biasa (kasus ini tidak relevan utk data
    // rate/IDR di kalkulator, tapi tetap jangan biarkan NaN/undefined lolos).
    const factor = Math.pow(10, ndigits);
    const r = Math.round(abs * factor) / factor;
    return neg ? -r : r;
  }

  const shift = ndigits; // posisi digit yg mau dipertahankan setelah titik desimal
  const allDigits = intPart + fracPart;
  const intLen = intPart.length;
  // Index digit terakhir yg dipertahankan (dlm allDigits), relatif thd titik desimal asli.
  const keepUpto = intLen + shift; // jumlah digit yg dipertahankan dari kiri

  if (keepUpto >= allDigits.length) {
    // Tidak ada pembulatan yg perlu dilakukan (presisi diminta >= presisi tersedia)
    return neg ? -abs : abs;
  }
  if (keepUpto < 0) {
    return neg ? -0 : 0;
  }

  const keptDigits = allDigits.slice(0, keepUpto) || "0";
  const roundDigit = allDigits[keepUpto];
  const restDigits = allDigits.slice(keepUpto + 1);
  const restNonZero = /[1-9]/.test(restDigits);

  let keptNum = BigInt(keptDigits || "0");

  if (
    roundDigit > "5" ||
    (roundDigit === "5" && restNonZero) ||
    (roundDigit === "5" && !restNonZero && keptNum % 2n === 1n) // half-to-even
  ) {
    keptNum += 1n;
  }

  const keptStr = keptNum.toString().padStart(Math.max(keepUpto, 1), "0");
  const newIntLen = keptStr.length - shift;
  let resultStr;
  if (shift <= 0) {
    resultStr = keptStr + "0".repeat(-shift);
  } else {
    const ip = keptStr.slice(0, Math.max(newIntLen, 0)) || "0";
    const fp = keptStr.slice(Math.max(newIntLen, 0)).padStart(shift, "0");
    resultStr = `${ip}.${fp}`;
  }

  const result = Number(resultStr);
  return neg ? -result : result;
}
