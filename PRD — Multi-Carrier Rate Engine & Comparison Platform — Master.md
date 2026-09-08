# PRD — Multi-Carrier Rate Engine & Comparison Platform

**Status:** Master PRD — Ready for Implementation  
**Tanggal:** 7 September 2026  
**Produk:** Multi-Carrier Shipping Rate Engine  
**Basis:** Evolusi dari existing FedEx Calculator

---

# 1. Latar Belakang

Project ini awalnya merupakan calculator shipping khusus **FedEx** yang berjalan menggunakan Python, Streamlit, dan standalone `index.html`.

Existing engine sudah memiliki logic FedEx yang cukup kompleks, termasuk:

- Publish Rate
- Commercial / Exsis Rate
- Zone calculation
- Country lookup
- ODA / OPA
- Demand Surcharge
- Non-Standard Fees
- Special Handling Fees
- Dimensional Weight
- Chargeable Weight
- CWT
- Service auto-switch
- Discount

Existing FedEx Commercial sudah selesai di backend Python.

Project selanjutnya tidak lagi diposisikan hanya sebagai "FedEx Calculator", tetapi dikembangkan menjadi:

> **Multi-Carrier Rate Engine**

yang nantinya dapat menghitung dan membandingkan rate dari beberapa carrier seperti:

- FedEx
- UPS
- DHL (potensial / future)

Tujuan akhirnya adalah memiliki **rate calculation engine yang independen dari frontend**, sehingga engine dapat digunakan melalui:

- Python library
- Streamlit
- Standalone HTML/JavaScript
- REST API
- Produk SaaS / aplikasi lain di masa depan

PRD ini menjadi **single source of truth** untuk implementasi teknis project.

---

# 2. Tujuan Project

## 2.1 Tujuan Utama

Membangun rate engine yang:

1. Akurat.
2. Modular.
3. Mudah ditambahkan carrier baru.
4. Tidak mencampur logic antar carrier.
5. Dapat menghasilkan breakdown biaya.
6. Dapat membandingkan beberapa rate.
7. Dapat digunakan oleh frontend melalui API di tahap berikutnya.
8. Tetap mempertahankan behavior existing FedEx 100%.

---

# 3. Prinsip Arsitektur — NON-NEGOTIABLE

## 3.1 Carrier Isolation

Setiap carrier mempunyai "dunia" sendiri.

Contoh:

```text
carriers/
├── fedex/
└── ups/
```

FedEx memiliki:

- zone
- rate table
- service
- surcharge
- dimensional rule
- weight breakpoint
- commercial rule
- discount rule

UPS memiliki struktur sendiri.

**Jangan mengasumsikan logic FedEx dapat digunakan UPS.**

---

## 3.2 Jangan Membuat Universal Carrier Formula

DILARANG membuat satu calculator besar seperti:

```python
if carrier == "fedex":
    ...
elif carrier == "ups":
    ...
elif carrier == "dhl":
    ...
```

dengan seluruh logic carrier berada dalam satu file.

Percabangan carrier hanya boleh dilakukan pada **routing / registry layer**.

Contoh:

```python
CARRIER_REGISTRY = {
    "fedex": fedex_calculator,
    "ups": ups_calculator,
}
```

Setelah request diarahkan ke carrier tertentu, seluruh calculation dilakukan oleh carrier tersebut.

---

# 4. Shared Contract vs Carrier Logic

Yang boleh/shared:

```text
RateRequest
RateResult
Comparison Result
API contract
```

Yang TIDAK boleh dipaksa menjadi shared:

```text
FedEx zone logic
UPS zone logic
FedEx surcharge
UPS surcharge
FedEx discount rule
UPS discount rule
FedEx service logic
UPS service logic
```

Prinsipnya:

> **Uniform contract, NOT uniform calculation logic.**

---

# 5. Scope Project

## Phase 1 — FedEx Foundation

Carrier:

```text
FedEx
```

Rate type:

```text
Publish
Commercial
```

Fitur:

- Existing FedEx calculator
- FedEx Commercial
- FedEx Publish
- Publish vs Commercial comparison
- Regression testing
- Refactor architecture

