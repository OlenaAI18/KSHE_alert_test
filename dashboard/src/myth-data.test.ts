import { it, expect, vi, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { validateMyths, loadMyths, mythStates } from "./myth-data";
const results = () =>
  JSON.parse(readFileSync("public/data/myth_lab_results.json", "utf8"));
afterEach(() => vi.unstubAllGlobals());
it("validates seven versioned myth results with required schema", () => {
  const rows = validateMyths(results());
  expect(rows).toHaveLength(7);
  expect(rows.map((r) => r.myth_id)).toEqual(
    Array.from({ length: 7 }, (_, i) => `myth_${i + 1}`),
  );
  for (const r of rows) {
    expect(mythStates).toContain(r.verdict_state);
    expect(r.chart_data.labels.length).toBe(r.chart_data.values.length);
  }
});
it("rejects confirmed-truth verdicts and nonfinite datasets", () => {
  const r = results();
  r[0].verdict_state = "confirmed";
  expect(() => validateMyths(r)).toThrow();
  const b = results();
  b[0].chart_data.values[0] = NaN;
  expect(() => validateMyths(b)).toThrow();
});
it("rejects duplicate IDs, missing questions and missing limitations", () => {
  const r = results();
  r[1].myth_id = "myth_1";
  expect(() => validateMyths(r)).toThrow();
  expect(() => validateMyths(results().slice(1))).toThrow();
  const b = results();
  b[0].limitations_uk = [];
  expect(() => validateMyths(b)).toThrow();
});
it("keeps source scope and reversal explicit", () => {
  const r = results();
  expect(r[2].headline_result_uk).toContain("2026");
  expect(r[4].headline_result_uk).toContain("змінює знак");
  expect(r[5].limitations_uk.join(" ")).toContain("не причинний");
  expect(r[6].limitations_uk.join(" ")).toContain("не гарантує");
});
it("schema error remains isolated from core loader", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
  );
  await expect(loadMyths()).rejects.toThrow();
  expect(readFileSync("src/data.ts", "utf8")).not.toContain("myth_lab");
});
it("uses bundled relative paths and defaults to unrevealed results", () => {
  expect(readFileSync("src/myth-data.ts", "utf8")).toContain(
    "import.meta.env.BASE_URL",
  );
  const source = readFileSync("src/MythLab.tsx", "utf8");
  expect(source).toContain("useState(false)");
  expect(source).toContain("aria-expanded");
  expect(source).toContain("Перевірити");
});
