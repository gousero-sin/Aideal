"""Casos de uso do módulo de Orçamento."""

from __future__ import annotations

import math
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import OrcamentoDatabase
from .dfp import build_default_dfp_snapshot, compute_dfp_summary, normalize_dfp_payload
from .exceptions import InvalidOrcamentoInputError, InvalidSituacaoTransitionError
from .models import (
    MODALIDADES,
    SITUACAO_EM_REVISAO,
    SITUACAO_EMITIDO,
    SITUACAO_INATIVO,
    SITUACAO_PRONTO_PARA_PROPOSTA,
    SITUACAO_RASCUNHO,
    VALIDADE_PADRAO_DIAS,
    Orcamento,
    Revisao,
    SituacaoEvento,
    calcular_validade,
)
from .repository import OrcamentoRepository

MAX_TEXTO_CURTO = 120
MAX_TEXTO_LONGO = 2000
MAX_ESCOPO = 4000
MAX_MOTIVO = 500
MAX_SALDO_MAO_DE_OBRA = 1_000_000_000
REVISAO_CAMPOS_HERDAVEIS = (
    "escopo",
    "modalidade",
    "regiao",
    "prazo_execucao_dias",
    "saldo_mao_de_obra",
    "dados_contratante",
    "mobilizacao",
    "desmobilizacao",
    "area_unidade_base",
    "regime_tributario",
    "dfp",
)
REVISAO_CAMPOS_ENTRADA = frozenset((*REVISAO_CAMPOS_HERDAVEIS, "motivo"))

# Ciclo de vida de Orc_Proposta_Técnica.md:
# Rascunho -> Em revisão -> Pronto para proposta -> Emitido -> Inativo.
# Uma revisão inativa nunca é reativada: a saída é criar uma nova revisão.
TRANSICOES_PERMITIDAS: dict[str, frozenset[str]] = {
    SITUACAO_RASCUNHO: frozenset({SITUACAO_EM_REVISAO, SITUACAO_INATIVO}),
    SITUACAO_EM_REVISAO: frozenset(
        {SITUACAO_RASCUNHO, SITUACAO_PRONTO_PARA_PROPOSTA, SITUACAO_INATIVO}
    ),
    SITUACAO_PRONTO_PARA_PROPOSTA: frozenset(
        {SITUACAO_EM_REVISAO, SITUACAO_EMITIDO, SITUACAO_INATIVO}
    ),
    SITUACAO_EMITIDO: frozenset({SITUACAO_INATIVO}),
    SITUACAO_INATIVO: frozenset(),
}

