const FEDEX_TO_UPS = {
    "IP":  "saver",
    "IPF": "wwef",
    "IE":  "expedited",
    "IEF": "wwef",
}

const UPS_TO_FEDEX = {
    "saver":     "IP",
    "expedited": "IE",
    "wwef":      "IPF",
    "envelope":  "IE",
}

export function mapService(fromCarrier, toCarrier, service) {
    const fc = fromCarrier.toLowerCase()
    const tc = toCarrier.toLowerCase()

    if (fc === "fedex" && tc === "ups") {
        return FEDEX_TO_UPS[service.toUpperCase()] || null
    }
    if (fc === "ups" && tc === "fedex") {
        return UPS_TO_FEDEX[service.toLowerCase()] || null
    }

    return null
}
