"""Deterministic purposive sample; diagnostic signals are never error labels."""
from collections import Counter, defaultdict
import random
from kyiv_alerts.classification.rules import CATEGORIES
from kyiv_alerts.ingestion.timeutils import KYIV
from kyiv_alerts.attribution.core import SUPPORTED, baseline_counts

SEED=20261011
STATUS='DIAGNOSTIC SAMPLE — HUMAN REVIEW REQUIRED'
GROUPS={
 'A':'Lexical detection failure (requires explicit threat evidence without a hit)',
 'B':'Overly strict geography (rejection alone does not establish an error)',
 'C':'Overly strict context (rejection alone does not establish an error)',
 'D':'Missing cross-message context (same episode needs review)',
 'E':'Incorrect temporal attribution (pre-alert connection needs review)',
 'F':'Insufficient information (human assessment required)',
 'G':'Non-operational content (human assessment required)',
 'H':'Other or unknown failure',
}


def order(message):
    return (message['message_time'],message['source_file'],message['source_message_index'],message['message_id'])


def signals(feature,markers,inside):
    tags=set()
    rejected=[m for m in markers if not m['accepted_for_aggregation']]
    if not markers:tags.add('no_lexical_candidates')
    if rejected:tags.add('rejected_lexical_candidates')
    if any('geography_' in (m['exclusion_reason'] or '') for m in rejected):tags.add('geography_rejection')
    if any('context_' in (m['exclusion_reason'] or '') for m in rejected):tags.add('context_rejection')
    if any(m['geography'] in {'unspecified','uncertain'} for m in markers):tags.add('ambiguous_geography')
    if any(m['evidence_status']=='uncertain' for m in markers):tags.add('uncertain_context')
    if any(m['category']!='other' and m['subtype']!='generic_uav' for m in markers):tags.add('explicit_named_threat_lexical_hit')
    if any(r['evidence_level'] in SUPPORTED for r in inside):tags.add('task0044_provisional_inside')
    if any(r['evidence_level']=='contextually_supported_threat' for r in inside):tags.add('cross_message_association')
    return tags


def select(features,markers,inside,seed=SEED):
    bm=defaultdict(list);bi=defaultdict(list)
    for m in markers:bm[m['alert_id']].append(m)
    for r in inside:bi[r['alert_id']].append(r)
    unclassified=[f for f in features if f['classification_status']=='no_marker_with_text' and (f['telegram_text_message_count'] or 0)>0]
    def month(f):return f['start_time'].astimezone(KYIV).strftime('%Y-%m')
    pools=[('october_2026',8,[f for f in unclassified if month(f)=='2026-10']),
      ('august_september_2026',5,[f for f in unclassified if month(f) in {'2026-08','2026-09'}]),
      ('high_volume_2024_2025',4,[f for f in unclassified if month(f)[:4] in {'2024','2025'} and f['telegram_text_message_count']>=20]),
      ('low_volume_2023_2025',3,[f for f in unclassified if month(f)[:4] in {'2023','2024','2025'} and f['telegram_text_message_count']<=3])]
    rng=random.Random(seed);selected=[];used=set();observed=set();audit=[]
    for name,count,pool in pools:
        candidates=sorted(pool,key=lambda f:f['alert_id']);rng.shuffle(candidates)
        available=len(candidates);chosen=[]
        for _ in range(min(count,available)):
            # Greedy novel diagnostic signal coverage; seeded rank resolves ties.
            pick=max(candidates,key=lambda f:len(signals(f,bm[f['alert_id']],bi[f['alert_id']])-observed))
            candidates.remove(pick);chosen.append(pick);observed.update(signals(pick,bm[pick['alert_id']],bi[pick['alert_id']]))
        for f in chosen:
            if f['alert_id'] in used:raise ValueError('Selection strata overlap')
            used.add(f['alert_id']);selected.append(dict(alert_id=f['alert_id'],sample_role='unclassified',selection_stratum=name,diagnostic_signals=sorted(signals(f,bm[f['alert_id']],bi[f['alert_id']]))))
        audit.append(dict(stratum=name,requested=count,available=available,selected=len(chosen),unavailable=max(0,count-available)))
    positives=[f for f in features if (f['unique_threat_category_count'] or 0)>0 and any(m['accepted_for_aggregation'] and not m['uncertainty_flag'] and m['evidence_status'] in {'explicit_alert_cause','current_threat'} for m in bm[f['alert_id']])]
    positives.sort(key=lambda f:f['alert_id']);rng.shuffle(positives);category_seen=set();chosen=[]
    for _ in range(min(5,len(positives))):
        def score(f):
            mm=[m for m in bm[f['alert_id']] if m['accepted_for_aggregation'] and not m['uncertainty_flag']]
            cats={m['category'] for m in mm}
            return (len(cats-category_seen),any(m['evidence_status']=='explicit_alert_cause' for m in mm),-f['telegram_message_count'])
        pick=max(positives,key=score);positives.remove(pick);chosen.append(pick)
        category_seen.update(m['category'] for m in bm[pick['alert_id']] if m['accepted_for_aggregation'])
        selected.append(dict(alert_id=pick['alert_id'],sample_role='positive_control',selection_stratum='positive_control',diagnostic_signals=['existing_accepted_source_evidence']))
    audit.append(dict(stratum='positive_control',requested=5,available=len(positives)+len(chosen),selected=len(chosen),unavailable=max(0,5-len(chosen))))
    return selected,audit