# Campos obrigatórios do cabeçalho canônico para avançar além de Rascunho.
CABECALHO_OBRIGATORIO = (
    ("escopo", "Escopo do Serviço"),
    ("modalidade", "Modalidade do Trabalho"),
    ("regiao", "Região da Obra"),
    ("prazo_execucao_dias", "Prazo de execução"),
    ("dados_contratante", "Dados da Contratante"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrcamentoService:
    """Interface de integração do módulo de Orçamento do GoFlow."""

    def __init__(
        self,
        repository: OrcamentoRepository,
        *,
        clock: Callable[[], datetime] = _utc_now,
        validade_dias: int = VALIDADE_PADRAO_DIAS,
    ):
        if validade_dias <= 0:
            raise ValueError("validade_dias deve ser positivo")
        self.repository = repository
        self.clock = clock
        self.validade_dias = validade_dias

    # -- validação -------------------------------------------------------

    @staticmethod
    def _validar_payload(dados: Any, *, campos: frozenset[str], nome: str) -> dict[str, Any]:
        if not isinstance(dados, dict):
            raise InvalidOrcamentoInputError(f"{nome} deve ser um objeto")
        desconhecidos = set(dados) - campos
        if desconhecidos:
            raise InvalidOrcamentoInputError(
                f"Campos de {nome} desconhecidos: " + ", ".join(sorted(desconhecidos))
            )
        return dados

    @staticmethod
    def _texto_obrigatorio(valor: Any, campo: str, limite: int) -> str:
        if not isinstance(valor, str) or not valor.strip():
            raise InvalidOrcamentoInputError(f"{campo} é obrigatório")
        limpo = valor.strip()
        if len(limpo) > limite:
            raise InvalidOrcamentoInputError(f"{campo} excede {limite} caracteres")
        return limpo

    @staticmethod
    def _texto_opcional(valor: Any, campo: str, limite: int) -> str | None:
        if valor is None:
            return None
        if not isinstance(valor, str):
            raise InvalidOrcamentoInputError(f"{campo} deve ser texto")
        limpo = valor.strip()
        if not limpo:
            return None
        if len(limpo) > limite:
            raise InvalidOrcamentoInputError(f"{campo} excede {limite} caracteres")
        return limpo

    @staticmethod
    def _modalidade(valor: Any) -> str | None:
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return None
        if valor not in MODALIDADES:
            raise InvalidOrcamentoInputError(
                f"modalidade deve ser uma de {' ou '.join(MODALIDADES)}"
            )
        return valor

    @staticmethod
    def _prazo(valor: Any) -> int | None:
        if valor is None:
            return None
        if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
            raise InvalidOrcamentoInputError("prazo_execucao_dias deve ser inteiro positivo")
        return valor

    @staticmethod
    def _saldo(valor: Any) -> float | None:
        if valor is None:
            return None
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise InvalidOrcamentoInputError("saldo_mao_de_obra deve ser numérico")
        if isinstance(valor, float) and not math.isfinite(valor):
            raise InvalidOrcamentoInputError("saldo_mao_de_obra deve ser finito")
        if valor < 0:
            raise InvalidOrcamentoInputError("saldo_mao_de_obra não pode ser negativo")
        if valor > MAX_SALDO_MAO_DE_OBRA:
            raise InvalidOrcamentoInputError("saldo_mao_de_obra excede o limite")
        return float(valor)

    def _montar_revisao(self, dados: dict[str, Any], *, autor_user_id: str) -> dict[str, Any]:
        dados_normalizados = {
            "escopo": self._texto_opcional(dados.get("escopo"), "escopo", MAX_ESCOPO) or "",
            "modalidade": self._modalidade(dados.get("modalidade")),
            "regiao": self._texto_opcional(dados.get("regiao"), "regiao", MAX_TEXTO_CURTO),
            "prazo_execucao_dias": self._prazo(dados.get("prazo_execucao_dias")),
            "saldo_mao_de_obra": self._saldo(dados.get("saldo_mao_de_obra")),
            "dados_contratante": self._texto_opcional(
                dados.get("dados_contratante"), "dados_contratante", MAX_TEXTO_LONGO
            ),
            "mobilizacao": self._texto_opcional(
                dados.get("mobilizacao"), "mobilizacao", MAX_TEXTO_CURTO
            ),
            "desmobilizacao": self._texto_opcional(
                dados.get("desmobilizacao"), "desmobilizacao", MAX_TEXTO_CURTO
            ),
            "area_unidade_base": self._texto_opcional(
                dados.get("area_unidade_base"), "area_unidade_base", MAX_TEXTO_CURTO
            ),
            "regime_tributario": self._texto_opcional(
                dados.get("regime_tributario"), "regime_tributario", MAX_TEXTO_CURTO
            ),
        }
        dfp = normalize_dfp_payload(
            dados.get("dfp"),
            seed={
                **dados_normalizados,
                "contratante": dados.get("contratante"),
            },
        )
        # Validate combined totals before persistence, not only when serializing
        # the response: otherwise one invalid draft can break every listing.
        compute_dfp_summary(dfp)
        return {
            "situacao": SITUACAO_RASCUNHO,
            **dados_normalizados,
            "dfp": dfp,
            "versao_regras": f"orcamento.regras.v{dfp['calculation_version']}",
            "autor_user_id": autor_user_id,
            "motivo": self._texto_opcional(dados.get("motivo"), "motivo", MAX_MOTIVO),
        }

    @staticmethod
    def _herdar_cabecalho(revisao: Revisao) -> dict[str, Any]:
        herdado = {campo: getattr(revisao, campo) for campo in REVISAO_CAMPOS_HERDAVEIS}
        herdado["dfp"] = deepcopy(revisao.dfp)
        return herdado

    @staticmethod
    def _codigo_dfp_informado(dados: dict[str, Any]) -> str | None:
        dfp = dados.get("dfp")
        if not isinstance(dfp, dict) or dfp.get("calculation_version") != 2:
            return None
        return OrcamentoService._codigo_dfp_bruto(dados)

    @staticmethod
    def _codigo_dfp_bruto(dados: dict[str, Any]) -> str | None:
        dfp = dados.get("dfp")
        if not isinstance(dfp, dict):
            return None
        metadata = dfp.get("metadata")
        if not isinstance(metadata, dict):
            return None
        codigo = metadata.get("codigo_dfp")
        if not isinstance(codigo, str):
            return None
        return codigo.strip() or None

    @staticmethod
    def _validar_codigo_dfp(codigo_informado: str | None, *, permitidos: set[str]) -> None:
        if codigo_informado is not None and codigo_informado not in permitidos:
            raise InvalidOrcamentoInputError(
                "codigo_dfp é derivado do orçamento e não pode ser alterado manualmente"
            )

    @staticmethod
    def cabecalho_pendente(revisao: Revisao) -> tuple[str, ...]:
        """Campos do cabeçalho canônico ainda vazios nesta revisão."""
        faltantes = []
        for campo, rotulo in CABECALHO_OBRIGATORIO:
            valor = getattr(revisao, campo)
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                faltantes.append(rotulo)
        return tuple(faltantes)

    # -- casos de uso ----------------------------------------------------

    def list_orcamentos(self) -> tuple[Orcamento, ...]:
        return self.repository.list_orcamentos()

    def get_orcamento(self, orcamento_id: str) -> Orcamento:
        return self.repository.get_orcamento(orcamento_id)

    def get_revisao(self, revisao_id: str) -> Revisao:
        return self.repository.get_revisao(revisao_id)

    def list_situacao_eventos(self, revisao_id: str) -> tuple[SituacaoEvento, ...]:
        return self.repository.list_situacao_eventos(revisao_id)

    def create_orcamento(self, dados: dict[str, Any], *, autor_user_id: str) -> Orcamento:
        """Cria o orçamento com código sequencial e a revisão 0 em rascunho."""
        dados = self._validar_payload(
            dados,
            campos=frozenset((*REVISAO_CAMPOS_ENTRADA, "contratante")),
            nome="orçamento",
        )
        autor_user_id = self._texto_obrigatorio(
            autor_user_id, "autor_user_id", MAX_TEXTO_CURTO
        )
        self._validar_codigo_dfp(self._codigo_dfp_informado(dados), permitidos=set())
        agora = self.clock()
        contratante = self._texto_obrigatorio(
            dados.get("contratante"), "contratante", MAX_TEXTO_CURTO
        )
        if not dados.get("dfp"):
            dados = {**dados, "dfp": build_default_dfp_snapshot(dados, calculation_version=2)}
        return self.repository.create_orcamento(
            contratante=contratante,
            criado_por_user_id=autor_user_id,
            revisao=self._montar_revisao(dados, autor_user_id=autor_user_id),
            agora=agora,
        )

    def create_revisao(
        self, orcamento_id: str, dados: dict[str, Any], *, autor_user_id: str
    ) -> Revisao:
        """Cria a próxima revisão sem tocar nas anteriores."""
        dados = self._validar_payload(
            dados, campos=REVISAO_CAMPOS_ENTRADA, nome="revisão"
        )
        autor_user_id = self._texto_obrigatorio(
            autor_user_id, "autor_user_id", MAX_TEXTO_CURTO
        )
        orcamento = self.repository.get_orcamento(orcamento_id)
        atual = orcamento.revisao_atual
        codigo_informado = self._codigo_dfp_informado(dados)
        permitidos = set()
        if atual is not None:
            permitidos.add(f"{orcamento.codigo}-R{atual.numero}")
        self._validar_codigo_dfp(codigo_informado, permitidos=permitidos)
        dados_revisao = {
            **(self._herdar_cabecalho(atual) if atual is not None else {}),
            **dados,
        }
        return self.repository.create_revisao(
            orcamento_id=orcamento_id,
            revisao=self._montar_revisao(dados_revisao, autor_user_id=autor_user_id),
            agora=self.clock(),
        )

    def update_cabecalho(
        self,
        revisao_id: str,
        dados: dict[str, Any],
        *,
        responsavel_user_id: str,
    ) -> Revisao:
        """Edita parcialmente o cabeçalho da revisão atual enquanto for rascunho."""
        dados = self._validar_payload(
            dados, campos=frozenset(REVISAO_CAMPOS_HERDAVEIS), nome="revisão"
        )
        if not dados:
            raise InvalidOrcamentoInputError("Informe ao menos um campo da revisão")
        responsavel_user_id = self._texto_obrigatorio(
            responsavel_user_id,
            "responsavel_user_id",
            MAX_TEXTO_CURTO,
        )

        atual = self.repository.get_revisao(revisao_id)
        if atual.situacao != SITUACAO_RASCUNHO:
            raise InvalidSituacaoTransitionError(
                "Somente revisões em rascunho podem ter o cabeçalho editado"
            )
        orcamento = self.repository.get_orcamento(atual.orcamento_id)
        revisao_atual = orcamento.revisao_atual
        if revisao_atual is None or revisao_atual.id != atual.id:
            raise InvalidSituacaoTransitionError(
                "Somente a revisão atual pode ter o cabeçalho editado"
            )

        if "dfp" in dados and atual.dfp.get("calculation_version") == 2:
            self._validar_codigo_dfp(
                self._codigo_dfp_informado(dados),
                permitidos={f"{orcamento.codigo}-R{atual.numero}"},
            )

        if "dfp" in dados and atual.dfp.get("calculation_version") == 1:
            incoming_dfp = dados.get("dfp")
            if isinstance(incoming_dfp, dict) and incoming_dfp.get("calculation_version", 1) == 1:
                codigo_atual = str(atual.dfp.get("metadata", {}).get("codigo_dfp") or "").strip()
                codigo_informado = self._codigo_dfp_bruto(dados)
                if codigo_informado is not None and codigo_informado != codigo_atual:
                    raise InvalidOrcamentoInputError(
                        "codigo_dfp histórico não pode ser alterado manualmente"
                    )
                if codigo_atual:
                    incoming_dfp = deepcopy(incoming_dfp)
                    metadata = incoming_dfp.get("metadata")
                    if not isinstance(metadata, dict):
                        metadata = {}
                    incoming_dfp["metadata"] = {**metadata, "codigo_dfp": codigo_atual}
                    dados = {**dados, "dfp": incoming_dfp}

        revisao_validada = self._montar_revisao(
            {**self._herdar_cabecalho(atual), **dados},
            autor_user_id=atual.autor_user_id,
        )
        if (
            "dfp" in dados
            and revisao_validada["dfp"]["calculation_version"]
            != atual.dfp["calculation_version"]
        ):
            raise InvalidOrcamentoInputError(
                "calculation_version não pode ser alterada na mesma revisão; crie uma nova revisão"
            )
        cabecalho = {
            campo: revisao_validada[campo] for campo in REVISAO_CAMPOS_HERDAVEIS
        }
        return self.repository.update_cabecalho(
            revisao_id=revisao_id,
            cabecalho=cabecalho,
            agora=self.clock(),
            responsavel_user_id=responsavel_user_id,
        )

    def list_historico(self, orcamento_id: str) -> tuple[dict[str, Any], ...]:
        return self.repository.list_historico(orcamento_id)

    def get_catalogo(self) -> dict[str, Any]:
        catalogo = self.repository.get_catalogo()
        funcoes = {item["nome"].casefold(): item for item in catalogo["funcoes"]}
        itens = {item["nome"].casefold(): item for item in catalogo["itens"]}
        # Explicit catalog prices win; otherwise use the latest saved budget.
        budgets = sorted(
            self.repository.list_orcamentos(), key=lambda budget: budget.updated_at, reverse=True
        )
        for budget in budgets:
            if not budget.revisao_atual:
                continue
            for key, section in budget.revisao_atual.dfp.items():
                if not isinstance(section, dict):
                    continue
                labor = key in ("mao_de_obra_direta", "mao_de_obra_indireta")
                for item in section.get("items", []):
                    nome = str(item.get("label") or "").strip()
                    valor = item.get("salary_real" if labor else "unit_cost")
                    if not nome or not valor:
                        continue
                    target = funcoes if labor else itens
                    if nome.casefold() not in target:
                        campo = "salario_real" if labor else "valor_unitario"
                        target[nome.casefold()] = {"nome": nome, campo: valor}
        return {**catalogo, "funcoes": list(funcoes.values()), "itens": list(itens.values())}

    def list_catalogo_historico(self) -> tuple[dict[str, Any], ...]:
        return self.repository.list_catalogo_historico()

    def save_catalogo(self, dados: dict[str, Any], *, responsavel_user_id: str) -> dict[str, Any]:
        responsavel_user_id = self._texto_obrigatorio(
            responsavel_user_id, "responsavel_user_id", MAX_TEXTO_CURTO
        )
        campos_catalogo = {"funcoes", "itens", "custo_administrativo_diario"}
        if not isinstance(dados, dict) or set(dados) - campos_catalogo:
            raise InvalidOrcamentoInputError("Catálogo inválido")
        normalizado = {}
        for grupo, campo_valor in (("funcoes", "salario_real"), ("itens", "valor_unitario")):
            itens = dados.get(grupo, [])
            if not isinstance(itens, list) or len(itens) > 1000:
                raise InvalidOrcamentoInputError(f"{grupo} deve conter até 1000 itens")
            registros = []
            nomes = set()
            for item in itens:
                if not isinstance(item, dict) or set(item) - {"nome", campo_valor}:
                    raise InvalidOrcamentoInputError(f"Registro inválido em {grupo}")
                nome = self._texto_obrigatorio(item.get("nome"), "nome", MAX_TEXTO_CURTO)
                if nome.casefold() in nomes:
                    raise InvalidOrcamentoInputError(f"Nome duplicado em {grupo}: {nome}")
                nomes.add(nome.casefold())
                valor = self._saldo(item.get(campo_valor))
                if valor is None:
                    raise InvalidOrcamentoInputError(f"{campo_valor} obrigatório")
                registros.append({"nome": nome, campo_valor: valor})
            normalizado[grupo] = registros
        normalizado["custo_administrativo_diario"] = (
            self._saldo(dados.get("custo_administrativo_diario", 0)) or 0
        )
        return self.repository.save_catalogo(
            normalizado, responsavel_user_id=responsavel_user_id, agora=self.clock()
        )

    def alterar_situacao(
        self, revisao_id: str, *, situacao: str, motivo: str, responsavel_user_id: str
    ) -> Revisao:
        """Aplica a transição permitida e registra o evento; nada é excluído."""
        responsavel_user_id = self._texto_obrigatorio(
            responsavel_user_id, "responsavel_user_id", MAX_TEXTO_CURTO
        )
        atual = self.repository.get_revisao(revisao_id)
        if situacao not in TRANSICOES_PERMITIDAS:
            raise InvalidOrcamentoInputError(f"Situação desconhecida: {situacao}")
        if situacao not in TRANSICOES_PERMITIDAS[atual.situacao]:
            if atual.situacao == SITUACAO_INATIVO:
                raise InvalidSituacaoTransitionError(
                    "Revisão inativa não é reativada; crie uma nova revisão do orçamento"
                )
            raise InvalidSituacaoTransitionError(
                f"Transição de {atual.situacao} para {situacao} não é permitida"
            )

        # O fluxo não sai de rascunho sem o cabeçalho canônico completo;
        # mantemos a checagem também nos marcos seguintes por defesa em profundidade.
        if (
            (atual.situacao == SITUACAO_RASCUNHO and situacao != SITUACAO_INATIVO)
            or situacao in (SITUACAO_PRONTO_PARA_PROPOSTA, SITUACAO_EMITIDO)
        ):
            faltantes = self.cabecalho_pendente(atual)
            if faltantes:
                raise InvalidOrcamentoInputError("Cabeçalho incompleto: " + ", ".join(faltantes))

        agora = self.clock()
        # A validade comercial só começa a contar na emissão.
        emissao = None
        if situacao == SITUACAO_EMITIDO:
            emissao = (agora, calcular_validade(agora.date(), self.validade_dias))

        return self.repository.registrar_situacao(
            revisao_id=revisao_id,
            situacao=situacao,
            situacao_esperada=atual.situacao,
            motivo=self._texto_obrigatorio(motivo, "motivo", MAX_MOTIVO),
            responsavel_user_id=responsavel_user_id,
            agora=agora,
            emissao=emissao,
        )


def create_orcamento_service(
    path: Path | str, *, clock: Callable[[], datetime] = _utc_now
) -> OrcamentoService:
    database = OrcamentoDatabase(path)
    database.migrate()
    return OrcamentoService(OrcamentoRepository(database), clock=clock)
