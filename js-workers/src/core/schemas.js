/**
 * Port dari backend/core/schemas.py (RateRequest, RateResult dataclasses).
 *
 * Dipakai plain object literal (bukan class) sengaja -- lebih gampang
 * di-clone (structuredClone/spread), di-JSON.stringify apa adanya utk
 * response HTTP, dan cocok dgn gaya "data class" yg dipakai Python asli
 * (field publik semua, tidak ada method/behavior nempel).
 *
 * makeRateRequest(overrides) & makeRateResult(overrides) isi default yg
 * sama persis dgn default field di RateRequest/RateResult Python, supaya
 * caller cuma perlu isi field yg relevan (spt Python dataclass).
 */

/**
 * @param {object} fields
 * @param {string} fields.carrier
 * @param {string} fields.rate_type
 * @param {string} fields.service
 * @param {string} fields.direction
 * @param {string} fields.origin_country
 * @param {string} fields.destination_country
 * @param {number} fields.weight_kg
 * @param {[number,number,number]|null} [fields.dimensions_cm]
 * @param {number} [fields.packages=1]
 * @param {string|null} [fields.postal_code_origin]
 * @param {string|null} [fields.postal_code_destination]
 * @param {number|null} [fields.discount_pct]
 * @param {object} [fields.extra={}]
 */
export function makeRateRequest(fields) {
  return {
    carrier: fields.carrier,
    rate_type: fields.rate_type,
    service: fields.service,
    direction: fields.direction,
    origin_country: fields.origin_country,
    destination_country: fields.destination_country,
    weight_kg: fields.weight_kg,
    dimensions_cm: fields.dimensions_cm ?? null,
    packages: fields.packages ?? 1,
    postal_code_origin: fields.postal_code_origin ?? null,
    postal_code_destination: fields.postal_code_destination ?? null,
    discount_pct: fields.discount_pct ?? null,
    extra: fields.extra ? { ...fields.extra } : {},
  };
}

/**
 * Shallow copy RateRequest -- padanan `copy.copy(request)` di Python yg
 * dipakai compare.py & calculate_commercial_tiers(). `extra` SENGAJA
 * di-copy dangkal (bukan deep clone) supaya perilakunya identik dgn
 * Python copy.copy() thd dataclass (field dict di dalamnya tetap
 * reference yg sama kecuali di-assign ulang eksplisit oleh caller,
 * spt yg dilakukan calculate_commercial_tiers()).
 */
export function cloneRateRequest(request) {
  return { ...request, extra: { ...request.extra } };
}

/**
 * @param {object} fields
 */
export function makeRateResult(fields) {
  return {
    carrier: fields.carrier,
    rate_type: fields.rate_type,
    service: fields.service,
    zone: fields.zone,
    base_price: fields.base_price,
    surcharges: fields.surcharges ?? {},
    discount: fields.discount ?? 0,
    total: fields.total ?? 0,
    currency: fields.currency ?? "IDR",
    notes: fields.notes ?? [],
    extra: fields.extra ?? {},
  };
}
