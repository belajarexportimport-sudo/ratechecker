import pricingRouter from '../pricing/router.js'
import { mapService } from './service_mapping.js'

function compareRates(baseRequest, combinations, discounts = {}) {
    const results = []
    const unavailable = []

    const baseCarrier = baseRequest.carrier.toLowerCase()
    const baseService = baseRequest.service

    for (const combo of combinations) {
        if (!Array.isArray(combo) || combo.length !== 2) continue
        const carrier = combo[0]
        const rateType = combo[1]

        // Deep copy JSON request
        const req = JSON.parse(JSON.stringify(baseRequest))
        req.carrier = carrier
        req.rate_type = rateType

        // Diskon per-jenis-rate (mis. {"fedex:commercial": 10, "ups:a26": 8}).
        // Kalau ada override utk kombinasi carrier:rate_type ini, pakai itu;
        // kalau tidak, fallback ke discount_pct global di baseRequest (kalau
        // ada) supaya request lama yang cuma kirim discount_pct tetap jalan.
        const discountKey = `${carrier}:${rateType}`.toLowerCase()
        if (discounts && Object.prototype.hasOwnProperty.call(discounts, discountKey)) {
            req.discount_pct = discounts[discountKey]
        }

        if (carrier.toLowerCase() !== baseCarrier) {
            const mapped = mapService(baseCarrier, carrier, baseService)
            if (!mapped) {
                unavailable.push({
                    carrier: carrier,
                    rate_type: rateType,
                    reason: `Tidak ada service mapping dari ${baseCarrier.toUpperCase()} '${baseService}' ke ${carrier.toUpperCase()}`
                })
                continue
            }
            req.service = mapped
        }

        try {
            const result = pricingRouter.calculate(req)
            results.push(result)
        } catch (e) {
            unavailable.push({
                carrier: carrier,
                rate_type: rateType,
                reason: e.message || String(e)
            })
        }
    }

    let cheapest = null
    if (results.length > 0) {
        // Find min total
        cheapest = results.reduce((min, curr) => curr.total < min.total ? curr : min, results[0])
    }

    return {
        results,
        unavailable,
        cheapest
    }
}

export default { compareRates }
