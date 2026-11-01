#!/bin/bash
# One-command hackathon demo: builds the scratch DB if missing and
# serves it detached. Just open the printed URL in your browser.
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
DB="${IA_DEMO_DB:-/tmp/debitos-demo/demo.db}"
PORT="${IA_DEMO_PORT:-8932}"
export no_proxy="127.0.0.1,localhost" NO_PROXY="127.0.0.1,localhost"
if [ ! -f "$DB" ]; then
  echo "building scratch demo DB at $DB ..."
  "$ROOT/.venv/bin/python" -B "$ROOT/tools/demo_circuit.py" --db "$DB" || exit 1
fi
if curl -s -m 3 "http://127.0.0.1:$PORT/api/provider" 2>/dev/null | grep -q provider; then
  echo "demo already running: open http://127.0.0.1:$PORT/ in your browser (case EXP-2501)"
  exit 0
fi
setsid -f env IA_PROVIDER=simulated IA_DEMO_DB="$DB" IA_DEMO_PORT="$PORT" \
  "$ROOT/.venv/bin/python" -B -m debit_ai.demo_app </dev/null >>/tmp/debitos-demo.log 2>&1
sleep 4
if curl -s -m 5 "http://127.0.0.1:$PORT/api/provider" 2>/dev/null | grep -q provider; then
  echo "demo running: open http://127.0.0.1:$PORT/ in your browser (case EXP-2501)"
else
  echo "FAILED to start; see /tmp/debitos-demo.log"; exit 1
fi
