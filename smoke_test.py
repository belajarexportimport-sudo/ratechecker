"""
Smoke test — verifikasi engine baru menghasilkan hasil yang sama
dengan engine lama untuk beberapa test case dasar.

Cara jalankan:
    python smoke_test.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Engine LAMA ──────────────────────────────────────────────────────────────
import calculator as old_calc

# ─── Engine BARU ──────────────────────────────────────────────────────────────
from backend.core.schemas import RateRequest
from backend.comparison.compare import compare, format_comparison

TEST_CASES = [
    # (label, kwargs_lama, RateRequest_baru)
    {
        "label": "FedEx Publish — Singapore 1kg Export IP",
        "old": dict(service="IP", direction="export", country="Singapore",
                    weight_kg=1.0, rate_type="promotional"),
        "new": RateRequest(carrier="fedex", rate_type="publish",
                           service="IP", direction="export",
                           origin_country="Indonesia",
                           destination_country="Singapore",
                           weight_kg=1.0),
    },
    {
        "label": "FedEx Commercial — Japan 5kg Export IP",
        "old": dict(service="IP", direction="export", country="Japan",
                    weight_kg=5.0, rate_type="commercial"),
        "new": RateRequest(carrier="fedex", rate_type="commercial",
                           service="IP", direction="export",
                           origin_country="Indonesia",
                           destination_country="Japan",
                           weight_kg=5.0),
    },
    {
        "label": "FedEx Publish — USA 10kg Export IE",
        "old": dict(service="IE", direction="export",
                    country="United States (Rest of Country)",
                    weight_kg=10.0, rate_type="promotional"),
        "new": RateRequest(carrier="fedex", rate_type="publish",
                           service="IE", direction="export",
                           origin_country="Indonesia",
                           destination_country="United States (Rest of Country)",
                           weight_kg=10.0),
    },
]

PASS = 0
FAIL = 0

for tc in TEST_CASES:
    label = tc["label"]
    try:
        old_r = old_calc.calculate(**tc["old"])
        old_total = old_r["subtotal_invoice"] or old_r["subtotal"]
        old_zone = old_r["zone"]
        old_base = next(c["amount"] for c in old_r["components"] if c["label"] == "Base rate")
    except Exception as e:
        print(f"[ERROR OLD] {label}: {e}")
        FAIL += 1
        continue

    try:
        from backend.pricing.router import calculate as new_calc
        new_r = new_calc(tc["new"])
        new_total = new_r.total
        new_zone = new_r.zone
        new_base = new_r.base_price
    except Exception as e:
        print(f"[ERROR NEW] {label}: {e}")
        FAIL += 1
        continue

    ok = True
    issues = []
    if abs(old_base - new_base) > 0.01:
        issues.append(f"base_price: old={old_base:,.0f} new={new_base:,.0f}")
        ok = False
    if str(old_zone) != str(new_zone):
        issues.append(f"zone: old={old_zone} new={new_zone}")
        ok = False
    if abs(old_total - new_total) > 1:
        issues.append(f"total: old={old_total:,.0f} new={new_total:,.0f}")
        ok = False

    if ok:
        print(f"[PASS] {label}")
        print(f"       Zone={new_zone}  Base=IDR {new_base:,.0f}  Total=IDR {new_total:,.0f}")
        PASS += 1
    else:
        print(f"[FAIL] {label}")
        for issue in issues:
            print(f"       DIFF: {issue}")
        FAIL += 1

print()
print(f"--- Results: {PASS} PASS / {FAIL} FAIL ---")

# ─── Test Comparison Engine ───────────────────────────────────────────────────
print()
print("=== Comparison Test: FedEx Publish vs Commercial (Singapore 2kg) ===")
req = RateRequest(
    carrier="fedex", rate_type="publish",
    service="IP", direction="export",
    origin_country="Indonesia",
    destination_country="Singapore",
    weight_kg=2.0,
)
cr = compare(req, combinations=[("fedex", "publish"), ("fedex", "commercial")])
print(format_comparison(cr))
