"""Composed frozen profile plus the Task0048-authorized narrow expressions."""
import re
from kyiv_alerts.classification_v14.lexical import LexicalProfile


class Profile:
    def __init__(self, dictionary_path, geography_path, policy_v14, policy):
        self.previous = LexicalProfile(dictionary_path, geography_path, policy_v14)
        self.base = self.previous.base
        extensions = policy['lexical_extensions'] if 'B' in policy['enabled_corrections'] else []
        self.extension_ids = {r['rule_id'] for r in extensions}
        for r in extensions:
            self.base.rules.append((r, re.compile(r['pattern']), [re.compile(p) for p in r['exclusions']]))
            self.base.config['rules'].append(r)

    def classify(self, text):
        rows = self.previous.classify(text)
        for row in rows:
            row.update(dictionary_version='v1.5', source_dictionary_version='v1.4',
                       lexical_rule_source='task0048_approved_expression' if row['rule_id'] in self.extension_ids else row['lexical_rule_source'])
        return rows

    def normalize(self, text):
        return self.previous.normalize(text)

    def geographic_evidence(self, normalized, original):
        return self.previous.geographic_evidence(normalized, original)
