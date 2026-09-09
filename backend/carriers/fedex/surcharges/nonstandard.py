"""
FedEx Indonesia Rate Calculator - Tahap 4 (nonstandard_fees.py)
=================================================================
Non-Standard Shipment Fees - berbasis dimensi & flag paket/freight unit.

Sumber:
- 'aturan rumus rate fedex.txt' (rumus & kriteria singkat dari user)
- 'fedex-rates-sur-en-id-2026.pdf' hal. 1-2 & bagian "Miscellaneous
  Information" (nominal, kriteria detail, dan aturan kombinasi surcharge)

Cakupan:
- IP & IE (per PACKAGE / collie):
    1. AHS - Dimension          : IDR 431.000/package
    2. AHS - Weight              : IDR 431.000/package
    3. AHS - Packaging           : IDR 431.000/package
    4. Oversize Charge           : IDR 1.072.000/package
    5. Unauthorized Package Chg  : IDR 4.447.000/package
- IPF & IEF (per FREIGHT HANDLING UNIT / piece-skid-pallet):
    6. AHS - Freight             : IDR 2.944.000/unit
    7. Non-Stackable Surcharge   : IDR 3.700.000/unit
    8. Unauthorized Freight Chg  : IDR 7.306.000/unit

Aturan kombinasi (PENTING, dari PDF bagian Miscellaneous Information):
- IP/IE (package): "If a package qualifies for more than one non-standard
  surcharge ... the highest charge after the discount will be assessed."
  -> SELALU ambil yang PALING BESAR di antara kandidat yang trigger,
     TIDAK PERNAH dijumlah, untuk package yang sama.
- IPF/IEF (freight unit): "If a FedEx freight handling unit is subject to
  Unauthorized Freight Charge and also meets the criteria for either
  Additional Handling Surcharge - Freight or Non-Stackable Surcharge, then
  only the highest charge will apply."
  -> Aturan "ambil tertinggi" DISEBUT EKSPLISIT cuma untuk kombinasi yang
     melibatkan Unauthorized Freight Charge. Tidak ada aturan eksplisit utk
     kombinasi AHS-Freight + Non-Stackable TANPA Unauthorized -> di modul
     ini keduanya DIJUMLAH kalau sama-sama trigger tanpa Unauthorized
     (diberi catatan eksplisit di 'notes', bukan diam-diam diasumsikan).
     Kalau butuh interpretasi lain (mis. tetap ambil tertinggi), konfirmasi
     ke FedEx CS & ganti logikanya di sini.

known_limitations (BACA sebelum pakai untuk keputusan bisnis):
1. AHS - Dimension & Unauthorized Package Charge punya "18kg minimum
   billable weight" PER PACKAGE (berlaku juga utk Oversize kalau paket
   itu JUGA memenuhi kriteria AHS-Dimension). Ini mempengaruhi BILLED
   WEIGHT paket itu sendiri (bisa menaikkan biaya dasar/base rate),
   BUKAN cuma nominal surcharge non-standard-nya. Modul ini HANYA
   memberi tahu lewat field 'min_billable_weight_kg' -> BELUM otomatis
   diterapkan ke rates.py/calculator.py (yang saat ini bekerja di level
   TOTAL shipment weight, bukan per-package). Kalau shipment-nya
   single-piece dan actual weight-nya sudah >= 18kg, ini tidak berpengaruh;
   kalau multi-piece atau actual weight < 18kg, HARUS dicek & disesuaikan
   manual.
2. AHS - Packaging pakai flag boolean manual (belum ada cara otomatis
   mendeteksi bentuk kemasan dari data) -> user yang isi.
3. Dimensional/volumetric weight (Length x Width x Height / 5000) TIDAK
   dihitung di modul/kalkulator ini sama sekali -> billed weight yang
   dipakai rates.py masih actual weight saja. Kalau berat volumetrik
   lebih besar dari actual weight, base rate & sebagian kriteria (mis.
   weight-based) di sini bisa under-estimate.
4. Freight (IPF/IEF): kriteria Unauthorized Freight Charge butuh
   length+girth, jadi width_cm & height_cm sebaiknya diisi. Kalau tidak
   diisi, cek length+girth di-skip (hanya cek longest side & weight),
   dan ada catatan di 'notes'.
5. Special Handling Fees (Address Correction, Third Party Billing,
   ISR/DSR/ASR, Residential Delivery, Dangerous Goods, Dry Ice, dll.)
   ada di modul terpisah -> lihat special_handling_fees.py.

=================================================================
TAMBAHAN (auto-switch IP/IE -> IPF/IEF & Chargeable Weight/CWT)
=================================================================
Sumber: instruksi user, dikonfirmasi juga sudah ada di 'index.html'
(kalkulator standalone JS) sejak sebelumnya -> bagian ini PORT logika
yang sama ke Python supaya kedua implementasi tidak divergen.

Aturan (per collie, utk IP & IE):
1. Berat aktual >= 68 kg/collie -> WAJIB pindah ke service freight (IPF/IEF).
2. Panjang+girth per collie > 330 cm -> WAJIB pindah ke freight. Kalau
   dipaksakan tetap IP/IE, kena Oversize Charge (1.072.000/collie) atau
   Unauthorized Package Charge (4.447.000/collie) tergantung seberapa jauh
   melebihi batas (lihat check_package_surcharge()).
3. Panjang (sisi terpanjang) >= 274 cm/collie -> WAJIB pindah ke freight.
4. Kalau dalam SATU shipment ada >=2 collie dan SEBAGIAN (bukan semua) kena
   kriteria 1/2/3 sementara collie lain masih dalam batas IP/IE -> shipment
   HARUS di-split jadi 2 pengiriman terpisah (beda service), karena satu
   AWB tidak boleh campur IP/IE dengan IPF/IEF.

Catatan implementasi:
- Ambang auto-switch (68kg, 274cm, 330cm) SAMA PERSIS dengan ambang
  Unauthorized Package Charge (68kg, 274cm) dan Oversize Charge (330cm
  length+girth) di check_package_surcharge() -> ini BUKAN kebetulan,
  keduanya berasal dari batas resmi FedEx utk apa yang "boleh" dikirim
  sbg IP/IE non-freight.
- Kriteria #3 pakai ">=" (bukan ">") sesuai instruksi eksplisit user &
  index.html, SEDIKIT beda dari threshold Unauthorized Package Charge
  yang pakai ">" murni (>274cm) di check_package_surcharge() -> FedEx
  sendiri tidak 100% konsisten soal ini di dokumen sumber; kalkulator
  ini ikuti versi yang lebih ketat (>=) utk auto-switch supaya tidak
  under-estimate, dan versi asli (>) utk nominal surcharge non-standard.
- CWT (Chargeable/dimensional weight): "invoice weight" utk multi-piece
  shipment = SUM per-package max(actual weight, dimensional weight),
  sesuai fedex-rates-sur-en-id-2026.pdf: "dimensional weight (kg) =
  Length x Width x Height (cm) / 5.000". Kalau package itu JUGA kena
  AHS-Dimension, ada floor tambahan 18kg (lihat AHS_DIMENSION_MIN_BILLABLE_KG).
  calculator.py memakai total CWT ini SEBAGAI PENGGANTI actual weight utk
  base rate kalau parameter `packages` diisi (lihat calculator.calculate()).
"""

