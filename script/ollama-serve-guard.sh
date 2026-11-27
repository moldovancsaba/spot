#!/bin/bash
# Idempotent Ollama server launcher (used by com.ollama.serve). If something already owns
# 11434, exit 1 so launchd retries later; at boot the port is free and this execs the server.
if lsof -nP -iTCP:11434 -sTCP:LISTEN >/dev/null 2>&1; then
  exit 1
fi
exec /Applications/Ollama.app/Contents/Resources/ollama serve
