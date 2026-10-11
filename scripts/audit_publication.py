"""Read-only Git publication inventory. Never print matched sensitive strings."""
import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

PATTERNS = {
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'github_token': rb'\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,})\b',
    'aws_access_key': rb'\bAKIA[0-9A-Z]{16}\b',
    'ukrainian_phone': rb'\+380\d{9}\b',
}


def audit(root):
    files = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
    files = [f for f in files if f]
    issues, review_context, inventory = [], [], []
    tracked = set(files)
    def scan(name, raw):
        for kind, pattern in PATTERNS.items():
            count = len(re.findall(pattern, raw))
            if count: issues.append({'file': name, 'kind': kind, 'count': count})
    for name in files:
        path = root / name
        if not path.exists():
            issues.append({'file': name, 'kind': 'tracked file missing'}); continue
        raw = path.read_bytes()
        inventory.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        if name.startswith(('data/raw/', 'data/interim/', 'data/external/')) and path.name != '.gitkeep':
            issues.append({'file': name, 'kind': 'original/normalized source tracked'})
        if path.suffix in {'.zip', '.xlsx'}:
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None, name
                for member in archive.infolist():
                    assert member.file_size <= 64 * 1024 * 1024, 'Oversized review archive member'
                    assert not Path(member.filename).is_absolute() and '..' not in Path(member.filename).parts
                    if Path(member.filename).suffix in {'.xml', '.csv', '.json', '.md', '.txt', '.py', '.yaml', '.yml'}:
                        scan(name + ':' + member.filename, archive.read(member))
        elif path.suffix != '.png':
            scan(name, raw)
        if path.suffix == '.json': json.loads(raw)
        if path.suffix == '.csv':
            rows = csv.reader(io.StringIO(raw.decode('utf-8-sig')))
            header = next(rows, [])
            for row in rows:
                assert len(row) == len(header), 'Malformed CSV: ' + name
            if any(re.search(r'(original_text|original_message_text|message_text)', h) for h in header):
                review_context.append(name)
        if path.suffix == '.md':
            for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', raw.decode('utf-8')):
                target = target.strip('<>').split('#')[0]
                if not target or '://' in target or target.startswith('mailto:'): continue
                resolved = (path.parent / target).resolve()
                try: relative = resolved.relative_to(root.resolve()).as_posix()
                except ValueError:
                    issues.append({'file': name, 'kind': 'local link outside repository'}); continue
                if not resolved.exists() or (relative not in tracked and not any(p.startswith(relative + '/') for p in tracked)):
                    issues.append({'file': name, 'kind': 'unpublished local link', 'target': target})
    # GitHub report hrefs must exist in Git, not merely in a private local workspace.
    for name in ['dashboard/src/main.tsx', 'dashboard/src/MythLab.tsx']:
        for target in re.findall(r'["\x27]((?:reports|docs|review_downloads)/[^"\x27]+)["\x27]', (root/name).read_text()):
            if target not in tracked: issues.append({'file': name, 'kind': 'dashboard points to untracked report', 'target': target})
    return {'status': 'PASS' if not issues else 'FAIL', 'tracked_files': len(files),
            'issues': issues, 'authorized_review_context_csv': review_context,
            'scope_note': 'Review archives are historical human-review material and excluded from Pages. Pattern scanning is not a comprehensive privacy certification; compressed Parquet contents are not text-scanned.',
            'inventory': inventory}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path.cwd());parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=audit(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='inventory'},indent=2))
    raise SystemExit(result['status']!='PASS')
