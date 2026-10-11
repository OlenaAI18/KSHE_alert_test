"""Read-only provenance validation, ranked diagnostic evidence and period tables."""
from collections import Counter, defaultdict
import statistics
from .core import *
from .catalog import FAMILIES, diagnostic_matches
from kyiv_alerts.classification.pipeline import unique_index
from kyiv_alerts.integration.__main__ import validate_links, validate_h2


def prepare(alerts,messages,links,coverage,features,markers):
    validate_h2(messages);validate_links(links,coverage,alerts,messages)
    am=unique_index(alerts,'alert_id');fm=unique_index(features,'alert_id');cm=unique_index(coverage,'alert_id')
    mm=unique_index([m for m in messages if m['message_id'] is not None],'message_id')
    if set(am)!=set(fm) or set(am)!=set(cm):raise ValueError('Official/feature/coverage alert IDs differ')
    expected=('v1.1','kyiv-geography-v1.1','v1.2-reviewed-rules')
    for f in features:
        if tuple(f[k] for k in ('dictionary_version','geography_dictionary_version','classification_version'))!=expected:
            raise ValueError('Current reviewed v1.2 inputs required; refusing older classification')
        for k in ['start_time','end_time','duration_minutes']:
            if f[k]!=am[f['alert_id']][k]:raise ValueError('Official feature field changed: '+k)
        for k in ['coverage_status','historical_range_relation','telegram_message_count','telegram_text_message_count']:
            if f[k]!=cm[f['alert_id']][k]:raise ValueError('Coverage feature field changed: '+k)
    pairs={(l['alert_id'],l['message_id']) for l in links}
    evidence=defaultdict(list);keys=set()
    for m in markers:
        pair=m['alert_id'],m['message_id']
        if pair not in pairs:raise ValueError('Candidate is not Task 003 linked')
        if tuple(m[k] for k in ('dictionary_version','geography_dictionary_version','classification_version'))!=expected:raise ValueError('Stale marker version')
        source=mm[m['message_id']]
        for k in ['source_file','source_message_index']:
            if m[k]!=source[k]:raise ValueError('Marker provenance mismatch')
        if source['text'][m['match_start']:m['match_end']]!=m['matched_text']:raise ValueError('Marker source span changed')
        key=(*pair,m['rule_id'],m['match_start'],m['match_end'])
        if key in keys:raise ValueError('Duplicate candidate')
        keys.add(key);evidence[pair].append(m)
    records=[];byalert=defaultdict(list)
    for l in sorted(links,key=lambda l:(l['alert_start_time'],l['message_time'],l['message_id'])):
        source=mm[l['message_id']];aid=l['alert_id'];f=fm[aid]
        r=dict(source,alert_id=aid,alert_start_time=f['start_time'],population=population(f),period=period_for(f['start_time']),
               current_classification=f['threat_combination'],current_classification_status=f['classification_status'],markers=evidence[(aid,source['message_id'])])
        byalert[aid].append(r)
        if source['text'] and source['text'].strip():
            r['normalized_text']=normalize_text(source['text']);records.append(r)
    for f in features:
        rows=byalert[f['alert_id']]
        count=sum(bool(r['text'] and r['text'].strip()) for r in rows)
        if cm[f['alert_id']]['deterministic_message_count']!=len(rows) or cm[f['alert_id']]['deterministic_text_message_count']!=count:raise ValueError('Linked counts mismatch')
        candidates=sum(len(r['markers']) for r in rows)
        if candidates!=f['candidate_marker_count']:raise ValueError('Alert candidate count mismatch')
        accepted=[m for r in rows for m in r['markers'] if m['accepted_for_aggregation']]
        for c in CATEGORIES[:-1]:
            if f[c] is not None and f[c] != any(m['category']==c for m in accepted):raise ValueError('Accepted category mismatch')
        if f['marker_evidence_count'] is not None and f['marker_evidence_count']!=len(accepted):raise ValueError('Accepted evidence count mismatch')
    return records,byalert,fm


