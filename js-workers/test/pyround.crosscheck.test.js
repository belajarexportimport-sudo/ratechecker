// Cross-check pyRound() terhadap output Python round() ASLI (bukan cuma
// asumsi teori "half to even"). Kasus di /home/claude/work/pyround_cases.json
// digenerate langsung dari Python 3 (lihat perintah generate di riwayat
// audit) -- kalau ada mismatch, itu bug di pyRound(), BUKAN di data
// expected-nya.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { pyRound } from "../src/core/pyround.js";

const cases = JSON.parse(
  readFileSync(new URL("./fixtures/pyround_cases.json", import.meta.url))
);

test("pyRound matches Python round() ground truth on all generated cases", () => {
  let mismatches = [];
  for (const c of cases) {
    const got = pyRound(c.value, c.ndigits);
    // Toleransi floating point sangat kecil (1e-9) utk kasus ndigits>0 yg
    // representasi desimalnya tidak eksak di IEEE754 -- BUKAN utk
    // menyembunyikan bug pembulatan half-to-even (itu dites exact match).
    const tol = c.ndigits === 0 ? 0 : 1e-9;
    if (Math.abs(got - c.expected) > tol) {
      mismatches.push({ ...c, got });
    }
  }
  if (mismatches.length > 0) {
    console.error(`${mismatches.length}/${cases.length} MISMATCH:`);
    console.error(mismatches.slice(0, 20));
  }
  assert.equal(mismatches.length, 0, `${mismatches.length} mismatch dari ${cases.length} kasus`);
});
