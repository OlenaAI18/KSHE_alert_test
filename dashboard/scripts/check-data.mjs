import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../", import.meta.url));
const core = [
  "summary",
  "official_monthly",
  "category_statistics",
  "category_duration",
  "category_overlap",
  "forecast_comparison",
  "forecast_history",
  "forecastability_by_category",
  "temporal_patterns",
  "classification_quality",
  "duration_distribution",
];
const myth = ["myth_lab_questions", "myth_lab_results", "myth_lab_summary"];
const categories = [
  "shahed_uav",
  "jet_uav",
  "ballistic_high_speed",
  "cruise_missile",
  "mig31",
  "strategic_aviation",
  "other",
];
const states = [
  "not_supported",
  "partially_supported",
  "inconclusive",
  "insufficient_data",
];
const hash = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");
const close = (a, b) =>
  assert.ok(
    typeof a === "number" && typeof b === "number" && Math.abs(a - b) < 1e-9,
    `Numeric reconciliation failed: ${a} != ${b}`,
  );
function scan(value) {
  if (typeof value === "number")
    assert.ok(Number.isFinite(value), "Nonfinite public number");
  if (typeof value === "string")
    assert.ok(
      !/\/workspace\/|\/tmp\/|[A-Za-z]:\\/.test(value),
      "Local path in public data",
    );
  if (Array.isArray(value)) value.forEach(scan);
  else if (value && typeof value === "object")
    for (const [key, v] of Object.entries(value)) {
      assert.ok(
        !/^(text|original_text|original_message_text|message_text|message_id|alert_id|source_file|source_timestamp_original|start_time_original|matched_text|supporting_message_ids)$/.test(
          key,
        ),
        `Private source field: ${key}`,
      );
      scan(v);
    }
}
export function checkPublicData(
  directory = resolve(root, "dashboard/public/data"),
  repository = root,
) {
  const names = [...core, "manifest", ...myth].map((n) => n + ".json");
  assert.deepEqual(
    readdirSync(directory).sort(),
    names.sort(),
    "Unexpected or missing public asset",
  );
  const data = Object.fromEntries(
    names.map((name) => {
      const value = JSON.parse(readFileSync(resolve(directory, name), "utf8"));
      scan(value);
      return [name.slice(0, -5), value];
    }),
  );
  const manifest = data.manifest;
  assert.equal(manifest.schema_version, 1);
  assert.deepEqual(
    Object.keys(manifest.outputs).sort(),
    core.map((n) => n + ".json").sort(),
  );
  for (const [name, digest] of Object.entries(manifest.outputs))
    assert.equal(
      hash(resolve(directory, name)),
      digest,
      `Public checksum mismatch: ${name}`,
    );
  let unavailablePrivateInputs = 0;
  for (const inputMap of [manifest.inputs, data.myth_lab_summary.inputs])
    for (const [name, digest] of Object.entries(inputMap)) {
      assert.ok(/^[a-f0-9]{64}$/.test(digest), "Invalid SHA256");
      const path = resolve(repository, name);
      assert.ok(
        !relative(repository, path).startsWith(".."),
        "Input path escapes repository",
      );
      if (existsSync(path))
        assert.equal(hash(path), digest, `Input checksum mismatch: ${name}`);
      else {
        assert.ok(
          name.startsWith("data/"),
          "Missing versioned research input: " + name,
        );
        unavailablePrivateInputs++;
      }
    }
  const reviewed = JSON.parse(
    readFileSync(
      resolve(repository, "reports/myth_lab/validation_results.json"),
      "utf8",
    ),
  );
  for (const name of myth.map((n) => n + ".json"))
    assert.equal(
      hash(resolve(directory, name)),
      reviewed.public_output_hashes[name],
      `Reviewed Myth Lab checksum mismatch: ${name}`,
    );
  const s = data.summary,
    p = s.population;
  assert.equal(s.schema_version, 1);
  assert.equal(s.classification_version, "v1.6");
  assert.equal(p.official, 2594);
  assert.equal(s.duration.n, 2593);
  assert.equal(p.eligible, 1803);
  assert.equal(p.classified, 1295);
  close(s.coverage, p.classified / p.eligible);
  assert.equal(p.text_unknown + p.no_text + p.classified, p.eligible);
  assert.equal(p.eligible + p.outside + p.unresolved, p.official);
  assert.equal(data.classification_quality.accuracy, null);
  assert.equal(data.classification_quality.categories_overlap, true);
  assert.equal(
    data.official_monthly.reduce((sum, r) => sum + r.all_record_starts, 0),
    p.official,
  );
  assert.equal(
    data.official_monthly.reduce((sum, r) => sum + r.classified, 0),
    p.classified,
  );
  assert.equal(
    data.official_monthly.reduce((sum, r) => sum + r.eligible, 0),
    p.eligible,
  );
  for (const r of data.official_monthly) {
    assert.ok(/^202[2-6]-\d{2}$/.test(r.month));
    assert.equal(typeof r.partial_month, "boolean");
    assert.ok(r.days_observed > 0);
    if (r.eligible === 0) assert.equal(r.classification_coverage, null);
    else close(r.classification_coverage, r.classified / r.eligible);
  }
  assert.deepEqual(
    s.yearly.filter((r) => r.partial_period).map((r) => r.period),
    [2022, 2026],
  );
  assert.equal(data.official_monthly.at(-1).partial_month, true);
  assert.equal(
    s.yearly.reduce((sum, r) => sum + r.all_records, 0),
    p.official,
  );
  assert.equal(
    data.duration_distribution.reduce(
      (sum, r) => sum + r.bins.reduce((n, b) => n + b.count, 0),
      0,
    ),
    s.duration.n,
  );
  assert.deepEqual(
    data.category_statistics.map((r) => r.category),
    categories,
  );
  assert.deepEqual(
    data.category_statistics.map((r) => r.count),
    [630, 131, 458, 99, 293, 77, 70],
  );
  for (const r of data.category_statistics) {
    const diagonal = data.category_overlap.find(
      (x) => x.category_a === r.category && x.category_b === r.category,
    );
    assert.equal(diagonal.unique_alerts, r.count);
    assert.equal(
      data.category_duration
        .filter((x) => x.category === r.category)
        .reduce((n, x) => n + x.n, 0),
      r.count,
    );
  }
  for (const r of data.category_overlap)
    assert.equal(
      r.unique_alerts,
      data.category_overlap.find(
        (x) => x.category_a === r.category_b && x.category_b === r.category_a,
      ).unique_alerts,
    );
  assert.equal(data.forecast_history.length, 39 * 6);
  for (const r of data.forecast_comparison) {
    const rows = data.forecast_history.filter((x) => x.model === r.model);
    assert.equal(rows.length, 39);
    assert.equal(new Set(rows.map((x) => x.week_start)).size, 39);
    close(rows.reduce((n, x) => n + x.absolute_error, 0) / 39, r.MAE);
  }
  for (const r of data.forecast_history)
    close(r.absolute_error, Math.abs(r.prediction - r.actual));
  assert.equal(data.forecastability_by_category.length, 7);
  assert.equal(data.myth_lab_results.length, 7);
  assert.equal(data.myth_lab_questions.length, 7);
  data.myth_lab_results.forEach((r, i) => {
    assert.equal(r.myth_id, `myth_${i + 1}`);
    assert.ok(states.includes(r.verdict_state));
    assert.equal(r.title_uk, data.myth_lab_questions[i].title_uk);
    assert.equal(r.myth_id, data.myth_lab_questions[i].myth_id);
    for (const k of [
      "title_uk",
      "short_question_uk",
      "what_is_tested_uk",
      "headline_result_uk",
      "verdict_label",
      "methodology_note_uk",
    ])
      assert.ok(typeof r[k] === "string" && r[k].trim());
    assert.ok(r.limitations_uk.length > 0);
    assert.equal(r.chart_data.labels.length, r.chart_data.values.length);
    assert.ok(
      r.chart_data.values.every((v) => v === null || typeof v === "number"),
    );
  });
  const ms = data.myth_lab_summary;
  assert.equal(ms.official_starts_reconciled, p.official);
  assert.equal(ms.uav_unique_alerts, 630 + 131 - 70);
  assert.equal(ms.hosting_activated, false);
  for (const state of states)
    assert.equal(
      ms.verdict_counts[state],
      data.myth_lab_results.filter((r) => r.verdict_state === state).length,
    );
  const night = data.myth_lab_results[2].metric_summary;
  assert.equal(night.unique_alerts, ms.uav_unique_alerts);
  close(
    night.night_minute_share,
    night.night_alert_minutes / night.total_alert_minutes,
  );
  const patterns = data.temporal_patterns;
  close(
    data.myth_lab_results[6].metric_summary.raw.effect,
    patterns.find((r) => r.test === "daily_acf_lag_1").effect,
  );
  close(
    data.myth_lab_results[6].metric_summary.month_adjusted.effect,
    patterns.find((r) => r.test === "within_month_residual_acf_lag_1").effect,
  );
  // Report totals are checked without private inputs: this runs on a fresh checkout.
  const research = JSON.parse(
    readFileSync(
      resolve(repository, "reports/temporal_analysis/temporal_summary.json"),
      "utf8",
    ),
  );
  assert.deepEqual(p, research.baseline);
  close(s.duration.median, research.duration_minutes.median);
  return {
    status: "PASS",
    public_files: names.length,
    official_starts: p.official,
    eligible: p.eligible,
    classified: p.classified,
    myths: 7,
    unavailable_private_input_references: unavailablePrivateInputs,
  };
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
)
  console.log(JSON.stringify(checkPublicData()));
