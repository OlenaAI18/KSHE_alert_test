"""Scoped operational attribution with bounded episodes and corroborated pre-alerts."""
from collections import defaultdict
import copy
import re

from kyiv_alerts.attribution.core import pre_window, contamination, bulletin
from kyiv_alerts.classification.consolidation import is_eligible
from kyiv_alerts.classification_v14.core import (annotate, accept, aggregate,
    context_reference, operational as old_operational, confined_to_other_region,
    HARD, NONOP, MOVEMENT_REFERENCE, BYPASS)
from kyiv_alerts.controlled_review.core import order

STATUS = 'EXPERIMENTAL — HUMAN VALIDATION REQUIRED'
NONOP_SCOPED = re.compile(NONOP.pattern.removeprefix(r'\?|'), re.I)
HISTORY = re.compile(r'\b(?:вчора|учора|позавчора|торік|колись|раніше|минулого|ретроспект\w*|зведення|підсум\w*|статистик\w*)\b', re.I)
CLEAR = re.compile(r'\b(?:відбій|перекур|здох|знищен\w*|збит\w*)\b|загроз\w*\s+(?:нема(?:є)?|минул\w*)', re.I)
ABSENCE_CLEAR = re.compile(r'\bбез\s+ціл\w*|\bціл\w*\s+(?:відсутн\w*|нема(?:є)?)', re.I)
LOST = re.compile(r'не\s+(?:фіксу\w*|відміча\w*|спостеріга\w*)', re.I)
NEW_OBJECT = re.compile(r'\b(?:наступн\w*|новий|нові|ще\s+(?:один|одна|\d+))\b', re.I)
MOVE = re.compile(r'\b(?:змінил\w*|повернув\w*|поверта\w*|знижу\w*|лет\w*|курс\w*|рух\w*|заход\w*|напрям\w*)\b', re.I)
CAUSE_REF = re.compile(r'тривог\w*\s+(?:в|у)\s+(?:столиц\w*|ки[їє]в\w*)\s+через\s+(?:ньог\w*|неї|них|це)', re.I)
NEGATION = re.compile(r'\b(?:без\s+загроз\w*|загроз\w*\s+(?:нема(?:є)?|відсутн\w*)|не\s+підтверджен\w*|нема(?:є)?|не\s+(?:лет\w*|злет\w*|загрож\w*)|не)\b', re.I)
NO_STRIKES = re.compile(r'ворож\w*\s+удар\w*[^\n.!?;]*не\s+було', re.I)
CLAUSE_BOUNDARIES = re.compile(r'[\n.!?;]|\b(?:але|а)\b', re.I)
QUOTES = re.compile(r'«[^»]*»|"[^"\n]*"')


EXTRA_GUARDS = re.compile(r'\b(?:міг\s+(?:бути|відбутися)|якщо|якби|завтра|післязавтра|було\s+б|була\s+б|були\s+б|сіли|сіла|сів|посадку|посадка|сплутати|поспішив|ні-чо-го|перебазуван\w*|оглядов\w*\s+екскурс\w*)\b|\b(?:по|щодо)\s+[^\n.!?;]{0,35}(?:тихо|чисто|все\s+ок)|\bзагроз\w*\s+не\s+нес\w*', re.I)
CURRENT_VERB = re.compile(r'\b(?:загроз\w*|зліт\w*|підня\w*|злет\w*|виліт\w*|вилеті\w*|пуск\w*|застосовано|спрацювал\w*|лет\w*|прям\w*|наближ\w*|присутн\w*|актуальн\w*|заход\w*|йде|іде|борозд\w*|спостерігал\w*|до\s+нас\s+в\s+область|на\s+Київ\w*|в\s+повітрі|у\s+повітрі)\b', re.I)


