import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const output =
  process.env.RESEARCH_BROWSER_OUTPUT_DIR ||
  fileURLToPath(new URL("../reports/dashboard/", import.meta.url));
mkdirSync(output, { recursive: true });
const results = [];
try {
  for (const [name, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [],
      requests = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (r) => requests.push(r.url()));
    await page.goto("http://127.0.0.1:4173/KSHE_alert_test/");
    await page
      .getByRole("heading", {
        name: "Чи можна передбачити повітряні тривоги в Києві?",
      })
      .waitFor();
    await page.waitForFunction(
      () => document.querySelectorAll(".js-plotly-plot").length === 12,
    );
    await page.waitForTimeout(500);
    if (
      await page
        .locator("body")
        .evaluate((el) => el.scrollWidth > innerWidth + 1)
    )
      throw Error(name + " overflow");
    await page.screenshot({ path: `${output}/${name}.png`, fullPage: true });
    await page.getByLabel("Рік", { exact: true }).selectOption("2026");
    await page.getByLabel("Від місяця").fill("2026-09");
    await page.getByLabel("До місяця").fill("2026-09");
    await page.waitForFunction(
      () =>
        document.querySelectorAll(".js-plotly-plot")[1].data[0].y.length === 1,
    );
    const count = await page
      .locator(".js-plotly-plot")
      .nth(1)
      .evaluate((el) => el.data[0].y[0]);
    if (count !== 190) throw Error("September count");
    await page.getByLabel("Категорія", { exact: true }).selectOption("jet_uav");
    await page.getByLabel("Тривалість у групі").selectOption("single_category");
    await page.waitForFunction(
      () =>
        Math.abs(
          document.querySelectorAll(".js-plotly-plot")[5].data[0].y[1] -
            26.96666666666667,
        ) < 1e-10,
    );
    await page.locator("nav a").last().click();
    await page.locator("details summary").first().click();
    if (
      !(await page
        .locator("details")
        .first()
        .evaluate((el) => el.open))
    )
      throw Error("details");
    await page.locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
    await page
      .locator(".js-plotly-plot")
      .first()
      .locator(".point")
      .first()
      .hover({ force: true });
    await page.waitForTimeout(300);
    const hover = await page.locator(".hoverlayer").first().textContent();
    if (!hover?.includes("592")) throw Error("tooltip");
    await page.screenshot({ path: `${output}/${name}-tooltip.png` });
    const external = requests.filter(
      (u) => !u.startsWith("http://127.0.0.1:4173/"),
    );
    if (external.length) throw Error("external dependencies");
    if (errors.length) throw Error(errors.join("\n"));
    results.push({
      viewport: name,
      width,
      height,
      charts: 12,
      september_count: count,
      tooltip: !!hover,
      no_overflow: true,
      console_errors: errors,
      external_requests: external,
    });
    await page.close();
  }
  const page = await browser.newPage();
  await page.route("**/data/summary.json", (r) =>
    r.fulfill({ status: 404, body: "missing" }),
  );
  await page.goto("http://127.0.0.1:4173/KSHE_alert_test/");
  await page.getByRole("heading", { name: "Дані недоступні" }).waitFor();
  results.push({ missing_data: "explicit error; no fabricated zeros" });
  await page.close();
  writeFileSync(
    `${output}/browser_validation.json`,
    JSON.stringify(results, null, 2) + "\n",
  );
  console.log(JSON.stringify(results));
} finally {
  await browser.close();
}
