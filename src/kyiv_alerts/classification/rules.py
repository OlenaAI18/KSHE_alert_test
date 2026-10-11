"""Small auditable rules: candidate mentions, context and text geography."""
from pathlib import Path
import re
import yaml
from .geography import GeographyDictionary
from .approved import ApprovedInterpretation

CONTEXTS = {'current_threat','explicit_alert_cause','historical_or_summary','negated_or_cancelled','uncertain'}
GEOGRAPHIES = {'explicit_kyiv','kyiv_region','other_region','nationwide','unspecified','uncertain'}
CATEGORIES = ['shahed_uav','jet_uav','ballistic_high_speed','cruise_missile','mig31','strategic_aviation','other','unknown']


class Dictionary:
    def __init__(self, path, geography_path=None):
        self.config = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
        c = self.config
        if c.get('dictionary_version') not in {'v1.0','v1.1','v1.3'} or c.get('category_order') != CATEGORIES:
            raise ValueError('Expected approved taxonomy version and category order')
        self.version = c['dictionary_version']
        self.localities = GeographyDictionary(geography_path) if geography_path else None
        self.classification_version = 'v1.1-geo' if self.localities else 'v1.0'
        self.geography_version = self.localities.version if self.localities else None
        self.approved = ApprovedInterpretation(c['interpretation_policy']) if self.version in {'v1.1','v1.3'} else None
        if self.approved:
            if self.geography_version != c['interpretation_policy']['required_geography_version']:
                raise ValueError('Reviewed contextual rules require matching geography v1.1')
            self.classification_version=c['interpretation_policy']['classification_version']
        elif self.geography_version == 'kyiv-geography-v1.1':
            raise ValueError('Geography v1.1 requires reviewed threat rules v1.1')
        self.rules = []
        seen = set()
        for rule in c['rules']:
            if rule['rule_id'] in seen or rule['category'] not in CATEGORIES[:-1]:
                raise ValueError('Duplicate rule ID or invalid marker category')
            if not rule['subtype']:
                raise ValueError('Missing subtype')
            seen.add(rule['rule_id'])
            pattern = re.compile(rule['pattern'])
            if pattern.search(''):
                raise ValueError('Empty-string dictionary match is forbidden')
            if self.version=='v1.3' and rule.get('inferred_shorthand') and (rule['category']!='jet_uav' or rule.get('uav_evidence_type')!='reactive_shorthand_inferred'):
                raise ValueError('Inferred reactive shorthand must retain jet group and auditable evidence type')
            self.rules.append((rule, pattern, [re.compile(x) for x in rule.get('exclusions', [])]))
        if {r['category'] for r,_,_ in self.rules} != set(CATEGORIES[:-1]):
            raise ValueError('Dictionary must implement every approved marker category')
        self.launch_negation = [re.compile(p) for p in c['launch_negation_patterns']]
        self.context = {k: [re.compile(p) for p in v] for k,v in c['context_rules'].items()}
        self.geography = {k: [re.compile(p) for p in v] for k,v in c['geography_rules'].items()}
        if set(self.context) != CONTEXTS or set(self.geography) != GEOGRAPHIES - {'uncertain','unspecified'}:
            raise ValueError('Invalid context/geography vocabulary')
        agg = c['aggregation']
        if not set(agg['accepted_contexts']) <= {'current_threat','explicit_alert_cause'} or not set(agg['accepted_geographies']) <= {'explicit_kyiv','nationwide'}:
            raise ValueError('Unsupported aggregation policy')

    def normalize(self, text):
        # Every source character maps to exactly one character: spans stay reversible.
        cfg = self.config['normalization']
        result = []
        for char in text:
            if char in cfg['hyphens']:
                char = '-'
            elif char in cfg['apostrophes']:
                char = "'"
            lowered = char.lower() if cfg['lowercase'] else char
            result.append(lowered if len(lowered) == 1 else char)
        return ''.join(result)

    @staticmethod
    def hits(patterns, text):
        return any(p.search(text) for p in patterns)

    def geo(self, text):
        found = {k for k,v in self.geography.items() if self.hits(v,text)}
        if 'nationwide' in found:
            return 'nationwide' if not (found & {'explicit_kyiv','kyiv_region','other_region'}) else 'uncertain'
        if len(found) > 1:
            return 'uncertain'
        return next(iter(found)) if found else 'unspecified'

    def geographic_evidence(self, normalized, original):
        if self.localities:
            return self.localities.resolve(normalized, original, self.geography)
        return self.geo(normalized), []

    def classify(self, text):
        if not text or not text.strip():
            return []
        normalized = self.normalize(text)
        message_geo, message_mentions = self.geographic_evidence(normalized, text)
        candidates = []
        # Clauses are deliberately bounded by sentences, semicolons and line breaks.
        for clause in re.finditer(r'[^\n.!?;]+[.!?;]?', normalized):
            body = clause.group()
            geography, mentions = self.geographic_evidence(body, text[clause.start():clause.end()])
            geography_source = 'clause'
            for mention in mentions:
                mention['match_start'] += clause.start()
                mention['match_end'] += clause.start()
            if geography == 'unspecified':
                geography, mentions = message_geo, message_mentions
                geography_source = 'message_fallback'
            clause_candidate_start = len(candidates)
            status = next((s for s in ['negated_or_cancelled','historical_or_summary','uncertain','explicit_alert_cause','current_threat'] if self.hits(self.context[s],body)), 'uncertain')
            for rule, pattern, exclusions in self.rules:
                for hit in pattern.finditer(body):
                    start, end = clause.start()+hit.start(), clause.start()+hit.end()
                    around = body[max(0,hit.start()-20):min(len(body),hit.end()+20)]
                    excluded = self.hits(exclusions,around)
                    marker_status = status
                    if re.match(r'\s+(?:немає|нема|не\s+(?:лет\w*|злет\w*|загрож\w*))\b',body[hit.end():]):
                        marker_status = 'negated_or_cancelled'
                    if rule['category'] not in {'mig31','strategic_aviation'} and self.hits(self.launch_negation, body):
                        marker_status = 'negated_or_cancelled'
                    if rule['subtype'] == 'mig_takeoff_unspecified_model':
                        marker_status = 'uncertain'
                    reason = []
                    if excluded:
                        reason.append('dictionary_exclusion')
                    if marker_status not in self.config['aggregation']['accepted_contexts']:
                        reason.append('context_'+marker_status)
                    if geography not in self.config['aggregation']['accepted_geographies']:
                        reason.append('geography_'+geography)
                    candidates.append(dict(category=rule['category'],subtype=rule['subtype'],matched_text=text[start:end],rule_id=rule['rule_id'],evidence_context=text[clause.start():clause.end()].strip(),evidence_status=marker_status,geography=geography,context_status_original=marker_status,context_rule_id=None,relevant_to_kyiv=geography in {'explicit_kyiv','nationwide'},relevance_rule_id='text_geography' if geography in {'explicit_kyiv','nationwide'} else None,uncertainty_flag=marker_status=='uncertain',evidence_qualifiers=[],geography_mentions=mentions,geography_source=geography_source,geography_dictionary_version=self.geography_version,classification_version=self.classification_version,accepted_for_aggregation=not reason,exclusion_reason=';'.join(reason) or None,dictionary_version=self.version,match_start=start,match_end=end,priority=rule['priority']))
            if self.version=='v1.3':
                byrule={r['rule_id']:r for r,_,_ in self.rules}
                for marker in candidates[clause_candidate_start:]:
                    rule=byrule[marker['rule_id']]
                    marker.update(uav_evidence_type=rule.get('uav_evidence_type'),inferred_shorthand=bool(rule.get('inferred_shorthand')))
            if self.approved:
                clause_markers=candidates[clause_candidate_start:]
                for marker in clause_markers:
                    interpretation=self.approved.evaluate(body,marker,clause.start(),clause_markers)
                    allowed=interpretation.pop('context_allowed')
                    marker.update(interpretation)
                    if self.version=='v1.3' and marker['inferred_shorthand']:
                        marker['uncertainty_flag']=True
                    reasons=['dictionary_exclusion'] if 'dictionary_exclusion' in (marker['exclusion_reason'] or '') else []
                    if not allowed:
                        reasons.append('context_'+marker['evidence_status'])
                    if not marker['relevant_to_kyiv']:
                        reasons.append('geography_'+marker['geography'])
                    marker['exclusion_reason']=';'.join(reasons) or None
                    marker['accepted_for_aggregation']=not reasons
        # Retain suppressed candidates too: exclusions and priority arbitration are auditable.
        selected = []
        for marker in sorted(candidates,key=lambda r:(-r['priority'],r['match_start'],r['rule_id'])):
            overlaps = any(marker['match_start'] < r['match_end'] and r['match_start'] < marker['match_end'] for r in selected)
            if overlaps and marker['exclusion_reason'] != 'dictionary_exclusion':
                marker['accepted_for_aggregation'] = False
                marker['exclusion_reason'] = ';'.join(filter(None,[marker['exclusion_reason'],'overlapping_specific_rule']))
            elif not marker['exclusion_reason'] or 'dictionary_exclusion' not in marker['exclusion_reason']:
                selected.append(marker)
        for marker in candidates:
            families = {'generic_uav': {'shahed_uav','jet_uav'}, 'unspecified_missile': {'ballistic_high_speed','cruise_missile'}}
            if marker['subtype'] in families and any(r is not marker and r['subtype']!=marker['subtype'] and r['category'] in families[marker['subtype']] and r['evidence_context'] == marker['evidence_context'] and 'dictionary_exclusion' not in (r['exclusion_reason'] or '') for r in candidates):
                marker['accepted_for_aggregation'] = False
                marker['exclusion_reason'] = ';'.join(filter(None,[marker['exclusion_reason'],'specific_family_in_clause']))
            marker.pop('priority')
        return sorted(candidates,key=lambda r:(r['match_start'],r['match_end'],r['rule_id']))
