# Повітряні тривоги в Києві · дослідницький dashboard

Статичний український dashboard і відтворюваний Python-проєкт для дослідження
історії офіційних київських тривог та повідомленого контексту загроз, 2022–2026.

**Головний висновок:** перевірена регуляризована модель не показала стабільної
переваги на фінальній історичній вибірці над простими орієнтирами. Це не доводить
фізичну неможливість прогнозування. Проєкт не створює оперативних прогнозів і не
замінює офіційні попередження.

## Поточний результат

- 2 594 офіційні початки; 2 593 інтервали з визначеним кінцем.
- Медіанна тривалість 37,37 хвилини.
- 1 803 тривоги в Telegram-покритті; v1.6 класифікує 1 295 (71,82%).
- Класифікація експериментальна: покриття не є точністю, категорії перетинаються,
  невідома категорія не означає відсутність загрози.
- Сім розділів dashboard: основне дослідження та сім карток Myth Lab.

Дані є історичним зрізом: останній офіційний відбій — **05.10.2026 00:38:04 Kyiv**.
2022, 2026 та крайні місяці неповні. Жовті й червоні попередження враховані як
реальні тривоги. Публічний сайт ще не активований; push не запускає deployment.

## Запустити dashboard із репозиторію

Потрібен **Node.js 24**. Сирі джерела, Python і зовнішній API для перегляду не потрібні.

```sh
cd dashboard
npm ci
npm test
npm run build
npm run dev
```

Відкрийте локальну адресу, яку покаже Vite, на своєму комп’ютері. Для перевірки
зібраної версії: `npm run preview`. Базовий шлях — `/KSHE_alert_test/`.
`npm run build` перевіряє всі 15 публічних JSON, контрольні суми й узгодженість
показників перед компіляцією. Дані графіків bundled; runtime CDN відсутній.

[Інструкції dashboard і GitHub Pages](dashboard/README.md) ·
[Остання перевірка готовності](reports/release_readiness/release_readiness.md).
Публікацію погоджено 2026-10-11. Спроба deployment заблокована вимкненим
Pages та обмеженням доступу інтеграції (403). Потрібен вибір
**Settings → Pages → GitHub Actions** та ручний запуск workflow
**Publish approved research dashboard** на `main`. Перевірки push/PR не мають
повноважень публікувати сайт.

## Дослідницькі звіти

| Напрям | Звіт |
| --- | --- |
| Часова динаміка й сезонність | [Task 005](reports/temporal_analysis/temporal_analysis_report.md) |
| Зовнішня перевірка та межі інтерпретації | [Task 005.1](reports/external_validation/external_validation_report.md) |
| Історична перевірка прогнозованості | [Task 006](reports/forecastability_validation/forecastability_report.md) |
| Прогнозованість повідомлених категорій | [Task 006.1](reports/threat_forecastability/threat_forecastability_report.md) |
| Сім публічних гіпотез | [Myth Lab](reports/myth_lab/myth_lab_report.md) |
| Класифікація v1.6 | [Статус і обмеження](review_downloads/task0049/time_series_handoff.md) |

Task 006 перевіряє 39 фінальних тижнів; Task 006.1 — 36, без пізнього вересневого
хвоста. Myth Lab — окремі описові перевірки, не причинні докази. Узагальнена група
БПЛА не підтверджує Shahed; умовне «МіГ» не підтверджує конкретну модель.

## Python: розробка та відтворення

Пакет підтримує Python 3.11+; повне середовище й lockfiles перевірено на
**Python 3.12/Linux**. Для всього дослідницького workflow встановіть усі чотири набори:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.lock.txt -r requirements-analysis.lock.txt -r requirements-review.lock.txt -r requirements-temporal.lock.txt
python -m pip install -e . --no-deps
python -m pytest -q
```

**Повна Python-перевірка та регенерація результатів потребують локальних оригінальних
джерел і попередніх derived tables**, які не входять до Git. Fresh clone достатній
для dashboard, але не є повною приватною копією дослідницького workspace. Без цих
входів artifact-dependent тести можуть завершуватися помилкою; це не причина
вигадувати дані чи запускати новий аналіз автоматично.

[Команди відтворення всіх етапів](docs/REPRODUCTION.md) ·
[Джерела](docs/DATA_SOURCES.md) · [Методологія](docs/METHODOLOGY.md) ·
[Архітектура](docs/ARCHITECTURE.md) · [Рішення](docs/DECISIONS.md).

## Що зберігається де

| Каталог | Призначення |
| --- | --- |
| `dashboard/` | Frontend, тести, build gate та 15 публічних агрегованих JSON |
| `src/kyiv_alerts/`, `scripts/` | Python-парсинг, класифікація, дослідження, експортери |
| `config/`, `docs/` | Версії правил, календарі, методологія й рішення |
| `reports/` | Вибрані збережені звіти, перевірки та графіки |
| `review_downloads/` | Історичні Excel/CSV і ZIP для ручного дослідницького перегляду |
| `data/` | Локальні оригінали, normalized/derived дані; виключені з Git |

**Pages публікує лише `dashboard/dist`**, а не весь репозиторій. Public JSON не містять
Telegram-текстів чи індивідуального provenance. Раніше за вашим запитом опубліковані
review-файли можуть містити витяги повідомлень і часові лінії; це архів ручного
перегляду, не production dataset і не підтверджена істина. Не копіюйте його в
`dashboard/public`. Оригінальні Telegram-архіви, credentials і runtime caches не
входять до релізу. Архіви не переписуються для зміни історичних результатів.
