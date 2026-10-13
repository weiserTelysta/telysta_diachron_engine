const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");

// Exercise the planning grammar with the actual ECMAScript RegExp engine;
// use BigInt as an independent range oracle, never as an IPC payload.
const schema = JSON.parse(readFileSync(join(__dirname, "../../docs/ADR_011_SCHEMA_DRAFT_V1.json"), "utf8"));
const definition = schema.$defs.u64Decimal;
const range = new RegExp(definition.pattern);
const nonDigit = new RegExp(definition.not.pattern);
const maximum = (1n << 64n) - 1n;
const accepts = (value) => typeof value === "string" && value.length <= definition.maxLength &&
  range.test(value) && !nonDigit.test(value);

test("planning seed strings round-trip exactly and match the independent u64 range", () => {
  const values = new Set([0n, 888n, (1n << 53n) - 1n, 1n << 53n, (1n << 53n) + 1n]);
  for (let offset = -1024n; offset <= 1024n; offset += 1n) values.add(maximum + offset);
  const bound = maximum.toString();
  for (let index = 0; index < bound.length; index += 1) {
    for (const digit of "0123456789") {
      for (const fill of "09") values.add(BigInt(bound.slice(0, index) + digit + fill.repeat(bound.length - index - 1)));
    }
  }
  for (const value of values) {
    const text = value.toString();
    assert.equal(accepts(text), value >= 0n && value <= maximum, text);
    if (accepts(text)) assert.equal(JSON.parse(JSON.stringify({ rootSeed: text })).rootSeed, text);
  }
  for (const invalid of ["", "00", "01", "-0", "-1", "+1", "1.0", "1e3", " 1", "1 ", "0\n", "١", "１", 0, null]) {
    assert.equal(accepts(invalid), false, String(invalid));
  }
});
