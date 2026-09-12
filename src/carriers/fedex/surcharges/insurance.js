/**
 * FedEx Insurance / Declared Value Surcharge
 * ============================================
 * Ported dari "Calculate insurance UPS & FedEx.xlsx" (sheet "insurance"),
 * formula Excel:
 *   =IF(B2 <= MAX(B4, (B3*2.20462)*B5), 0,
 *       CEILING((B2 - MAX(B4, (B3*2.20462)*B5)) / B4, 1) * B6)
 *   B2 = Nilai Barang (IDR)
 *   B3 = Berat Barang (kg)
 *   B4 = Batas Minimum (IDR)        -- juga dipakai sebagai step CEILING
 *   B5 = Rate Berat per Lbs (IDR)
 *   B6 = Biaya Premi per Kelipatan (IDR)
 *   FreeCoverage = MAX(B4, berat_lbs x B5)
 *
 * Belum ada modul insurance FedEx sebelumnya sama sekali -- modul ini baru.
 */

const KG_TO_LBS = 2.20462

export const INSURANCE_MIN_LIMIT_IDR = 1_375_000
export const INSURANCE_RATE_PER_LBS_IDR = 125_000
export const INSURANCE_UNIT_RATE_IDR = 34_000

export function computeInsuranceSurcharge(declaredValueIdr, weightKg,
    minLimit = INSURANCE_MIN_LIMIT_IDR,
    ratePerLbs = INSURANCE_RATE_PER_LBS_IDR,
    unitRate = INSURANCE_UNIT_RATE_IDR) {

    const kg = weightKg && weightKg > 0 ? weightKg : 0
    const weightCoverage = kg * KG_TO_LBS * ratePerLbs
    const freeCoverage = Math.max(minLimit, weightCoverage)

    if (declaredValueIdr <= freeCoverage) {
        return {
            fee: 0,
            freeCoverage,
            note: `Nilai barang IDR ${declaredValueIdr.toLocaleString('id-ID')} <= MAX(batas minimum ` +
                  `IDR ${minLimit.toLocaleString('id-ID')}, ${kg}kg x ${KG_TO_LBS} x IDR ` +
                  `${ratePerLbs.toLocaleString('id-ID')}) = IDR ${Math.round(freeCoverage).toLocaleString('id-ID')} -> Insurance gratis.`,
        }
    }
    const units = Math.ceil((declaredValueIdr - freeCoverage) / minLimit)
    const fee = units * unitRate
    return {
        fee,
        freeCoverage,
        note: `Insurance: ceil((IDR ${declaredValueIdr.toLocaleString('id-ID')} - IDR ` +
              `${Math.round(freeCoverage).toLocaleString('id-ID')}) / IDR ${minLimit.toLocaleString('id-ID')}) = ` +
              `${units} unit x IDR ${unitRate.toLocaleString('id-ID')} = IDR ${fee.toLocaleString('id-ID')}.`,
    }
}
