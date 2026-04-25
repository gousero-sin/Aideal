"""Exporter — orquestra a geração de arquivos finais e logs de execução."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from ..config import settings
from ..contracts.common import FlowType, ProcessingLog, ProcessingStatus

logger = logging.getLogger(__name__)


class Exporter:
    """Gerencia saída de arquivos processados e logs de execução."""

    def __init__(
        self,
        base_dir: Path | None = None,
        logs_dir: Path | None = None,
        temp_dir: Path | None = None,
        output_dir: Path | None = None,
    ):
        self.base_dir = Path(base_dir) if base_dir else settings.base_dir
        self.logs_dir = Path(logs_dir) if logs_dir else settings.logs_dir
        self.temp_dir = Path(temp_dir) if temp_dir else settings.temp_dir
        self.output_dir = Path(output_dir) if output_dir else self.base_dir / "output"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def criar_log(self, fluxo: FlowType, arquivos_entrada: list[str]) -> ProcessingLog:
        """Cria um novo log de processamento."""
        return ProcessingLog(
            id=str(uuid.uuid4())[:8],
            fluxo=fluxo,
            status=ProcessingStatus.PENDING,
            arquivo_entrada=arquivos_entrada,
        )

    def gerar_nome_saida(self, fluxo: FlowType, competencia: str) -> str:
        """Gera nome padronizado para o arquivo de saída."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tipo = "DRE" if fluxo == FlowType.DRE else "Fluxo_Caixa"
        return f"AIDEAL_{tipo}_{competencia}_{timestamp}.xlsx"

    def caminho_saida(self, nome_arquivo: str) -> Path:
        """Retorna caminho completo para arquivo de saída."""
        return self.output_dir / nome_arquivo

    def salvar_log(self, log: ProcessingLog) -> Path:
        """Persiste log de processamento em arquivo JSON."""
        log_file = self.logs_dir / f"log_{log.id}_{log.fluxo.value}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Log salvo: {log_file.name}")
        return log_file

    def limpar_temporarios(self) -> int:
        """Remove arquivos temporários (RNF-06)."""
        count = 0
        if self.temp_dir.exists():
            for f in self.temp_dir.iterdir():
                if f.is_file():
                    f.unlink()
                    count += 1
        if count > 0:
            logger.info(f"Temporários removidos: {count} arquivo(s)")
        return count

    def localizar_log(self, processamento_id: str) -> Path | None:
        """Localiza o arquivo de log de um processamento pelo id."""
        candidatos = sorted(self.logs_dir.glob(f"log_{processamento_id}_*.json"), reverse=True)
        return candidatos[0] if candidatos else None

    def carregar_log(self, processamento_id: str) -> ProcessingLog | None:
        """Carrega um log salvo a partir do id do processamento."""
        log_path = self.localizar_log(processamento_id)
        if not log_path or not log_path.exists():
            return None

        with open(log_path, encoding="utf-8") as f:
            raw = json.load(f)
        return ProcessingLog.model_validate(raw)
