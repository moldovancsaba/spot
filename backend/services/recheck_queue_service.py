"""Read the durable recheck plan without confusing machine work with human work."""
from __future__ import annotations
import json
from pathlib import Path


def pending_recheck_rows(runs_dir: Path, run_id: str) -> set[int]:
    path = runs_dir / run_id / 'automatic_recheck.json'
    try:
        plan = json.loads(path.read_text())
    except FileNotFoundError:
        return set()
    except (OSError, ValueError) as exc:
        # Do not silently expose unfinished machine work as a human queue.
        raise RuntimeError('Automatic recheck state is unavailable; refresh when the run is ready') from exc
    planned, done = plan.get('row_indices'), plan.get('done_rows', [])
    if not isinstance(planned,list) or not isinstance(done,list) or any(type(i) is not int or i < 1 for i in planned + done):
        raise RuntimeError('Automatic recheck state is invalid')
    # Completion is acknowledged only after the worker committed its result and saved this marker.
    return set(planned) - set(done)