def current_statement(marker, clause, full, dictionary):
    """Finite current bulletins, never a locality-only or unnamed-type inference."""
    if EXTRA_GUARDS.search(clause) or '?' in clause:
        return None
    if CURRENT_VERB.search(clause):
        return 'current_operational_clause'
    # Explicit type-only bulletins denote current threat in this channel.
    short = full.strip(' \n\t⚠️❗🚀✈️🛫+.,!🫠')
    if marker['category'] != 'mig31' and re.fullmatch(r'(?:балістика|шах|шахед(?:и|ів)?|бпла|дрони)(?:\s+знову)?', short, re.I):
        return 'explicit_type_only_bulletin'
    if marker['category'] == 'cruise_missile' and re.fullmatch(r'крилат(?:а|і)\s+ракет(?:а|и)(?:\s+(?:схоже|ймовірно))?', short, re.I):
        return 'explicit_probable_cruise_bulletin'
    if marker['category'] == 'ballistic_high_speed' and re.search(r'\b(?:ціл\w*|тра(?:є|е)кторі\w*|тривог\w*)\b', clause):
        return 'ballistic_target_or_alert_bulletin'
    geo, mentions = dictionary.geographic_evidence(full, full)
    if marker['category'] in {'shahed_uav','jet_uav'}:
        if re.search(r'\b(?:біля|поблизу|північніше|південніше|вище|в\s+районі|до\s+вас|в\s+сторону|в\s+напрямку)\b', full) and geo in {'explicit_kyiv','kyiv_region'}:
            return 'position_or_route_with_explicit_type'
        if geo == 'explicit_kyiv' and len(full.split()) <= 12 and not re.search(r'\b(?:був|були|було|буде|будуть|колись|може\s+бути)\b', full):
            return 'kyiv_locality_with_explicit_uav'
    return None


def key(row):
    return row['alert_id'], row['message_id'], row['rule_id'], row['match_start'], row['match_end'], row['evidence_role']


def clause_bounds(text, start, end):
    lower, upper = 0, len(text)
    for h in CLAUSE_BOUNDARIES.finditer(text):
        if h.end() <= start:
            lower = h.end()
        elif h.start() >= end:
            upper = h.end() if h.group() == '?' else h.start()
            break
    return lower, upper