---

## Phase 2 — UPS

Carrier:

```text
FedEx
UPS
```

Fitur:

- UPS Publish
- UPS Commercial jika data tersedia
- UPS zone
- UPS service
- UPS surcharge
- UPS dimensional rules
- UPS discount
- Cross-carrier comparison

---

## Phase 3 — API

Engine diakses melalui REST API.

Contoh:

```text
POST /quote
POST /compare
```

Frontend tidak lagi menjalankan calculation logic sendiri.

---

## Phase 4 — Future

Potential:

```text
DHL
Other carriers
Multi-tenant
Authentication
Billing
Public API
SaaS dashboard
Usage tracking
```

Fitur-fitur tersebut **belum menjadi scope implementasi sekarang**.

---

# 6. Arsitektur Target

```text
Frontend
    │
    ▼
FastAPI
    │
    ▼
Rate Engine
    │
    ├── FedEx Engine
    │     ├── Publish
    │     ├── Commercial
    │     ├── Zones
    │     ├── Surcharges
    │     └── Rules
    │
    └── UPS Engine
          ├── Publish
          ├── Commercial
          ├── Zones
          ├── Surcharges
          └── Rules
    │
    ▼
RateResult
    │
    ▼
Comparison Engine
    │
    ▼
Frontend
```

---

# 7. Target Folder Structure

Struktur final yang direkomendasikan:

```text
backend/
│
├── core/
│   └── schemas.py
│
├── carriers/
│   ├── __init__.py
│   │
│   ├── fedex/
│   │   ├── __init__.py
│   │   ├── rates/
│   │   │   ├── __init__.py
│   │   │   ├── publish.py
│   │   │   └── commercial.py
│   │   │
│   │   ├── zones.py
│   │   ├── surcharges.py
│   │   ├── rules.py
│   │   └── calculator.py
│   │
│   └── ups/
│       ├── __init__.py
│       ├── rates/
│       │   ├── __init__.py
│       │   ├── publish.py
│       │   └── commercial.py
│       │
│       ├── zones.py
│       ├── surcharges.py
│       ├── rules.py
│       └── calculator.py
│
├── pricing/
│   ├── router.py
│   └── discounts.py
│
├── comparison/
│   ├── compare.py
│   └── service_mapping.py
│
├── api/
│   └── routes.py
│
└── tests/
    ├── fedex/
    ├── ups/
    └── comparison/
```

Catatan:

Struktur folder boleh disesuaikan selama prinsip isolation tetap dipertahankan.

---

# 8. `core/schemas.py`

`core/schemas.py` hanya berisi **shared data contract**.

## 8.1 WAJIB: Tidak Menggunakan Pydantic

Project ini **TIDAK menggunakan Pydantic**.

Jangan menggunakan:

```python
from pydantic import BaseModel
```

atau:

```python
class RateRequest(BaseModel):
    ...
```

Shared contract menggunakan Python standard library:

```python
from dataclasses import dataclass, field
from typing import Optional
```

Tujuan:

- dependency lebih ringan
- core engine tidak bergantung kepada framework API
- engine dapat digunakan sebagai Python library
- API layer tetap hanya sebagai transport layer

---

# 9. `RateRequest`

Contoh contract:

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateRequest:
    carrier: str
    rate_type: str
    service: str

    direction: str

    origin_country: str
    destination_country: str

    weight_kg: float

    dimensions_cm: Optional[tuple[float, float, float]] = None

    packages: int = 1

    postal_code_origin: Optional[str] = None
    postal_code_destination: Optional[str] = None

    discount_pct: Optional[float] = None

    extra: dict = field(default_factory=dict)
```

`extra` digunakan untuk data yang memang spesifik carrier.

Contoh:

```python
extra={
    "leg_type": "IP",
    "pieces": 2,
}
```

Jangan memasukkan field FedEx-specific ke shared schema hanya agar UPS terlihat sama.

---

# 10. `RateResult`

Shared output contract:

```python
@dataclass
class RateResult:
    carrier: str
    rate_type: str
    service: str

    zone: str

    base_price: float

    surcharges: dict[str, float] = field(default_factory=dict)

    discount: float = 0

    total: float = 0

    currency: str = "IDR"

    notes: list[str] = field(default_factory=list)

    extra: dict = field(default_factory=dict)
