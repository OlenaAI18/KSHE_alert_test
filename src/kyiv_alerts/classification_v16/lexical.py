"""Evidence-backed inflections and exact channel boilerplate masking."""
import re
from kyiv_alerts.classification_v15.lexical import Profile as PreviousProfile

BOILERPLATE = re.compile(r'^.*✙.*Український Єнот.*$|^\s*🦝\s*Новини з Сіверщини та Полтавщини\s*$|^\s*🔥\s*Збір помсти\s*$', re.M)


def mask_boilerplate(text):
    """Length-preserving context view; source strings and offsets remain original."""
    return BOILERPLATE.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m.group()), text)


class Profile:
    def __init__(self, dictionary_path, geography_path, policy14, policy15, policy):
        self.previous = PreviousProfile(dictionary_path, geography_path, policy14, policy15)
        self.base = self.previous.base
        self.policy = policy
        self.boilerplate = BOILERPLATE
        self.extension_ids = set()
        if 'lexical' in policy['enabled_v16_corrections']:
            for rule in policy['lexical_extensions']:
                if rule['subtype'] == 'mig_channel_model_unspecified' and not policy['mig_shorthand_approved']: continue
                self.base.rules.append((rule, re.compile(rule['pattern']), []))
                self.base.config['rules'].append(rule)
                self.extension_ids.add(rule['rule_id'])

    def context_view(self, text):
        return mask_boilerplate(text) if 'boilerplate' in self.policy['enabled_v16_corrections'] else text

    def classify(self, text):
        view = self.context_view(text)
        rows = self.previous.classify(view)
        for row in rows:
            # Recover original source wording at identical character positions.
            row['matched_text'] = text[row['match_start']:row['match_end']]
            for mention in row['geography_mentions']:
                mention['matched_text'] = text[mention['match_start']:mention['match_end']]
            if row['subtype'] == 'mig_channel_model_unspecified':
                row['uncertainty_flag'] = True
                row['inferred_shorthand'] = True
            row.update(dictionary_version='v1.6', source_dictionary_version='v1.5',
                       lexical_rule_source='task0049_evidence_supported_expression' if row['rule_id'] in self.extension_ids else row['lexical_rule_source'])
        return rows

    def normalize(self, text):
        return self.previous.normalize(text)

    def geographic_evidence(self, normalized, original):
        return self.previous.geographic_evidence(normalized, original)
