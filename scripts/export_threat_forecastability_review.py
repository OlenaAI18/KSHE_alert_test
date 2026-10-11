"""Task006.1 derived review overlay; excludes original messages/source exports."""
import argparse,hashlib,json,zipfile
from pathlib import Path

def export(root):
    paths=list((root/'reports/threat_forecastability').rglob('*'))+list((root/'data/processed/threat_forecastability_v1').glob('*.parquet'))+list((root/'src/kyiv_alerts/threat_forecastability').glob('*.py'))
    paths += [root/'config/threat_forecastability_v1.yaml',root/'tests/test_threat_forecastability.py',root/'scripts/export_threat_forecastability_review.py',root/'README.md']
    paths += [root/'docs'/name for name in ['DATA_SOURCES.md','METHODOLOGY.md','DECISIONS.md','VALIDATION_PLAN.md']]
    paths=sorted(p for p in paths if p.is_file() and '__pycache__' not in p.parts)
    hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    out=root/'review_downloads/task0061/task0061_threat_forecastability_bundle.zip';out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(root))
        z.writestr('BUNDLE_MANIFEST.json',json.dumps(hashes,indent=2))
        z.writestr('BUNDLE_README.txt','Task006.1 overlay for the existing research repository. Includes derived weekly marker tables, historical predictions, reports/figures, new code/config/tests/docs. No original text or raw exports. Reproduction requires frozen v1.5/v1.6 alert/marker Parquet files, data/interim/telegram_messages.parquet and the existing package/locked environment. Input hashes are recorded in threat_forecastability_summary.json. Run .venv/bin/python -m kyiv_alerts.threat_forecastability --root . --quality-only then without --quality-only. Existing full tests require all previous local research inputs. All targets are reported markers, not attacks or true weapon incidence. No dashboard/live forecast/deployment.\n')
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for name,h in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
    return dict(path=str(out),files=len(hashes),bytes=out.stat().st_size,integrity='PASS')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));print(json.dumps(export(p.parse_args().root.resolve())))
