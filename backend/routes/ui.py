from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.services.request_auth import require_permission

router = APIRouter()
DEFAULT_AGENT_EVAL_RUN_ID = os.getenv("DEFAULT_AGENT_EVAL_RUN_ID", "eval-2000")
DEFAULT_CLASSIFY_RUN_ID = os.getenv("DEFAULT_CLASSIFY_RUN_ID", "spot-sample-v031")



def _operator_page_chrome_css(max_width: int = 1180) -> str:
    return f"""
    .shell {{ max-width: {max_width}px; margin: 0 auto; padding: 28px 20px 40px; }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 18px;
      padding: 14px 18px;
      border: 1px solid var(--line);
      background: rgba(255,250,241,0.82);
      border-radius: 18px;
    }}
    .brand-mark {{
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--accent);
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .brand-copy {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      max-width: 42rem;
    }}
    .quick-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .nav-chip {{
      display: inline-flex;
      align-items: center;
      text-decoration: none;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--text);
      background: rgba(255,255,255,0.72);
      padding: 9px 14px;
      font-size: 13px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-weight: 700;
    }}
    @media (max-width: 920px) {{
      .topbar {{ display: grid; }}
    }}
    """


def _operator_page_topbar(*, title: str, subtitle: str, links: list[tuple[str, str]]) -> str:
    nav = "".join([f'<a class="nav-chip" href="{href}">{label}</a>' for label, href in links])
    return f"""
    <section class="topbar">
      <div>
        <div class="brand-mark">{title}</div>
        <div class="brand-copy">{subtitle}</div>
      </div>
      <div class="quick-nav">{nav}</div>
    </section>
    """

@router.get("/agent-eval", response_class=HTMLResponse)
def agent_eval_page(request: Request):
    require_permission(request, "view")
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <title>{spot} Legacy Evaluation Monitor</title>
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
  <h2>{spot} Legacy Evaluation Monitor</h2>
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


@router.get("/classify-monitor", response_class=HTMLResponse)
def classify_monitor_page(request: Request):
    require_permission(request, "view")
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <title>{spot} Legacy Classification Monitor</title>
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
  <h2>{spot} Legacy Classification Monitor</h2>
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


