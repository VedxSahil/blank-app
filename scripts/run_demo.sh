#!/usr/bin/env bash
# Start the PEReport demo (API + web app) on one document and print the URL.
# Usage: scripts/run_demo.sh [ilpa|sample]      (default: ilpa)
# Needs: python 3.13+, node 20+, internet for pip/npm (no other hosts).
set -euo pipefail
cd "$(dirname "$0")/.."
DOC="${1:-ilpa}"
API_PORT="${API_PORT:-8000}"; WEB_PORT="${WEB_PORT:-3100}"

PY=.demo-venv/bin
[ -x "$PY/python" ] || python3 -m venv .demo-venv
"$PY/pip" install -q -e . httpx >/dev/null
[ -d web/node_modules ] || (cd web && npm ci --no-audit --no-fund >/dev/null)

case "$DOC" in
  ilpa)
    "$PY/python" scripts/build_index.py data/real/meta.json --src data/real --out data/chunks >/dev/null
    export PEREPORT_CHUNKS=data/chunks PEREPORT_EVAL=eval/ilpa/test PEREPORT_MANIFEST=data/real/manifest.json
    export PEREPORT_BANNER="REAL DOCUMENT: official ILPA Reporting Template v2.0 (public template). Answers describe the template, not any fund." ;;
  sample)
    "$PY/python" scripts/build_index.py --src data/sample --out data/chunks_sample >/dev/null
    export PEREPORT_CHUNKS=data/chunks_sample PEREPORT_EVAL=eval/sample/test PEREPORT_MANIFEST=data/sample/manifest.json
    export PEREPORT_BANNER="SAMPLE DOCUMENT: replica of a real PPM with names changed. Pipeline test, not a real-data result." ;;
  *) echo "unknown document '$DOC' (use ilpa or sample)"; exit 2 ;;
esac

export API_URL="http://127.0.0.1:$API_PORT"
(cd web && npm run build >/dev/null)
"$PY/uvicorn" pereport.api:app_from_disk --factory --port "$API_PORT" --log-level warning &
API=$!
(cd web && npm run start -- -p "$WEB_PORT" >/dev/null) &
WEB=$!
trap 'kill $API $WEB 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 1 60); do curl -fs "http://127.0.0.1:$API_PORT/api/health" >/dev/null && break; sleep 1; done
echo
echo "PEReport is running on the $DOC document:  http://127.0.0.1:$WEB_PORT"
echo "Try: What is a Returned Clawback?  (answer)   |   What is the fund's hurdle rate?  (refusal)"
echo "Press Ctrl+C to stop."
wait
