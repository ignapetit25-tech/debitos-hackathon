// Vectors for the REAL parseMoney in debit_ai/static/app.js (no deps).
// Run: node tests/test_parse_money.cjs
// Strict US format: "12,500.50" and "12500.50" valid; AR-style,
// trailing text, bad grouping, empties and negatives invalid.
const fs = require("fs");
const path = require("path");

const src = fs.readFileSync(
  path.join(__dirname, "..", "debit_ai", "static", "app.js"), "utf8");
const start = src.indexOf("function parseMoney(s) {");
if (start < 0) throw new Error("parseMoney not found in app.js");
let depth = 0, end = -1;
for (let i = src.indexOf("{", start); i < src.length; i++) {
  if (src[i] === "{") depth++;
  else if (src[i] === "}") { depth--; if (!depth) { end = i + 1; break; } }
}
if (end < 0) throw new Error("parseMoney body not closed");
// eslint-disable-next-line no-new-func
const parseMoney = new Function(src.slice(start, end) + "; return parseMoney;")();

const cases = [
  // [input, wantCentsOrNull]
  ["12,500.50", 1250050],
  ["12500.50", 1250050],
  ["$12,500.50", 1250050],
  ["  12500.50  ", 1250050],
  ["0", 0],
  ["0.00", 0],
  ["12", 1200],
  ["12.5", 1250],
  ["1,234", 123400],
  ["1,234,567.89", 123456789],
  ["", null],
  ["   ", null],
  [null, null],
  [undefined, null],
  ["-", null],
  ["-5", null],
  ["-12,500.50", null],
  ["12abc", null],
  ["abc", null],
  ["12.500,50", null],
  ["1,23", null],
  ["12,50.00", null],
  ["12.555", null],
  ["1.2.3", null],
  ["12 500.50", 1250050],
];

let fail = 0;
for (const [inp, want] of cases) {
  const got = parseMoney(inp);
  if (got !== want) {
    fail++;
    console.error(`FAIL ${JSON.stringify(inp)} -> ${got}, want ${want}`);
  }
}
if (fail) {
  console.error(`${fail} failure(s)`);
  process.exit(1);
}
console.log(`parseMoney: ${cases.length}/${cases.length} vectors OK`);
