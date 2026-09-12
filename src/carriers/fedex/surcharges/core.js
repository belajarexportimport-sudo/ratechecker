import { calculateDimWeight, isFreight } from '../rules.js'

export const SURCHARGE_RATES = {
    demand_export_parcel: 15000,
    demand_import_parcel: 15000,
    demand_export_freight: 150000,
    demand_import_freight: 150000,
    oda_opa_min: 440000,
    oda_opa_per_kg: 8700
}

export function computeDemandSurcharge(service, isImport, weight) {
    const isFr = isFreight(service);
    let rate;
    if (isImport) {
        rate = isFr ? SURCHARGE_RATES.demand_import_freight : SURCHARGE_RATES.demand_import_parcel;
    } else {
        rate = isFr ? SURCHARGE_RATES.demand_export_freight : SURCHARGE_RATES.demand_export_parcel;
    }
    return rate * Math.ceil(weight);
}

// Dummy for now to pass compilation
export function computeOdaOpaCharge(postalCode, weight) {
    return 0; // Requires ODA dataset mapping
}
