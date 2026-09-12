export const DIM_DIVISOR = 5000;

export const COSTS_MAY_24_2026 = {
    AHS: 280016,
    LPS: 1058200,
    OMX: 4121800,
    BROKERAGE: 118647
};

// Additional Insurance -- UPS Rate & Service Guide Indonesia (eff. 7 Jun 2026,
// hal. 5): "For each shipment over IDR1,480,000, you may purchase additional
// coverage against loss or damage at IDR32,710 for each additional
// IDR1,480,000 or fraction thereof." TIDAK ada komponen berat -- murni
// berbasis nilai barang (declared value).
export const INSURANCE_FREE_LIMIT = 1480000;
export const INSURANCE_INCREMENT = 1480000;
export const INSURANCE_RATE_PER_INCREMENT = 32710;

// declaredValueIdr: nilai barang yang didaftarkan (IDR). Return 0 kalau <=
// batas gratis (INSURANCE_FREE_LIMIT).
export function computeAdditionalInsurance(declaredValueIdr) {
    if (!declaredValueIdr || declaredValueIdr <= INSURANCE_FREE_LIMIT) return 0;
    const excess = declaredValueIdr - INSURANCE_FREE_LIMIT;
    const units = Math.ceil(excess / INSURANCE_INCREMENT);
    return units * INSURANCE_RATE_PER_INCREMENT;
}

// International Processing Fee (IPF) -- UPS: dikenakan flat per shipment
// utk EKSPOR ke US saja (WW Express/Express Plus/Express Saver/Expedited).
// Tidak berlaku utk Envelope maupun WWEF, dan tidak berlaku utk import.
export const IPF_FEE = 37000;
export const IPF_ELIGIBLE_SERVICES = ["saver", "expedited"];

// Nama negara (sudah lowercase) yang dianggap "United States" di data zone
// UPS (lihat zones_data.js: key "united states" & alias "usa").
const US_COUNTRY_NAMES = new Set(["united states", "usa", "united states of america", "amerika serikat"]);

export function isUnitedStates(countryName) {
    return US_COUNTRY_NAMES.has(countryName.trim().toLowerCase());
}

export const SURGE_V3 = {
    export: {
        "uae": 48840,
        "israel": 48840,
        "middle east": 43660,
        "new zealand": 1480,
        "australia": 1480,
        "asia pacific": 1480,
        "europe": 7400,
        "americas": 7400,
        "rest of world": 7400
    },
    import: {
        "asia pacific": 1480,
        "middle east": 43660,
        "europe": 0,
        "americas": 0,
        "rest of world": 0
    }
};

export const REGIONS = {
    uae: ["united arab emirates"],
    israel: ["israel"],
    middle_east: [
        "bahrain", "egypt", "kuwait", "lebanon", "oman", "qatar", "saudi arabia", "turkey", "yemen", "jordan"
    ],
    anz: ["australia", "new zealand"],
    asia_pacific: [
        "bangladesh", "bhutan", "cambodia", "china", "cn southern", "hong kong", "india", "indonesia", "japan",
        "laos", "macau", "malaysia", "maldives", "mongolia", "myanmar", "nepal", "pakistan",
        "philippines", "singapore", "south korea", "sri lanka", "taiwan", "thailand", "vietnam"
    ],
    americas: ["united states", "canada", "mexico", "brazil", "argentina", "chile", "colombia", "peru"],
    europe: ["united kingdom", "germany", "france", "italy", "spain", "netherlands", "belgium", "switzerland", "sweden", "norway"]
};

export function determineSurgeRegion(countryName) {
    const c = countryName.toLowerCase();
    for (const [r, list] of Object.entries(REGIONS)) {
        if (list.includes(c)) {
            if (r === "uae") return "uae";
            if (r === "israel") return "israel";
            if (r === "middle_east") return "middle east";
            if (r === "anz") return c; // australia or new zealand
            if (r === "asia_pacific") return "asia pacific";
            if (r === "americas") return "americas";
            if (r === "europe") return "europe";
        }
    }
    return "rest of world";
}

// Jenis kemasan yang otomatis memicu Additional Handling (AHS) di UPS,
// TERLEPAS dari berat/dimensi (mis. kemasan kertas kado, poly bag tanpa
// kemasan luar kaku, bentuk bulat/silinder, ada tali/roda/pegangan yang
// menonjol, atau berpotensi tersangkut/merusak paket lain di dalam
// kendaraan/pesawat). Nama flag disamakan dgn punya FedEx
// (nonstandard.js) supaya UI cukup 1 set checkbox utk kedua carrier.
export function packagingTriggersAHS(opts = {}) {
    const {
        non_cardboard_packaging = false,
        round_or_cylindrical = false,
        banded_or_has_wheels_handles_straps = false,
        could_entangle_or_damage = false
    } = opts;
    return Boolean(
        non_cardboard_packaging ||
        round_or_cylindrical ||
        banded_or_has_wheels_handles_straps ||
        could_entangle_or_damage
    );
}

// Extended Area & Remote Area Surcharge -- UPS Rate & Service Guide Indonesia
// (eff. 7 Jun 2026, hal. 6). TIDAK OTOMATIS: UPS tidak menerbitkan daftar
// kode pos/titik Extended/Remote Area dalam format yang bisa dibaca mesin di
// rate guide ini -- PDF-nya sendiri bilang "For a copy of the Extended/Remote
// Area Surcharge points, please download from ups.com/id" (perlu file
// terpisah dari UPS). Karena itu ini WAJIB dicentang manual oleh user,
// persis seperti backend/carriers/ups/calculator.py (extra.optional.
// extended_area / remote_area) -- bukan auto-detect dari kode pos, beda dgn
// ODA/OPA FedEx yang datanya sudah ada (oda_opa_data.json).
export const OPTIONAL_COSTS = {
    extended_area_min: 429792,
    extended_area_kg: 8288,
    remote_area_min: 479964,
    remote_area_kg: 9472,
};

export function computeExtendedAreaCharge(chargeableWeightKg, multiplier = 1) {
    return Math.max(OPTIONAL_COSTS.extended_area_min, OPTIONAL_COSTS.extended_area_kg * chargeableWeightKg) * multiplier;
}

export function computeRemoteAreaCharge(chargeableWeightKg, multiplier = 1) {
    return Math.max(OPTIONAL_COSTS.remote_area_min, OPTIONAL_COSTS.remote_area_kg * chargeableWeightKg) * multiplier;
}

export function validateGeometry(length, width, height) {
    const L = length;
    const W = width;
    const H = height;
    const girth = (2 * W) + (2 * H);
    const length_plus_girth = L + girth;
    return { L, W, H, girth, length_plus_girth };
}
