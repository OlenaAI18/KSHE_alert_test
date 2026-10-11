export const mythStates = [
  "not_supported",
  "partially_supported",
  "inconclusive",
  "insufficient_data",
] as const;
export type MythResult = {
  myth_id: string;
  title_uk: string;
  short_question_uk: string;
  what_is_tested_uk: string;
  metric_summary: Record<string, unknown>;
  chart_data: {
    labels: string[];
    values: (number | null)[];
    ylabel_uk: string;
  };
  headline_result_uk: string;
  verdict_label: string;
  verdict_state: (typeof mythStates)[number];
  limitations_uk: string[];
  methodology_note_uk: string;
};
export function validateMyths(value: unknown): MythResult[] {
  if (!Array.isArray(value) || value.length !== 7)
    throw new Error("Очікується сім перевірок Myth Lab");
  value.forEach((r, i) => {
    const strings = [
      "title_uk",
      "short_question_uk",
      "what_is_tested_uk",
      "headline_result_uk",
      "verdict_label",
      "methodology_note_uk",
    ];
    if (
      !r ||
      r.myth_id !== `myth_${i + 1}` ||
      !mythStates.includes(r.verdict_state) ||
      strings.some((k) => typeof r[k] !== "string" || !r[k].trim())
    )
      throw new Error("Невідповідна схема Myth Lab");
    if (
      !r.metric_summary ||
      typeof r.metric_summary !== "object" ||
      !Array.isArray(r.limitations_uk) ||
      !r.limitations_uk.length ||
      r.limitations_uk.some((x: unknown) => typeof x !== "string")
    )
      throw new Error("Немає методики Myth Lab");
    const chart = r.chart_data;
    if (
      !chart ||
      typeof chart.ylabel_uk !== "string" ||
      !Array.isArray(chart.labels) ||
      !Array.isArray(chart.values) ||
      chart.labels.length !== chart.values.length ||
      !chart.labels.length ||
      chart.labels.some((x: unknown) => typeof x !== "string") ||
      chart.values.some(
        (x: unknown) =>
          x !== null && (typeof x !== "number" || !Number.isFinite(x)),
      )
    )
      throw new Error("Невідповідні дані графіка Myth Lab");
  });
  return value;
}
export async function loadMyths() {
  const response = await fetch(
    `${import.meta.env.BASE_URL}data/myth_lab_results.json`,
  );
  if (!response.ok) throw new Error("Не вдалося завантажити Myth Lab");
  return validateMyths(await response.json());
}
