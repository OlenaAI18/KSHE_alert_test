"""Local delivery copies only; Task0048 explicitly forbids automatic commits."""
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'reports/classification_v1_5'
DATA = ROOT/'data/processed/classification_v1_5'
DEST = ROOT.parent/'downloads'


def main():
    required = ['classification_comparison.md', 'classification_comparison.json',
                'regression_cases.csv', 'false_positive_audit_20.xlsx',
                'validation_results.json', 'reproducibility_results.json']
    if any(not (REPORT/name).is_file() for name in required):
        raise ValueError('Generate and validate v1.5 before local delivery')
    DEST.mkdir(exist_ok=True)
    shutil.copy2(REPORT/'false_positive_audit_20.xlsx', DEST/'task0048_false_positive_audit_20.xlsx')
    shutil.copy2(REPORT/'classification_comparison.md', DEST/'task0048_classification_comparison.md')
    archive = DEST/'task0048_v15_bundle.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for folder in [REPORT, DATA]:
            for p in sorted(folder.iterdir()):
                if p.is_file():
                    z.write(p, p.relative_to(ROOT))
        for name in ['attribution_v1_5.yaml','task0048_reviewed_cases.yaml']:
            z.write(ROOT/'config'/name, 'config/'+name)
        for p in sorted((ROOT/'src/kyiv_alerts/classification_v15').glob('*.py')):
            z.write(p,p.relative_to(ROOT))
        for name in ['tests/test_attribution_v15.py','scripts/export_v15_review.py',
                     'docs/DECISIONS.md','docs/METHODOLOGY.md','docs/DATA_SOURCES.md','docs/VALIDATION_PLAN.md']:
            z.write(ROOT/name,name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    print(DEST/'task0048_false_positive_audit_20.xlsx')
    print(archive)


if __name__=='__main__':
    main()
