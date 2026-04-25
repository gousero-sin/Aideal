#!/bin/bash
# AIDEAL GoFlowOS MVP — Script de inicialização
# Uso: bash scripts/start.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "=== AIDEAL GoFlowOS MVP ==="
echo "Diretório: $PROJECT_DIR"

# --- Backend ---
echo ""
echo "[1/3] Configurando backend Python..."
cd "$PROJECT_DIR/backend"

if [ ! -d ".venv" ]; then
    echo "  Criando ambiente virtual..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "  Instalando dependências..."
pip install -e ".[dev]" --quiet 2>/dev/null || pip install -e . --quiet

# --- Frontend ---
echo ""
echo "[2/3] Configurando frontend..."
cd "$PROJECT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "  Instalando dependências npm..."
    npm install --silent
fi

# --- Diretórios ---
echo ""
echo "[3/3] Verificando diretórios..."
mkdir -p "$PROJECT_DIR/logs/tmp"
mkdir -p "$PROJECT_DIR/output"
mkdir -p "$PROJECT_DIR/backend/config/template_baselines"

DRE_BASELINE="$PROJECT_DIR/backend/config/template_baselines/dre_template_baseline.json"
FC_BASELINE="$PROJECT_DIR/backend/config/template_baselines/fluxo_template_baseline.json"

if [ ! -f "$DRE_BASELINE" ] || [ ! -f "$FC_BASELINE" ]; then
    echo "  Capturando baseline estrutural dos templates..."
    cd "$PROJECT_DIR"
    python3 scripts/template_integrity.py capture-defaults
fi

echo ""
echo "=== Setup completo! ==="
echo ""
echo "Para iniciar o backend:"
echo "  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo ""
echo "Para iniciar o frontend:"
echo "  cd frontend && npm run dev"
echo ""
echo "Acesse: http://localhost:5173"
