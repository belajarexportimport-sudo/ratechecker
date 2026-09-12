import fedexCalculator from '../carriers/fedex/calculator.js'
import upsCalculator from '../carriers/ups/calculator.js'

const CARRIER_REGISTRY = {
    "fedex": fedexCalculator,
    "ups": upsCalculator
}

/**
 * @param {import('../core/schemas.js').RateRequest} request
 * @returns {import('../core/schemas.js').RateResult}
 */
function calculate(request) {
    if (!request.carrier) {
        throw new Error("Field 'carrier' wajib diisi.")
    }
    
    const carrierKey = request.carrier.toLowerCase()
    const calculator = CARRIER_REGISTRY[carrierKey]
    
    if (!calculator) {
        throw new Error(`Carrier '${request.carrier}' tidak didukung atau belum diimplementasikan di Cloudflare Worker.`)
    }
    
    return calculator.calculate(request)
}

export default {
    calculate,
    CARRIER_REGISTRY
}
