"""Recorded signals, overlapping hypotheses and deterministic purposive sampling."""
from collections import Counter, defaultdict
import random
import re

from kyiv_alerts.attribution.core import bulletin
from kyiv_alerts.classification_v14.core import NONOP, RESET, NEGATED, MOVEMENT_REFERENCE
from kyiv_alerts.ingestion.timeutils import KYIV

SEED = 20261011
STATUS = 'DIAGNOSTIC — HUMAN REVIEW REQUIRED'
QUOTAS = {'A': 8, 'B': 8, 'C': 8, 'D': 6, 'E': 5, 'F': 5}
PRIMARY_PRIORITY = ('A', 'C', 'D', 'B', 'E', 'F')
HUMAN_FIELDS = ('human_categories', 'human_decision', 'confirmed_failure_type',
                'supporting_message_ids', 'human_comment', 'proposed_rule_correction')
# Detection-only probes. They assign no category and never enter the classifier.
GAP_PROBES = {
    'gap.reactive_variant': r'(?<!\w)реактив\w*(?!\w)',
    'gap.banderol_variant': r'(?<!\w)бандерол\w*(?!\w)',
    'gap.uav_spelling': r'(?<!\w)(?:бплт\w*|блп\w*|бп\s+ла|бпл)(?!\w)',
    'gap.euphemism': r'(?<!\w)(?:мандрівник\w*|жужик\w*|мопед\w*|балалайк\w*|герань\w*|герані)(?!\w)',
    'gap.unspecified_object': r'(?<!\w)(?:ціл(?:ь|і|ей|лю)|розвідник\w*|невідом\w*\s+об[ʼ’\x27]?єкт\w*)(?!\w)',
}
PATTERNS = {k: re.compile(v, re.I) for k, v in GAP_PROBES.items()}
RULES = {
    'A': 'At least one rejected in-alert v1.4 lexical_anchor (context references excluded). A rejection is not a confirmed error.',
    'B': 'At least one nonempty <=12-token in-alert bulletin, no lexical anchor in that message, no frozen NONOP/RESET/NEGATED match, with a recognized explicit-Kyiv locality or a frozen MOVEMENT_REFERENCE hit. No category is inferred.',
    'C': 'At least one diagnostic gap-probe span not overlapped by any recorded in-alert lexical anchor, outside frozen NONOP/RESET/NEGATED messages. Probes name possible wording gaps, not validated threat types.',
    'D': 'At least one rejected operational v1.4 pre-alert anchor in [start-10min,start), or an operational frozen-profile lexical readout in [end,end+10min). Boundary proximity does not establish the same event; no post-alert evidence is attributed.',
    'E': 'At least half of nonempty linked texts have frozen NONOP/RESET/NEGATED signals or every in-alert lexical anchor in that message is explicitly other-region-confined or negated/history/non-operational. This is a coarse recorded-signal proxy, not a semantic content judgment.',
    'F': 'No A/B/C/D signal, or <=2 text messages and no A/C/D signal. Sparse locality-only evidence can overlap B; other residual cases default to F. Insufficiency is a review hypothesis.',
}


def blank_human():
    return dict.fromkeys(HUMAN_FIELDS)


def gap_hits(text, markers):
    if NONOP.search(bulletin(text)) or RESET.search(text) or NEGATED.search(text):
        return []
    spans = [(m['match_start'], m['match_end']) for m in markers
             if m['evidence_role'] == 'lexical_anchor']
    result = []
    for rule, pattern in PATTERNS.items():
        for h in pattern.finditer(text):
            if not any(h.start() < end and start < h.end() for start, end in spans):
                result.append(dict(rule_id=rule, matched_text=h.group(), match_start=h.start(),
                                   match_end=h.end(), interpretation='diagnostic_only_no_category'))
    return sorted(result, key=lambda h: (h['match_start'], h['rule_id']))


