"""Deterministic bounded episodes; IDs never appear in interpretation rules."""
from collections import defaultdict,Counter
from datetime import timedelta
import re,copy
from kyiv_alerts.classification.rules import CATEGORIES
from kyiv_alerts.classification.consolidation import SPECIFIC,is_eligible
from kyiv_alerts.attribution.core import pre_window,contamination,bulletin
from kyiv_alerts.controlled_review.core import order

STATUS='EXPERIMENTAL — HUMAN VALIDATION REQUIRED'
HARD=('dictionary_exclusion','overlapping_specific_rule','specific_family_in_clause')
RESET=re.compile(r'відбій|не\s+фіксу\w*|не\s+відміча\w*|всьо\s+нема|здох|перекур|знищен\w*|збит\w*|загроз\w*\s+(?:нема|минул)',re.I)
NEGATED=re.compile(r'не\s+(?:фіксу\w*|відміча\w*|спостеріга\w*|актив\w*)|(?:нема(?:є)?|відсутн\w*)\s+(?:бпла|дрон\w*|шах\w*|загроз\w*|пуск\w*)|(?:бпла|дрон\w*|шах\w*)\s+(?:нема(?:є)?|відсутн\w*)',re.I)
NONOP=re.compile(r'\?|\b(?:жарт\w*|мем\w*|донат\w*|збір\w*|банка|банк[уи]|вчора|позавчора|торік|завтра|навчан\w*|характеристик\w*|специфікац\w*|поясню\w*|ілюстратив\w*)\b|теоретич\w*|принцип\s+(?:дії|роботи)|як\s+(?:працю\w*|влаштован\w*)|є\s+носієм|це\s+носій|на\s+русню',re.I)
DIRECTION=re.compile(r'\b(?:на|над|біля|поблизу|повз|через|курс\w*|лет\w*|рух\w*|пуск\w*|зліт\w*|загроз\w*|підліта\w*|напрям\w*|підход\w*|підльот\w*)\b',re.I)
MOVEMENT_REFERENCE=re.compile(r'\b(?:лет\w*|курс\w*|рух\w*|знижу\w*|підліта\w*|підход\w*|напрям\w*)\b',re.I)
BYPASS=re.compile(r'обходитим\w*\s+київ',re.I)


def operational(marker,source,max_tokens=12):
    text=bulletin(source['text'] or '');body=bulletin(marker['evidence_context'] or '')
    if any(x in (marker.get('exclusion_reason') or '') for x in HARD):return False,'specificity_or_dictionary_exclusion'
    if marker['evidence_status'] in {'historical_or_summary','negated_or_cancelled'} or NEGATED.search(body):return False,'negation_or_history'
    if NONOP.search(text):return False,'non_operational_or_explanatory'
    if marker['subtype']=='mig_takeoff_unspecified_model':return False,'ambiguous_aircraft_model'
    if BYPASS.search(body):return False,'route_bypasses_kyiv'
    if marker['evidence_status'] in {'current_threat','explicit_alert_cause'}:return True,'explicit_operational_legacy_context'
    if len(body.split())<=max_tokens and DIRECTION.search(body) and not re.search(r'\b(?:був|були|було|буде|якщо|колись)\b',body,re.I):return True,'short_current_operational_bulletin'
    return False,'no_explicit_current_operational_signal'


def confined_to_other_region(marker,dictionary):
    body=dictionary.normalize(marker['evidence_context'] or '')
    engine=getattr(dictionary,'base',dictionary)
    foreign=[hit.group() for pattern in engine.geography['other_region'] for hit in pattern.finditer(body) if not hit.group().startswith(('бориспі','бровар','фастів','білоцерк'))]
    city=[m for m in marker.get('geography_mentions',[]) if m['category']=='explicit_kyiv' and m['locality_id']!='city_center']
    if foreign and not city and any(m['locality_id']=='city_center' for m in marker.get('geography_mentions',[])):
        return True  # Center of an explicitly different city is not a Kyiv anchor.
    if marker.get('relevant_to_kyiv') or marker['geography']!='other_region':return False
    # Distinguish origin from confinement; literal geography remains untouched.
    body=dictionary.normalize(marker['evidence_context'] or '')
    route=re.search(r'\b(?:з|із|від)\s+.+?\s+(?:на|до|курсом\s+на)\s+(.+)',body)
    if route:
        target_geo,_=dictionary.geographic_evidence(route.group(1),route.group(1))
        if target_geo!='other_region':return False
    return True


