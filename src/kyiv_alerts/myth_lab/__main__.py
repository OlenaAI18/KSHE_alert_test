"""Generate isolated Myth Lab reports and public aggregates from frozen inputs."""
import argparse
import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo
import pyarrow.parquet as pq
from . import (TITLES, VERDICTS, night_minutes, calendar_dates, complete_days,
               event_comparison, before_after, calm_comparison)


def run(root, report=None, public=None):
    root=Path(root);report=report or root/'reports/myth_lab';public=public or root/'dashboard/public/data'
    inputs={}
    def load(path, columns=None):
        p=root/path;inputs[path]=hashlib.sha256(p.read_bytes()).hexdigest()
        if p.suffix=='.parquet':return pq.read_table(p,columns=columns).to_pylist()
        if p.suffix=='.json':return json.loads(p.read_text(encoding='utf-8'))
        return list(csv.DictReader(p.open(encoding='utf-8-sig')))
    cfg=load('config/myth_lab_v1.json')
    daily_rows=load('data/processed/temporal_analysis/daily_alert_metrics.parquet')
    fact=load('data/processed/temporal_analysis/alert_analysis_fact.parquet',
              ['start_time','end_time','valid_interval','eligible','year','shahed_uav','jet_uav'])
    v15=load('data/processed/classification_v1_5/alert_threat_features.parquet',
             ['start_time','end_time','shahed_uav','jet_uav'])
    temporal=load('reports/temporal_analysis/temporal_summary.json')
    stats=load('reports/temporal_analysis/statistical_tests.csv')
    sources=load('reports/myth_lab/source_register.csv')
    source_access=load('reports/myth_lab/source_access.json')
    assert sum(r['all_record_starts'] for r in daily_rows)==temporal['baseline']['official']==2594
    daily=complete_days(daily_rows)
    symbolic=calendar_dates(cfg['symbolic_dates']);holidays=calendar_dates(cfg['ukrainian_holidays'])
    control_exclusions=set(d for d,_ in calendar_dates([{'month_day':d,'label_uk':''} for d in cfg['control_holiday_exclusions_month_day']]))
    control_exclusions.update(date.fromisoformat(d) for d in cfg['control_moving_holiday_exclusions'])
    results=[]
    def card(index, tested, metrics, labels, values, ylabel, headline, state, limitations, methodology):
        assert state in VERDICTS
        result={'myth_id':f'myth_{index}','title_uk':TITLES[index-1],'short_question_uk':TITLES[index-1],
                'what_is_tested_uk':tested,'metric_summary':metrics,
                'chart_data':{'labels':labels,'values':values,'ylabel_uk':ylabel},
                'headline_result_uk':headline,'verdict_label':{'not_supported':'Не підтримано цією перевіркою',
                'partially_supported':'Частково підтримано','inconclusive':'Висновок невизначений','insufficient_data':'Недостатньо даних'}[state],
                'verdict_state':state,'limitations_uk':limitations,'methodology_note_uk':methodology}
        results.append(result)
    def fmt(v):return 'недоступно' if v is None else f'{v:.2f}'.replace('.',',')
    for index,events,name,exclusions in [(1,symbolic,'символічних дат',()),(2,holidays,'вибраних свят',control_exclusions)]:
        primary=event_comparison(daily,events,cfg['matched_control_offsets_days'],0,exclusions)
        window=event_comparison(daily,events,cfg['matched_control_offsets_days'],cfg['event_window_radius_days'],exclusions)
        card(index,'Початки офіційних київських тривог на вибрані календарні дати та у вікні ±1 день.',
             {'primary':primary,'window_sensitivity':window},['Дата події','Зіставні контрольні дні'],
             [primary['event_mean'],primary['control_mean']],'Початки / день',
             f"На {primary['event_count']} датах: {fmt(primary['event_mean'])} тривоги/день проти {fmt(primary['control_mean'])} у контролі. Мотив вибору дат не встановлено.",
             'inconclusive' if primary['event_count'] else 'insufficient_data',
             ['Київські попередження не є всіма обстрілами України. Намір або причинність не вимірюються.',
              'Мала вибірка, залежні повторення та зміни інтенсивності; контрольні дні можуть повторюватися між подіями.',
              'Три символічні дати — вибрана гіпотеза, не вичерпний перелік «сакральних» дат.' if index==1 else
              'Шість стабільних свят — підмножина календаря. Рухомі свята й зміни законодавства не тестуються; виключаються з контролю консервативно.'],
             'Контроль: той самий день тижня й місяць/рік за зсувами ±7/14/21/28 днів. Спочатку середнє контролів для кожної події, потім рівна вага подій. Окремо показано ±1 день. Немає тесту статистичної значущості.')
    zone=ZoneInfo(cfg['timezone'])
    def night_stats(rows):
        selected=[r for r in rows if r['end_time'] is not None and (r['shahed_uav'] is True or r['jet_uav'] is True)]
        total=sum((r['end_time']-r['start_time']).total_seconds()/60 for r in selected)
        overlaps=[night_minutes(r['start_time'],r['end_time'],cfg['night_start_hour'],cfg['night_end_hour']) for r in selected]
        starts=sum(r['start_time'].astimezone(zone).hour>=cfg['night_start_hour'] or r['start_time'].astimezone(zone).hour<cfg['night_end_hour'] for r in selected)
        return {'unique_alerts':len(selected),'night_start_count':starts,'night_start_share':starts/len(selected) if selected else None,
                'night_intersection_count':sum(x>0 for x in overlaps),'night_intersection_share':sum(x>0 for x in overlaps)/len(selected) if selected else None,
                'total_alert_minutes':total,'night_alert_minutes':sum(overlaps),'night_minute_share':sum(overlaps)/total if total else None}
    night=night_stats(fact)
    annual=[{'year':year,**night_stats([r for r in fact if r['year']==year])} for year in [2023,2024,2025,2026]]
    exposure_start=datetime.fromisoformat(temporal['telegram_first']);exposure_end=datetime.fromisoformat(temporal['official_source_last_end'])
    exposure_minutes=(exposure_end-exposure_start).total_seconds()/60
    night['calendar_exposure_share']=night_minutes(exposure_start,exposure_end)/exposure_minutes
    night['yearly']=annual;night['v15_sensitivity']=night_stats(v15)
    card(3,'Частка фактичних хвилин тривог із БПЛА-маркером, що припадає на 22:00–06:00 у Києві.',night,
         ['Ніч · хвилини тривог','День · хвилини тривог'],[100*night['night_minute_share'],100*(1-night['night_minute_share'])],'% хвилин',
         f"За весь архів — {fmt(100*night['night_minute_share'])}% хвилин уночі, але у 2026 — {fmt(100*annual[-1]['night_minute_share'])}%. Це не стале правило. Нічні початки за весь архів: {fmt(100*night['night_start_share'])}%.",
         'partially_supported' if night['night_minute_share']>0.5 else 'not_supported',
         ['Це повідомлений контекст v1.6, не підтверджені дронові атаки; generic UAV не підтверджує Shahed.',
          'Класифікація та обсяг повідомлень можуть залежати від часу доби й тривалості. Категорії можуть змішуватися.',
          'Частка хвилин, початків і перетинів — різні показники; 22:00–06:00 не є астрономічною ніччю.'],
         'Об’єднання shahed_uav або jet_uav без подвійного рахунку. Інтервали перетинаються з нічними вікнами; хвилини рахуються за UTC, із сезонним Europe/Kyiv. Окремо річні показники, v1.5 та частка нічної календарної експозиції.')
    weekend=[r['all_record_starts'] for d,r in daily.items() if d.weekday()>=5]
    weekday=[r['all_record_starts'] for d,r in daily.items() if d.weekday()<5]
    months=[]
    for month in sorted({r['month'] for r in daily.values()}):
        a=[r['all_record_starts'] for d,r in daily.items() if r['month']==month and d.weekday()>=5]
        b=[r['all_record_starts'] for d,r in daily.items() if r['month']==month and d.weekday()<5]
        if len(a)>=4 and len(b)>=10:months.append({'month':month,'weekend_mean':mean(a),'weekday_mean':mean(b),'difference':mean(a)-mean(b)})
    weekend_stats={'weekend_days':len(weekend),'weekday_days':len(weekday),'weekend_starts':sum(weekend),'weekday_starts':sum(weekday),
                   'weekend_mean':mean(weekend),'weekday_mean':mean(weekday),'month_adjusted_difference':mean(r['difference'] for r in months),'matched_month_count':len(months),'monthly':months}
    card(4,'Середня кількість початків офіційних київських тривог на суботу/неділю та будні.',weekend_stats,
         ['Вихідні','Будні'],[mean(weekend),mean(weekday)],'Початки / день',
         f"Вихідні: {fmt(mean(weekend))}; будні: {fmt(mean(weekday))} тривоги/день. Середня різниця всередині місяців: {fmt(weekend_stats['month_adjusted_difference'])}.",'inconclusive',
         ['Попередження не вимірюють усі атаки; причина вибору дня не встановлена.','Дні серійно залежні, режими змінюються; новий тест значущості не проводився.'],
         'Порівнюємо на один доступний календарний день, не загальні суми для 2 та 5 днів. Місячна поправка — рівновагове середнє різниць у місяцях із ≥4 вихідними та ≥10 буднями.')
    calm=calm_comparison(daily,cfg['calm_preceding_days'],cfg['calm_preceding_max_total_starts'])
    calm['zero_start_sensitivity']=calm_comparison(daily,cfg['calm_preceding_days'],cfg['calm_sensitivity_max_total_starts'])
    card(5,'Чи відрізняється наступний день після трьох днів із сумарно ≤1 початком тривоги.',calm,
         ['Після затишшя','Після інших 3 днів'],[calm['after_calm_mean'],calm['after_other_mean']],'Початки наступного дня',
         f"Після затишшя: {fmt(calm['after_calm_mean'])}; після інших періодів: {fmt(calm['after_other_mean'])}. Усередині місяців різниця змінює знак: +{fmt(calm['month_adjusted_difference'])}. Висновок залежить від порівняння.",'inconclusive',
         ['«Затишшя» означає мало записаних попереджень, не відсутність небезпеки.','Вікна перекриваються, спостереження залежні. Порівняння не є перспективно перевіреним прогнозом.','Не встановлено повноту нульових днів; тиждень без записів виключено.'],
         'Визначення зафіксоване до розрахунку: попередні 3 календарні дні, сумарно ≤1 старт. Ціль — наступний день. Чутливість: рівно 0 стартів; також різниця всередині місяців і за роками. Пропущені дні не стискаються.')
    negotiation=[before_after(daily,cfg['negotiations'],width) for width in cfg['negotiation_window_days']]
    primary=negotiation[0]
    card(6,'Початки київських тривог за 3 дні до й після трьох вибраних раундів переговорів у Стамбулі.',
         {'primary':primary,'seven_day_sensitivity':negotiation[1]},['3 дні до','3 дні після'],[primary['before_mean'],primary['after_mean']],'Початки / день',
         f"Лише {primary['event_count']} події: до — {fmt(primary['before_mean'])}, після — {fmt(primary['after_mean'])} тривоги/день. Причинного висновку немає.",
         'inconclusive' if primary['event_count'] else 'insufficient_data',
         ['Описове порівняння, не причинний доказ; переговори не призначаються випадково.','Лише три вибрані події, не повний календар дипломатії; добір і ширина вікна впливають на результат.','Немає даних про всі обстріли, цілі або фізичні пуски.'],
         '29.03.2022, 16.05.2025, 02.06.2025: дати підтверджено календарними джерелами. День події виключено; рівна вага подій; 7-денне вікно показано як чутливість, без вибору «кращого» результату.')
    raw=next(r for r in stats if r['test']=='daily_acf_lag_1' and r['block_length']=='14')
    adjusted=next(r for r in stats if r['test']=='within_month_residual_acf_lag_1')
    acf={'raw':{k:float(raw[k]) for k in ['effect','ci_low','ci_high']},
         'month_adjusted':{k:float(adjusted[k]) for k in ['effect','ci_low','ci_high']},'source':'Task005 statistical_tests.csv; 14-day raw CI'}
    card(7,'Кореляція кількості київських тривог сьогодні з попереднім днем із уже перевіреного Task005.',acf,
         ['Початковий ряд','Без місячного середнього'],[acf['raw']['effect'],acf['month_adjusted']['effect']],'Кореляція lag 1',
         f"Початкова кореляція {fmt(acf['raw']['effect'])}; після місячної поправки — {fmt(acf['month_adjusted']['effect'])}. Значна частина зв’язку описує зміну режимів.",'partially_supported',
         ['Місячне середнє вилучається ретроспективно й не доступне наперед.','Описова кореляція не гарантує прогнозу. Task006 не показав стабільної переваги моделі на фінальних 39 тижнях.','Це не правило для окремого дня й не порада про безпечний час.'],
         'Значення й дослідницькі 95% блокові інтервали перенесено дослівно з Task005. Нова кореляція не підміняє попередню методику; часткова підтримка стосується лише початкової описової залежності.')
    summary={'schema_version':1,'version':cfg['version'],'scope_uk':'Офіційні київські тривоги та повідомлені маркери загроз; не всі обстріли України.',
             'official_starts_reconciled':2594,'daily_observed_days':len(daily_rows),'daily_comparison_days':len(daily),
             'excluded_daily_days':len(daily_rows)-len(daily),'uav_unique_alerts':night['unique_alerts'],
             'verdict_counts':{state:sum(r['verdict_state']==state for r in results) for state in sorted(VERDICTS)},
             'inputs':inputs,'sources':[{k:r[k] for k in ['source_id','publisher','title','url','status']} for r in sources],
             'source_access':source_access,'new_significance_tests':False,'hosting_activated':False}
    report.mkdir(parents=True,exist_ok=True);public.mkdir(parents=True,exist_ok=True)
    def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    write(public/'myth_lab_results.json',results);write(public/'myth_lab_questions.json',[{'myth_id':r['myth_id'],'title_uk':r['title_uk']} for r in results]);write(public/'myth_lab_summary.json',summary)
    write(report/'myth_lab_summary.json',summary)
    report_text=['# Task007.1 — Myth Lab','\nStatus: COMPLETE FOR REVIEW. Seven separate descriptive checks; no physical-strike or causal claims. No prior research output modified.\n',
                 f'Official totals reconcile to2594; {len(daily)} / {len(daily_rows)} daily observations used for new comparisons. Source endpoints, unresolved-end day and no-record week withheld. No new significance tests.',
                 '\nSix fixed Ukrainian holidays are a selected stable subset; moving dates are conservative control exclusions only. Sources are calendrical provenance, not independent attack evidence. Rada HTTP503 and Reuters401 were not bypassed; usable cited secondary/dated journalism sources retrieved.\n']
    for r in results:
        report_text.extend([f"## {r['myth_id']} — {r['title_uk']}",r['headline_result_uk'],f"Verdict: `{r['verdict_state']}`",r['methodology_note_uk'],'\n'.join('- '+x for x in r['limitations_uk'])])
    report_text.append('\nDetailed per-event/window/year/version numeric results: dashboard/public/data/myth_lab_results.json. Definitions: config/myth_lab_v1.json; source_register.csv; methodology_notes.md. Public assets contain no raw Telegram texts/individual provenance.')
    (report/'myth_lab_report.md').write_text('\n\n'.join(report_text)+'\n',encoding='utf-8')
    return summary,results

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path.cwd());args=parser.parse_args()
    summary,_=run(args.root);print(json.dumps({k:summary[k] for k in ['official_starts_reconciled','uav_unique_alerts','daily_comparison_days','verdict_counts']},ensure_ascii=False))