@router.get("/", response_class=HTMLResponse)
@router.get("/app", response_class=HTMLResponse)
def app_shell_page(request: Request):
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>{spot} Operator Dashboard</title>
  <style>
    :root {
      --bg: #f3efe4;
      --panel: #fffaf1;
      --panel-2: #f9f3e7;
      --line: #d9cfbf;
      --text: #1f1d19;
      --muted: #6c655c;
      --accent: #0f766e;
      --accent-2: #b45309;
      --danger: #b91c1c;
      --ok: #166534;
      --shadow: 0 12px 30px rgba(51, 41, 24, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(180,83,9,0.10), transparent 28%),
        radial-gradient(circle at top right, rgba(15,118,110,0.10), transparent 26%),
        linear-gradient(180deg, #f7f2e9 0%, var(--bg) 100%);
      color: var(--text);
      font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
    }
    .shell {
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px 20px 40px;
    }
    .topbar {
      display: grid;
      gap: 18px;
      margin-bottom: 20px;
      padding: 22px 24px;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at top right, rgba(15,118,110,0.10), transparent 24%),
        linear-gradient(135deg, rgba(255,255,255,0.94), rgba(250,244,234,0.94));
      border-radius: 28px;
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
    }
    .topbar::after {
      content: "";
      position: absolute;
      width: 240px;
      height: 240px;
      border-radius: 50%;
      right: -80px;
      top: -120px;
      background: radial-gradient(circle, rgba(180,83,9,0.10), transparent 68%);
      pointer-events: none;
    }
    .brand-row {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
    }
    .brand-mark {
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      color: var(--accent);
      font-weight: 800;
      margin-bottom: 8px;
    }
    .brand-title {
      font-size: 44px;
      line-height: 0.96;
      max-width: 14ch;
      margin-bottom: 12px;
    }
    .brand-copy {
      color: var(--muted);
      font-size: 17px;
      line-height: 1.52;
      max-width: 48rem;
    }
    .session-rail {
      min-width: 300px;
      display: grid;
      gap: 12px;
      padding: 16px;
      border-radius: 22px;
      border: 1px solid rgba(15,118,110,0.16);
      background: rgba(255,250,241,0.88);
      position: relative;
      z-index: 1;
    }
    .session-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .session-field {
      display: grid;
      gap: 6px;
    }
    .session-field label {
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    .hero {
      display: grid;
      gap: 16px;
      margin-bottom: 28px;
    }
    .hero-card, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }
    .hero-card {
      padding: 26px;
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 11px;
      color: var(--accent);
      margin-bottom: 10px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-weight: 800;
    }
    h1, h2, h3 { margin: 0; }
    .mission-grid {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 22px;
      align-items: start;
    }
    .metrics-card {
      background: linear-gradient(180deg, rgba(255,255,255,0.76), rgba(249,243,231,0.86));
      border: 1px solid rgba(15,118,110,0.10);
      border-radius: 22px;
      padding: 24px;
      display: grid;
      gap: 20px;
    }
    .control-card {
      background: linear-gradient(180deg, rgba(249,243,231,0.86), rgba(255,255,255,0.82));
      border: 1px solid rgba(180,83,9,0.12);
      border-radius: 22px;
      padding: 24px;
      display: grid;
      gap: 18px;
    }
    .status-actions,
    .session-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
    }
    .status-tile {
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      min-width: 0;
      overflow: hidden;
    }
    .status-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 10px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }
    .status-value {
      font-size: clamp(22px, 2.2vw, 28px);
      font-weight: 700;
      line-height: 1.02;
      letter-spacing: -0.02em;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .status-sub {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .control-note {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.45;
    }
    .inline-kpis {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .mini-kpi {
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.78);
      padding: 8px 12px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 12px;
      color: var(--muted);
    }
    .layout {
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 20px;
      align-items: start;
    }
    .stack {
      display: grid;
      gap: 20px;
    }
    .panel {
      padding: 24px 20px 20px;
      min-width: 0;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 14px;
      margin-bottom: 16px;
    }
    .panel-title {
      font-size: 28px;
      line-height: 1.08;
      padding-top: 2px;
    }
    .panel-note {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.45;
      max-width: 34rem;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    button, .ghost-link {
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 14px;
      cursor: pointer;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }
    button.primary {
      background: var(--accent);
      color: white;
    }
    button.secondary {
      background: #e7ddd0;
      color: var(--text);
    }
    button.warn {
      background: var(--accent-2);
      color: white;
    }
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .ghost-link {
      display: inline-block;
      text-decoration: none;
      background: transparent;
      color: var(--accent);
      border: 1px solid var(--line);
    }
    .workflow-badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      border: 1px solid rgba(180,83,9,0.16);
      background: rgba(180,83,9,0.08);
      color: var(--accent-2);
      padding: 8px 12px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-weight: 700;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      line-height: 1.3;
    }
    .upload-form {
      display: grid;
      gap: 12px;
    }
    .file-drop {
      display: grid;
      gap: 10px;
      padding: 18px;
      border: 1px dashed rgba(15,118,110,0.28);
      background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(244,250,248,0.8));
      border-radius: 18px;
    }
    .file-drop-title {
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 15px;
      font-weight: 700;
      color: var(--text);
    }
    .file-drop-copy {
      font-size: 13px;
      color: var(--muted);
      line-height: 1.45;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }
    .upload-meta {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    input[type="text"], select, input[type="file"] {
      width: 100%;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: white;
      padding: 11px 12px;
      font-size: 14px;
      color: var(--text);
    }
    .section-grid {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 16px;
      align-items: start;
    }
    .message {
      border-radius: 16px;
      padding: 12px 14px;
      font-size: 14px;
      line-height: 1.5;
      border: 1px solid var(--line);
      background: #f8f4eb;
      color: var(--text);
      white-space: pre-wrap;
    }
    .message.error {
      border-color: rgba(185, 28, 28, 0.24);
      background: rgba(185, 28, 28, 0.08);
      color: var(--danger);
    }
    .message.ok {
      border-color: rgba(22, 101, 52, 0.24);
      background: rgba(22, 101, 52, 0.08);
      color: var(--ok);
    }
    .list {
      display: grid;
      gap: 10px;
    }
    .card {
      border: 1px solid var(--line);
      background: white;
      border-radius: 20px;
      padding: 16px;
      display: grid;
      gap: 10px;
      min-width: 0;
    }
    .card.selected {
      border-color: rgba(15,118,110,0.4);
      box-shadow: inset 0 0 0 1px rgba(15,118,110,0.18);
      background: linear-gradient(180deg, #ffffff 0%, #f5fbf9 100%);
    }
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }
    .card-title {
      font-size: 16px;
      font-weight: 700;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .meta-box {
      border: 1px solid rgba(217,207,191,0.8);
      background: #fbf7f0;
      border-radius: 14px;
      padding: 12px;
      min-width: 0;
    }
    .meta-box-label {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }
    .meta-box-value {
      font-size: 18px;
      font-weight: 700;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .phase-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .phase-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--panel-2);
      padding: 6px 10px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 12px;
      color: var(--muted);
    }
    .pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 12px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-weight: 700;
      border: 1px solid var(--line);
      background: var(--panel-2);
    }
    .pill.ok { color: var(--ok); }
    .pill.warn { color: var(--accent-2); }
    .pill.danger { color: var(--danger); }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .detail-box {
      border: 1px solid var(--line);
      background: white;
      border-radius: 14px;
      padding: 12px;
      min-width: 0;
    }
    .detail-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }
    pre {
      margin: 0;
      padding: 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: #fbf7f0;
      overflow: auto;
      font-size: 12px;
      line-height: 1.45;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 12px;
    }
    .detail-summary {
      display: grid;
      gap: 12px;
    }
    .run-detail-panel {
      transition: all 0.2s ease;
    }
    .run-detail-panel.is-empty {
      padding-bottom: 16px;
    }
    .empty-state {
      display: grid;
      gap: 10px;
      border: 1px dashed rgba(15,118,110,0.22);
      background: linear-gradient(180deg, rgba(255,255,255,0.68), rgba(249,243,231,0.78));
      border-radius: 18px;
      padding: 18px;
    }
    .empty-state-title {
      font-size: 18px;
      font-weight: 700;
    }
    .empty-state-copy {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }
    details.debug {
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fbf7f0;
      overflow: hidden;
    }
    details.debug summary {
      list-style: none;
      cursor: pointer;
      padding: 14px 16px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 13px;
      font-weight: 700;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    details.debug summary::-webkit-details-marker { display: none; }
    .scroll-region {
      max-height: 760px;
      overflow: auto;
      padding-right: 4px;
      min-width: 0;
    }
    .scroll-region.runs {
      max-height: 820px;
    }
    .scroll-region.uploads {
      max-height: 960px;
    }
    @media (max-width: 980px) {
      .layout, .upload-meta, .detail-grid, .section-grid, .metrics-grid, .mission-grid, .session-grid, .meta-grid {
        grid-template-columns: 1fr;
      }
      .brand-row {
        display: grid;
      }
      .brand-title { font-size: 34px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="topbar">
      <div class="brand-row">
        <div>
          <div class="brand-mark">Local Operator Surface</div>
          <h1 class="brand-title">{spot} Browser Operations Dashboard</h1>
          <div class="brand-copy">Local-first upload, run tracking, review-state visibility, and audit-oriented operator actions for the current `.xlsx` workflow.</div>
        </div>
        <div class="session-rail">
          <div class="eyebrow">Operator Session</div>
          <div class="message" id="authMessage">Loading session.</div>
          <div class="session-grid">
            <div class="session-field">
              <label for="actorNameInput">Actor</label>
              <input type="text" id="actorNameInput" placeholder="Actor name" value="local-operator" />
            </div>
            <div class="session-field">
              <label for="roleInput">Role</label>
              <select id="roleInput">
                <option value="operator">operator</option>
                <option value="reviewer">reviewer</option>
                <option value="acceptance_lead">acceptance_lead</option>
                <option value="admin">admin</option>
              </select>
            </div>
            <div class="session-field">
              <label for="accessCodeInput">Access Code</label>
              <input type="text" id="accessCodeInput" placeholder="Local access code" value="spot-local" />
            </div>
          </div>
          <div class="session-actions">
            <button class="secondary" type="button" onclick="login()">Login</button>
            <button class="secondary" type="button" onclick="logout()">Logout</button>
          </div>
        </div>
      </div>
    </section>
    <section class="hero">
      <div class="hero-card">
        <div class="mission-grid">
          <div class="metrics-card">
            <div>
              <div class="eyebrow">Mission Control</div>
              <div class="brand-copy">Processing status, operator controls, throughput, and queue pressure for the currently active local workload.</div>
            </div>
            <div class="status-actions">
              <button class="secondary" type="button" id="pauseActiveButton" onclick="manageActiveRun('pause')" disabled>Pause Processing</button>
              <button class="secondary" type="button" id="resumeActiveButton" onclick="manageActiveRun('resume')" disabled>Resume Processing</button>
              <button class="warn" type="button" id="stopActiveButton" onclick="manageActiveRun('stop')" disabled>Stop Run</button>
            </div>
            <div class="metrics-grid">
              <div class="status-tile">
                <div class="status-label">Run State</div>
                <div class="status-value" id="activeRunState">Idle</div>
                <div class="status-sub" id="activeRunId">No active run</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Processed Rows</div>
                <div class="status-value" id="rowsInvestigated">0</div>
                <div class="status-sub">Rows classified so far</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Total Rows</div>
                <div class="status-value" id="rowsLoaded">0</div>
                <div class="status-sub">Rows accepted for the active run</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Row Progress</div>
                <div class="status-value" id="queueProgress">0%</div>
                <div class="status-sub" id="queueEta">Estimated time remaining unavailable</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Rows Remaining</div>
                <div class="status-value" id="activeRowsRemaining">-</div>
                <div class="status-sub">Rows not yet classified</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Average Seconds per Row</div>
                <div class="status-value" id="activeAvgSecPerRow">-</div>
                <div class="status-sub">Observed processing speed</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Elapsed Processing Time</div>
                <div class="status-value" id="activeElapsedSeconds">-</div>
                <div class="status-sub">Wall-clock time since run start</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Review-Required Rows</div>
                <div class="status-value" id="activeReviewRequiredRows">-</div>
                <div class="status-sub">Rows flagged for reviewer action</div>
              </div>
            </div>
            <div class="inline-kpis">
              <span class="mini-kpi">Judge-Lane Rows: <strong id="rowsJudged">0</strong></span>
              <span class="mini-kpi">Threat Rows: <strong id="activeThreats">-</strong></span>
              <span class="mini-kpi">Threat Rate: <strong id="activeThreatRate">-</strong></span>
              <span class="mini-kpi">Projected Threats: <strong id="activeThreatProjection">-</strong></span>
            </div>
            <div class="message" id="activeProcessingMessage">No active run metrics yet.</div>
          </div>
          <div class="control-card">
            <div>
              <div class="eyebrow">Operational Snapshot</div>
              <div class="control-note">A compact readout of intake health, review load, and current queue pressure. This surface should stay readable while a run is in motion.</div>
            </div>
            <div class="metrics-grid" style="grid-template-columns: repeat(2, minmax(0, 1fr));">
              <div class="status-tile">
                <div class="status-label">Run Records</div>
                <div class="status-value" id="runCount">0</div>
                <div class="status-sub" id="runHealth">No run selected</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Accepted Workbooks</div>
                <div class="status-value" id="uploadCount">0</div>
                <div class="status-sub">Validated intake records</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Pending Review Rows</div>
                <div class="status-value" id="pendingReviewCount">0</div>
                <div class="status-sub">Rows awaiting reviewer action</div>
              </div>
              <div class="status-tile">
                <div class="status-label">Segment Queue</div>
                <div class="status-value" id="segmentCount">0</div>
                <div class="status-sub" id="segmentHealth">No queued uploads</div>
              </div>
            </div>
            <div class="message" id="queueSummaryMessage">Queue summary unavailable.</div>
          </div>
        </div>
      </div>
    </section>

    <section class="layout">
      <div class="stack">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Upload Intake</h2>
              <div class="panel-note">Queue one or more approved `.xlsx` workbooks, validate them against runtime guardrails, and promote the selected intake record into a live run.</div>
            </div>
            <span class="workflow-badge">Queue Intake -> Run Control -> Review -> Artifacts</span>
          </div>
          <form class="upload-form" onsubmit="event.preventDefault(); uploadWorkbooks();">
            <div class="file-drop">
              <div class="file-drop-title">Workbook Intake</div>
              <div class="file-drop-copy">Choose one or more Excel workbooks. Intake validation happens immediately, and accepted files become queue candidates for run start.</div>
              <input type="file" id="uploadFile" accept=".xlsx" multiple />
            </div>
            <div class="upload-meta">
              <input type="text" id="runIdInput" placeholder="Run ID (for start action)" value="spot-browser-run" />
              <input type="text" id="languageInput" list="languageSuggestions" placeholder="Language code (e.g. he, ar, hu, de)" value="de" />
              <datalist id="languageSuggestions">
                <option value="he"></option>
                <option value="ar"></option>
                <option value="hu"></option>
                <option value="de"></option>
                <option value="en"></option>
                <option value="ru"></option>
                <option value="other"></option>
              </datalist>
              <select id="reviewModeInput">
                <option value="partial">partial</option>
                <option value="full">full</option>
                <option value="none">none</option>
              </select>
            </div>
            <div class="actions">
              <button class="primary" id="uploadButton" type="submit">Add Workbooks To Queue</button>
              <button class="warn" id="startUploadButton" type="button" onclick="startSelectedUpload()" disabled>Start Run From Selected Workbook</button>
            </div>
            <div class="message" id="uploadMessage">No workbooks queued yet.</div>
          </form>
        </div>

        <div class="section-grid">
          <div class="panel">
            <div class="panel-head">
              <div>
                <h2 class="panel-title">Recent Runs</h2>
                <div class="panel-note">Persisted run records prioritized for operator decisions, not raw storage inspection.</div>
              </div>
              <div class="actions">
                <button class="secondary" onclick="loadDashboard()">Refresh</button>
              </div>
            </div>
            <div class="scroll-region runs">
              <div class="list" id="runsList"></div>
            </div>
          </div>

          <div class="panel run-detail-panel is-empty" id="runDetailPanel">
            <div class="panel-head">
              <div>
                <h2 class="panel-title">Run Detail</h2>
                <div class="panel-note">Select a run to inspect state, review summary, and next operator actions.</div>
              </div>
            </div>
            <div id="runDetailEmpty" class="empty-state">
              <div class="empty-state-title">No run selected</div>
              <div class="empty-state-copy">Choose a run from the left column to unlock lifecycle controls, review payloads, and action history. This panel stays compact until it has something worth showing.</div>
            </div>
            <div id="runDetail" style="display:none;">
              <div class="detail-summary">
                <div class="detail-grid">
                  <div class="detail-box">
                    <div class="detail-label">Run ID</div>
                    <div id="detailRunId"></div>
                  </div>
                  <div class="detail-box">
                    <div class="detail-label">State</div>
                    <div id="detailState"></div>
                  </div>
                  <div class="detail-box">
                    <div class="detail-label">Review Summary</div>
                    <div id="detailReview"></div>
                  </div>
                  <div class="detail-box">
                    <div class="detail-label">Upload Link</div>
                    <div id="detailUpload"></div>
                  </div>
                </div>
                <div class="toolbar">
                  <button class="secondary" type="button" onclick="loadSelectedRun()">Refresh Run Detail</button>
                  <button class="secondary" type="button" onclick="loadSelectedRunReviews()">Load Review Rows</button>
                  <button class="secondary" type="button" onclick="loadSelectedRunActions()">Load Action Log</button>
                  <button class="secondary" type="button" id="pauseSelectedButton" onclick="manageSelectedRun('pause')" disabled>Pause</button>
                  <button class="secondary" type="button" id="resumeSelectedButton" onclick="manageSelectedRun('resume')" disabled>Resume</button>
                  <button class="warn" type="button" id="stopSelectedButton" onclick="manageSelectedRun('stop')" disabled>Stop</button>
                </div>
                <div class="message" id="detailMessage">Run detail loaded.</div>
                <details class="debug">
                  <summary>Review Rows Payload</summary>
                  <pre id="reviewRowsPre">[]</pre>
                </details>
                <details class="debug">
                  <summary>Action Log Payload</summary>
                  <pre id="actionsPre">[]</pre>
                </details>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="stack">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Accepted Uploads</h2>
              <div class="panel-note">Accepted intake records are queue candidates. Select one to promote it into the current run lane.</div>
            </div>
          </div>
          <div class="scroll-region uploads">
            <div class="list" id="uploadsList"></div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Queue Overview</h2>
              <div class="panel-note">High-level queue visibility stays in view; raw diagnostics are available only when needed.</div>
            </div>
          </div>
          <div class="meta-grid" style="margin-bottom:16px;">
            <div class="meta-box">
              <div class="meta-box-label">Tracked Uploads</div>
              <div class="meta-box-value" id="overviewUploadCount">0</div>
            </div>
            <div class="meta-box">
              <div class="meta-box-label">Active Uploads</div>
              <div class="meta-box-value" id="overviewActiveUploadCount">0</div>
            </div>
            <div class="meta-box">
              <div class="meta-box-label">Total Segments</div>
              <div class="meta-box-value" id="overviewSegmentCount">0</div>
            </div>
            <div class="meta-box">
              <div class="meta-box-label">Processed Rows</div>
              <div class="meta-box-value" id="overviewProcessedRows">0</div>
            </div>
          </div>
          <div class="phase-row" id="queueOverviewPhases"></div>
          <details class="debug" style="margin-top:16px;">
            <summary>Raw Queue Diagnostics</summary>
            <pre id="queueOverviewPre">No queue data loaded yet.</pre>
          </details>
        </div>
      </div>
    </section>
  </div>

  <script>
    let selectedUploadId = null;
    let selectedRunId = null;

    function formatEta(seconds) {
      const value = Number(seconds);
      if (!Number.isFinite(value) || value <= 0) return 'Estimated time remaining unavailable';
      if (value < 60) return `ETA ${value}s`;
      const minutes = Math.floor(value / 60);
      const remainingSeconds = value % 60;
      if (minutes < 60) return `ETA ${minutes}m ${remainingSeconds}s`;
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      return `ETA ${hours}h ${remainingMinutes}m`;
    }

    function formatDuration(seconds) {
      const value = Number(seconds);
      if (!Number.isFinite(value) || value < 0) return '-';
      if (value < 60) return `${value.toFixed(0)}s`;
      const minutes = Math.floor(value / 60);
      const remainingSeconds = Math.floor(value % 60);
      if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      return `${hours}h ${remainingMinutes}m`;
    }

    function escapeHtml(v) {
      return String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',\"'\":'&#39;'}[ch]));
    }

    function pillClass(status) {
      const txt = String(status || '').toUpperCase();
      if (txt.includes('COMPLETED') || txt.includes('ACCEPTED')) return 'pill ok';
      if (txt.includes('FAILED') || txt.includes('REJECTED') || txt.includes('NOT_ACCEPTED')) return 'pill danger';
      return 'pill warn';
    }

    function setMessage(id, text, kind) {
      const el = document.getElementById(id);
      el.className = 'message' + (kind ? ' ' + kind : '');
      el.textContent = text;
    }

    function formatNumber(value) {
      const num = Number(value);
      if (!Number.isFinite(num)) return '-';
      return num.toLocaleString();
    }

    function formatPercent(value) {
      const num = Number(value);
      if (!Number.isFinite(num)) return '-';
      return `${num.toFixed(2)}%`;
    }

    function renderPhasePills(phases) {
      const entries = Object.entries(phases || {});
      if (!entries.length) {
        return '<span class="phase-pill">No queue phases</span>';
      }
      return entries.map(([name, count]) => `
        <span class="phase-pill"><strong>${escapeHtml(name)}</strong><span>${escapeHtml(count)}</span></span>
      `).join('');
    }

    function setProcessButtons({ pause, resume, stop }) {
      document.getElementById('pauseActiveButton').disabled = !pause;
      document.getElementById('resumeActiveButton').disabled = !resume;
      document.getElementById('stopActiveButton').disabled = !stop;
      document.getElementById('pauseSelectedButton').disabled = !pause;
      document.getElementById('resumeSelectedButton').disabled = !resume;
      document.getElementById('stopSelectedButton').disabled = !stop;
    }

    async function manageRun(runId, action, messageId) {
      if (!runId) {
        setMessage(messageId, 'No run is available for this action.', 'error');
        return;
      }
      const pathByAction = {
        pause: '/classify/pause/' + encodeURIComponent(runId),
        resume: '/classify/resume/' + encodeURIComponent(runId),
        stop: '/classify/stop/' + encodeURIComponent(runId),
      };
      const res = await fetch(pathByAction[action], { method: 'POST' });
      const data = await res.json();
      setMessage(messageId, res.ok ? `Run action "${action}" completed for ${runId}.` : JSON.stringify(data, null, 2), res.ok ? 'ok' : 'error');
      await loadDashboard();
      if (selectedRunId === runId) {
        await loadSelectedRun();
      }
    }

    async function manageActiveRun(action) {
      const runId = document.getElementById('activeRunId').textContent;
      await manageRun(runId === 'No active run' ? '' : runId, action, 'activeProcessingMessage');
    }

    async function manageSelectedRun(action) {
      await manageRun(selectedRunId, action, 'detailMessage');
    }

    async function loadSession() {
      const res = await fetch('/auth/session');
      const data = await res.json();
      const session = data.session || {};
      if (data.authenticated) {
        setMessage('authMessage', `Authenticated as ${session.actor_name || 'unknown'} · role ${session.role || 'unknown'} · local auth ${data.auth_enabled ? 'enabled' : 'disabled'}.`, 'ok');
      } else {
        setMessage('authMessage', `No active operator session. Local auth ${data.auth_enabled ? 'is enabled' : 'is disabled'}.`, 'error');
      }
    }

    async function login() {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actor_name: document.getElementById('actorNameInput').value,
          role: document.getElementById('roleInput').value,
          access_code: document.getElementById('accessCodeInput').value
        })
      });
      const data = await res.json();
      setMessage('authMessage', res.ok ? `Login succeeded for ${data.actor_name || document.getElementById('actorNameInput').value}.` : JSON.stringify(data, null, 2), res.ok ? 'ok' : 'error');
      await loadSession();
    }

    async function logout() {
      const res = await fetch('/auth/logout', { method: 'POST' });
      await res.json();
      setMessage('authMessage', 'Local operator session closed.', 'ok');
      await loadSession();
    }

    async function uploadWorkbooks() {
      const fileInput = document.getElementById('uploadFile');
      const button = document.getElementById('uploadButton');
      const files = Array.from(fileInput.files || []);
      if (!files.length) {
        setMessage('uploadMessage', 'Choose one or more .xlsx workbooks first.', 'error');
        return;
      }
      button.disabled = true;
      try {
        const results = [];
        for (const file of files) {
          const buf = await file.arrayBuffer();
          const encodedFilename = encodeURIComponent(file.name || 'upload.xlsx');
          const res = await fetch('/uploads/intake?filename=' + encodedFilename, {
            method: 'POST',
            body: buf,
          });
          const data = await res.json();
          results.push({ ok: res.ok, data });
          if (res.ok && data.status === 'accepted') {
            selectedUploadId = data.upload_id;
          }
        }
        document.getElementById('startUploadButton').disabled = !selectedUploadId;
        const accepted = results.filter(item => item.ok && item.data.status === 'accepted').length;
        const rejected = results.filter(item => item.ok && item.data.status !== 'accepted').length;
        const failed = results.filter(item => !item.ok).length;
        setMessage(
          'uploadMessage',
          `${accepted} workbook(s) accepted, ${rejected} rejected, ${failed} failed request(s). ${selectedUploadId ? `Selected intake record: ${selectedUploadId}.` : 'No accepted workbook selected yet.'}`,
          accepted > 0 ? 'ok' : 'error',
        );
        await loadDashboard();
      } catch (err) {
        setMessage('uploadMessage', String(err), 'error');
      } finally {
        button.disabled = false;
      }
    }

    async function startSelectedUpload() {
      if (!selectedUploadId) {
        setMessage('uploadMessage', 'Select or create an accepted upload first.', 'error');
        return;
      }
      const runId = document.getElementById('runIdInput').value.trim();
      const language = document.getElementById('languageInput').value.trim();
      const reviewMode = document.getElementById('reviewModeInput').value;
      if (!runId) {
        setMessage('uploadMessage', 'Run ID is required.', 'error');
        return;
      }
      if (!language) {
        setMessage('uploadMessage', 'Language code is required.', 'error');
        return;
      }
      const res = await fetch('/classify/start/' + encodeURIComponent(runId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          upload_id: selectedUploadId,
          language: language,
          review_mode: reviewMode
        })
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage('uploadMessage', JSON.stringify(data, null, 2), 'error');
        return;
      }
      selectedRunId = runId;
      setMessage('uploadMessage', `Run ${runId} started from intake record ${selectedUploadId}.`, 'ok');
      await loadDashboard();
      await loadSelectedRun();
    }

    async function loadDashboard() {
      const [runsRes, uploadsRes, overviewRes] = await Promise.all([fetch('/runs'), fetch('/uploads'), fetch('/operations/overview')]);
      const runs = await runsRes.json();
      const uploads = await uploadsRes.json();
      const overview = await overviewRes.json();
      renderRuns(Array.isArray(runs) ? runs : []);
      renderUploads(Array.isArray(uploads) ? uploads : []);
      document.getElementById('queueOverviewPre').textContent = JSON.stringify(overview, null, 2);
      document.getElementById('overviewUploadCount').textContent = formatNumber((overview && overview.uploads) || 0);
      document.getElementById('overviewActiveUploadCount').textContent = formatNumber((overview && overview.active_uploads) || 0);
      document.getElementById('overviewSegmentCount').textContent = formatNumber((overview && overview.total_segments) || 0);
      document.getElementById('overviewProcessedRows').textContent = formatNumber((overview && overview.processed_rows) || 0);
      document.getElementById('queueOverviewPhases').innerHTML = renderPhasePills((overview && overview.segments_by_status) || {});
      const acceptedUploads = uploads.filter(u => u.status === 'accepted');
      const activeRun = runs.find(r => ['STARTING', 'PENDING', 'VALIDATING', 'PROCESSING', 'WRITING', 'PAUSED'].includes(String(r.state || r.status || '').toUpperCase()));
      const pendingReview = runs.reduce((acc, r) => acc + Number((((r.review_summary || {}).pending_rows) || 0)), 0);
      const activeQueueUpload = ((overview && overview.recent_uploads) || []).find(item => item.run && ['STARTING', 'PENDING', 'VALIDATING', 'PROCESSING', 'WRITING', 'PAUSED'].includes(String(item.run.state || '').toUpperCase()));
      document.getElementById('runCount').textContent = String(runs.length);
      document.getElementById('uploadCount').textContent = String(acceptedUploads.length);
      document.getElementById('activeRunState').textContent = activeRun ? String(activeRun.state || activeRun.status) : 'Idle';
      document.getElementById('activeRunId').textContent = activeRun ? String(activeRun.run_id || '-') : 'No active run';
      document.getElementById('runHealth').textContent = runs.length ? `Latest: ${String((runs[0] || {}).run_id || '-')}` : 'No run selected';
      document.getElementById('pendingReviewCount').textContent = String(pendingReview);
      document.getElementById('segmentCount').textContent = String((overview && overview.total_segments) || 0);
      document.getElementById('segmentHealth').textContent = activeQueueUpload
        ? `${((activeQueueUpload.segments_by_status) || {}).COMPLETED || 0} completed · ${((activeQueueUpload.segments_by_status) || {}).PROCESSING || 0} processing · ${((activeQueueUpload.segments_by_status) || {}).QUEUED || 0} queued`
        : `${((overview && overview.segments_by_status) || {}).COMPLETED || 0} completed · ${((overview && overview.segments_by_status) || {}).PROCESSING || 0} processing · ${((overview && overview.segments_by_status) || {}).QUEUED || 0} queued`;
      document.getElementById('queueProgress').textContent = formatPercent((activeQueueUpload && activeQueueUpload.progress_percentage) || (overview && overview.progress_percentage) || 0);
      document.getElementById('queueEta').textContent = activeQueueUpload ? formatEta((activeQueueUpload.run || {}).estimated_remaining_seconds) : 'ETA unavailable';
      document.getElementById('queueSummaryMessage').textContent = activeQueueUpload
        ? `Active intake ${activeQueueUpload.filename || activeQueueUpload.upload_id} is in ${String(((activeQueueUpload.run || {}).state) || 'unknown').toLowerCase()} state with ${formatPercent(activeQueueUpload.row_progress_percentage || 0)} row completion and ${formatPercent(activeQueueUpload.segment_progress_percentage || 0)} segment completion.`
        : `The queue is tracking ${formatNumber((overview && overview.uploads) || 0)} upload records across ${formatNumber((overview && overview.total_segments) || 0)} segments.`;
      const activeStats = ((activeQueueUpload || {}).run || {}).processing_stats || ((activeQueueUpload || {}).processing_stats) || {};
      const activeQueueRun = ((activeQueueUpload || {}).run) || {};
      document.getElementById('rowsLoaded').textContent = formatNumber(activeQueueRun.total_rows || activeStats.total_rows || 0);
      document.getElementById('rowsInvestigated').textContent = formatNumber(activeQueueRun.processed_rows || activeStats.processed_rows || 0);
      document.getElementById('rowsJudged').textContent = formatNumber(activeStats.judged_rows || 0);
      const activeState = String(activeQueueRun.state || '').toUpperCase();
      setProcessButtons({
        pause: ['STARTING', 'PENDING', 'VALIDATING', 'PROCESSING', 'WRITING'].includes(activeState),
        resume: activeState === 'PAUSED',
        stop: ['STARTING', 'PENDING', 'VALIDATING', 'PROCESSING', 'WRITING', 'PAUSED'].includes(activeState),
      });
      renderActiveProcessing(activeQueueUpload);
    }

    function renderActiveProcessing(activeQueueUpload) {
      const stats = ((activeQueueUpload || {}).run || {}).processing_stats || ((activeQueueUpload || {}).processing_stats) || {};
      const run = ((activeQueueUpload || {}).run) || {};
      const processedRows = Number(run.processed_rows || stats.processed_rows || 0);
      const totalRows = Number(run.total_rows || stats.total_rows || 0);
      const rowsRemaining = Math.max(totalRows - processedRows, 0);
      document.getElementById('rowsLoaded').textContent = formatNumber(totalRows);
      document.getElementById('rowsInvestigated').textContent = formatNumber(processedRows);
      document.getElementById('activeRowsRemaining').textContent = totalRows > 0
        ? formatNumber(rowsRemaining)
        : '-';
      document.getElementById('activeAvgSecPerRow').textContent = Number.isFinite(Number(stats.avg_seconds_per_row))
        ? `${Number(stats.avg_seconds_per_row).toFixed(2)} s`
        : '-';
      document.getElementById('activeElapsedSeconds').textContent = Number.isFinite(Number(stats.elapsed_seconds))
        ? formatDuration(Number(stats.elapsed_seconds))
        : '-';
      document.getElementById('activeReviewRequiredRows').textContent = Number.isFinite(Number(stats.review_required_rows_detected))
        ? formatNumber(stats.review_required_rows_detected)
        : '-';
      document.getElementById('activeThreats').textContent = Number.isFinite(Number(stats.threat_rows_detected))
        ? formatNumber(stats.threat_rows_detected)
        : '-';
      document.getElementById('activeThreatRate').textContent = Number.isFinite(Number(stats.threat_rate))
        ? `${(Number(stats.threat_rate) * 100).toFixed(2)}%`
        : '-';
      document.getElementById('activeThreatProjection').textContent = Number.isFinite(Number(stats.projected_threat_rows))
        ? `${formatNumber(stats.projected_threat_rows)} est.`
        : '-';
      if (activeQueueUpload) {
        const threatRate = Number.isFinite(Number(stats.threat_rate)) ? `${(Number(stats.threat_rate) * 100).toFixed(2)}% provisional threat rate` : 'Threat rate unavailable';
        const elapsed = Number.isFinite(Number(stats.elapsed_seconds)) ? `${formatDuration(Number(stats.elapsed_seconds))} elapsed` : 'Elapsed time unavailable';
        const judged = Number.isFinite(Number(stats.judged_rows)) ? `${formatNumber(stats.judged_rows)} judge-lane rows` : 'Judge-lane row count unavailable';
        setMessage('activeProcessingMessage', `${formatNumber(processedRows)} of ${formatNumber(totalRows)} rows processed · ${elapsed} · ${threatRate} · ${judged}`, 'ok');
        return;
      }
      setMessage('activeProcessingMessage', 'No active run metrics yet.', '');
    }

    function renderRuns(runs) {
      const root = document.getElementById('runsList');
      if (!runs.length) {
        root.innerHTML = '<div class=\"message\">No persisted runs yet.</div>';
        return;
      }
      root.innerHTML = runs.slice(0, 10).map(run => `
        <div class="card ${selectedRunId === (run.run_id || '') ? 'selected' : ''}">
          <div class="card-top">
            <div class="card-title">${escapeHtml(run.run_id || '-')}</div>
            <span class="${pillClass(run.state || run.status)}">${escapeHtml(run.state || run.status || 'unknown')}</span>
          </div>
          <div class="meta">Language: ${escapeHtml(run.language || '-')} · Review mode: ${escapeHtml(run.review_mode || '-')}</div>
          <div class="meta-grid">
            <div class="meta-box">
              <div class="meta-box-label">Rows</div>
              <div class="meta-box-value">${escapeHtml((((run.progress || {}).processed_rows) || (run.processed_rows || 0)))} / ${escapeHtml((((run.progress || {}).total_rows) || (run.total_rows || '-')))}</div>
            </div>
            <div class="meta-box">
              <div class="meta-box-label">Review Queue</div>
              <div class="meta-box-value">${escapeHtml((((run.review_summary || {}).pending_rows) || 0))}</div>
            </div>
          </div>
          <div class="meta">Upload link: ${escapeHtml(run.upload_id || 'none attached')}</div>
          <div class="actions">
            <button class="secondary" type="button" onclick="selectRun('${escapeHtml(run.run_id || '')}')">Open Run Detail</button>
            <a class="ghost-link" href="/runs/${encodeURIComponent(run.run_id || '')}/view">Full Page</a>
            <a class="ghost-link" href="/runs/${encodeURIComponent(run.run_id || '')}/review">Review Queue</a>
          </div>
        </div>
      `).join('');
    }

    function renderUploads(uploads) {
      const root = document.getElementById('uploadsList');
      if (!uploads.length) {
        root.innerHTML = '<div class=\"message\">No uploads persisted yet.</div>';
        return;
      }
      root.innerHTML = uploads.slice(0, 10).map(upload => `
        <div class="card ${selectedUploadId === (upload.upload_id || '') ? 'selected' : ''}">
          <div class="card-top">
            <div class="card-title">${escapeHtml(upload.filename || upload.upload_id)}</div>
            <span class="${pillClass(upload.status)}">${escapeHtml(upload.status || 'unknown')}</span>
          </div>
          <div class="meta">${escapeHtml(upload.upload_id || '-')}</div>
          <div class="meta-grid">
            <div class="meta-box">
              <div class="meta-box-label">Rows</div>
              <div class="meta-box-value">${escapeHtml((((upload.validation || {}).row_count) || '-'))}</div>
            </div>
            <div class="meta-box">
              <div class="meta-box-label">Segments</div>
              <div class="meta-box-value">${escapeHtml((((upload.queue_summary || {}).segment_count) || 0))}</div>
            </div>
          </div>
          <div class="meta">Row progress ${formatPercent((((upload.queue_summary || {}).row_progress_percentage) || 0))} · Segment progress ${formatPercent((((upload.queue_summary || {}).segment_progress_percentage) || 0))}</div>
          <div class="phase-row">${renderPhasePills(((upload.queue_summary || {}).segments_by_status) || {})}</div>
          <div class="actions">
            <button class="secondary" type="button" onclick="selectUpload('${escapeHtml(upload.upload_id || '')}')">Use For Run Start</button>
          </div>
        </div>
      `).join('');
    }

    function selectUpload(uploadId) {
      selectedUploadId = uploadId;
      document.getElementById('startUploadButton').disabled = false;
      setMessage('uploadMessage', 'Selected workbook for run start: ' + uploadId, 'ok');
    }

    async function selectRun(runId) {
      selectedRunId = runId;
      await loadSelectedRun();
    }

    async function loadSelectedRun() {
      if (!selectedRunId) return;
      const res = await fetch('/runs/' + encodeURIComponent(selectedRunId) + '/detail');
      const data = await res.json();
      if (!res.ok) {
        setMessage('detailMessage', JSON.stringify(data, null, 2), 'error');
        return;
      }
      document.getElementById('runDetailPanel').classList.remove('is-empty');
      document.getElementById('runDetailEmpty').style.display = 'none';
      document.getElementById('runDetail').style.display = 'block';
      document.getElementById('detailRunId').textContent = data.run_id || '-';
      const rowPct = (data.progress && Number.isFinite(Number(data.progress.total_rows)) && Number(data.progress.total_rows) > 0)
        ? ((Number(data.progress.processed_rows || 0) / Number(data.progress.total_rows)) * 100).toFixed(2)
        : String((data.progress || {}).progress_percentage ?? 0);
      document.getElementById('detailState').textContent = `${data.state || '-'} (${rowPct}% of rows)`;
      const summary = data.review_summary || {};
      document.getElementById('detailReview').textContent = `required=${summary.review_required_rows || 0}, reviewed=${summary.reviewed_rows || 0}, pending=${summary.pending_rows || 0}`;
      document.getElementById('detailUpload').textContent = data.upload_id || '-';
      const processedRows = Number((data.progress || {}).processed_rows || 0);
      const totalRows = Number((data.progress || {}).total_rows || 0);
      const state = String(data.state || '').toUpperCase();
      setProcessButtons({
        pause: ['STARTING', 'PENDING', 'VALIDATING', 'PROCESSING', 'WRITING'].includes(state),
        resume: state === 'PAUSED',
        stop: ['STARTING', 'PENDING', 'VALIDATING', 'PROCESSING', 'WRITING', 'PAUSED'].includes(state),
      });
      setMessage('detailMessage', `${data.state || 'Unknown'} · ${formatNumber(processedRows)} processed row(s) out of ${totalRows > 0 ? formatNumber(totalRows) : 'unknown total'} · pending review ${summary.pending_rows || 0}.`, 'ok');
    }

    async function loadSelectedRunReviews() {
      if (!selectedRunId) return;
      const res = await fetch('/runs/' + encodeURIComponent(selectedRunId) + '/review-rows');
      const data = await res.json();
      document.getElementById('reviewRowsPre').textContent = JSON.stringify(data, null, 2);
    }

    async function loadSelectedRunActions() {
      if (!selectedRunId) return;
      const res = await fetch('/runs/' + encodeURIComponent(selectedRunId) + '/actions');
      const data = await res.json();
      document.getElementById('actionsPre').textContent = JSON.stringify(data, null, 2);
    }

    function resetRunDetailPanel() {
      document.getElementById('runDetailPanel').classList.add('is-empty');
      document.getElementById('runDetailEmpty').style.display = 'grid';
      document.getElementById('runDetail').style.display = 'none';
    }

    loadDashboard();
    resetRunDetailPanel();
    loadSession();
    setInterval(loadDashboard, 5000);
    setInterval(loadSession, 5000);
  </script>
