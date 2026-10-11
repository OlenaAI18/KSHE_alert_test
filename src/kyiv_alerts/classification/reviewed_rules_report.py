"""Compare reviewed contextual rules with frozen geographic and original baselines."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time
import pyarrow.parquet as pq
from kyiv_alerts.ingestion.__main__ import file_hash
from kyiv_alerts.ingestion.timeutils import KYIV
from .geography_review import feature_summary,marker_key,sample_changes,write_csv,indexed
from .rules import CATEGORIES


def compare(bm,nm,bf,nf,messages):
    old=indexed(bm,marker_key);new=indexed(nm,marker_key)
    # Updated lexical rules may add candidates; existing occurrences remain traceable.
    if not set(old)<=set(new):raise ValueError('Reviewed rules lost a pre-existing lexical candidate')
    oldf=indexed(bf,lambda r:r['alert_id']);newf=indexed(nf,lambda r:r['alert_id'])
    if set(oldf)!=set(newf):raise ValueError('Official alert set changed')
    for aid,f in oldf.items():
        for key in ['start_time','end_time','duration_minutes','coverage_status','historical_range_relation','telegram_message_count','telegram_text_message_count']:
            if f[key]!=newf[aid][key]:raise ValueError('Source alert/coverage changed')
    mmap={m['message_id']:m for m in messages if m['message_id'] is not None}
    changes=[]
    for key,m in sorted(new.items()):
        before=old.get(key)
        if before:
            for field in ['category','subtype','matched_text','evidence_context','source_file','source_message_index']:
                if m[field]!=before[field]:raise ValueError('Existing candidate provenance changed')
            if all(m[k]==before[k] for k in ['geography','evidence_status','accepted_for_aggregation']):continue
        source=mmap[m['message_id']]
        changes.append(dict(alert_id=m['alert_id'],message_id=m['message_id'],rule_id=m['rule_id'],category=m['category'],subtype=m['subtype'],matched_text=m['matched_text'],evidence_status=m['evidence_status'],before_geography=before['geography'] if before else 'no_lexical_marker',after_geography=m['geography'],before_accepted=before['accepted_for_aggregation'] if before else False,after_accepted=m['accepted_for_aggregation'],before_exclusion=before['exclusion_reason'] if before else 'no_lexical_marker',after_exclusion=m['exclusion_reason'],geography_mentions=json.dumps(m['geography_mentions'],ensure_ascii=False),geography_source=m['geography_source'],context_status_original=m['context_status_original'],context_rule_id=m['context_rule_id'],relevance_rule_id=m['relevance_rule_id'],uncertainty_flag=m['uncertainty_flag'],evidence_qualifiers=json.dumps(m['evidence_qualifiers'],ensure_ascii=False),original_text=source['text'],original_timestamp=source['message_time_original'],source_file=m['source_file'],source_message_index=m['source_message_index'],reviewer_geography='',reviewer_kyiv_relevance='',reviewer_decision='',reviewer_notes=''))
    gained=sorted(aid for aid in newf if oldf[aid]['unknown'] and not newf[aid]['unknown'])
    lost=sorted(aid for aid in newf if not oldf[aid]['unknown'] and newf[aid]['unknown'])
    monthly=[]
    for month in sorted({f['start_time'].astimezone(KYIV).strftime('%Y-%m') for f in bf}):
        olds=[f for f in bf if f['start_time'].astimezone(KYIV).strftime('%Y-%m')==month]
        news=[newf[f['alert_id']] for f in olds]
        b,a=feature_summary(olds),feature_summary(news)
        monthly.append(dict(month=month,eligible_alerts=b['eligible_alerts'],before_classified=b['classified_alerts'],after_classified=a['classified_alerts'],before_rate=b['classified_share_of_eligible'],after_rate=a['classified_share_of_eligible']))
    return dict(before=feature_summary(bf),after=feature_summary(nf),gained_alert_ids=gained,lost_alert_ids=lost,old_candidate_records=len(old),new_candidate_records=len(new),new_lexical_candidates=len(set(new)-set(old)),newly_accepted_existing_candidates=sum(not old[k]['accepted_for_aggregation'] and new[k]['accepted_for_aggregation'] for k in old),previously_accepted_now_excluded_candidates=sum(old[k]['accepted_for_aggregation'] and not new[k]['accepted_for_aggregation'] for k in old),accepted_new_lexical_candidates=sum(new[k]['accepted_for_aggregation'] for k in set(new)-set(old)),context_rule_counts=dict(Counter(m['context_rule_id'] or 'unchanged' for m in nm if m['accepted_for_aggregation'])),relevance_rule_counts=dict(Counter(m['relevance_rule_id'] or 'unresolved' for m in nm if m['accepted_for_aggregation'])),accepted_with_uncertainty=sum(m['accepted_for_aggregation'] and m['uncertainty_flag'] for m in nm),monthly_comparison=monthly),changes


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,default=Path('data/processed/classification_v1_1'))
    parser.add_argument('--after',type=Path,default=Path('data/processed/classification_v1_2'))
    parser.add_argument('--messages',type=Path,default=Path('data/interim/telegram_messages.parquet'))
    parser.add_argument('--report',type=Path,default=Path('reports/classification_v1_2'))
    args=parser.parse_args(argv);start=time.perf_counter()
    paths={prefix+'_'+name:directory/(name+'.parquet') for prefix,directory in [('before',args.before),('after',args.after)] for name in ['message_threat_markers','alert_threat_features']}
    paths['messages']=args.messages
    hashes={k:file_hash(v) for k,v in paths.items()}
    tables={k:pq.read_table(v).to_pylist() for k,v in paths.items()}
    report,changes=compare(tables['before_message_threat_markers'],tables['after_message_threat_markers'],tables['before_alert_threat_features'],tables['after_alert_threat_features'],tables['messages'])
    sample=sample_changes(changes)
    args.report.mkdir(parents=True,exist_ok=True)
    write_csv(changes,args.report/'reviewed_rule_changes.csv');write_csv(sample,args.report/'reviewed_rule_sample.csv')
    report.update(task_status='TECHNICALLY COMPLETE',semantic_validation_status='PROVISIONAL — HUMAN VALIDATION REQUIRED',classification_version='v1.2-reviewed-rules',input_sha256=hashes,review_sample_size=len(sample),sampling_seed=20261010,reviewed_independent_reference_examples=0,precision=None,recall=None)
    if hashes!={k:file_hash(v) for k,v in paths.items()}:raise ValueError('Comparison input changed')
    report['elapsed_seconds']=round(time.perf_counter()-start,6)
    (args.report/'reviewed_rules_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# Task 004 — User-approved contextual rules','', '**PROVISIONAL — HUMAN VALIDATION REQUIRED**','',
           'Approved by the research lead on 2026-10-11. These rules describe alert threat context, not actual weapon deployment. Rule-design examples are not an independent labeled evaluation set; precision/recall are unavailable.', '',
           '| Metric | Geographic baseline | Reviewed rules |','| --- | ---: | ---: |']
    for k in ['classified_alerts','eligible_alerts','eligible_alerts_with_text','classified_share_of_eligible','classified_share_of_text']:
        lines.append(f"| {k} | {report['before'][k]} | {report['after'][k]} |")
    lines += ['', 'Newly classified alerts: '+str(len(report['gained_alert_ids']))+'; lost classifications: '+str(len(report['lost_alert_ids']))+'.', '',
              '| Category | Before | After |','| --- | ---: | ---: |']
    for c in CATEGORIES[:-1]:lines.append(f"| {c} | {report['before']['per_category_alert_counts'][c]} | {report['after']['per_category_alert_counts'][c]} |")
    lines += ['', '## Implemented interpretation','',
              'Kyiv locality + short threat bulletin is current threat. Center is Kyiv in this inspected channel; Bucha alone remains oblast. Named movement toward Kyiv and explicit Kyiv alert causes are relevant even when source text mentions suburbs. Bare Kinzhal launch warnings count as Kyiv-relevant context without changing unspecified literal geography. Probability qualifiers are included only as operational warnings and retained as uncertainty. Shakh is Shahed shorthand. Bare reactive shorthand is user-inferred Shahed context, not an independently established model; explicit jet UAV/model matches retain jet_uav and avoid overlapping double counting. Generic UAV stays generic.', '',
              'Negation/cancellation, historical summaries, questions, carrier explanations and unsupported hypotheses are still excluded. Unapproved generic locality aliases retain previous anchoring requirements. No cross-message object inference was added. A named city target is text interpretation, never independently verified geolocation. Literal geography, relevance rule, original context, promoted context and uncertainty remain separate trace fields.', '',
              'Accepted context rule counts: '+json.dumps(report['context_rule_counts']), '',
              'Accepted relevance rule counts: '+json.dumps(report['relevance_rule_counts']), '',
              'Accepted records with uncertainty: '+str(report['accepted_with_uncertainty']), '',
              'New lexical candidates: '+str(report['new_lexical_candidates'])+'; accepted: '+str(report['accepted_new_lexical_candidates']), '',
              'Existing candidate gains/losses: '+str(report['newly_accepted_existing_candidates'])+' / '+str(report['previously_accepted_now_excluded_candidates']), '',
              '## Monthly detection yield','', '| Month | Eligible | Before count | After count | Before rate | After rate |','| --- | ---: | ---: | ---: | --- | --- |']
    pct=lambda v:'unavailable' if v is None else f'{100*v:.2f}%'
    for m in report['monthly_comparison']:lines.append(f"| {m['month']} | {m['eligible_alerts']} | {m['before_classified']} | {m['after_classified']} | {pct(m['before_rate'])} | {pct(m['after_rate'])} |")
    lines += ['', '## Review','',f"{len(sample)} unique changed alert/message pairs in reviewed_rule_sample.csv; all review fields blank. Full candidate changes are in reviewed_rule_changes.csv. Sample is for error discovery, not unbiased population accuracy estimation.", '',
              'Remaining limitations: finite synonyms and localities; ambiguous general nouns; clause-level negation; route phrases can refer to origin/transit; probabilistic reports can be wrong; inferred reactive subtype is based on the research lead\'s channel convention. Historical coverage and unresolved time remain missing observations. Rule approval is not independent semantic validation.', '',
              'Input hashes: '+json.dumps(hashes),'',
              'Reproduce: `python -m kyiv_alerts.classification --dictionary config/threat_dictionary_v1_1.yaml --geography config/kyiv_geography_v1_1.yaml --output data/processed/classification_v1_2 --report reports/classification_v1_2`, then `python -m kyiv_alerts.classification.reviewed_rules_report`.','']
    (args.report/'reviewed_rules_report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(f"Reviewed rules: {report['before']['classified_alerts']} -> {report['after']['classified_alerts']}; added candidates={report['new_lexical_candidates']}; review examples={len(sample)}")
    return 0


if __name__=='__main__':raise SystemExit(main())
