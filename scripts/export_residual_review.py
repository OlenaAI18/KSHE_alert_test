"""Copy review-only artifacts to Git delivery and a local downloadable ZIP."""
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'reports/classification_v1_4/residual_review'
PUBLISH = ROOT/'review_downloads/task0047'
DOWNLOADS = ROOT.parent/'downloads'


def main():
    required = ['residual_segment_summary.md', 'residual_segment_summary.json',
                'residual_alert_segments.csv', 'residual_review_50.xlsx',
                'residual_review_alerts.csv', 'residual_full_timeline.csv',
                'residual_pre_alert_evidence.csv', 'false_positive_review_sample.csv',
                'no_linked_text_source_audit.csv', 'residual_post_alert_context.csv',
                'residual_human_review.csv', 'validation_results.json']
    if any(not (SOURCE/name).is_file() for name in required):
        raise ValueError('Generate and validate Task0047 before delivery')
    PUBLISH.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(exist_ok=True)
    for name in required:
        shutil.copy2(SOURCE/name, PUBLISH/name)
    shutil.copy2(SOURCE/'residual_review_50.xlsx', DOWNLOADS/'task0047_residual_review_50.xlsx')
    archive = DOWNLOADS/'task0047_residual_review_bundle.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in required:
            z.write(SOURCE/name, name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    print(PUBLISH)
    print(archive)


if __name__ == '__main__':
    main()