</body>
</html>"""
    return page


@router.get("/runs/{run_id}/view", response_class=HTMLResponse)
def run_detail_page(run_id: str, request: Request):
    require_permission(request, "view")
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>{spot} Run Detail</title>
  <style>
    :root {
      --bg: #f5efe3;
      --panel: #fffaf2;
      --line: #dacdb7;
      --text: #201d18;
      --muted: #6d655b;
      --accent: #0f766e;
      --warn: #b45309;
      --danger: #b91c1c;
      --ok: #166534;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: linear-gradient(180deg, #f8f2e8 0%, var(--bg) 100%);
      color: var(--text);
      font-family: Georgia, "Palatino Linotype", serif;
    }
    __PAGE_CHROME_CSS__
    .header, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      margin-bottom: 18px;
    }
    .header-top, .panel-top {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 14px;
    }
    h1, h2, h3 { margin: 0; }
    h1 { font-size: 34px; }
    .muted { color: var(--muted); line-height: 1.45; }
    .pill {
      display: inline-flex;
      border-radius: 999px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      font-size: 12px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-weight: 700;
    }
    .pill.ok { color: var(--ok); }
    .pill.warn { color: var(--warn); }
    .pill.danger { color: var(--danger); }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .box {
      background: white;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
    }
    .label {
      color: var(--muted);
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }
    .value { font-size: 18px; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
    button, a.link-btn, select, textarea {
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 14px;
    }
    button, a.link-btn {
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      cursor: pointer;
      text-decoration: none;
    }
    button.primary { background: var(--accent); color: white; }
    button.secondary, a.link-btn { background: #e9dfcf; color: var(--text); }
    .list { display: grid; gap: 10px; }
    .row-card {
      background: white;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      display: grid;
      gap: 8px;
    }
    .row-head { display: flex; justify-content: space-between; gap: 10px; }
    pre {
      margin: 0;
      padding: 12px;
      border-radius: 14px;
      background: #fbf6ed;
      border: 1px solid var(--line);
      overflow: auto;
      font-size: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    textarea, select {
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      background: white;
    }
    .review-form { display: grid; gap: 8px; margin-top: 10px; }
    .message {
      white-space: pre-wrap;
      padding: 10px 12px;
      border-radius: 12px;
      background: #f7f1e6;
      border: 1px solid var(--line);
      font-size: 13px;
      line-height: 1.45;
    }
    @media (max-width: 920px) {
      .grid { grid-template-columns: 1fr; }
      .header-top, .panel-top { flex-direction: column; }
      h1 { font-size: 28px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    __PAGE_TOPBAR__
    <section class="header">
      <div class="header-top">
        <div>
          <div class="muted"><a href="/app">Back to dashboard</a></div>
          <h1>Run Detail: __RUN_ID__</h1>
          <p class="muted">Lifecycle, review summary, artifacts, and operator-safe actions for a single local `{spot}` run.</p>
        </div>
        <div class="pill warn" id="statePill">Loading</div>
      </div>
      <div class="grid">
        <div class="box"><div class="label">Progress</div><div class="value" id="progressValue">-</div></div>
        <div class="box"><div class="label">Review Queue</div><div class="value" id="reviewValue">-</div></div>
        <div class="box"><div class="label">Sign-off</div><div class="value" id="signoffValue">-</div></div>
      </div>
      <div class="actions">
        <button class="secondary" type="button" onclick="loadDetail()">Refresh</button>
        <button class="secondary" type="button" onclick="loadActions()">Load Actions</button>
        <button class="secondary" type="button" id="pauseBtn" onclick="runOperation('pause')">Pause Processing</button>
        <button class="secondary" type="button" id="resumeBtn" onclick="runOperation('resume')">Resume Processing</button>
        <button class="secondary" type="button" id="cancelBtn" onclick="runOperation('cancel')">Cancel Run</button>
        <button class="secondary" type="button" id="retryBtn" onclick="runOperation('retry')">Retry Run</button>
        <button class="secondary" type="button" id="recoverBtn" onclick="runOperation('recover')">Recover Run</button>
      </div>
      <div class="message" id="detailMessage">Loading run detail.</div>
    </section>

    <section class="panel">
      <div class="panel-top">
        <div>
          <h2>Run Overview</h2>
          <div class="muted">Current state, inputs, outputs, and next actions derived from persisted run records and artifacts.</div>
        </div>
      </div>
      <pre id="overviewPre">{}</pre>
    </section>

    <section class="panel">
      <div class="panel-top">
        <div>
          <h2>Available Actions</h2>
          <div class="muted">Actions shown here are guidance from the current run state, not speculative workflow beyond supported backend behavior.</div>
        </div>
      </div>
      <div class="list" id="actionsList"></div>
      <pre id="recoveryPre" style="margin-top:12px;">{}</pre>
    </section>

    <section class="panel">
      <div class="panel-top">
        <div>
          <h2>Review Rows</h2>
          <div class="muted">Flagged rows are listed with quick triage controls backed by the persistent review-state store.</div>
        </div>
      </div>
      <div class="list" id="reviewRowsList"></div>
    </section>

    <section class="panel">
      <div class="panel-top">
        <div>
          <h2>Artifacts And Sign-off</h2>
          <div class="muted">Downloadable local artifacts plus a sign-off control for completed runs.</div>
        </div>
      </div>
      <div class="actions" style="margin-bottom:12px;">
        <a class="link-btn" href="/runs/__RUN_ID__/artifacts/view">Open Artifact Center</a>
      </div>
      <div class="list" id="artifactList"></div>
      <div class="review-form" style="margin-top: 16px;">
        <select id="signoffDecision">
          <option value="accepted">accepted</option>
          <option value="accepted_with_conditions">accepted_with_conditions</option>
          <option value="not_accepted">not_accepted</option>
        </select>
        <textarea id="signoffNote" rows="4" placeholder="Sign-off note"></textarea>
        <button class="primary" type="button" onclick="submitSignoff()">Submit Sign-off</button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-top">
        <div>
          <h2>Action Log</h2>
          <div class="muted">Auditable operator and system actions written to the run directory.</div>
        </div>
      </div>
      <pre id="actionsPre">[]</pre>
    </section>
  </div>

  <script>
    const runId = '__RUN_ID__';
    let currentDetail = null;

    function pillClass(status) {
      const txt = String(status || '').toUpperCase();
      if (txt.includes('COMPLETED') || txt.includes('ACCEPTED')) return 'pill ok';
      if (txt.includes('FAILED') || txt.includes('NOT_ACCEPTED')) return 'pill danger';
      return 'pill warn';
    }

    function escapeHtml(v) {
      return String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',\"'\":'&#39;'}[ch]));
    }

    function setOperationButtons(ops) {
      document.getElementById('pauseBtn').disabled = !ops.pause;
      document.getElementById('resumeBtn').disabled = !ops.resume;
      document.getElementById('cancelBtn').disabled = !ops.cancel;
      document.getElementById('retryBtn').disabled = !ops.retry;
      document.getElementById('recoverBtn').disabled = !ops.recover;
    }

    async function loadDetail() {
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/detail');
      const data = await res.json();
      if (!res.ok) {
        document.getElementById('detailMessage').textContent = JSON.stringify(data, null, 2);
        return;
      }
      currentDetail = data;
      document.getElementById('statePill').className = pillClass(data.state);
      document.getElementById('statePill').textContent = data.state || '-';
      const processedRows = Number((data.progress || {}).processed_rows || 0);
      const totalRows = Number((data.progress || {}).total_rows || 0);
      const rowPct = totalRows > 0 ? ((processedRows / totalRows) * 100).toFixed(2) : String((data.progress || {}).progress_percentage ?? 0);
      document.getElementById('progressValue').textContent = totalRows > 0
        ? `${processedRows} / ${totalRows} rows (${rowPct}%)`
        : `${rowPct}%`;
      const summary = data.review_summary || {};
      document.getElementById('reviewValue').textContent = `required=${summary.review_required_rows || 0}, pending=${summary.pending_rows || 0}`;
      document.getElementById('signoffValue').textContent = data.signoff ? data.signoff.decision : 'not signed';
      document.getElementById('overviewPre').textContent = JSON.stringify(data, null, 2);
      document.getElementById('detailMessage').textContent = JSON.stringify({
        run_id: data.run_id,
        state: data.state,
        output_ready: data.output_ready,
        next_actions: data.next_actions
      }, null, 2);
      renderNextActions(data.next_actions || []);
      setOperationButtons(data.available_operations || {});
      document.getElementById('recoveryPre').textContent = JSON.stringify({
        running: (data.recovery || {}).running,
        paused: (data.recovery || {}).paused,
        pid: (data.recovery || {}).pid,
        output_ready: (data.recovery || {}).output_ready,
        can_retry: (data.recovery || {}).can_retry,
        can_cancel: (data.recovery || {}).can_cancel
      }, null, 2);
      renderReviewRows(data.review_rows_preview || []);
      renderArtifacts(data.artifacts || []);
    }

    async function runOperation(op) {
      const pathMap = {
        pause: '/classify/pause/' + encodeURIComponent(runId),
        resume: '/classify/resume/' + encodeURIComponent(runId),
        cancel: '/runs/' + encodeURIComponent(runId) + '/cancel',
        retry: '/runs/' + encodeURIComponent(runId) + '/retry',
        recover: '/runs/' + encodeURIComponent(runId) + '/recover'
      };
      const res = await fetch(pathMap[op], { method: 'POST' });
      const data = await res.json();
      document.getElementById('detailMessage').textContent = JSON.stringify(data, null, 2);
      await loadDetail();
      await loadActions();
    }

    function renderNextActions(actions) {
      const root = document.getElementById('actionsList');
      const labels = {
        inspect_failure: 'Inspect failure evidence and control state.',
        retry_when_supported: 'Retry once a deterministic restart path is available.',
        monitor_progress: 'Continue watching the persisted run progress.',
        pause_or_stop_if_needed: 'Use lifecycle controls only when operator intervention is required.',
        review_flagged_rows: 'Open review queue and complete pending row triage.',
        sign_off: 'Submit acceptance decision once evidence is complete.',
        view_signoff: 'Inspect the existing persisted sign-off record.',
        download_output: 'Retrieve workbook and audit artifacts.'
      };
      if (!actions.length) {
        root.innerHTML = '<div class="message">No guided actions for the current state.</div>';
        return;
      }
      root.innerHTML = actions.map(action => `
        <div class="row-card">
          <strong>${escapeHtml(action)}</strong>
          <div class="muted">${escapeHtml(labels[action] || 'Operator action derived from current run state.')}</div>
        </div>
      `).join('');
    }

    function renderReviewRows(rows) {
      const root = document.getElementById('reviewRowsList');
      if (!rows.length) {
        root.innerHTML = '<div class="message">No review-required rows for this run.</div>';
        return;
      }
      root.innerHTML = rows.map(row => `
        <div class="row-card">
          <div class="row-head">
            <strong>Row ${escapeHtml(row.row_index)}</strong>
            <span class="${pillClass(row.review_state || 'pending')}">${escapeHtml(row.review_state || 'pending')}</span>
          </div>
          <div>${escapeHtml(row.assigned_category || '-')}</div>
          <div class="muted">${escapeHtml(row.post_text || '')}</div>
          <div class="muted">Flags: ${escapeHtml((row.flags || []).join(', ') || '-')}</div>
          <div class="muted">Soft signals: ${escapeHtml((row.soft_signal_flags || []).join(', ') || '-')}</div>
          <div class="review-form">
            <select id="reviewState-${row.row_index}">
              <option value="pending" ${(row.review_state || 'pending') === 'pending' ? 'selected' : ''}>pending</option>
              <option value="reviewed" ${(row.review_state || '') === 'reviewed' ? 'selected' : ''}>reviewed</option>
              <option value="escalated" ${(row.review_state || '') === 'escalated' ? 'selected' : ''}>escalated</option>
            </select>
            <select id="reviewDecision-${row.row_index}">
              <option value="">no decision</option>
              <option value="confirm" ${(row.review_decision || '') === 'confirm' ? 'selected' : ''}>confirm</option>
              <option value="override" ${(row.review_decision || '') === 'override' ? 'selected' : ''}>override</option>
              <option value="escalate" ${(row.review_decision || '') === 'escalate' ? 'selected' : ''}>escalate</option>
            </select>
            <textarea id="reviewNote-${row.row_index}" rows="3" placeholder="Reviewer note">${escapeHtml(row.reviewer_note || '')}</textarea>
            <button class="secondary" type="button" onclick="submitReviewRow(${row.row_index})">Save Review Row</button>
          </div>
        </div>
      `).join('');
    }

    function renderArtifacts(artifacts) {
      const root = document.getElementById('artifactList');
      if (!artifacts.length) {
        root.innerHTML = '<div class="message">No artifacts detected yet.</div>';
        return;
      }
      root.innerHTML = artifacts.map(item => `
        <div class="row-card">
          <div class="row-head">
            <strong>${escapeHtml(item.name)}</strong>
            <span class="pill warn">${escapeHtml(item.bytes)} bytes</span>
          </div>
          <div class="muted">${escapeHtml(item.purpose || 'Run artifact')}</div>
          <div class="muted">${escapeHtml(item.path)}</div>
          <div class="actions">
            <a class="link-btn" href="${escapeHtml(item.download_path || '#')}">Download</a>
          </div>
        </div>
      `).join('');
    }

    async function submitReviewRow(rowIndex) {
      const payload = {
        review_state: document.getElementById('reviewState-' + rowIndex).value,
        review_decision: document.getElementById('reviewDecision-' + rowIndex).value || null,
        reviewer_note: document.getElementById('reviewNote-' + rowIndex).value,
        actor: 'browser-reviewer'
      };
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/review-rows/' + encodeURIComponent(rowIndex), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      document.getElementById('detailMessage').textContent = JSON.stringify(data, null, 2);
      await loadDetail();
      await loadActions();
    }

    async function submitSignoff() {
      const payload = {
        decision: document.getElementById('signoffDecision').value,
        note: document.getElementById('signoffNote').value,
        actor: 'browser-acceptance-lead'
      };
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/signoff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      document.getElementById('detailMessage').textContent = JSON.stringify(data, null, 2);
      await loadDetail();
      await loadActions();
    }

    async function loadActions() {
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/actions');
      const data = await res.json();
      document.getElementById('actionsPre').textContent = JSON.stringify(data, null, 2);
    }

    loadDetail();
    loadActions();
    setInterval(loadDetail, 5000);
  </script>
</body>
</html>"""
    return (
        page.replace("__RUN_ID__", run_id)
        .replace("__PAGE_CHROME_CSS__", _operator_page_chrome_css(max_width=1180))
        .replace(
            "__PAGE_TOPBAR__",
            _operator_page_topbar(
                title="{spot} Run Workspace",
                subtitle="Lifecycle control, review handling, and artifact retrieval for one deterministic local run.",
                links=[
                    ("Dashboard", "/app"),
                    ("Review Queue", f"/runs/{run_id}/review"),
                    ("Artifact Center", f"/runs/{run_id}/artifacts/view"),
                ],
            ),
        )
    )