def message_signals(message, markers, dictionary):
    text = message['text'] or ''
    body = bulletin(text)
    lexical = [m for m in markers if m['evidence_role'] == 'lexical_anchor']
    geo, mentions = dictionary.geographic_evidence(dictionary.normalize(text), text)
    blocked = bool(NONOP.search(body) or RESET.search(body) or NEGATED.search(body))
    nonop_reasons = {'explicit_other_region_without_kyiv_association', 'negation_or_history',
                     'non_operational_or_explanatory'}
    nonop = blocked or bool(lexical and all(m['exclusion_reason'] in nonop_reasons for m in lexical))
    elliptical = bool(body and len(body.split()) <= 12 and not lexical and not blocked
                      and (any(x['category'] == 'explicit_kyiv' for x in mentions)
                           or MOVEMENT_REFERENCE.search(body)))
    return dict(message_id=message['message_id'], rejected_lexical_count=sum(not m['accepted_for_aggregation'] for m in lexical),
                elliptical_signal=elliptical, gap_probes=gap_hits(text, lexical),
                nonoperational_signal=nonop, literal_geography=geo,
                locality_mentions=mentions)


def segment(feature, sequence, markers, dictionary, post_readouts):
    bymsg = defaultdict(list)
    for m in markers:
        if m['time_relation'] == 'inside_interval':
            bymsg[m['message_id']].append(m)
    textseq = [m for m in sequence if m['text'] and m['text'].strip()]
    signals = [message_signals(m, bymsg[m['message_id']], dictionary) for m in textseq]
    rejected = sum(s['rejected_lexical_count'] for s in signals)
    rejected_records = [m for m in markers if m['time_relation'] == 'inside_interval'
                        and m['evidence_role'] == 'lexical_anchor' and not m['accepted_for_aggregation']]
    elliptical = [s['message_id'] for s in signals if s['elliptical_signal']]
    gaps = [dict(message_id=s['message_id'], **h) for s in signals for h in s['gap_probes']]
    pre = [m for m in markers if m['time_relation'] == 'before_alert'
           and m['evidence_role'] == 'lexical_anchor' and m['operational_status'] == 'operational'
           and not m['accepted_for_aggregation']]
    post = [h for h in post_readouts if h['operational_status'] == 'operational']
    nonop = sum(s['nonoperational_signal'] for s in signals)
    conditions = dict(A=bool(rejected), B=bool(elliptical), C=bool(gaps), D=bool(pre or post),
                      E=bool(textseq and 2 * nonop >= len(textseq)))
    conditions['F'] = not any(conditions[g] for g in 'ABCD') or (
        len(textseq) <= 2 and not any(conditions[g] for g in 'ACD'))
    membership = [g for g in QUOTAS if conditions[g]]
    primary = next(g for g in PRIMARY_PRIORITY if conditions[g])
    diversity = sorted({
        *('rejection.'+str(m['exclusion_reason']) for m in rejected_records),
        *(h['rule_id'] for h in gaps),
        *('elliptical.'+s['literal_geography'] for s in signals if s['elliptical_signal']),
        *(['boundary.pre'] if pre else []), *(['boundary.post'] if post else []),
        'text_volume.'+('sparse' if len(textseq) <= 2 else 'medium' if len(textseq) < 20 else 'high'),
    })
    return dict(alert_id=feature['alert_id'], start_local=feature['start_time'].astimezone(KYIV).isoformat(),
                year=feature['start_time'].astimezone(KYIV).year,
                classification_status=feature['classification_status'], primary_segment=primary,
                diagnostic_segments=membership, diagnostic_rule_ids=['segment.'+g for g in membership],
                linked_message_count=len(sequence), linked_text_count=len(textseq),
                rejected_in_alert_lexical_count=rejected,
                rejected_in_alert_message_ids=sorted({m['message_id'] for m in rejected_records}),
                rejected_in_alert_rule_ids=sorted({m['rule_id'] for m in rejected_records}),
                recorded_rejection_reasons=dict(Counter(m['exclusion_reason'] for m in rejected_records)),
                elliptical_message_ids=elliptical,
                gap_probe_occurrences=gaps, potential_pre_alert_anchor_ids=sorted({m['message_id'] for m in pre}),
                potential_post_alert_anchor_ids=sorted({h['message_id'] for h in post}),
                nonoperational_signal_text_count=nonop,
                nonoperational_signal_share=nonop/len(textseq) if textseq else None,
                sampling_signal_types=diversity,
                source_information_status='diagnostic_not_validated',
                **{'segment_'+g: conditions[g] for g in QUOTAS})


