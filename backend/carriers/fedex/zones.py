"""
FedEx Zone Index & Lookup
=========================
Berisi semua data zone FedEx (Publish dan Commercial) serta fungsi lookup.
Dipisah dari rates/publish.py dan rates/commercial.py agar zone logic
tidak tersebar di banyak file.

Source asli:
  - Publish zones  : rates_promotional.py (ZONES, _ZONE_CSV, ZONE_INDEX, find_country, get_zone)
  - Commercial zones: rates_commercial.py  (COMMERCIAL_ZONES, COMMERCIAL_ZONE_INDEX,
                       COMMERCIAL_ALIASES, COMMERCIAL_UNAVAILABLE_COUNTRIES,
                       find_country_commercial, get_zone_commercial)

Tidak ada perubahan logic - hanya dipindah lokasinya.
"""

from backend.carriers.fedex.rates.common import FedExRateError, resolve_china_zone

# =============================================================================
# PUBLISH ZONES (Zone A-G, dari fedex-rates-exp/imp-en-id-2026.pdf)
# =============================================================================
ZONES = ["A", "B", "C", "D", "E", "F", "G"]

_ZONE_CSV = """
Afghanistan,G,G,G,G
Albania,G,G,G,G
Algeria,G,G,G,G
American Samoa,G,G,G,G
Andorra,E,E,E,E
Angola,G,G,G,G
Anguilla,G,G,G,G
Antigua,G,G,G,G
Argentina,G,G,G,G
Armenia,G,G,G,G
Aruba,G,G,G,G
Australia,C,C,C,C
Austria,E,E,E,E
Azerbaijan,G,G,G,G
Bahamas,G,G,G,G
Bahrain,F,F,F,F
Bangladesh,F,F,F,F
Barbados,G,G,G,G
Barbuda,G,G,G,G
Belarus,G,G,G,G
Belgium,E,E,E,E
Belize,G,G,G,G
Benin,G,G,G,G
Bermuda,G,G,G,G
Bhutan,G,G,G,G
Bolivia,G,G,G,G
Bonaire,G,G,G,G
Bosnia-Herzegovina,G,G,G,G
Botswana,G,G,G,G
Brazil,G,G,G,G
British Virgin Islands,G,G,G,G
Brunei,B,B,B,B
Bulgaria,E,E,E,E
Burkina Faso,G,G,G,G
Burundi,G,G,G,G
Cambodia,B,B,B,B
Cameroon,G,G,G,G
Canada,D,D,D,D
Canary Islands,E,E,E,E
Cape Verde,G,G,G,G
Cayman Islands,G,G,G,G
Chad,G,G,G,G
Channel Islands,E,E,E,E
Chile,G,G,G,G
China,C,C,C,C
Colombia,G,G,G,G
Congo,G,G,G,G
Congo Dem Rep Of,G,G,G,G
Cook Islands,G,G,G,G
Costa Rica,G,G,G,G
Croatia,E,E,E,E
Curacao,G,G,G,G
Cyprus,E,E,E,E
Czech Republic,E,E,E,E
Denmark,E,E,E,E
Djibouti,G,G,G,G
Dominica,G,G,G,G
Dominican Republic,G,G,G,G
East Timor,G,G,G,G
Ecuador,G,G,G,G
Egypt,F,F,F,F
El Salvador,G,G,G,G
Eritrea,G,G,G,G
Estonia,E,E,E,E
Ethiopia,G,G,G,G
Faeroe Islands,E,E,E,E
Fiji,G,G,G,G
Finland,E,E,E,E
France,E,E,E,E
French Guiana,G,G,G,G
French Polynesia,G,G,G,G
Gabon,G,G,G,G
Gambia,G,G,G,G
Georgia,G,G,G,G
Germany,E,E,E,E
Ghana,G,G,G,G
Gibraltar,E,E,E,E
Grand Cayman,G,G,G,G
Great Thatch Island,G,G,G,G
Great Tobago Islands,G,G,G,G
Greece,E,E,E,E
Greenland,E,E,E,E
Grenada,G,G,G,G
Guadeloupe,G,G,G,G
Guam,G,G,G,G
Guatemala,G,G,G,G
Guinea,G,G,G,G
Guyana,G,G,G,G
Haiti,G,G,G,G
Honduras,G,G,G,G
Hong Kong,B,B,B,B
Hungary,E,E,E,E
Iceland,E,E,E,E
India,F,F,F,F
Iraq,G,G,G,G
Ireland,E,E,E,E
Israel,E,E,E,E
Italy,E,E,E,E
Ivory Coast,G,G,G,G
Jamaica,G,G,G,G
Japan,C,C,C,C
Jordan,F,F,F,F
Jost Van Dyke Islands,G,G,G,G
Kazakhstan,G,G,G,G
Kenya,G,G,G,G
Kuwait,F,F,F,F
Kyrgyzstan,G,G,G,G
Laos,B,B,B,B
Latvia,E,E,E,E
Lebanon,F,F,F,F
Lesotho,G,G,G,G
Liberia,G,G,G,G
Libya,G,G,G,G
Liechtenstein,E,E,E,E
Lithuania,E,E,E,E
Luxembourg,E,E,E,E
Macau,B,B,B,B
Macedonia,G,G,G,G
Madagascar,G,G,G,G
Malawi,G,G,G,G
Malaysia,B,B,B,B
Maldives,G,G,G,G
Mali,G,G,G,G
Malta,E,E,E,E
Marshall Islands,G,G,G,G
Martinique,G,G,G,G
Mauritania,G,G,G,G
Mauritius,G,G,G,G
Mexico,D,D,D,D
Micronesia,G,G,G,G
Moldova,G,G,G,G
Monaco,E,E,E,E
Mongolia,B,B,B,B
Montenegro,G,G,G,G
Montserrat,G,G,G,G
Morocco,G,G,G,G
Mozambique,G,G,G,G
Namibia,G,G,G,G
Nepal,G,G,G,G
Netherlands,E,E,E,E
Nevis,G,G,G,G
New Caledonia,G,G,G,G
New Zealand,C,C,C,C
Nicaragua,G,G,G,G
Niger,G,G,G,G
Nigeria,G,G,G,G
Norfolk Island,C,C,C,C
Norman Island,G,G,G,G
Northern Mariana Islands,G,G,G,G
Norway,E,E,E,E
Oman,F,F,F,F
Pakistan,F,F,F,F
Palau,G,G,G,G
Palestine Autonomous,G,G,G,G
Panama,G,G,G,G
Papua New Guinea,G,G,G,G
Paraguay,G,G,G,G
Peru,G,G,G,G
Philippines,B,B,B,B
Poland,E,E,E,E
Portugal,E,E,E,E
Puerto Rico,D,D,D,D
Qatar,F,F,F,F
Reunion,G,G,G,G
Romania,E,E,E,E
Rota,G,G,G,G
Russia,E,E,E,E
Rwanda,G,G,G,G
Saba,G,G,G,G
Saipan,G,G,G,G
Samoa,G,G,G,G
San Marino,E,E,E,E
Saudi Arabia,F,F,F,F
Senegal,G,G,G,G
Serbia,E,E,E,E
Seychelles,G,G,G,G
Singapore,A,A,A,A
Slovak Republic,E,E,E,E
Slovenia,E,E,E,E
South Africa,F,F,F,F
South Korea,C,C,C,C
Spain,E,E,E,E
Sri Lanka,F,F,F,F
St. Barthelemy,G,G,G,G
St. Christopher,G,G,G,G
St. Croix Island,G,G,G,G
St. Eustatius,G,G,G,G
St. John,G,G,G,G
St. Kitts & Nevis,G,G,G,G
St. Lucia,G,G,G,G
St. Maarten,G,G,G,G
St. Martin,G,G,G,G
St. Thomas,G,G,G,G
St. Vincent,G,G,G,G
Suriname,G,G,G,G
Swaziland,G,G,G,G
Sweden,E,E,E,E
Switzerland,E,E,E,E
Syria,G,G,G,G
Tahiti,G,G,G,G
Taiwan,C,C,C,C
Tanzania,G,G,G,G
Thailand,B,B,B,B
Tinian,G,G,G,G
Togo,G,G,G,G
Tonga,G,G,G,G
Tortola Island,G,G,G,G
Trinidad & Tobago,G,G,G,G
Tunisia,G,G,G,G
Turkey,E,E,E,E
Turks & Caicos Islands,G,G,G,G
U.S. Virgin Islands,G,G,G,G
Uganda,G,G,G,G
Ukraine,E,E,E,E
Union Island,G,G,G,G
United Arab Emirates,F,F,F,F
United Kingdom,E,E,E,E
United States (Western Region),D,D,D,D
United States (Rest of Country),D,D,D,D
Uruguay,G,G,G,G
Uzbekistan,G,G,G,G
Vanuatu,G,G,G,G
Vatican City,E,E,E,E
Venezuela,G,G,G,G
Vietnam,B,B,B,B
Wallis & Futuna,G,G,G,G
Yemen,G,G,G,G
Zambia,G,G,G,G
Zimbabwe,G,G,G,G
""".strip()