@router.get("/runs/{run_id}/review", response_class=HTMLResponse)
def review_queue_page(run_id: str, request: Request):
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>{spot} Review Queue</title>
  <style>
    :root {
      --bg: #f4efe3;
      --panel: #fffaf2;
      --line: #d8cbb7;
      --text: #201d18;
      --muted: #6b655e;
      --accent: #0f766e;
      --warn: #b45309;
      --danger: #b91c1c;
      --ok: #166534;
    }
    * { box-sizing: border-box; }
    body { margin:0; background:linear-gradient(180deg,#f8f3ea 0%,var(--bg) 100%); color:var(--text); font-family:Georgia,"Palatino Linotype",serif; }
    __PAGE_CHROME_CSS__
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; margin-bottom:18px; }
    .head { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:14px; }
    h1,h2 { margin:0; }
    h1 { font-size: 34px; }
    .muted { color:var(--muted); line-height:1.45; }
    .session-panel { display:grid; gap:14px; }
    .session-grid { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:10px; }
    .session-field { display:grid; gap:6px; }
    .session-field label, .micro-label, .section-label {
      color:var(--muted); text-transform:uppercase; font-size:12px; letter-spacing:.08em; font-family:"Avenir Next","Segoe UI",sans-serif;
    }
    .filters { display:grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap:10px; }
    input[type="text"], select, textarea { width:100%; border-radius:12px; border:1px solid var(--line); padding:10px 12px; background:white; font-family:"Avenir Next","Segoe UI",sans-serif; font-size:14px; }
    button, a.link-btn {
      border:0; border-radius:999px; padding:10px 14px; cursor:pointer; text-decoration:none;
      font-family:"Avenir Next","Segoe UI",sans-serif; font-size:14px;
    }
    button.primary { background:var(--accent); color:white; }
    button.secondary, a.link-btn { background:#e8decf; color:var(--text); }
    .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    .stats { display:grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap:12px; margin-top:12px; }
    .stat { background:white; border:1px solid var(--line); border-radius:14px; padding:12px; }
    .label { color:var(--muted); text-transform:uppercase; font-size:12px; letter-spacing:.08em; margin-bottom:8px; font-family:"Avenir Next","Segoe UI",sans-serif; }
    .value { font-size:22px; }
    .list { display:grid; gap:12px; }
    .row-card { background:white; border:1px solid var(--line); border-radius:14px; padding:14px; display:grid; gap:10px; }
    .row-head { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
    .pill { display:inline-flex; border-radius:999px; padding:5px 10px; border:1px solid var(--line); font-size:12px; font-weight:700; font-family:"Avenir Next","Segoe UI",sans-serif; }
    .pill.ok { color:var(--ok); } .pill.warn { color:var(--warn); } .pill.danger { color:var(--danger); }
    .grid { display:grid; grid-template-columns: 1.15fr .85fr; gap:14px; }
    .content-stack, .review-form, .evidence-stack { display:grid; gap:10px; }
    .content-box, .evidence-box {
      background:#fbf7f0; border:1px solid var(--line); border-radius:14px; padding:12px;
    }
    .row-text, .explanation-text {
      white-space:pre-wrap; line-height:1.6; font-size:15px;
    }
    .chip-row { display:flex; flex-wrap:wrap; gap:8px; }
    .chip {
      display:inline-flex; align-items:center; border-radius:999px; padding:6px 10px;
      background:white; border:1px solid var(--line); font-family:"Avenir Next","Segoe UI",sans-serif; font-size:12px;
    }
    .review-meta { display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:10px; }
    .meta-card {
      background:#fbf7f0; border:1px solid var(--line); border-radius:14px; padding:12px;
    }
    .review-form { display:grid; gap:8px; }
    .message { white-space:pre-wrap; padding:10px 12px; border-radius:12px; background:#f7f1e6; border:1px solid var(--line); font-size:13px; line-height:1.45; }
    .message.error { border-color:rgba(185,28,28,0.24); background:rgba(185,28,28,0.08); color:var(--danger); }
    .message.ok { border-color:rgba(22,101,52,0.24); background:rgba(22,101,52,0.08); color:var(--ok); }
    @media (max-width: 960px) { .filters,.stats,.grid,.session-grid,.review-meta { grid-template-columns:1fr; } .head { flex-direction:column; } h1 { font-size:28px; } }
  </style>
</head>
<body>
  <div class="shell">
    __PAGE_TOPBAR__
    <section class="panel">
      <div class="head">
        <div>
          <h2>Reviewer Session</h2>
          <div class="muted">This page can load before authentication. Sign in here to unlock the flagged-row queue and save reviewer decisions.</div>
        </div>
      </div>
      <div class="session-panel">
        <div class="message" id="authMessage">Checking current reviewer session.</div>
        <div class="session-grid">
          <div class="session-field">
            <label for="actorNameInput">Actor</label>
            <input type="text" id="actorNameInput" value="local-reviewer" />
          </div>
          <div class="session-field">
            <label for="roleInput">Role</label>
            <select id="roleInput">
              <option value="reviewer">reviewer</option>
              <option value="admin">admin</option>
              <option value="acceptance_lead">acceptance_lead</option>
              <option value="operator">operator</option>
            </select>
          </div>
          <div class="session-field">
            <label for="accessCodeInput">Access Code</label>
            <input type="text" id="accessCodeInput" value="spot-local" />
          </div>
        </div>
        <div class="actions">
          <button class="secondary" type="button" onclick="login()">Login</button>
          <button class="secondary" type="button" onclick="logout()">Logout</button>
        </div>
      </div>
    </section>
    <section class="panel">
      <div class="head">
        <div>
          <div class="muted"><a href="/runs/__RUN_ID__/view">Back to run detail</a> · <a href="/app">Dashboard</a></div>
          <h1>Review Queue: __RUN_ID__</h1>
          <p class="muted">Filter and triage `Review Required` rows without leaving the browser surface.</p>
        </div>
        <div class="actions">
          <button class="secondary" type="button" onclick="loadQueue()">Refresh Queue</button>
        </div>
      </div>
      <div class="filters">
        <select id="filterReviewState">
          <option value="all">all states</option>
          <option value="pending">pending</option>
          <option value="reviewed">reviewed</option>
          <option value="escalated">escalated</option>
        </select>
        <select id="filterDecision">
          <option value="all">all decisions</option>
          <option value="confirm">confirm</option>
          <option value="override">override</option>
          <option value="escalate">escalate</option>
        </select>
        <select id="sortBy">
          <option value="row_index">row index</option>
          <option value="confidence">confidence</option>
          <option value="category">category</option>
          <option value="review_state">review state</option>
        </select>
        <select id="sortOrder">
          <option value="asc">ascending</option>
          <option value="desc">descending</option>
        </select>
      </div>
      <div class="actions">
        <button class="primary" type="button" onclick="loadQueue()">Apply Filters</button>
      </div>
      <div class="stats">
        <div class="stat"><div class="label">Queue Rows</div><div class="value" id="statRows">0</div></div>
        <div class="stat"><div class="label">Pending</div><div class="value" id="statPending">0</div></div>
        <div class="stat"><div class="label">Reviewed</div><div class="value" id="statReviewed">0</div></div>
        <div class="stat"><div class="label">Escalated</div><div class="value" id="statEscalated">0</div></div>
      </div>
      <div class="message" id="queueMessage">Loading queue.</div>
    </section>

    <section class="panel">
      <div class="head">
        <div>
          <h2>Flagged Rows</h2>
          <div class="muted">Each row exposes quick triage controls and a direct path back to the dedicated run-detail page.</div>
        </div>
      </div>
      <div class="list" id="queueList"></div>
    </section>
  </div>

  <script>
    const runId = '__RUN_ID__';

    function escapeHtml(v) {
      return String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',\"'\":'&#39;'}[ch]));
    }

    function setMessage(id, text, tone='') {
      const node = document.getElementById(id);
      node.className = tone ? `message ${tone}` : 'message';
      node.textContent = text;
    }

    function pillClass(status) {
      const txt = String(status || '').toUpperCase();
      if (txt.includes('REVIEWED') || txt.includes('CONFIRM')) return 'pill ok';
      if (txt.includes('ESCALAT')) return 'pill danger';
      return 'pill warn';
    }

    function chips(items, emptyLabel='none') {
      const values = Array.isArray(items) ? items.filter(Boolean) : [];
      if (!values.length) return `<span class="chip">${escapeHtml(emptyLabel)}</span>`;
      return values.map(value => `<span class="chip">${escapeHtml(value)}</span>`).join('');
    }

    function summarizeExplanation(text) {
      const value = String(text || '').trim();
      if (!value) return 'No explanation recorded for this row.';
      return value;
    }

    async function loadSession() {
      const res = await fetch('/auth/session');
      const data = await res.json();
      const session = data.session || {};
      if (data.authenticated) {
        setMessage('authMessage', `Authenticated as ${session.actor_name || 'unknown'} with role ${session.role || 'unknown'}.`, 'ok');
      } else {
        setMessage('authMessage', `No active reviewer session. Login is required to view flagged rows.`, 'error');
      }
      return data;
    }

    async function login() {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actor_name: document.getElementById('actorNameInput').value,
          role: document.getElementById('roleInput').value,
          access_code: document.getElementById('accessCodeInput').value
        })
      });
      const data = await res.json();
      setMessage('authMessage', res.ok ? `Login succeeded for ${document.getElementById('actorNameInput').value}.` : JSON.stringify(data, null, 2), res.ok ? 'ok' : 'error');
      await loadSession();
      if (res.ok) await loadQueue();
    }

    async function logout() {
      await fetch('/auth/logout', { method: 'POST' });
      setMessage('authMessage', 'Reviewer session closed.', 'ok');
      await loadSession();
      renderRows([]);
      setMessage('queueMessage', 'Login required to load the review queue.', 'error');
    }

    function currentFilters() {
      return new URLSearchParams({
        review_state: document.getElementById('filterReviewState').value,
        review_decision: document.getElementById('filterDecision').value,
        sort_by: document.getElementById('sortBy').value,
        sort_order: document.getElementById('sortOrder').value
      });
    }

    async function loadQueue() {
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/review-rows?' + currentFilters().toString());
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 401) {
          renderRows([]);
          document.getElementById('statRows').textContent = '0';
          document.getElementById('statPending').textContent = '0';
          document.getElementById('statReviewed').textContent = '0';
          document.getElementById('statEscalated').textContent = '0';
          setMessage('queueMessage', 'Authentication required. Login above, then refresh the queue.', 'error');
          await loadSession();
          return;
        }
        setMessage('queueMessage', JSON.stringify(data, null, 2), 'error');
        return;
      }
      const rows = data.rows || [];
      setMessage('queueMessage', `${rows.length} flagged row(s) loaded for run ${runId}. Current run state: ${data.state || '-'}.`, rows.length ? 'ok' : '');
      document.getElementById('statRows').textContent = String(rows.length);
      document.getElementById('statPending').textContent = String(rows.filter(r => (r.review_state || 'pending') === 'pending').length);
      document.getElementById('statReviewed').textContent = String(rows.filter(r => r.review_state === 'reviewed').length);
      document.getElementById('statEscalated').textContent = String(rows.filter(r => r.review_state === 'escalated').length);
      renderRows(rows);
    }

    function renderRows(rows) {
      const root = document.getElementById('queueList');
      if (!rows.length) {
        root.innerHTML = '<div class="message">No review rows match the current filters.</div>';
        return;
      }
      root.innerHTML = rows.map(row => `
        <div class="row-card">
          <div class="row-head">
            <div>
              <strong>Row ${escapeHtml(row.row_index)}</strong>
              <div class="muted">Item ${escapeHtml(row.item_number || '-')} · ${escapeHtml(row.assigned_category || '-')}</div>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
              <span class="${pillClass(row.review_state || 'pending')}">${escapeHtml(row.review_state || 'pending')}</span>
              <span class="pill warn">confidence ${escapeHtml(row.confidence_score ?? '-')}</span>
            </div>
          </div>
          <div class="grid">
            <div class="content-stack">
              <div class="content-box">
                <div class="section-label">Source Text</div>
                <div class="row-text">${escapeHtml(row.post_text || '') || '<em>No source text available.</em>'}</div>
              </div>
              <div class="content-box">
                <div class="section-label">Classifier Explanation</div>
                <div class="explanation-text">${escapeHtml(summarizeExplanation(row.explanation))}</div>
              </div>
              <div class="evidence-stack">
                <div class="evidence-box">
                  <div class="section-label">Flags</div>
                  <div class="chip-row">${chips(row.flags, 'no flags')}</div>
                </div>
                <div class="evidence-box">
                  <div class="section-label">Soft Signals</div>
                  <div class="chip-row">${chips(row.soft_signal_flags, 'no soft signals')}</div>
                  <div class="muted" style="margin-top:8px;">Soft score: ${escapeHtml(row.soft_signal_score ?? '-')}</div>
                </div>
                <div class="evidence-box">
                  <div class="section-label">Fallback Events</div>
                  <div class="chip-row">${chips(row.fallback_events, 'no fallbacks')}</div>
                </div>
              </div>
            </div>
            <div class="review-form">
              <div class="review-meta">
                <div class="meta-card">
                  <div class="micro-label">Review Decision</div>
                  <div>${escapeHtml(row.review_decision || 'no decision')}</div>
                </div>
                <div class="meta-card">
                  <div class="micro-label">Assigned Category</div>
                  <div>${escapeHtml(row.assigned_category || '-')}</div>
                </div>
              </div>
              <select id="reviewState-${row.row_index}">
                <option value="pending" ${(row.review_state || 'pending') === 'pending' ? 'selected' : ''}>pending</option>
                <option value="reviewed" ${(row.review_state || '') === 'reviewed' ? 'selected' : ''}>reviewed</option>
                <option value="escalated" ${(row.review_state || '') === 'escalated' ? 'selected' : ''}>escalated</option>
              </select>
              <select id="reviewDecision-${row.row_index}">
                <option value="">no decision</option>
                <option value="confirm" ${(row.review_decision || '') === 'confirm' ? 'selected' : ''}>confirm</option>
                <option value="override" ${(row.review_decision || '') === 'override' ? 'selected' : ''}>override</option>
                <option value="escalate" ${(row.review_decision || '') === 'escalate' ? 'selected' : ''}>escalate</option>
              </select>
              <textarea id="reviewNote-${row.row_index}" rows="3" placeholder="Reviewer note">${escapeHtml(row.reviewer_note || '')}</textarea>
              <div class="actions">
                <button class="primary" type="button" onclick="saveRow(${row.row_index})">Save Triage</button>
                <a class="link-btn" href="/runs/${encodeURIComponent(runId)}/review-rows/${encodeURIComponent(row.row_index)}/view">Open Row Inspector</a>
              </div>
            </div>
          </div>
        </div>
      `).join('');
    }

    async function saveRow(rowIndex) {
      const payload = {
        review_state: document.getElementById('reviewState-' + rowIndex).value,
        review_decision: document.getElementById('reviewDecision-' + rowIndex).value || null,
        reviewer_note: document.getElementById('reviewNote-' + rowIndex).value,
        actor: 'browser-reviewer'
      };
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/review-rows/' + encodeURIComponent(rowIndex), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      setMessage('queueMessage', res.ok ? `Saved review state for row ${rowIndex}.` : JSON.stringify(data, null, 2), res.ok ? 'ok' : 'error');
      await loadQueue();
    }

    loadSession();
    loadQueue();
    setInterval(loadQueue, 5000);
    setInterval(loadSession, 15000);
  </script>
