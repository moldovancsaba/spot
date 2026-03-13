from pathlib import Path
import json
import os
import signal
import subprocess
import time
import shutil

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from src.defaults import (
    DEFAULT_ENSEMBLE_MODELS,
    DEFAULT_INPUT_PATH,
    DEFAULT_LANGUAGE,
    DEFAULT_LIMIT,
    DEFAULT_MAX_WORKERS,
    DEFAULT_PROGRESS_EVERY,
    DEFAULT_REVIEW_MODE,
    DEFAULT_SINGLE_MODEL,
    DEFAULT_SSOT_PATH,
)

app = FastAPI(title="{spot} Classification Backend", version="0.3.1")
RUNS_DIR = Path(os.getenv("RUNS_DIR", str(Path(__file__).resolve().parent.parent / "runs")))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_BIN = PROJECT_ROOT / ".venv" / "bin" / "python"
DEFAULT_AGENT_EVAL_RUN_ID = os.getenv("DEFAULT_AGENT_EVAL_RUN_ID", "eval-2000")
DEFAULT_CLASSIFY_RUN_ID = os.getenv("DEFAULT_CLASSIFY_RUN_ID", "sample-final-v020")


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    progress_path = RUNS_DIR / run_id / "progress.json"
    if not progress_path.exists():
        raise HTTPException(status_code=404, detail="run not found")
    return json.loads(progress_path.read_text(encoding="utf-8"))


@app.get("/runs")
def list_runs():
    runs = []
    if not RUNS_DIR.exists():
        return runs
    for d in sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()], reverse=True):
        progress_path = d / "progress.json"
        if not progress_path.exists():
            continue
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        runs.append(
            {
                "run_id": progress.get("run_id", d.name),
                "status": progress.get("state"),
                "started_at": progress.get("started_at"),
                "completed_at": progress.get("completed_at"),
                "total_rows": progress.get("total_rows"),
                "progress_percentage": progress.get("progress_percentage"),
            }
        )
    return runs


def _safe_read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _control_path(run_id: str) -> Path:
    return RUNS_DIR / run_id / "control.json"


