"""Contracts para persistência de dados financeiros no banco."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from .fluxo_caixa import FCMovimento, TipoMovimento


class DREUpload(BaseModel):
    """Registro de upload de arquivo DRE."""

    id: str = Field(..., description="ID único do upload (UUID)")
    created_at: datetime = Field(default_factory=datetime.now)
    arquivo_nome: str = Field(..., description="Nome original do arquivo")
    arquivo_sha256: str = Field(..., description="Hash SHA256 do arquivo")
    competencia_ano: int = Field(..., ge=2000, le=2100)
    competencia_mes: int = Field(..., ge=1, le=12)
    status: str = Field(default="pending", pattern=r"^(pending|processing|completed|error)$")
    total_linhas: int = Field(default=0)
    linhas_validas: int = Field(default=0)
    linhas_rejeitadas: int = Field(default=0)
    observacao: str | None = None

    def model_to_db(self) -> tuple:
        """Converte modelo para tupla de inserção no banco."""
        return (
            self.id,
            self.created_at.isoformat(),
            self.arquivo_nome,
            self.arquivo_sha256,
            self.competencia_ano,
            self.competencia_mes,
            self.status,
            self.total_linhas,
            self.linhas_validas,
            self.linhas_rejeitadas,
            self.observacao,
        )

    @classmethod
    def from_db_row(cls, row: Any) -> "DREUpload":
        """Cria instância a partir de row do banco."""
        return cls(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            arquivo_nome=row["arquivo_nome"],
            arquivo_sha256=row["arquivo_sha256"],
            competencia_ano=row["competencia_ano"],
            competencia_mes=row["competencia_mes"],
            status=row["status"],
            total_linhas=row["total_linhas"],
            linhas_validas=row["linhas_validas"],
            linhas_rejeitadas=row["linhas_rejeitadas"],
            observacao=row["observacao"],
        )


class DRELancamentoDB(BaseModel):
    """Lançamento DRE persistido no banco de dados."""

    id: int | None = Field(None, description="ID auto-incrementado no banco")
    upload_id: str = Field(..., description="ID do upload pai")
    competencia_ano: int = Field(..., ge=2000, le=2100)
    competencia_mes: int = Field(..., ge=1, le=12)
    data_lancamento: str = Field(..., description="Data do lançamento (ISO format)")
    historico: str = Field(..., description="Histórico/descrição")
    valor_bruto: Decimal = Field(default=Decimal("0"))
    credito: Decimal = Field(default=Decimal("0"))
    debito: Decimal = Field(default=Decimal("0"))
    natureza_raw: str | None = Field(None, description="Natureza original do arquivo")
    natureza_norm: str | None = Field(None, description="Natureza normalizada")
    centro_custo: str | None = Field(None, description="Centro de custo/obra")
    rubrica: str | None = Field(None, description="Rubrica/classificação")
    conta_pai: str | None = Field(None, description="Conta pai/agrupador")
    linha_origem: int | None = Field(None, description="Número da linha no arquivo original")
    hash_linha: str = Field(..., description="Hash único da linha para deduplicação")
    created_at: datetime = Field(default_factory=datetime.now)

    def model_to_db(self) -> tuple:
        """Converte modelo para tupla de inserção no banco."""
        return (
            self.upload_id,
            self.competencia_ano,
            self.competencia_mes,
            self.data_lancamento,
            self.historico,
            float(self.valor_bruto),
            float(self.credito),
            float(self.debito),
            self.natureza_raw,
            self.natureza_norm,
            self.centro_custo,
            self.rubrica,
            self.conta_pai,
            self.linha_origem,
            self.hash_linha,
            self.created_at.isoformat(),
        )

    @classmethod
    def from_db_row(cls, row: Any) -> "DRELancamentoDB":
        """Cria instância a partir de row do banco."""
        return cls(
            id=row["id"],
            upload_id=row["upload_id"],
            competencia_ano=row["competencia_ano"],
            competencia_mes=row["competencia_mes"],
            data_lancamento=row["data_lancamento"],
            historico=row["historico"],
            valor_bruto=Decimal(str(row["valor_bruto"])),
            credito=Decimal(str(row["credito"])),
            debito=Decimal(str(row["debito"])),
            natureza_raw=row["natureza_raw"],
            natureza_norm=row["natureza_norm"],
            centro_custo=row["centro_custo"],
            rubrica=row["rubrica"],
            conta_pai=row["conta_pai"],
            linha_origem=row["linha_origem"],
            hash_linha=row["hash_linha"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @property
    def valor_liquido(self) -> Decimal:
        """Calcula valor líquido (crédito - débito)."""
        return self.credito - self.debito


class DRECompetenciaQuery(BaseModel):
    """Parâmetros para consulta de lançamentos por competência."""

    ano: int = Field(..., ge=2000, le=2100)
    mes: int = Field(..., ge=1, le=12)
    centro_custo: str | None = None
    conta_pai: str | None = None
    natureza: str | None = None


class DREResumoCompetencia(BaseModel):
    """Resumo de lançamentos por competência."""

    competencia_ano: int
    competencia_mes: int
    total_lancamentos: int
    total_credito: Decimal
    total_debito: Decimal
    saldo_liquido: Decimal
    total_contas_pai: int
    total_centros_custo: int


class DREAcumuladoYTD(BaseModel):
    """Dados acumulados YTD (Year to Date) por conta pai."""

    competencia_ano: int
    competencia_mes: int
    conta_pai: str | None
    centro_custo: str | None
    credito_acumulado: Decimal
    debito_acumulado: Decimal
    saldo_acumulado: Decimal
    quantidade_lancamentos: int


class DREIndicadoresManuais(BaseModel):
    """Indicadores DRE informados manualmente por competência na ADM."""

    id: int | None = Field(None, description="ID auto-incrementado no banco")
    competencia_ano: int = Field(..., ge=2000, le=2100)
    competencia_mes: int = Field(..., ge=1, le=12)
    contas_pagar: Decimal = Field(default=Decimal("0"), ge=0)
    contas_receber: Decimal = Field(default=Decimal("0"), ge=0)
    total_impostos_retidos_acima_meta: Decimal = Field(default=Decimal("0"), ge=0)
    total_impostos_retidos: Decimal = Field(default=Decimal("0"), ge=0)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def model_to_db(self) -> tuple:
        """Converte modelo para tupla de upsert no banco."""
        return (
            self.competencia_ano,
            self.competencia_mes,
            float(self.contas_pagar),
            float(self.contas_receber),
            float(self.total_impostos_retidos_acima_meta),
            float(self.total_impostos_retidos),
            self.created_at.isoformat(),
            self.updated_at.isoformat(),
        )

    @classmethod
    def from_db_row(cls, row: Any) -> "DREIndicadoresManuais":
        """Cria instância a partir de row do banco."""
        return cls(
            id=row["id"],
            competencia_ano=row["competencia_ano"],
            competencia_mes=row["competencia_mes"],
            contas_pagar=Decimal(str(row["contas_pagar"])),
            contas_receber=Decimal(str(row["contas_receber"])),
            total_impostos_retidos_acima_meta=Decimal(
                str(row["total_impostos_retidos_acima_meta"])
            ),
            total_impostos_retidos=Decimal(str(row["total_impostos_retidos"])),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class FluxoUpload(BaseModel):
    """Registro de upload de arquivo do Fluxo de Caixa."""

    id: str = Field(..., description="ID único do upload (UUID)")
    created_at: datetime = Field(default_factory=datetime.now)
    arquivo_nome: str = Field(..., description="Nome original do arquivo")
    arquivo_sha256: str = Field(..., description="Hash SHA256 do arquivo")
    competencia_ano: int = Field(..., ge=2000, le=2100)
    competencia_mes: int = Field(..., ge=1, le=12)
    banco: str | None = None
    status: str = Field(default="pending", pattern=r"^(pending|processing|completed|error)$")
    total_linhas: int = Field(default=0)
    linhas_validas: int = Field(default=0)
    linhas_rejeitadas: int = Field(default=0)
    observacao: str | None = None

    def model_to_db(self) -> tuple:
        """Converte modelo para tupla de inserção no banco."""
        return (
            self.id,
            self.created_at.isoformat(),
            self.arquivo_nome,
            self.arquivo_sha256,
            self.competencia_ano,
            self.competencia_mes,
            self.banco,
            self.status,
            self.total_linhas,
            self.linhas_validas,
            self.linhas_rejeitadas,
            self.observacao,
        )

    @classmethod
    def from_db_row(cls, row: Any) -> "FluxoUpload":
        """Cria instância a partir de row do banco."""
        return cls(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            arquivo_nome=row["arquivo_nome"],
            arquivo_sha256=row["arquivo_sha256"],
            competencia_ano=row["competencia_ano"],
            competencia_mes=row["competencia_mes"],
            banco=row["banco"],
            status=row["status"],
            total_linhas=row["total_linhas"],
            linhas_validas=row["linhas_validas"],
            linhas_rejeitadas=row["linhas_rejeitadas"],
            observacao=row["observacao"],
        )


class FluxoMovimentoDB(BaseModel):
    """Movimento de Fluxo de Caixa persistido no banco de dados."""

    id: int | None = Field(None, description="ID auto-incrementado no banco")
    upload_id: str = Field(..., description="ID do upload pai")
    competencia_ano: int = Field(..., ge=2000, le=2100)
    competencia_mes: int = Field(..., ge=1, le=12)
    data_movimento: str = Field(..., description="Data do movimento (ISO format)")
    tipo: str = Field(..., pattern=r"^(credito|debito|transferencia)$")
    descricao: str
    valor: Decimal = Field(default=Decimal("0"))
    saldo: Decimal | None = None
    classificacao: str | None = None
    conta_gerencial: str | None = None
    banco_origem: str
    arquivo_origem: str | None = None
    linha_origem: int | None = None
    aba_origem: str | None = None
    hash_linha: str
    created_at: datetime = Field(default_factory=datetime.now)

    def model_to_db(self) -> tuple:
        """Converte modelo para tupla de inserção no banco."""
        return (
            self.upload_id,
            self.competencia_ano,
            self.competencia_mes,
            self.data_movimento,
            self.tipo,
            self.descricao,
            float(self.valor),
            float(self.saldo) if self.saldo is not None else None,
            self.classificacao,
            self.conta_gerencial,
            self.banco_origem,
            self.arquivo_origem,
            self.linha_origem,
            self.aba_origem,
            self.hash_linha,
            self.created_at.isoformat(),
        )

    @classmethod
    def from_db_row(cls, row: Any) -> "FluxoMovimentoDB":
        """Cria instância a partir de row do banco."""
        saldo = row["saldo"]
        return cls(
            id=row["id"],
            upload_id=row["upload_id"],
            competencia_ano=row["competencia_ano"],
            competencia_mes=row["competencia_mes"],
            data_movimento=row["data_movimento"],
            tipo=row["tipo"],
            descricao=row["descricao"],
            valor=Decimal(str(row["valor"])),
            saldo=Decimal(str(saldo)) if saldo is not None else None,
            classificacao=row["classificacao"],
            conta_gerencial=row["conta_gerencial"],
            banco_origem=row["banco_origem"],
            arquivo_origem=row["arquivo_origem"],
            linha_origem=row["linha_origem"],
            aba_origem=row["aba_origem"],
            hash_linha=row["hash_linha"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @classmethod
    def from_movimento(
        cls,
        movimento: FCMovimento,
        upload_id: str,
        ano: int,
        mes: int,
        hash_linha: str,
    ) -> "FluxoMovimentoDB":
        """Converte movimento de domínio para modelo DB."""
        return cls(
            upload_id=upload_id,
            competencia_ano=ano,
            competencia_mes=mes,
            data_movimento=movimento.data_movimento.isoformat(),
            tipo=movimento.tipo.value,
            descricao=movimento.descricao,
            valor=movimento.valor,
            saldo=movimento.saldo,
            classificacao=movimento.classificacao,
            conta_gerencial=movimento.conta_gerencial,
            banco_origem=movimento.banco_origem,
            arquivo_origem=movimento.arquivo_origem,
            linha_origem=movimento.linha_origem,
            aba_origem=movimento.aba_origem,
            hash_linha=hash_linha,
        )

    def to_movimento(self) -> FCMovimento:
        """Converte registro DB para movimento de domínio."""
        return FCMovimento(
            data_movimento=date.fromisoformat(self.data_movimento),
            tipo=TipoMovimento(self.tipo),
            descricao=self.descricao,
            valor=self.valor,
            saldo=self.saldo,
            classificacao=self.classificacao or "",
            conta_gerencial=self.conta_gerencial or "",
            banco_origem=self.banco_origem,
            arquivo_origem=self.arquivo_origem or "",
            linha_origem=self.linha_origem,
            aba_origem=self.aba_origem,
        )