</body>
</html>"""
    return (
        page.replace("__RUN_ID__", run_id)
        .replace("__PAGE_CHROME_CSS__", _operator_page_chrome_css(max_width=1240))
        .replace(
            "__PAGE_TOPBAR__",
            _operator_page_topbar(
                title="{spot} Review Workspace",
                subtitle="Filter, triage, and route flagged rows without leaving the local browser surface.",
                links=[
                    ("Dashboard", "/app"),
                    ("Run Detail", f"/runs/{run_id}/view"),
                    ("Artifact Center", f"/runs/{run_id}/artifacts/view"),
                ],
            ),
        )
    )


@router.get("/runs/{run_id}/review-rows/{row_index}/view", response_class=HTMLResponse)
def row_inspector_page(run_id: str, row_index: int, request: Request):
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>{spot} Row Inspector</title>
  <style>
    :root {
      --bg: #f4efe4;
      --panel: #fffaf2;
      --line: #d8cbb7;
      --text: #201d18;
      --muted: #6a655d;
      --accent: #0f766e;
      --warn: #b45309;
      --danger: #b91c1c;
      --ok: #166534;
    }
    * { box-sizing: border-box; }
    body { margin:0; background:linear-gradient(180deg,#f8f2e9 0%,var(--bg) 100%); color:var(--text); font-family:Georgia,"Palatino Linotype",serif; }
    __PAGE_CHROME_CSS__
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; margin-bottom:18px; }
    .head { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:14px; }
    h1,h2,h3 { margin:0; }
    h1 { font-size: 34px; }
    .muted { color:var(--muted); line-height:1.45; }
    .session-grid { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:10px; }
    .session-field { display:grid; gap:6px; }
    .session-field label, .section-label {
      color:var(--muted); text-transform:uppercase; font-size:12px; letter-spacing:.08em; font-family:"Avenir Next","Segoe UI",sans-serif;
    }
    .grid { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px; }
    .box { background:white; border:1px solid var(--line); border-radius:14px; padding:12px; }
    .label { color:var(--muted); text-transform:uppercase; font-size:12px; letter-spacing:.08em; margin-bottom:8px; font-family:"Avenir Next","Segoe UI",sans-serif; }
    .value { font-size:18px; }
    .pill { display:inline-flex; border-radius:999px; padding:5px 10px; border:1px solid var(--line); font-size:12px; font-weight:700; font-family:"Avenir Next","Segoe UI",sans-serif; }
    .pill.ok { color:var(--ok); } .pill.warn { color:var(--warn); } .pill.danger { color:var(--danger); }
    .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    button, a.link-btn, input[type="text"], select, textarea {
      border:0; border-radius:999px; padding:10px 14px; cursor:pointer; text-decoration:none;
      font-family:"Avenir Next","Segoe UI",sans-serif; font-size:14px;
    }
    button.primary { background:var(--accent); color:white; }
    button.secondary, a.link-btn { background:#e8decf; color:var(--text); }
    select, textarea { border-radius:12px; border:1px solid var(--line); background:white; padding:10px 12px; width:100%; }
    textarea { min-height: 120px; }
    .message { white-space:pre-wrap; padding:10px 12px; border-radius:12px; background:#f7f1e6; border:1px solid var(--line); font-size:13px; line-height:1.45; }
    .message.error { border-color:rgba(185,28,28,0.24); background:rgba(185,28,28,0.08); color:var(--danger); }
    .message.ok { border-color:rgba(22,101,52,0.24); background:rgba(22,101,52,0.08); color:var(--ok); }
    .stack { display:grid; gap:12px; }
    .body-copy { white-space:pre-wrap; line-height:1.65; font-size:15px; }
    .chip-row { display:flex; flex-wrap:wrap; gap:8px; }
    .chip {
      display:inline-flex; align-items:center; border-radius:999px; padding:6px 10px;
      background:#fbf6ee; border:1px solid var(--line); font-family:"Avenir Next","Segoe UI",sans-serif; font-size:12px;
    }
    details.debug {
      border:1px solid var(--line); border-radius:14px; background:#fbf6ee; overflow:hidden;
    }
    details.debug summary {
      cursor:pointer; list-style:none; padding:12px 14px; font-family:"Avenir Next","Segoe UI",sans-serif; font-size:13px; color:var(--muted);
    }
    details.debug summary::-webkit-details-marker { display:none; }
    pre {
      margin: 0; padding: 12px; border-top:1px solid var(--line);
      overflow:auto; font-size:12px; line-height:1.45; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    @media (max-width: 920px) { .grid,.session-grid { grid-template-columns:1fr; } .head { flex-direction:column; } h1 { font-size:28px; } }
  </style>
</head>
<body>
  <div class="shell">
    __PAGE_TOPBAR__
    <section class="panel">
      <div class="head">
        <div>
          <h2>Reviewer Session</h2>
          <div class="muted">Use the same local sign-in here if you opened the row inspector directly.</div>
        </div>
      </div>
      <div class="message" id="authMessage">Checking current reviewer session.</div>
      <div class="session-grid">
        <div class="session-field">
          <label for="actorNameInput">Actor</label>
          <input type="text" id="actorNameInput" value="local-reviewer" />
        </div>
        <div class="session-field">
          <label for="roleInput">Role</label>
          <select id="roleInput">
            <option value="reviewer">reviewer</option>
            <option value="admin">admin</option>
            <option value="acceptance_lead">acceptance_lead</option>
            <option value="operator">operator</option>
          </select>
        </div>
        <div class="session-field">
          <label for="accessCodeInput">Access Code</label>
          <input type="text" id="accessCodeInput" value="spot-local" />
        </div>
      </div>
      <div class="actions">
        <button class="secondary" type="button" onclick="login()">Login</button>
        <button class="secondary" type="button" onclick="logout()">Logout</button>
      </div>
    </section>
    <section class="panel">
      <div class="head">
        <div>
          <div class="muted"><a href="/runs/__RUN_ID__/review">Back to review queue</a> · <a href="/runs/__RUN_ID__/view">Run detail</a></div>
          <h1>Row Inspector: __RUN_ID__ / row __ROW_INDEX__</h1>
          <p class="muted">Focused evidence view for one flagged row, including explanation, flags, fallback events, disagreement evidence, and persistent review controls.</p>
        </div>
        <div class="pill warn" id="statePill">Loading</div>
      </div>
      <div class="message" id="inspectorMessage">Loading row detail.</div>
    </section>

    <section class="panel">
      <div class="grid">
        <div class="box"><div class="label">Assigned Category</div><div class="value" id="assignedCategory">-</div></div>
        <div class="box"><div class="label">Confidence</div><div class="value" id="confidenceValue">-</div></div>
        <div class="box"><div class="label">Review State</div><div class="value" id="reviewStateValue">-</div></div>
        <div class="box"><div class="label">Review Decision</div><div class="value" id="reviewDecisionValue">-</div></div>
      </div>
    </section>

    <section class="panel">
      <div class="head"><h2>Source Row</h2></div>
      <div class="box">
        <div class="label">Post Text</div>
        <div class="body-copy" id="rowPre"></div>
      </div>
    </section>

    <section class="panel">
      <div class="head"><h2>Evidence</h2></div>
      <div class="stack">
        <div class="box">
          <div class="label">Explanation</div>
          <div class="body-copy" id="explanationPre"></div>
        </div>
        <div class="box">
          <div class="label">Flags And Fallback Events</div>
          <div id="flagsPre"></div>
        </div>
        <div class="box">
          <div class="label">Disagreement Evidence</div>
          <div id="disagreementPre" class="body-copy muted">No disagreement evidence loaded yet.</div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="head"><h2>Row Debug Payload</h2></div>
      <details class="debug">
        <summary>Open raw row payload</summary>
        <pre id="debugRowPre">{}</pre>
      </details>
    </section>

    <section class="panel">
      <div class="head"><h2>Reviewer Controls</h2></div>
      <div class="stack">
        <select id="reviewStateInput">
          <option value="pending">pending</option>
          <option value="reviewed">reviewed</option>
          <option value="escalated">escalated</option>
        </select>
        <select id="reviewDecisionInput">
          <option value="">no decision</option>
          <option value="confirm">confirm</option>
          <option value="override">override</option>
          <option value="escalate">escalate</option>
        </select>
        <textarea id="reviewNoteInput" placeholder="Reviewer note"></textarea>
        <div class="actions">
          <button class="primary" type="button" onclick="saveInspector()">Save Inspector Review</button>
          <a class="link-btn" href="/runs/__RUN_ID__/review">Return to Queue</a>
        </div>
      </div>
    </section>
  </div>

  <script>
    const runId = '__RUN_ID__';
    const rowIndex = '__ROW_INDEX__';

    function escapeHtml(v) {
      return String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',\"'\":'&#39;'}[ch]));
    }

    function pillClass(status) {
      const txt = String(status || '').toUpperCase();
      if (txt.includes('REVIEWED') || txt.includes('CONFIRM')) return 'pill ok';
      if (txt.includes('ESCALAT')) return 'pill danger';
      return 'pill warn';
    }

    function setMessage(id, text, tone='') {
      const node = document.getElementById(id);
      node.className = tone ? `message ${tone}` : 'message';
      node.textContent = text;
    }

    function chips(items, emptyLabel='none') {
      const values = Array.isArray(items) ? items.filter(Boolean) : [];
      if (!values.length) return `<span class="chip">${escapeHtml(emptyLabel)}</span>`;
      return values.map(value => `<span class="chip">${escapeHtml(String(value))}</span>`).join('');
    }

    async function loadSession() {
      const res = await fetch('/auth/session');
      const data = await res.json();
      const session = data.session || {};
      if (data.authenticated) {
        setMessage('authMessage', `Authenticated as ${session.actor_name || 'unknown'} with role ${session.role || 'unknown'}.`, 'ok');
      } else {
        setMessage('authMessage', 'No active reviewer session. Login is required to load this row.', 'error');
      }
      return data;
    }

    async function login() {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actor_name: document.getElementById('actorNameInput').value,
          role: document.getElementById('roleInput').value,
          access_code: document.getElementById('accessCodeInput').value
        })
      });
      const data = await res.json();
      setMessage('authMessage', res.ok ? `Login succeeded for ${document.getElementById('actorNameInput').value}.` : JSON.stringify(data, null, 2), res.ok ? 'ok' : 'error');
      await loadSession();
      if (res.ok) await loadInspector();
    }

    async function logout() {
      await fetch('/auth/logout', { method: 'POST' });
      setMessage('authMessage', 'Reviewer session closed.', 'ok');
      await loadSession();
      setMessage('inspectorMessage', 'Login required to load row detail.', 'error');
    }

    async function loadInspector() {
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/review-rows/' + encodeURIComponent(rowIndex));
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 401) {
          setMessage('inspectorMessage', 'Authentication required. Login above, then reload this row.', 'error');
          await loadSession();
          return;
        }
        setMessage('inspectorMessage', JSON.stringify(data, null, 2), 'error');
        return;
      }
      document.getElementById('statePill').className = pillClass((data.review_controls || {}).review_state || 'pending');
      document.getElementById('statePill').textContent = (data.review_controls || {}).review_state || 'pending';
      document.getElementById('assignedCategory').textContent = ((data.row || {}).assigned_category) || '-';
      document.getElementById('confidenceValue').textContent = String(((data.row || {}).confidence_score) ?? '-');
      document.getElementById('reviewStateValue').textContent = (data.review_controls || {}).review_state || 'pending';
      document.getElementById('reviewDecisionValue').textContent = (data.review_controls || {}).review_decision || '-';
      document.getElementById('rowPre').textContent = (data.row || {}).post_text || '';
      document.getElementById('explanationPre').textContent = (data.evidence || {}).explanation || 'No explanation recorded for this row.';
      document.getElementById('flagsPre').innerHTML = `
        <div class="section-label">Flags</div>
        <div class="chip-row">${chips((data.evidence || {}).flags, 'no flags')}</div>
        <div class="section-label" style="margin-top:12px;">Fallback Events</div>
        <div class="chip-row">${chips((data.evidence || {}).fallback_events, 'no fallbacks')}</div>
        <div class="section-label" style="margin-top:12px;">Soft Signals</div>
        <div class="chip-row">${chips((data.evidence || {}).soft_signal_flags, 'no soft signals')}</div>
        <div class="muted" style="margin-top:10px;">Soft score: ${String((data.evidence || {}).soft_signal_score ?? '-')}</div>
        <div class="muted">Soft evidence: ${((data.evidence || {}).soft_signal_evidence || []).join(' | ') || 'none'}</div>
      `;
      const disagreement = (data.evidence || {}).disagreement;
      document.getElementById('disagreementPre').innerHTML = disagreement
        ? `<details class="debug" open><summary>Disagreement evidence</summary><pre>${JSON.stringify(disagreement, null, 2)}</pre></details>`
        : '<div class="muted">No disagreement report entry exists for this row.</div>';
      document.getElementById('debugRowPre').textContent = JSON.stringify(data.row || {}, null, 2);
      document.getElementById('reviewStateInput').value = (data.review_controls || {}).review_state || 'pending';
      document.getElementById('reviewDecisionInput').value = (data.review_controls || {}).review_decision || '';
      document.getElementById('reviewNoteInput').value = (data.review_controls || {}).reviewer_note || '';
      setMessage('inspectorMessage', `Run ${data.run_id} · row ${data.row_index} · run state ${data.run_state} · review state ${(data.review_controls || {}).review_state || 'pending'}.`, 'ok');
    }

    async function saveInspector() {
      const payload = {
        review_state: document.getElementById('reviewStateInput').value,
        review_decision: document.getElementById('reviewDecisionInput').value || null,
        reviewer_note: document.getElementById('reviewNoteInput').value,
        actor: 'browser-reviewer'
      };
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/review-rows/' + encodeURIComponent(rowIndex), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      setMessage('inspectorMessage', res.ok ? `Saved review state for row ${rowIndex}.` : JSON.stringify(data, null, 2), res.ok ? 'ok' : 'error');
      await loadInspector();
    }

    loadSession();
    loadInspector();
    setInterval(loadInspector, 5000);
    setInterval(loadSession, 15000);
  </script>
</body>
</html>"""
    return (
        page.replace("__RUN_ID__", run_id)
        .replace("__ROW_INDEX__", str(row_index))
        .replace("__PAGE_CHROME_CSS__", _operator_page_chrome_css(max_width=1120))
        .replace(
            "__PAGE_TOPBAR__",
            _operator_page_topbar(
                title="{spot} Evidence Workspace",
                subtitle="Focused row inspection for reviewer evidence, fallback signals, and final triage decisions.",
                links=[
                    ("Dashboard", "/app"),
                    ("Run Detail", f"/runs/{run_id}/view"),
                    ("Review Queue", f"/runs/{run_id}/review"),
                ],
            ),
        )
    )