def scope(marker, source, lexical, dictionary):
    """Return source-span-backed guards, specific to this occurrence/category."""
    text = source['text'] or ''; norm = dictionary.normalize(text)
    start, end = marker['match_start'], marker['match_end']
    lower, upper = clause_bounds(norm, start, end)
    body = norm[lower:upper]; traces = []; blocked = False
    def trace(h, kind, block, offset=0):
        nonlocal blocked
        traces.append(dict(kind=kind, matched_expression=text[offset+h.start():offset+h.end()],
                           match_start=offset+h.start(), match_end=offset+h.end(),
                           applies_to_category=marker['category'], blocks_occurrence=block))
        blocked = blocked or block
    for h in HISTORY.finditer(body):
        trace(h, 'historical_reference', True, lower)
    for h in NONOP_SCOPED.finditer(body):
        trace(h, 'non_operational_explanation', True, lower)
    if '?' in body:
        h = re.search(r'\?', body); trace(h, 'question_about_this_occurrence', True, lower)
    peers = [m for m in lexical if m['match_start'] >= lower and m['match_end'] <= upper]
    for h in NEGATION.finditer(body):
        absolute = lower+h.start(); absolute_end = lower+h.end()
        # A nearby negation belongs to the closest named threat, not every family.
        closest = min(peers, key=lambda m: min(abs(absolute-m['match_end']), abs(absolute_end-m['match_start'])), default=marker)
        if closest['category'] != marker['category']:
            trace(h, 'negation_of_different_family', False, lower); continue
        before = norm[lower:start]
        immediate_ne = h.group() == 'не' and bool(re.search(r'\bне\s*$', before))
        targeted = immediate_ne or h.group() != 'не'
        if h.group() in {'нема','немає'}:
            between = norm[end:absolute] if absolute >= end else norm[absolute_end:start] if absolute_end <= start else ''
            targeted = bool(re.fullmatch(r'[\s—–\-:,]*', between))
        # Generic "не" in "не було ударів" is outcome, not threat cancellation.
        strike = next((x for x in NO_STRIKES.finditer(norm) if x.start() <= absolute < x.end()), None)
        if strike:
            trace(strike, 'no_strikes_is_not_no_threat', False); continue
        if targeted:
            trace(h, 'scoped_negation_or_unconfirmed', True, lower)
    for h in LOST.finditer(body):
        trace(h, 'lost_observation_not_retroactive_absence', True, lower)
    for h in CLEAR.finditer(body):
        absolute, absolute_end = lower+h.start(), lower+h.end()
        closest = min(peers, key=lambda m: min(abs(absolute-m['match_end']), abs(absolute_end-m['match_start'])), default=marker)
        trace(h, 'all_clear_or_destroyed_occurrence', closest['category'] == marker['category'], lower)
    for h in re.finditer(r'\bне\s+(?:на|до|над)\s+(?:ки[їє]в\w*|столиц\w*)', body):
        trace(h, 'explicit_geographic_exclusion', True, lower)
    for h in QUOTES.finditer(text):
        if h.start() <= start and end <= h.end():
            outside = norm[:h.start()]+norm[h.end():]
            warning_outside = bool(re.search(r'загроз\w*|пуск\w*|лет\w*|курс\w*|ворож\w*', outside))
            trace(h, 'quoted_threat_reference', not warning_outside)
    for h in EXTRA_GUARDS.finditer(body):
        trace(h, 'v16_explicit_noncurrent_or_negative', True, lower)
    for h in re.finditer(r'\bне\s+(?:спостеріга\w*|фіксу\w*|актив\w*)|\bвідсутн\w*|\bбез\s+(?:ціл\w*|баліст\w*)', body):
        closest = min(peers, key=lambda m: min(abs(lower+h.start()-m['match_end']), abs(lower+h.end()-m['match_start'])), default=marker)
        trace(h, 'v16_current_absence', closest['category'] == marker['category'], lower)
    for h in re.finditer(r'\bнема(?:є)?\b|\bне\s+було\b', body):
        closest = min(peers, key=lambda m: min(abs(lower+h.start()-m['match_end']), abs(lower+h.end()-m['match_start'])), default=marker)
        no_launch_only = marker['category'] in {'mig31','strategic_aviation'} and bool(re.search(r'пуск\w*[^.!?;]{0,15}(?:нема(?:є)?|не\s+було)|(?:нема(?:є)?|не\s+було)[^.!?;]{0,15}пуск\w*', body))
        no_strikes = bool(re.search(r'удар\w*[^.!?;\n]{0,20}не\s+було|не\s+було[^.!?;\n]{0,20}удар\w*', body))
        trace(h, 'v16_absence_of_named_threat', closest['category'] == marker['category'] and not no_launch_only and not no_strikes, lower)
    for h in re.finditer(r'короткі\s+висновки\s+за\s+ніч|давайте\s+коротко\s+відповімо|сповістили\s+першими|(?:надіюсь|сподіваюсь)\s+не\s+зустрінемось|(?:буде|нестись)\s+істерика', norm):
        trace(h, 'explicit_explanation_summary_or_future_speculation', True)
    if marker['category'] in {'mig31','strategic_aviation'}:
        for h in re.finditer(r'вивід\s+бортів\s+з-під\s+удару|загроз\w*\s+не\s+нес\w*[, ]+борти|з\s+метою\s+перебазування', norm):
            trace(h, 'aircraft_explicitly_non_threatening_mission', True)
    for h in re.finditer(r'який\s+жах|жахіття|версії\s+експертів\s+телеграм', norm):
        trace(h, 'satirical_or_speculation_list', True)
    # Record outcome scope even where the occurrence is in a different sentence.
    for h in NO_STRIKES.finditer(norm):
        if not any(t['kind'] == 'no_strikes_is_not_no_threat' for t in traces):
            trace(h, 'no_strikes_is_not_no_threat', False)
    return blocked, traces, text[lower:upper]


