#!/bin/bash
# Idempotent launcher for the DeepSeek Harness (used by com.dsh.web).
# If another instance already owns port 3080, exit 1 so launchd retries later
# (KeepAlive); at boot the port is free and this execs the real harness.
if lsof -nP -iTCP:3080 -sTCP:LISTEN >/dev/null 2>&1; then
  exit 1
fi
exec /Users/Shared/Projects/settings/bin/dsh-harness-node \
  /Users/Shared/Projects/settings/npm/bin/dsh web \
  --patch /Users/chappie/.ollama/launch/dsh/ollama.cordis.yml