def association_key(row):return row['alert_id'],row['anchor_message_id'],row['rule_id'],row['category'],row['subtype']


def review_focus(markers,inside,pre):
    # These are questions for review, deliberately not assigned failure causes.
    letters=set()
    if not markers:letters.update(['A','F','G','H'])
    if any('geography_' in (m['exclusion_reason'] or '') for m in markers):letters.add('B')
    if any('context_' in (m['exclusion_reason'] or '') for m in markers):letters.add('C')
    if any(r['evidence_level']=='contextually_supported_threat' for r in inside):letters.add('D')
    if any(r['evidence_level']!='not_relevant' for r in pre):letters.add('E')
    return 'Review questions only: '+','.join(sorted(letters)) if letters else 'Review questions only: F,G,H'


def reconstruct(selected,features,messages,links,markers,inside,pre):
    fm={f['alert_id']:f for f in features};mm={m['message_id']:m for m in messages if m['message_id'] is not None}
    ids={s['alert_id'] for s in selected};bm=defaultdict(list);seq=defaultdict(list);bi=defaultdict(list);bp=defaultdict(list);assoc=defaultdict(list);bim=defaultdict(list)
    for marker in markers:
        if marker['alert_id'] in ids:bm[marker['alert_id']].append(marker)
    for l in links:
        if l['alert_id'] in ids:seq[l['alert_id']].append(mm[l['message_id']])
    for r in inside:
        if r['alert_id'] in ids:
            bi[r['alert_id']].append(r);assoc[association_key(r)].append(r)
            for mid in r['source_message_ids']:bim[(r['alert_id'],mid)].append(r)
    for r in pre:
        if r['alert_id'] in ids:bp[r['alert_id']].append(r)
    overview=[];timeline=[];trace=[]
    for s in selected:
        aid=s['alert_id'];f=fm[aid];rows=sorted(seq[aid],key=order);ms=bm[aid];bymsg=defaultdict(list)
        for m in ms:bymsg[m['message_id']].append(m)
        overview.append(dict(s,start=f['start_time'],end=f['end_time'],duration_minutes=f['duration_minutes'],current_status=f['classification_status'],current_categories=[c for c in CATEGORIES[:-1] if f[c] is True],message_count=len(rows),text_message_count=sum(bool(m['text'] and m['text'].strip()) for m in rows),candidate_marker_count=len(ms),accepted_marker_count=sum(m['accepted_for_aggregation'] for m in ms),rejected_marker_count=sum(not m['accepted_for_aggregation'] for m in ms),task0044_candidate_categories=sorted({r['category'] for r in bi[aid] if r['evidence_level'] in SUPPORTED},key=CATEGORIES.index),task0044_status='PROVISIONAL — HUMAN VALIDATION REQUIRED' if bi[aid] else 'no_inside_records',proposed_diagnostic_group='positive_control' if s['sample_role']=='positive_control' else review_focus(ms,bi[aid],bp[aid]),pre_alert_candidate_count=len(bp[aid]),dictionary_version=f['dictionary_version'],classification_version=f['classification_version'],human_confirmed_threat_category=None,human_confirmed_primary_failure_reason=None,human_decision=None,review_notes=None))
        for m in rows:
            hits=sorted(bymsg[m['message_id']],key=lambda x:(x['match_start'],x['match_end'],x['rule_id']))
            timeline.append(dict(alert_id=aid,message_id=m['message_id'],timestamp=m['message_time'],timestamp_original=m['message_time_original'],minutes_from_alert_start=(m['message_time']-f['start_time']).total_seconds()/60,original_message_text=m['text'],message_type=m['message_type'],dictionary_hit=bool(hits),candidate_category=[h['category'] for h in hits],context_decision=[h['evidence_status'] for h in hits],geography_decision=[h['geography'] for h in hits],accepted_rejected=['accepted' if h['accepted_for_aggregation'] else 'rejected' for h in hits],exclusion_reason=[h['exclusion_reason'] for h in hits],dictionary_candidates=hits,task0044_evidence=bim[(aid,m['message_id'])],source_file=m['source_file'],source_message_index=m['source_message_index'],human_interpretation=None,human_notes=None))
        for h in ms:
            m=mm[h['message_id']];key=(aid,h['message_id'],h['rule_id'],h['category'],h['subtype']);associations=assoc[key]
            missing=['legacy_geography_regex_rule_ids_not_recorded','legacy_context_pattern_ids_not_recorded']
            if any(x in (h['exclusion_reason'] or '') for x in ['overlapping_specific_rule','specific_family_in_clause']):missing.append('overlap_suppressor_identity_not_recorded')
            if associations:missing.append('task0044_occurrence_spans_not_recorded')
            # A null approved override is absence of override, not an absent legacy trace.
            trace.append(dict(alert_id=aid,message_id=h['message_id'],original_text=m['text'],matched_expression=h['matched_text'],rule_id=h['rule_id'],candidate_category=h['category'],candidate_subtype=h['subtype'],lexical_match_status='matched',evidence_context=h['evidence_context'],geography=h['geography'],geography_rule={'locality_rule_ids':list(dict.fromkeys(x['rule_id'] for x in h.get('geography_mentions',[]))),'relevance_rule_id':h.get('relevance_rule_id'),'legacy_regex_rule_ids':'not_recorded'},context_rule={'approved_override_rule_id':h.get('context_rule_id'),'legacy_pattern_ids':'not_recorded'},exclusion_reasons=(h['exclusion_reason'] or '').split(';') if h['exclusion_reason'] else [],final_acceptance_status='accepted' if h['accepted_for_aggregation'] else 'rejected',task0044_candidate_status=[r['evidence_level'] for r in associations] or ['not_evaluated_positive_control' if s['sample_role']=='positive_control' else 'not_recorded'],task0044_provisional_associations=associations,task0044_association_alignment='anchor/rule/category/subtype; occurrence spans unavailable in Task0044' if associations else 'no_association',source_file=m['source_file'],source_message_index=m['source_message_index'],timestamp=m['message_time'],timestamp_original=m['message_time_original'],match_start=h['match_start'],match_end=h['match_end'],evidence_status=h['evidence_status'],context_status_original=h.get('context_status_original'),context_rule_id_recorded=h.get('context_rule_id'),relevance_rule_id_recorded=h.get('relevance_rule_id'),geography_mentions=h.get('geography_mentions'),geography_source=h.get('geography_source'),relevant_to_kyiv=h.get('relevant_to_kyiv'),uncertainty_flag=h.get('uncertainty_flag'),evidence_qualifiers=h.get('evidence_qualifiers'),uav_evidence_type=h.get('uav_evidence_type'),inferred_shorthand=h.get('inferred_shorthand'),dictionary_version=h['dictionary_version'],geography_dictionary_version=h.get('geography_dictionary_version'),classification_version=h['classification_version'],missing_instrumentation=missing,human_interpretation=None,human_notes=None))
    return overview,timeline,trace,[r for aid in sorted(ids) for r in bp[aid]]
