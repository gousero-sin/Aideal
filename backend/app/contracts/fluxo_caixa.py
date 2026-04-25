"""Contrato de dados normalizado para o fluxo de Caixa."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from .common import ValidationError


class TipoMovimento(str, Enum):
    """Tipo de movimentação bancária."""
    CREDITO = "credito"
    DEBITO = "debito"
    TRANSFERENCIA = "transferencia"


class FCMovimento(BaseModel):
    """Movimento individual normalizado do Fluxo de Caixa.

    Campos essenciais conforme Apêndice A do plano:
    - Data Mov.: data da movimentação bancária
    - Tipo: crédito, débito ou transferência
    - Descrição: histórico da transação
    - Valor: montante da operação
    - Saldo: saldo após lançamento
    - Conta Gerencial/Classificação: categoria financeira para consolidação
    - Banco/Origem: identificação da instituição fonte
    """

    data_movimento: date = Field(..., description="Data da movimentação bancária")
    tipo: TipoMovimento = Field(..., description="Tipo: crédito, débito ou transferência")
    descricao: str = Field(..., description="Histórico/descrição da transação")
    valor: Decimal = Field(..., description="Montante da operação")
    saldo: Decimal | None = Field(None, description="Saldo após lançamento")
    classificacao: str = Field(default="", description="Categoria financeira para consolidação")
    conta_gerencial: str = Field(default="", description="Conta gerencial de agrupamento")
    banco_origem: str = Field(..., description="Identificação do banco/instituição fonte")

    # Campos de rastreabilidade
    arquivo_origem: str = Field(default="", description="Arquivo de origem")
    linha_origem: int | None = Field(None, description="Linha de origem no arquivo bruto")
    aba_origem: str | None = Field(None, description="Aba de origem no arquivo bruto")


class FCLote(BaseModel):
    """Lote consolidado de movimentos do Fluxo de Caixa."""

    periodo: str = Field(..., description="Período de referência (MM/AAAA)")
    data_processamento: datetime = Field(default_factory=datetime.now)
    arquivos_origem: list[str] = Field(default_factory=list)
    bancos: list[str] = Field(default_factory=list)
    movimentos: list[FCMovimento] = Field(default_factory=list)

    @property
    def total_creditos(self) -> Decimal:
        return sum(m.valor for m in self.movimentos if m.tipo == TipoMovimento.CREDITO)

    @property
    def total_debitos(self) -> Decimal:
        return sum(m.valor for m in self.movimentos if m.tipo == TipoMovimento.DEBITO)

    @property
    def total_registros(self) -> int:
        return len(self.movimentos)

    @property
    def bancos_unicos(self) -> list[str]:
        return list(set(m.banco_origem for m in self.movimentos))


class FCValidationResult(BaseModel):
    """Resultado da validação de arquivos do Fluxo de Caixa."""

    valido: bool = True
    arquivos: list[str] = Field(default_factory=list)
    bancos_identificados: list[str] = Field(default_factory=list)
    colunas_encontradas: dict[str, list[str]] = Field(default_factory=dict)
    colunas_esperadas: list[str] = Field(default_factory=list)
    erros: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)
    total_linhas_por_arquivo: dict[str, int] = Field(default_factory=dict)
