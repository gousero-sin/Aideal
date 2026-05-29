#!/usr/bin/env bash
# AIDEAL GoFlowOS MVP — produção local Linux
# Uso: bash scripts/subir-producao.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
HOST="${AIDEAL_HOST:-127.0.0.1}"
PORT="${AIDEAL_PORT:-8000}"
WORKERS="${AIDEAL_WORKERS:-1}"

export AIDEAL_CORS_ORIGINS="${AIDEAL_CORS_ORIGINS:-http://127.0.0.1:${PORT},http://localhost:${PORT}}"

echo "=== AIDEAL GoFlowOS MVP — Produção Linux ==="
echo "Diretório: $PROJECT_DIR"
echo "Bind: http://${HOST}:${PORT}"

echo ""
echo "[1/5] Preparando backend Python..."
cd "$BACKEND_DIR"

if [ ! -d ".venv" ]; then
    echo "  Criando ambiente virtual..."
    python3 -m venv .venv
fi

"$PYTHON_BIN" -m pip install -e . --quiet

echo ""
echo "[2/5] Gerando frontend de produção..."
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    if [ -f "package-lock.json" ]; then
        npm ci --silent
    else
        npm install --silent
    fi
fi

npm run build

echo ""
echo "[3/5] Verificando diretórios persistentes..."
mkdir -p "$PROJECT_DIR/logs/tmp"
mkdir -p "$PROJECT_DIR/output"
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/backend/config/template_baselines"

if [ ! -f "$PROJECT_DIR/data/aideal.db" ]; then
    echo "  Banco data/aideal.db não existe; as migrações criarão uma base vazia."
else
    echo "  Banco preservado: data/aideal.db"
fi

echo ""
echo "[4/5] Verificando baseline dos templates..."
DRE_BASELINE="$PROJECT_DIR/backend/config/template_baselines/dre_template_baseline.json"
FC_BASELINE="$PROJECT_DIR/backend/config/template_baselines/fluxo_template_baseline.json"

if [ ! -f "$DRE_BASELINE" ] || [ ! -f "$FC_BASELINE" ]; then
    cd "$PROJECT_DIR"
    "$PYTHON_BIN" scripts/template_integrity.py capture-defaults
else
    echo "  Baselines já existem."
fi

echo ""
echo "[5/5] Subindo aplicação final..."
echo "  Frontend estático: frontend/dist"
echo "  API + frontend: http://${HOST}:${PORT}"
echo "  Health: http://${HOST}:${PORT}/health"
echo "  Ready: http://${HOST}:${PORT}/ready"
echo ""
echo "Pressione Ctrl+C para parar."

cd "$BACKEND_DIR"
exec "$PYTHON_BIN" -m uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --proxy-headers \
    --timeout-keep-alive 30
