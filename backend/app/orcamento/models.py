"""Objetos imutáveis expostos pelo domínio de Orçamento."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

# Ciclo de vida do ORÇAMENTO, conforme Orc_Proposta_Técnica.md.
# Os estados 'Em elaboração'/'Pronta para emissão' pertencem à PROPOSTA TÉCNICA.
SITUACAO_RASCUNHO = "rascunho"
SITUACAO_EM_REVISAO = "em_revisao"
SITUACAO_PRONTO_PARA_PROPOSTA = "pronto_para_proposta"
SITUACAO_EMITIDO = "emitido"
SITUACAO_INATIVO = "inativo"

SITUACOES = (
    SITUACAO_RASCUNHO,
    SITUACAO_EM_REVISAO,
    SITUACAO_PRONTO_PARA_PROPOSTA,
    SITUACAO_EMITIDO,
    SITUACAO_INATIVO,
)

# Modalidade do cabeçalho canônico: apenas HH ou Spot.
MODALIDADES = ("HH", "Spot", "Rotina", "m²")

# Toda revisão grava a versão das regras aplicadas, conforme RNF-04.
# A versão corrente acompanha o cálculo DFP v2; snapshots legados continuam
# identificados explicitamente como v1 pelo service.
VERSAO_REGRAS = "orcamento.regras.v2"

# Validade comercial confirmada em 2026-08-26: 30 dias corridos a partir da emissão.
VALIDADE_PADRAO_DIAS = 30

# O código é gerado pelo sistema a partir de um sequencial contínuo.
CODIGO_PREFIXO = "ORC"
CODIGO_DIGITOS = 4


def formatar_codigo(sequencial: int) -> str:
    """ORC-0001. Sequenciais acima do limite apenas crescem em dígitos."""
    if sequencial < 1:
        raise ValueError("sequencial deve ser positivo")
    return f"{CODIGO_PREFIXO}-{sequencial:0{CODIGO_DIGITOS}d}"


def calcular_validade(emissao: date, dias: int = VALIDADE_PADRAO_DIAS) -> date:
    """válido_até = data_de_emissão + 30 dias corridos; o último dia ainda vale."""
    return emissao + timedelta(days=dias)


@dataclass(frozen=True, slots=True)
class Revisao:
    id: str
    orcamento_id: str
    numero: int
    situacao: str
    escopo: str
    modalidade: str | None
    regiao: str | None
    prazo_execucao_dias: int | None
    saldo_mao_de_obra: float | None
    dados_contratante: str | None
    mobilizacao: str | None
    desmobilizacao: str | None
    area_unidade_base: str | None
    regime_tributario: str | None
    dfp: dict[str, Any]
    versao_regras: str
    autor_user_id: str
    motivo: str | None
    emitido_em: datetime | None
    valido_ate: date | None
    created_at: datetime

    def vencida_em(self, agora: datetime) -> bool:
        """O último dia integra o período válido; o vencimento vale no dia seguinte."""
        if self.valido_ate is None:
            return False
        return agora.date() > self.valido_ate

    def to_dict(self, *, agora: datetime | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "orcamento_id": self.orcamento_id,
            "numero": self.numero,
            "situacao": self.situacao,
            "escopo": self.escopo,
            "modalidade": self.modalidade,
            "regiao": self.regiao,
            "prazo_execucao_dias": self.prazo_execucao_dias,
            "saldo_mao_de_obra": self.saldo_mao_de_obra,
            "dados_contratante": self.dados_contratante,
            "mobilizacao": self.mobilizacao,
            "desmobilizacao": self.desmobilizacao,
            "area_unidade_base": self.area_unidade_base,
            "regime_tributario": self.regime_tributario,
            "dfp": deepcopy(self.dfp),
            "versao_regras": self.versao_regras,
            "motivo": self.motivo,
            "emitido_em": self.emitido_em.isoformat() if self.emitido_em else None,
            "valido_ate": self.valido_ate.isoformat() if self.valido_ate else None,
            "vencida": self.vencida_em(agora) if agora is not None else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class Orcamento:
    id: str
    sequencial: int
    codigo: str
    contratante: str
    criado_por_user_id: str
    revisoes: tuple[Revisao, ...]
    created_at: datetime
    updated_at: datetime

    @property
    def revisao_atual(self) -> Revisao | None:
        """A revisão de maior número; revisões anteriores nunca são sobrescritas."""
        return max(self.revisoes, key=lambda item: item.numero, default=None)

    def to_dict(self, *, agora: datetime | None = None) -> dict[str, Any]:
        atual = self.revisao_atual
        return {
            "id": self.id,
            "sequencial": self.sequencial,
            "codigo": self.codigo,
            "codigo_revisao": f"{self.codigo}-R{atual.numero}" if atual else self.codigo,
            "contratante": self.contratante,
            "revisao_atual": atual.to_dict(agora=agora) if atual else None,
            "revisoes": [item.to_dict(agora=agora) for item in self.revisoes],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SituacaoEvento:
    id: str
    revisao_id: str
    situacao: str
    motivo: str
    responsavel_user_id: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "revisao_id": self.revisao_id,
            "situacao": self.situacao,
            "motivo": self.motivo,
            "responsavel_user_id": self.responsavel_user_id,
            "created_at": self.created_at.isoformat(),
        }
