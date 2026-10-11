import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
const out =
  process.env.RESEARCH_BROWSER_OUTPUT_DIR ||
  fileURLToPath(new URL("../reports/myth_lab/", import.meta.url));
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const checks = [];
try {
  for (const [name, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } }),
      errors = [],
      requests = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (r) => requests.push(r.url()));
    await page.goto("http://127.0.0.1:4173/KSHE_alert_test/");
    await page.locator(".myth-card").last().waitFor();
    if ((await page.locator(".myth-card").count()) !== 7)
      throw Error("seven cards");
    if ((await page.locator(".myth-verdict").count()) !== 0)
      throw Error("answers leaked before reveal");
    await page.waitForFunction(
      () => document.querySelectorAll(".js-plotly-plot").length === 12,
    );
    await page.getByRole("link", { name: "Myth Lab", exact: true }).click();
    await page.screenshot({ path: join(out, name + "-cards.png") });
    const buttons = page.locator(".myth-button");
    for (let i = 0; i < 7; i++) await buttons.nth(i).click();
    await page.waitForFunction(
      () => document.querySelectorAll(".js-plotly-plot").length === 19,
    );
    if ((await page.locator(".myth-verdict").count()) !== 7)
      throw Error("verdicts");
    if (
      await page.locator("body").evaluate((e) => e.scrollWidth > innerWidth + 1)
    )
      throw Error("body overflow");
    await page
      .locator("#myth-lab")
      .screenshot({ path: join(out, name + "-results.png") });
    const night = page.locator(".myth-card").nth(2);
    await night.scrollIntoViewIfNeeded();
    if (
      !(await night
        .innerText()
        .then((t) => t.includes("2026") && t.includes("39,90")))
    )
      throw Error("year reversal hidden");
    await night
      .locator(".js-plotly-plot .point")
      .first()
      .hover({ force: true });
    await page.waitForTimeout(150);
    if (
      !(await night
        .locator(".hoverlayer")
        .textContent()
        .then((t) => t.includes("63.182")))
    )
      throw Error("night tooltip");
    await page.screenshot({ path: join(out, name + "-night.png") });
    const calm = page.locator(".myth-card").nth(4);
    if (!(await calm.innerText().then((t) => t.includes("змінює знак"))))
      throw Error("calm contradiction hidden");
    const first = page.locator(".myth-card").first();
    await first
      .getByText("Як перевіряли та що обмежує висновок", { exact: true })
      .click();
    if (
      !(await first
        .locator("details")
        .last()
        .evaluate((e) => e.open))
    )
      throw Error("limitations expand");
    await first.locator(".myth-button").click();
    if ((await first.locator(".myth-verdict").count()) !== 0)
      throw Error("collapse");
    // Core filters/charts still work after the extension, without overwriting Task007 evidence.
    await page.getByLabel("Рік", { exact: true }).selectOption("2026");
    await page.getByLabel("Від місяця").fill("2026-09");
    await page.getByLabel("До місяця").fill("2026-09");
    await page.waitForFunction(
      () =>
        document.querySelectorAll(".js-plotly-plot")[1].data[0].y.length === 1,
    );
    if (
      (await page
        .locator(".js-plotly-plot")
        .nth(1)
        .evaluate((e) => e.data[0].y[0])) !== 190
    )
      throw Error("core counts");
    await page.getByLabel("Категорія", { exact: true }).selectOption("jet_uav");
    await page.getByLabel("Тривалість у групі").selectOption("single_category");
    await page.waitForFunction(
      () =>
        Math.abs(
          document.querySelectorAll(".js-plotly-plot")[5].data[0].y[1] -
            26.96666666666667,
        ) < 1e-10,
    );
    if (errors.length) throw Error(errors.join("\n"));
    if (requests.some((r) => !r.startsWith("http://127.0.0.1:4173/")))
      throw Error("external runtime request");
    checks.push({
      viewport: name,
      width,
      height,
      initial_core_charts: 12,
      revealed_total_charts: 19,
      cards: 7,
      hidden_before_click: true,
      expand_collapse: true,
      night_and_calm_reversals_visible: true,
      tooltips: true,
      core_filters_preserved: true,
      no_body_overflow: true,
      page_errors: errors,
    });
    await page.close();
  }
  for (const fault of ["missing", "invalid"]) {
    const page = await browser.newPage();
    await page.route("**/data/myth_lab_results.json", (r) =>
      r.fulfill({
        status: fault === "missing" ? 404 : 200,
        body: "[]",
        contentType: "application/json",
      }),
    );
    await page.goto("http://127.0.0.1:4173/KSHE_alert_test/");
    await page
      .getByRole("alert")
      .filter({ hasText: "Myth Lab недоступний" })
      .waitFor();
    await page.waitForFunction(
      () => document.querySelectorAll(".js-plotly-plot").length === 12,
    );
    checks.push({ fault, core_preserved: true, no_fake_zeros: true });
    await page.close();
  }
  writeFileSync(
    join(out, "browser_validation.json"),
    JSON.stringify(checks, null, 2) + "\n",
  );
  console.log(JSON.stringify(checks));
} finally {
  await browser.close();
}
