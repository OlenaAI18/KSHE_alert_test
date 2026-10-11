"""Downloadable copies of the isolated Task 004.5 review, with no source writes."""
from pathlib import Path
import shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/controlled_review'
DEST=ROOT.parent/'downloads';DEST.mkdir(exist_ok=True)
for source,target in [('controlled_alert_review.xlsx','task0045_controlled_alert_review.xlsx'),('classification_error_trace.csv','task0045_classification_error_trace.csv'),('controlled_review_summary.md','task0045_controlled_review_summary.md')]:
    shutil.copy2(REPORT/source,DEST/target)
with zipfile.ZipFile(DEST/'task0045_controlled_review_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted(REPORT.iterdir()):
        if path.is_file():z.write(path,path.name)
    z.write(ROOT/'requirements-review.lock.txt','requirements-review.lock.txt')
    z.writestr('REVIEW_README.txt','DIAGNOSTIC SAMPLE — HUMAN REVIEW REQUIRED\nOpen controlled_alert_review.xlsx in Excel Desktop. Read README, select an alert in Alert Overview and follow its ID link to Full Message Timeline. Human fields are blank. All candidates remain provisional. Companion CSV files retain full original text and source provenance. No source classifications or dictionaries have been modified.\n')
print(DEST/'task0045_controlled_alert_review.xlsx')