def balanced_pick(rows, count, rng):
    """Seeded per-year pools, cycle years 2023..2026; no population inference."""
    pools = defaultdict(list)
    for row in sorted(rows, key=lambda r: r['alert_id']):
        pools[row['year']].append(row)
    for year in sorted(pools):
        rng.shuffle(pools[year])
    selected = []; observed = set()
    while len(selected) < count and any(pools.values()):
        for year in sorted(pools):
            if pools[year] and len(selected) < count:
                # Novel recorded signals within the next year take precedence;
                # the seeded order resolves ties without overriding year balance.
                pick = max(pools[year], key=lambda r: len(set(r.get('sampling_signal_types', []))-observed))
                pools[year].remove(pick); selected.append(pick)
                observed.update(pick.get('sampling_signal_types', []))
    return selected


def select_residual(segments, excluded, seed=SEED):
    rng = random.Random(seed)
    selected, audit = [], []
    for group, quota in QUOTAS.items():
        pool = [r for r in segments if r['primary_segment'] == group and r['alert_id'] not in excluded]
        chosen = balanced_pick(pool, quota, rng)
        selected += [dict(r, sample_role='residual', requested_segment=group, fallback=False) for r in chosen]
        audit.append(dict(segment=group, requested=quota, available=len(pool), selected=len(chosen),
                          shortfall=quota-len(chosen)))
    used = {r['alert_id'] for r in selected}
    fallback = balanced_pick([r for r in segments if r['alert_id'] not in excluded | used], 40-len(selected), rng)
    selected += [dict(r, sample_role='residual', requested_segment='fallback', fallback=True) for r in fallback]
    return selected, audit


def safety_risks(feature, markers):
    accepted = [m for m in markers if m['accepted_for_aggregation']]
    risks = []
    for category in ['ballistic_high_speed', 'strategic_aviation', 'jet_uav']:
        if feature[category] is True:
            risks.append(category)
    if any(m['time_relation'] == 'before_alert' or m['anchor_time_relation'] == 'before_alert' for m in accepted):
        risks.append('pre_alert')
    if any(m['geographic_uncertainty'] for m in accepted):
        risks.append('uncertain_geography')
    if feature['unique_threat_category_count'] > 1 and any(m['uncertainty_flag'] for m in accepted):
        risks.append('multiple_categories_uncertain_evidence')
    return risks


def select_safety(features, bymarker, excluded, seed=SEED):
    candidates = []
    for f in features:
        if f['baseline_categories'] or not f['unique_threat_category_count'] or f['alert_id'] in excluded:
            continue
        risks = safety_risks(f, bymarker[f['alert_id']])
        candidates.append(dict(alert_id=f['alert_id'], year=f['start_time'].astimezone(KYIV).year,
                               sample_role='false_positive_safety', diagnostic_segments=[],
                               primary_segment='not_applicable', safety_risk_flags=risks))
    candidates.sort(key=lambda r: r['alert_id'])
    random.Random(seed).shuffle(candidates)
    seen, years, selected = set(), Counter(), []
    while candidates and len(selected) < 10:
        pick = max(candidates, key=lambda r: (len(set(r['safety_risk_flags'])-seen),
                                             -years[r['year']], len(r['safety_risk_flags'])))
        candidates.remove(pick)
        selected.append(pick)
        seen.update(pick['safety_risk_flags'])
        years[pick['year']] += 1
    return selected
