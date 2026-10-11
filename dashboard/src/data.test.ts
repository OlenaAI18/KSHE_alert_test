import config from "../vite.config";
import { it, expect, vi, afterEach } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { categories, files, finite, selectedMonths, loadData } from "./data";
const read = (n: string) =>
  JSON.parse(readFileSync(`public/data/${n}.json`, "utf8"));
afterEach(() => vi.unstubAllGlobals());
it("validates public schema and chart datasets", () => {
  for (const f of files) expect(read(f)).toBeDefined();
  const s = read("summary");
  expect(s.schema_version).toBe(1);
  expect(s.population.official).toBe(2594);
  expect(s.population.eligible).toBe(1803);
  expect(s.duration.n).toBe(2593);
  for (const r of read("official_monthly")) {
    expect(typeof r.partial_month).toBe("boolean");
    expect(typeof r.all_record_starts).toBe("number");
    expect(r.days_observed).toBeGreaterThan(0);
  }
});
it("retains category overlaps and counts", () => {
  const r = read("category_statistics");
  expect(r.map((x: any) => x.category)).toEqual(Object.keys(categories));
  expect(r.map((x: any) => x.count)).toEqual([630, 131, 458, 99, 293, 77, 70]);
  expect(r.reduce((s: number, x: any) => s + x.count, 0)).toBeGreaterThan(1295);
});
it("marks partial periods", () => {
  expect(
    read("summary")
      .yearly.filter((r: any) => r.partial_period)
      .map((r: any) => r.period),
  ).toEqual([2022, 2026]);
  expect(read("official_monthly").at(-1).partial_month).toBe(true);
});
it("filters existing monthly aggregates only", () => {
  expect(
    selectedMonths(read("official_monthly"), "2026", "2026-09", "2026-09"),
  ).toHaveLength(1);
  expect(
    selectedMonths(read("official_monthly"), "2023", "2026-09", "2026-10"),
  ).toHaveLength(0);
});
it("does not turn missing values into zero", () => {
  expect(finite(null)).toBeNull();
  expect(finite(NaN)).toBeNull();
  expect(finite(0)).toBe(0);
  expect(read("classification_quality").accuracy).toBeNull();
});
it("uses repository subpath and hash navigation", () => {
  expect(config.base).toBe("/KSHE_alert_test/");
  expect(readFileSync("src/data.ts", "utf8")).toContain(
    "import.meta.env.BASE_URL",
  );
  expect(readFileSync("src/main.tsx", "utf8")).toMatch(/href=\{["']#["']\s*\+\s*ids\[i\]\}/);
});
it("has no source texts, IDs, nonfinite values or local paths", () => {
  for (const name of readdirSync("public/data")) {
    const text = readFileSync(`public/data/${name}`, "utf8");
    expect(text).not.toMatch(
      /"(message_id|message_text|text|alert_id|start_time_original)"\s*:/,
    );
    expect(text).not.toMatch(/\/workspace\/|\/tmp\/|\bNaN\b|\bInfinity\b/);
  }
});
it("rejects missing files explicitly", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
  await expect(loadData()).rejects.toThrow("Не вдалося");
});
