"""Configuração central da aplicação AIDEAL MVP."""

from pathlib import Path

from pydantic_settings import BaseSettings

# Raiz do projeto: usada para localizar o .env independente do CWD do processo.
_BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "AIDEAL GoFlowOS MVP"
    version: str = "1.0.0"
    debug: bool = False

    # Diretórios base
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    templates_dir: Path = base_dir / "templates"
    exemplos_dir: Path = base_dir / "exemplos"
    config_dir: Path = base_dir / "backend" / "config"
    logs_dir: Path = base_dir / "logs"
    temp_dir: Path = base_dir / "logs" / "tmp"
    output_dir: Path = base_dir / "output"
    frontend_dist_dir: Path = base_dir / "frontend" / "dist"
    data_dir: Path = base_dir / "data"
    db_path: Path = data_dir / "aideal.db"

    # Templates oficiais
    template_dre: str = "DRE AIDEAL - 05 2025  - obra.xlsx"
    template_fluxo: str = "Fluxo de Caixa A Ideal - 07 2025.xlsx"

    # Limites
    max_upload_size_mb: int = 50
    max_files_per_batch: int = 20
    upload_chunk_size_bytes: int = 1024 * 1024
    allowed_upload_extensions: str = ".xls,.xlsx"

    # Produção local
    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000"
    sqlite_timeout_seconds: float = 30.0
    sqlite_busy_timeout_ms: int = 5000

    # Admin Banco
    admin_username: str = ""
    admin_password: str = ""
    admin_password_hash: str = ""
    admin_session_secret: str = ""
    admin_session_max_age_seconds: int = 8 * 60 * 60
    admin_cookie_secure: bool = False

    @property
    def template_dre_path(self) -> Path:
        return self.templates_dir / "dre" / self.template_dre

    @property
    def template_fluxo_path(self) -> Path:
        return self.templates_dir / "fluxo_caixa" / self.template_fluxo

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_upload_extensions_set(self) -> set[str]:
        return {
            ext.strip().lower()
            for ext in self.allowed_upload_extensions.split(",")
            if ext.strip()
        }

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = {
        "env_prefix": "AIDEAL_",
        "env_file": str(_BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