def _load_zones(csv_text):
    zones = {}
    for line in csv_text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        name, exp_ip, exp_ie, imp_ip, imp_ie = parts
        zones[name.lower()] = {
            "display_name": name,
            "export": {"IP": exp_ip, "IPF": exp_ip, "IE": exp_ie, "IEF": exp_ie},
            "import": {"IP": imp_ip, "IPF": imp_ip, "IE": imp_ie, "IEF": imp_ie},
        }
    return zones


ZONE_INDEX = _load_zones(_ZONE_CSV)


# Alias kode negara pendek (ISO-2 dkk) -> nama lengkap sesuai key di ZONE_INDEX/
# COMMERCIAL_ZONE_INDEX. Ditambahkan reaktif tiap ada laporan negara yang gagal
# ditemukan gara-gara user pakai kode singkat (bukan nama lengkap) -- lihat
# laporan "CN tidak muncul di commercial rate" (12 Sep 2026). Substring-match
# fallback di find_country() TIDAK menangkap kasus ini ("cn" bukan substring
# dari "china"), jadi butuh alias eksplisit.
COUNTRY_CODE_ALIASES = {
    "cn": "china",
}


def _normalize_country_key(name):
    key = name.strip().lower()
    return COUNTRY_CODE_ALIASES.get(key, key)