def baseline(features):
    elig=[f for f in features if eligible(f)]
    return dict(total_alerts=len(features),eligible_alerts=len(elig),eligible_alerts_with_text=sum((f['telegram_text_message_count'] or 0)>0 for f in elig),
      classified_alerts=sum(not f['unknown'] for f in features),text_unclassified_alerts=sum(population(f)=='text_unclassified' for f in features),
      classified_yield=sum(not f['unknown'] for f in elig)/len(elig) if elig else None,
      populations=dict(Counter(population(f) for f in features)),classification_status_counts=dict(Counter(f['classification_status'] for f in features)),
      per_category_alert_counts={c:sum(f[c] is True for f in features) for c in CATEGORIES[:-1]})


def message_diagnostics(records):
    out={}
    for pop in POPULATIONS[:3]:
        rows=[r for r in records if r['population']==pop]
        tests={
          'with_lexical_candidates':lambda r:bool(r['markers']),
          'without_lexical_candidates':lambda r:not r['markers'],
          'with_previously_rejected_candidates':lambda r:any(not m['accepted_for_aggregation'] for m in r['markers']),
          'with_geography_exclusions':lambda r:any(x.startswith('geography_') for x in reasons(r['markers'])),
          'with_uncertain_context_exclusions':lambda r:'context_uncertain' in reasons(r['markers']),
          'with_negated_or_cancelled_candidates':lambda r:'context_negated_or_cancelled' in reasons(r['markers']),
          'with_historical_candidates':lambda r:'context_historical_or_summary' in reasons(r['markers']),
          'apparent_shorthand_for_review':lambda r:any(p in r.get('pattern_ids',[]) for p in ('P01','P02','P03','P04','P06','P07','P13')),
        }
        out[pop]=dict(total_text_messages=len({r['message_id'] for r in rows}),total_alerts=len({r['alert_id'] for r in rows}),
             subsets={k:dict(unique_messages=len({r['message_id'] for r in rows if test(r)}),unique_alerts=len({r['alert_id'] for r in rows if test(r)})) for k,test in tests.items()},
             exclusion_reason_messages={reason:len({r['message_id'] for r in rows if reason in reasons(r['markers'])}) for reason in sorted({reason for r in rows for reason in reasons(r['markers'])})})
    return out


def representative(rows,n=5):
    """Cover dates/alerts/texts rather than selecting a burst of duplicate messages."""
    ordered=sorted(rows,key=lambda r:(r['message_time'],r['alert_id'],r['message_id']))
    if len(ordered)<=n:return ordered
    selected=[];seen=set();seenalerts=set()
    # Spread across time, prefer unique alerts and source texts.
    probes=[ordered[round(i*(len(ordered)-1)/(n-1))] for i in range(n)] if n>1 else [ordered[0]]
    for r in probes+ordered:
        key=(r['message_id'],r['alert_id'])
        if key in seen or any(x['normalized_text']==r['normalized_text'] for x in selected):continue
        if r['alert_id'] in seenalerts and len(seenalerts)<min(n,len({x['alert_id'] for x in rows})):continue
        selected.append(r);seen.add(key);seenalerts.add(r['alert_id'])
        if len(selected)==n:break
    # A repeated phrase still needs 3–5 source records when available.
    for r in ordered:
        if len(selected)==min(n,len(ordered)):break
        key=(r['message_id'],r['alert_id'])
        if key not in seen:selected.append(r);seen.add(key)
    return selected


def evidence_example(pattern_id,r):
    return dict(pattern_id=pattern_id,alert_id=r['alert_id'],message_id=r['message_id'],timestamp=r['message_time'],original_timestamp=r['message_time_original'],
      original_text=r['text'],current_classification=r['current_classification'],original_classification_status=r['current_classification_status'],population=r['population'],
      candidate_dictionary_hits=[{k:m[k] for k in ('rule_id','category','subtype','matched_text','evidence_status','geography','accepted_for_aggregation','exclusion_reason')} for m in r['markers']],
      exclusion_reasons=reasons(r['markers']),source_file=r['source_file'],source_message_index=r['source_message_index'],
      requires_context_review=pattern_id in {'P01','P03','P04','P05','P09','P10','P11','P13'},human_decision='',review_notes='')


