"""Package Task0049 derived outputs for local review; no Git or raw exports."""
import argparse
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',type=Path,default=Path('/workspace/downloads'));args=parser.parse_args()
    root=args.root.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    folders=['data/processed/classification_v1_6','reports/classification_v1_6','src/kyiv_alerts/classification_v16','docs']
    paths=[p for folder in folders for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    paths += [root/p for p in ['README.md','config/attribution_v1_6.yaml','config/task0049_exception_audit.yaml','tests/test_attribution_v16.py','tests/test_attribution_v15.py','scripts/validate_v16.py','scripts/export_v16_review.py']]
    bundle=out/'task0049_v16_bundle.zip'
    with ZipFile(bundle,'w',ZIP_DEFLATED) as archive:
        for path in paths:archive.write(path,str(path.relative_to(root)))
        archive.writestr('TASK0049_BUNDLE_README.txt','EXPERIMENTAL — HUMAN VALIDATION REQUIRED\nDerived v1.6 outputs and changed implementation/docs only; no raw export or prior frozen datasets.\nReproduction requires the existing KSHE_alert_test workspace with frozen inputs/profiles.\nRun python -m kyiv_alerts.classification_v16 --root . then python scripts/validate_v16.py --root .\nNo Git commit/push or forecasting has been performed.\n')
    with ZipFile(bundle) as archive:assert archive.testzip() is None
    for name in ['classification_comparison.md','time_series_handoff.md']:
        shutil.copyfile(root/'reports/classification_v1_6'/name,out/('task0049_'+name))
    print(json.dumps(dict(bundle=str(bundle),bytes=bundle.stat().st_size,files=len(paths)),ensure_ascii=False))


if __name__=='__main__':main()
