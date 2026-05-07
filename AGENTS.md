# Agent Guide

Read these first:
- [`READMEDEV.md`](/Users/moldovancsaba/Projects/spot/READMEDEV.md)
- [`README.md`](/Users/moldovancsaba/Projects/spot/README.md)
- [`docs/LOCAL_APPLIANCE_RUNBOOK.md`](/Users/moldovancsaba/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md)
- [`docs/HANDOVER.md`](/Users/moldovancsaba/Projects/spot/docs/HANDOVER.md)

Working rules:
- inspect the repo directly before changing it
- check `git status --short` first
- keep doc edits minimal and grounded in repo usage
- preserve `{spot}` branding exactly as written

Common commands:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
.venv/bin/python -m src.cli classify \
  --input samples/sample_germany.xlsx \
  --output samples/sample_germany_out.xlsx \
  --run-id run-001 \
  --language de \
  --review-mode partial \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --max-workers 1
```

```bash
.venv/bin/python -m src.cli preflight \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --port 8765
```

```bash
python3 -m src.cli bootstrap \
  --project-root . \
  --venv-path .venv \
  --requirements requirements.txt \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --logs-dir logs
```

```bash
.venv/bin/python -m src.cli evaluate \
  --input samples/sample_germany.xlsx \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --evaluation-run-id eval-2000 \
  --language de \
  --review-mode partial \
  --single-model mlx://mlx-community/Apertus-8B-Instruct-2509-4bit \
  --ensemble-models ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.1:8b \
  --max-workers 1 \
  --limit 500 \
  --progress-every 10
```

```bash
.venv/bin/python -m src.cli benchmark-workers \
  --input samples/sample_germany.xlsx \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --benchmark-run-id bench-001 \
  --language de \
  --review-mode partial \
  --worker-values 1,2,4 \
  --limit 500 \
  --progress-every 10
```

Browser appliance workflow:
- supported startup entrypoint: `bash start_browser_appliance.sh`
- the script runs preflight first unless `SPOT_RUN_PREFLIGHT=0`
- backend binds to `127.0.0.1:8765`
- supported browser URL: `http://127.0.0.1:8765/app`

Browser verification workflow:
- repo-native smoke command: `.venv/bin/python backend/browser_operator_smoke.py`
- this validates auth, upload intake, run detail, review, artifacts, sign-off, recovery, and page renders
- this is integration smoke only, not live client acceptance evidence

Minimum validation:

```bash
git status --short --branch
python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py backend/browser_operator_smoke.py backend/backend_contract_regression.py backend/ops_queue_regression.py backend/segment_worker.py src/benchmark.py src/targeted_adjudication_regression.py
.venv/bin/python backend/backend_contract_regression.py
.venv/bin/python backend/ops_queue_regression.py
.venv/bin/python src/targeted_adjudication_regression.py
```