def annotate(marker,source,aid,relation,baseline=False):
    row=copy.deepcopy(marker)
    row.update(alert_id=aid,message_id=source['message_id'],source_file=source['source_file'],source_message_index=source['source_message_index'],
      classification_version='v1.4',source_classification_version='v1.3',attribution_version='v1.4',experiment_status=STATUS,
      source_dictionary_version='v1.3',
      source_message_time=source['message_time'],source_timestamp_original=source['message_time_original'],original_text=source['text'],
      anchor_message_id=source['message_id'],anchor_rule_id=marker['rule_id'],anchor_match_start=marker['match_start'],anchor_match_end=marker['match_end'],
      evidence_role='lexical_anchor',time_relation=relation,anchor_time_relation=relation,anchor_geography=marker['geography'],minutes_before_alert=None,baseline_accepted=bool(baseline),
      baseline_exclusion_reason=marker.get('exclusion_reason'),baseline_evidence_status=marker['evidence_status'],
      attribution_strength='baseline_accepted' if baseline else 'ambiguous_candidate',operational_status='not_evaluated',operational_rule_id=None,
      attribution_rule_ids=['baseline_preserved'] if baseline else [],correction_causes=[],uncertainty_reasons=[],
      support_message_ids=[source['message_id']],previous_alert_ids=[],intervening_boundary_alert_ids=[],unresolved_envelope_alert_ids=[],
      context_geography=None,ablation_blocked=False,geographic_uncertainty=marker['geography'] not in {'explicit_kyiv','nationwide'},human_decision=None,human_notes=None)
    return row


def accept(row,strength,causes,rules,reason):
    row['accepted_for_aggregation']=True;row['attribution_strength']=strength
    row['correction_causes']=sorted(set(row['correction_causes'])|set(causes));row['attribution_rule_ids']+=rules
    row['exclusion_reason']=None
    if not row['baseline_accepted']:
        row['uncertainty_flag']=True
        row['uncertainty_reasons']=sorted(set(row['uncertainty_reasons']+[reason,'experimental_alert_association_not_independent_confirmation']))


def context_reference(row,source,geo,mentions,unambiguous,alert_start):
    ref=copy.deepcopy(row)
    ref.update(message_id=source['message_id'],source_file=source['source_file'],source_message_index=source['source_message_index'],source_message_time=source['message_time'],source_timestamp_original=source['message_time_original'],original_text=source['text'],evidence_context=source['text'],rule_id='attribution.context_reference',matched_text=None,match_start=None,match_end=None,evidence_role='context_reference',baseline_accepted=False,baseline_exclusion_reason=None,baseline_evidence_status=None,geography=geo,geography_mentions=copy.deepcopy(mentions),geography_source='context_reference_literal',geographic_uncertainty=geo not in {'explicit_kyiv','nationwide'},relevant_to_kyiv=geo in {'explicit_kyiv','nationwide'},context_geography=geo,accepted_for_aggregation=False,exclusion_reason='ambiguous_elliptical_reference',attribution_strength='ambiguous_candidate',uncertainty_flag=True,support_message_ids=list(dict.fromkeys([row['anchor_message_id'],source['message_id']])))
    ref['time_relation']='before_alert' if source['message_time']<alert_start else 'inside_interval'
    ref['minutes_before_alert']=(alert_start-source['message_time']).total_seconds()/60 if ref['time_relation']=='before_alert' else None
    if unambiguous:accept(ref,'contextually_supported_threat',['cross_message'],['bounded_episode_reference'],'cross_message_identity_is_inferred')
    return ref


