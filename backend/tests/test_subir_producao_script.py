import shlex
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "subir-producao.sh"


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
