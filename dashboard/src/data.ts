export const categories: Record<string, string> = {
  shahed_uav: "БПЛА · широка група",
  jet_uav: "Реактивні БПЛА",
  ballistic_high_speed: "Балістичні / швидкісні",
  cruise_missile: "Крилаті ракети",
  mig31: "МіГ · контекст каналу",
  strategic_aviation: "Стратегічна авіація",
  other: "Інші маркери",
};
export const methods: Record<string, string> = {
  B0: "Історичне середнє",
  B1: "Середнє за 4 тижні",
  B2: "Середнє за 8 тижнів",
  B3: "Попередній тиждень",
  B4: "Середнє за 13 тижнів",
  M1: "Регуляризована модель",
};
export const decisions: Record<string, string> = {
  INCONCLUSIVE: "Висновок невизначений",
  NO_STABLE_GAIN_OVER_BASELINES: "Без стабільного покращення",
  INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST:
    "Недостатньо даних / стабільності",
};
export type Row = Record<string, string | number | boolean | null>;
export type Summary = {
  population: {
    official: number;
    eligible: number;
    classified: number;
    text_unknown: number;
    no_text: number;
    outside: number;
    unresolved: number;
  };
  duration: { n: number; median: number };
  coverage: number;
  first_start: string;
  last_end: string;
  yearly: {
    period: number;
    partial_period: boolean;
    all_records: number;
    days: number;
  }[];
};
export type Data = {
  summary: Summary;
  official_monthly: Row[];
  category_statistics: Row[];
  category_duration: Row[];
  category_overlap: Row[];
  forecast_comparison: Row[];
  forecast_history: Row[];
  forecastability_by_category: Row[];
  temporal_patterns: Row[];
  classification_quality: Row;
  duration_distribution: {
    year: number;
    bins: { label: string; count: number }[];
  }[];
};
export const files = [
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
] as const;
export async function loadData(): Promise<Data> {
  const entries = await Promise.all(
    files.map(async (name) => {
      const response = await fetch(
        `${import.meta.env.BASE_URL}data/${name}.json`,
      );
      if (!response.ok) throw new Error(`Не вдалося завантажити ${name}`);
      return [name, await response.json()];
    }),
  );
  const data = Object.fromEntries(entries) as Data;
  if (
    data.summary.population.official !== 2594 ||
    !Array.isArray(data.official_monthly)
  )
    throw new Error("Невідповідна версія агрегатів");
  return data;
}
export function selectedMonths(
  rows: Row[],
  year: string,
  start: string,
  end: string,
) {
  return rows.filter(
    (r) =>
      (year === "all" || String(r.month).startsWith(year)) &&
      String(r.month) >= start &&
      String(r.month) <= end,
  );
}
export function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
export const repo = "https://github.com/OlenaAI18/KSHE_alert_test/blob/main/";
