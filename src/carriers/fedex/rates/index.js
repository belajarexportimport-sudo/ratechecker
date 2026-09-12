
import { RATES } from './publish_data.js'
import { COMMERCIAL_RATES } from './commercial_data.js'
import { roundUp1000 } from '../rules.js'

function priceFromTable(table, zone, service, weight_kg) {
    let billed_weight = weight_kg;
    let min_kg = table.min_kg || 0;
    
    if (min_kg && weight_kg < min_kg) {
        billed_weight = min_kg;
    }
    
    const bands = table.band;
    
    // We simplify and assume standard packages (no envelope or pak selected)
    // 2) Document/flat table (<= 20.5kg)
    if (table.doc && billed_weight <= 20.5) {
        const steps = Object.keys(table.doc).map(Number).sort((a,b)=>a-b);
        let step = steps[steps.length - 1];
        for (const s of steps) {
            if (s >= billed_weight - 1e-9) {
                step = s;
                break;
            }
        }
        
        let stepStr = step.toString();
        if (stepStr.indexOf('.') === -1) stepStr += '.0'; // match 1.0 or similar
        
        let docStep = table.doc[step] || table.doc[step.toFixed(1)];
        if (docStep) {
            let price = docStep[zone];
            if (price) return price;
        }
    }
    
    // 3) Per-kg bands
    if (bands) {
        let chosen = null;
        for (const band of bands) {
            const [min_band, label, rates] = band;
            if (billed_weight >= min_band) {
                chosen = [label, rates];
            }
        }
        if (chosen) {
            const [label, rates] = chosen;
            const per_kg = rates[zone];
            if (per_kg) {
                return per_kg * Math.ceil(billed_weight);
            }
        }
    }
    
    return null;
}

export function calculateBasePublish(service, direction, zone, weight) {
    const isImport = direction.toLowerCase() === 'import';
    const srv = service.toUpperCase();
    let tableDir = isImport ? RATES.import : RATES.export;
    if (!tableDir) return null;
    
    let tableSrv = tableDir[srv];
    if (!tableSrv) return null;
    
    return priceFromTable(tableSrv, zone, srv, weight);
}

export function calculateBaseCommercial(service, direction, zone, weight) {
    const isImport = direction.toLowerCase() === 'import';
    const srv = service.toUpperCase();
    let tableDir = isImport ? COMMERCIAL_RATES.import : COMMERCIAL_RATES.export;
    if (!tableDir) return null;
    
    let tableSrv = tableDir[srv];
    if (!tableSrv) return null;
    
    return priceFromTable(tableSrv, zone, srv, weight);
}

export function calculateBase(rateType, service, direction, zone, weight) {
    const rt = rateType.toLowerCase();
    if (rt === 'publish' || rt === 'promotional') {
        return calculateBasePublish(service, direction, zone, weight);
    } else if (rt === 'commercial') {
        return calculateBaseCommercial(service, direction, zone, weight);
    }
    throw new Error(`rate_type '${rateType}' tidak dikenal untuk FedEx.`);
}
