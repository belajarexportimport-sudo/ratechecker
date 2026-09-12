import { Hono } from 'hono'
import { cors } from 'hono/cors'
import pricingRouter from './pricing/router.js'
import compareRouter from './comparison/compare.js'
import { getCountryList } from './core/countries.js'
import { computeDutyTax } from './duty_tax/calculator.js'

const app = new Hono()

// Gunakan CORS agar bisa diakses dari index.html di GitHub Pages
app.use('/*', cors())

app.get('/', (c) => {
  return c.json({ 
    message: 'Multi-Carrier Rate Engine API is running on Cloudflare Workers',
    status: 'OK'
  })
})

// Daftar negara gabungan (FedEx + UPS) utk autocomplete di frontend --
// lihat src/core/countries.js utk latar belakang.
app.get('/api/countries', (c) => {
  return c.json({ countries: getCountryList() })
})

// Route kalkulasi rate
app.post('/api/rates/calculate', async (c) => {
  try {
    const reqBody = await c.req.json()
    const result = pricingRouter.calculate(reqBody)
    return c.json(result)
  } catch (err) {
    return c.json({ detail: err.message }, 400)
  }
})

// Route perbandingan antar carrier
app.post('/api/rates/compare', async (c) => {
  try {
    const reqBody = await c.req.json()
    const result = compareRouter.compareRates(reqBody.base_request, reqBody.combinations, reqBody.discounts)
    return c.json(result)
  } catch (err) {
    return c.json({ detail: err.message }, 400)
  }
})

// Route Bea Masuk & Pajak Impor (Duty & Tax) -- khusus IMPOR. Terpisah
// dari /api/rates/compare krn "freight_idr" yg dipakai utk hitung CIF
// idealnya adalah TOTAL akhir salah satu kartu hasil (base+surcharge+
// FSI+VAT), jadi frontend manggil route ini SETELAH dapat hasil compare,
// sekali per kartu yang mau ditampilkan estimasi duty/tax-nya.
app.post('/api/duty-tax/calculate', async (c) => {
  try {
    const reqBody = await c.req.json()
    const result = computeDutyTax(reqBody.items, reqBody.opts || {})
    if (result.error) return c.json(result, 400)
    return c.json(result)
  } catch (err) {
    return c.json({ detail: err.message }, 400)
  }
})

export default app
