"""Reuse approved engine with only explicitly authorized v1.4 alias extensions."""
import re,copy
from kyiv_alerts.classification.rules import Dictionary

class LexicalProfile:
    def __init__(self,dictionary_path,geography_path,policy):
        self.base=Dictionary(dictionary_path,geography_path)
        if self.base.version!='v1.3':raise ValueError('Frozen v1.3 lexical base required')
        self.extensions=copy.deepcopy(policy.get('user_approved_lexical_extensions',[]))
        for r in self.extensions:
            if r['category']!='jet_uav' or r['rule_id']!='jet_uav.banderol_user_confirmed':raise ValueError('Unapproved lexical extension')
            pattern=re.compile(r['pattern'])
            if pattern.search(''):raise ValueError('Empty alias')
            self.base.rules.append((r,pattern,[re.compile(x) for x in r.get('exclusions',[])]));self.base.config['rules'].append(r)
    def classify(self,text):
        markers=self.base.classify(text)
        extension_ids={r['rule_id'] for r in self.extensions}
        for m in markers:
            m.update(dictionary_version='v1.4',source_dictionary_version='v1.3',lexical_rule_source='user_confirmed_v1.4_alias' if m['rule_id'] in extension_ids else 'frozen_v1.3',classification_version='v1.4')
        return markers
    def normalize(self,text):return self.base.normalize(text)
    def geographic_evidence(self,normalized,original):return self.base.geographic_evidence(normalized,original)
