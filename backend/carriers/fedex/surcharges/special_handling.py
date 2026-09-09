"""
FedEx Indonesia Rate Calculator - Tahap 4b (special_handling_fees.py)
========================================================================
Special Handling Fees - fee opsional/berbasis flag per shipment, dari
'fedex-rates-sur-en-id-2026.pdf' hal. 2 ("Special Handling Fees").

Beda dari Non-Standard Shipment Fees (nonstandard_fees.py):
- Non-Standard Shipment Fees dipicu OTOMATIS oleh dimensi/berat paket
  (obyektif, bisa dihitung dari angka).
- Special Handling Fees kebanyakan OPSI yang DIPILIH shipper (mis. minta
  signature khusus, bill ke third party, kirim dangerous goods, dll.) ->
  di modul ini semuanya jadi FLAG boolean yang diisi manual, bukan
  dideteksi otomatis dari dimensi.

Fee yang diimplementasikan (per shipment, kecuali disebutkan lain):
  - Address Correction                    : IDR 187.000
  - Third Party Consignee Surcharge       : IDR 163.000
  - FedEx International Broker Select     : IDR 163.000 atau IDR 19.000/kg,
                                             mana yang lebih besar
  - Saturday Pick Up                      : IDR 250.000
  - Saturday Delivery                     : IDR 250.000
  - Inbound Processing Fee                : IDR 44.000 (auto: shipment
                                             EXPORT dgn tujuan U.S. atau
                                             negara anggota EU)
  - Indirect Signature Required (ISR)     : IDR 53.000 (non-freight saja)
  - Direct Signature Required (DSR)       : IDR 59.000 (non-freight saja)
  - Adult Signature Required (ASR)        : IDR 75.000 (non-freight saja)
  - Residential Delivery Surcharge        : IDR 55.000 (non-freight) /
                                             IDR 1.772.000 (freight) - hanya
                                             tujuan US & Canada, TIDAK berlaku
                                             kalau ODA Surcharge sudah kena
  - Accessible Dangerous Goods            : IDR 1.890.000 atau IDR 34.000/kg,
                                             mana yang lebih besar
  - Inaccessible Dangerous Goods          : IDR 885.000 atau IDR 13.000/kg,
                                             mana yang lebih besar
  - Dry Ice Surcharge                     : IDR 82.000 - TIDAK berlaku kalau
                                             Dangerous Goods surcharge (jenis
                                             manapun) sudah kena
  - Third Party Billing Surcharge         : 2.5% dari total shipment charges
                                             -> DIHITUNG DI calculator.py
                                             (bukan di modul ini), karena
                                             butuh subtotal SEMUA komponen lain
                                             lebih dulu.
  - Global Print Return Label Surcharge   : Gratis -> tidak ada nominal,
                                             tidak diimplementasikan sbg fee.

known_limitations (BACA sebelum pakai untuk keputusan bisnis):
1. Inbound Processing Fee dideteksi OTOMATIS dari 'country' & 'direction'
   (lihat is_us_or_eu_destination()), tapi TIDAK mengecek origin -> aturan
   asli "tidak berlaku kalau shipment antar-sesama negara EU" otomatis
   terpenuhi di sini karena origin kalkulator ini SELALU Indonesia (bukan
   EU), jadi tidak perlu dicek terpisah.
2. ISR/DSR/ASR: kriteria resmi FedEx menyebut syarat "declared value for
   Carriage" (< / >= USD500/CAD500) dan "US/Canada residential destination"
   -> modul ini TIDAK memvalidasi declared value atau residential-ness
   secara otomatis (declared value tidak ada di data kalkulator ini).
   Flag isr/dsr/asr = keputusan manual shipper; modul cuma memvalidasi
   bahwa itu non-freight (IP/IE), bukan validasi declared value/destinasi.
3. Residential Delivery Surcharge: modul MENGECEK destinasi US/Canada &
   status ODA (mutually exclusive, sesuai PDF), TAPI validasi "bukan FedEx
   10kg/25kg Box" tidak dicek (rates.py belum bedakan box shipment).
4. Accessible/Inaccessible Dangerous Goods & Dry Ice: PDF bilang DG
   surcharge cuma berlaku "origin/destination di Great Jakarta dan Batam"
   -> kalkulator ini TIDAK melacak kota asal/tujuan secara umum (cuma ODA/
   OPA yg pakai kode pos/kota Indonesia), jadi validasi lokasi Jakarta/Batam
   HARUS dipastikan manual oleh user sebelum set flag DG.
5. Kalau Accessible & Inaccessible Dangerous Goods flag SAMA-SAMA True
   (dua jenis barang berbeda dalam 1 AWB), modul ini MENJUMLAHKAN keduanya
   (asumsi, tidak ada aturan eksplisit di PDF utk kombinasi ini).
"""

