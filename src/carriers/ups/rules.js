export const DIM_DIVISOR = 5000;

export const COSTS_MAY_24_2026 = {
    AHS: 280016,
    LPS: 1058200,
    OMX: 4121800,
    BROKERAGE: 118647
};

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

export function validateGeometry(length, width, height) {
    const dims = [length, width, height].sort((a,b)=>b-a);
    const L = dims[0];
    const W = dims[1];
    const H = dims[2];
    const girth = L + (2 * W) + (2 * H);
    return { L, W, H, girth };
}