```

Contoh:

```text
carrier: FedEx
rate_type: Commercial
service: IP
zone: 4

base_price: 1,250,000

surcharges:
    fuel: 150,000
    oda: 75,000
    demand: 50,000

discount: -125,000

total: 1,400,000
```

---

# 11. Aturan `RateResult`

`RateResult` harus selalu dapat menjelaskan:

```text
Carrier
Rate Type
Service
Zone
Base Rate
Surcharge Breakdown
Discount
Final Total
Currency
Notes
```

Jika carrier memiliki informasi tambahan seperti:

```text
chargeable_weight
dimensional_weight
actual_weight
leg_type
cwt
```

masukkan ke:

```python
extra={}
```

---

# 12. FedEx Engine

FedEx engine adalah migrasi dari existing code.

**Jangan rewrite dari nol.**

Existing logic yang harus dipertahankan mencakup:

- `rates.py`
- `calculator.py`
- `oda_opa.py`
- `surcharges.py`
- `nonstandard_fees.py`
- `special_handling_fees.py`
- logic Commercial
- CWT
- DIM weight
- service switching
- zone lookup
- country alias

Behavior existing harus dipertahankan.

---

# 13. FedEx Rate Structure

FedEx rate type:

```text
Publish
Commercial
```

Rate tables harus tetap terpisah.

Contoh:

```text
fedex/rates/publish.py
fedex/rates/commercial.py
```

Jangan membuat satu tabel universal yang memaksakan Publish dan Commercial menjadi sama.

---

# 14. FedEx Zones

Semua zone logic FedEx berada di:

```text
carriers/fedex/zones.py
```

Termasuk:

- country lookup
- country alias
- Publish zone
- Commercial zone
- zone index
- unavailable country handling

Zone logic tidak boleh diletakkan di comparison layer.

---

# 15. FedEx Rules

Logic seperti:

- minimum weight
- dimensional divisor
- CWT
- chargeable weight
- service auto-switch
- IP → IPF
- IE → IEF
- weight breakpoint

ditempatkan di:

```text
carriers/fedex/rules.py
```

Tujuan pemisahan:

```text
rates = harga
zones = lokasi
rules = aturan
surcharges = biaya tambahan
calculator = orchestrator
```

---

# 16. FedEx Surcharges

FedEx surcharge logic ditempatkan di:

```text
carriers/fedex/surcharges.py
```

Meliputi existing:

- ODA
- OPA
- Demand Surcharge
- Non-Standard Fees
- Special Handling Fees
- surcharge lainnya yang sudah ada

Jika file menjadi terlalu besar, boleh dipecah menjadi submodule:

```text
fedex/surcharges/
├── oda_opa.py
├── demand.py
├── nonstandard.py
└── special_handling.py
```

Namun jangan mengubah calculation behavior hanya demi refactor.

---

# 17. FedEx Calculator

File:

```text
carriers/fedex/calculator.py
```

bertindak sebagai orchestrator.

Konsep:

```text
RateRequest
    ↓
Validate / normalize
    ↓
Determine zone
    ↓
Determine chargeable weight
    ↓
Determine service/rule
    ↓
Get base rate
    ↓
Calculate surcharges
    ↓
Apply discount
    ↓