EU_MEMBER_STATES = {
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech republic",
    "denmark", "estonia", "finland", "france", "germany", "greece", "hungary",
    "ireland", "italy", "latvia", "lithuania", "luxembourg", "malta",
    "netherlands", "poland", "portugal", "romania", "slovak republic",
    "slovenia", "spain", "sweden",
}

ADDRESS_CORRECTION_FEE = 187000
THIRD_PARTY_CONSIGNEE_FEE = 163000
BROKER_SELECT_MIN_FEE = 163000
BROKER_SELECT_PER_KG = 19000
SATURDAY_PICKUP_FEE = 250000
SATURDAY_DELIVERY_FEE = 250000
INBOUND_PROCESSING_FEE = 44000
ISR_FEE = 53000
DSR_FEE = 59000
ASR_FEE = 75000
RESIDENTIAL_NON_FREIGHT_FEE = 55000
RESIDENTIAL_FREIGHT_FEE = 1772000
ACCESSIBLE_DG_MIN_FEE = 1890000
ACCESSIBLE_DG_PER_KG = 34000
INACCESSIBLE_DG_MIN_FEE = 885000
INACCESSIBLE_DG_PER_KG = 13000
DRY_ICE_FEE = 82000

THIRD_PARTY_BILLING_PCT = 2.5  # dihitung terpisah di calculator.py


def is_us_or_eu_destination(direction, country):
    """Auto-detect kriteria Inbound Processing Fee (destinasi US atau EU)."""
    if direction != "export":
        return False
    c = country.strip().lower()
    if c.startswith("united states"):
        return True
    return c in EU_MEMBER_STATES


def is_us_or_canada(country):
    c = country.strip().lower()
    return c.startswith("united states") or c == "canada"


