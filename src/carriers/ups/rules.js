export const DIM_DIVISOR = 5000;

export const COSTS_MAY_24_2026 = {
    AHS: 280016,
    LPS: 1058200,
    OMX: 4121800,
    BROKERAGE: 118647
};

// Optional surcharges (UPS Rate & Service Guide Indonesia, efektif 7 Jun
// 2026) -- PORT dari backend/carriers/ups/rules.py OPTIONAL_COSTS. Ini yang
// tadinya TIDAK ADA SAMA SEKALI di calculator.js (audit 12 Sep 2026: banyak
// checkbox di frontend sudah ada, misalnya "Adult Signature Required", tapi
// backend JS-nya belum pernah mengimplementasikan surcharge-nya sama sekali,
// bukan cuma soal wiring).
export const OPTIONAL_COSTS = {
    extended_area_min: 429792,
    extended_area_kg: 8288,
    remote_area_min: 479964,
    remote_area_kg: 9472,
    peb: 190189,
    residential: 58312,       // Saver/Expedited
    residential_wwef: 1879600, // Per AWB (freight)
    adult_signature: 71040,
    delivery_confirm: 37740,
    alternate_broker: 429502,
    duty_tax_forward: 310060,
    ipf: 37000,
    paper_invoice: 370000,
    insurance_free_limit: 1480000,
    insurance_unit_rate: 32710,
    carbon_offset_package: 11690,   // per package (non-freight)
    carbon_offset_pallet: 311980,   // per pallet (UPS Worldwide Express Freight)
};

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

export function validateGeometry(length, width, height) {
    const L = length;
    const W = width;
    const H = height;
    const girth = (2 * W) + (2 * H);
    const length_plus_girth = L + girth;
    return { L, W, H, girth, length_plus_girth };
}
