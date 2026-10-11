import { it, expect } from "vitest";
import {
  mkdtempSync,
  cpSync,
  readFileSync,
  writeFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
// Node-only production publication gate.
// @ts-expect-error JavaScript CLI is independently runnable without TS compilation.
import { checkPublicData } from "../scripts/check-data.mjs";
it("checks all publication aggregates, checksums and source reconciliation", () => {
  expect(checkPublicData().public_files).toBe(15);
});
it.each([
  "unknown asset",
  "tampered checksum",
  "raw field",
  "invalid myth verdict",
])("rejects %s before publication", (kind) => {
  const temp = mkdtempSync(join(tmpdir(), "kyiv-gate-"));
  const data = join(temp, "data");
  cpSync(resolve("public/data"), data, { recursive: true });
  try {
    if (kind === "unknown asset") writeFileSync(join(data, "raw.json"), "{}");
    else if (kind === "tampered checksum")
      writeFileSync(join(data, "summary.json"), "{}");
    else {
      const file = join(data, "myth_lab_results.json");
      const rows = JSON.parse(readFileSync(file, "utf8"));
      if (kind === "raw field") rows[0].original_text = "must not publish";
      else rows[0].verdict_state = "confirmed";
      writeFileSync(file, JSON.stringify(rows));
    }
    expect(() => checkPublicData(data)).toThrow();
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});
