#!/usr/bin/env bash
# Sobe backend ou frontend deste checkout para pré-visualização local, com bancos
# descartáveis fora do repositório. Uso: bash scripts/preview-local.sh backend|frontend
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${AIDEAL_PREVIEW_DATA_DIR:-${TMPDIR:-/tmp}/aideal-preview}"
mkdir -p "$DATA_DIR"

# O venv pode estar neste checkout ou, num worktree, no checkout principal.
resolve_python() {
    local candidate
    for candidate in "${AIDEAL_PREVIEW_PYTHON:-}" "$PROJECT_DIR/backend/.venv/bin/python" \
        "$(git -C "$PROJECT_DIR" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print substr($0, 10); exit}')/backend/.venv/bin/python"; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

case "${1:-}" in
    backend)
        PYTHON_BIN="$(resolve_python)" || { echo "Erro: backend/.venv não encontrado" >&2; exit 1; }
        export AIDEAL_ADMIN_USERNAME="${AIDEAL_ADMIN_USERNAME:-Eduardo}"
        export AIDEAL_ADMIN_PASSWORD="${AIDEAL_ADMIN_PASSWORD:-senha-admin-e2e-segura}"
        export AIDEAL_ADMIN_COOKIE_SECURE=false
        export AIDEAL_DB_PATH="$DATA_DIR/financeiro.db"
        export AIDEAL_IDENTITY_DB_PATH="$DATA_DIR/identity.db"
        export AIDEAL_ORCAMENTO_DB_PATH="$DATA_DIR/orcamento.db"
        exec "$PYTHON_BIN" -m uvicorn app.main:app --app-dir "$PROJECT_DIR/backend" \
            --host 127.0.0.1 --port "${AIDEAL_PORT:-8000}" --reload --reload-dir "$PROJECT_DIR/backend/app"
        ;;
    frontend)
        export AIDEAL_API_TARGET="${AIDEAL_API_TARGET:-http://127.0.0.1:${AIDEAL_PORT:-8000}}"
        cd "$PROJECT_DIR/frontend"
        exec npm run dev
        ;;
    *)
        echo "Uso: bash scripts/preview-local.sh backend|frontend" >&2
        exit 2
        ;;
esac
