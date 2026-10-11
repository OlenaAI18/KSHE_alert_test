import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Chart } from "./Chart";
import { MythLab } from "./MythLab";
import {
  loadData,
  categories,
  methods,
  decisions,
  selectedMonths,
  finite,
  repo,
  type Data,
  type Row,
} from "./data";
import "./style.css";
const num = (v: unknown, d = 0) =>
  finite(v) === null
    ? "Немає даних"
    : Number(v).toLocaleString("uk-UA", { maximumFractionDigits: d });
const sections = [
  "Огляд",
  "Динаміка",
  "Типи загроз",
  "Часові патерни",
  "Прогнозованість",
  "Методологія",
  "Myth Lab",
];
const ids = [
  "overview",
  "history",
  "threats",
  "patterns",
  "forecast",
  "methodology",
  "myth-lab",
];
function App() {
  const [data, setData] = useState<Data>();
  const [error, setError] = useState("");
  const [year, setYear] = useState("all");
  const [start, setStart] = useState("2022-02");
  const [end, setEnd] = useState("2026-10");
  const [category, setCategory] = useState("shahed_uav");
  const [duration, setDuration] = useState("any");
  useEffect(() => {
    loadData()
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);
  if (error)
    return (
      <main>
        <h1>Дані недоступні</h1>
        <p role="alert">{error}</p>
        <p>
          Показники не підмінено нулями. Перезавантажте сторінку або відкрийте{" "}
          <a
            href={
              repo + "reports/temporal_analysis/temporal_analysis_report.md"
            }
          >
            дослідницький звіт
          </a>
          .
        </p>
      </main>
    );
  if (!data)
    return (
      <main aria-busy="true">
        <p>Завантажуємо дослідницькі агрегати…</p>
      </main>
    );
  const s = data.summary,
    months = selectedMonths(data.official_monthly, year, start, end),
    cats = Object.keys(categories);
  const chosen = data.category_statistics.find((r) => r.category === category)!;
  const durationRows =
    duration === "any"
      ? data.category_statistics.map((r) => ({
          category: r.category,
          median: r.median,
          n: r.count,
        }))
      : data.category_duration.filter(
          (r) => r.category !== "ALL" && r.group === duration,
        );
  const hist = (model: string) =>
    data.forecast_history.filter((r) => r.model === model);
  const distribution = data.duration_distribution.filter(
    (r) => year === "all" || String(r.year) === year,
  );
  const bins =
    distribution[0]?.bins.map((b, i) => ({
      label: b.label,
      count: distribution.reduce((sum, r) => sum + r.bins[i].count, 0),
    })) ?? [];
  const pattern = data.temporal_patterns.filter(
    (r) =>
      r.test === "daily_acf_lag_1" ||
      r.test === "within_month_residual_acf_lag_1",
  );
  const card = (value: unknown, label: string, d = 0) => (
    <div className="metric">
      <strong>{num(value, d)}</strong>
      <span>{label}</span>
    </div>
  );
  const sectionTitle = (i: number, title: string) => (
    <div className="section-title">
      <span className="index">0{i + 1}</span>
      <h2>{title}</h2>
    </div>
  );
  return (
    <>
      <header>
        <a className="brand" href="#overview">
          <span className="brand-mark">К</span> КИЇВ / ALERT RESEARCH
        </a>
        <span className="edition">Дослідницький MVP · 2026</span>
      </header>
      <nav aria-label="Розділи дослідження">
        {sections.map((x, i) => (
          <a key={x} href={"#" + ids[i]}>
            {x}
          </a>
        ))}
      </nav>
      <main>
        <section id="overview">
          <p className="eyebrow">
            ІСТОРІЯ ТРИВОГ · КОНТЕКСТ ЗАГРОЗ · ПЕРЕВІРКА ГІПОТЕЗ
          </p>
          <h1>Чи можна передбачити повітряні тривоги в Києві?</h1>
          <p className="subtitle">
            Ретроспективне дослідження історії повітряних тривог та повідомлень
            про типи загроз, 2022–2026.
          </p>
          <div className="finding">
            <span className="pill">ГОЛОВНИЙ РЕЗУЛЬТАТ</span>
            <h2>Стабільного покращення прогнозу не виявлено</h2>
            <p>
              Перевірена регуляризована модель не показала стабільної переваги
              поза навчальною вибіркою над простими історичними орієнтирами. Це
              не доводить фізичну неможливість прогнозування.
            </p>
          </div>
          <div className="metrics">
            {card(s.population.official, "офіційні тривоги")}
            {card(s.duration.n, "інтервали з визначеним кінцем")}
            {card(s.duration.median, "хв · медіанна тривалість", 2)}
            {card(s.population.eligible, "тривоги в межах Telegram")}
            {card(s.population.classified, "класифіковано · v1.6")}
            {card(s.coverage * 100, "% · покриття класифікації", 2)}
          </div>
          <ul className="conclusions">
            <li>Інтенсивність змінюється між історичними періодами.</li>
            <li>
              Типи загроз — експериментальна інтерпретація повідомленого
              контексту.
            </li>
            <li>Невідомий тип не означає відсутність загрози.</li>
            <li>
              Історичний dashboard — обґрунтований MVP; оперативний прогноз не
              підтверджено.
            </li>
          </ul>
        </section>
        <section id="history">
          {sectionTitle(1, "Як змінювалась історія тривог")}
          <p>
            Джерело охоплює 28.02.2022 — 05.10.2026 (останній відбій). 2022 та
            2026 — неповні роки, жовтень 2026 — неповний місяць. Відсутність
            записів не гарантує повноту архіву.
          </p>
          <div className="controls">
            <label>
              Рік
              <select
                aria-label="Рік"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              >
                <option value="all">Усі роки</option>
                {s.yearly.map((r) => (
                  <option key={r.period}>{r.period}</option>
                ))}
              </select>
            </label>
            <label>
              Від місяця
              <input
                type="month"
                min="2022-02"
                max="2026-10"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              До місяця
              <input
                type="month"
                min="2022-02"
                max="2026-10"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
          </div>
          <p className="caption">
            Місячні графіки: вибрані місяці. Річний графік: повна доступна
            історія. Розподіл тривалості: вибраний рік, без фільтра місяців.
            Загальні картки залишаються за весь архів.
          </p>
          {months.length === 0 && (
            <p role="status" className="notice">
              У вибраному діапазоні немає опублікованих місяців.
            </p>
          )}
          <div className="chart-grid">
            <Chart
              title="Офіційні тривоги за роками"
              ylabel="Початки тривог"
              data={[
                {
                  type: "bar",
                  x: s.yearly.map(
                    (r) =>
                      `${r.period}${r.partial_period ? " · неповний" : ""}`,
                  ),
                  y: s.yearly.map((r) => r.all_records),
                  customdata: s.yearly.map((r) => r.days),
                  hovertemplate:
                    "%{x}<br>%{y} тривог<br>%{customdata} днів у джерелі<extra></extra>",
                },
              ]}
            />
            <Chart
              title="Місячна кількість тривог"
              ylabel="Початки тривог"
              data={[
                {
                  type: "bar",
                  x: months.map(
                    (r) => String(r.month) + (r.partial_month ? " *" : ""),
                  ),
                  y: months.map((r) => Number(r.all_record_starts)),
                  marker: {
                    color: months.map((r) =>
                      r.partial_month ? "#e99536" : "#2256c7",
                    ),
                  },
                  hovertemplate: "%{x}<br>%{y} тривог<extra></extra>",
                },
              ]}
              description="* Неповний місяць. Усі відомі початки, включно з інтервалом без визначеного кінця."
            />
            <Chart
              title="Місячна інтенсивність"
              ylabel="Тривоги / день у джерелі"
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers",
                  x: months.map((r) => String(r.month)),
                  y: months.map(
                    (r) =>
                      Number(r.all_record_starts) / Number(r.days_observed),
                  ),
                  hovertemplate: "%{x}<br>%{y:.2f} / день<extra></extra>",
                },
              ]}
              description="Ділиться на кількість календарних днів у межах джерела, а не на число активних днів. Неповні місяці мають іншу експозицію."
            />
            <Chart
              title="Розподіл тривалості"
              ylabel="Завершені інтервали"
              data={[
                {
                  type: "bar",
                  x: bins.map((r) => r.label),
                  y: bins.map((r) => r.count),
                  marker: { color: "#009e9a" },
                },
              ]}
              description="Інтервали в хвилинах, нижня межа включена. Один DST-неоднозначний кінець виключено; жодного виправлення тривалості."
            />
          </div>
          <aside className="notice">
            У вересні 2026 запроваджено жовтий і червоний рівні попереджень.
            Обидва — реальні офіційні тривоги. Зміна режиму вимірювання не
            доводить причину вересневого зростання.
          </aside>
        </section>
        <section id="threats">
          {sectionTitle(2, "Що описує контекст загроз")}
          <p>
            Маркери — кількість унікальних тривог із категорією. Категорії
            перетинаються: їх не можна складати як взаємовиключні події. «БПЛА»
            не означає підтверджений Shahed; «МіГ» не підтверджує модель
            МіГ-31К.
          </p>
          <div className="controls">
            <label>
              Категорія
              <select
                aria-label="Категорія"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {cats.map((c) => (
                  <option key={c} value={c}>
                    {categories[c]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Тривалість у групі
              <select
                aria-label="Тривалість у групі"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
              >
                <option value="any">Будь-яка тривога з категорією</option>
                <option value="single_category">Лише одна категорія</option>
                <option value="multiple_categories">Кілька категорій</option>
              </select>
            </label>
          </div>
          <div className="inline-stat">
            {categories[category]}: <b>{num(chosen.count)}</b> тривог ·{" "}
            {num((chosen.share_eligible as number) * 100, 2)}% із 1803
            доступних.
          </div>
          <div className="chart-grid">
            <Chart
              title="Кількість категорій у контексті"
              ylabel="Унікальні тривоги"
              data={[
                {
                  type: "bar",
                  x: cats.map((c) => categories[c]),
                  y: data.category_statistics.map((r) => Number(r.count)),
                  marker: {
                    color: cats.map((c) =>
                      c === category ? "#009e9a" : "#2256c7",
                    ),
                  },
                },
              ]}
            />
            <Chart
              title="Медіанна тривалість за категорією"
              ylabel="Хвилини"
              data={[
                {
                  type: "bar",
                  x: durationRows.map((r) => categories[String(r.category)]),
                  y: durationRows.map((r) => finite(r.median)),
                  customdata: durationRows.map((r) => Number(r.n)),
                  hovertemplate:
                    "%{x}<br>%{y:.2f} хв · n=%{customdata}<extra></extra>",
                },
              ]}
              description="Тривалість адміністративного попередження, не час польоту або наближення зброї."
            />
            <Chart
              title="Перетини з вибраною категорією"
              ylabel="Тривоги з обома маркерами"
              data={[
                {
                  type: "bar",
                  x: cats
                    .filter((c) => c !== category)
                    .map((c) => categories[c]),
                  y: cats
                    .filter((c) => c !== category)
                    .map((c) =>
                      Number(
                        data.category_overlap.find(
                          (r) =>
                            r.category_a === category && r.category_b === c,
                        )?.unique_alerts ?? 0,
                      ),
                    ),
                  marker: { color: "#009e9a" },
                },
              ]}
            />
            <Chart
              title="Одна, кілька або невідома категорія"
              ylabel="Медіана · хв"
              data={[
                {
                  type: "bar",
                  x: ["Одна категорія", "Кілька категорій", "Невідомо"],
                  y: data.category_duration
                    .filter((r) => r.category === "ALL")
                    .map((r) => finite(r.median)),
                  customdata: data.category_duration
                    .filter((r) => r.category === "ALL")
                    .map((r) => Number(r.n)),
                  hovertemplate:
                    "%{x}<br>%{y:.2f} хв · n=%{customdata}<extra></extra>",
                },
              ]}
            />
          </div>
          <aside className="notice">
            508 із 1803 тривог залишаються невідомими: 410 мають текст без
            прийнятого маркера, 98 — без тексту. Окремо 790 поза
            Telegram-покриттям і один невизначений інтервал. Довші тривоги мають
            більше повідомлень та можливостей виявити категорії; покриття 71,82%
            не є точністю.
          </aside>
        </section>
        <section id="patterns">
          {sectionTitle(3, "Кореляція ще не означає прогноз")}
          <div className="chart-grid">
            <Chart
              title="Щоденна автокореляція · lag 1"
              ylabel="Кореляція"
              data={[
                {
                  type: "bar",
                  x: ["Початковий ряд", "Після вилучення місячного середнього"],
                  y: pattern.map((r) => Number(r.effect)),
                  error_y: {
                    type: "data",
                    symmetric: false,
                    array: pattern.map(
                      (r) => Number(r.ci_high) - Number(r.effect),
                    ),
                    arrayminus: pattern.map(
                      (r) => Number(r.effect) - Number(r.ci_low),
                    ),
                  },
                },
              ]}
              description="Дослідницькі блокові 95% інтервали. Корекція використовує весь місяць ретроспективно, не є доступною майбутньою ознакою."
            />
            <article className="text-card">
              <h3>Стабільної сезонності не підтверджено</h3>
              <p>
                Після поправки Holm для чотирьох сезонів жоден результат не
                досяг порогу 0,05. Лише три повні річні повторення: 2023–2025.
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Сезон</th>
                    <th>p · Holm</th>
                  </tr>
                </thead>
                <tbody>
                  {data.temporal_patterns
                    .filter((r) => String(r.test).startsWith("season_"))
                    .map((r) => (
                      <tr key={String(r.test)}>
                        <td>
                          {
                            {
                              season_DJF_vs_rest: "Зима",
                              season_MAM_vs_rest: "Весна",
                              season_JJA_vs_rest: "Літо",
                              season_SON_vs_rest: "Осінь",
                            }[String(r.test)]
                          }
                        </td>
                        <td>{num(r.holm_p, 3)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </article>
          </div>
          <p>
            Lag 1: початковий ряд — {num(pattern[0]?.effect, 6)}; після
            вилучення місячного середнього — {num(pattern[1]?.effect, 6)}.
          </p>
          <p>
            Зміни інтенсивності та практики повідомлень впливають на початкову
            кореляцію. Описова залежність не гарантує стабільного результату на
            наступних тижнях і не визначає «безпечних годин».
          </p>
        </section>
        <section id="forecast">
          {sectionTitle(4, "Перевірка на майбутніх щодо навчання тижнях")}
          <p>
            Task 006: 39 фінальних історичних тижнів, 05.01–28.09.2026. Ціль —
            кількість усіх офіційних початків за наступний тиждень. Вибір моделі
            завершено до фінального періоду.
          </p>
          <Chart
            title="Середня абсолютна помилка · фінальна перевірка"
            ylabel="Тривоги / тиждень · MAE"
            data={[
              {
                type: "bar",
                x: data.forecast_comparison.map(
                  (r) => methods[String(r.model)],
                ),
                y: data.forecast_comparison.map((r) => Number(r.MAE)),
                marker: {
                  color: data.forecast_comparison.map((r) =>
                    r.model === "M1" ? "#e99536" : "#2256c7",
                  ),
                },
                hovertemplate: "%{x}<br>MAE %{y:.3f}<extra></extra>",
              },
            ]}
            description="Менше — краще. Чотиритижневе середнє — обраний історичний орієнтир; найкращий фінальний результат попереднього тижня не використано для повторного вибору."
          />
          <div className="chart-grid">
            <Chart
              title="Факт та історичні оцінки наступного тижня"
              ylabel="Офіційні початки"
              data={["actual", "B1", "M1"].map((m) => ({
                type: "scatter",
                mode: "lines",
                name: m === "actual" ? "Факт" : methods[m],
                x: hist(m === "actual" ? "B1" : m).map((r) =>
                  String(r.week_start),
                ),
                y: hist(m === "actual" ? "B1" : m).map((r) =>
                  Number(r[m === "actual" ? "actual" : "prediction"]),
                ),
              }))}
              description="Збережені ретроспективні оцінки, не актуальний прогноз."
            />
            <Chart
              title="Абсолютні помилки протягом перевірки"
              ylabel="Тривоги / тиждень"
              data={["B1", "M1"].map((m) => ({
                type: "scatter",
                mode: "lines",
                name: methods[m],
                x: hist(m).map((r) => String(r.week_start)),
                y: hist(m).map((r) => Number(r.absolute_error)),
              }))}
            />
          </div>
          <h3>Окрема перевірка повідомлених категорій · Task 006.1</h3>
          <p>
            36 фінальних тижнів до 14.09.2026. 21 і 28 вересня не оцінювалися
            через несвоєчасно завершені попередні мітки. Це коротший період і
            інша ціль, ніж у Task 006.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Категорія</th>
                  <th>Висновок</th>
                  <th>MAE орієнтира</th>
                  <th>MAE моделі</th>
                </tr>
              </thead>
              <tbody>
                {data.forecastability_by_category.map((r) => (
                  <tr key={String(r.category)}>
                    <td>{categories[String(r.category)]}</td>
                    <td>
                      <span className="state">
                        {decisions[String(r.decision)]}
                      </span>
                    </td>
                    <td>{num(r.baseline_MAE, 3)}</td>
                    <td>
                      {r.candidate_tested
                        ? num(r.candidate_MAE, 3)
                        : "Не тестувалася"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="caption">
            Для БПЛА інтервал переваги включає нуль; для балістики модель не
            запускалася за правилом навчального відбору. П’ять категорій не
            пройшли перевірку даних. Таксономію створено ретроспективно, включно
            з 2026: незалежна перспективна валідація відсутня.
          </p>
        </section>
        <section id="methodology">
          {sectionTitle(5, "Методологія та межі висновків")}
          {[
            [
              "Джерела та незалежність",
              "Kyiv Digital задає офіційні інтервали; наданий Telegram HTML-архів дає контекст. Збіг із поточним офіційним експортом підтверджує тотожність джерела, не незалежну істину. Волонтерські архіви можуть мати спільне походження.",
            ],
            [
              "Час, сезонні зміни та DST",
              "На 28 реальних прикладах перевірено, що Telegram-годинник інтерпретується як Europe/Kyiv, а фіксований +02:00 експорту не коригується сезонно. Оригінальні значення збережені. Один неоднозначний кінець офіційного інтервалу та вісім Telegram-часів не отримують вигаданого моменту.",
            ],
            [
              "Контекстне віднесення та експериментальна v1.6",
              "Словники географії й загроз, контекст повідомлень та часові межі пов’язують маркери із тривогою. Джерельний підтип і невизначеність збережені в дослідженні. Багатоміткова класифікація не перевіряє фізичний тип зброї. Незалежна точність не виміряна.",
            ],
            [
              "Відсутні дані та зміни режиму",
              "Невідома категорія, відсутній текст та період поза Telegram-покриттям — різні стани. Відсутність маркера не є відсутністю загрози. Жовті й червоні попередження враховані; попередні рівні не домислюються.",
            ],
            [
              "Що означає фінальний висновок",
              "У перевірених даних і методах немає стабільно продемонстрованої оперативної прогностичної переваги. Це обмежений ретроспективний висновок; він не доводить фізичну непередбачуваність. Dashboard не замінює офіційних попереджень.",
            ],
          ].map(([title, text]) => (
            <details key={title}>
              <summary>{title}</summary>
              <p>{text}</p>
            </details>
          ))}
          <div className="links">
            {[
              [
                "Task 005 · часовий аналіз",
                "reports/temporal_analysis/temporal_analysis_report.md",
              ],
              [
                "Task 005.1 · зовнішня перевірка",
                "reports/external_validation/external_validation_report.md",
              ],
              [
                "Task 006 · прогнозованість",
                "reports/forecastability_validation/forecastability_report.md",
              ],
              [
                "Task 006.1 · окремі категорії",
                "reports/threat_forecastability/threat_forecastability_report.md",
              ],
              [
                "Класифікація v1.6",
                "review_downloads/task0049/time_series_handoff.md",
              ],
              ["Джерела та методологія", "docs/DATA_SOURCES.md"],
            ].map(([title, path]) => (
              <a key={path} href={repo + path}>
                {title} ↗
              </a>
            ))}
            <a href="https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal">
              Офіційний набір Kyiv Digital ↗
            </a>
            <a href={`${import.meta.env.BASE_URL}data/manifest.json`}>
              Версія та контрольні суми агрегатів ↗
            </a>
          </div>
        </section>
        <MythLab />
      </main>
      <footer>
        <b>Київ · Air Alert Research</b>
        <span>Статичний дослідницький зріз · без оперативних прогнозів</span>
        <a href="https://github.com/OlenaAI18/KSHE_alert_test">
          Код та звіти ↗
        </a>
      </footer>
    </>
  );
}
// Future presentation extensions belong outside the frozen aggregate loader; no chat service is instantiated.
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
