#!/bin/bash

# ==============================================================================
# Shruti Samvad Startup Script (macOS, no Docker, single terminal)
# ==============================================================================
# Runs every service as a background process in THIS terminal:
#   1. Ollama             (only if not already running)
#   2. RSS API            (uvicorn  :8000)
#   3. RSS worker         (arq ingestion)
#   4. Podcast API        (uvicorn  :8001)
#   5. Podcast worker     (arq LangGraph pipeline)
#   6. Frontend           (next dev :3000)
#
# Output from all services is streamed here (prefixed with [service]) and also
# written to ./logs/<service>.log. Press Ctrl+C to stop everything.
#
# Assumes PostgreSQL (5432) and Redis (6379) are already running locally and
# Ollama is installed. Docker is NOT required.
# ==============================================================================

set -uo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Resolve absolute paths (independent of where the script is called from)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
VENV="$BACKEND/.venv"
FRONTEND="$ROOT/frontend/web"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

# Run all Python processes from the backend root with it on PYTHONPATH so that
# both `core.*` and `services.*` package imports resolve consistently. Also load
# .env so DATABASE_URL/REDIS_URL/OLLAMA_MODEL reach each process (the services
# read these via os.getenv and otherwise fall back to defaults).
PYRUN="cd '$BACKEND' && source '$VENV/bin/activate' && set -a && source '$ROOT/.env' && set +a && export PYTHONPATH='$BACKEND'"

echo -e "${BLUE}=== Shruti Samvad startup (no Docker, single terminal) ===${NC}"

# ------------------------------------------------------------------ preflight
fail() { echo -e "${RED}ERROR:${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}WARN:${NC} $1"; }
port_open() { nc -z localhost "$1" >/dev/null 2>&1; }

[ -d "$VENV" ] || fail "Python venv not found at $VENV. Create it: python3.11 -m venv backend/.venv && pip install -r ... (see README)."
[ -d "$FRONTEND/node_modules" ] || warn "frontend deps not installed — run: (cd frontend/web && npm install)"

if [ ! -f "$ROOT/.env" ]; then
    warn ".env missing — copying from .env.example"
    cp "$ROOT/.env.example" "$ROOT/.env"
fi

port_open 5432 || warn "PostgreSQL not reachable on :5432 — start it (e.g. brew services start postgresql@16)."
port_open 6379 || warn "Redis not reachable on :6379 — start it (e.g. brew services start redis)."

# ------------------------------------------------------------------ process mgmt
PIDS=()
LABELS=()

# Run a command in the background, streaming output here (prefixed) and to a log.
run_service() {
    local label=$1
    local cmd=$2
    echo -e "${GREEN}Starting ${label}...${NC}"
    ( eval "$cmd" 2>&1 | awk -v l="$label" '{ printf "[%s] %s\n", l, $0; fflush() }' | tee "$LOGDIR/$label.log" ) &
    PIDS+=("$!")
    LABELS+=("$label")
}

CLEANED=0
cleanup() {
    [ "$CLEANED" = "1" ] && return
    CLEANED=1
    echo ""
    echo -e "${YELLOW}Stopping all services...${NC}"
    # Kill tracked background pipelines and their children
    for pid in "${PIDS[@]:-}"; do
        [ -n "$pid" ] || continue
        pkill -P "$pid" >/dev/null 2>&1
        kill "$pid" >/dev/null 2>&1
    done
    # Reliable fallback: stop uvicorn/arq by their command patterns (these may
    # have re-parented away from the tracked pipeline pids).
    pkill -f "uvicorn services.rss.main:app" >/dev/null 2>&1
    pkill -f "uvicorn services.podcast.main:app" >/dev/null 2>&1
    pkill -f "arq services.rss.worker" >/dev/null 2>&1
    pkill -f "arq services.podcast.worker" >/dev/null 2>&1
    echo -e "${GREEN}All services stopped.${NC}"
}
trap cleanup INT TERM EXIT

# ------------------------------------------------------------------ services
# 1. Ollama (only if not already serving)
if port_open 11434; then
    echo -e "${GREEN}Ollama already running on :11434${NC}"
else
    run_service "ollama" "ollama serve"
    sleep 2
fi

# 2. RSS API
run_service "rss-api"        "$PYRUN && exec uvicorn services.rss.main:app --reload --port 8000"

# 3. RSS ingestion worker
run_service "rss-worker"     "$PYRUN && exec arq services.rss.worker.WorkerSettings"

# 4. Podcast API
run_service "podcast-api"    "$PYRUN && exec uvicorn services.podcast.main:app --reload --port 8001"

# 5. Podcast worker
run_service "podcast-worker" "$PYRUN && exec arq services.podcast.worker.WorkerSettings"

# 6. Frontend
run_service "frontend"       "cd '$FRONTEND' && exec npm run dev"

# ------------------------------------------------------------------ banner
sleep 2
echo ""
echo -e "${GREEN}========================================================${NC}"
echo -e "${GREEN}  All Shruti Samvad services started${NC}"
echo -e "${GREEN}========================================================${NC}"
echo -e "  ${GREEN}✓${NC} Ollama           (LLM: gemma4:12b)"
echo -e "  ${GREEN}✓${NC} RSS API          ${BLUE}http://localhost:8000${NC}  (docs: /docs)"
echo -e "  ${GREEN}✓${NC} RSS Worker       (arq ingestion: fetch · extract · rules)"
echo -e "  ${GREEN}✓${NC} Podcast API      ${BLUE}http://localhost:8001${NC}  (docs: /docs)"
echo -e "  ${GREEN}✓${NC} Podcast Worker   (arq LangGraph pipeline)"
echo -e "  ${GREEN}✓${NC} Frontend         ${BLUE}http://localhost:3000${NC}"
echo -e "${GREEN}--------------------------------------------------------${NC}"
echo -e "  Open the app:    ${BLUE}http://localhost:3000${NC}"
echo -e "  API reference:   ${BLUE}http://localhost:8000/docs${NC}  ·  ${BLUE}http://localhost:8001/docs${NC}"
echo -e "  Logs:            ${LOGDIR}/<service>.log"
echo -e "${GREEN}========================================================${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services.${NC}"
echo ""

# Wait for all background services; Ctrl+C triggers cleanup()
wait
