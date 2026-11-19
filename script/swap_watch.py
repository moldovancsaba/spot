#!/usr/bin/env python3
"""Swap watchdog: warn (and optionally act) when unified memory pressure enters the danger zone.

The 3-worker incident drove ~20 GB into swap and degraded throughput 15x with no signal until a human
looked. This watcher logs swap usage every run; above --warn-gb it appends a WARNING line, and above
--crit-gb it also writes the process memory leaders so post-mortems have data. It never kills anything.

Usage: .venv/bin/python script/swap_watch.py [--warn-gb 12] [--crit-gb 20] [--log runs/swap_watch.log]
"""
from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path


def swap_used_gb() -> float:
    raw = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    # e.g. "total = 25600.00M  used = 25196.88M  free = 403.12M  (encrypted)"
    import re
    match = re.search(r"used = ([0-9.]+)M", raw)
    return float(match.group(1)) / 1024.0 if match else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--warn-gb", type=float, default=12.0)
    ap.add_argument("--crit-gb", type=float, default=20.0)
    ap.add_argument("--log", default="runs/swap_watch.log")
    args = ap.parse_args()

    used = swap_used_gb()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"{stamp} swap_used={used:.2f}GB"
    level = "OK" if used < args.warn_gb else ("WARNING" if used < args.crit_gb else "CRITICAL")
    if level == "CRITICAL":
        top = subprocess.run(["ps", "-Ao", "rss,command"], capture_output=True, text=True).stdout.splitlines()
        leaders = " | ".join(line.split(" ", 1)[1][:70] for line in sorted(top, reverse=True)[:6])
        line += f" {level} mem_leaders: {leaders}"
    else:
        line += f" {level}"
    path = Path(args.log)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
