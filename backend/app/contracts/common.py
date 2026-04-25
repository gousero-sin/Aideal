"""Contratos comuns compartilhados entre DRE e Fluxo de Caixa."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FlowType(str, Enum):
    """Tipo de fluxo de processamento."""
    DRE = "dre"
    FLUXO_CAIXA = "fluxo_caixa"


class ProcessingStatus(str, Enum):
    """Status do processamento."""
    PENDING = "pending"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ErrorSeverity(str, Enum):
    """Severidade do erro."""
    BLOQUEANTE = "bloqueante"
    WARNING = "warning"


class ValidationError(BaseModel):
    """Erro de validação estruturado."""
    campo: str = Field(..., description="Campo ou coluna com problema")
    mensagem: str = Field(..., description="Descrição clara do erro")
    severidade: ErrorSeverity = Field(..., description="Severidade: bloqueante ou warning")
    linha: int | None = Field(None, description="Linha do erro, se aplicável")
    aba: str | None = Field(None, description="Aba/sheet de origem")
    sugestao: str | None = Field(None, description="Ação sugerida ao usuário")


class ProcessingLog(BaseModel):
    """Log de execução do processamento."""
    id: str = Field(..., description="Identificador único do processamento")
    fluxo: FlowType
    status: ProcessingStatus
    inicio: datetime = Field(default_factory=datetime.now)
    fim: datetime | None = None
    arquivo_entrada: list[str] = Field(default_factory=list)
    arquivo_saida: str | None = None
    total_registros: int = 0
    registros_processados: int = 0
    erros: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def tem_bloqueante(self) -> bool:
        return any(e.severidade == ErrorSeverity.BLOQUEANTE for e in self.erros)

    def adicionar_erro(
        self,
        campo: str,
        mensagem: str,
        severidade: ErrorSeverity = ErrorSeverity.BLOQUEANTE,
        **kwargs,
    ) -> None:
        erro = ValidationError(campo=campo, mensagem=mensagem, severidade=severidade, **kwargs)
        if severidade == ErrorSeverity.BLOQUEANTE:
            self.erros.append(erro)
        else:
            self.warnings.append(erro)

    def finalizar(self, status: ProcessingStatus, arquivo_saida: str | None = None) -> None:
        self.status = status
        self.fim = datetime.now()
        self.arquivo_saida = arquivo_saida