Return RateResult
```

Calculator tidak boleh menjadi tempat seluruh data dan seluruh formula menumpuk.

---

# 18. UPS Engine

UPS dibuat sebagai engine independen:

```text
carriers/ups/
```

UPS memiliki:

```text
rates
zones
rules
surcharges
calculator
```

Jangan copy-paste FedEx lalu hanya mengganti nama.

Struktur boleh sama, tetapi isi logic mengikuti aturan UPS.

---

# 19. UPS Rate Data

UPS belum boleh dibuat berdasarkan asumsi.

Sebelum coding UPS:

1. Kumpulkan rate card resmi.
2. Identifikasi zone.
3. Identifikasi service.
4. Identifikasi weight breakpoint.
5. Identifikasi surcharge.
6. Identifikasi dimensional rule.
7. Identifikasi discount/commercial rule.
8. Validasi sample calculation.

Jika data belum tersedia:

> **Jangan membuat angka dummy yang dianggap sebagai production rate.**

Dummy data hanya boleh digunakan untuk structural/unit testing dan harus diberi label jelas.

---

# 20. Pricing Layer

Pricing layer **bukan tempat calculation logic carrier**.

Fungsi utamanya adalah routing.

Contoh:

```python
CARRIER_REGISTRY = {
    "fedex": fedex_calculator,
    "ups": ups_calculator,
}
```

Kemudian:

```python
def calculate(request):
    calculator = CARRIER_REGISTRY[request.carrier]
    return calculator.calculate(request)
```

---

# 21. Discount

Discount tidak boleh otomatis dianggap universal.

Jika FedEx:

```text
discount = base_rate × percentage
```

dan UPS mempunyai struktur berbeda, jangan dipaksakan ke:

```text
pricing/discounts.py
```

Dalam kondisi tersebut discount harus berada di carrier masing-masing.

`pricing/discounts.py` hanya boleh berisi utility yang benar-benar identical dan reusable.

---

# 22. Comparison Engine

Comparison adalah layer terpisah dari carrier calculation.

File:

```text
comparison/compare.py
```

Tugasnya:

1. Menerima request dasar.
2. Menentukan kombinasi carrier/rate_type.
3. Memanggil engine masing-masing.
4. Mengumpulkan `RateResult`.
5. Mengurutkan hasil.
6. Menghitung perbedaan.
7. Menghasilkan comparison result.

Comparison **tidak menghitung ulang rate carrier**.

---

# 23. FedEx Comparison — Phase 1

Input:

```text
1 RateRequest
```

Kemudian:

```text
FedEx Publish
FedEx Commercial
```

Contoh:

```text
                 Publish      Commercial
-----------------------------------------
Base Rate        Rp...        Rp...
Fuel             Rp...        Rp...
ODA              Rp...        Rp...
Demand           Rp...        Rp...
Discount         Rp...        Rp...
-----------------------------------------
TOTAL            Rp...        Rp...
```

Tambahkan:

```text
Difference
Difference %
```

Jika salah satu rate tidak tersedia:

```text
N/A
Reason: ...
```

Jangan membuat seluruh comparison gagal.

---

# 24. Cross-Carrier Comparison — Phase 2

Contoh:

```text
FedEx Publish
FedEx Commercial
UPS Publish
UPS Commercial
```

Comparison engine tidak boleh menganggap:

```text
FedEx IP == UPS Service X
```

secara otomatis.

Harus ada mapping eksplisit:

```text
comparison/service_mapping.py
```

Contoh konsep:

```python
SERVICE_MAPPING = {
    "fedex:IP": {
        "ups": "TBD"
    }
}
```

Mapping hanya boleh diisi setelah service equivalence ditentukan berdasarkan kebutuhan bisnis/data yang valid.

---

# 25. Service Equivalence

Perbandingan carrier harus membedakan:

### Price comparison

```text
Rate A vs Rate B
```

dengan:

### Service-equivalent comparison

```text
Service A ≈ Service B
```

Jangan mengklaim dua service equivalent hanya karena namanya sama-sama "Express".

Jika equivalence belum diketahui:

```text
Service equivalence: TBD
```

atau tampilkan sebagai perbandingan non-equivalent.

---

# 26. API Layer

API akan menggunakan:

```text
FastAPI
```

Tetapi FastAPI hanya menjadi **transport layer**.

Core engine tidak boleh bergantung kepada FastAPI.

Arsitektur:

```text
HTTP Request
    ↓
API Route
    ↓
Convert input → RateRequest
    ↓
Rate Engine
    ↓
RateResult
    ↓
