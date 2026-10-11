"""Reproduce Task 002.1 reviewed-example comparison directly from immutable raw inputs."""
import argparse
import json
from pathlib import Path
from kyiv_alerts.ingestion.alerts import parse_alerts
from kyiv_alerts.ingestion.telegram import parse_telegram
from kyiv_alerts.ingestion.__main__ import file_hash
from kyiv_alerts.validation.time_alignment import compare_example, summarize, dst_interval_candidates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alerts', type=Path, default=Path('data/raw/airAlert_2026-10-10.json'))
    parser.add_argument('--telegram', type=Path, default=Path('data/raw/ChatExport_2026-10-10 (1).zip'))
    parser.add_argument('--sample', type=Path, default=Path('config/time_alignment_sample.json'))
    parser.add_argument('--report', type=Path, default=Path('reports/data_quality'))
    args = parser.parse_args(argv)
    manifest = json.loads(args.sample.read_text(encoding='utf-8'))
    for key, path in [('alerts', args.alerts), ('telegram', args.telegram)]:
        if file_hash(path) != manifest['source_sha256'][key]:
            raise ValueError(f'{key} source hash differs from reviewed sample')
    alerts = {r['alert_id']: r for r in parse_alerts(args.alerts)}
    messages, metadata = parse_telegram(args.telegram)
    if metadata['duplicate_identifier_occurrences'] or metadata['html_parse_errors']:
        raise ValueError('Investigate source duplicates or HTML errors before using sample')
    messages = {r['message_id']: r for r in messages if r['message_id'] is not None}
    examples = [compare_example(messages[r['message_id']], alerts[r['alert_id']], r['event'])
                for r in manifest['samples']]
    summaries = summarize(examples)
    summer = summaries['daylight_time']
    supported = (summer['n'] >= 10 and summer['h2']['matching_rates']['300'] >= 0.9
                 and summer['h1']['matching_rates']['300'] <= 0.1
                 and summaries['standard_time']['h2']['matching_rates']['300'] >= 0.9)
    decision = 'H2 SUPPORTED' if supported else 'BLOCKED'
    evidence = {'decision': decision, 'source_sha256': manifest['source_sha256'],
                'sample_manifest_sha256': file_hash(args.sample),
                'summaries': summaries, 'examples': examples,
                'excluded_examples': manifest['excluded_examples'],
                'dst_interval': {'alert_id': '1837', 'status': 'unresolved; no fold selected',
                                 'candidates': dst_interval_candidates(alerts['1837'])}}
    lines = ['# Task 002.1 — Time alignment verification', '', f'Outcome: **{decision}**.', '',
             '## Method and scope', '',
             '28 manually reviewed Kyiv-city/capital start/end announcements across 2023–2026. Geography and event text were inspected before freezing references in config/time_alignment_sample.json. Region-only alerts, predictions, commentary and jokes are excluded; examples and reasons appear below. This is exploratory, purposive verification, not a random accuracy sample or statistical significance test. No production alert/message links are generated.', '',
             'H1 honors the exported UTC+02:00 suffix. H2 interprets the displayed clock in Europe/Kyiv and ignores that non-seasonal suffix for this inspected export. Both are compared against the same manually reviewed Kyiv Digital boundary, not against separate nearest events selected for each hypothesis. Positive signed differences mean the message was later than the official boundary.', '',
             'Descriptive matching means absolute difference <=5 minutes; sensitivity at 1, 3 and 10 minutes is also recorded. These are publication-lag diagnostics, not Task 003 linking rules. The exploratory decision gate requires at least 10 daylight examples, >=90% H2 agreement within 5 minutes in each season, and <=10% H1 daylight agreement. Winter/standard-time examples cannot discriminate H1 from H2; summer/daylight examples do.', '',
             'Sample includes the start/end pair for alert 796, which fixes event identity independently of choosing separate nearest boundaries. Forwarded city bulletins 14568 and 15068 include clock times in their body. Message 47859 explicitly announces 00:00 for Kyiv, matching alert 2395 (00:00:51); H1 would incorrectly place it around 01:00, near a different later alert. Forwarding delays are included using publication timestamps, not replaced with embedded original times.', '',
             '## Quantitative comparison', '',
             '| Group | N | H1 median signed (min) | H1 median absolute (min) | H1 <=5 min | H2 median signed (min) | H2 median absolute (min) | H2 <=5 min |',
             '| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |']
    for group, summary in summaries.items():
        a, b, n = summary['h1'], summary['h2'], summary['n']
        lines.append(f"| {group} | {n} | {a['median_signed_seconds']/60:.3f} | {a['median_absolute_seconds']/60:.3f} | {a['matching_counts']['300']}/{n} | {b['median_signed_seconds']/60:.3f} | {b['median_absolute_seconds']/60:.3f} | {b['matching_counts']['300']}/{n} |")
    lines += ['', '## Fixed reviewed examples', '',
              '| Message ID | Original Telegram title | Event | Alert ID | Kyiv Digital local boundary | H1 signed min | H2 signed min |',
              '| --- | --- | --- | --- | --- | ---: | ---: |']
    for r in examples:
        lines.append(f"| {r['message_id']} | {r['original_timestamp']} | {r['event']} | {r['alert_id']} | {r['official_timestamp_original']} | {r['h1_signed_difference_seconds']/60:.3f} | {r['h2_signed_difference_seconds']/60:.3f} |")
    lines += ['', '## Reviewed message excerpts', '']
    for r in examples:
        excerpt = r['text_excerpt'].replace('\n', ' / ').replace('|', '\\|')
        lines.append(f"- {r['message_id']} ({r['source_file']}, element {r['source_message_index']}): {excerpt}")
    lines += ['', '## Excluded examples', '']
    lines += [f"- {r['message_id']}: {r['reason']}" for r in manifest['excluded_examples']]
    lines += ['', '## Near-DST coverage and limitations', '',
              'Messages 14469 (2024-10-27, transition day after the change), 14568 (2024-10-29), 15068 (2024-11-02), and 25060 (2025-03-28, before the spring change) provide near-transition coverage. No unambiguous city boundary announcement at the exact 2025-10-26 repeated-hour end was found. Predicted city all-clears near transitions were excluded instead of treated as confirmed ends. The sample does not establish every historical message lag or solve DST folds. H2 is the source-specific interpretation supported by reviewed examples; future exports require their own validation.', '',
              '## DST-ambiguous Kyiv Digital alert 1837', '',
              'Start 2025-10-26T02:27:00 is unambiguous (2025-10-25T23:27:00Z). End 2025-10-26T03:05:12 has two admissible instants:', '',
              '| Fold | Local end | UTC end | Duration minutes |', '| --- | --- | --- | ---: |']
    for c in evidence['dst_interval']['candidates']:
        lines.append(f"| {c['fold']} | {c['local_end']} | {c['utc_end']} | {c['duration_minutes']:.3f} |")
    lines += ['', 'Both candidates follow the start and precede the next official alert (2025-10-27T18:35:44); neighboring intervals do not resolve the fold. Message 35433 says reconnaissance at 02:58:06, while 35434 at 03:05:19 asks about Fastiv district, not a Kyiv all-clear. These are not unequivocal end announcements. End UTC and duration remain null. Under H2, Telegram IDs 35434–35441 also lie in the ambiguous 03:00 hour and must remain unresolved rather than inheriting the misleading export offset. No automatic fold is selected.', '',
              '## Supported normalization rule', '',
              'For the inspected Telegram Desktop titles DD.MM.YYYY HH:MM:SS UTC+02:00, localize the displayed clock to Europe/Kyiv using the pinned tzdata package, then convert to UTC only if the instant is unique. Preserve the exact original title. Do not apply a global -1-hour shift: standard-time values remain unchanged; daylight-time values differ by one hour from H1. Ambiguous/nonexistent clocks remain null with explicit statuses. Other explicit ISO/offset formats retain their existing interpretation; the evidence applies to this export, not all Telegram data.', '',
              '## Reproduction and source integrity', '',
              'From the repository root with the project installed: `python scripts/verify_time_alignment.py`. The script verifies raw hashes, reloads real records and the frozen sample, and writes this report plus time_alignment.json. That JSON contains per-example UTC instants, source-file/index provenance, signed differences and matching-rate sensitivity. Reports remain ignored by Git; only reference IDs and source hashes are versioned.', '',
              f"Alerts SHA-256: {manifest['source_sha256']['alerts']}", '',
              f"Telegram SHA-256: {manifest['source_sha256']['telegram']}", '']
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / 'time_alignment.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.report / 'time_alignment.md').write_text('\n'.join(lines), encoding='utf-8')
    print(decision)
    print(json.dumps(summaries, indent=2))
    return 0 if supported else 1


if __name__ == '__main__':
    raise SystemExit(main())
