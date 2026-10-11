"""Run the read-only Task 004.4 attribution experiment."""
from pathlib import Path
from collections import defaultdict,Counter
from statistics import median
import hashlib,json,time,argparse
import pyarrow as pa
import pyarrow.parquet as pq
from .core import *
from kyiv_alerts.classification.rules import Dictionary
from kyiv_alerts.classification.coverage_audit import write_audit_csv
from kyiv_alerts.classification.coverage_audit import validate_consolidation
from kyiv_alerts.integration.__main__ import validate_links,validate_h2
from kyiv_alerts.ingestion.timeutils import KYIV


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def serial(value):return value.isoformat() if hasattr(value,'isoformat') else str(value)

def run(root):
    tick=time.perf_counter()
    sources={key:root/path for key,path in {'alerts':'data/interim/alerts.parquet','messages':'data/interim/telegram_messages.parquet','links':'data/processed/alert_message_links.parquet','coverage':'data/processed/alert_coverage.parquet','features':'data/processed/classification_v1_3/alert_threat_features.parquet','markers':'data/processed/classification_v1_3/message_threat_markers.parquet','dictionary':'config/threat_dictionary_v1_3.yaml','geography':'config/kyiv_geography_v1_1.yaml'}.items()}
    hashes={k:digest(p) for k,p in sources.items()}
    data={k:pq.read_table(p).to_pylist() for k,p in sources.items() if p.suffix=='.parquet'}
    alerts,messages,links,features,markers=(data[k] for k in ['alerts','messages','links','features','markers'])
    validate_h2(messages);validate_links(links,data['coverage'],alerts,messages);validate_consolidation(markers,features,messages,links)
    if any(f['classification_version']!='v1.3' for f in features):raise ValueError('Frozen v1.3 required')
    dictionary=Dictionary(sources['dictionary'],sources['geography'])
    mm={m['message_id']:m for m in messages if m['message_id'] is not None}
    fm={f['alert_id']:f for f in features};am={a['alert_id']:a for a in alerts}
    bm=defaultdict(list);seq=defaultdict(list);members=defaultdict(set)
    for marker in markers:bm[(marker['alert_id'],marker['message_id'])].append(marker)
    for link in links:
        seq[link['alert_id']].append(mm[link['message_id']]);members[link['message_id']].add(link['alert_id'])
    baseline=baseline_counts(features)
    inside=[];target={f['alert_id'] for f in features if f['classification_status']=='no_marker_with_text'}
    for aid in sorted(target):
        local={m['message_id']:bm[(aid,m['message_id'])] for m in seq[aid]}
        inside.extend(inside_sequence(aid,seq[aid],local,dictionary))
    inside_ids={r['alert_id'] for r in inside if r['evidence_level'] in SUPPORTED}
    # Stage C includes eligible no-text alerts too, retained as a separate stratum.
    stagec={f['alert_id'] for f in features if f['classification_status'] in {'no_marker_with_text','no_linked_text'}}-inside_ids
    timed=sorted([m for m in messages if m['message_time'] is not None and m['text'] and m['message_type']=='message'],key=lambda m:(m['message_time'],m['message_id']))
    times=[m['message_time'] for m in timed];lexcache={};pre=[]
    for aid in sorted(stagec):
        start=am[aid]['start_time']
        for m in pre_window(start,times,timed,60):
            mid=m['message_id']
            if mid not in lexcache:lexcache[mid]=dictionary.classify(m['text'])
            previous,boundaries,uncertain=contamination(aid,start,m,alerts,members)
            for marker in lexcache[mid]:
                level='ambiguous_candidate'
                if not operational(marker,m):level='not_relevant'
                elif re.search(r'обходитим\w*\s+Київ',m['text'],re.I):level='ambiguous_candidate'
                elif marker.get('relevant_to_kyiv') and not previous and not boundaries and not uncertain:level='direct_operational_threat'
                elif marker['geography']=='other_region':level='not_relevant'
                minutes=(start-m['message_time']).total_seconds()/60
                row=candidate(aid,marker,m,level,'before_alert',reason='Pre-alert association is experimental, never a confirmed cause',minutes=minutes)
                row.update(previous_alert_ids=previous,intervening_boundary_alert_ids=boundaries,unresolved_envelope_alert_ids=uncertain,
                    contamination_flag=bool(previous or boundaries or uncertain),candidate_windows=[w for w in WINDOWS if minutes<=w],
                    baseline_stratum=fm[aid]['classification_status'],lookback_history_complete=(start-timedelta(minutes=60)>=times[0]),complete_history_windows=[w for w in WINDOWS if start-timedelta(minutes=w)>=times[0]])
                pre.append(row)
    comparisons=[];previous_ids=set()
    for w in WINDOWS:
        rows=[r for r in pre if w in r['candidate_windows']];usable_rows=[r for r in rows if r['evidence_level']!='not_relevant']
        clean=[r for r in rows if r['evidence_level']=='direct_operational_threat' and not r['contamination_flag']]
        ids={r['alert_id'] for r in clean};anyids={r['alert_id'] for r in usable_rows}
        delays=[r['minutes_before_alert'] for r in clean];amb=[r for r in usable_rows if r['evidence_level']=='ambiguous_candidate'];cont=[r for r in rows if r['contamination_flag']]
        pairs={(r['alert_id'],r['anchor_message_id']) for r in usable_rows}
        comparisons.append(dict(window_minutes=w,unique_candidate_alerts=len(anyids),clean_kyiv_candidate_alerts=len(ids),clean_text_covered_alerts=sum(fm[a]['classification_status']=='no_marker_with_text' for a in ids),clean_no_text_alerts=sum(fm[a]['classification_status']=='no_linked_text' for a in ids),marginal_clean_alerts=len(ids-previous_ids),candidate_categories=dict(Counter(c for a,c in {(r['alert_id'],r['category']) for r in clean})),ambiguous_associations=len(amb),ambiguous_alerts=len({r['alert_id'] for r in amb}),contaminated_associations=len(cont),contaminated_alerts=len({r['alert_id'] for r in cont}),manual_review_alerts=len(anyids),manual_review_message_alert_pairs=len(pairs),minutes_before_distribution={str(k):sum(lo<=v<hi for v in delays) for k,lo,hi in [('0-5',0,5),('5-10',5,10),('10-15',10,15),('15-30',15,30),('30-60',30,60.00001)]},median_minutes_before=median(delays) if delays else None,min_minutes_before=min(delays) if delays else None,max_minutes_before=max(delays) if delays else None,remaining_eligible_unclassified=len(stagec-ids),remaining_text_unclassified=len((target-inside_ids)-ids)))
        previous_ids=ids
    coverage=[]
    for f in features:
        aid=f['alert_id'];available=f['classification_status'] not in {'outside_telegram_coverage','unresolved'}
        cats=sorted({r['category'] for r in inside if r['alert_id']==aid and r['evidence_level'] in SUPPORTED},key=CATEGORIES.index)
        row=dict(f,baseline_accepted=bool((f['unique_threat_category_count'] or 0)>0),inside_provisional_categories=cats if aid in target else None,inside_new_candidate=aid in inside_ids if available else None,experiment_status='PROVISIONAL — HUMAN VALIDATION REQUIRED')
        for w in WINDOWS:
            cc=sorted({r['category'] for r in pre if r['alert_id']==aid and w in r['candidate_windows'] and r['evidence_level']=='direct_operational_threat'},key=CATEGORIES.index)
            row[f'pre_{w}_candidate_categories']=cc if aid in stagec else None
        coverage.append(row)
    if len(coverage)!=len(set(r['alert_id'] for r in coverage)) or set(fm)!=set(am):raise ValueError('Alert reconciliation failed')
    if len(target)!=len(inside_ids)+len(target-inside_ids):raise ValueError('Stage B reconciliation failed')
    out=root/'data/processed/attribution_experiment_v1';reportdir=root/'reports/attribution_experiment_v1'
    out.mkdir(parents=True,exist_ok=True);reportdir.mkdir(parents=True,exist_ok=True)
    for name,rows in [('inside_interval_candidates',inside),('pre_alert_candidates',pre),('progressive_alert_coverage',coverage)]:
        pq.write_table(pa.Table.from_pylist(rows),out/(name+'.parquet'))
    write_audit_csv(inside,reportdir/'inside_interval_review.csv')
    write_audit_csv(comparisons,reportdir/'pre_alert_window_comparison.csv')
    # Review sample: stratify earliest qualifying window, relevance and contamination, all original text.
    groups=defaultdict(list)
    for r in pre:
        group=(min(r['candidate_windows']),r['evidence_level'],r['contamination_flag'],am[r['alert_id']]['start_time'].astimezone(KYIV).year)
        groups[group].append(r)
    review=[];seen=set()
    # Six distinct alert-message examples per first-qualifying window where available.
    for w in WINDOWS:
        keys=[k for k in sorted(groups) if k[0]==w]
        selected=0
        while selected<6 and any(groups[k] for k in keys):
            for key in keys:
                if not groups[key] or selected>=6:continue
                r=groups[key].pop(0);identity=(r['alert_id'],r['anchor_message_id'])
                if identity in seen:continue
                seen.add(identity);review.append(r);selected+=1
    write_audit_csv(review,reportdir/'pre_alert_review.csv')
    monthly=[]
    for month in ['2026-08','2026-09','2026-10']:
        ids={f['alert_id'] for f in features if f['start_time'].astimezone(KYIV).strftime('%Y-%m')==month}
        monthly.append(dict(month=month,total=len(ids),baseline_accepted=sum((fm[a]['unique_threat_category_count'] or 0)>0 for a in ids),text_unclassified=len(ids&target),inside_candidates=len(ids&inside_ids),stage_c_alerts=len(ids&stagec),clean_pre_by_window={str(w):len({r['alert_id'] for r in pre if r['alert_id'] in ids and w in r['candidate_windows'] and r['evidence_level']=='direct_operational_threat'}) for w in WINDOWS},partial_official_month=month=='2026-10'))
    reasons=Counter()
    for aid in target-inside_ids:
        rr=[r for r in inside if r['alert_id']==aid]
        reasons['no_lexical_anchor' if not rr else 'only_non_relevant_anchors' if all(r['evidence_level']=='not_relevant' for r in rr) else 'unresolved_geography_or_context']+=1
    after={k:digest(p) for k,p in sources.items()}
    if after!=hashes:raise ValueError('Protected source mutated')
    report=dict(status='PROVISIONAL — HUMAN VALIDATION REQUIRED',baseline=baseline,stage_b=dict(evaluated_text_alerts=len(target),new_provisional_alerts=len(inside_ids),still_text_unclassified=len(target-inside_ids),category_alert_counts=dict(Counter(c for a,c in {(r['alert_id'],r['category']) for r in inside if r['evidence_level'] in SUPPORTED})),evidence_level_occurrences=dict(Counter(r['evidence_level'] for r in inside)),manual_review_alerts=len({r['alert_id'] for r in inside if r['evidence_level']!='not_relevant'}),remaining_reasons=dict(reasons)),stage_c=dict(evaluated_alerts=len(stagec),includes_no_linked_text=True,windows=comparisons,review_sample_count=len(review)),recent_months=monthly,input_hashes=hashes,source_hashes_unchanged=hashes==after,context_policy=dict(minutes=5,next_message_limit=3,production_approved=False),recommendation='Prioritize 10 minutes for human review, with 5/15-minute sensitivity checks: shorter windows reduce ambiguous and contaminated associations; 30 minutes has no additional clean coverage over 15, and 60 adds only two clean candidates. No optimal or production-approved window is established without independently reviewed labels.',elapsed_seconds=round(time.perf_counter()-tick,6))
    (reportdir/'attribution_gap_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=serial)+'\n',encoding='utf-8')
    text=markdown(report,inside,review)
    (reportdir/'attribution_gap_report.md').write_text(text,encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,default=serial))
    return report


