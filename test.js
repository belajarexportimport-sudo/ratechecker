
import pricingRouter from './src/pricing/router.js'
import compareRouter from './src/comparison/compare.js'

const req = {
    carrier: 'fedex',
    rate_type: 'publish',
    service: 'IP',
    direction: 'export',
    origin_country: 'Indonesia',
    destination_country: 'Singapore',
    weight_kg: 10,
    extra: { fsi_pct: 14.5 }
}

const resFedEx = pricingRouter.calculate(req)
console.log('FedEx:', resFedEx.total)

req.carrier = 'ups'
req.rate_type = 'b26'
req.service = 'saver'
const resUPS = pricingRouter.calculate(req)
console.log('UPS:', resUPS.total)

const comp = compareRouter.compareRates({
    carrier: 'fedex',
    rate_type: 'publish',
    service: 'IP',
    direction: 'export',
    origin_country: 'Indonesia',
    destination_country: 'Singapore',
    weight_kg: 10,
    extra: { fsi_pct: 14.5 }
}, [
    ['fedex', 'publish'],
    ['fedex', 'commercial'],
    ['ups', 'a26'],
    ['ups', 'b26']
])

console.log('Compare Best:', comp.cheapest.carrier, comp.cheapest.total)
