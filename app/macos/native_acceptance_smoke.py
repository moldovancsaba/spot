#!/usr/bin/env python3
"""Verify the installed native runtime against a real run without inventing run state."""
from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from openpyxl import Workbook

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = 'http://127.0.0.1:8765'


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, *, payload=None, body=None):
        if payload is not None:
            body = json.dumps(payload).encode()
        request = urllib.request.Request(BASE_URL + path, data=body, headers={'Content-Type': 'application/json' if payload is not None else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        try:
            with self.opener.open(request, timeout=20) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def json(self, path, *, payload=None, body=None, expected=200):
        status, raw = self.request(path, payload=payload, body=body)
        if status != expected:
            raise RuntimeError(f'{path}: expected HTTP {expected}, got {status}')
        try:
            return json.loads(raw)
        except ValueError:
            raise RuntimeError(f'{path}: invalid JSON response') from None

    def login(self, role, access_code):
        self.json('/auth/login', payload={'role': role, 'actor_name': 'native-acceptance-test', 'access_code': access_code})


def native_config():
    path = Path.home() / 'Library/Application Support/spot/native-runtime.env'
    config = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip('"')
    return config


def check(*, run_id, wait_seconds, check_intake):
    client = Client()
    health = client.json('/api/health')
    if health.get('service') != '{spot} Classification Backend' or not health.get('ok'):
        raise RuntimeError('Unexpected or unhealthy service; launch /Applications/spot.app first')
    config = native_config()
    access_code = os.getenv('SPOT_LOCAL_ACCESS_CODE') or config.get('SPOT_LOCAL_ACCESS_CODE', '')
    auth = client.json('/auth/config')
    if not auth.get('auth_enabled'):
        raise RuntimeError('Native acceptance requires authentication to be enabled')
    status, _ = client.request('/runs')
    if status != 401:
        raise RuntimeError('Anonymous run inventory access was not rejected')
    client.login('operator', access_code)
    if not run_id:
        runs = client.json('/runs')
        if not runs:
            raise RuntimeError('No actual runs exist; intake and start a workbook in the native app first')
        run_id = max(runs, key=lambda run: run.get('created_at') or 0)['run_id']
    status, _ = client.request(f'/runs/{run_id}/review-rows/0', payload={'review_state': 'reviewed', 'review_decision': 'confirm'})
    if status != 403:
        raise RuntimeError('Operator role unexpectedly permits review mutation')
    client.login('admin', access_code)
    checks = {'service_identity': True, 'authentication_enabled': True, 'anonymous_access_rejected': True, 'operator_review_denied': True}
    if check_intake:
        workbook = Workbook()
        workbook.active.append(['Wrong header'])
        workbook.active.append(['Synthetic invalid-schema control'])
        stream = io.BytesIO()
        workbook.save(stream)
        workbook.close()
        upload = client.json('/uploads/intake?filename=native-acceptance-invalid-schema.xlsx', body=stream.getvalue())
        if upload.get('status') != 'rejected':
            raise RuntimeError('Invalid-schema workbook was not rejected')
        checks['invalid_schema_rejected'] = True
    deadline = time.monotonic() + wait_seconds
    while True:
        detail = client.json(f'/runs/{run_id}/detail')
        state = detail.get('state')
        if state == 'COMPLETED':
            break
        if state in {'FAILED', 'CANCELLED', 'BLOCKED'}:
            raise RuntimeError(f'Run ended in {state}')
        if time.monotonic() >= deadline:
            return {'run_id': run_id, 'status': 'pending', 'state': state, 'checks': checks, 'reviewer_decision': 'pending designated reviewer'}
        time.sleep(5)
    queue = client.json(f'/runs/{run_id}/review-rows')
    rows = queue.get('rows', [])
    if not rows:
        raise RuntimeError('Expected full-review acceptance run to expose review rows')
    index = int(rows[0]['row_index'])
    client.json(f'/runs/{run_id}/review-rows/{index}')
    checks['review_queue_and_inspector'] = True
    artifacts = client.json(f'/runs/{run_id}/artifacts')
    names = {artifact['name'] for artifact in artifacts.get('artifacts', [])}
    required = {'output.xlsx', 'policy.json', 'integrity_report.json', 'artifact_manifest.json', 'logs.txt'}
    if not required.issubset(names):
        raise RuntimeError('Required audit artifacts are missing')
    checks['required_artifacts'] = True
    status, output = client.request(f'/runs/{run_id}/artifacts/download/output.xlsx')
    if status != 200 or not output.startswith(b'PK'):
        raise RuntimeError('Output workbook download failed')
    checks['output_download'] = True
    runs_dir = Path(config.get('SPOT_NATIVE_RUNS_DIR') or REPO_ROOT / 'runs')
    run_path = runs_dir / run_id
    if hashlib.sha256(output).hexdigest() != hashlib.sha256((run_path/'output.xlsx').read_bytes()).hexdigest():
        raise RuntimeError('Downloaded workbook differs from stored output')
    checks['output_download_hash'] = True
    manifest = json.loads((run_path/'artifact_manifest.json').read_text())
    for name in ('output.xlsx', 'policy.json', 'integrity_report.json', 'logs.txt'):
        recorded = manifest.get('artifacts', {}).get(name, {})
        actual = hashlib.sha256((run_path/name).read_bytes()).hexdigest()
        if recorded.get('sha256') != actual:
            raise RuntimeError(f'Artifact hash mismatch: {name}')
    checks['governed_artifact_hashes'] = True
    return {'run_id': run_id, 'status': 'passed', 'state': state, 'checks': checks, 'review_rows': len(rows), 'artifacts': sorted(names), 'reviewer_decision': 'pending designated reviewer', 'scope': 'Engineering acceptance checks; no client review decisions were saved.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', default='')
    parser.add_argument('--wait-seconds', type=int, default=1800)
    parser.add_argument('--check-intake', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = check(run_id=args.run_id, wait_seconds=args.wait_seconds, check_intake=args.check_intake)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