Serialize response
```

---

# 27. Pydantic — DILARANG

Project ini secara eksplisit:

> **TIDAK MENGGUNAKAN PYDANTIC.**

Jangan menambahkan Pydantic hanya karena FastAPI secara default sering digunakan bersama Pydantic.

Core data contract tetap:

```text
Python dataclass
```

API layer harus menangani parsing/validation input secara manual atau menggunakan utility standard Python yang ringan.

Contoh:

```python
RateRequest(...)
```

bukan:

```python
RateRequest(BaseModel)
```

---

# 28. API Endpoint

## `POST /quote`

Input:

```text
RateRequest
```

Output:

```text
RateResult
```

Contoh konsep:

```text
POST /quote

{
    "carrier": "fedex",
    "rate_type": "commercial",
    "service": "IP",
    ...
}
```

Response:

```text
{
    "carrier": "fedex",
    "rate_type": "commercial",
    "service": "IP",
    "zone": "4",
    "base_price": ...,
    "surcharges": {...},
    "discount": ...,
    "total": ...
}
```

---

# 29. `POST /compare`

Input:

```text
Base shipment information
+
requested carrier/rate combinations
```

Contoh:

```text
FedEx Publish
FedEx Commercial
UPS Publish
```

Output:

```text
RateResult[]
+
comparison summary
```

---

# 30. Frontend Architecture

Existing:

```text
index.html
```

boleh tetap dipertahankan selama migration.

Namun target architecture:

```text
index.html
      ↓
fetch()
      ↓
FastAPI
      ↓
Rate Engine
```

Frontend **tidak boleh memiliki duplicate calculation logic**.

Dilarang mempertahankan:

```javascript
function calculateFedExRate() {
    // duplicate Python logic
}
```

setelah API engine sudah menjadi source of truth.

Frontend hanya:

```text
Collect Input
↓
Send Request
↓
Receive Result
↓
Render Result
```

---

# 31. Streamlit

Streamlit tetap dapat digunakan sebagai internal UI.

Arsitektur:

```text
Streamlit
    ↓
Rate Engine
```

bukan:

```text
Streamlit
    ↓
copy-paste calculation logic
```

Dengan demikian Streamlit dan API menggunakan engine yang sama.

---

# 32. Migration Existing FedEx

Migration bukan rewrite.

Mapping:

| Existing | Target |
|---|---|
| `rates.py` | `carriers/fedex/rates/` |
| zone logic | `carriers/fedex/zones.py` |
| `oda_opa.py` | `carriers/fedex/surcharges/` |
| `surcharges.py` | `carriers/fedex/surcharges/` |
| `nonstandard_fees.py` | `carriers/fedex/surcharges/` |
| `special_handling_fees.py` | `carriers/fedex/surcharges/` |
| CWT logic | `carriers/fedex/rules.py` |
| DIM logic | `carriers/fedex/rules.py` |
| Service switching | `carriers/fedex/rules.py` |
| `calculator.py` | `carriers/fedex/calculator.py` |

---

# 33. Regression Test — WAJIB

Migration dianggap berhasil hanya jika:

```text
Old FedEx Engine
        VS
New FedEx Engine
```

menghasilkan hasil yang sama.

Minimal test:

```text
Base Rate
Zone
Chargeable Weight
CWT
Fuel
ODA
OPA
Demand
Non-Standard
Special Handling
Discount
Total
```

Target:

> **Behavior harus identik 100% untuk seluruh test case existing yang sudah tervalidasi.**

Jangan melakukan refactor sekaligus mengubah business logic tanpa alasan dan test.

---

# 34. Testing Strategy

Testing dibagi:

```text
Unit Test
Integration Test
Regression Test
Comparison Test
API Test
```

## Unit Test

Menguji:

```text
zone lookup
weight calculation
DIM
CWT
surcharge
discount
```

secara terpisah.

## Integration Test

Menguji:

```text
RateRequest
→ Calculator
→ RateResult
```

## Regression Test

Membandingkan engine lama dan engine baru.

## Comparison Test

Menguji:

```text
Publish vs Commercial
FedEx vs UPS
```

## API Test

Menguji:

```text
POST /quote
POST /compare
```

---

# 35. Error Handling

Engine tidak boleh menghasilkan error yang tidak informatif.

Contoh:

```text
Unsupported carrier
Unsupported rate type
Unsupported service
Country not found
Zone unavailable
Rate unavailable
Invalid weight
Invalid dimensions
```

Error harus dapat dibedakan antara:

```text
invalid input
```

dan:

```text
rate genuinely unavailable
```

---

# 36. Rate Unavailable

Jika carrier/rate tidak tersedia untuk kondisi tertentu, jangan menganggap sebagai system failure.

Contoh:

```text
FedEx Commercial
Status: unavailable

