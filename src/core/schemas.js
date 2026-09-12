/**
 * @typedef {Object} PackageItem
 * @property {number} [qty=1]
 * @property {number} weight_kg
 * @property {number} [length_cm=0]
 * @property {number} [width_cm=0]
 * @property {number} [height_cm=0]
 * @property {string} [packing_type="box"]
 * @property {string} [label=""]
 */

/**
 * @typedef {Object} RateRequest
 * @property {string} carrier - "fedex" | "ups"
 * @property {string} rate_type - "publish" | "commercial" | "a26" | "b26"
 * @property {string} service - e.g., "IP", "IE", "saver"
 * @property {string} direction - "export" | "import"
 * @property {string} origin_country
 * @property {string} destination_country
 * @property {number} weight_kg
 * @property {number[]} [dimensions_cm] - [L, W, H]
 * @property {string} [postal_code_origin]
 * @property {string} [postal_code_destination]
 * @property {number} [discount_pct=0]
 * @property {Object} extra - Extra parameters (fsi_pct, optional surcharges, packages array, etc.)
 */

/**
 * @typedef {Object} RateResult
 * @property {string} carrier
 * @property {string} rate_type
 * @property {string} service
 * @property {string} zone
 * @property {number} base_price
 * @property {Object.<string, number>} surcharges
 * @property {number} discount
 * @property {number} total
 * @property {string} currency
 * @property {string[]} notes
 * @property {Object} extra
 */

export {};
