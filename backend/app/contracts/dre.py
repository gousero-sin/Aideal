"""Contrato de dados normalizado para o fluxo DRE."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from .common import ValidationError


class DRELancamento(BaseModel):
    """Lançamento individual normalizado do DRE.

    Campos essenciais conforme Apêndice A do plano:
    - Data: data do lançamento financeiro
    - Histórico: identificação textual do lançamento/documento
    - Crédito/Débito: valor de entrada e saída
    - Natureza: classificação financeira origem
    - Centro de Custo / Obra: dimensão de alocação
    - Rubrica/Conta Pai: agrupadores para visão gerencial final
    """

    data: date = Field(..., description="Data do lançamento financeiro")
    historico: str = Field(..., description="Identificação textual do lançamento/documento")
    credito: Decimal = Field(default=Decimal("0"), description="Valor de entrada (crédito)")
    debito: Decimal = Field(default=Decimal("0"), description="Valor de saída (débito)")
    natureza: str = Field(..., description="Código C. gerencial (ex: 1.1.1 - Recebimento de Clientes)")
    classificacao_entrada_saida: str = Field(default="", description="Indicador ENTRADA/SAIDA da coluna CLASSIFICAÇÃO do relatório")
    centro_custo: str = Field(default="", description="Centro de custo / obra")
    rubrica: str = Field(default="", description="Rubrica ou conta pai para agrupamento")
    conta_pai: str = Field(default="", description="Agrupador gerencial superior")

    # Campos de rastreabilidade
    linha_origem: int | None = Field(None, description="Linha de origem no arquivo bruto")
    aba_origem: str | None = Field(None, description="Aba de origem no arquivo bruto")

    @property
    def valor_liquido(self) -> Decimal:
        return self.credito - self.debito


class DRELote(BaseModel):
    """Lote de lançamentos DRE normalizados."""

    competencia: str = Field(..., description="Mês/ano de competência (MM/AAAA)")
    arquivo_origem: str = Field(..., description="Nome do arquivo de entrada")
    data_processamento: datetime = Field(default_factory=datetime.now)
    lancamentos: list[DRELancamento] = Field(default_factory=list)

    @property
    def total_credito(self) -> Decimal:
        return sum(l.credito for l in self.lancamentos)

    @property
    def total_debito(self) -> Decimal:
        return sum(l.debito for l in self.lancamentos)

    @property
    def total_registros(self) -> int:
        return len(self.lancamentos)


class DREValidationResult(BaseModel):
    """Resultado da validação de um arquivo DRE."""

    valido: bool = True
    arquivo: str = ""
    abas_encontradas: list[str] = Field(default_factory=list)
    abas_esperadas: list[str] = Field(default_factory=list)
    colunas_encontradas: list[str] = Field(default_factory=list)
    colunas_esperadas: list[str] = Field(default_factory=list)
    erros: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)
    total_linhas: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