def discover_families(records,geography):
    matched=defaultdict(list)
    for r in records:
        r['pattern_ids']=diagnostic_matches(r,geography)
        if r['population'] in POPULATIONS[1:3]:
            for pid in r['pattern_ids']:matched[pid].append(r)
    patterns=[];examples=[];assign=[]
    for pid,ptype,phrase,alts,action,interpretation,_ in FAMILIES:
        rows=matched[pid]
        if not rows:continue
        sample=representative(rows)
        hitrows=[m for r in rows for m in r['markers']]
        support=len({r['alert_id'] for r in rows})
        unclassified=len({r['alert_id'] for r in rows if r['population']=='text_unclassified'})
        coverage=dict(messages_with_any_candidate=len({r['message_id'] for r in rows if r['markers']}),messages_with_accepted_candidate=len({r['message_id'] for r in rows if any(m['accepted_for_aggregation'] for m in r['markers'])}),
                 existing_rule_ids=sorted({m['rule_id'] for m in hitrows}),specificity='diagnostic match, not an approved category')
        patterns.append(dict(pattern_id=pid,pattern_type=ptype,representative_phrase=phrase,alternative_phrases=alts,
             unique_alert_support=support,unique_message_support=len({r['message_id'] for r in rows}),text_unclassified_alert_support=unclassified,
             other_only_alert_support=len({r['alert_id'] for r in rows if r['population']=='other_only'}),
             first_seen=min(r['message_time'] for r in rows),last_seen=max(r['message_time'] for r in rows),
             period_distribution={p:dict(unique_alerts=len({r['alert_id'] for r in rows if r['period']==p}),unique_messages=len({r['message_id'] for r in rows if r['period']==p})) for p in PERIODS},
             monthly_distribution={m:len({r['alert_id'] for r in rows if r['alert_start_time'].astimezone(KYIV).strftime('%Y-%m')==m}) for m in sorted({r['alert_start_time'].astimezone(KYIV).strftime('%Y-%m') for r in rows})},
             current_dictionary_coverage=coverage,common_exclusion_reasons=dict(Counter(x for r in rows for x in reasons(r['markers']))),
             candidate_interpretation=interpretation,representative_alert_ids=[r['alert_id'] for r in sample],representative_message_ids=[r['message_id'] for r in sample],representative_texts=[r['text'] for r in sample],
             proposed_action=action,human_decision='',review_notes=''))
        examples.extend(evidence_example(pid,r) for r in sample)
        assign.extend(dict(pattern_id=pid,alert_id=r['alert_id'],message_id=r['message_id'],population=r['population']) for r in rows)
    patterns.sort(key=lambda p:(-p['unique_alert_support'],-p['text_unclassified_alert_support'],-p['unique_message_support'],p['pattern_id']))
    return patterns,examples,assign