Reason:
Commercial rate is not available for destination country.
```

Comparison tetap dapat berjalan untuk carrier/rate lain.

---

# 37. Currency

`RateResult` memiliki:

```python
currency: str
```

Default existing:

```text
IDR
```

Namun jangan hard-code IDR di seluruh calculation logic.

Future engine dapat mendukung currency berbeda.

---

# 38. Precision & Rounding

Rounding harus ditentukan secara konsisten.

Jangan melakukan rounding sembarangan pada setiap intermediate calculation.

Prinsip:

```text
Calculate
↓
Apply required business rounding
↓
Final total
```

Existing FedEx behavior menjadi reference utama.

Jika UPS memiliki aturan rounding berbeda:

```text
FedEx rounding → FedEx rules
UPS rounding → UPS rules
```

---

# 39. Logging / Debugging

Untuk debugging calculation, engine sebaiknya dapat memberikan informasi seperti:

```text
service
zone
actual weight
dimensional weight
chargeable weight
base rate
surcharges
discount
final total
```

Tetapi informasi debug tidak boleh mengubah calculation result.

---

# 40. Non-Goals

Untuk saat ini TIDAK termasuk:

- SaaS billing
- subscription
- payment gateway
- multi-tenant authentication
- customer management
- user management
- public API monetization
- dashboard SaaS baru
- full frontend redesign
- automatic rate-card scraping
- automatic carrier account integration

Semua dapat menjadi PRD terpisah di masa depan.

---

# 41. Known Unknowns

## UPS

Belum tersedia:

- UPS rate card
- UPS zone
- UPS surcharge
- UPS commercial structure
- UPS discount structure
- UPS service mapping

Tidak boleh mengarang data tersebut.

---

## DHL

DHL belum masuk implementasi.

Hanya disiapkan agar architecture tidak menghambat penambahan carrier baru.

---

# 42. Definition of Done

Phase 1 dianggap selesai jika:

- [ ] `core/schemas.py` selesai.
- [ ] Tidak ada Pydantic.
- [ ] `RateRequest` menggunakan dataclass.
- [ ] `RateResult` menggunakan dataclass.
- [ ] FedEx berhasil dimigrasikan.
- [ ] Existing FedEx calculation tetap identik.
- [ ] Regression test lulus.
- [ ] FedEx Publish bekerja.
- [ ] FedEx Commercial bekerja.
- [ ] FedEx Publish vs Commercial comparison bekerja.
- [ ] Existing Streamlit tetap bekerja.
- [ ] Existing frontend tidak rusak.
- [ ] Tidak ada duplicate calculation logic yang tidak diperlukan.

---

# 43. Urutan Implementasi

Implementasi HARUS dilakukan bertahap.

## Step 1 — Freeze Existing Behavior

Jangan ubah business logic.

Buat baseline test dari existing FedEx calculator.

---

## Step 2 — Create Core Contract

Buat:

```text
backend/core/schemas.py
```

menggunakan dataclass.

**Tidak menggunakan Pydantic.**

---

## Step 3 — Migrate FedEx

Pindahkan logic existing ke:

```text
backend/carriers/fedex/
```

Jangan rewrite.

---

## Step 4 — Regression Test

Bandingkan:

```text
old result
vs
new result
```

Semua harus identik.

---

## Step 5 — Comparison FedEx

Implementasikan:

```text
FedEx Publish
vs
FedEx Commercial
```

---

## Step 6 — Validate Comparison

Pastikan comparison tidak mengetahui detail internal FedEx.

Comparison hanya menerima:

```text
RateResult
```

---

## Step 7 — Collect UPS Data

Sebelum coding UPS:

```text
Rate
Zone
Service
Surcharge
Weight Break
DIM
Discount
```

harus dikumpulkan dan divalidasi.

---

## Step 8 — Build UPS Engine

Implementasikan UPS sebagai engine independen.

---

## Step 9 — Cross-Carrier Comparison

Implementasikan:

```text
FedEx
vs
UPS
```

dengan explicit service mapping.

---

## Step 10 — FastAPI

Setelah engine stabil:

```text
POST /quote
POST /compare
```

API menggunakan engine yang sama.

---

## Step 11 — Frontend API Integration

Frontend:

```text
index.html
    ↓