def process(features,messages,links,baseline_markers,dictionary,alerts,policy,cache=None):
    mm={m['message_id']:m for m in messages if m['message_id'] is not None};fm={f['alert_id']:f for f in features}
    bypair=defaultdict(list);seq=defaultdict(list);members=defaultdict(set)
    baseline_keys={ (m['alert_id'],m['message_id'],m['rule_id'],m['match_start'],m['match_end']):m for m in baseline_markers }
    for marker in baseline_markers:bypair[(marker['alert_id'],marker['message_id'])].append(marker)
    for link in links:seq[link['alert_id']].append(mm[link['message_id']]);members[link['message_id']].add(link['alert_id'])
    timed=sorted([m for m in messages if m['message_time'] is not None and m.get('text') and m.get('message_type')=='message'],key=order);times=[m['message_time'] for m in timed]
    cache={} if cache is None else cache;out=[]
    enabled=set(policy.get('enabled_corrections',['geography','context','cross_message','pre_alert']))
    for f in features:
        aid=f['alert_id'];eligible=is_eligible(f);linked=sorted(seq[aid],key=order)
        # No new candidates may manufacture unavailable historical/DST observations.
        pre=pre_window(f['start_time'],times,timed,policy['pre_alert_minutes']) if eligible and 'pre_alert' in enabled else []
        timeline=sorted(pre+linked,key=order);active=[];last_time=None
        for source in timeline:
            relation='before_alert' if source['message_time']<f['start_time'] else 'inside_interval'
            text=bulletin(source['text'] or '')
            if last_time and (source['message_time']-last_time).total_seconds()>policy['context_max_gap_minutes']*60:active=[]
            active=[r for r in active if (source['message_time']-mm[r['anchor_message_id']]['message_time']).total_seconds()<=policy['context_anchor_max_minutes']*60]
            if RESET.search(text) or NEGATED.search(text) or NONOP.search(text):active=[]
            if source['message_id'] not in cache:cache[source['message_id']]=dictionary.classify(source['text'])
            lexical=cache[source['message_id']]
            rows=[]
            for marker in lexical:
                old=baseline_keys.get((aid,source['message_id'],marker['rule_id'],marker['match_start'],marker['match_end']))
                baseline=bool(old and old['accepted_for_aggregation'])
                row=annotate(marker,source,aid,relation,baseline)
                if old:
                    row['baseline_exclusion_reason']=old['exclusion_reason']
                    row['baseline_evidence_status']=old['evidence_status']
                    if baseline:row['exclusion_reason']=old['exclusion_reason']
                ok,reason=operational(marker,source,policy['short_bulletin_max_tokens']);row['operational_status']='operational' if ok else 'non_operational_or_unresolved';row['operational_rule_id']=reason
                if baseline:
                    row['uncertainty_reasons']=['source_uncertainty'] if row['uncertainty_flag'] else []
                else:
                    row['accepted_for_aggregation']=False;row['exclusion_reason']=reason if not ok else 'alert_association_requires_review'
                    if eligible and ok and not confined_to_other_region(marker,dictionary):
                        causes=[]
                        if not marker.get('relevant_to_kyiv'):causes.append('geography')
                        if marker['evidence_status']=='uncertain':causes.append('context')
                        if not set(causes)<=enabled:
                            row['ablation_blocked']=True;row['exclusion_reason']='disabled_correction'
                        elif relation=='inside_interval':
                            strength='explicit_alert_cause' if marker['evidence_status']=='explicit_alert_cause' and marker.get('relevant_to_kyiv') else 'direct_operational_threat'
                            accept(row,strength,causes,['within_official_kyiv_interval','operational_before_literal_geography'],'literal_geography_not_verified_kyiv_direction')
                        else:
                            previous,boundaries,unresolved=contamination(aid,f['start_time'],source,alerts,members)
                            row.update(previous_alert_ids=previous,intervening_boundary_alert_ids=boundaries,unresolved_envelope_alert_ids=unresolved)
                            causes.append('pre_alert');row['correction_causes']=sorted(set(causes))
                            if previous or boundaries or unresolved:row['exclusion_reason']='previous_alert_or_boundary_contamination'
                            elif marker.get('relevant_to_kyiv') and not BYPASS.search(text):accept(row,'pre_alert_operational_context',causes,['ten_minute_pre_alert','explicit_kyiv_relevance'],'pre_alert_association_unapproved_optimal_window')
                    elif ok and confined_to_other_region(marker,dictionary):row['exclusion_reason']='explicit_other_region_without_kyiv_association'
                    if not row['accepted_for_aggregation']:row['uncertainty_reasons']=[row['exclusion_reason'] or 'unresolved']
                if relation=='before_alert':
                    row['minutes_before_alert']=(f['start_time']-source['message_time']).total_seconds()/60
                    # Flag contamination even for excluded lexical occurrences.
                    previous,boundaries,unresolved=contamination(aid,f['start_time'],source,alerts,members)
                    row.update(previous_alert_ids=previous,intervening_boundary_alert_ids=boundaries,unresolved_envelope_alert_ids=unresolved)
                rows.append(row);out.append(row)
            explicit=[r for r in rows if r['operational_status']=='operational' and not any(x in (r['baseline_exclusion_reason'] or '') for x in HARD)]
            if explicit:
                newcats={r['category'] for r in explicit}
                if active and newcats!={r['category'] for r in active}:active=[]
                # Each explicit current message resets the bounded anchor; multiple types stay ambiguous for following references.
                active=[r for r in explicit if not confined_to_other_region(r,dictionary)]
            elif 'cross_message' in enabled and not rows and active and text and len(text.split())<=policy['short_bulletin_max_tokens'] and not RESET.search(text) and not NONOP.search(text):
                geo,mentions=dictionary.geographic_evidence(dictionary.normalize(source['text']),source['text'])
                local_support=geo in {'explicit_kyiv','kyiv_region'} or any(m['category']=='explicit_kyiv' for m in mentions)
                recognizable=local_support or bool(MOVEMENT_REFERENCE.search(text))
                distinct={r['category'] for r in active}
                for anchor in active:
                    clean=not (anchor['previous_alert_ids'] or anchor['intervening_boundary_alert_ids'] or anchor['unresolved_envelope_alert_ids'])
                    # Pre-alert ambiguity can be supported only by an inside-interval local followup, not an arbitrary pre-alert chain.
                    if not anchor['accepted_for_aggregation'] and not anchor['ablation_blocked'] and relation=='inside_interval' and anchor['time_relation']=='before_alert' and clean and local_support and geo!='other_region' and len(distinct)==1:
                        accept(anchor,'pre_alert_contextually_supported',anchor['correction_causes']+['cross_message'],['ten_minute_pre_alert','bounded_inside_followup'],'pre_alert_category_and_episode_link_are_inferred')
                        anchor['support_message_ids'].append(source['message_id']);anchor['context_geography']=geo
                    unambiguous=recognizable and len(distinct)==1 and geo!='other_region' and anchor['accepted_for_aggregation'] and clean
                    out.append(context_reference(anchor,source,geo,mentions,unambiguous,f['start_time']))
            last_time=source['message_time']
    return out,aggregate(features,out,mm)


