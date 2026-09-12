export const DIM_DIVISOR = 5000;
export const MINIMUM_BILLED_WEIGHT_KG = 0.5;

export const FREIGHT_SERVICES = ["IPF", "IEF"];
export const PARCEL_SERVICES = ["IP", "IE"];

export function isFreight(service) {
    return FREIGHT_SERVICES.includes(service.toUpperCase());
}

export function calculateDimWeight(length, width, height) {
    if (!length || !width || !height) return 0;
    return (length * width * height) / DIM_DIVISOR;
}

export function roundUp1000(amount) {
    return Math.ceil(amount / 1000) * 1000;
}
