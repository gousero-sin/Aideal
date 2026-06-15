#!/usr/bin/env bash
# AIDEAL GoFlowOS MVP - producao local Linux
# Uso: bash scripts/subir-producao.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
HOST="${AIDEAL_HOST:-0.0.0.0}"
PORT="${AIDEAL_PORT:-8000}"
WORKERS="${AIDEAL_WORKERS:-1}"

export AIDEAL_CORS_ORIGINS="${AIDEAL_CORS_ORIGINS:-http://127.0.0.1:${PORT},http://localhost:${PORT}}"

log() {
    printf '%s\n' "$*"
}

die() {
    printf 'Erro: %s\n' "$*" >&2
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

run_privileged() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
        return
    fi

    if command_exists sudo; then
        sudo "$@"
        return
    fi

    die "preciso de root ou sudo para instalar dependencias do sistema: $*"
}

detect_package_manager() {
    if command_exists apt-get; then
        printf 'apt\n'
    elif command_exists dnf; then
        printf 'dnf\n'
    elif command_exists yum; then
        printf 'yum\n'
    elif command_exists apk; then
        printf 'apk\n'
    elif command_exists pacman; then
        printf 'pacman\n'
    else
        return 1
    fi
}

install_base_system_packages() {
    local manager
    manager="$(detect_package_manager || true)"

    case "$manager" in
        apt)
            run_privileged env DEBIAN_FRONTEND=noninteractive apt-get update
            run_privileged env DEBIAN_FRONTEND=noninteractive apt-get install -y \
                ca-certificates \
                curl \
                build-essential \
                python3 \
                python3-pip \
                python3-venv
            ;;
        dnf)
            run_privileged dnf install -y \
                ca-certificates \
                curl \
                gcc \
                gcc-c++ \
                make \
                nodejs \
                npm \
                python3 \
                python3-pip
            ;;
        yum)
            run_privileged yum install -y \
                ca-certificates \
                curl \
                gcc \
                gcc-c++ \
                make \
                nodejs \
                npm \
                python3 \
                python3-pip
            ;;
        apk)
            run_privileged apk add --no-cache \
                ca-certificates \
                curl \
                build-base \
                nodejs \
                npm \
                py3-pip \
                python3 \
                py3-virtualenv
            ;;
        pacman)
            run_privileged pacman -Sy --needed --noconfirm \
                base-devel \
                ca-certificates \
                curl \
                nodejs \
                npm \
                python \
                python-pip
            ;;
        *)
            die "gerenciador de pacotes nao encontrado. Instale Python 3.11+, python3-venv, curl, Node.js e npm."
            ;;
    esac
}

node_version_satisfies_frontend() {
    local version="${1#v}"
    local major minor patch

    IFS='.' read -r major minor patch <<< "$version"
    patch="${patch:-0}"

    [[ "$major" =~ ^[0-9]+$ ]] || return 1
    [[ "$minor" =~ ^[0-9]+$ ]] || return 1
    [[ "$patch" =~ ^[0-9]+$ ]] || return 1

    if [ "$major" -eq 20 ]; then
        [ "$minor" -ge 19 ]
        return
    fi

    if [ "$major" -eq 22 ]; then
        [ "$minor" -ge 12 ]
        return
    fi

    [ "$major" -gt 22 ]
}

python_version_satisfies_backend() {
    local version="$1"
    local major minor patch

    IFS='.' read -r major minor patch <<< "$version"
    patch="${patch:-0}"

    [[ "$major" =~ ^[0-9]+$ ]] || return 1
    [[ "$minor" =~ ^[0-9]+$ ]] || return 1
    [[ "$patch" =~ ^[0-9]+$ ]] || return 1

    [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; }
}

python_venv_available() {
    local python_bin="$1"

    "$python_bin" -m venv --help >/dev/null 2>&1
}

resolve_system_python() {
    local candidate version

    for candidate in "${AIDEAL_PYTHON:-}" python3.14 python3.13 python3.12 python3.11 python3; do
        [ -n "$candidate" ] || continue
        command_exists "$candidate" || continue
        version="$("$candidate" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
        if python_version_satisfies_backend "$version"; then
            printf '%s\n' "$candidate"
            return
        fi
    done

    return 1
}

base_system_dependencies_present() {
    local system_python

    command_exists curl || return 1
    system_python="$(resolve_system_python || true)"
    [ -n "$system_python" ] || return 1
    python_venv_available "$system_python" || return 1
}

install_node_from_nodesource() {
    local setup_script="/tmp/aideal-nodesource-setup.sh"

    command_exists curl || die "curl nao encontrado para instalar Node.js"
    log "  Instalando Node.js 22 LTS via NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_22.x -o "$setup_script"
    run_privileged bash "$setup_script"
    rm -f "$setup_script"
    run_privileged env DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
}