def aggregate(previous,markers,mm):
    accepted=defaultdict(list)
    for m in markers:
        if m['accepted_for_aggregation']:accepted[m['alert_id']].append(m)
    result=[];candidate_counts=Counter(m['alert_id'] for m in markers)
    for old in previous:
        f=copy.deepcopy(old);rows=accepted[f['alert_id']];eligible=is_eligible(f)
        unavailable=not eligible
        observed=eligible and (bool(f['telegram_text_message_count']) or bool(rows))
        cats=[c for c in CATEGORIES[:-1] if any(r['category']==c for r in rows)]
        support_ids=sorted({mid for r in rows for mid in r['support_message_ids']},key=lambda mid:order(mm[mid]))
        bycat=[]
        for c in cats:
            rr=[r for r in rows if r['category']==c];ids=sorted({mid for r in rr for mid in r['support_message_ids']},key=lambda mid:order(mm[mid]))
            bycat.append(dict(category=c,first_message_id=ids[0],message_ids=ids,supporting_message_count=len(ids),supporting_marker_count=len(rr),uncertain_marker_count=sum(r['uncertainty_flag'] for r in rr)))
        specific=sum(c in SPECIFIC for c in cats)
        state='unresolved' if old['classification_status']=='unresolved' else 'outside_telegram_coverage' if unavailable else 'multiple_types' if specific>=2 else 'single_type' if specific==1 else 'only_other' if 'other' in cats else 'no_marker_with_text' if old['telegram_text_message_count'] else 'no_linked_text'
        f.update({c:(c in cats) if observed else None for c in CATEGORIES[:-1]})
        f.update(unknown=not bool(cats),threat_combination=('+'.join(cats) or 'unknown') if observed else None,classification_status=state,classification_version='v1.4',source_classification_version='v1.3',attribution_version='v1.4',experiment_status=STATUS,
          unique_threat_category_count=len(cats) if observed else None,specific_threat_category_count=specific if observed else None,
          marker_evidence_count=len(rows) if observed else None,candidate_marker_count=candidate_counts[f['alert_id']],
          first_accepted_evidence_message_id=support_ids[0] if support_ids else None,supporting_message_ids=support_ids if observed else None,supporting_message_count=len(support_ids) if observed else None,category_message_support=bycat if observed else None,
          explicit_cause_categories=[c for c in cats if any(r['category']==c and r['time_relation']=='inside_interval' and r['evidence_role']=='lexical_anchor' and r['evidence_status']=='explicit_alert_cause' and r.get('relevant_to_kyiv') for r in rows)] if observed else None,
          baseline_classification_status=old['classification_status'],baseline_categories=[c for c in CATEGORIES[:-1] if old[c] is True],
          evidence_strengths=sorted({r['attribution_strength'] for r in rows}) if observed else None,
          correction_causes=sorted({cause for r in rows for cause in r['correction_causes']}) if observed else None,
          uncertainty_marker_count=sum(r['uncertainty_flag'] for r in rows) if observed else None,
          has_pre_alert_evidence=any(r['time_relation']=='before_alert' for r in rows) if observed else None)
        result.append(f)
    return result