def find_country(name):
    key = _normalize_country_key(name)
    if key in ZONE_INDEX:
        return ZONE_INDEX[key]
    matches = [v for k, v in ZONE_INDEX.items() if key in k]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(m["display_name"] for m in matches)
        raise FedExRateError(f"'{name}' ambigu, cocok dengan beberapa negara: {names}")
    raise FedExRateError(f"Negara '{name}' tidak ditemukan di Zone Index.")


def get_zone(country, direction, service, postal_code=None):
    c = find_country(country)
    zone = c[direction][service]
    if c["display_name"] == "China" and postal_code:
        is_south, _ = resolve_china_zone(postal_code)
        if is_south:
            zone = "B"
    return zone


# =============================================================================
# COMMERCIAL ZONES (Zone 20-huruf, dari Rate_FDX_Exsis_Export/Import.xls)
# =============================================================================
COMMERCIAL_ZONES = ['B', 'C', 'D', 'E', 'F', 'G', 'K', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'U', 'V', 'W', 'X', 'Y', 'Z']

_ZONE_CSV_COMMERCIAL_EXPORT = """
Afghanistan,G,,G,
Albania,G,G,G,G
Algeria,G,G,G,G
American Samoa,G,G,G,G
Andorra,E,,E,
Angola,G,G,G,
Anguilla,G,,G,
Antigua & Barbuda,G,,G,
Argentina,G,G,G,G
Armenia,G,G,G,
Aruba,G,,G,
Australia,U,U,U,U
Austria,E,E,E,E
Azerbaijan,G,G,G,
Bahama,G,,G,
Bahrain,F,F,F,F
Bangladesh,F,F,F,F
Barbados,G,,G,
Belarus,G,G,G,
Belgium,M,M,M,M
Belize,G,,G,
Benin,G,,G,
Bermuda,G,,G,
Bhutan,G,,G,
Bolivia,G,G,G,
Bonaire,G,G,G,
Bosnia-Herzegovina,G,G,G,G
Botswana,G,,G,
Brazil,G,G,G,G
British Virgin Islands,G,,G,
Brunei,B,B,B,B
Bulgaria,E,E,E,E
Burkina Faso,G,,G,
Burundi,G,,G,
Cambodia,B,B,B,B
Cameroon,G,G,G,
Canada,D,D,D,D
Cape Verde,G,,G,
Cayman Islands,G,,G,
Chad,G,,G,
Chile,G,G,G,G
China (Excluding China South),W,W,W,W
China (South),K,K,K,K
Colombia,G,G,G,G
Congo,G,,G,
Cook Islands,G,G,G,G
Costa Rica,G,G,G,
Croatia,E,E,E,E
Curacao,G,G,G,
Cyprus,E,E,E,E
Czech Republic,E,E,E,E
Côte D'ivoire (Ivory Coast),G,,G,
Democratic Republic of the Congo,G,,G,
Denmark,E,E,E,E
Djibouti,G,,G,
Dominica,G,,G,
Dominican Republic,G,G,G,G
East Timor,G,G,G,G
Ecuador,G,G,G,
Egypt,F,F,F,F
El Salvador,G,G,G,
Eritrea,G,,G,
Estonia,E,E,E,E
Ethiopia,G,G,G,G
Faeroe Islands,E,,E,
Fiji,G,G,G,G
Finland,E,E,E,E
France,M,M,M,M
French Guiana,G,,G,
French Polynesia,G,G,G,G
Gabon,G,G,G,
Gambia,G,,G,
Georgia,G,G,G,G
Germany,M,M,M,M
Ghana,G,G,G,G
Gibraltar,E,,E,
Greece,E,E,E,E
Greenland,E,,E,
Grenada,G,G,G,
Guadeloupe,G,G,G,
Guam,G,G,G,G
Guatemala,G,G,G,
Guinea,G,,G,
Guyana,G,G,G,
Haiti,G,,G,
Honduras,G,G,G,
Hong Kong SAR, China,V,V,V,V
Hungary,E,E,E,E
Iceland,E,E,E,
India,O,O,O,O
Iraq,G,G,G,
Ireland,E,E,E,E
Israel,E,E,E,E
Italy,M,M,M,M
Jamaica,G,,G,
Japan,P,P,P,P
Jordan,F,F,F,
Kazakhstan,G,,G,
Kenya,G,G,G,G
Kuwait,F,F,F,F
Kyrgyzstan,G,,G,
Laos,B,B,B,B
Latvia,E,E,E,E
Lebanon,F,F,F,F
Lesotho,G,,G,
Liberia,G,G,G,
Libya,G,G,G,G
Liechtenstein,E,E,E,E
Lithuania,E,E,E,E
Luxembourg,E,E,E,E
Macau SAR, China,B,B,B,B
Macedonia,G,G,G,G
Madagascar,G,G,G,
Malawi,G,,G,
Malaysia,Q,Q,Q,Q
Maldives,G,,G,
Mali,G,,G,
Malta,E,E,E,E
Marshall Islands,G,G,G,G
Martinique,G,G,G,
Mauritania,G,,G,
Mauritius,G,G,G,G
Mexico,D,D,D,D
Micronesia,G,G,G,G
Monaco,E,E,E,E
Mongolia,B,B,B,B
Monserrat,G,,G,
Montenegro,G,G,G,G
Morocco,G,G,G,
Mozambique,G,G,G,G
Namibia,G,G,G,
Nepal,G,G,G,
Netherlands,M,M,M,M
Netherlands Antilles,G,G,G,
New Caledonia,G,G,G,G
New Zealand,C,C,C,C
Nicaragua,G,,G,
Niger,G,,G,
Nigeria,G,G,G,G
Northern Mariana Islands,G,G,G,G
Norway,E,E,E,E
Oman,F,F,F,F
Pakistan,F,F,F,F
Palau,G,G,G,G
Palestine Autonomous,G,,G,
Panama,G,G,G,G
Papua New Guinea,G,G,G,G
Paraguay,G,G,G,
Peru,G,G,G,G
Phillipines,S,S,S,S
Poland,E,E,E,E
Portugal,E,E,E,E
Puerto Rico,D,D,D,D
Qatar,F,F,F,F
Republic of Moldova,G,G,G,G
Romania,E,E,E,E
Russian Federation,E,E,E,E
Rwanda,G,,G,
Réunion,G,G,G,
Saint Lucia,G,,G,
Samoa,G,G,G,G
Saudi Arabia,F,F,F,F
Senegal,G,G,G,
Serbia,E,E,E,E
Seychelles,G,G,G,
Singapore,Y,Y,Y,Y
Slovakia,E,E,E,E
Slovenia,E,E,E,E
South Africa,F,F,F,F
South Korea,Z,Z,Z,Z
Spain,M,M,M,M
Sri Lanka,F,F,F,F
St. Kitts and Nevis,G,,G,
St. Maarten,G,G,G,
St. Martin,G,G,G,
St. Vincent & the Grenadines,G,,G,
Suriname,G,,G,
Swaziland,G,,G,
Sweden,E,E,E,E
Switzerland,E,E,E,E
Syrian Arab Republic,G,,G,
Taiwan,X,X,X,X
Thailand,R,R,R,R
Togo,G,,G,
Tonga,G,G,G,G
Trinidad & Tobago,G,G,G,
Tunisia,G,G,G,G
Turkey,E,E,E,E
Turks & Caicos Islands,G,,G,
U.S.A.,D,D,D,D
U.S. Virgin Islands,G,,G,
Uganda,G,G,G,
Ukraine,E,E,E,E
United Arab Emirates,F,F,F,F
United Kingdom (Great Britain),M,M,M,M
United Republic of Tanzania,G,G,G,G
Uruguay,G,G,G,
Uzbekistan,G,,G,
Vanuatu,G,G,G,G
Venezuela,G,G,G,G
Vietnam,N,N,N,N
Wallis & Futuna,G,G,G,G
Yemen,G,,G,
Zambia,G,,G,
Zimbabwe,G,,G,
"""

