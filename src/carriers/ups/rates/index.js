import { RATES } from './publish_data.js'
import { A26_RATES, B26_RATES } from './commercial_data.js'

function priceFromTable(table, weight) {
    if (weight <= 20.0) {
        // Flat rates, nearest 0.5kg
        const rounded = Math.round(weight * 2) / 2;
        const key = rounded.toFixed(1);
        if (table[key] !== undefined) return table[key];
        
        const floatKeys = Object.keys(table).filter(k => !isNaN(parseFloat(k))).map(parseFloat).sort((a,b)=>a-b);
        for (const k of floatKeys) {
            if (k >= weight - 0.001) return table[k.toFixed(1)] || table[k.toString()];
        }
    }
    
    // Per-kg rate, round up to 1kg
    const wCeil = Math.ceil(weight);
    const intKeys = Object.keys(table).filter(k => !isNaN(parseInt(k)) && !k.includes('.')).map(Number).sort((a,b)=>a-b);
    for (const k of intKeys) {
        if (k === 71) {
            if (wCeil <= 71) return table["71"];
        } else if (k === 1000) {
            if (wCeil > 99) return table["1000"];
        } else {
            if (wCeil <= k) return table[k.toString()];
        }
    }
    
    return null;
}

export function calculateBasePublish(service, direction, zone, weight) {
    const tableDir = direction === "import" ? RATES.import : RATES.export;
    if (!tableDir) return null;
    
    const tableSrv = tableDir[service];
    if (!tableSrv) return null;
    
    // Publish uses zone as string (e.g. "1", "2")
    const tableZone = tableSrv[zone.toString()];
    if (!tableZone) return null;
    
    const rate = priceFromTable(tableZone, weight);
    if (!rate) return null;
    
    return weight <= 20.0 ? rate : rate * Math.ceil(weight);
}

export function calculateBaseCommercial(rateType, service, direction, zone, weight) {
    // A26 / B26 uses RATES_EXTENDED format
    const db = rateType === "a26" ? A26_RATES : B26_RATES;
    
    const tableDir = direction === "import" ? db.import : db.export;
    if (!tableDir) return null;
    
    const tableSrv = tableDir[service];
    if (!tableSrv) return null;
    
    // Zone key could be number or string
    let tableZone = tableSrv[zone.toString()];
    if (!tableZone && typeof zone === 'string') {
        const lowerZone = zone.toLowerCase();
        for (const k of Object.keys(tableSrv)) {
            if (k.toLowerCase() === lowerZone) {
                tableZone = tableSrv[k];
                break;
            }
        }
    }
    
    if (!tableZone) return null;
    
    const rate = priceFromTable(tableZone, weight);
    if (!rate) return null;
    
    return weight <= 20.0 ? rate : rate * Math.ceil(weight);
}

export function calculateBase(rateType, service, direction, zone, weight) {
    if (rateType === "publish") {
        return calculateBasePublish(service, direction, zone, weight);
    } else if (rateType === "a26" || rateType === "b26") {
        return calculateBaseCommercial(rateType, service, direction, zone, weight);
    }
    throw new Error(`rate_type '${rateType}' tidak dikenal untuk UPS.`);
}
