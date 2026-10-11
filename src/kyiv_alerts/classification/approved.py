"""User-authorized contextual rules, separately traced from literal text geography."""
import re


class ApprovedInterpretation:
    def __init__(self, config):
        self.config=config
        self.target=re.compile(config['city_target_prefix'])
        self.denied_target=re.compile(config['denied_target_prefix'])
        self.cause_city=re.compile(config['city_alert_prefix'])
        self.launch=re.compile(config['launch_pattern'])
        self.qualifier=re.compile(config['qualifier_pattern'])
        self.blocked=re.compile(config['blocked_context_pattern'])
        self.bulletin=re.compile(config['short_bulletin_allowed_tokens'])
        self.operational=re.compile(config['operational_pattern'])

    def evaluate(self, body, marker, clause_start, clause_markers):
        original=marker['evidence_status']
        status=original
        qualifiers=[hit.group() for hit in self.qualifier.finditer(body)]
        relevance=marker['geography'] in {'explicit_kyiv','nationwide'}
        relevance_rule='text_geography' if relevance else None
        context_rule=None
        # Text geography stays mixed/unspecified where that is what the text says.
        city_mentions=[m for m in marker['geography_mentions'] if m['category']=='explicit_kyiv' and m['resolution_status']!='needs_kyiv_anchor']
        targets=[]
        city_cause=False
        for location in city_mentions:
            offset=location['match_start']-clause_start
            if not (0<=offset<len(body)):
                continue  # no directional inference from another sentence
            prefix=body[:offset]
            end=location['match_end']-clause_start
            if location['locality_id']=='city_center' and any(m['category']=='kyiv_region' and 0<=m['match_start']-clause_start-end<=3 for m in marker['geography_mentions']):
                continue  # center of Bucha is not the Kyiv center shorthand
            if self.target.search(prefix) and not self.denied_target.search(prefix):
                targets.append(location)
            if self.cause_city.search(prefix):
                city_cause=True
        blocked=original in {'negated_or_cancelled','historical_or_summary'} or bool(self.blocked.search(body)) or marker['subtype']=='mig_takeoff_unspecified_model'
        if not blocked:
            if city_cause and (original=='explicit_alert_cause' or re.search(r'\bчерез\b',body)):
                relevance=True;relevance_rule='user.kyiv_alert_cause'
            elif targets:
                relevance=True;relevance_rule='user.toward_kyiv'
            elif marker['subtype']=='kinzhal' and self.launch.search(body) and marker['geography'] in {'unspecified','nationwide','explicit_kyiv'}:
                relevance=True;relevance_rule='user.kinzhal_launch_warning'
        short_bulletin=False
        if marker['geography_source']=='clause' and marker['geography']=='explicit_kyiv' and len(body)<=self.config['short_bulletin_max_characters']:
            residue=list(body)
            spans=[(m['match_start'],m['match_end']) for m in marker['geography_mentions']]
            spans += [(m['match_start'],m['match_end']) for m in clause_markers]
            for start,end in spans:
                lo,hi=max(0,start-clause_start),min(len(body),end-clause_start)
                if lo<hi:residue[lo:hi]=' '*(hi-lo)
            residual=self.qualifier.sub(' ',''.join(residue))
            short_bulletin=bool(self.bulletin.fullmatch(residual))
        if not blocked and original=='uncertain' and not qualifiers:
            if targets:
                status='current_threat';context_rule='user.toward_kyiv'
            elif short_bulletin:
                status='current_threat';context_rule='user.locality_threat_bulletin'
        uncertain_accepted=not blocked and original=='uncertain' and bool(qualifiers) and relevance and (bool(targets) or city_cause or short_bulletin or bool(self.operational.search(body)))
        if uncertain_accepted:
            context_rule='user.probabilistic_warning'
        context_allowed=not blocked and (status in {'current_threat','explicit_alert_cause'} or uncertain_accepted)
        return dict(evidence_status=status,context_status_original=original,context_rule_id=context_rule,relevant_to_kyiv=relevance,relevance_rule_id=relevance_rule,uncertainty_flag=bool(qualifiers) or status=='uncertain',evidence_qualifiers=qualifiers,context_allowed=context_allowed)