_ZONE_CSV_COMMERCIAL_IMPORT = """
Afghanistan,G,,G,
Albania,G,G,G,G
Algeria,G,,G,
American Samoa,G,,G,
Andorra,E,,E,
Angola,G,,G,
Anguilla,G,G,G,G
Antigua & Barbuda,G,G,G,G
Argentina,G,G,G,G
Armenia,G,G,G,
Aruba,G,G,G,G
Australia,U,U,U,U
Austria,E,E,E,E
Azerbaijan,G,G,G,
Bahama,G,G,G,G
Bahrain,F,F,F,F
Bangladesh,F,F,F,F
Barbados,G,G,G,G
Belarus,G,,G,
Belgium,M,M,M,M
Belize,G,G,G,G
Benin,G,,G,
Bermuda,G,G,G,G
Bhutan,G,,G,
Bolivia,G,G,G,G
Bonaire,G,G,G,G
Bosnia-Herzegovina,G,G,G,G
Botswana,G,,G,
Brazil,G,G,G,G
British Virgin Islands,G,G,G,G
Brunei,B,,B,
Bulgaria,E,E,E,E
Burkina Faso,G,,G,
Burundi,G,,G,
Cambodia,B,B,B,B
Cameroon,G,,G,
Canada,D,D,D,D
Cape Verde,G,,G,
Cayman Islands,G,G,G,G
Chad,G,,G,
Chile,G,G,G,G
China (Excluding China South),W,W,W,W
China (South),K,K,K,K
Colombia,G,G,G,G
Congo,G,,G,
Cook Islands,G,,G,
Costa Rica,G,G,G,G
Croatia,E,E,E,E
Curacao,G,G,G,G
Cyprus,E,,E,
Czech Republic,E,E,E,E
Côte D'ivoire (Ivory Coast),G,,G,
Democratic Republic of the Congo,G,,G,
Denmark,E,E,E,E
Djibouti,G,,G,
Dominica,G,G,G,G
Dominican Republic,G,G,G,G
East Timor,G,,G,
Ecuador,G,G,G,G
Egypt,F,F,F,F
El Salvador,G,G,G,G
Eritrea,G,,G,
Estonia,E,E,E,
Ethiopia,G,,G,
Faeroe Islands,E,,E,
Fiji,G,,G,G
Finland,E,E,E,E
France,M,M,M,M
French Guiana,G,G,G,G
French Polynesia,G,,G,
Gabon,G,,G,
Gambia,G,,G,
Georgia,G,G,G,G
Germany,M,M,M,M
Ghana,G,,G,
Gibraltar,E,,E,
Greece,E,E,E,
Greenland,E,,E,
Grenada,G,G,G,G
Guadeloupe,G,G,G,G
Guam,G,G,G,
Guatemala,G,G,G,G
Guinea,G,,G,
Guyana,G,G,G,G
Haiti,G,G,G,G
Honduras,G,G,G,G
Hong Kong SAR, China,V,V,V,V
Hungary,E,E,E,E
Iceland,E,,E,
India,O,O,O,O
Iraq,G,,G,
Ireland,E,E,E,E
Israel,E,E,E,E
Italy,M,M,M,M
Jamaica,G,G,G,G
Japan,P,P,P,P
Jordan,F,F,F,F
Kazakhstan,G,,G,
Kenya,G,G,G,G
Kuwait,F,F,F,F
Kyrgyzstan,G,,G,
Laos,B,,B,
Latvia,E,E,E,
Lebanon,F,,F,
Lesotho,G,,G,
Liberia,G,,G,
Libya,G,G,G,G
Liechtenstein,E,,E,
Lithuania,E,E,E,
Luxembourg,E,E,E,E
Macau SAR, China,B,B,B,B
Macedonia,G,G,G,G
Madagascar,G,,G,
Malawi,G,G,G,G
Malaysia,Q,Q,Q,Q
Maldives,G,,G,
Mali,G,,G,
Malta,E,E,E,E
Marshall Islands,G,,G,
Martinique,G,G,G,G
Mauritania,G,,G,
Mauritius,G,,G,
Mexico,D,D,D,D
Micronesia,G,,G,
Monaco,E,,E,
Mongolia,B,,B,
Monserrat,G,G,G,G
Montenegro,G,G,G,G
Morocco,G,,G,
Mozambique,G,G,G,G
Namibia,G,G,G,
Nepal,G,,G,
Netherlands,M,M,M,M
Netherlands Antilles,G,G,G,G
New Caledonia,G,,G,
New Zealand,C,C,C,C
Nicaragua,G,G,G,G
Niger,G,,G,
Nigeria,G,G,G,
Northern Mariana Islands,G,,G,
Norway,E,E,E,E
Oman,F,F,F,
Pakistan,F,,F,
Palau,G,,G,
Palestine Autonomous,G,,G,
Panama,G,G,G,G
Papua New Guinea,G,G,G,G
Paraguay,G,G,G,G
Peru,G,G,G,G
Phillipines,S,S,S,S
Poland,E,E,E,E
Portugal,E,E,E,E
Puerto Rico,D,D,D,D
Qatar,F,,F,
Republic of Moldova,G,G,G,G
Romania,E,E,E,E
Russian Federation,E,,E,
Rwanda,G,,G,
Réunion,G,,G,
Saint Lucia,G,G,G,G
Samoa,G,,G,
Saudi Arabia,F,F,F,F
Senegal,G,,G,
Serbia,E,,E,E
Seychelles,G,,G,
Singapore,Y,Y,Y,Y
Slovakia,E,E,E,E
Slovenia,E,E,E,E
South Africa,F,F,F,F
South Korea,Z,Z,Z,Z
Spain,M,M,M,M
Sri Lanka,F,,F,
St. Kitts and Nevis,G,G,G,G
St. Maarten,G,G,G,G
St. Martin,G,G,G,G
St. Vincent & the Grenadines,G,G,G,G
Suriname,G,,G,
Swaziland,G,,G,
Sweden,E,E,E,E
Switzerland,E,E,E,E
Syrian Arab Republic,G,,G,
Taiwan,X,X,X,X
Thailand,R,R,R,R
Togo,G,,G,
Tonga,G,,G,
Trinidad & Tobago,G,G,G,G
Tunisia,G,G,G,G
Turkey,E,E,E,E
Turks & Caicos Islands,G,G,G,G
U.S.A.,D,D,D,D
U.S. Virgin Islands,G,G,G,G
Uganda,G,,G,
Ukraine,E,E,E,E
United Arab Emirates,F,F,F,F
United Kingdom (Great Britain),M,M,M,M
United Republic of Tanzania,G,,G,
Uruguay,G,G,G,G
Uzbekistan,G,,G,
Vanuatu,G,,G,
Venezuela,G,G,G,G
Vietnam,N,N,N,N
Wallis & Futuna,G,,G,
Yemen,G,,G,
Zambia,G,,G,
Zimbabwe,G,,G,
"""




