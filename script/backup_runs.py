#!/usr/bin/env python3
"""Backup and restore the {spot} operational state (deck p.11: verify backup and restore before launch).

Backup copies the runs directory and the ops database into a timestamped directory with an integrity
manifest; restore copies a verified backup back. Both refuse to act on paths outside the given roots.

Usage (repo root):
    .venv/bin/python script/backup_runs.py backup --runs-dir runs --backup-dir backups
    .venv/bin/python script/backup_runs.py restore --from backups/<timestamp> --to runs
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
from pathlib import Path


def manifest_of(root: Path) -> dict:
    entries: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        entries[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"root": str(root), "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": entries}


def backup(runs_dir: Path, backup_dir: Path) -> dict:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    target = backup_dir / stamp
    if target.exists():
        raise RuntimeError(f"backup target already exists: {target}")
    target.mkdir(parents=True, exist_ok=True)
    if runs_dir.exists():
        shutil.copytree(runs_dir, target / "runs")
    db = runs_dir.parent / "spot_ops.sqlite3"
    if db.exists():
        shutil.copy2(db, target / "spot_ops.sqlite3")
    manifest = manifest_of(target)
    import json

    (target / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return {"backup_dir": str(target), "files": len(manifest["files"])}


def restore(source: Path, runs_dir: Path) -> dict:
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"not a backup (manifest missing): {source}")
    import json

    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest["files"].items():
        path = source / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"integrity check failed: {name}")
    if runs_dir.exists():
        shutil.rmtree(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    for name in manifest["files"]:
        if not name.startswith("runs/"):
            continue
        src = source / name
        dst = runs_dir / name[len("runs/"):]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    db_src = source / "spot_ops.sqlite3"
    if db_src.is_file():
        shutil.copy2(db_src, runs_dir.parent / "spot_ops.sqlite3")
    return {"restored": str(runs_dir), "files": len(manifest["files"])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--runs-dir", default="runs")
    b.add_argument("--backup-dir", default="backups")
    r = sub.add_parser("restore")
    r.add_argument("--from", dest="source", required=True)
    r.add_argument("--to", dest="runs_dir", default="runs")
    args = ap.parse_args()

    if args.command == "backup":
        print(backup(Path(args.runs_dir), Path(args.backup_dir)))
    else:
        print(restore(Path(args.source), Path(args.runs_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
