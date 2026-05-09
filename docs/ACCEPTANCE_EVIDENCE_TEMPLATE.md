# {spot} Acceptance Evidence Template

Document date: `2026-05-03`
Workspace baseline: `0.5.0`
SSOT: `0.2`

## Session Details

- Date: `<YYYY-MM-DD>`
- Machine model: `<hardware model>`
- Unified memory: `<memory>`
- SSD size: `<storage>`
- macOS version: `<macOS version>`
- Python version: `<python version>`
- `{spot}` commit hash: `<git commit hash>`
- Workspace baseline: `0.5.0`
- Latest shipped release: `v0.3.1`
- SSOT path: `/Users/moldovancsaba/Projects/spot/ssot/ssot.json`
- Production mode: `SPOT_PRODUCTION_MODE=1` for bootstrap/preflight/runtime acceptance commands
- Supported native build/install path: `cd app/macos && swift build && bash build-bundle.sh && bash install-bundle.sh`
- Native acceptance smoke command: `.venv/bin/python app/macos/native_acceptance_smoke.py`
- Operator: `<operator>`
- Reviewer: `<reviewer>`
- Historical acceptance record for the prior `0.3.2` session: [`docs/ACCEPTANCE_EVIDENCE_2026-03-18.md`](/Users/moldovancsaba/Projects/spot/docs/ACCEPTANCE_EVIDENCE_2026-03-18.md)

## Native Operator Workflow Record

- Native app installed and launched: `<yes/no>`
- Startup preflight result: `<passed/failed>`
- Native acceptance smoke verification passed: `<yes/no>`
- Upload intake flow confirmed: `<yes/no>`
- Review queue and row inspector confirmed: `<yes/no>`
- Artifact center confirmed: `<yes/no>`
- Local auth / permission boundary confirmed: `<yes/no>`
- Notes: `<exact command outputs, native-visible failure states, and whether the operator completed the workflow without engineering help>`

## Benchmark Record

- Benchmark workbook: `<input workbook path>`
- Row count: `<rows executed>`
- Language: `<language>`
- Primary-route run ID: `<run id>`
- Duration: `<duration>`
- Rows per minute: `<rpm>`
- Output workbook: `<output workbook path>`
- Artefact directory: `<artifact directory>`
- Result summary: `<whether the primary route completed cleanly, whether fallback occurred, and any guardrail findings>`

## Fallback Record

- Fallback demonstrated: `<yes/no>`
- Run ID: `<run id>`
- Trigger reason: `<reason>`
- Fallback event type: `<event type>`
- Affected rows: `<count>`
- Evidence files: `<key files>`
- Operator visibility confirmed: `<yes/no>`

## Disagreement Record

- Disagreement demonstrated: `<yes/no>`
- Run ID: `<run id>`
- Disagreement row count: `<count>`
- `disagreement_report.json` present: `<yes/no>`
- Judge participation confirmed: `<yes/no>`
- Evidence files: `<key files>`

## Workbook Output Review

- Metadata columns present: `<yes/no>`
- `Assigned Category` correct: `<yes/no/conditional>`
- `Fallback Events` present when expected: `<yes/no>`
- `Review Required` populated correctly: `<yes/no>`
- Explanation quality acceptable: `<yes/no/conditional>`
- Notes: `<output quality observations>`

## Artefact Review

- `policy.json` present: `<yes/no>`
- `integrity_report.json` present: `<yes/no>`
- `artifact_manifest.json` present: `<yes/no>`
- `logs.txt` present: `<yes/no>`
- Artefact access path confirmed: `<yes/no>`
- Notes: `<artifact observations>`

## Operational Review

- `py_compile` completed: `<yes/no>`
- bootstrap completed: `<yes/no>`
- preflight completed: `<yes/no>`
- operator started run successfully: `<yes/no>`
- operator retrieved outputs successfully: `<yes/no>`
- operator understood review workflow: `<yes/no>`
- Notes: `<runtime probe notes, guardrail findings, or operational caveats>`

## Final Acceptance Position

- Decision: `<accepted / accepted_with_conditions / not_accepted>`
- Critical issues: `<blocking issues>`
- Non-critical follow-up actions: `<follow-up actions>`
- Sign-off date: `<date>`
- Client representative: `<name>`
- Sentinel Squad representative: `<name>`