AHS_DIMENSION_FEE = 431000
AHS_WEIGHT_FEE = 431000
AHS_PACKAGING_FEE = 431000
OVERSIZE_FEE = 1072000
UNAUTHORIZED_PACKAGE_FEE = 4447000

AHS_DIMENSION_MIN_BILLABLE_KG = 18

AHS_FREIGHT_FEE = 2944000
NON_STACKABLE_FEE = 3700000
UNAUTHORIZED_FREIGHT_FEE = 7306000


def _longest_and_length_plus_girth(length_cm, width_cm, height_cm):
    """
    REVISI (per klarifikasi user, aturan_rumus_rate_fedex.txt): TIDAK di-sort.
    "Length" = field length_cm APA ADANYA (bukan sisi terpanjang hasil sortir),
    dan Girth = 2*width_cm + 2*height_cm (dua field lain apa adanya, juga tidak
    disortir). Jadi:
        Length + Girth = length_cm + 2*width_cm + 2*height_cm
    Asumsi lama (sortir 3 sisi lalu ambil terbesar sbg "longest") SALAH dan
    sudah dikoreksi user -> jangan dikembalikan ke logika sortir.

    Return value (longest, second, length_plus_girth) dipertahankan agar
    kompatibel dgn caller lain, tapi "longest" di sini = length_cm apa adanya
    dan "second" = width_cm apa adanya (BUKAN hasil sortir).
    """
    girth = 2 * width_cm + 2 * height_cm
    return length_cm, width_cm, length_cm + girth


