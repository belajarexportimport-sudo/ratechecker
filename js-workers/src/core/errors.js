/**
 * Port dari backend/core/errors.py.
 * Dipakai router HTTP (src/index.js) utk mapping ke status code:
 *   RateEngineError (& turunannya)  -> 400
 *   ValueError-equivalent           -> 400 (lihat ValidationError di bawah)
 *   lainnya                         -> 500
 */
export class RateEngineError extends Error {
  constructor(message) {
    super(message);
    this.name = "RateEngineError";
  }
}

export class UPSRateError extends RateEngineError {
  constructor(message) {
    super(message);
    this.name = "UPSRateError";
  }
}

export class FedExRateError extends RateEngineError {
  constructor(message) {
    super(message);
    this.name = "FedExRateError";
  }
}

/**
 * Padanan `raise ValueError(...)` di Python (dipakai mis. validasi
 * markup_pct/discount_pct) -- di Python ValueError BUKAN turunan
 * RateEngineError, tapi tetap ditangkap & di-map ke HTTP 400 di routes.py.
 * Di sini kita buat class terpisah senada, supaya pemanggil bisa
 * membedakan "error validasi input" vs "error logic rate engine" kalau
 * suatu saat perlu, tapi keduanya di-map ke 400 yg sama di index.js.
 */
export class ValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "ValidationError";
  }
}
