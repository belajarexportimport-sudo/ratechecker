/**
 * UPS Insurance / Declared Value Surcharge
 * =========================================
 * Ported dari "Calculate insurance UPS & FedEx.xlsx" (sheet "insurance"),
 * formula Excel:
 *   =IF(E2 <= E4, 0, CEILING((E2 - E4) / E4, 1) * E5)
 *   E2 = Nilai Barang (IDR)
 *   E4 = Batas Gratis UPS (IDR)  -- juga dipakai sebagai step CEILING
 *   E5 = Biaya Premi per Kelipatan (IDR)
 *
 * Sebelumnya modul ini SENGAJA belum dibuat (lihat komentar lama di
 * optional.js: "BELUM dimasukkan ... Additional Insurance (butuh input
 * nilai barang/declared value)"). Sekarang sudah ada.
 */

export const INSURANCE_FREE_LIMIT_IDR = 1_480_000
export const INSURANCE_UNIT_RATE_IDR = 32_710

export function computeInsuranceSurcharge(declaredValueIdr, freeLimit = INSURANCE_FREE_LIMIT_IDR, unitRate = INSURANCE_UNIT_RATE_IDR) {
    if (declaredValueIdr <= freeLimit) {
        return {
            fee: 0,
            freeLimit,
            note: `Nilai barang IDR ${declaredValueIdr.toLocaleString('id-ID')} <= batas gratis ` +
                  `IDR ${freeLimit.toLocaleString('id-ID')} -> Insurance gratis.`,
        }
    }
    const units = Math.ceil((declaredValueIdr - freeLimit) / freeLimit)
    const fee = units * unitRate
    return {
        fee,
        freeLimit,
        note: `Insurance: ceil((IDR ${declaredValueIdr.toLocaleString('id-ID')} - IDR ` +
              `${freeLimit.toLocaleString('id-ID')}) / IDR ${freeLimit.toLocaleString('id-ID')}) = ` +
              `${units} unit x IDR ${unitRate.toLocaleString('id-ID')} = IDR ${fee.toLocaleString('id-ID')}.`,
    }
}