def check_package_surcharge(length_cm, width_cm, height_cm, weight_kg,
                             non_cardboard_packaging=False,
                             round_or_cylindrical=False,
                             banded_or_has_wheels_handles_straps=False,
                             could_entangle_or_damage=False):
    """
    Hitung Non-Standard Shipment Fee utk SATU package/collie (service IP & IE).
    Dimensi dalam cm, weight_kg = actual weight package ini (bukan total shipment).

    Flag AHS-Packaging (isi manual sesuai kondisi paket):
      non_cardboard_packaging               : bukan dus karton (metal/kayu/kanvas/
                                               kulit/plastik keras-lunak/styrofoam),
                                               tidak sepenuhnya tertutup, atau
                                               dibungkus shrink/stretch wrap
      round_or_cylindrical                  : bentuk bulat/silinder (tabung, kaleng,
                                               ember, drum, ban, dll.)
      banded_or_has_wheels_handles_straps   : diikat metal/plastik/kain, atau ada
                                               roda/handle/strap (mis. sepeda)
      could_entangle_or_damage              : berpotensi tersangkut/merusak paket
                                               lain atau sistem sortir FedEx

    Return:
      triggered   : list nama semua surcharge yang KRITERIANYA terpenuhi
      charge      : nominal yang DIBEBANKAN (hanya yang TERBESAR, sesuai aturan
                    "highest charge ... will be assessed" - tidak dijumlah)
      label       : nama surcharge yang dipakai (None kalau tidak ada yang trigger)
      min_billable_weight_kg : 18 kalau kena AHS-Dimension (lihat known_limitations #1),
                    None kalau tidak
    """
    if length_cm <= 0 or width_cm <= 0 or height_cm <= 0:
        raise ValueError("Dimensi (length/width/height) harus > 0 cm.")
    if weight_kg <= 0:
        raise ValueError("weight_kg harus > 0.")

    longest, second_longest, length_plus_girth = _longest_and_length_plus_girth(
        length_cm, width_cm, height_cm)
    volume_cm3 = length_cm * width_cm * height_cm

    ahs_dimension = (longest > 121 or second_longest > 76
                      or length_plus_girth > 266 or volume_cm3 > 169901)
    ahs_weight = weight_kg > 25
    ahs_packaging = (non_cardboard_packaging or round_or_cylindrical
                      or banded_or_has_wheels_handles_straps or could_entangle_or_damage)
    oversize = (longest > 243 or length_plus_girth > 330
                or weight_kg > 50 or volume_cm3 > 283168)
    unauthorized = (longest > 274 or length_plus_girth > 419 or weight_kg > 68)

    candidates = []
    if ahs_dimension:
        candidates.append(("AHS - Dimension", AHS_DIMENSION_FEE))
    if ahs_weight:
        candidates.append(("AHS - Weight", AHS_WEIGHT_FEE))
    if ahs_packaging:
        candidates.append(("AHS - Packaging", AHS_PACKAGING_FEE))
    if oversize:
        candidates.append(("Oversize Charge", OVERSIZE_FEE))
    if unauthorized:
        candidates.append(("Unauthorized Package Charge", UNAUTHORIZED_PACKAGE_FEE))

    if not candidates:
        return {
            "triggered": [],
            "charge": 0,
            "label": None,
            "min_billable_weight_kg": None,
            "measurements": {
                "longest_cm": longest, "second_longest_cm": second_longest,
                "length_plus_girth_cm": length_plus_girth, "volume_cm3": volume_cm3,
            },
        }

    label, charge = max(candidates, key=lambda c: c[1])
    return {
        "triggered": [c[0] for c in candidates],
        "charge": charge,
        "label": label,
        "min_billable_weight_kg": AHS_DIMENSION_MIN_BILLABLE_KG if ahs_dimension else None,
        "measurements": {
            "longest_cm": longest, "second_longest_cm": second_longest,
            "length_plus_girth_cm": length_plus_girth, "volume_cm3": volume_cm3,
        },
    }


