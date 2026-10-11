"""Run local Task 004.2 diagnostics against immutable reviewed-v1.2 inputs."""
import argparse
from collections import Counter
from importlib.metadata import version
import csv
import json
from pathlib import Path
import platform
import time
import pyarrow.parquet as pq
from kyiv_alerts.ingestion.__main__ import file_hash
from kyiv_alerts.validation.quality import json_default
from kyiv_alerts.classification.geography import GeographyDictionary
from .core import *
from .pipeline import prepare,baseline,discover_families,message_diagnostics,period_comparison,october_review,evidence_example


def write_csv(path,rows,columns=None):
    if not rows and not columns:columns=['no_observations']
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns or list(rows[0]));writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True,default=json_default) if isinstance(v,(list,dict)) else json_default(v) if hasattr(v,'isoformat') else v for k,v in row.items()})


def formatted(value,spec):
    return format(value,spec) if value is not None else 'unavailable'


def markdown(r):
    if r['task_status']=='BLOCKED':return '# Task 004.2 — BLOCKED\n\n'+r['error']+'\n'
    b=r['baseline'];o=r['october'];d=r['message_diagnostics']['text_unclassified'];lines=[
      '# Task 004.2 — Pattern discovery in unclassified air alert context','',
      '**TECHNICALLY COMPLETE — exploratory findings require human review.**','',
      '## Executive summary','',
      f"The reviewed baseline retains {b['total_alerts']:,} official alerts: {b['classified_alerts']} classified, {b['text_unclassified_alerts']} with text but no accepted marker. Classification yield is {formatted(b['classified_yield'],'.2%')} among {b['eligible_alerts']} historically eligible alerts. Neither source datasets, dictionaries nor classification outputs were modified.", '',
      f"October has {o['total_alerts']} alerts, {o['alerts_with_text']} with text, {o['specifically_classified_alerts']} specifically classified and {o['other_only_alerts']} other-only. The official alert dataset stops at start {r['official_last_start_kyiv']} / end {r['official_last_end_kyiv']}, while Telegram continues through {r['source_last_timestamp_kyiv']}. October alert observations therefore form a partial month. Place-only messages, unidentified moving objects, abbreviated/euphemistic nouns and tracking/cancellation language occur repeatedly; temporal linkage alone does not prove Kyiv relevance or weapon type.",'',
      '## Baseline reconciliation','',
      '| Population | Alerts | Meaning |','| --- | ---: | --- |']
    meanings={'specific_classified':'At least one accepted specific category; includes specific + other.','other_only':'Accepted other, no specific category.','text_unclassified':'Text exists, no accepted category.','unavailable_or_unresolved':'Unavailable history/text or unresolved timing; never a negative label.'}
    lines += [f"| {p} | {b['populations'].get(p,0)} | {meanings[p]} |" for p in POPULATIONS]
    lines+=['','Original statuses: '+json.dumps(b['classification_status_counts'],sort_keys=True), '',
      'Per-category counts (overlapping): '+json.dumps(b['per_category_alert_counts'],sort_keys=True),'',
      '## October diagnostic','',
      'Every October official alert appears in october_2026_alert_review.csv; every linked October message (including empty text) appears in chronological order in october_2026_messages.csv. Review fields are blank. The alert table retains no-text observations separately. Full texts and dictionary/exclusion evidence are preserved; no neighboring-message referent is inferred.','',
      'October summary: '+json.dumps(o,ensure_ascii=False,sort_keys=True),'',
      '## Why classification remains missing','',
      f"Among C's {d['total_text_messages']} messages, {d['subsets']['without_lexical_candidates']['unique_messages']} have no lexical candidate. {d['total_alerts']-d['subsets']['with_lexical_candidates']['unique_alerts']} C alerts have no lexical candidates anywhere in their linked text. Geography exclusions appear in {d['subsets']['with_geography_exclusions']['unique_alerts']} C alerts and uncertain-context exclusions in {d['subsets']['with_uncertain_context_exclusions']['unique_alerts']} C alerts; these subsets overlap.",'',
      'These are overlapping message subsets, not additive causes. A lexical miss may be a place-only update, commentary, donation, euphemism or an out-of-area report, and not necessarily a missed threat. A geography rejection can be correct. Uncertain context, history, cancellation and family/span suppression remain distinct.','']
    for p in POPULATIONS[1:3]:
        d=r['message_diagnostics'][p]
        lines += [f"### {p}: {d['total_alerts']} alerts / {d['total_text_messages']} text messages",'',
           '| Diagnostic subset | Unique messages | Unique alerts |','| --- | ---: | ---: |']
        lines += [f"| {name} | {v['unique_messages']} | {v['unique_alerts']} |" for name,v in d['subsets'].items()]
        lines += ['','Exclusion reasons (overlap): '+json.dumps(d['exclusion_reason_messages'],sort_keys=True),'']
    lines+=['## Recurring candidate families','',
      'Support counts refer to unique B/C alerts; families overlap and must not be summed. The transparent family catalog was assembled after inspecting October examples and complements data-driven n-grams and clusters. It is a diagnostic codebook, not an acceptance dictionary. No semantic labels were auto-approved.','',
      '| ID | Family | B/C alerts | C alerts | Messages | Proposed review |','| --- | --- | ---: | ---: | ---: | --- |']
    for p in r['candidate_patterns']:
        lines.append(f"| {p['pattern_id']} | {p['representative_phrase']} | {p['unique_alert_support']} | {p['text_unclassified_alert_support']} | {p['unique_message_support']} | {p['proposed_action']} |")
    lines += ['','Each supported family has 3–5 complete source examples where available in representative_examples.csv and the candidate table. P01/P03/P04/P09 are explicitly requires_context_review. Generic UAV/missile/unspecified-MiG subgroups are not promoted to specific categories. Acoustic, terminal, slang and absence-of-detection phrases remain unknown unless independently reviewed.','',
      '## Historical vocabulary and format drift','',
      '| Period | Eligible | With text | Specific | Other-only | Text unclassified | Mean linked messages / eligible | Median |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for p in r['period_comparison']:
        lines.append(f"| {p['period']} | {p['eligible_alerts']} | {p['alerts_with_text']} | {p['specifically_classified_alerts']} | {p['other_only_alerts']} | {p['text_unclassified_alerts']} | {formatted(p['mean_linked_messages_per_eligible_alert'],'.2f')} | {p['median_linked_messages_per_eligible_alert']} |")
    lines+=['','Distinctive phrases are smoothed period-versus-other-period B/C alert-prevalence ratios, with support >=3 alerts; they are descriptive, not significance tests. Newly prominent families require >=3 current alerts and a smoothed current-versus-prior text-alert-normalized rate ratio >=2 (screening heuristic, no significance claim). Character fragments are useful for spelling discovery but not interpretable threat labels. Period-normalized supports and complete denominators are in period_comparison.csv; candidate and n-gram CSVs also retain month-level support.','']
    for p in r['period_comparison']:
        phrases=p['most_distinctive_candidate_phrases'][:8]
        lines += [f"- **{p['period']}**: "+'; '.join(f"{x['phrase']} ({x['unique_alert_support']} alerts)" for x in phrases)]
    lines+=['',f"Reporting format drift: alerts containing at least one <=3-token analytical message rise from {formatted(r['period_comparison'][1]['short_message_alert_share'],'.1%')} in 2024 to {formatted(r['period_comparison'][-2]['short_message_alert_share'],'.1%')} in August–September 2026 and {formatted(r['period_comparison'][-1]['short_message_alert_share'],'.1%')} in the partial October window. Literal standalone-place fragments occur in {formatted(r['period_comparison'][1]['standalone_place_alert_share'],'.1%')}, {formatted(r['period_comparison'][-2]['standalone_place_alert_share'],'.1%')}, and {formatted(r['period_comparison'][-1]['standalone_place_alert_share'],'.1%')} respectively (denominator: alerts with text). Noun/euphemism drift is retained per family in candidate_patterns.csv and period_comparison.csv; newly prominent candidates are descriptive screening suggestions. These families may involve oblast objects, not necessarily city threats.",'',
      'The incomplete October window and first partial 2023 period cannot be compared by raw calendar totals. Increased place/route-only reporting can reduce lexical classification even when message density is high. These observations establish reporting/vocabulary changes only, not a new military threat regime.','',
      '## Other-only subgroups','',
      'Accepted subtypes within B (overlap): '+json.dumps(r['other_only_accepted_subgroups'],sort_keys=True)+'. Generic labels are not new specific weapon categories.','',
      '## Frequency analysis and similarity grouping','',
      'Analysis-only NFKC/case/apostrophe normalization and Ukrainian/Cyrillic/Latin/digit tokenization preserve originals separately. URLs, standalone decorated channel footer lines and unbroken numeric strings of five or more digits and grouped 16-digit card numbers are removed only from analytical text (bank/account/link noise); short numeric operational forms remain. Word 1–3-grams retain short abbreviations; only all-function-word phrases are filtered. Character 3–5-grams include word boundaries. Frequencies are binary per message and binary per alert; one repeated burst cannot dominate unique-alert support. Comparison reference is specifically classified A; diagnostic target is B/C.','',
      'Sparse TF-IDF combines word and character features. MiniBatchKMeans uses sorted unique normalized texts, fixed seed, single-thread math and alert-balanced sample weights. Cosine similarity is computed only to the assigned normalized centroid, in bounded chunks. No dense N×N matrix, remote API, hosted model or embeddings service was used. Clusters are exploratory and can mix unrelated meanings.','',
      'Grouping configuration: '+json.dumps(r['grouping'],ensure_ascii=False,sort_keys=True),'',
      '## Potential dictionary improvements and exploratory coverage ceiling','',
      'Recommended review order: (1) reactive-noun and parcel wording in full operational context; (2) missing locality aliases, keeping city versus suburb separate; (3) generic-UAV reconnaissance/model subgroups; (4) elliptical routing and place-only bulletins, for which object type cannot be recovered from one message automatically. Cancellations/terminal states, sounds, donations and carrier explanations should not become broad threat synonyms.','',
      json.dumps(r['exploratory_potential'],ensure_ascii=False,sort_keys=True),'',
      'These are upper bounds on a human review queue, not predicted improvements: some/all candidates may remain unknown. The lower bound of independently validated additional classifications is zero. No new accepted marker or alert category has been produced. Broad geography/context screening is separately reported to avoid presenting its large union as plausible confirmed gain.','',
      '## Human decisions required','',
      '- Decide whether reactive-noun and parcel euphemisms are object mentions and whether their type can be distinguished; inspect non-operational collisions.',
      '- Confirm ambiguous landmarks/aliases independently, especially city versus oblast; place-only text cannot supply a weapon category.',
      '- Decide whether generic-UAV reconnaissance/decoy subgroups belong in the existing taxonomy or only in descriptive subtypes.',
      '- Define a reviewed policy for elliptic object references; do not transfer a weapon identity from a previous message automatically.',
      '- Annotate positives and counterexamples, adjudicate, then evaluate a held-out set before any versioned rule change.','',
      '## Limitations and reproducibility','',
      'Current classification and exploratory families lack independent semantic validation. Precision/recall are null. Families and clusters overlap, broad lexical matches can include summaries or irrelevant geography, and a channel convention may not generalize. TF-IDF/KMeans and smoothed prevalence are discovery tools, not causal, forecast or weapon confirmation models. Frequency feature vocabulary is capped at 70,000 per analyzer and min_df=3; rare forms can be missed and are still exposed in October full-text evidence.','',
      'Run: `.venv/bin/python -m kyiv_alerts.pattern_discovery` (install local analysis dependencies from requirements-analysis.lock.txt). The command refuses missing/stale reviewed inputs and records all input hashes. Tests and rerun verification are recorded separately in docs/VALIDATION_PLAN.md.','',
      'Input hashes unchanged: '+str(r['input_hashes_unchanged'])+'. Baseline matched current classification report: '+str(r['baseline_reconciled'])+'.',
      'Input SHA-256: '+json.dumps(r['input_sha256'],sort_keys=True),'',
      'Software: '+json.dumps(r['software_versions'],sort_keys=True),'',
      f"Runtime: {r['elapsed_seconds']:.3f} seconds; outputs are deterministic except execution runtime metadata.",'']
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--report',type=Path,default=Path('reports/pattern_discovery'))
    parser.add_argument('--seed',type=int,default=20261011)
    parser.add_argument('--groups',type=int,default=64)
    args=parser.parse_args(argv)
    if args.groups<=0:parser.error('groups must be positive')
    root=args.root.resolve();output=args.report.resolve();started=time.perf_counter()
    paths={name:root/p for name,p in dict(alerts='data/interim/alerts.parquet',messages='data/interim/telegram_messages.parquet',links='data/processed/alert_message_links.parquet',coverage='data/processed/alert_coverage.parquet',features='data/processed/classification_v1_2/alert_threat_features.parquet',markers='data/processed/classification_v1_2/message_threat_markers.parquet',dictionary='config/threat_dictionary_v1_1.yaml',geography='config/kyiv_geography_v1_1.yaml',baseline_report='reports/classification_v1_2/classification_report.json',reviewed_report='reports/classification_v1_2/reviewed_rules_report.json').items()}
    protected_dirs=[root/'data',root/'config',root/'reports/classification',root/'reports/classification_v1_1',root/'reports/classification_v1_2',root/'reports/temporal_linking',root/'reports/data_quality']
    if any(output==p or output.is_relative_to(p) for p in protected_dirs):parser.error('Diagnostic report must be separate from source/config/prior-report directories')
    # Hash all retained parquet/config/prior reports, not just files loaded here.
    protected=set(paths.values())|set((root/'data').rglob('*.parquet'))|set((root/'config').glob('*.yaml'))
    for folder in ['classification','classification_v1_1','classification_v1_2','temporal_linking','data_quality']:
        protected.update(p for p in (root/'reports'/folder).glob('*') if p.is_file())
    r={'task_status':'BLOCKED'}
    try:
        hashes={k:file_hash(p) for k,p in paths.items()}
        protected_hashes={str(p.relative_to(root)):file_hash(p) for p in sorted(protected)}
        previous=json.loads(paths['baseline_report'].read_text());reviewed=json.loads(paths['reviewed_report'].read_text())
        if previous['classification_version']!='v1.2-reviewed-rules':raise ValueError('Reviewed v1.2 classification report required')
        for key in ['alerts','messages','links','coverage','dictionary','geography']:
            if previous['input_sha256'][key]!=hashes[key]:raise ValueError('Input differs from reviewed classification run: '+key)
        for key,reportkey in [('features','after_alert_threat_features'),('markers','after_message_threat_markers')]:
            if reviewed['input_sha256'][reportkey]!=hashes[key]:raise ValueError('Reviewed output hash differs: '+key)
        tables={k:pq.read_table(paths[k]).to_pylist() for k in ['alerts','messages','links','coverage','features','markers']}
        records,byalert,fm=prepare(**tables)
        b=baseline(tables['features'])
        for actual,expected in [('total_alerts','total_processed_alerts'),('eligible_alerts_with_text','alerts_with_telegram_text'),('classified_alerts','alerts_with_detected_category')]:
            if b[actual]!=previous[expected]:raise ValueError('Classification baseline count differs: '+actual)
        if b['per_category_alert_counts']!=previous['per_category_alert_counts'] or b['classification_status_counts']!=previous['classification_status_counts']:raise ValueError('Classification baseline distribution differs')
        if b['eligible_alerts']!=reviewed['after']['eligible_alerts']:raise ValueError('Eligible baseline differs')
        patterns,examples,assignments=discover_families(records,GeographyDictionary(paths['geography']))
        print(f"Baseline reconciled: {len(tables['features'])} alerts; {b['classified_alerts']} classified; populations={b['populations']}",flush=True)
        words,distinctive,wordmeta=frequency_analysis(records,'word')
        chars,_,charmeta=frequency_analysis(records,'char')
        print('Word and character n-gram supports computed with sparse matrices.',flush=True)
        groups,clusters,groupmeta=group_similar(records,args.seed,args.groups)
        periods=period_comparison(tables['features'],records,patterns,distinctive)
        october=october_review(tables['features'],byalert)
        october_messages=[]
        for row in october:
            for m in byalert[row['alert_id']]:
                e=evidence_example('october_all_linked',m)
                e.update(pattern_ids=m.get('pattern_ids',[]),message_type=m['message_type'],has_text=bool(m.get('text') and m['text'].strip()),review_status='')
                october_messages.append(e)
        diag=message_diagnostics(records)
        c=[r for r in records if r['population']=='text_unclassified']
        lexical_ids={'P06','P07','P08','P12'}
        lexical={r['alert_id'] for r in c if lexical_ids & set(r['pattern_ids'])}
        broad={r['alert_id'] for r in c if {'P16','P17'} & set(r['pattern_ids'])}
        other_subgroups=[]
        other_rows=[r for r in records if r['population']=='other_only']
        for subtype in sorted({m['subtype'] for r in other_rows for m in r['markers'] if m['accepted_for_aggregation'] and m['category']=='other'}):
            hit=[r for r in other_rows if any(m['accepted_for_aggregation'] and m['category']=='other' and m['subtype']==subtype for m in r['markers'])]
            other_subgroups.append(dict(subtype=subtype,unique_alert_support=len({r['alert_id'] for r in hit}),unique_message_support=len({r['message_id'] for r in hit})))
        named=set()
        geo=GeographyDictionary(paths['geography'])
        for x in c:
            if lexical_ids & set(x['pattern_ids']):
                literal,mentions=geo.resolve(x['normalized_text'],x['normalized_text'],{})
                if literal=='explicit_kyiv':named.add(x['alert_id'])
        potential=dict(validated_additional_classifications=0,lexical_review_upper_bound_alerts=len(lexical),lexical_review_pattern_ids=sorted(lexical_ids),
            lexical_review_with_literal_city_upper_bound_alerts=len(named),lexical_review_upper_bound_total_classified=b['classified_alerts']+len(lexical),
            lexical_review_upper_bound_eligible_yield=(b['classified_alerts']+len(lexical))/b['eligible_alerts'],
            broad_context_geography_review_ceiling_alerts=len(broad),union_lexical_and_broad_screening_ceiling_alerts=len(lexical|broad),
            interpretation='Review workload/maximum candidate overlap only; includes irrelevant, cancelled and ambiguous texts; no gain is validated or predicted.')
        o=dict(total_alerts=len(october),eligible_alerts=sum(r['historically_eligible'] for r in october),alerts_with_text=sum(r['linked_text_count']>0 for r in october),
              specifically_classified_alerts=sum(r['population']=='specific_classified' for r in october),other_only_alerts=sum(r['population']=='other_only' for r in october),text_unclassified_alerts=sum(r['population']=='text_unclassified' for r in october),
              unavailable_or_unresolved_alerts=sum(r['population']=='unavailable_or_unresolved' for r in october),linked_text_messages=sum(r['linked_text_count'] for r in october),
              messages_without_lexical_candidates=sum(r['messages_without_lexical_candidates'] for r in october),candidate_marker_records=sum(r['candidate_marker_count'] for r in october),
              candidate_exclusion_reason_messages=dict(Counter(reason for row in october for reason,n in row['candidate_exclusion_reasons'].items() for _ in range(n))),
              period_note='Partial official October alert starts through October 4; last interval ends October 5 Kyiv time. Telegram continues through October 10; no full-month comparison.')
        r=dict(task_status='TECHNICALLY COMPLETE',semantic_validation_status='EXPLORATORY — HUMAN REVIEW REQUIRED',baseline=b,baseline_reconciled=True,
           input_sha256=hashes,protected_input_sha256=protected_hashes,baseline_version='v1.2-reviewed-rules',october=o,message_diagnostics=diag,
           candidate_patterns=patterns,other_only_accepted_subgroups=other_subgroups,period_comparison=periods,frequency_analysis=dict(word=wordmeta,character=charmeta),grouping=groupmeta,
           exploratory_potential=potential,source_first_timestamp_kyiv=min(m['message_time'] for m in tables['messages'] if m['message_time']).astimezone(KYIV),
           source_last_timestamp_kyiv=max(m['message_time'] for m in tables['messages'] if m['message_time']).astimezone(KYIV),
           official_last_start_kyiv=max(f['start_time'] for f in tables['features']).astimezone(KYIV),official_last_end_kyiv=max(f['end_time'] for f in tables['features'] if f['end_time']).astimezone(KYIV),
           seed=args.seed,precision=None,recall=None,independently_reviewed_examples=0,
           quality_checks=dict(valid_task003_provenance=True,source_spans_valid=True,all_alerts_retained=True,populations_exhaustive_and_disjoint=sum(b['populations'].values())==b['total_alerts'],original_classification_unchanged=True,unique_alert_ranking=True,no_cross_message_inference=True),
           software_versions={n:version(n) for n in ['pyarrow','numpy','scipy','scikit-learn','threadpoolctl']},python_version=platform.python_version())
        output.mkdir(parents=True,exist_ok=True)
        outputs={'candidate_patterns.csv':patterns,'october_2026_alert_review.csv':october,'period_comparison.csv':periods,'representative_examples.csv':examples,
          'word_ngram_frequency.csv':words,'character_ngram_frequency.csv':chars,'similarity_groups.csv':clusters,'similarity_assignments.csv':groups,'pattern_assignments.csv':assignments,'october_2026_messages.csv':october_messages}
        for name,rows in outputs.items():write_csv(output/name,rows)
        if protected_hashes!={str(p.relative_to(root)):file_hash(p) for p in sorted(protected)}:raise ValueError('Protected input changed during discovery')
        r['input_hashes_unchanged']=True
        print(f"Candidate families={len(patterns)}; October text alerts={o['alerts_with_text']}; lexical review ceiling={len(lexical)} (not validated gain)",flush=True)
    except (OSError,ValueError,TypeError,KeyError) as exc:r={'task_status':'BLOCKED','error':str(exc)}
    r['elapsed_seconds']=round(time.perf_counter()-started,6)
    output.mkdir(parents=True,exist_ok=True)
    (output/'pattern_discovery_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True,default=json_default)+'\n',encoding='utf-8')
    (output/'pattern_discovery_report.md').write_text(markdown(r),encoding='utf-8')
    print(f"Task 004.2: {r['task_status']}; seconds={r['elapsed_seconds']}",flush=True)
    return 0 if r['task_status']=='TECHNICALLY COMPLETE' else 1


if __name__=='__main__':raise SystemExit(main())
