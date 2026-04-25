"""Configuração central da aplicação AIDEAL MVP."""

from pathlib import Path

from pydantic_settings import BaseSettings


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
    data_dir: Path = base_dir / "data"
    db_path: Path = data_dir / "aideal.db"

    # Templates oficiais
    template_dre: str = "DRE AIDEAL - 05 2025  - obra.xlsx"
    template_fluxo: str = "Fluxo de Caixa A Ideal - 07 2025.xlsx"

    # Limites
    max_upload_size_mb: int = 50
    max_files_per_batch: int = 20

    @property
    def template_dre_path(self) -> Path:
        return self.templates_dir / "dre" / self.template_dre

    @property
    def template_fluxo_path(self) -> Path:
        return self.templates_dir / "fluxo_caixa" / self.template_fluxo

    model_config = {"env_prefix": "AIDEAL_"}


settings = Settings()