def check_freight_surcharge(length_cm, weight_kg, width_cm=None, height_cm=None,
                             non_stackable=False):
    """
    Hitung Non-Standard Shipment Fee utk SATU freight handling unit
    (piece/skid/pallet), utk service IPF & IEF.

    length_cm      : sisi terpanjang unit (cm) - WAJIB.
    width_cm/height_cm : opsional, dipakai utk hitung length+girth (kriteria
                     Unauthorized Freight Charge). Kalau tidak diisi, kriteria
                     length+girth di-skip (lihat known_limitations #4).
    weight_kg      : actual weight unit ini (kg), bukan total shipment.
    non_stackable  : True kalau unit tidak bisa ditumpuk dgn aman.
    """
    if length_cm <= 0:
        raise ValueError("length_cm harus > 0.")
    if weight_kg <= 0:
        raise ValueError("weight_kg harus > 0.")

    notes = []
    length_plus_girth = None
    if width_cm is not None and height_cm is not None:
        if width_cm <= 0 or height_cm <= 0:
            raise ValueError("width_cm/height_cm harus > 0 kalau diisi.")
        longest, _, length_plus_girth = _longest_and_length_plus_girth(
            length_cm, width_cm, height_cm)
    else:
        longest = length_cm
        notes.append("width_cm/height_cm tidak diisi -> kriteria length+girth utk "
                      "Unauthorized Freight Charge di-skip (cek manual kalau unit "
                      "besar/tidak beraturan).")

    ahs_freight = longest > 157
    unauthorized = (longest > 302 or weight_kg > 1995
                     or (length_plus_girth is not None and length_plus_girth > 762))

    ahs_freight_charge = AHS_FREIGHT_FEE if ahs_freight else 0
    non_stackable_charge = NON_STACKABLE_FEE if non_stackable else 0
    unauthorized_charge = UNAUTHORIZED_FREIGHT_FEE if unauthorized else 0

    if unauthorized_charge and (ahs_freight_charge or non_stackable_charge):
        # Aturan eksplisit di PDF: kombinasi yg melibatkan Unauthorized Freight
        # Charge -> ambil yang PALING BESAR saja.
        components = [c for c in [
            ("Unauthorized Freight Charge", unauthorized_charge),
            ("AHS - Freight", ahs_freight_charge),
            ("Non-Stackable Surcharge", non_stackable_charge),
        ] if c[1] > 0]
        label, charge = max(components, key=lambda c: c[1])
        triggered = [c[0] for c in components]
    else:
        # AHS-Freight & Non-Stackable Surcharge TIDAK ada aturan eksplisit "ambil
        # tertinggi" kalau Unauthorized Freight Charge tidak ikut trigger ->
        # keduanya DIJUMLAH di sini (lihat catatan di docstring modul).
        parts = []
        if ahs_freight_charge:
            parts.append(("AHS - Freight", ahs_freight_charge))
        if non_stackable_charge:
            parts.append(("Non-Stackable Surcharge", non_stackable_charge))
        charge = sum(c[1] for c in parts)
        triggered = [c[0] for c in parts]
        label = " + ".join(triggered) if parts else None
        if len(parts) > 1:
            notes.append("AHS - Freight dan Non-Stackable Surcharge sama-sama "
                          "trigger tanpa Unauthorized Freight Charge -> DIJUMLAH "
                          "(asumsi, karena PDF tidak menyebut aturan 'ambil "
                          "tertinggi' utk kombinasi spesifik ini). Konfirmasi ke "
                          "FedEx CS kalau butuh kepastian.")

    return {
        "triggered": triggered,
        "charge": charge,
        "label": label,
        "notes": notes,
        "measurements": {"longest_cm": longest, "length_plus_girth_cm": length_plus_girth},
    }


