#!/usr/bin/env bash
# AIDEAL GoFlowOS MVP — Iniciar backend e frontend em paralelo
# Uso: bash scripts/subir-dev.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== AIDEAL GoFlowOS MVP — Modo Desenvolvimento ==="

cleanup_port() {
    local port=$1
    local pids
    pids=$(lsof -ti tcp:"$port" || true)
    if [ -n "$pids" ]; then
        echo "Encerrando processo(s) existente(s) na porta $port: $pids"
        kill $pids 2>/dev/null || true
        sleep 1
    fi
}

# Evita conflito com processos antigos (especialmente backend sem --reload)
cleanup_port 8000
cleanup_port 5173

# Iniciar backend
echo "Iniciando backend (porta 8000)..."
cd "$PROJECT_DIR/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Iniciar frontend
echo "Iniciando frontend (porta 5173)..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Acesse: http://localhost:5173"
echo ""
echo "Pressione Ctrl+C para parar ambos."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