def _load_zones_commercial(csv_text):
    zones = {}
    for line in csv_text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        name = parts[0]
        ip, ie, ipf, ief = (parts[1] or None, parts[2] or None, parts[3] or None, parts[4] or None)
        zones[name.lower()] = {
            "display_name": name,
            "IP": ip or None,
            "IE": ie or None,
            "IPF": ipf or None,
            "IEF": ief or None,
        }
    return zones


COMMERCIAL_ZONE_INDEX = {
    "export": _load_zones_commercial(_ZONE_CSV_COMMERCIAL_EXPORT),
    "import": _load_zones_commercial(_ZONE_CSV_COMMERCIAL_IMPORT),
}

COMMERCIAL_ALIASES = {
    "grand cayman": "cayman islands",
    "great thatch island": "british virgin islands",
    "great tobago islands": "british virgin islands",
    "jost van dyke islands": "british virgin islands",
    "montserrat": "monserrat",
    "norman island": "british virgin islands",
    "philippines": "phillipines",
    "reunion": "réunion",
    "rota": "northern mariana islands",
    "saipan": "northern mariana islands",
    "tinian": "northern mariana islands",
    "slovak republic": "slovakia",
    "st. christopher": "st. kitts and nevis",
    "st. kitts & nevis": "st. kitts and nevis",
    "st. croix island": "u.s. virgin islands",
    "st. john": "u.s. virgin islands",
    "st. thomas": "u.s. virgin islands",
    "st. lucia": "saint lucia",
    "tahiti": "french polynesia",
    "tortola island": "british virgin islands",
    "union island": "st. vincent & the grenadines",
    "united states (rest of country)": "u.s.a.",
    "united states (western region)": "u.s.a.",
    "usa": "u.s.a.",
    "united states": "u.s.a.",
    "korea": "south korea",
    "ivory coast": "côte d'ivoire (ivory coast)",
    "moldova": "republic of moldova",
    "tanzania": "united republic of tanzania",
    "uae": "united arab emirates",
    "united kingdom": "united kingdom (great britain)",
    "great britain": "united kingdom (great britain)",
    "macedonia": "macedonia",
    "macau": "macau sar, china",
    "hong kong": "hong kong sar, china",
    "congo dem rep of": "democratic republic of the congo",
}