def operational(marker, source, lexical, dictionary, enabled):
    blocked, traces, clause = scope(marker, source, lexical, dictionary)
    if blocked:
        return False, 'v16_scoped_exclusion', traces
    hard = [x for x in HARD if x in (marker.get('exclusion_reason') or '')]
    if hard:
        return False, 'specificity_or_dictionary_exclusion', traces
    if marker['subtype'] == 'mig_takeoff_unspecified_model':
        return False, 'ambiguous_aircraft_model', traces
    if marker['subtype'] == 'mig_channel_model_unspecified':
        full = dictionary.normalize(bulletin(source['text'] or '')).strip(' \n\t+⚠️❗🛫✈️🚀.,!😳')
        finite = bool(re.fullmatch(r'(?:знову\s+)?(?:міг|миг|mig)(?:\s+(?:знову|\d+\s*шт))?', full))
        explicit = bool(re.search(r'(?<!\w)(?:міг|миг|mig)(?:у|а|ів|и|ам)?\s+(?:в\s+повітрі|у\s+повітрі|зліт)|тривог\w*\s+по\s+(?:міг|миг)(?:у|а|ів|и|ам)?|(?:зліт|підйом)\s+(?:міг|миг)(?:у|а|ів|и|ам)?', full))
        if finite or explicit: return True, 'v16_user_confirmed_mig_channel_bulletin', traces
        return False, 'ambiguous_verb_or_aircraft_commentary', traces
    if BYPASS.search(clause):
        return False, 'route_bypasses_kyiv', traces
    old_ok, old_reason = old_operational(marker, source)
    if old_ok:
        return True, old_reason, traces
    if 'A' not in enabled:
        return False, old_reason, traces
    norm = dictionary.normalize(clause); full = dictionary.normalize(bulletin(source['text'] or ''))
    geo, _ = dictionary.geographic_evidence(full, source['text'] or '')
    explicit = marker['evidence_status'] in {'current_threat', 'explicit_alert_cause'}
    qualified = bool(re.search(r'ворож\w*\s+бпл[аa]|загроз\w*\s+(?:застосув\w*\s+)?балістичн\w*\s+озброєнн\w*|балістик\w*\s+(?:з|зі|із|від)\s+\w+|(?:бпл[аa]|дрон\w*)\s+(?:між|над|біля|поблизу|в\s+районі)\s+\w+', full))
    route_supported, _, route_rule, _ = geography(marker, source, dictionary)
    reactive_move = marker['category'] == 'jet_uav' and marker.get('inferred_shorthand') and bool(MOVE.search(full)) and (
        geo in {'explicit_kyiv', 'kyiv_region', 'other_region'} or route_rule == 'route_destination_near_kyiv')
    if marker['evidence_status'] == 'historical_or_summary' and 'scope' not in enabled:
        return False, 'legacy_history_guard', traces
    if marker['evidence_status'] == 'negated_or_cancelled' and 'scope' not in enabled:
        return False, 'legacy_negation_guard', traces
    if explicit or qualified or reactive_move:
        return True, 'v16_complete_operational_statement', traces
    if 'operational' in dictionary.policy['enabled_v16_corrections']:
        current = current_statement(marker, norm, full, dictionary)
        if current: return True, 'v16_' + current, traces
    return False, old_reason, traces


def geography(marker, source, dictionary):
    norm = dictionary.normalize(bulletin(source['text'] or ''))
    full_geo, mentions = dictionary.geographic_evidence(norm, source['text'] or '')
    relevant = full_geo in {'explicit_kyiv', 'nationwide'}
    # A place explicitly named as an origin is not the final destination.
    flattened = ' '.join(norm.split())
    route = re.search(r'(?:на|до|над|між)\s+(.+)', flattened)
    destination_geo = None
    if route:
        destination_geo, _ = dictionary.geographic_evidence(route.group(1), route.group(1))
    if marker['geography'] == 'other_region' and destination_geo in {'explicit_kyiv', 'kyiv_region'} and MOVE.search(norm):
        return True, False, 'route_destination_near_kyiv', full_geo
    confined = confined_to_other_region(marker, dictionary)
    if marker['geography_source'] == 'message_fallback' and full_geo in {'other_region','uncertain'}:
        clause_geo, _ = dictionary.geographic_evidence(dictionary.normalize(marker['evidence_context']), marker['evidence_context'])
        if clause_geo == 'unspecified' and full_geo == 'other_region': confined = True
        foreign = any(p.search(norm) for p in dictionary.base.geography['other_region'])
        if clause_geo == 'unspecified' and full_geo == 'uncertain' and foreign and not marker.get('relevant_to_kyiv') and not any(m['category'] == 'explicit_kyiv' for m in mentions): confined = True
    return relevant or bool(marker.get('relevant_to_kyiv')), confined, 'literal_geography_or_official_interval', full_geo


