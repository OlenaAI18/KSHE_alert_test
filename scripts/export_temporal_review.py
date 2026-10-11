"""Package authorized Task005 derived outputs/documents, without raw exports."""
from pathlib import Path
import argparse,hashlib,json,zipfile

def export(root):
    files=[]
    for folder in ('data/processed/temporal_analysis','reports/temporal_analysis','src/kyiv_alerts/temporal_analysis'):
        files.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.extend(root/p for p in ('tests/test_temporal_analysis.py','tests/test_attribution_v16.py','requirements-temporal.lock.txt','README.md','docs/METHODOLOGY.md','docs/DATA_DICTIONARY.md','docs/DATA_SOURCES.md','docs/DECISIONS.md','docs/VALIDATION_PLAN.md','scripts/export_temporal_review.py'))
    manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    target=root/'review_downloads/task005/task005_temporal_bundle.zip';target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):z.write(p,p.relative_to(root))
        z.writestr('TASK005_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
        z.writestr('TASK005_README.txt','Task005 review overlay: four analytical Parquet tables, reports and new implementation/tests. Requires retained earlier source/interim/classification inputs and core modules. Raw exports are excluded. Unpack into the existing research checkout, install requirements-temporal.lock.txt after analysis/dev requirements, run python -m kyiv_alerts.temporal_analysis --root . and python -m pytest. No forecast model.\n')
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for path,expected in manifest.items():assert hashlib.sha256(z.read(path)).hexdigest()==expected
    return target,len(files)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'));args=parser.parse_args();print(export(args.root.resolve()))
