"""Bounded lexical context and strictly earlier lookbacks, never cause inference."""
from bisect import bisect_left
from collections import defaultdict, Counter
from datetime import timedelta
import re
from kyiv_alerts.classification.rules import CATEGORIES
from kyiv_alerts.integration.linking import possible_instants

WINDOWS=(5,10,15,30,60)
SUPPORTED={'explicit_alert_cause','direct_operational_threat','contextually_supported_threat'}
BLOCKING=('dictionary_exclusion','overlapping_specific_rule','specific_family_in_clause','context_negated','context_historical')
RESET=re.compile(r'відбій|перекур|небезпек\w*\s+минул|загроз\w*\s+нема|поки\s+(?:нема|чисто)',re.I)
NONOP=re.compile(r'\?|жарт|мем|донат|збір|банка|ретроспект|вчора|завтра|навчан|можливо\s+буде',re.I)


def bulletin(text):
    # Remove only known export channel footer for short-bulletin length, never evidence.
    return '\n'.join(line for line in text.splitlines() if not ('Український Єнот' in line and '✙' in line)).strip()


def usable(marker):
    return not any(x in (marker.get('exclusion_reason') or '') for x in BLOCKING) and marker['evidence_status'] not in {'historical_or_summary','negated_or_cancelled'}


def operational(marker, message):
    if not usable(marker) or NONOP.search(message['text'] or ''):return False
    if marker['evidence_status'] in {'current_threat','explicit_alert_cause'}:return True
    # Experimental short current bulletin, not arbitrary uncertain commentary.
    text=bulletin(message['text'] or '')
    return len(text.split())<=8 and bool(re.search(r'курс|лет\w*|рух\w*|над\s|на\s|бпла|дрон|шах',text,re.I)) and not re.search(r'якщо|може|можлив|імовір|ймовір|очіку|буде|був|були',text,re.I)


def candidate(aid,marker,source,level,relation,related=(),reason='',minutes=None):
    ordered=[source,*related]
    return dict(alert_id=aid,category=marker['category'],anchor_message_id=source['message_id'],
        source_message_ids=list(dict.fromkeys(m['message_id'] for m in ordered)),
        evidence_text=[m['text'] for m in ordered],source_timestamps_original=[m['message_time_original'] for m in ordered],
        source_message_times=[m['message_time'] for m in ordered],source_files=[m['source_file'] for m in ordered],
        source_message_indices=[m['source_message_index'] for m in ordered],evidence_level=level,time_relation=relation,
        minutes_before_alert=minutes,geography=marker['geography'],relevant_to_kyiv=marker.get('relevant_to_kyiv',False),
        confidence_or_review_status='PROVISIONAL — HUMAN VALIDATION REQUIRED',reason=reason,
        source_dictionary_version=marker['dictionary_version'],rule_id=marker['rule_id'],subtype=marker['subtype'],
        uav_evidence_type=marker.get('uav_evidence_type'),uncertainty_flag=bool(marker.get('uncertainty_flag')),
        original_exclusion_reason=marker.get('exclusion_reason'),human_decision=None,human_notes=None)


def inside_sequence(aid,sequence,by_message,dictionary,context_minutes=5):
    rows=[]
    sequence=sorted(sequence,key=lambda m:(m['message_time'],m['source_file'],m['source_message_index'],m['message_id']))
    for i,source in enumerate(sequence):
        for marker in by_message.get(source['message_id'],[]):
            level='ambiguous_candidate';related=[];reason='Explicit lexical anchor; alert relationship unresolved'
            if not usable(marker) or NONOP.search(source['text'] or ''):
                level='not_relevant';reason='Negation, history, non-operational content or suppressed lexical occurrence'
            elif operational(marker,source):
                if marker.get('relevant_to_kyiv'):
                    level='explicit_alert_cause' if marker['evidence_status']=='explicit_alert_cause' else 'direct_operational_threat'
                    reason='Explicit current threat and same-message approved Kyiv relevance'
                else:
                    # At most next three messages, <=5min; stop reset or competing explicit type.
                    for following in sequence[i+1:i+4]:
                        if (following['message_time']-source['message_time']).total_seconds()>context_minutes*60:break
                        text=bulletin(following['text'] or '')
                        if RESET.search(text) or NONOP.search(text):break
                        competing={x['category'] for x in by_message.get(following['message_id'],[]) if usable(x)}
                        if competing and competing!={marker['category']}:break
                        geo,_=dictionary.geographic_evidence(dictionary.normalize(text),text)
                        if geo=='explicit_kyiv' and len(text.split())<=12:
                            # Explicit other-region anchor does not jump regions via a locality followup.
                            if marker['geography'] in {'unspecified','kyiv_region','nationwide'}:
                                related=[following];level='contextually_supported_threat'
                                reason='Explicit operational threat anchor followed by short Kyiv locality update within experimental 5min/3-message bound'
                            break
            rows.append(candidate(aid,marker,source,level,'inside_interval',related,reason))
    return rows


def pre_window(start,times,messages,minutes):
    return messages[bisect_left(times,start-timedelta(minutes=minutes)):bisect_left(times,start)]


def contamination(aid,start,message,alerts,memberships):
    previous=sorted(x for x in memberships.get(message['message_id'],set()) if x!=aid)
    boundaries=[];uncertain=[]
    t=message['message_time']
    for alert in alerts:
        if alert['alert_id']==aid:continue
        s,e=alert['start_time'],alert['end_time']
        if any(b is not None and t<b<start for b in (s,e)):boundaries.append(alert['alert_id'])
        if s is not None and e is None:
            ends=possible_instants(alert.get('end_time_original'))
            upper=max(ends) if ends else start
            if s<=t<upper:uncertain.append(alert['alert_id'])
    return previous,sorted(set(boundaries)),sorted(set(uncertain))


def baseline_counts(features):
    states=Counter(f['classification_status'] for f in features)
    accepted=[f for f in features if f['unique_threat_category_count'] is not None and f['unique_threat_category_count']>0]
    eligible=[f for f in features if f['classification_status'] not in {'outside_telegram_coverage','unresolved'}]
    return dict(total=len(features),eligible=len(eligible),eligible_with_text=sum((f['telegram_text_message_count'] or 0)>0 for f in eligible),accepted=len(accepted),specific=sum(f['specific_threat_category_count']>0 for f in accepted),other_only=states['only_other'],multiple_specific=states['multiple_types'],multiple_all=sum(f['unique_threat_category_count']>1 for f in accepted),text_unclassified=states['no_marker_with_text'],no_linked_text=states['no_linked_text'],outside=states['outside_telegram_coverage'],unresolved=states['unresolved'],states=dict(states))
