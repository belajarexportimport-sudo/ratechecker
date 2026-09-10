import { test } from "node:test";
import assert from "node:assert/strict";
import { makeRateRequest, cloneRateRequest, makeRateResult } from "../src/core/schemas.js";
import { RateEngineError, UPSRateError, FedExRateError } from "../src/core/errors.js";

test("makeRateRequest fills defaults like Python dataclass", () => {
  const req = makeRateRequest({
    carrier: "ups", rate_type: "b26", service: "saver",
    direction: "export", origin_country: "Indonesia",
    destination_country: "Japan", weight_kg: 2.0,
  });
  assert.equal(req.packages, 1);
  assert.deepEqual(req.extra, {});
  assert.equal(req.discount_pct, null);
});

test("cloneRateRequest does shallow copy of extra (mutating clone.extra does not affect original after reassignment)", () => {
  const req = makeRateRequest({
    carrier: "ups", rate_type: "commercial", service: "saver",
    direction: "export", origin_country: "Indonesia",
    destination_country: "Japan", weight_kg: 2.0,
    extra: { ups_tier: "a26" },
  });
  const clone = cloneRateRequest(req);
  clone.rate_type = "a26";
  clone.extra = { ...clone.extra };
  delete clone.extra.ups_tier;

  assert.equal(req.rate_type, "commercial"); // original tidak berubah
  assert.equal(req.extra.ups_tier, "a26");   // original tidak berubah
  assert.equal(clone.rate_type, "a26");
  assert.equal(clone.extra.ups_tier, undefined);
});

test("UPSRateError & FedExRateError are instanceof RateEngineError", () => {
  assert.ok(new UPSRateError("x") instanceof RateEngineError);
  assert.ok(new FedExRateError("x") instanceof RateEngineError);
  assert.ok(new UPSRateError("x") instanceof Error);
});

test("makeRateResult fills defaults", () => {
  const r = makeRateResult({ carrier: "ups", rate_type: "b26", service: "saver", zone: "10", base_price: 550200 });
  assert.deepEqual(r.surcharges, {});
  assert.equal(r.discount, 0);
  assert.equal(r.currency, "IDR");
});
