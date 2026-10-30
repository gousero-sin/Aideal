#!/usr/bin/env bash
# Validação /ecc:multiplan para backend, segurança e disponibilidade.
# Uso: bash scripts/validate-prod.sh

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
FAILURES=0

section() {
    printf '\n=== %s ===\n' "$1"
}

run_step() {
    local name="$1"
    shift
    printf '\n[check] %s\n' "$name"
    if "$@"; then
        printf '[ok] %s\n' "$name"
    else
        printf '[fail] %s\n' "$name"
        FAILURES=$((FAILURES + 1))
    fi
}

ensure_backend_dev() {
    cd "$BACKEND_DIR" || return 1
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv || return 1
    fi
    "$PYTHON_BIN" -m pip install -e ".[dev]" --quiet
}

ensure_frontend_deps() {
    cd "$FRONTEND_DIR" || return 1
    if [ -f "package-lock.json" ]; then
        npm ci --include=dev --silent
    else
        npm install --include=dev --silent
    fi
}

# CORS aceita só loopback e o nome da rede local (goflowaideal, goflowaideal.local)
# ou o host de AIDEAL_PUBLIC_URL, quando definido. O host é comparado por igualdade
# após o parse: prefixo deixaria passar algo como http://goflowaideal.example.com.
check_local_config() {
    cd "$BACKEND_DIR" || return 1
    "$PYTHON_BIN" - <<'PY'
import os
from urllib.parse import urlsplit

from app.config import settings

assert settings.max_upload_size_mb <= 50
assert settings.max_files_per_batch <= 20
assert '.xls' in settings.allowed_upload_extensions_set
assert '.xlsx' in settings.allowed_upload_extensions_set
assert '*' not in settings.cors_origin_list

allowed_hosts = {'127.0.0.1', 'localhost', 'goflowaideal', 'goflowaideal.local'}
public_url = os.environ.get('AIDEAL_PUBLIC_URL', '').strip()
if public_url:
    allowed_hosts.add(urlsplit(public_url).hostname or '')
for origin in settings.cors_origin_list:
    parts = urlsplit(origin)
    assert parts.scheme in ('http', 'https') and parts.hostname in allowed_hosts, (
        f'origem CORS fora da rede local: {origin}'
    )
print('limites e CORS locais OK')
PY
}

main() {
    section "backend"
    run_step "Dependências Python dev" ensure_backend_dev
    run_step "Testes Python" bash -lc "cd \"$BACKEND_DIR\" && .venv/bin/python -m pytest"
    run_step "Lint Python" bash -lc "cd \"$BACKEND_DIR\" && .venv/bin/python -m ruff check app tests"
    run_step "Integridade de dependências Python" bash -lc \
        "cd \"$BACKEND_DIR\" && .venv/bin/python -m pip check"

    section "segurança"
    run_step "Dependências frontend" ensure_frontend_deps
    run_step "Configuração local e limites de upload" check_local_config
    run_step "Auditoria npm produção" bash -lc \
        "cd \"$FRONTEND_DIR\" && npm audit --omit=dev"

    section "disponibilidade"
    run_step "Build frontend produção" bash -lc "cd \"$FRONTEND_DIR\" && npm run build"
    run_step "Sintaxe do script de produção" bash -lc \
        "bash -n \"$PROJECT_DIR/scripts/subir-producao.sh\""
    run_step "Artefatos operacionais" bash -lc "cd \"$BACKEND_DIR\" && \"$PYTHON_BIN\" - <<'PY'
from app.config import settings

checks = {
    'data/aideal.db': settings.db_path.exists(),
    'templates DRE': settings.template_dre_path.exists(),
    'templates Fluxo': settings.template_fluxo_path.exists(),
    'frontend/dist': (settings.frontend_dist_dir / 'index.html').exists(),
}
for name, ok in checks.items():
    print(f'{name}: {ok}')
assert all(checks.values())
PY"

    printf '\n=== resultado ===\n'
    if [ "$FAILURES" -eq 0 ]; then
        echo "Produção validada: backend, segurança e disponibilidade OK."
        exit 0
    fi

    echo "Produção ainda não validada: $FAILURES check(s) falharam."
    exit 1
}

# Carregado com `source` (testes), só define as funções.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
