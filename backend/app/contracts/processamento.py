"""Contratos de resposta para processamento DRE."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import FlowType, ProcessingStatus, ValidationError


class DREProcessamentoResponse(BaseModel):
    """Resposta padronizada de execução do motor DRE."""

    id: str
    fluxo: FlowType = Field(default=FlowType.DRE)
    status: ProcessingStatus
    valido: bool
    arquivo_entrada: list[str] = Field(default_factory=list)
    arquivo_saida: str | None = None
    download_url: str | None = None
    total_registros: int = 0
    registros_processados: int = 0
    erros: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)
    inicio: datetime | None = None
    fim: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
