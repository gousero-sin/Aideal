import shlex
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "subir-producao.sh"
VALIDATE_PATH = ROOT_DIR / "scripts" / "validate-prod.sh"


def run_bash(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_subir_producao_define_funcoes_sem_executar_ao_ser_carregado():
    result = run_bash(
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        "declare -f main >/dev/null; "
        "declare -f install_frontend_dependencies >/dev/null"
    )

    assert result.returncode == 0, result.stderr
    assert "Produção Linux" not in result.stdout


def test_host_padrao_expoe_app_para_rede_local():
    result = run_bash(f"source {shlex.quote(str(SCRIPT_PATH))}; printf '%s' \"$HOST\"")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0.0.0.0"


def test_host_pode_ser_restrito_por_variavel_de_ambiente():
    result = run_bash(
        f"AIDEAL_HOST=127.0.0.1 source {shlex.quote(str(SCRIPT_PATH))}; "
        "printf '%s' \"$HOST\""
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "127.0.0.1"


def _fake_nproc(tmp_path: Path, cpus: int) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    nproc = bin_dir / "nproc"
    nproc.write_text(f"#!/usr/bin/env bash\nprintf '{cpus}\\n'\n", encoding="utf-8")
    nproc.chmod(0o755)
    return bin_dir


def test_workers_padrao_usa_cpus_ate_quatro(tmp_path):
    bin_dir = _fake_nproc(tmp_path, 2)
    result = run_bash(
        "unset AIDEAL_WORKERS; "
        f"export PATH={shlex.quote(str(bin_dir))}:$PATH; "
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        "printf '%s' \"$WORKERS\""
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "2"


def test_workers_padrao_limita_em_quatro(tmp_path):
    bin_dir = _fake_nproc(tmp_path, 16)
    result = run_bash(
        "unset AIDEAL_WORKERS; "
        f"export PATH={shlex.quote(str(bin_dir))}:$PATH; "
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        "printf '%s' \"$WORKERS\""
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "4"


def test_workers_pode_ser_definido_por_variavel_de_ambiente():
    result = run_bash(
        f"AIDEAL_WORKERS=1 source {shlex.quote(str(SCRIPT_PATH))}; printf '%s' \"$WORKERS\""
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1"


def test_workers_invalido_aborta_antes_de_subir():
    result = run_bash(
        f"AIDEAL_WORKERS=zero source {shlex.quote(str(SCRIPT_PATH))}; start_application"
    )

    assert result.returncode != 0
    assert "AIDEAL_WORKERS" in result.stderr


def test_instalacao_frontend_roda_npm_ci_com_dev_deps_mesmo_com_node_modules(tmp_path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    (frontend_dir / "node_modules").mkdir()
    log_path = tmp_path / "npm.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npm_stub = bin_dir / "npm"
    npm_stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$NPM_CALL_LOG"\n',
        encoding="utf-8",
    )
    npm_stub.chmod(0o755)

    result = run_bash(
        "set -euo pipefail; "
        f"export PATH={shlex.quote(str(bin_dir))}:$PATH; "
        f"export NPM_CALL_LOG={shlex.quote(str(log_path))}; "
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        f"FRONTEND_DIR={shlex.quote(str(frontend_dir))}; "
        "install_frontend_dependencies"
    )

    assert result.returncode == 0, result.stderr
    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "ci --include=dev --silent"
    ]


def test_instalacao_frontend_usa_npm_install_com_dev_deps_sem_lockfile(tmp_path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    log_path = tmp_path / "npm.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npm_stub = bin_dir / "npm"
    npm_stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$NPM_CALL_LOG"\n',
        encoding="utf-8",
    )
    npm_stub.chmod(0o755)

    result = run_bash(
        "set -euo pipefail; "
        f"export PATH={shlex.quote(str(bin_dir))}:$PATH; "
        f"export NPM_CALL_LOG={shlex.quote(str(log_path))}; "
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        f"FRONTEND_DIR={shlex.quote(str(frontend_dir))}; "
        "install_frontend_dependencies"
    )

    assert result.returncode == 0, result.stderr
    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "install --include=dev --silent"
    ]


def test_validacao_node_aceita_apenas_versoes_compativeis_com_frontend():
    result = run_bash(
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        "node_version_satisfies_frontend 20.19.0; "
        "node_version_satisfies_frontend 22.12.0; "
        "! node_version_satisfies_frontend 20.18.9; "
        "! node_version_satisfies_frontend 18.20.0"
    )

    assert result.returncode == 0, result.stderr


def test_skip_system_install_nao_tenta_corrigir_node_incompativel(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    node_stub = bin_dir / "node"
    node_stub.write_text("#!/usr/bin/env bash\necho v18.20.0\n", encoding="utf-8")
    node_stub.chmod(0o755)
    npm_stub = bin_dir / "npm"
    npm_stub.write_text("#!/usr/bin/env bash\necho 10.0.0\n", encoding="utf-8")
    npm_stub.chmod(0o755)

    result = run_bash(
        "set -euo pipefail; "
        f"export PATH={shlex.quote(str(bin_dir))}:$PATH; "
        "export AIDEAL_SKIP_SYSTEM_INSTALL=1; "
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        "ensure_node_toolchain"
    )

    assert result.returncode != 0
    assert "AIDEAL_SKIP_SYSTEM_INSTALL=1" in result.stderr


def test_dependencias_base_nao_forcam_instalador_quando_toolchain_existe(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python_stub = bin_dir / "python-ok"
    python_stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "${1:-}" = "-c" ]; then echo "3.12.1"; exit 0; fi\n'
        'if [ "${1:-}" = "-m" ] && [ "${2:-}" = "venv" ]; then exit 0; fi\n'
        "exit 0\n",
        encoding="utf-8",
    )
    python_stub.chmod(0o755)
    curl_stub = bin_dir / "curl"
    curl_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    curl_stub.chmod(0o755)

    result = run_bash(
        "set -euo pipefail; "
        f"export PATH={shlex.quote(str(bin_dir))}:$PATH; "
        "export AIDEAL_PYTHON=python-ok; "
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        "base_system_dependencies_present"
    )

    assert result.returncode == 0, result.stderr


def test_url_publica_padrao_usa_nome_goflowaideal():
    result = run_bash(
        "unset AIDEAL_PUBLIC_URL AIDEAL_PORT AIDEAL_CORS_ORIGINS; "
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        "printf '%s|%s' \"$PUBLIC_URL\" \"$AIDEAL_CORS_ORIGINS\""
    )

    assert result.returncode == 0, result.stderr
    public_url, cors = result.stdout.split("|")
    assert public_url == "http://goflowaideal.local:8000"
    assert cors.split(",") == [
        "http://goflowaideal.local:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]


def test_url_publica_acompanha_porta_configurada():
    result = run_bash(
        "unset AIDEAL_PUBLIC_URL AIDEAL_CORS_ORIGINS; "
        f"AIDEAL_PORT=8010 source {shlex.quote(str(SCRIPT_PATH))}; "
        "printf '%s' \"$PUBLIC_URL\""
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "http://goflowaideal.local:8010"


def test_url_publica_pode_ser_sobrescrita_por_variavel_de_ambiente():
    result = run_bash(
        "unset AIDEAL_CORS_ORIGINS; "
        "export AIDEAL_PUBLIC_URL=http://goflowaideal.local:8000/; "
        f"source {shlex.quote(str(SCRIPT_PATH))}; "
        "printf '%s|%s' \"$PUBLIC_URL\" \"$AIDEAL_CORS_ORIGINS\""
    )

    assert result.returncode == 0, result.stderr
    public_url, cors = result.stdout.split("|")
    # Origem CORS não aceita barra final; o script a remove.
    assert public_url == "http://goflowaideal.local:8000"
    assert cors.split(",")[0] == "http://goflowaideal.local:8000"


def run_validacao_cors(cors_origins: str, public_url: str = "") -> subprocess.CompletedProcess[str]:
    return run_bash(
        f"export AIDEAL_CORS_ORIGINS={shlex.quote(cors_origins)}; "
        f"export AIDEAL_PUBLIC_URL={shlex.quote(public_url)}; "
        f"source {shlex.quote(str(VALIDATE_PATH))}; "
        "check_local_config"
    )


def test_validate_prod_aceita_origem_goflowaideal_junto_de_loopback():
    result = run_validacao_cors(
        "http://goflowaideal:8000,http://127.0.0.1:8000,http://localhost:8000"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "limites e CORS locais OK" in result.stdout


def test_validate_prod_aceita_origem_publica_configurada():
    result = run_validacao_cors(
        "http://app-interno:9000,http://127.0.0.1:9000",
        public_url="http://app-interno:9000",
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_prod_rejeita_curinga_e_origem_externa():
    curinga = run_validacao_cors("*")
    externa = run_validacao_cors("http://goflowaideal.example.com:8000")

    assert curinga.returncode != 0
    assert externa.returncode != 0
