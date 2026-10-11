"""Diagnostic families suggested by inspected source messages, NOT acceptance rules.

All matches generate review evidence only. This catalog cannot be used to
classify alerts or change the approved taxonomy. Broad families deliberately
include counterexamples; original messages and exclusions are retained.
"""
import re
from .core import word_ngrams, reasons

FAMILIES = [
 ('P01','reporting_format','Only a place / direction fragment','Троя; Оболонь; на Труханів','review_context_rule','requires_context_review: place-only wording does not establish threat type or active object.',None),
 ('P02','geography_alias','Colloquial/local landmark aliases','ПОХ; Борщаги; Протас; Заспа; нова забудова','review_geography_rule','Review place alias and city/oblast ambiguity separately; no threat category implied.',r'(?<!\w)(?:пох|борщаг(?:а|и|у|ів)?|протас(?:ів)?|заспа|заспу|нова забудова|нову забудову|тец\s*[456]|вєнік|венік|берковець|берковці)(?!\w)'),
 ('P03','context_shorthand','Elliptical direction','на місто; на водосховище; залітає','review_context_rule','requires_context_review: destination or movement without an explicitly identified object.',r'(?<!\w)(?:на місто|на водосховище|по водосховищу|на київ|в київ|у київ|залітає|заходить)(?!\w)'),
 ('P04','context_shorthand','Pronoun / numbered object','ще один; цей на; 1 на','review_context_rule','requires_context_review: referent unknown; do not infer a weapon from neighboring messages.',r'(?<!\w)(?:ще (?:один|одна|одне|\d+)|цей на|ця на|цей від|\d+ (?:на|від|над|біля))(?!\w)'),
 ('P05','tracking_status','Not currently detected / no observation','не фіксується; без фіксації; нема','keep_unknown','Detection status, not an independently confirmed absence or a weapon class.',r'(?<!\w)(?:не фіксується|без фіксації|всьо|все нема|нема|немає)(?!\w)'),
 ('P06','new_lexical_form','Reactive noun shorthand','реактив; реактиви','review_new_synonym','Possible lexical extension of approved reactive adjective; object/type and Kyiv relevance require review.',r'(?<!\w)реактив(?:и|ів|ом|у|а)?(?!\w)'),
 ('P07','euphemism','Parcel euphemism','бандероль; бандеролі','review_new_synonym','Potential object euphemism, not a verified UAV/Shahed category; preserve context and counterexamples.',r'(?<!\w)бандерол(?:ь|і|ей|лю|ями|ям)(?!\w)'),
 ('P08','other_subgroup','Reconnaissance vocabulary','розвідник; розвідувальний; розвідка','review_subcategory','Possible reconnaissance-context subgroup; not every reconnaissance reference is an active Kyiv UAV.',r'(?<!\w)(?:розвід\w*|розвідуваль\w*|развед\w*)(?!\w)'),
 ('P09','movement','Circling / repeated movement','кружляє; колами; накручує','review_context_rule','requires_context_review: movement describes an unidentified object unless explicit within the message.',r'(?<!\w)(?:кружля\w*|колами|накручу\w*|ходить по колу)(?!\w)'),
 ('P10','ambiguous_observation','Audible activity','гучно; чути; почули; вибух','keep_unknown','Sound/activity does not reliably distinguish threat family, interception or impact.',r'(?<!\w)(?:гучно|чути|почули|вибух\w*|гримить|чутно)(?!\w)'),
 ('P11','tracking_status','Terminal / falling / destroyed wording','падає; здох; закінчився; збито','keep_unknown','Terminal, colloquial or retrospective state is not automatically an active threat; referent may be absent.',r'(?<!\w)(?:падає|здох\w*|закінчив\w*|збит\w*|знищен\w*|буль буль)(?!\w)'),
 ('P12','potential_model_name','Model / decoy vocabulary','Гербера; Пародія; Молнія; ZALA','review_subcategory','Potential subgroup/model mentions; no automatic mapping to Shahed or operational threat.',r'(?<!\w)(?:гербер\w*|гернер\w*|пароді\w*|молні\w*|молни\w*|zala|ланцет\w*|орлан\w*)(?!\w)'),
 ('P13','ambiguous_slang','Unresolved object slang','хрін; шляпа; мопед; пташка','keep_unknown','Potential object nickname with strong non-operational collisions; do not assign a threat family.',r'(?<!\w)(?:хрін\w*|шляп\w*|мопед\w*|пташ\w*|балалай\w*|жуж\w*)(?!\w)'),
 ('P14','non_operational','Fundraising / donation','збір; донат; грн','exclude_non_operational','Likely fundraising/commentary; mixed messages may still contain operational text and need review.',r'(?<!\w)(?:збір|збору|збираємо|донат\w*|грн|грив\w*|банка|банку)(?!\w)'),
 ('P15','alert_status','Generic alert / button / cancellation','тривога; відбій; кнопка','keep_unknown','Official-alert or channel-status commentary does not identify a weapon category.',r'(?<!\w)(?:тривог\w*|відбій|відбою|кнопк\w*|укрит\w*)(?!\w)'),
 ('P16','existing_rejected_evidence','Lexical hit rejected by geography','existing candidate with geography exclusion','review_geography_rule','Inspect place and destination evidence; out-of-city reports can be correctly excluded.',None),
 ('P17','existing_rejected_evidence','Lexical hit rejected by uncertain context','existing candidate with context_uncertain','review_context_rule','Inspect uncertainty versus operational shorthand; cancellation/history must remain distinct.',None),
 ('P18','other_subgroup','Accepted generic UAV subgroup','other:generic_uav','review_subcategory','Generic UAV evidence does not establish Shahed; retain as generic unless independent source wording supports a subtype.',None),
 ('P19','other_subgroup','Accepted generic missile subgroup','other:unspecified_missile','review_subcategory','Generic missile evidence does not establish cruise/ballistic type; review only.',None),
 ('P20','other_subgroup','Accepted unspecified MiG subgroup','other:mig_takeoff_unspecified_model','keep_unknown','Unspecified aircraft model cannot be safely promoted to MiG-31K.',None),
]
COMPILED={pid:re.compile(rx,re.I) for pid,_,_,_,_,_,rx in FAMILIES if rx}


def diagnostic_matches(record, geography):
    body=record['normalized_text'];markers=record['markers'];matches=[]
    for pid,pattern in COMPILED.items():
        if pattern.search(body):matches.append(pid)
    # Literal standalone locality (including oblast), not a threat inference.
    if not markers and len(body.split())<=5 and body:
        _,hits=geography.resolve(body,body,{})
        covered=set()
        for h in hits:covered.update(range(h['match_start'],h['match_end']))
        residual=''.join(' ' if i in covered else ch for i,ch in enumerate(body)).split()
        if hits and all(t in {'на','до','над','біля','від','у','в','з','коло'} or t.isdigit() for t in residual):matches.append('P01')
    why=reasons(markers)
    if any(r.startswith('geography_') for r in why):matches.append('P16')
    if 'context_uncertain' in why:matches.append('P17')
    if any(m['accepted_for_aggregation'] and m['category']=='other' and m['subtype']=='generic_uav' for m in markers):matches.append('P18')
    if any(m['accepted_for_aggregation'] and m['category']=='other' and m['subtype']=='unspecified_missile' for m in markers):matches.append('P19')
    if any(m['accepted_for_aggregation'] and m['category']=='other' and m['subtype']=='mig_takeoff_unspecified_model' for m in markers):matches.append('P20')
    return sorted(set(matches))