_PACKAGE_SURCHARGE_KEYS = {
    "length_cm", "width_cm", "height_cm", "weight_kg",
    "non_cardboard_packaging", "round_or_cylindrical",
    "banded_or_has_wheels_handles_straps", "could_entangle_or_damage",
}


def _package_surcharge_kwargs(pkg):
    """
    Filter 1 dict package jadi kwargs yang VALID utk check_package_surcharge()
    saja -- buang 'label' dan field API lain yang belum/tidak relevan di
    fungsi ini (mis. 'qty', 'packing_type' dari skema RateRequest.extra
    lewat API -- lihat backend/api/routes.py::_normalize_package()).

    Kenapa whitelist (bukan blacklist per-field): supaya caller/skema API
    boleh nambah field baru di masa depan tanpa bikin fungsi ini crash lagi
    (pola bug yang sudah 2x kejadian: 'qty' lalu 'packing_type').

    CATATAN: 'packing_type' SENGAJA belum di-mapping ke flag
    non_cardboard_packaging/dll di sini -- itu flag manual yang belum ada
    logic otomatis dari string packing_type, jadi utk sekarang cuma
    di-drop diam-diam (bukan bug, tapi keterbatasan yang perlu tahu: kalau
    user isi packing_type='pallet' misalnya, itu TIDAK otomatis menaikkan
    non_cardboard_packaging=True -- perlu isi extra kalau mau AHS-Packaging
    ke-detect).
    """
    return {k: v for k, v in pkg.items() if k in _PACKAGE_SURCHARGE_KEYS}


def summarize_packages(packages):
    """
    packages: list of dict, tiap dict = kwargs utk check_package_surcharge()
              (boleh tambah key 'label' bebas utk identifikasi, contoh
              {'label': 'Collie 1', 'length_cm':130,'width_cm':40,'height_cm':40,
               'weight_kg':10}).
    Return: total charge semua package + detail per package + notes gabungan.
    """
    details = []
    notes = []
    total = 0
    for i, pkg in enumerate(packages, start=1):
        pkg = dict(pkg)
        pkg_label = pkg.pop("label", f"Collie {i}")
        res = check_package_surcharge(**_package_surcharge_kwargs(pkg))
        res["package_label"] = pkg_label
        details.append(res)
        total += res["charge"]
        if res["min_billable_weight_kg"]:
            notes.append(f"{pkg_label}: kena AHS-Dimension -> minimum billable "
                          f"weight {res['min_billable_weight_kg']}kg utk package ini "
                          f"(lihat known_limitations #1 di nonstandard_fees.py, "
                          f"BELUM otomatis diterapkan ke base rate).")
    return {"total_charge": total, "details": details, "notes": notes}


