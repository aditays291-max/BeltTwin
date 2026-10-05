"""Run the unchanged suite in an isolated, checkout-portable evidence fixture.

Git does not preserve filesystem timestamps. Restore the recorded baseline
timestamps ONLY on disposable copies, after verifying their original hashes.
The real baseline files, history and accepted audit snapshots are never edited.
Requires Windows CPython 3.12+; no Isaac runtime or packages for these tests.
"""
import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='test-checkout-',dir=ROOT/'data') as directory:
        fixture=Path(directory)
        (fixture/'scripts').mkdir()
        (fixture/'data').mkdir()
        for source in (ROOT/'scripts').glob('*.py'):
            shutil.copy2(source,fixture/'scripts'/source.name)
        for source in (ROOT/'data').glob('*.json'):
            shutil.copy2(source,fixture/'data'/source.name)
        for name in ('baseline','history','degradation','health'):
            if (ROOT/'data'/name).exists():
                shutil.copytree(ROOT/'data'/name,fixture/'data'/name,ignore=shutil.ignore_patterns('*.lock','*.tmp'))
        expected=json.loads((fixture/'data/phase7_before.json').read_text(encoding='utf-8'))['baseline']
        for name, metadata in expected.items():
            path=fixture/'data/baseline'/name
            if hashlib.sha256(path.read_bytes()).hexdigest()!=metadata['sha256']:
                raise ValueError(f'Baseline content differs from accepted fingerprint: {name}')
            os.utime(path,ns=(metadata['mtime_ns'],metadata['mtime_ns']))
        return subprocess.call([sys.executable,'-B','-S','-m','unittest','discover',
                                '-s',str(fixture/'scripts'),'-p','test_*.py','-v'],cwd=fixture)


if __name__=='__main__':
    raise SystemExit(main())
