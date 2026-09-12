import { Hono } from 'hono'
import { cors } from 'hono/cors'
import pricingRouter from './pricing/router.js'
import compareRouter from './comparison/compare.js'
import { getCountryList } from './core/countries.js'

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

export default app
