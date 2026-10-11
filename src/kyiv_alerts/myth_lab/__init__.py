"""Frozen, descriptive Myth Lab aggregates; no operational forecast or source edits."""
from datetime import date, datetime, time, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

VERDICTS = {'not_supported', 'partially_supported', 'inconclusive', 'insufficient_data'}
TITLES = [
    'Чи справді Росія приурочує обстріли до сакральних дат Путіна?',
    'Чи атакують Україну частіше на українські свята?',
    'Чи правда, що дронові тривоги переважно нічні?',
    'Чи частіше атакують на вихідних?',
    'Чи буває затишшя перед бурею?',
    'Чи посилюються обстріли після мирних переговорів?',
    'Якщо вчора було багато тривог, сьогодні теж буде багато?',
]


def night_minutes(start, end, start_hour=22, end_hour=6):
    """Intersect half-open UTC instants with local nightly intervals; honor DST."""
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError('Resolved aware interval required')
    zone = ZoneInfo('Europe/Kyiv')
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    day = start.astimezone(zone).date() - timedelta(days=1)
    last = end.astimezone(zone).date()
    total = 0.0
    while day <= last:
        low = datetime.combine(day, time(start_hour), zone).astimezone(timezone.utc)
        high = datetime.combine(day + timedelta(days=1), time(end_hour), zone).astimezone(timezone.utc)
        total += max(0, (min(end, high) - max(start, low)).total_seconds()) / 60
        day += timedelta(days=1)
    return total


def calendar_dates(entries, first_year=2022, last_year=2026):
    return sorted((date.fromisoformat(f'{year}-{r["month_day"]}'), r['label_uk'])
                  for year in range(first_year, last_year + 1) for r in entries)


def complete_days(rows):
    """No compressed calendar: unknown/boundary days absent, never fake zeros."""
    low, high = date(2023, 10, 9), date(2023, 10, 15)
    return {r['date']: r for r in rows
            if not r['source_boundary_day'] and not r['unresolved_interval_day']
            and not low <= r['date'] <= high}


def event_comparison(daily, events, offsets, radius=0, excluded_dates=()):
    excluded = set(excluded_dates)
    event_windows = {d + timedelta(days=i) for d, _ in events for i in range(-radius, radius + 1)}
    results, omitted = [], []
    for event, label in events:
        window = [event + timedelta(days=i) for i in range(-radius, radius + 1)]
        if not all(d in daily for d in window):
            omitted.append({'date': str(event), 'reason': 'event window unavailable'}); continue
        controls = []
        for offset in offsets:
            center = event + timedelta(days=offset)
            days = [center + timedelta(days=i) for i in range(-radius, radius + 1)]
            if center.month != event.month or center.year != event.year:
                continue
            if all(d in daily and d not in excluded and d not in event_windows for d in days):
                controls.append(days)
        if not controls:
            omitted.append({'date': str(event), 'reason': 'no complete non-event same-month controls'}); continue
        event_rate = mean(daily[d]['all_record_starts'] for d in window)
        control_rate = mean(mean(daily[d]['all_record_starts'] for d in days) for days in controls)
        results.append({'date':str(event), 'label_uk':label, 'event_starts_per_day':event_rate,
                        'control_starts_per_day':control_rate, 'difference':event_rate-control_rate,
                        'control_window_count':len(controls), 'control_centers':[str(w[radius]) for w in controls]})
    return {'events':results, 'excluded_events':omitted, 'event_count':len(results),
            'event_mean':mean(r['event_starts_per_day'] for r in results) if results else None,
            'control_mean':mean(r['control_starts_per_day'] for r in results) if results else None,
            'paired_difference':mean(r['difference'] for r in results) if results else None}


def before_after(daily, events, width):
    rows, omitted = [], []
    for entry in events:
        d = date.fromisoformat(entry['date'])
        before = [d-timedelta(days=i) for i in range(1,width+1)]
        after = [d+timedelta(days=i) for i in range(1,width+1)]
        if not all(x in daily for x in before+after):
            omitted.append(str(d)); continue
        a, b = mean(daily[x]['all_record_starts'] for x in before), mean(daily[x]['all_record_starts'] for x in after)
        rows.append({'date':str(d), 'before':a, 'after':b, 'difference':b-a})
    return {'window_days':width, 'event_count':len(rows), 'events':rows, 'excluded_events':omitted,
            'before_mean':mean(r['before'] for r in rows) if rows else None,
            'after_mean':mean(r['after'] for r in rows) if rows else None,
            'difference':mean(r['difference'] for r in rows) if rows else None}


def calm_comparison(daily, length=3, threshold=1):
    paired=[]
    monthly={}
    for d,r in sorted(daily.items()):
        previous=[d-timedelta(days=i) for i in range(1,length+1)]
        if not all(x in daily for x in previous): continue
        row={'month':r['month'], 'calm':sum(daily[x]['all_record_starts'] for x in previous)<=threshold,
             'count':r['all_record_starts'], 'year':d.year}
        paired.append(row);monthly.setdefault(r['month'],[]).append(row)
    a=[r['count'] for r in paired if r['calm']];b=[r['count'] for r in paired if not r['calm']]
    differences=[]
    for rows in monthly.values():
        one=[r['count'] for r in rows if r['calm']];other=[r['count'] for r in rows if not r['calm']]
        if one and other:differences.append(mean(one)-mean(other))
    yearly=[]
    for year in sorted({r['year'] for r in paired}):
        one=[r['count'] for r in paired if r['year']==year and r['calm']];other=[r['count'] for r in paired if r['year']==year and not r['calm']]
        yearly.append({'year':year,'calm_days':len(one),'other_days':len(other),'difference':mean(one)-mean(other) if one and other else None})
    return {'preceding_days':length,'preceding_max_total_starts':threshold,'calm_days':len(a),'other_days':len(b),
            'after_calm_mean':mean(a) if a else None,'after_other_mean':mean(b) if b else None,
            'month_adjusted_difference':mean(differences) if differences else None,'matched_month_count':len(differences),'yearly':yearly}