def summarize_freight_units(units):
    """
    units: list of dict, tiap dict = kwargs utk check_freight_surcharge()
           (boleh tambah key 'label' bebas, contoh {'label': 'Pallet 1',
           'length_cm': 180, 'weight_kg': 300}).
    """
    details = []
    notes = []
    total = 0
    for i, unit in enumerate(units, start=1):
        unit = dict(unit)
        unit_label = unit.pop("label", f"Freight Unit {i}")
        res = check_freight_surcharge(**unit)
        res["unit_label"] = unit_label
        details.append(res)
        total += res["charge"]
        for n in res["notes"]:
            notes.append(f"{unit_label}: {n}")
    return {"total_charge": total, "details": details, "notes": notes}


# =============================================================================
# Auto-switch IP/IE -> IPF/IEF & wajib-split (lihat docstring modul di atas)
# =============================================================================

IPIE_MAX_WEIGHT_KG = 68
IPIE_MAX_LENGTH_CM = 274
IPIE_MAX_LENGTH_PLUS_GIRTH_CM = 330


class ShipmentSplitRequired(Exception):
    """
    Di-raise kalau dalam satu shipment ada >=2 collie dan SEBAGIAN (bukan
    semua) melebihi batas maksimum IP/IE (lihat check_service_eligibility),
    sementara collie lain masih dalam batas -> satu AWB tidak boleh campur
    service IP/IE dengan IPF/IEF, harus di-split jadi 2 pengiriman terpisah.

    Atribut:
      eligibility : list hasil check_service_eligibility() per collie
                    (masing-masing sudah ditambah key 'label')
    """
    def __init__(self, message, eligibility):
        super().__init__(message)
        self.eligibility = eligibility


def check_service_eligibility(length_cm, width_cm, height_cm, weight_kg):
    """
    Cek APAKAH satu collie melebihi batas maksimum service IP/IE (harus
    IPF/IEF), berdasarkan 3 kriteria (lihat docstring modul):
      1. weight_kg >= 68kg
      2. length_cm + girth(2*width_cm+2*height_cm) > 330cm
      3. length_cm (field "Length" apa adanya, BUKAN sisi terpanjang hasil
         sortir -- lihat revisi di _longest_and_length_plus_girth) >= 274cm
    """
    if length_cm <= 0 or width_cm <= 0 or height_cm <= 0:
        raise ValueError("Dimensi (length/width/height) harus > 0 cm.")
    if weight_kg <= 0:
        raise ValueError("weight_kg harus > 0.")

    longest, _, length_plus_girth = _longest_and_length_plus_girth(
        length_cm, width_cm, height_cm)

    reasons = []
    if weight_kg >= IPIE_MAX_WEIGHT_KG:
        reasons.append(f"Berat {weight_kg}kg >= {IPIE_MAX_WEIGHT_KG}kg")
    if longest >= IPIE_MAX_LENGTH_CM:
        reasons.append(f"Panjang {longest}cm >= {IPIE_MAX_LENGTH_CM}cm")
    if length_plus_girth > IPIE_MAX_LENGTH_PLUS_GIRTH_CM:
        reasons.append(f"Panjang + lilit {length_plus_girth}cm > "
                        f"{IPIE_MAX_LENGTH_PLUS_GIRTH_CM}cm")

    return {
        "required": bool(reasons),
        "reasons": reasons,
        "longest_cm": longest,
        "length_plus_girth_cm": length_plus_girth,
    }


