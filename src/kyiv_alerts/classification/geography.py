"""Optional auditable locality recognition; no inferred destination or geolocation."""
from pathlib import Path
import re
import yaml


class GeographyDictionary:
    def __init__(self, path):
        config = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
        self.version = config['dictionary_version']
        if self.version not in {'kyiv-geography-v1.0','kyiv-geography-v1.1'} or not config['localities']:
            raise ValueError('Expected approved nonempty geography dictionary')
        self.entries = {}
        self.patterns = []
        for entry in config['localities']:
            uid = entry['locality_id']
            if uid in self.entries or entry['category'] not in {'explicit_kyiv','kyiv_region'}:
                raise ValueError('Duplicate locality ID or unsupported category')
            self.entries[uid] = entry
            for i, pattern in enumerate(entry['patterns']):
                compiled = re.compile(pattern)
                if compiled.search(''):
                    raise ValueError('Empty locality match is forbidden')
                self.patterns.append((entry, f'{uid}.{i+1}', compiled))

    def resolve(self, normalized, original, legacy_patterns):
        candidates = []
        for entry, rid, pattern in self.patterns:
            for hit in pattern.finditer(normalized):
                candidates.append(dict(locality_id=entry['locality_id'],canonical_name=entry['canonical_name'],locality_type=entry['locality_type'],category=entry['category'],matched_text=original[hit.start():hit.end()],rule_id=rid,match_start=hit.start(),match_end=hit.end(),requires_kyiv_anchor=entry['requires_kyiv_anchor']))
        # Longer settlements, e.g. Sofiivska Borshchahivka, mask nested city aliases.
        selected = []
        for candidate in sorted(candidates,key=lambda m:(-(m['match_end']-m['match_start']),m['match_start'],m['rule_id'])):
            if not any(candidate['match_start'] < m['match_end'] and m['match_start'] < candidate['match_end'] for m in selected):
                selected.append(candidate)
        found = set()
        for category,patterns in legacy_patterns.items():
            for pattern in patterns:
                for hit in pattern.finditer(normalized):
                    # The new specific record supplies both the name and category.
                    # Mask a legacy broad hit only when its whole span is covered.
                    if any(m['match_start'] <= hit.start() and hit.end() <= m['match_end'] for m in selected):
                        continue
                    found.add(category)
        anchor = 'explicit_kyiv' in found or any(m['category']=='explicit_kyiv' and not m['requires_kyiv_anchor'] for m in selected)
        for mention in selected:
            mention['resolution_status'] = 'needs_kyiv_anchor' if mention['requires_kyiv_anchor'] and not anchor else 'provisional_lexical_match'
            found.add('uncertain' if mention['resolution_status']=='needs_kyiv_anchor' else mention['category'])
        geography = next(iter(found)) if len(found)==1 else 'uncertain' if found else 'unspecified'
        return geography, sorted(selected,key=lambda m:(m['match_start'],m['match_end'],m['rule_id']))