def period_comparison(features,records,patterns,distinctive):
    out=[]
    prior_text_den=0
    prior_support=Counter()
    for period in PERIODS:
        rows=[f for f in features if period_for(f['start_time'])==period]
        elig=[f for f in rows if eligible(f)];text=[f for f in elig if (f['telegram_text_message_count'] or 0)>0]
        density=[f['telegram_message_count'] for f in elig]
        counts=Counter(population(f) for f in rows)
        ranked=sorted(patterns,key=lambda p:(-p['period_distribution'][period]['unique_alerts'],p['pattern_id']))
        short=[r for r in records if r['period']==period and len(r['normalized_text'].split())<=3]
        place=[r for r in records if r['period']==period and 'P01' in r.get('pattern_ids',[])]
        newly=[]
        for p in patterns:
            current=p['period_distribution'][period]['unique_alerts']
            ratio=((current+.5)/(len(text)+1))/((prior_support[p['pattern_id']]+.5)/(prior_text_den+1)) if prior_text_den else None
            if current>=3 and ratio is not None and ratio>=2:
                newly.append(dict(pattern_id=p['pattern_id'],unique_alert_support=current,smoothed_rate_ratio_vs_prior=float(ratio),prior_alert_support=prior_support[p['pattern_id']],prior_alerts_with_text=prior_text_den))
        newly.sort(key=lambda x:(-x['unique_alert_support'],-x['smoothed_rate_ratio_vs_prior'],x['pattern_id']))
        out.append(dict(period=period,total_alerts=len(rows),eligible_alerts=len(elig),alerts_with_text=len(text),
           specifically_classified_alerts=counts['specific_classified'],other_only_alerts=counts['other_only'],text_unclassified_alerts=counts['text_unclassified'],unavailable_or_unresolved_alerts=counts['unavailable_or_unresolved'],
           linked_text_message_count=sum((f['telegram_text_message_count'] or 0) for f in elig),
           mean_linked_messages_per_eligible_alert=statistics.mean(density) if density else None,median_linked_messages_per_eligible_alert=statistics.median(density) if density else None,
           most_distinctive_candidate_phrases=distinctive.get(period,[]),newly_prominent_candidates=newly,
           short_message_unique_alerts=len({r['alert_id'] for r in short}),short_message_unique_messages=len({r['message_id'] for r in short}),
           standalone_place_unique_alerts=len({r['alert_id'] for r in place}),standalone_place_unique_messages=len({r['message_id'] for r in place}),
           short_message_alert_share=len({r['alert_id'] for r in short})/len(text) if text else None,standalone_place_alert_share=len({r['alert_id'] for r in place})/len(text) if text else None,
           prominent_patterns=[dict(pattern_id=p['pattern_id'],unique_alert_support=p['period_distribution'][period]['unique_alerts'],share_of_alerts_with_text=p['period_distribution'][period]['unique_alerts']/len(text) if text else None) for p in ranked[:8] if p['period_distribution'][period]['unique_alerts']],
           observed_last_official_alert_start=max((f['start_time'] for f in rows),default=None),observed_last_official_alert_end=max((f['end_time'] for f in rows if f['end_time']),default=None),
           observed_first_linked_timestamp=min((r['message_time'] for r in records if r['period']==period),default=None),observed_last_linked_timestamp=max((r['message_time'] for r in records if r['period']==period),default=None),
           partial_period=period in {PERIODS[0],PERIODS[-1]},comparison_note='Partial October official alert-start window through Oct 4, with final interval ending Oct 5 Kyiv time; Telegram continues through Oct 10. Compare text-alert-normalized support, not full-month totals.' if period==PERIODS[-1] else 'Telegram history begins Aug 17, 2023.' if period==PERIODS[0] else 'Fixed requested comparison period; reporting density is observational.'))
        prior_text_den+=len(text)
        for p in patterns:prior_support[p['pattern_id']]+=p['period_distribution'][period]['unique_alerts']
    return out


def october_review(features,byalert):
    out=[]
    for f in features:
        if period_for(f['start_time'])!=PERIODS[-1]:continue
        rows=[r for r in byalert[f['alert_id']] if r.get('normalized_text') is not None]
        markers=[m for r in rows for m in r['markers']]
        # Save every chronological linked message in a separate evidence table.
        inform=sorted(rows,key=lambda r:(-len(r['markers']),-len(r.get('pattern_ids',[])),r['message_time'],r['message_id']))
        examples=representative(inform) if inform else []
        out.append(dict(alert_id=f['alert_id'],start_time=f['start_time'],end_time=f['end_time'],linked_text_count=len(rows),
          current_classification=f['threat_combination'],original_classification_status=f['classification_status'],population=population(f),historically_eligible=eligible(f),
          candidate_marker_count=len(markers),candidate_exclusion_reasons=dict(Counter(reason for r in rows for reason in reasons(r['markers']))),
          top_pattern_ids=[k for k,v in Counter(p for r in rows for p in r.get('pattern_ids',[])).most_common(8)],
          representative_message_ids=[r['message_id'] for r in examples],representative_message_texts=[r['text'] for r in examples],
          messages_without_lexical_candidates=sum(not r['markers'] for r in rows),
          descriptive_content_flags=sorted({flag for r in rows for flag,test in [
             ('possible_operational_shorthand_requires_review',any(p in r.get('pattern_ids',[]) for p in ('P01','P02','P03','P04','P06','P07','P09'))),
             ('tracking_or_terminal_status',any(p in r.get('pattern_ids',[]) for p in ('P05','P11'))),
             ('fundraising_or_commentary', 'P14' in r.get('pattern_ids',[])),
             ('historical_or_summary_candidate',any(m['evidence_status']=='historical_or_summary' for m in r['markers']))] if test}),
          review_status='',human_decision='',review_notes=''))
    return sorted(out,key=lambda r:(r['start_time'],r['alert_id']))