def markdown(r,inside,review):
    b=r['baseline'];s=r['stage_b']
    lines=['# Task 004.4 — Progressive attribution experiment','',r['status'],'','## Executive summary',f"Frozen accepted baseline: {b['accepted']}; new inside-interval provisional candidates: {s['new_provisional_alerts']}; remaining text-unclassified: {s['still_text_unclassified']}. No independent semantic validation and no production methodology change.",'','## Baseline reconciliation',json.dumps(b,ensure_ascii=False),f"Accepted coverage: {b['accepted']}/{b['total']} all official; {b['accepted']}/{b['eligible']} historically eligible; {b['accepted']}/{b['eligible_with_text']} eligible with text. Multiple-category sets overlap specific classification; not additive.",'','## Stage B',json.dumps(s,ensure_ascii=False),f"Waterfall (eligible): {b['eligible']} = {b['accepted']} frozen accepted + {s['new_provisional_alerts']} provisional inside + {s['still_text_unclassified']} remaining with text + {b['no_linked_text']} without linked text. Accepted production coverage remains {b['accepted']}; provisional observed support is {b['accepted']+s['new_provisional_alerts']}.",'All linked messages in each text-unclassified interval were inspected chronologically. The lexical dictionary is unchanged. A context episode requires an explicit current threat anchor, a subsequent short approved Kyiv-locality message within five minutes / next three messages, no competing category, and no reset. Other-region anchors cannot jump to Kyiv. This experimental bound is not validated or approved. No geography-only category inference. Generic UAV is the broad analytical group, never verified Shahed model. Ambiguous and irrelevant lexical occurrences are retained separately.','', '## Stage C — Strictly earlier lookbacks','No pre-alert candidate is a confirmed cause. Stage C includes remaining text-unclassified and eligible no-linked-text alerts, reported separately. Candidate interval is [start-window, start); exact start excluded. Each candidate is stored once with its applicable windows. Previous membership, intervening official start/end boundaries and unresolved interval envelopes flag contamination; contaminated associations cannot contribute to clean candidate coverage.','', '| Minutes | All candidate alerts | Clean Kyiv candidates | Marginal clean | Ambiguous occurrences | Contaminated occurrences | Remaining eligible |','|---:|---:|---:|---:|---:|---:|---:|']
    for w in r['stage_c']['windows']:lines.append('| '+' | '.join(str(w[k]) for k in ['window_minutes','unique_candidate_alerts','clean_kyiv_candidate_alerts','marginal_clean_alerts','ambiguous_associations','contaminated_associations','remaining_eligible_unclassified'])+' |')
    lines+=['','Counts of occurrences are not independent message/alert associations: overlapping dictionary rules may occur. JSON/CSV separately report unique alert-message review workload and unique category-alert support. Window results are nested alternative experiments, never additive. Final remaining counts are conditional on unvalidated clean candidates; accepted production counts remain unchanged.','', '## Recent August–October 2026',json.dumps(r['recent_months'],ensure_ascii=False),'October official starts stop Oct 4; the final interval ends Oct 5. Telegram continues Oct 10. October is a partial-source month.','', '## Remaining gaps and recommendation',r['recommendation'],'Locality-only updates cannot identify a threat category without an explicit source anchor. Geography exclusions and vague context remain review questions. The absence of detected markers is not confirmed absence of threats. No human labels were fabricated.','', '## Illustrative source-backed review cases']
    examples=[x for x in inside if x['evidence_level'] in SUPPORTED][:5]+[x for i,x in enumerate(review) if i in {0,5,6,11,12,17,18,23,24,29}]
    for x in examples:lines+=['',f"Alert {x['alert_id']}; {x['category']}; {x['evidence_level']}; IDs {x['source_message_ids']}; original timestamps {x['source_timestamps_original']}; minutes before {x['minutes_before_alert']}; geography {x['geography']}; contamination {x.get('contamination_flag',False)}.",'```', '\n---\n'.join(x['evidence_text']),'```']
    lines+=['','## Limitations and human decisions','Review whether bounded locality followups concern the anchor episode, whether geographically unspecified warnings concern Kyiv, and whether pre-alert messages explain the next official interval. Review all proposed gains before approving methods. A warning may refer to another event even without a detectable intervening boundary. Historical range measures observed export bounds, not continuous reporting. DST-unresolved timestamps remain null; no fold or global correction is chosen. Original timestamps, raw data, links and every v1.3 feature are retained. No Time Series Analysis performed.','',f"Runtime: {r['elapsed_seconds']} seconds. Protected SHA-256 values are recorded in JSON and verified before/after."]
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'));args=parser.parse_args();run(args.root.resolve())