# Negara yang ADA di Zone Index promotional tapi TIDAK punya rate commercial
# (Exsis) sama sekali utk customer ini -> raise error yang jelas kalau
# dipanggil dgn rate_type="commercial", bukan silent fallback ke negara lain.
COMMERCIAL_UNAVAILABLE_COUNTRIES = {
    "canary islands", "channel islands", "norfolk island", "san marino",
    "st. barthelemy", "st. eustatius", "vatican city", "saba",
}


def find_country_commercial(name, direction):
    index = COMMERCIAL_ZONE_INDEX[direction]
    key = name.strip().lower()
    if key in COMMERCIAL_UNAVAILABLE_COUNTRIES:
        raise FedExRateError(
            f"Commercial rate (Exsis) tidak tersedia utk negara '{name}' -> "
            f"pakai rate_type='promotional' saja utk negara ini."
        )
    key = COMMERCIAL_ALIASES.get(key, key)
    if key in index:
        return index[key]
    matches = [v for k, v in index.items() if key in k]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(m["display_name"] for m in matches)
        raise FedExRateError(f"'{name}' ambigu di commercial (Exsis) Zone Index, cocok dgn: {names}")
    raise FedExRateError(
        f"Negara '{name}' tidak ditemukan di commercial (Exsis) Zone Index arah "
        f"'{direction}'. Kemungkinan: (a) ejaan beda dari Zone Index promotional "
        f"-> tambahkan ke COMMERCIAL_ALIASES, atau (b) memang belum ada rate "
        f"commercial utk negara ini -> pakai rate_type='promotional'."
    )


