"""Refresh each large CSDI snapshot independently; never publish damaged data.

A transient upstream rejection may use a validated snapshot up to seven days
old. Preserve its original mtime so fallback never masquerades as fresh data.
"""
from __future__ import annotations
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
MAX_AGE = 7 * 86400


def validate(path, kind):
    data = json.loads(path.read_text())
    if kind == 'buildings':
        if not isinstance(data, list) or len(data) < 100000:
            raise ValueError('building snapshot missing or unexpectedly small')
        ids = set()
        for row in data:
            if not isinstance(row, dict) or not row.get('id') or not isinstance(row.get('lat'), (int, float)) or not isinstance(row.get('lon'), (int, float)):
                raise ValueError('invalid building row')
            ids.add(row['id'])
        if len(ids) != len(data):
            raise ValueError('duplicate building IDs')
    else:
        if not isinstance(data, dict) or len(data) < 10000:
            raise ValueError('permit snapshot missing or unexpectedly small')
        for row in data.values():
            if not isinstance(row, dict) or not isinstance(row.get('year'), int) or not 1864 <= row['year'] <= 2043:
                raise ValueError('invalid permit row')
    return len(data)


def refresh(kind, force=False, root=ROOT, runner=subprocess.run, now=None):
    now = time.time() if now is None else now
    path = root / 'data' / f'{kind}.json'
    valid = False
    age = float('inf')
    try:
        validate(path, kind)
        age = now - path.stat().st_mtime
        valid = 0 <= age <= MAX_AGE
    except (OSError, ValueError, TypeError):
        pass
    if valid and not force and datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).date() == datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date():
        print(f'{kind}: reuse verified snapshot from today', flush=True)
        return 'fresh'
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        backup = Path(tmp) / path.name
        if path.exists():
            shutil.copy2(path, backup)
        try:
            result = runner([sys.executable, str(root / 'pipeline' / f'fetch_{kind}.py')], check=False)
            if result.returncode:
                raise RuntimeError(f'fetch_{kind} exited {result.returncode}')
            count = validate(path, kind)
            print(f'{kind}: refreshed {count:,} records', flush=True)
            return 'refreshed'
        except Exception as exc:
            if backup.exists():
                shutil.copy2(backup, path)
            else:
                path.unlink(missing_ok=True)
            if not valid:
                raise RuntimeError(f'{kind}: refresh failed and no valid snapshot within seven days') from exc
            stamp = datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat()
            print(f'::warning::{kind}: refresh failed ({exc}); using validated snapshot from {stamp}', flush=True)
            summary = os.environ.get('GITHUB_STEP_SUMMARY')
            if summary:
                with open(summary, 'a') as f:
                    f.write(f'\n- Upstream refresh failed for {kind}; using validated snapshot from {stamp}.\n')
            return 'fallback'


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('buildings', 'op'):
        raise SystemExit('usage: refresh_csdi.py buildings|op [--force]')
    refresh(sys.argv[1], force='--force' in sys.argv)
