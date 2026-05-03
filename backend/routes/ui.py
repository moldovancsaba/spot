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
  <title>{spot} Eval Monitor</title>
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
  <h2>{spot} Eval Monitor</h2>
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
  <title>{spot} Classify Monitor</title>
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
  <h2>{spot} Classify Monitor</h2>
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
      max-width: 1360px;
      margin: 0 auto;
      padding: 28px 20px 40px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 18px;
      padding: 14px 18px;
      border: 1px solid var(--line);
      background: rgba(255,250,241,0.82);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }
    .brand-mark {
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--accent);
      font-weight: 700;
      margin-bottom: 4px;
    }
    .brand-copy {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      max-width: 42rem;
    }
    .quick-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .nav-chip {
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
    }
    .hero {
      display: grid;
      grid-template-columns: 1.5fr 1fr;
      gap: 20px;
      align-items: stretch;
      margin-bottom: 20px;
    }
    .hero-card, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }
    .hero-card {
      padding: 24px;
      position: relative;
      overflow: hidden;
    }
    .hero-card::after {
      content: "";
      position: absolute;
      right: -30px;
      top: -30px;
      width: 180px;
      height: 180px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(15,118,110,0.16), transparent 70%);
      pointer-events: none;
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 12px;
      color: var(--accent);
      margin-bottom: 10px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-weight: 700;
    }
    h1, h2, h3 { margin: 0; }
    h1 {
      font-size: 36px;
      line-height: 1.05;
      margin-bottom: 12px;
    }
    .lede {
      color: var(--muted);
      font-size: 17px;
      line-height: 1.5;
      max-width: 52rem;
    }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      padding: 18px;
    }
    .status-tile {
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
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
      font-size: 28px;
      font-weight: 700;
    }
    .status-sub {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }
    .layout {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 20px;
    }
    .stack {
      display: grid;
      gap: 20px;
    }
    .panel {
      padding: 18px;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 14px;
      margin-bottom: 16px;
    }
    .panel-title {
      font-size: 22px;
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
    .upload-form {
      display: grid;
      gap: 12px;
    }
    .upload-meta {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    input[type="text"], select, input[type="file"] {
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: white;
      padding: 11px 12px;
      font-size: 14px;
      color: var(--text);
    }
    .message {
      border-radius: 14px;
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
      border-radius: 16px;
      padding: 14px;
      display: grid;
      gap: 8px;
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
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
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
    @media (max-width: 980px) {
      .hero, .layout, .upload-meta, .detail-grid {
        grid-template-columns: 1fr;
      }
      .topbar {
        display: grid;
      }
      h1 { font-size: 30px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="topbar">
      <div>
        <div class="brand-mark">{spot} Browser Surface</div>
        <div class="brand-copy">Local `.xlsx` intake, deterministic runs, reviewer triage, and audit retrieval in one operator-focused browser workspace.</div>
      </div>
      <div class="quick-nav">
        <a class="nav-chip" href="/classify-monitor" target="_blank">Classify Monitor</a>
        <a class="nav-chip" href="/agent-eval" target="_blank">Eval Monitor</a>
      </div>
    </section>
    <section class="hero">
      <div class="hero-card">
        <div class="eyebrow">Local Operator Surface</div>
        <h1>{spot} Browser Operations Dashboard</h1>
        <p class="lede">
          Local-first upload, run tracking, review-state visibility, and audit-oriented operator actions for the current `.xlsx` workflow.
        </p>
      </div>
      <div class="hero-card">
        <div class="status-grid">
          <div class="status-tile">
            <div class="status-label">Runs</div>
            <div class="status-value" id="runCount">0</div>
            <div class="status-sub" id="runHealth">No run selected</div>
          </div>
          <div class="status-tile">
            <div class="status-label">Accepted Uploads</div>
            <div class="status-value" id="uploadCount">0</div>
            <div class="status-sub">Guardrail-validated workbooks</div>
          </div>
          <div class="status-tile">
            <div class="status-label">Active Run</div>
            <div class="status-value" id="activeRunState">Idle</div>
            <div class="status-sub" id="activeRunId">No active run</div>
          </div>
          <div class="status-tile">
            <div class="status-label">Review Queue</div>
            <div class="status-value" id="pendingReviewCount">0</div>
            <div class="status-sub">Pending reviewer triage</div>
          </div>
        </div>
        <div style="padding: 0 18px 18px;">
          <div class="message" id="authMessage">Loading session.</div>
          <div class="upload-meta" style="margin-top:12px;">
            <input type="text" id="actorNameInput" placeholder="Actor name" value="local-operator" />
            <select id="roleInput">
              <option value="operator">operator</option>
              <option value="reviewer">reviewer</option>
              <option value="acceptance_lead">acceptance_lead</option>
              <option value="admin">admin</option>
            </select>
            <input type="text" id="accessCodeInput" placeholder="Local access code" value="spot-local" />
          </div>
          <div class="actions" style="margin-top:12px;">
            <button class="secondary" type="button" onclick="login()">Login</button>
            <button class="secondary" type="button" onclick="logout()">Logout</button>
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
              <div class="panel-note">Submit an approved `.xlsx` workbook, validate it against runtime guardrails, and start a run from the accepted intake record.</div>
            </div>
            <div class="actions">
              <span class="pill warn">Upload -> Run -> Review -> Artifacts</span>
            </div>
          </div>
          <form class="upload-form" onsubmit="event.preventDefault(); uploadWorkbook();">
            <input type="file" id="uploadFile" accept=".xlsx" />
            <div class="upload-meta">
              <input type="text" id="runIdInput" placeholder="Run ID (for start action)" value="spot-browser-run" />
              <select id="languageInput">
                <option value="de">de</option>
                <option value="en">en</option>
                <option value="hu">hu</option>
              </select>
              <select id="reviewModeInput">
                <option value="partial">partial</option>
                <option value="full">full</option>
                <option value="none">none</option>
              </select>
            </div>
            <div class="actions">
              <button class="primary" id="uploadButton" type="submit">Validate Upload</button>
              <button class="warn" id="startUploadButton" type="button" onclick="startSelectedUpload()" disabled>Start Run From Selected Upload</button>
            </div>
            <div class="message" id="uploadMessage">No upload submitted yet.</div>
          </form>
        </div>

        <div class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Recent Runs</h2>
              <div class="panel-note">The dashboard reads persisted run records and refreshes review summaries from local artifacts.</div>
            </div>
            <div class="actions">
              <button class="secondary" onclick="loadDashboard()">Refresh</button>
            </div>
          </div>
          <div class="list" id="runsList"></div>
        </div>
      </div>

      <div class="stack">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Accepted Uploads</h2>
              <div class="panel-note">Only accepted intake records can be used to start browser-driven runs.</div>
            </div>
          </div>
          <div class="list" id="uploadsList"></div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Run Detail</h2>
              <div class="panel-note">Select a run to inspect current state, review summary, and recent operator actions.</div>
            </div>
          </div>
          <div id="runDetailEmpty" class="message">No run selected.</div>
          <div id="runDetail" style="display:none;">
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
            </div>
            <div class="message" id="detailMessage">Run detail loaded.</div>
            <h3 style="margin: 18px 0 10px;">Review Rows</h3>
            <pre id="reviewRowsPre">[]</pre>
            <h3 style="margin: 18px 0 10px;">Action Log</h3>
            <pre id="actionsPre">[]</pre>
          </div>
        </div>
      </div>
    </section>
  </div>

  <script>
    let selectedUploadId = null;
    let selectedRunId = null;

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

    async function loadSession() {
      const res = await fetch('/auth/session');
      const data = await res.json();
      const session = data.session || {};
      if (data.authenticated) {
        setMessage('authMessage', JSON.stringify({
          authenticated: true,
          actor_name: session.actor_name,
          role: session.role,
          auth_enabled: data.auth_enabled
        }, null, 2), 'ok');
      } else {
        setMessage('authMessage', JSON.stringify({
          authenticated: false,
          auth_enabled: data.auth_enabled
        }, null, 2), 'error');
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
      setMessage('authMessage', JSON.stringify(data, null, 2), res.ok ? 'ok' : 'error');
      await loadSession();
    }

    async function logout() {
      const res = await fetch('/auth/logout', { method: 'POST' });
      const data = await res.json();
      setMessage('authMessage', JSON.stringify(data, null, 2), 'ok');
      await loadSession();
    }

    async function uploadWorkbook() {
      const fileInput = document.getElementById('uploadFile');
      const button = document.getElementById('uploadButton');
      const file = fileInput.files[0];
      if (!file) {
        setMessage('uploadMessage', 'Choose a .xlsx workbook first.', 'error');
        return;
      }
      button.disabled = true;
      try {
        const buf = await file.arrayBuffer();
        const res = await fetch('/uploads/intake', {
          method: 'POST',
          headers: { 'X-Filename': file.name },
          body: buf,
        });
        const data = await res.json();
        if (!res.ok) {
          setMessage('uploadMessage', JSON.stringify(data, null, 2), 'error');
          return;
        }
        selectedUploadId = data.upload_id;
        document.getElementById('startUploadButton').disabled = data.status !== 'accepted';
        setMessage('uploadMessage', JSON.stringify(data, null, 2), data.status === 'accepted' ? 'ok' : 'error');
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
      const language = document.getElementById('languageInput').value;
      const reviewMode = document.getElementById('reviewModeInput').value;
      if (!runId) {
        setMessage('uploadMessage', 'Run ID is required.', 'error');
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
      setMessage('uploadMessage', JSON.stringify(data, null, 2), 'ok');
      await loadDashboard();
      await loadSelectedRun();
    }

    async function loadDashboard() {
      const [runsRes, uploadsRes] = await Promise.all([fetch('/runs'), fetch('/uploads')]);
      const runs = await runsRes.json();
      const uploads = await uploadsRes.json();
      renderRuns(Array.isArray(runs) ? runs : []);
      renderUploads(Array.isArray(uploads) ? uploads : []);
      const acceptedUploads = uploads.filter(u => u.status === 'accepted');
      const activeRun = runs.find(r => ['STARTING', 'PENDING', 'VALIDATING', 'PROCESSING', 'WRITING', 'PAUSED'].includes(String(r.state || r.status || '').toUpperCase()));
      const pendingReview = runs.reduce((acc, r) => acc + Number((((r.review_summary || {}).pending_rows) || 0)), 0);
      document.getElementById('runCount').textContent = String(runs.length);
      document.getElementById('uploadCount').textContent = String(acceptedUploads.length);
      document.getElementById('activeRunState').textContent = activeRun ? String(activeRun.state || activeRun.status) : 'Idle';
      document.getElementById('activeRunId').textContent = activeRun ? String(activeRun.run_id || '-') : 'No active run';
      document.getElementById('runHealth').textContent = runs.length ? `Latest: ${String((runs[0] || {}).run_id || '-')}` : 'No run selected';
      document.getElementById('pendingReviewCount').textContent = String(pendingReview);
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
          <div class="meta">Pending review: ${escapeHtml((((run.review_summary || {}).pending_rows) || 0))} · Upload: ${escapeHtml(run.upload_id || '-')}</div>
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
          <div class="meta">Rows: ${escapeHtml((((upload.validation || {}).row_count) || '-'))}</div>
          <div class="actions">
            <button class="secondary" type="button" onclick="selectUpload('${escapeHtml(upload.upload_id || '')}')">Use For Run Start</button>
          </div>
        </div>
      `).join('');
    }

    function selectUpload(uploadId) {
      selectedUploadId = uploadId;
      document.getElementById('startUploadButton').disabled = false;
      setMessage('uploadMessage', 'Selected upload: ' + uploadId, 'ok');
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
      document.getElementById('runDetailEmpty').style.display = 'none';
      document.getElementById('runDetail').style.display = 'block';
      document.getElementById('detailRunId').textContent = data.run_id || '-';
      document.getElementById('detailState').textContent = `${data.state || '-'} (${(data.progress || {}).progress_percentage ?? 0}%)`;
      const summary = data.review_summary || {};
      document.getElementById('detailReview').textContent = `required=${summary.review_required_rows || 0}, reviewed=${summary.reviewed_rows || 0}, pending=${summary.pending_rows || 0}`;
      document.getElementById('detailUpload').textContent = data.upload_id || '-';
      setMessage('detailMessage', JSON.stringify(data, null, 2), 'ok');
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

    loadDashboard();
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
        <button class="secondary" type="button" id="pauseBtn" onclick="runOperation('pause')">Pause</button>
        <button class="secondary" type="button" id="resumeBtn" onclick="runOperation('resume')">Resume</button>
        <button class="secondary" type="button" id="cancelBtn" onclick="runOperation('cancel')">Cancel</button>
        <button class="secondary" type="button" id="retryBtn" onclick="runOperation('retry')">Retry</button>
        <button class="secondary" type="button" id="recoverBtn" onclick="runOperation('recover')">Recover</button>
        <a class="link-btn" href="/classify-monitor" target="_blank">Legacy Classify Monitor</a>
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
      document.getElementById('progressValue').textContent = `${(data.progress || {}).progress_percentage ?? 0}%`;
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
    require_permission(request, "view")
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
    .filters { display:grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap:10px; }
    select, textarea { width:100%; border-radius:12px; border:1px solid var(--line); padding:10px 12px; background:white; font-family:"Avenir Next","Segoe UI",sans-serif; font-size:14px; }
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
    .grid { display:grid; grid-template-columns: 1.1fr .9fr; gap:10px; }
    .review-form { display:grid; gap:8px; }
    .message { white-space:pre-wrap; padding:10px 12px; border-radius:12px; background:#f7f1e6; border:1px solid var(--line); font-size:13px; line-height:1.45; }
    @media (max-width: 960px) { .filters,.stats,.grid { grid-template-columns:1fr; } .head { flex-direction:column; } h1 { font-size:28px; } }
  </style>
</head>
<body>
  <div class="shell">
    __PAGE_TOPBAR__
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

    function pillClass(status) {
      const txt = String(status || '').toUpperCase();
      if (txt.includes('REVIEWED') || txt.includes('CONFIRM')) return 'pill ok';
      if (txt.includes('ESCALAT')) return 'pill danger';
      return 'pill warn';
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
        document.getElementById('queueMessage').textContent = JSON.stringify(data, null, 2);
        return;
      }
      const rows = data.rows || [];
      document.getElementById('queueMessage').textContent = `filters=${JSON.stringify(data.filters || {})}\nrun_state=${data.state || '-'}\nrows=${rows.length}`;
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
            <div>
              <div class="muted">${escapeHtml(row.post_text || '')}</div>
              <div class="muted" style="margin-top:8px;">Flags: ${escapeHtml((row.flags || []).join(', ') || '-')}</div>
              <div class="muted">Soft signals: ${escapeHtml((row.soft_signal_flags || []).join(', ') || '-')}</div>
              <div class="muted">Soft score: ${escapeHtml(row.soft_signal_score ?? '-')}</div>
              <div class="muted">Fallbacks: ${escapeHtml((row.fallback_events || []).join(', ') || '-')}</div>
            </div>
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
      document.getElementById('queueMessage').textContent = JSON.stringify(data, null, 2);
      await loadQueue();
    }

    loadQueue();
    setInterval(loadQueue, 5000);
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
    require_permission(request, "view")
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
    .grid { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px; }
    .box { background:white; border:1px solid var(--line); border-radius:14px; padding:12px; }
    .label { color:var(--muted); text-transform:uppercase; font-size:12px; letter-spacing:.08em; margin-bottom:8px; font-family:"Avenir Next","Segoe UI",sans-serif; }
    .value { font-size:18px; }
    .pill { display:inline-flex; border-radius:999px; padding:5px 10px; border:1px solid var(--line); font-size:12px; font-weight:700; font-family:"Avenir Next","Segoe UI",sans-serif; }
    .pill.ok { color:var(--ok); } .pill.warn { color:var(--warn); } .pill.danger { color:var(--danger); }
    .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    button, a.link-btn, select, textarea {
      border:0; border-radius:999px; padding:10px 14px; cursor:pointer; text-decoration:none;
      font-family:"Avenir Next","Segoe UI",sans-serif; font-size:14px;
    }
    button.primary { background:var(--accent); color:white; }
    button.secondary, a.link-btn { background:#e8decf; color:var(--text); }
    select, textarea { border-radius:12px; border:1px solid var(--line); background:white; padding:10px 12px; width:100%; }
    textarea { min-height: 120px; }
    pre {
      margin: 0; padding: 12px; border-radius: 14px; border:1px solid var(--line); background:#fbf6ee;
      overflow:auto; font-size:12px; line-height:1.45; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .message { white-space:pre-wrap; padding:10px 12px; border-radius:12px; background:#f7f1e6; border:1px solid var(--line); font-size:13px; line-height:1.45; }
    .stack { display:grid; gap:12px; }
    @media (max-width: 920px) { .grid { grid-template-columns:1fr; } .head { flex-direction:column; } h1 { font-size:28px; } }
  </style>
</head>
<body>
  <div class="shell">
    __PAGE_TOPBAR__
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
      <pre id="rowPre">{}</pre>
    </section>

    <section class="panel">
      <div class="head"><h2>Evidence</h2></div>
      <div class="stack">
        <div class="box">
          <div class="label">Explanation</div>
          <pre id="explanationPre"></pre>
        </div>
        <div class="box">
          <div class="label">Flags And Fallback Events</div>
          <pre id="flagsPre"></pre>
        </div>
        <div class="box">
          <div class="label">Disagreement Evidence</div>
          <pre id="disagreementPre">null</pre>
        </div>
      </div>
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

    function pillClass(status) {
      const txt = String(status || '').toUpperCase();
      if (txt.includes('REVIEWED') || txt.includes('CONFIRM')) return 'pill ok';
      if (txt.includes('ESCALAT')) return 'pill danger';
      return 'pill warn';
    }

    async function loadInspector() {
      const res = await fetch('/runs/' + encodeURIComponent(runId) + '/review-rows/' + encodeURIComponent(rowIndex));
      const data = await res.json();
      if (!res.ok) {
        document.getElementById('inspectorMessage').textContent = JSON.stringify(data, null, 2);
        return;
      }
      document.getElementById('statePill').className = pillClass((data.review_controls || {}).review_state || 'pending');
      document.getElementById('statePill').textContent = (data.review_controls || {}).review_state || 'pending';
      document.getElementById('assignedCategory').textContent = ((data.row || {}).assigned_category) || '-';
      document.getElementById('confidenceValue').textContent = String(((data.row || {}).confidence_score) ?? '-');
      document.getElementById('reviewStateValue').textContent = (data.review_controls || {}).review_state || 'pending';
      document.getElementById('reviewDecisionValue').textContent = (data.review_controls || {}).review_decision || '-';
      document.getElementById('rowPre').textContent = JSON.stringify(data.row || {}, null, 2);
      document.getElementById('explanationPre').textContent = JSON.stringify((data.evidence || {}).explanation || '', null, 2);
      document.getElementById('flagsPre').textContent = JSON.stringify({
        flags: (data.evidence || {}).flags || [],
        fallback_events: (data.evidence || {}).fallback_events || [],
        soft_signal_score: (data.evidence || {}).soft_signal_score ?? null,
        soft_signal_flags: (data.evidence || {}).soft_signal_flags || [],
        soft_signal_evidence: (data.evidence || {}).soft_signal_evidence || []
      }, null, 2);
      document.getElementById('disagreementPre').textContent = JSON.stringify((data.evidence || {}).disagreement, null, 2);
      document.getElementById('reviewStateInput').value = (data.review_controls || {}).review_state || 'pending';
      document.getElementById('reviewDecisionInput').value = (data.review_controls || {}).review_decision || '';
      document.getElementById('reviewNoteInput').value = (data.review_controls || {}).reviewer_note || '';
      document.getElementById('inspectorMessage').textContent = `run_id=${data.run_id}\nrow_index=${data.row_index}\nrun_state=${data.run_state}\nreview_state=${(data.review_controls || {}).review_state || 'pending'}`;
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
      document.getElementById('inspectorMessage').textContent = JSON.stringify(data, null, 2);
      await loadInspector();
    }

    loadInspector();
    setInterval(loadInspector, 5000);
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