def get_zone_commercial(country, direction, service, postal_code=None):
    """Return (zone_letter, display_name, note) utk rate_type='commercial'.
    China ditangani khusus (sama seperti promotional) krn Zone Index Exsis
    memecah China jadi 2 baris ('China (South)' / 'China (Excluding China
    South)') berdasar kode pos Fujian/Guangdong, BUKAN 1 baris 'China'."""
    name_key = _normalize_country_key(country)
    note = None
    if name_key == "china":
        override_zone, region_label = resolve_china_zone(postal_code)
        label = "china (south)" if override_zone else "china (excluding china south)"
        entry = COMMERCIAL_ZONE_INDEX[direction].get(label)
        if entry is None:
            raise FedExRateError(f"Zone commercial utk '{label}' tidak ditemukan (arah {direction}).")
        if not postal_code:
            note = ("Kode pos China tidak diisi -> commercial rate diasumsikan "
                    "'China (Excluding China South)'. Isi kode pos China kalau "
                    "tujuan/asal di Fujian (350000-369999) / Guangdong "
                    "(510000-529999) supaya otomatis pakai 'China (South)'.")
        else:
            note = f"Kode pos China -> commercial rate pakai '{entry['display_name']}'."
    else:
        entry = find_country_commercial(country, direction)
    zone = entry.get(service)
    if not zone:
        raise FedExRateError(
            f"Service '{service}' tidak tersedia utk negara '{entry['display_name']}' "
            f"di commercial rate (Exsis) arah '{direction}'."
        )
    return zone, entry["display_name"], note


# ---------------------------------------------------------------------------
# 2. RATE TABLES
#    Format dokumen (IP/IE): "weight,A,B,C,D,E,F,G" step 0.5kg dari 0.5 - 20.5
#    Format band (IPF/IEF & >20kg IP/IE): "band_label,min_kg,A,B,C,D,E,F,G"
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Rate tables (format CSV inline, lihat rate_common.parse_*_table)
# ---------------------------------------------------------------------------