def process(features, messages, links, baseline_markers, dictionary, alerts, policy, cache=None):
    enabled = set(policy['enabled_corrections']); cache = {} if cache is None else cache
    mm = {m['message_id']: m for m in messages if m['message_id'] is not None}
    seq = defaultdict(list); members = defaultdict(set)
    for l in links:
        seq[l['alert_id']].append(mm[l['message_id']]); members[l['message_id']].add(l['alert_id'])
    baseline = {key(r): r for r in baseline_markers if r['evidence_role'] == 'lexical_anchor'}
    timed = sorted([m for m in messages if m['message_time'] is not None and m.get('text') and m.get('message_type') == 'message'], key=order)
    times = [m['message_time'] for m in timed]; out = []
    for f in features:
        aid = f['alert_id']; eligible = is_eligible(f)
        if not eligible:
            continue
        pre = pre_window(f['start_time'], times, timed, policy['pre_alert_minutes'])
        timeline = sorted(pre+seq[aid], key=order)
        active = []; last_time = None
        for source in timeline:
            evaluation_source = dict(source, text=dictionary.context_view(source['text'] or ''))
            text = bulletin(evaluation_source['text']); relation = 'before_alert' if source['message_time'] < f['start_time'] else 'inside_interval'
            explicit_pre_reference = relation == 'inside_interval' and bool(CAUSE_REF.search(text)) and any(
                r['time_relation'] == 'before_alert' for r in active)
            if last_time and (source['message_time']-last_time).total_seconds() > policy['context_max_gap_minutes']*60 and not explicit_pre_reference:
                active = []
            active = [r for r in active if (source['message_time']-mm[r['anchor_message_id']]['message_time']).total_seconds() <= policy['context_anchor_max_minutes']*60]
            if CLEAR.search(text) or LOST.search(text) or NEW_OBJECT.search(text) or ABSENCE_CLEAR.search(text):
                event = (CLEAR.search(source['text'] or '') or LOST.search(source['text'] or '') or NEW_OBJECT.search(source['text'] or '') or ABSENCE_CLEAR.search(source['text'] or ''))
                for anchor in active:
                    ref = context_reference(anchor, source, 'unspecified', [], False, f['start_time'])
                    ref.update(classification_version='v1.6', attribution_version='v1.6', source_classification_version='v1.5',
                               v15_accepted=False, threat_identified=False, linking_confidence='episode_stopped',
                               exclusion_reason='lost_observation_or_episode_reset', scope_trace=[dict(
                                   kind='lost_observation_stops_propagation_not_retroactive_absence' if LOST.search(text) else 'episode_boundary',
                                   matched_expression=event.group(), match_start=event.start(), match_end=event.end(),
                                   applies_to_category=anchor['category'], blocks_occurrence=True)])
                    out.append(ref)
                active = []
            if source['message_id'] not in cache:
                cache[source['message_id']] = dictionary.classify(source['text'] or '')
            lexical = cache[source['message_id']]; rows = []
            for marker in lexical:
                row = annotate(marker, source, aid, relation)
                old = baseline.get(key(row)); row['baseline_accepted'] = bool(old and old['accepted_for_aggregation'])
                row.update(classification_version='v1.6', attribution_version='v1.6', source_classification_version='v1.5',
                           source_dictionary_version='v1.5',
                           v15_accepted=row['baseline_accepted'], v15_exclusion_reason=old['exclusion_reason'] if old else None,
                           correction_causes=[], attribution_rule_ids=[], accepted_for_aggregation=False,
                           threat_identified=True, linking_confidence='unresolved', geographic_relevance_status='unresolved')
                if old and old['accepted_for_aggregation']:
                    row['uncertainty_flag'] = old['uncertainty_flag']
                    row['uncertainty_reasons'] = list(old['uncertainty_reasons'])
                ok, reason, traces = operational(marker, evaluation_source, lexical, dictionary, enabled)
                if old and old['accepted_for_aggregation'] and not any(t['blocks_occurrence'] for t in traces) and not any(
                        x in (marker.get('exclusion_reason') or '') for x in HARD) and (
                        marker['evidence_status'] in {'current_threat','explicit_alert_cause'} or old['operational_status'] == 'operational'):
                    ok, reason = True, 'v15_valid_scoped_evidence_retained'
                row.update(operational_status='operational' if ok else 'non_operational_or_unresolved', operational_rule_id=reason,
                           scope_trace=traces, exclusion_reason=reason if not ok else 'alert_association_requires_review')
                required = []
                if not row['v15_accepted']:
                    if marker['lexical_rule_source'] == 'task0048_approved_expression': required.append('B')
                    if reason == 'v16_complete_operational_statement' or old and not old['accepted_for_aggregation']: required.append('A')
                    if old and old['exclusion_reason'] == 'negation_or_history': required.append('scope')
                row['correction_causes'] = required
                row['v16_correction_causes'] = []
                if marker['rule_id'] in dictionary.extension_ids: row['v16_correction_causes'].append('lexical')
                if dictionary.context_view(source['text'] or '') != (source['text'] or ''): row['v16_correction_causes'].append('boilerplate')
                if reason.startswith('v16_'): row['v16_correction_causes'].append('operational')
                row['context_view_excluded_spans'] = [dict(match_start=h.start(), match_end=h.end(), original_text=h.group()) for h in dictionary.boilerplate.finditer(source['text'] or '')] if 'boilerplate' in dictionary.policy['enabled_v16_corrections'] else []
                relevant, confined, geo_rule, full_geo = geography(marker, evaluation_source, dictionary)
                row.update(full_message_geography=full_geo, geographic_relevance_status='supported_literal' if relevant else 'confined_other_region' if confined else 'official_interval_association',
                           geography_attribution_rule=geo_rule)
                if relation == 'before_alert':
                    previous, boundaries, unresolved = contamination(aid, f['start_time'], source, alerts, members)
                    row.update(previous_alert_ids=previous, intervening_boundary_alert_ids=boundaries,
                               unresolved_envelope_alert_ids=unresolved,
                               minutes_before_alert=(f['start_time']-source['message_time']).total_seconds()/60)
                    row['exclusion_reason'] = 'pre_alert_requires_in_alert_correspondence' if ok else reason
                    if previous or boundaries or unresolved:
                        row['exclusion_reason'] = 'previous_alert_or_boundary_contamination'
                elif ok and not confined:
                    causes = required
                    row['baseline_accepted'] = bool(row['v15_accepted'])
                    accept(row, 'v15_preserved_valid' if row['v15_accepted'] else 'direct_operational_threat', causes,
                           ['v16_scoped_guard', geo_rule], 'experimental_operational_association')
                    row['linking_confidence'] = 'direct'
                elif confined:
                    row['exclusion_reason'] = 'explicit_other_region_pending_route_followup'
                # Valid frozen positives survive narrower new lexical priority arbitration.
                if relation == 'inside_interval' and row['v15_accepted'] and reason == 'specificity_or_dictionary_exclusion' and not any(t['blocks_occurrence'] for t in traces):
                    if 'dictionary_exclusion' not in (marker['exclusion_reason'] or ''):
                        accept(row, 'v15_preserved_valid', [], ['v15_valid_evidence_retained'], 'baseline_uncertainty')
                rows.append(row); out.append(row)
            negative_families = {r['category'] for r in rows if any(t['blocks_occurrence'] and t['kind'] in {
                'scoped_negation_or_unconfirmed','all_clear_or_destroyed_occurrence',
                'lost_observation_not_retroactive_absence','explicit_geographic_exclusion','v16_current_absence','v16_absence_of_named_threat'} for t in r['scope_trace'])}
            active = [r for r in active if r['category'] not in negative_families]
            candidates = [r for r in rows if r['operational_status'] == 'operational' and not any(x in (r['baseline_exclusion_reason'] or '') for x in HARD)]
            if candidates:
                cats = {r['category'] for r in candidates}
                if active and cats != {r['category'] for r in active}: active = []
                # Non-route, explicitly foreign threats cannot hop to an unrelated city.
                active = [r for r in candidates if r['geographic_relevance_status'] != 'confined_other_region'
                          or bool(re.search(r'\bкурс(?:ом|у|и|ів)?\b|\bнапрям\w*', text, re.I))]
            elif active and text and len(text.split()) <= policy['short_bulletin_max_tokens'] and not CLEAR.search(text) and not LOST.search(text) and not NEW_OBJECT.search(text):
                norm = dictionary.normalize(text); geo, mentions = dictionary.geographic_evidence(norm, source['text'] or '')
                cause = bool(CAUSE_REF.search(norm))
                recognized = geo in {'explicit_kyiv', 'kyiv_region'} or any(m['category'] == 'explicit_kyiv' for m in mentions)
                movement = bool(MOVE.search(norm) or MOVEMENT_REFERENCE.search(norm))
                body_nonop = bool(NONOP_SCOPED.search(norm) or EXTRA_GUARDS.search(norm) or re.search(r'висновки|відповімо|істерика|сповістили\s+першими', norm))
                ref_negation = bool(re.search(r'без\s+(?:загроз|ціл\w*)|відсутн\w*|не\s+підтверджен\w*|нема(?:є)?\s+(?:бпла|дрон\w*|загроз\w*)', norm))
                distinct = {r['category'] for r in active}
                for anchor in active:
                    clean = not (anchor['previous_alert_ids'] or anchor['intervening_boundary_alert_ids'] or anchor['unresolved_envelope_alert_ids'])
                    bounded = len(distinct) == 1 and not body_nonop and not ref_negation and '?' not in text and clean
                    corroboration = bounded and relation == 'inside_interval' and (cause or recognized)
                    pending_foreign = anchor['geographic_relevance_status'] == 'confined_other_region'
                    allow = 'C' in enabled or anchor['v15_accepted']
                    if not anchor['accepted_for_aggregation'] and allow and corroboration:
                        if anchor['time_relation'] == 'before_alert' and ('D' in enabled or anchor['v15_accepted']):
                            accept(anchor, 'pre_alert_contextually_supported', anchor['correction_causes']+['C','D'],
                                   ['ten_minute_pre_alert', 'v16_in_alert_correspondence'], 'retrospective_pre_alert_link')
                        elif anchor['time_relation'] == 'inside_interval' and (not pending_foreign or movement):
                            accept(anchor, 'contextually_supported_threat', anchor['correction_causes']+['C'],
                                   ['v16_bounded_route_followup'], 'route_identity_and_kyiv_relationship_inferred')
                        if anchor['accepted_for_aggregation']:
                            anchor['support_message_ids'].append(source['message_id'])
                            anchor['linking_confidence'] = 'explicit_pronominal' if cause else 'bounded_contextual'
                            anchor['geographic_relevance_status'] = 'supported_by_followup'
                            if cause and anchor['time_relation'] == 'before_alert':
                                anchor['attribution_rule_ids'].append('explicit_pre_cause_reference_within_ten_minutes')
                    unambiguous = allow and bounded and (cause or recognized or movement) and geo != 'other_region' and anchor['accepted_for_aggregation']
                    ref = context_reference(anchor, source, geo, mentions, unambiguous, f['start_time'])
                    ref.update(classification_version='v1.6', attribution_version='v1.6', evidence_role='context_reference',
                               v15_accepted=False,
                               linking_confidence='explicit_pronominal' if cause else 'bounded_contextual' if unambiguous else 'ambiguous',
                               threat_identified=False, scope_trace=[], source_classification_version='v1.5')
                    if unambiguous:
                        ref['correction_causes'] = sorted(set(anchor['correction_causes']) | {'C'})
                        ref['attribution_rule_ids'].append('v16_explicit_cause_reference' if cause else 'v16_bounded_update')
                    out.append(ref)
            last_time = source['message_time']
    for row in out:
        source = mm[row['message_id']]
        row['context_view_excluded_spans'] = [dict(match_start=h.start(), match_end=h.end(), original_text=h.group()) for h in dictionary.boilerplate.finditer(source['text'] or '')] if 'boilerplate' in dictionary.policy['enabled_v16_corrections'] else []
    features_out = aggregate(features, out, mm)
    for f in features_out:
        f.update(classification_version='v1.6', attribution_version='v1.6', source_classification_version='v1.5',
                 dictionary_version='v1.6')
    return out, features_out
