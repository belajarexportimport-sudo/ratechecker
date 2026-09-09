"""
Smoke test — entry point cepat untuk regression test seluruh Rate Engine.

CATATAN: versi lama file ini membandingkan `backend/` terhadap modul lama
`calculator.py` (single-file, pre-migrasi) yang sudah tidak ada di project
ini (migrasinya sudah selesai & sudah diverifikasi manual waktu itu -- lihat
riwayat PRD & AUDIT_UPS_COMMERCIAL.md). Sekarang project sudah punya test
suite proper di folder tests/ (FedEx, UPS, Comparison, API) dengan golden
value yang sudah dicocokkan ke sumber rate mentahnya masing-masing.

Cara jalankan (sama seperti sebelumnya):
    python smoke_test.py

Atau langsung:
    python -m unittest discover -s tests -p "test_*.py" -v
"""
import sys
import subprocess

if __name__ == "__main__":
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]
    )
    sys.exit(result.returncode)