def _write_control(run_id: str, payload: dict) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _control_path(run_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_control(run_id: str) -> dict | None:
    return _safe_read_json(_control_path(run_id))


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _discover_classify_pid(run_id: str) -> int | None:
    try:
        out = subprocess.check_output(["ps", "aux"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    needle = f"--run-id {run_id}"
    for line in out.splitlines():
        if "src.cli classify" not in line or needle not in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            return int(parts[1])
        except ValueError:
            continue
    return None


@app.post("/agent-eval/start/{evaluation_run_id}")
def start_agent_eval(evaluation_run_id: str, payload: dict | None = Body(default=None)):
    subprocess.run(["pkill", "-f", f"evaluation-run-id {evaluation_run_id}"], check=False)
    single = RUNS_DIR / f"{evaluation_run_id}-single"
    ensemble = RUNS_DIR / f"{evaluation_run_id}-ensemble"
    eval_dir = RUNS_DIR / evaluation_run_id
    for p in [single, ensemble, eval_dir]:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    log_path = RUNS_DIR / f"{evaluation_run_id}-ui.log"
    payload = payload or {}
    input_path = str(payload.get("input", DEFAULT_INPUT_PATH))
    ssot_path = str(payload.get("ssot", DEFAULT_SSOT_PATH))
    language = str(payload.get("language", DEFAULT_LANGUAGE))
    review_mode = str(payload.get("review_mode", DEFAULT_REVIEW_MODE))
    single_model = str(payload.get("single_model", DEFAULT_SINGLE_MODEL))
    ensemble_models = str(payload.get("ensemble_models", DEFAULT_ENSEMBLE_MODELS))
    max_workers = str(payload.get("max_workers", DEFAULT_MAX_WORKERS))
    limit = str(payload.get("limit", DEFAULT_LIMIT))
    progress_every = str(payload.get("progress_every", DEFAULT_PROGRESS_EVERY))

    cmd = [
        str(PYTHON_BIN),
        "-m",
        "src.cli",
        "evaluate",
        "--input",
        input_path,
        "--ssot",
        ssot_path,
        "--runs-dir",
        "runs",
        "--evaluation-run-id",
        evaluation_run_id,
        "--language",
        language,
        "--review-mode",
        review_mode,
        "--single-model",
        single_model,
        "--ensemble-models",
        ensemble_models,
        "--max-workers",
        max_workers,
        "--limit",
        limit,
        "--progress-every",
        progress_every,
    ]
    log = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    return {"status": "started", "evaluation_run_id": evaluation_run_id, "pid": proc.pid}


@app.post("/classify/start/{run_id}")
def classify_start(run_id: str, payload: dict | None = Body(default=None)):
    control = _read_control(run_id) or {}
    existing_pid = control.get("pid")
    if _pid_alive(existing_pid):
        os.kill(existing_pid, signal.SIGTERM)
        time.sleep(0.2)

    run_dir = RUNS_DIR / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)

    payload = payload or {}
    input_path = str(payload.get("input", DEFAULT_INPUT_PATH))
    output_path = str(payload.get("output", str(PROJECT_ROOT / "samples" / f"{run_id}_output.xlsx")))
    ssot_path = str(payload.get("ssot", DEFAULT_SSOT_PATH))
    language = str(payload.get("language", DEFAULT_LANGUAGE))
    review_mode = str(payload.get("review_mode", DEFAULT_REVIEW_MODE))
    max_workers = str(payload.get("max_workers", DEFAULT_MAX_WORKERS))
    progress_every = str(payload.get("progress_every", DEFAULT_PROGRESS_EVERY))
    limit = payload.get("limit", None)

    cmd = [
        str(PYTHON_BIN),
        "-m",
        "src.cli",
        "classify",
        "--input",
        input_path,
        "--output",
        output_path,
        "--run-id",
        run_id,
        "--language",
        language,
        "--review-mode",
        review_mode,
        "--ssot",
        ssot_path,
        "--runs-dir",
        "runs",
        "--max-workers",
        max_workers,
        "--progress-every",
        progress_every,
    ]
    if limit is not None:
        cmd.extend(["--limit", str(limit)])

    log_path = RUNS_DIR / f"{run_id}-classify-ui.log"
    log = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    _write_control(
        run_id,
        {
            "run_id": run_id,
            "pid": proc.pid,
            "paused": False,
            "started_at": int(time.time()),
            "input": input_path,
            "output": output_path,
        },
    )
    return {"status": "started", "run_id": run_id, "pid": proc.pid, "output": output_path}


@app.post("/classify/pause/{run_id}")
def classify_pause(run_id: str):
    control = _read_control(run_id)
    pid = control.get("pid") if control else _discover_classify_pid(run_id)
    if not control:
        control = {"run_id": run_id, "pid": pid, "paused": False}
    if pid is None:
        raise HTTPException(status_code=404, detail="run process not found")
    if not _pid_alive(pid):
        raise HTTPException(status_code=409, detail="process not running")
    os.kill(pid, signal.SIGSTOP)
    control["paused"] = True
    control["paused_at"] = int(time.time())
    _write_control(run_id, control)
    return {"status": "paused", "run_id": run_id, "pid": pid}


@app.post("/classify/resume/{run_id}")
def classify_resume(run_id: str):
    control = _read_control(run_id)
    pid = control.get("pid") if control else _discover_classify_pid(run_id)
    if not control:
        control = {"run_id": run_id, "pid": pid, "paused": True}
    if pid is None:
        raise HTTPException(status_code=404, detail="run process not found")
    if not _pid_alive(pid):
        raise HTTPException(status_code=409, detail="process not running")
    os.kill(pid, signal.SIGCONT)
    control["paused"] = False
    control["resumed_at"] = int(time.time())
    _write_control(run_id, control)
    return {"status": "resumed", "run_id": run_id, "pid": pid}


@app.post("/classify/stop/{run_id}")
def classify_stop(run_id: str):
    control = _read_control(run_id)
    pid = control.get("pid") if control else _discover_classify_pid(run_id)
    if not control:
        control = {"run_id": run_id, "pid": pid, "paused": False}
    if pid is None:
        raise HTTPException(status_code=404, detail="run process not found")
    if _pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
    control["paused"] = False
    control["stopped_at"] = int(time.time())
    _write_control(run_id, control)
    return {"status": "stopped", "run_id": run_id, "pid": pid}


@app.get("/classify/status/{run_id}")
def classify_status(run_id: str):
    progress = _safe_read_json(RUNS_DIR / run_id / "progress.json")
    control = _read_control(run_id)
    pid = control.get("pid") if control else None
    if pid is None:
        pid = _discover_classify_pid(run_id)
    running = _pid_alive(pid)
    paused = bool(control.get("paused")) if control else False
    output_path = control.get("output") if control else None
    output_exists = bool(output_path and Path(output_path).exists())
    effective_state = "NOT_STARTED"
    if progress:
        effective_state = str(progress.get("state") or "UNKNOWN")
    if paused and running:
        effective_state = "PAUSED"
    elif running and effective_state in {"NOT_STARTED", "UNKNOWN"}:
        effective_state = "STARTING"
    return {
        "run_id": run_id,
        "timestamp": int(time.time()),
        "effective_state": effective_state,
        "running": running,
        "paused": paused,
        "pid": pid,
        "progress": progress,
        "control": control,
        "output_exists": output_exists,
    }


@app.get("/agent-eval/status/{evaluation_run_id}")
def agent_eval_status(evaluation_run_id: str):
    single = _safe_read_json(RUNS_DIR / f"{evaluation_run_id}-single" / "progress.json")
    ensemble = _safe_read_json(RUNS_DIR / f"{evaluation_run_id}-ensemble" / "progress.json")
    report = _safe_read_json(RUNS_DIR / evaluation_run_id / "evaluation_report.json")

    overall = {"state": "NOT_STARTED", "progress_percentage": 0.0}
    if single and single.get("state") == "COMPLETED" and ensemble and ensemble.get("state") == "COMPLETED":
        overall = {"state": "COMPLETED", "progress_percentage": 100.0}
    elif single and single.get("state") == "PROCESSING":
        done = single.get("processed_rows") or 0
        total = single.get("total_rows") or 1
        overall = {"state": "SINGLE_PROCESSING", "progress_percentage": round(50.0 * (done / total), 2)}
    elif single and single.get("state") == "COMPLETED" and ensemble:
        if ensemble.get("state") == "PROCESSING":
            done = ensemble.get("processed_rows") or 0
            total = ensemble.get("total_rows") or 1
            overall = {"state": "ENSEMBLE_PROCESSING", "progress_percentage": round(50.0 + 50.0 * (done / total), 2)}
        elif ensemble.get("state") == "VALIDATING":
            overall = {"state": "ENSEMBLE_VALIDATING", "progress_percentage": 55.0}
    elif single and single.get("state") == "VALIDATING":
        overall = {"state": "SINGLE_VALIDATING", "progress_percentage": 5.0}

    return {
        "evaluation_run_id": evaluation_run_id,
        "timestamp": int(time.time()),
        "overall": overall,
        "single": single,
        "ensemble": ensemble,
        "report": report,
    }


@app.get("/agent-eval", response_class=HTMLResponse)
def agent_eval_page():
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <title>Agent Eval</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; }
    .row { margin-bottom: 12px; }
    .bar { width: 100%; height: 20px; background: #eee; border-radius: 6px; overflow: hidden; }
    .bar > div { height: 100%; background: #2b6cb0; width: 0%; transition: width 0.3s; }
    pre { background: #f6f8fa; padding: 12px; border-radius: 6px; overflow: auto; }
    button { padding: 8px 12px; }
  </style>
</head>
<body>
  <h2>Agent Eval</h2>
  <div class='row'>
    <label>Run ID: <input id='runId' value='__DEFAULT_RUN_ID__' /></label>
    <button onclick='startRun()'>Start / Restart</button>
  </div>
  <div class='row'>Overall: <span id='overallState'>NOT_STARTED</span> (<span id='overallPct'>0</span>%)</div>
  <div class='bar'><div id='bar'></div></div>
  <div class='row'>Single: <span id='singleState'>-</span>, processed: <span id='singleProc'>-</span>/<span id='singleTotal'>-</span></div>
  <div class='row'>Ensemble: <span id='ensembleState'>-</span>, processed: <span id='ensembleProc'>-</span>/<span id='ensembleTotal'>-</span></div>
  <h3>Evaluation Report</h3>
  <pre id='report'>No report yet.</pre>
  <script>
    async function startRun() {
      const runId = document.getElementById('runId').value.trim();
      await fetch('/agent-eval/start/' + encodeURIComponent(runId), { method: 'POST' });
      poll();
    }
    async function poll() {
      const runId = document.getElementById('runId').value.trim();
      const r = await fetch('/agent-eval/status/' + encodeURIComponent(runId));
      const d = await r.json();
      const o = d.overall || {};
      document.getElementById('overallState').textContent = o.state || '-';
      document.getElementById('overallPct').textContent = o.progress_percentage ?? 0;
      document.getElementById('bar').style.width = (o.progress_percentage || 0) + '%';
      const s = d.single || {};
      document.getElementById('singleState').textContent = s.state || '-';
      document.getElementById('singleProc').textContent = s.processed_rows ?? '-';
      document.getElementById('singleTotal').textContent = s.total_rows ?? '-';
      const e = d.ensemble || {};
      document.getElementById('ensembleState').textContent = e.state || '-';
      document.getElementById('ensembleProc').textContent = e.processed_rows ?? '-';
      document.getElementById('ensembleTotal').textContent = e.total_rows ?? '-';
      document.getElementById('report').textContent = d.report ? JSON.stringify(d.report, null, 2) : 'No report yet.';
    }
    setInterval(poll, 3000);
    poll();
  </script>
</body>
</html>"""
    return page.replace("__DEFAULT_RUN_ID__", DEFAULT_AGENT_EVAL_RUN_ID)


@app.get("/classify-monitor", response_class=HTMLResponse)
def classify_monitor_page():
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <title>Classify Monitor</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; }
    .row { margin-bottom: 12px; }
    .bar { width: 100%; height: 20px; background: #eee; border-radius: 6px; overflow: hidden; }
    .bar > div { height: 100%; background: #2b6cb0; width: 0%; transition: width 0.3s; }
    pre { background: #f6f8fa; padding: 12px; border-radius: 6px; overflow: auto; }
    button { padding: 8px 12px; margin-right: 8px; }
    input { padding: 6px; min-width: 260px; }
  </style>
</head>
<body>
  <h2>Classify Monitor</h2>
  <div class='row'>
    <label>Run ID: <input id='runId' value='__DEFAULT_RUN_ID__' /></label>
  </div>
  <div class='row'>
    <button onclick='startRun()'>Start / Restart</button>
    <button onclick='pauseRun()'>Pause</button>
    <button onclick='resumeRun()'>Resume</button>
    <button onclick='stopRun()'>Stop</button>
  </div>
  <div class='row'>State: <span id='state'>NOT_STARTED</span></div>
  <div class='row'>PID: <span id='pid'>-</span> | Running: <span id='running'>false</span> | Paused: <span id='paused'>false</span></div>
  <div class='row'>Rows: <span id='proc'>0</span>/<span id='total'>0</span> | Progress: <span id='pct'>0</span>%</div>
  <div class='bar'><div id='bar'></div></div>
  <div class='row'><a id='outputLink' href='#' target='_blank'>Output file</a></div>
  <h3>Progress JSON</h3>
  <pre id='progressRaw'>No progress yet.</pre>
  <script>
    function runId() { return document.getElementById('runId').value.trim(); }
    async function startRun() {
      await fetch('/classify/start/' + encodeURIComponent(runId()), { method: 'POST' });
      poll();
    }
    async function pauseRun() {
      await fetch('/classify/pause/' + encodeURIComponent(runId()), { method: 'POST' });
      poll();
    }
    async function resumeRun() {
      await fetch('/classify/resume/' + encodeURIComponent(runId()), { method: 'POST' });
      poll();
    }
    async function stopRun() {
      await fetch('/classify/stop/' + encodeURIComponent(runId()), { method: 'POST' });
      poll();
    }
    async function poll() {
      const res = await fetch('/classify/status/' + encodeURIComponent(runId()));
      if (!res.ok) return;
      const d = await res.json();
      const p = d.progress || {};
      const pct = p.progress_percentage ?? 0;
      document.getElementById('state').textContent = d.effective_state || '-';
      document.getElementById('pid').textContent = d.pid ?? '-';
      document.getElementById('running').textContent = String(d.running);
      document.getElementById('paused').textContent = String(d.paused);
      document.getElementById('proc').textContent = p.processed_rows ?? 0;
      document.getElementById('total').textContent = p.total_rows ?? 0;
      document.getElementById('pct').textContent = pct;
      document.getElementById('bar').style.width = pct + '%';
      const link = document.getElementById('outputLink');
      if (d.control && d.control.output) {
        link.textContent = d.control.output + (d.output_exists ? ' (ready)' : ' (not ready)');
      }
      document.getElementById('progressRaw').textContent = JSON.stringify(d, null, 2);
    }
    setInterval(poll, 2000);
    poll();
  </script>
</body>
</html>"""
    return page.replace("__DEFAULT_RUN_ID__", DEFAULT_CLASSIFY_RUN_ID)