def evaluate_packages_for_service_switch(service, packages):
    """
    Cek SEMUA package/collie dalam satu shipment IP/IE terhadap batas
    maksimum (check_service_eligibility). packages: list of dict (sama
    format dengan summarize_packages(), minimal length_cm/width_cm/
    height_cm/weight_kg).

    Return dict:
      action        : 'none' (semua collie masih dalam batas -> tidak perlu
                       apa-apa) | 'switch' (SEMUA collie melebihi batas ->
                       auto-switch ke freight)
      new_service   : 'IPF'/'IEF' kalau action=='switch', None kalau 'none'
      eligibility   : list hasil check_service_eligibility() per collie
                       (ditambah key 'label')
      forced_fee_preview : (hanya kalau action=='switch') list info nominal
                       non-standard fee yang AKAN kena kalau tetap dipaksakan
                       jadi IP/IE (utk ditampilkan sbg peringatan)

    Raise ShipmentSplitRequired kalau SEBAGIAN (bukan semua/tidak ada) collie
    melebihi batas -> caller WAJIB menangani (minta user split manual),
    tidak diam-diam dilanjutkan dengan data yang salah.
    """
    eligibility = []
    for i, pkg in enumerate(packages, start=1):
        label = pkg.get("label", f"Collie {i}")
        elig = check_service_eligibility(
            pkg["length_cm"], pkg["width_cm"], pkg["height_cm"], pkg["weight_kg"])
        elig["label"] = label
        eligibility.append(elig)

    any_required = any(e["required"] for e in eligibility)
    if not any_required:
        return {"action": "none", "new_service": None, "eligibility": eligibility}

    all_required = all(e["required"] for e in eligibility)
    if len(packages) > 1 and not all_required:
        raise ShipmentSplitRequired(
            f"Sebagian collie melebihi batas maksimum {service.upper()} "
            f"(berat >= {IPIE_MAX_WEIGHT_KG}kg, panjang >= {IPIE_MAX_LENGTH_CM}cm, "
            f"atau panjang+lilit > {IPIE_MAX_LENGTH_PLUS_GIRTH_CM}cm), sementara "
            f"collie lain masih dalam batas. Satu shipment tidak boleh mencampur "
            f"service {service.upper()} dengan IPF/IEF -> pisahkan jadi 2 "
            f"pengiriman terpisah.",
            eligibility,
        )

    new_service = "IPF" if service.upper() == "IP" else "IEF"
    forced_fee_preview = []
    for pkg, elig in zip(packages, eligibility):
        chk_kwargs = _package_surcharge_kwargs(pkg)
        chk = check_package_surcharge(**chk_kwargs)
        forced_fee_preview.append({
            "label": elig["label"],
            "reasons": elig["reasons"],
            "forced_label": chk["label"],
            "forced_charge": chk["charge"],
        })
    return {
        "action": "switch",
        "new_service": new_service,
        "eligibility": eligibility,
        "forced_fee_preview": forced_fee_preview,
    }


# =============================================================================
# Chargeable Weight (CWT) / dimensional weight
# =============================================================================

DIMENSIONAL_WEIGHT_DIVISOR_CM = 5000  # dari fedex-rates-sur-en-id-2026.pdf


def dimensional_weight_kg(length_cm, width_cm, height_cm,
                           divisor=DIMENSIONAL_WEIGHT_DIVISOR_CM):
    """Dimensional/volumetric weight (kg) = L x W x H (cm) / 5.000."""
    if length_cm <= 0 or width_cm <= 0 or height_cm <= 0:
        raise ValueError("Dimensi (length/width/height) harus > 0 cm.")
    return (length_cm * width_cm * height_cm) / divisor


