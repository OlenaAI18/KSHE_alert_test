"""Package only Task006 derived outputs/code/docs; never raw source exports."""
from pathlib import Path
import argparse,hashlib,json,zipfile

def export(root):
    paths=list((root/'reports/forecastability_validation').rglob('*'))+list((root/'data/processed/forecastability').glob('*.parquet'))+list((root/'src/kyiv_alerts/forecastability').glob('*.py'))
    paths += [root/'tests/test_forecastability.py',root/'scripts/export_forecastability_review.py',root/'README.md']
    paths += [root/'docs'/n for n in ['DATA_SOURCES.md','DECISIONS.md','METHODOLOGY.md','VALIDATION_PLAN.md']]
    paths += [root/n for n in ['requirements-analysis.lock.txt','requirements-temporal.lock.txt']]
    paths=sorted(p for p in paths if p.is_file() and '__pycache__' not in p.parts)
    hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    out=root/'review_downloads/task006/task006_forecastability_bundle.zip';out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(root))
        z.writestr('BUNDLE_MANIFEST.json',json.dumps(hashes,indent=2))
        z.writestr('BUNDLE_README.txt','Task006 review overlay. Includes derived weekly targets/predictions, reports, new module/tests and docs. No raw exports. Reproduction requires existing package/environment and frozen data/processed/temporal_analysis/alert_analysis_fact.parquet with hash recorded in forecastability_summary.json. Install existing dev/analysis/temporal locks; run .venv/bin/python -m kyiv_alerts.forecastability --root . and .venv/bin/python -m pytest. All values are historical retrospective aggregates. No live forecast, dashboard or deployment.\n')
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for n,h in hashes.items():assert hashlib.sha256(z.read(n)).hexdigest()==h
    return dict(path=str(out),files=len(hashes),bytes=out.stat().st_size,integrity='PASS')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));print(json.dumps(export(p.parse_args().root.resolve())))
