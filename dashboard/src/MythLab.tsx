import { useEffect, useState } from "react";
import { Chart } from "./Chart";
import { repo } from "./data";
import { loadMyths, type MythResult } from "./myth-data";
const topics = [
  "Символічні дати",
  "Свята",
  "Ніч і день",
  "Ритм тижня",
  "Затишшя",
  "Переговори",
  "Залежність днів",
];
const number = (v: unknown, digits = 2) =>
  typeof v === "number"
    ? v.toLocaleString("uk-UA", { maximumFractionDigits: digits })
    : "Немає даних";
type Sample = {
  date: string;
  event_starts_per_day?: number;
  control_starts_per_day?: number;
  before?: number;
  after?: number;
  difference: number;
};
function ExtraEvidence({ myth }: { myth: MythResult }) {
  const m = myth.metric_summary;
  if (myth.myth_id === "myth_3") {
    const yearly = m.yearly as {
      year: number;
      unique_alerts: number;
      night_minute_share: number | null;
      night_start_share: number | null;
    }[];
    const v15 = m.v15_sensitivity as Record<string, number>;
    return (
      <>
        <h4>Чи однаково в різні роки?</h4>
        <table>
          <thead>
            <tr>
              <th>Рік</th>
              <th>Тривоги</th>
              <th>Нічні хвилини</th>
              <th>Нічні початки</th>
            </tr>
          </thead>
          <tbody>
            {yearly.map((r) => (
              <tr key={r.year}>
                <td>
                  {r.year}
                  {[2023, 2026].includes(r.year) ? " *" : ""}
                </td>
                <td>{r.unique_alerts}</td>
                <td>
                  {number(
                    r.night_minute_share === null
                      ? null
                      : 100 * r.night_minute_share,
                  )}
                  %
                </td>
                <td>
                  {number(
                    r.night_start_share === null
                      ? null
                      : 100 * r.night_start_share,
                  )}
                  %
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="caption">
          * Неповна доступна історія категорій. За весь архів:{" "}
          {number(m.unique_alerts, 0)} унікальних тривог, нічний перетин мають{" "}
          {number(Number(m.night_intersection_share) * 100)}%. Ніч —{" "}
          {number(Number(m.calendar_exposure_share) * 100)}% календарної
          експозиції. v1.5: {number(v15.night_minute_share * 100)}% нічних
          хвилин у {number(v15.unique_alerts, 0)} тривог.
        </p>
      </>
    );
  }
  if (["myth_1", "myth_2", "myth_6"].includes(myth.myth_id)) {
    const primary = m.primary as { events: Sample[]; event_count: number };
    const sensitivity = (m.window_sensitivity ||
      m.seven_day_sensitivity) as Record<string, unknown>;
    const dateMyth = myth.myth_id !== "myth_6";
    return (
      <details className="myth-evidence">
        <summary>Події та чутливість до ширини вікна</summary>
        <p>
          Основна перевірка: {primary.event_count} подій.{" "}
          {dateMyth ? "Вікно ±1 день" : "Вікно 7 днів"}:{" "}
          {number(sensitivity.event_mean ?? sensitivity.before_mean)} проти{" "}
          {number(sensitivity.control_mean ?? sensitivity.after_mean)}{" "}
          початків/день.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>{dateMyth ? "Подія" : "До"}</th>
                <th>{dateMyth ? "Контроль" : "Після"}</th>
                <th>Різниця</th>
              </tr>
            </thead>
            <tbody>
              {primary.events.map((r) => (
                <tr key={r.date}>
                  <td>{r.date}</td>
                  <td>{number(r.event_starts_per_day ?? r.before)}</td>
                  <td>{number(r.control_starts_per_day ?? r.after)}</td>
                  <td>{number(r.difference)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="caption">
          Для календарних подій різниця = подія мінус контроль; для переговорів
          = після мінус до. Кожна подія має рівну вагу.
        </p>
      </details>
    );
  }
  if (myth.myth_id === "myth_5") {
    const sensitivity = m.zero_start_sensitivity as Record<string, unknown>;
    return (
      <p className="caption">
        {number(m.calm_days, 0)} днів після затишшя та {number(m.other_days, 0)}{" "}
        після інших періодів. Різниця всередині{" "}
        {number(m.matched_month_count, 0)} місяців: +
        {number(m.month_adjusted_difference)}. Для суворішого затишшя (0
        початків): {number(sensitivity.after_calm_mean)} проти{" "}
        {number(sensitivity.after_other_mean)}; місячна різниця +
        {number(sensitivity.month_adjusted_difference)}. Це не перспектива
        прогнозу.
      </p>
    );
  }
  if (myth.myth_id === "myth_4")
    return (
      <p className="caption">
        {number(m.weekend_days, 0)} вихідних і {number(m.weekday_days, 0)}{" "}
        буднів. Різниця всередині {number(m.matched_month_count, 0)} місяців:{" "}
        {number(m.month_adjusted_difference)} початків/день; вона не є оцінкою
        причинного ефекту.
      </p>
    );
  const raw = m.raw as Record<string, number>,
    adjusted = m.month_adjusted as Record<string, number>;
  return (
    <p className="caption">
      Точні значення Task005: {number(raw.effect, 6)} [95%:{" "}
      {number(raw.ci_low, 3)}; {number(raw.ci_high, 3)}] та{" "}
      {number(adjusted.effect, 6)} [{number(adjusted.ci_low, 3)};{" "}
      {number(adjusted.ci_high, 3)}]. Дослідницькі блокові інтервали, не
      гарантія передбачення.
    </p>
  );
}
function MythCard({ myth, index }: { myth: MythResult; index: number }) {
  const [revealed, setRevealed] = useState(false);
  const panel = `${myth.myth_id}-result`;
  return (
    <article className={`myth-card myth-tone-${index % 3}`}>
      <div className="myth-visual" aria-hidden="true">
        <span className="myth-number">0{index + 1}</span>
        <svg viewBox="0 0 160 65" fill="none">
          <path
            d="M9 53H151M25 11V54M51 24V54M77 35V54M103 18V54M129 30V54"
            stroke="currentColor"
            strokeWidth="2"
          />
          <path
            d="M18 42L47 32L75 44L103 10L137 22"
            stroke="currentColor"
            strokeWidth="3"
          />
          <circle cx="103" cy="10" r="5" fill="currentColor" />
        </svg>
        <span className="myth-topic">{topics[index]}</span>
      </div>
      <h3>{myth.title_uk}</h3>
      <p className="myth-test">{myth.what_is_tested_uk}</p>
      <button
        type="button"
        className="myth-button"
        aria-expanded={revealed}
        aria-controls={panel}
        onClick={() => setRevealed(!revealed)}
      >
        {revealed ? "Згорнути результат" : "Перевірити"}
        <span aria-hidden="true"> {revealed ? "−" : "+"}</span>
      </button>
      {revealed && (
        <div id={panel} className="myth-result">
          <span className={`myth-verdict state-${myth.verdict_state}`}>
            {myth.verdict_label}
          </span>
          <p className="myth-headline">{myth.headline_result_uk}</p>
          <Chart
            title="Що показує порівняння"
            ylabel={myth.chart_data.ylabel_uk}
            data={[
              {
                type: "bar",
                x: myth.chart_data.labels,
                y: myth.chart_data.values,
                marker: { color: ["#2256c7", "#009e9a"] },
                hovertemplate: "%{x}<br>%{y:.3f}<extra></extra>",
              },
            ]}
          />
          <ExtraEvidence myth={myth} />
          <details>
            <summary>Як перевіряли та що обмежує висновок</summary>
            <p>{myth.methodology_note_uk}</p>
            <ul>
              {myth.limitations_uk.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </article>
  );
}
export function MythLab() {
  const [myths, setMyths] = useState<MythResult[]>();
  const [error, setError] = useState("");
  useEffect(() => {
    loadMyths()
      .then(setMyths)
      .catch((e) => setError(String(e)));
  }, []);
  return (
    <section id="myth-lab" className="myth-lab">
      <div className="section-title">
        <span className="index">07</span>
        <h2>Міфи про тривоги: перевіряємо даними</h2>
      </div>
      <p className="eyebrow">MYTH LAB · СІМ ПИТАНЬ ДО АРХІВУ</p>
      <p>
        Який висновок ви очікуєте? Відкрийте перевірку й порівняйте припущення з
        даними. Ми вивчаємо <b>офіційні київські тривоги</b> та повідомлені
        маркери, а не всі обстріли України чи мотиви їх вибору.
      </p>
      <p className="caption">
        Це окремі описові досліди. Часткова підтримка стосується лише
        зазначеного показника; невизначений результат не підтверджує й не
        спростовує твердження.
      </p>
      {error ? (
        <p role="alert">
          Myth Lab недоступний. Основне дослідження доступне вище; результати не
          замінено нулями.
        </p>
      ) : !myths ? (
        <p aria-busy="true">Завантажуємо перевірки…</p>
      ) : (
        <div className="myth-grid">
          {myths.map((m, i) => (
            <MythCard key={m.myth_id} myth={m} index={i} />
          ))}
        </div>
      )}
      <div className="links">
        <a href={repo + "reports/myth_lab/myth_lab_report.md"}>
          Повний звіт Myth Lab ↗
        </a>
        <a href={repo + "reports/myth_lab/source_register.csv"}>
          Джерела календарних дат ↗
        </a>
        <a href={repo + "config/myth_lab_v1.json"}>Зафіксовані визначення ↗</a>
        <a href={`${import.meta.env.BASE_URL}data/myth_lab_results.json`}>
          Публічні агрегати ↗
        </a>
      </div>
    </section>
  );
}