fetch API
    ↓
Rate Engine
```

Tidak ada lagi duplicate calculation formula di frontend.

---

# 44. Instruksi Khusus untuk Claude / Antigravity

Agent yang mengerjakan project ini WAJIB mengikuti aturan berikut:

### Rule 1

**Jangan rewrite existing FedEx calculation logic tanpa alasan yang jelas.**

### Rule 2

**Jangan membuat universal calculation formula untuk semua carrier.**

### Rule 3

**Jangan mencampur FedEx logic dengan UPS logic.**

### Rule 4

**Jangan menggunakan Pydantic.**

Gunakan:

```python
@dataclass
```

untuk shared contract.

### Rule 5

Jangan membuat dummy UPS rate lalu menganggapnya sebagai production data.

### Rule 6

Jangan mengubah business logic existing hanya karena sedang melakukan refactor.

### Rule 7

Setiap perubahan calculation harus memiliki test.

### Rule 8

Comparison layer tidak boleh menghitung ulang carrier rate.

### Rule 9

Frontend bukan source of truth untuk calculation.

### Rule 10

Python Rate Engine adalah **single source of truth** untuk calculation.

---

# 45. Source of Truth

Architecture final:

```text
                    ┌───────────────┐
                    │   Frontend    │
                    │ index.html    │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   FastAPI     │
                    │ API Layer     │
                    └───────┬───────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │   Rate Engine     │
                  │ Python            │
                  └─────────┬─────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
       ┌─────────────┐             ┌─────────────┐
       │   FedEx     │             │     UPS     │
       │    Engine   │             │    Engine   │
       └──────┬──────┘             └──────┬──────┘
              │                           │
              └─────────────┬─────────────┘
                            ▼
                     ┌─────────────┐
                     │ RateResult  │
                     └──────┬──────┘
                            ▼
                     ┌─────────────┐
                     │ Comparison  │
                     └─────────────┘
```

---

# 46. Final Architectural Decision

Keputusan final untuk project ini:

| Area | Decision |
|---|---|
| Core language | Python |
| Core engine | Python Rate Engine |
| Shared contract | Python `dataclass` |
| Validation | Manual / standard Python |
| Pydantic | **TIDAK DIGUNAKAN** |
| API | FastAPI |
| Frontend | Existing HTML/JS |
| Internal UI | Streamlit |
| Carrier architecture | Independent |
| FedEx | Existing logic migrated |
| UPS | Independent engine |
| Comparison | Separate layer |
| API | Transport layer only |
| Frontend calculation | Tidak menjadi source of truth |
| Future DHL | Supported architecturally |
| SaaS | Future phase |

---

# 47. Prinsip Besar Project

Project ini harus selalu mengikuti prinsip:

> **One Engine Contract, Multiple Independent Carrier Engines.**

atau:

```text
Shared interface
≠
Shared business logic
```

FedEx tetap FedEx.

UPS tetap UPS.

DHL nanti tetap DHL.

Yang menyatukan mereka hanyalah:

```text
RateRequest
RateResult
Comparison
API
```

Dengan architecture ini, penambahan carrier baru tidak membutuhkan perubahan besar pada carrier yang sudah stabil.

---

# 48. Referensi Existing Project

Referensi utama:

```text
PRD Calculator FDX.md
```

untuk detail business logic FedEx existing.

Dan:

```text
RINGKASAN_COMMERCIAL_RATE.md
```

untuk implementasi FedEx Commercial yang sudah selesai.

Dokumen tersebut tetap menjadi referensi business logic FedEx dan tidak digantikan oleh PRD multi-carrier ini.