@router.get("/runs/{run_id}/artifacts/view", response_class=HTMLResponse)
def artifact_center_page(run_id: str, request: Request):
    require_permission(request, "view")
    page = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>{spot} Artifact Center</title>
  <style>
    :root {
      --bg: #f4efe4;
      --panel: #fffaf2;
      --line: #d8cbb7;
      --text: #201d18;
      --muted: #6a655d;
      --accent: #0f766e;
      --warn: #b45309;
      --ok: #166534;
    }
    * { box-sizing: border-box; }
    body { margin:0; background:linear-gradient(180deg,#f8f2e9 0%,var(--bg) 100%); color:var(--text); font-family:Georgia,"Palatino Linotype",serif; }
    __PAGE_CHROME_CSS__
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; margin-bottom:18px; }
    .head { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:14px; }
    h1,h2 { margin:0; }
    h1 { font-size: 34px; }
    .muted { color:var(--muted); line-height:1.45; }
    .stats { display:grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap:12px; margin-top:12px; }
    .stat { background:white; border:1px solid var(--line); border-radius:14px; padding:12px; }
    .label { color:var(--muted); text-transform:uppercase; font-size:12px; letter-spacing:.08em; margin-bottom:8px; font-family:"Avenir Next","Segoe UI",sans-serif; }
    .value { font-size:22px; }
    .list { display:grid; gap:12px; }
    .card { background:white; border:1px solid var(--line); border-radius:14px; padding:14px; display:grid; gap:10px; }
    .card-head { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
    .pill { display:inline-flex; border-radius:999px; padding:5px 10px; border:1px solid var(--line); font-size:12px; font-weight:700; font-family:"Avenir Next","Segoe UI",sans-serif; color:var(--warn); }
    .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    a.link-btn, button {
      border:0; border-radius:999px; padding:10px 14px; cursor:pointer; text-decoration:none;
      font-family:"Avenir Next","Segoe UI",sans-serif; font-size:14px;
    }
    a.link-btn, button.secondary { background:#e8decf; color:var(--text); }
    button.primary { background:var(--accent); color:white; }
    .message { white-space:pre-wrap; padding:10px 12px; border-radius:12px; background:#f7f1e6; border:1px solid var(--line); font-size:13px; line-height:1.45; }
    @media (max-width: 920px) { .stats { grid-template-columns:1fr; } .head { flex-direction:column; } h1 { font-size:28px; } }
  </style>
</head>
<body>
  <div class="shell">
    __PAGE_TOPBAR__
    <section class="panel">
      <div class="head">
        <div>
          <div class="muted"><a href="/runs/__RUN_ID__/view">Back to run detail</a> · <a href="/app">Dashboard</a></div>
          <h1>Artifact Center: __RUN_ID__</h1>
          <p class="muted">Download governed output and audit files for a completed or in-progress local run.</p>
        </div>
        <div class="actions">
          <button class="secondary" type="button" onclick="loadArtifacts()">Refresh Artifact List</button>
        </div>
      </div>
      <div class="stats">
        <div class="stat"><div class="label">Run State</div><div class="value" id="runState">-</div></div>
        <div class="stat"><div class="label">Artifacts</div><div class="value" id="artifactCount">0</div></div>
        <div class="stat"><div class="label">Sign-off</div><div class="value" id="signoffState">-</div></div>
      </div>
      <div class="message" id="artifactMessage">Loading artifacts.</div>
    </section>

    <section class="panel">
      <div class="head">
        <div>
          <h2>Downloadable Files</h2>
          <div class="muted">Each artifact is linked through the local backend so the operator does not need direct filesystem access.</div>
        </div>
      </div>
      <div class="list" id="artifactList"></div>
    </section>
  </div>

  <script>
    const runId = '__RUN_ID__';

    function escapeHtml(v) {
      return String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',\"'\":'&#39;'}[ch]));
    }

    async function loadArtifacts() {
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/artifacts');
      const data = await res.json();
      if (!res.ok) {
        document.getElementById('artifactMessage').textContent = JSON.stringify(data, null, 2);
        return;
      }
      document.getElementById('runState').textContent = data.state || '-';
      document.getElementById('artifactCount').textContent = String((data.artifacts || []).length);
      document.getElementById('signoffState').textContent = data.signoff ? data.signoff.decision : 'not signed';
      document.getElementById('artifactMessage').textContent = `run_id=${data.run_id}\nstate=${data.state || '-'}\nsignoff=${data.signoff ? data.signoff.decision : 'not signed'}`;
      renderArtifacts(data.artifacts || []);
    }

    function renderArtifacts(items) {
      const root = document.getElementById('artifactList');
      if (!items.length) {
        root.innerHTML = '<div class="message">No artifacts available yet.</div>';
        return;
      }
      root.innerHTML = items.map(item => `
        <div class="card">
          <div class="card-head">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <div class="muted">${escapeHtml(item.purpose || '')}</div>
            </div>
            <span class="pill">${escapeHtml(item.bytes)} bytes</span>
          </div>
          <div class="muted">${escapeHtml(item.path)}</div>
          <div class="actions">
            <a class="link-btn" href="${escapeHtml(item.download_path)}">Download</a>
          </div>
        </div>
      `).join('');
    }

    loadArtifacts();
    setInterval(loadArtifacts, 5000);
  </script>
</body>
</html>"""
    return (
        page.replace("__RUN_ID__", run_id)
        .replace("__PAGE_CHROME_CSS__", _operator_page_chrome_css(max_width=1120))
        .replace(
            "__PAGE_TOPBAR__",
            _operator_page_topbar(
                title="{spot} Artifact Workspace",
                subtitle="Download governed outputs and audit files from the same local operator environment.",
                links=[
                    ("Dashboard", "/app"),
                    ("Run Detail", f"/runs/{run_id}/view"),
                    ("Review Queue", f"/runs/{run_id}/review"),
                ],
            ),
        )
    )