def compute_shipment_chargeable_weight(packages,
                                        divisor=DIMENSIONAL_WEIGHT_DIVISOR_CM):
    """
    Hitung Chargeable Weight (CWT) / invoice weight utk shipment IP/IE
    multi-piece, sesuai aturan PDF: "invoice weight will be the sum of the
    higher actual weight or dimensional weight of each individual package".

    Per package: chargeable_weight = max(actual_weight, dimensional_weight,
    18kg floor kalau package itu kena kriteria AHS-Dimension).

    packages: list of dict (sama format check_package_surcharge(), boleh ada
              key 'label'; flag AHS-Packaging opsional, tidak berpengaruh ke
              CWT tapi dipakai kalau ada utk deteksi AHS-Dimension yang akurat
              -- sebenarnya AHS-Packaging tidak mempengaruhi threshold
              AHS-Dimension, jadi aman diabaikan kalau tidak ada).

    Return dict:
      total_chargeable_weight_kg : total CWT semua package (dipakai sbg
                                    weight utk base rate)
      details : list per package {label, actual_weight_kg,
                dimensional_weight_kg, chargeable_weight_kg,
                ahs_dimension_floor_applied (bool)}
    """
    details = []
    total = 0.0
    for i, pkg in enumerate(packages, start=1):
        label = pkg.get("label", f"Collie {i}")
        length_cm, width_cm, height_cm = pkg["length_cm"], pkg["width_cm"], pkg["height_cm"]
        actual = pkg["weight_kg"]
        dim_w = dimensional_weight_kg(length_cm, width_cm, height_cm, divisor)

        chk_kwargs = _package_surcharge_kwargs(pkg)
        chk = check_package_surcharge(**chk_kwargs)
        floor = chk["min_billable_weight_kg"] or 0

        cw = max(actual, dim_w, floor)
        total += cw
        details.append({
            "label": label,
            "actual_weight_kg": actual,
            "dimensional_weight_kg": dim_w,
            "chargeable_weight_kg": cw,
            "ahs_dimension_floor_applied": floor > 0 and cw == floor,
        })
    return {"total_chargeable_weight_kg": total, "details": details}


def compute_freight_chargeable_weight(freight_units,
                                       divisor=DIMENSIONAL_WEIGHT_DIVISOR_CM):
    """
    Hitung Chargeable Weight (CWT) / invoice weight utk shipment IPF/IEF
    multi-unit. Konfirmasi user (7 Sep 2026): aturan pembagian dimensional
    weight utk IPF/IEF SAMA dengan IP/IE -> divisor 5.000, formula identik
    (L x W x H / 5.000), TIDAK ada divisor freight yang berbeda.

    Per freight unit: chargeable_weight = max(actual_weight, dimensional_weight).
    BEDA dari compute_shipment_chargeable_weight() (IP/IE): TIDAK ada floor
    18kg -> itu murni aturan AHS-Dimension yang cuma berlaku utk IP/IE
    (lihat fedex-rates-sur-en-id-2026.pdf, "Applicable to IPE, IP & IE"),
    freight punya threshold sendiri (AHS-Freight, Unauthorized Freight) yang
    tidak menyertakan minimum billable weight per-unit.

    freight_units: list of dict (sama format check_freight_surcharge()) -
                   width_cm/height_cm OPSIONAL (kalau salah satu/keduanya
                   tidak diisi, dimensional weight unit itu di-skip, cuma
                   pakai actual weight -> sama seperti check_freight_surcharge
                   yang skip kriteria length+girth kalau width/height kosong).

    Return dict:
      total_chargeable_weight_kg : total CWT semua unit (dipakai sbg weight
                                    utk base rate)
      details : list per unit {label, actual_weight_kg,
                dimensional_weight_kg (None kalau di-skip),
                chargeable_weight_kg}
    """
    details = []
    total = 0.0
    for i, unit in enumerate(freight_units, start=1):
        label = unit.get("label", f"Unit {i}")
        actual = unit["weight_kg"]
        length_cm = unit.get("length_cm")
        width_cm = unit.get("width_cm")
        height_cm = unit.get("height_cm")

        if length_cm and width_cm and height_cm:
            dim_w = dimensional_weight_kg(length_cm, width_cm, height_cm, divisor)
            cw = max(actual, dim_w)
        else:
            dim_w = None
            cw = actual

        total += cw
        details.append({
            "label": label,
            "actual_weight_kg": actual,
            "dimensional_weight_kg": dim_w,
            "chargeable_weight_kg": cw,
        })
    return {"total_chargeable_weight_kg": total, "details": details}