ensure_node_toolchain() {
    local manager node_version

    if command_exists node && command_exists npm; then
        node_version="$(node --version)"
        if node_version_satisfies_frontend "$node_version"; then
            log "  Node.js OK: $node_version"
            log "  npm OK: $(npm --version)"
            return
        fi
        log "  Node.js $node_version nao atende ao build do frontend."
    else
        log "  Node.js/npm nao encontrados."
    fi

    if [ "${AIDEAL_SKIP_SYSTEM_INSTALL:-0}" = "1" ]; then
        die "Node.js/npm ausentes ou incompativeis, e AIDEAL_SKIP_SYSTEM_INSTALL=1 desativou a instalacao automatica."
    fi

    manager="$(detect_package_manager || true)"
    if [ "$manager" = "apt" ]; then
        install_node_from_nodesource
    else
        install_base_system_packages
    fi

    command_exists node || die "Node.js nao foi instalado corretamente"
    command_exists npm || die "npm nao foi instalado corretamente"
    node_version="$(node --version)"
    node_version_satisfies_frontend "$node_version" || die "Node.js $node_version ainda e incompativel. Use Node.js 20.19+ ou 22.12+."
    log "  Node.js OK: $node_version"
    log "  npm OK: $(npm --version)"
}

ensure_system_dependencies() {
    if [ "${AIDEAL_SKIP_SYSTEM_INSTALL:-0}" = "1" ]; then
        log "  Instalacao de dependencias do sistema ignorada por AIDEAL_SKIP_SYSTEM_INSTALL=1."
        return
    fi

    if base_system_dependencies_present; then
        log "  Dependencias base do sistema ja estao disponiveis."
    else
        install_base_system_packages
    fi

    ensure_node_toolchain
}

prepare_backend() {
    local system_python

    cd "$BACKEND_DIR"

    system_python="$(resolve_system_python || true)"
    [ -n "$system_python" ] || die "Python 3.11+ nao encontrado apos instalacao das dependencias."

    if [ ! -d "$VENV_DIR" ]; then
        log "  Criando ambiente virtual com $system_python..."
        "$system_python" -m venv "$VENV_DIR"
    fi

    "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
    "$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel --quiet

    # Versões fixadas garantem paridade com o ambiente validado. Sem o lock, o
    # resolver de `pip install -e .` (constraints `>=` no pyproject) pode
    # escolher versões diferentes de openpyxl/et_xmlfile/pandas por servidor —
    # o que corrompe o OOXML do DRE (templates/writer.py) e diverge a ingestão.
    # O lock é reaplicado mesmo em venv pré-existente (faz up/downgrade).
    if [ -f "$BACKEND_DIR/requirements.txt" ]; then
        "$PYTHON_BIN" -m pip install -r "$BACKEND_DIR/requirements.txt" --quiet
        "$PYTHON_BIN" -m pip install -e . --no-deps --quiet
    else
        log "  AVISO: requirements.txt ausente; instalando sem lock de versões."
        "$PYTHON_BIN" -m pip install -e . --quiet
    fi
}

install_frontend_dependencies() {
    cd "$FRONTEND_DIR"

    if [ -f "package-lock.json" ]; then
        npm ci --include=dev --silent
    else
        npm install --include=dev --silent
    fi
}

build_frontend() {
    cd "$FRONTEND_DIR"
    npm run build
}

prepare_frontend() {
    ensure_node_toolchain
    install_frontend_dependencies
    build_frontend
}

ensure_persistent_directories() {
    mkdir -p "$PROJECT_DIR/logs/tmp"
    mkdir -p "$PROJECT_DIR/output"
    mkdir -p "$PROJECT_DIR/data"
    mkdir -p "$PROJECT_DIR/backend/config/template_baselines"

    if [ ! -f "$PROJECT_DIR/data/aideal.db" ]; then
        log "  Banco data/aideal.db nao existe; as migracoes criarao uma base vazia."
    else
        log "  Banco preservado: data/aideal.db"
    fi
}

ensure_template_baselines() {
    local dre_baseline="$PROJECT_DIR/backend/config/template_baselines/dre_template_baseline.json"
    local fc_baseline="$PROJECT_DIR/backend/config/template_baselines/fluxo_template_baseline.json"

    if [ ! -f "$dre_baseline" ] || [ ! -f "$fc_baseline" ]; then
        cd "$PROJECT_DIR"
        "$PYTHON_BIN" scripts/template_integrity.py capture-defaults
    else
        log "  Baselines ja existem."
    fi
}

start_application() {
    cd "$BACKEND_DIR"
    exec "$PYTHON_BIN" -m uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --proxy-headers \
        --timeout-keep-alive 30
}

main() {
    log "=== AIDEAL GoFlowOS MVP - Producao Linux ==="
    log "Diretorio: $PROJECT_DIR"
    log "Bind: http://${HOST}:${PORT}"

    log ""
    log "[1/6] Instalando/verificando dependencias do sistema..."
    ensure_system_dependencies

    log ""
    log "[2/6] Preparando backend Python..."
    prepare_backend

    log ""
    log "[3/6] Instalando dependencias e gerando frontend de producao..."
    prepare_frontend

    log ""
    log "[4/6] Verificando diretorios persistentes..."
    ensure_persistent_directories

    log ""
    log "[5/6] Verificando baseline dos templates..."
    ensure_template_baselines

    log ""
    log "[6/6] Subindo aplicacao final..."
    log "  Frontend estatico: frontend/dist"
    log "  API + frontend: http://${HOST}:${PORT}"
    log "  Health: http://${HOST}:${PORT}/health"
    log "  Ready: http://${HOST}:${PORT}/ready"
    log ""
    log "Pressione Ctrl+C para parar."

    start_application
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