def compute_special_handling(service, direction, country, billed_weight_kg,
                              oda_applied=False,
                              address_correction=False,
                              third_party_consignee=False,
                              broker_select=False,
                              saturday_pickup=False,
                              saturday_delivery=False,
                              isr=False, dsr=False, asr=False,
                              residential=False,
                              accessible_dangerous_goods=False,
                              inaccessible_dangerous_goods=False,
                              dry_ice=False,
                              inbound_processing_fee_override=None):
    """
    Hitung semua Special Handling Fees KECUALI Third Party Billing Surcharge
    (lihat known_limitations di atas kenapa itu ditangani di calculator.py).

    service           : 'IP' | 'IPF' | 'IE' | 'IEF'
    direction         : 'export' | 'import'
    country           : nama negara (sesuai Zone Index)
    billed_weight_kg  : billed weight shipment (kg) - dipakai utk Broker
                        Select & Dangerous Goods (per kg vs per shipment)
    oda_applied       : True kalau ODA Surcharge sudah dihitung di shipment
                        ini (utk aturan mutually-exclusive dgn Residential
                        Delivery Surcharge)
    inbound_processing_fee_override : None = auto-detect dari destinasi
                        (US/EU); True/False = paksa override manual.
    """
    is_freight = service.upper() in ("IPF", "IEF")
    components = []
    notes = []

    if address_correction:
        components.append(("Address Correction", ADDRESS_CORRECTION_FEE))

    if third_party_consignee:
        components.append(("Third Party Consignee Surcharge", THIRD_PARTY_CONSIGNEE_FEE))

    if broker_select:
        charge = max(BROKER_SELECT_MIN_FEE, BROKER_SELECT_PER_KG * billed_weight_kg)
        components.append(("FedEx International Broker Select", charge))

    if saturday_pickup:
        components.append(("Saturday Pick Up", SATURDAY_PICKUP_FEE))

    if saturday_delivery:
        components.append(("Saturday Delivery", SATURDAY_DELIVERY_FEE))

    inbound_applicable = (
        inbound_processing_fee_override
        if inbound_processing_fee_override is not None
        else is_us_or_eu_destination(direction, country)
    )
    if inbound_applicable:
        components.append(("Inbound Processing Fee", INBOUND_PROCESSING_FEE))

    for flag, label, fee in (
        (isr, "Indirect Signature Required (ISR)", ISR_FEE),
        (dsr, "Direct Signature Required (DSR)", DSR_FEE),
        (asr, "Adult Signature Required (ASR)", ASR_FEE),
    ):
        if not flag:
            continue
        if is_freight:
            notes.append(f"{label} hanya berlaku utk non-freight (IP/IE) -> "
                          f"diabaikan untuk {service.upper()}.")
        else:
            components.append((label, fee))

    if residential:
        if not is_us_or_canada(country):
            notes.append("Residential Delivery Surcharge hanya berlaku utk "
                          "destinasi US & Canada -> diabaikan (destinasi saat "
                          f"ini: {country}).")
        elif oda_applied:
            notes.append("ODA Surcharge sudah diterapkan pada shipment ini -> "
                          "Residential Delivery Surcharge TIDAK dibebankan "
                          "(mutually exclusive, sesuai aturan FedEx).")
        else:
            charge = RESIDENTIAL_FREIGHT_FEE if is_freight else RESIDENTIAL_NON_FREIGHT_FEE
            components.append(("Residential Delivery Surcharge", charge))

    dg_present = False
    if accessible_dangerous_goods:
        charge = max(ACCESSIBLE_DG_MIN_FEE, ACCESSIBLE_DG_PER_KG * billed_weight_kg)
        components.append(("Accessible Dangerous Goods", charge))
        dg_present = True
    if inaccessible_dangerous_goods:
        charge = max(INACCESSIBLE_DG_MIN_FEE, INACCESSIBLE_DG_PER_KG * billed_weight_kg)
        components.append(("Inaccessible Dangerous Goods", charge))
        dg_present = True
    if accessible_dangerous_goods and inaccessible_dangerous_goods:
        notes.append("Accessible & Inaccessible Dangerous Goods sama-sama "
                      "ditandai -> kedua surcharge DIJUMLAH (asumsi utk 2 jenis "
                      "barang berbeda dalam 1 AWB; PDF tidak eksplisit atur "
                      "kombinasi ini, konfirmasi ke FedEx CS kalau perlu pasti).")
    if dg_present:
        notes.append("Dangerous Goods surcharge hanya berlaku utk shipment dgn "
                      "origin/destination di Great Jakarta atau Batam -> pastikan "
                      "kondisi ini terpenuhi (TIDAK divalidasi otomatis di sini).")

    if dry_ice:
        if dg_present:
            notes.append("Dangerous Goods surcharge sudah diterapkan -> Dry Ice "
                          "Surcharge TIDAK dibebankan (sesuai aturan FedEx: DG + "
                          "dry ice bareng, cuma DG surcharge yang berlaku).")
        else:
            components.append(("Dry Ice Surcharge", DRY_ICE_FEE))

    total = sum(c[1] for c in components)
    return {
        "components": [{"label": c[0], "amount": c[1]} for c in components],
        "total_charge": total,
        "notes": notes,
    }
