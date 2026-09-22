"""Regras do módulo de Orçamento conforme os documentos do vault.

Referências: Orçamento.md (cabeçalho canônico), Orc_Proposta_Técnica.md
(ciclo de vida e validade) e Orc_Dados_e_Cálculos.md.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.orcamento import (
    SITUACAO_EM_REVISAO,
    SITUACAO_EMITIDO,
    SITUACAO_INATIVO,
    SITUACAO_PRONTO_PARA_PROPOSTA,
    SITUACAO_RASCUNHO,
    VALIDADE_PADRAO_DIAS,
    VERSAO_REGRAS,
    InvalidOrcamentoInputError,
    InvalidSituacaoTransitionError,
    OrcamentoNotFoundError,
    RevisaoNotFoundError,
    create_orcamento_service,
    formatar_codigo,
)
from app.orcamento.dfp import build_default_dfp_snapshot

AGORA = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)

# Cabeçalho canônico completo, espelhando o DFP 0055-26 da AMBEV Anápolis.
CABECALHO = {
    "escopo": "Hidrojateamento e aplicação de revestimento anticorrosivo",
    "modalidade": "Spot",
    "regiao": "Anápolis/GO",
    "prazo_execucao_dias": 10,
    "saldo_mao_de_obra": 4,
    "dados_contratante": "AMBEV S.A. — unidade Anápolis",
}


def _service(tmp_path, clock=None):
    return create_orcamento_service(tmp_path / "orcamento.db", clock=clock or (lambda: AGORA))


def _criar(service, **extras):
    return service.create_orcamento(
        {"contratante": "AMBEV - ANÁPOLIS/GO.", **extras}, autor_user_id="user-1"
    )


def _avancar(service, revisao_id, situacao, motivo="conferido"):
    return service.alterar_situacao(
        revisao_id, situacao=situacao, motivo=motivo, responsavel_user_id="user-1"
    )


def _ate_pronto(service, **extras):
    orcamento = _criar(service, **{**CABECALHO, **extras})
    revisao = orcamento.revisao_atual
    _avancar(service, revisao.id, SITUACAO_EM_REVISAO)
    return _avancar(service, revisao.id, SITUACAO_PRONTO_PARA_PROPOSTA)


# ── criação e código sequencial ──────────────────────────────────────────


def test_criacao_gera_revisao_0_em_rascunho_sem_validade(tmp_path):
    service = _service(tmp_path)

    orcamento = _criar(service, **CABECALHO)

    revisao = orcamento.revisao_atual
    assert orcamento.sequencial == 1
    assert orcamento.codigo == "ORC-0001"
    assert orcamento.contratante == "AMBEV - ANÁPOLIS/GO."
    assert revisao.numero == 0
    assert revisao.situacao == SITUACAO_RASCUNHO
    assert revisao.modalidade == "Spot"
    assert revisao.versao_regras == VERSAO_REGRAS
    # A validade só nasce na emissão, nunca na criação.
    assert revisao.emitido_em is None
    assert revisao.valido_ate is None
    assert revisao.vencida_em(AGORA) is False


def test_codigo_e_sequencial_gerados_pelo_sistema_sem_lacuna(tmp_path):
    service = _service(tmp_path)

    criados = [_criar(service) for _ in range(3)]

    assert [item.sequencial for item in criados] == [1, 2, 3]
    assert [item.codigo for item in criados] == ["ORC-0001", "ORC-0002", "ORC-0003"]


def test_formato_do_codigo_cresce_alem_de_quatro_digitos(tmp_path):
    assert formatar_codigo(1) == "ORC-0001"
    assert formatar_codigo(9999) == "ORC-9999"
    assert formatar_codigo(10000) == "ORC-10000"
    with pytest.raises(ValueError):
        formatar_codigo(0)


# ── cabeçalho canônico ───────────────────────────────────────────────────


def test_cabecalho_incompleto_bloqueia_avanco_para_pronto(tmp_path):
    service = _service(tmp_path)
    revisao = _criar(service).revisao_atual

    with pytest.raises(InvalidOrcamentoInputError, match="Cabeçalho incompleto"):
        _avancar(service, revisao.id, SITUACAO_EM_REVISAO)

    inativada = _avancar(service, revisao.id, SITUACAO_INATIVO, motivo="cancelado")
    assert inativada.situacao == SITUACAO_INATIVO

    faltantes = service.cabecalho_pendente(service.get_revisao(revisao.id))
    assert "Escopo do Serviço" in faltantes
    assert "Modalidade do Trabalho" in faltantes
    assert "Saldo de Mão de Obra" not in faltantes


def test_modalidade_aceita_apenas_hh_ou_spot(tmp_path):
    service = _service(tmp_path)

    assert _criar(service, modalidade="HH").revisao_atual.modalidade == "HH"
    with pytest.raises(InvalidOrcamentoInputError, match="modalidade deve ser"):
        _criar(service, modalidade="Empreitada")


def test_cabecalho_completo_nao_deixa_pendencia(tmp_path):
    service = _service(tmp_path)

    revisao = _criar(service, **CABECALHO).revisao_atual

    assert service.cabecalho_pendente(revisao) == ()


def test_edita_parcialmente_cabecalho_da_revisao_atual_em_rascunho(tmp_path):
    service = _service(tmp_path)
    original = _criar(
        service,
        **CABECALHO,
        mobilizacao="Equipe original",
        desmobilizacao="Retirada original",
        area_unidade_base="1.200 m2",
        regime_tributario="Lucro presumido",
    ).revisao_atual

    editada = service.update_cabecalho(
        original.id,
        {"escopo": "  Escopo ajustado  ", "prazo_execucao_dias": 12},
        responsavel_user_id="user-2",
    )

    assert editada.id == original.id
    assert editada.numero == 0
    assert editada.escopo == "Escopo ajustado"
    assert editada.prazo_execucao_dias == 12
    assert editada.modalidade == original.modalidade
    assert editada.regiao == original.regiao
    assert editada.saldo_mao_de_obra == original.saldo_mao_de_obra
    assert editada.dados_contratante == original.dados_contratante
    assert editada.mobilizacao == original.mobilizacao
    assert editada.desmobilizacao == original.desmobilizacao
    assert editada.area_unidade_base == original.area_unidade_base
    assert editada.regime_tributario == original.regime_tributario
    assert service.list_situacao_eventos(original.id) == ()


@pytest.mark.parametrize(
    "situacoes",
    [
        (SITUACAO_EM_REVISAO,),
        (SITUACAO_EM_REVISAO, SITUACAO_PRONTO_PARA_PROPOSTA),
        (SITUACAO_EM_REVISAO, SITUACAO_PRONTO_PARA_PROPOSTA, SITUACAO_EMITIDO),
        (SITUACAO_INATIVO,),
    ],
)
def test_conteudo_de_revisao_fora_de_rascunho_e_imutavel(tmp_path, situacoes):
    service = _service(tmp_path)
    revisao = _criar(service, **CABECALHO).revisao_atual
    for situacao in situacoes:
        revisao = _avancar(service, revisao.id, situacao)
    eventos_antes = service.list_situacao_eventos(revisao.id)

    with pytest.raises(InvalidSituacaoTransitionError, match="rascunho"):
        service.update_cabecalho(
            revisao.id,
            {"escopo": "Tentativa de sobrescrita"},
            responsavel_user_id="user-2",
        )

    recarregada = service.get_revisao(revisao.id)
    assert recarregada.escopo == CABECALHO["escopo"]
    assert service.list_situacao_eventos(revisao.id) == eventos_antes


def test_revisao_anterior_permanece_imutavel_mesmo_se_era_rascunho(tmp_path):
    service = _service(tmp_path)
    orcamento = _criar(service, **CABECALHO)
    anterior = orcamento.revisao_atual
    service.create_revisao(
        orcamento.id,
        {"escopo": "Nova revisão"},
        autor_user_id="user-2",
    )

    with pytest.raises(InvalidSituacaoTransitionError, match="revisão atual"):
        service.update_cabecalho(
            anterior.id,
            {"escopo": "Sobrescrita indevida"},
            responsavel_user_id="user-2",
        )

    assert service.get_revisao(anterior.id).escopo == CABECALHO["escopo"]


# ── ciclo de vida ────────────────────────────────────────────────────────


def test_ciclo_completo_rascunho_ate_emitido(tmp_path):
    service = _service(tmp_path)
    pronto = _ate_pronto(service)

    emitido = _avancar(service, pronto.id, SITUACAO_EMITIDO, motivo="emissão ao cliente")

    assert pronto.situacao == SITUACAO_PRONTO_PARA_PROPOSTA
    assert emitido.situacao == SITUACAO_EMITIDO
    eventos = service.list_situacao_eventos(emitido.id)
    assert [evento.situacao for evento in eventos] == [
        SITUACAO_EM_REVISAO,
        SITUACAO_PRONTO_PARA_PROPOSTA,
        SITUACAO_EMITIDO,
    ]
    assert all(evento.responsavel_user_id == "user-1" for evento in eventos)


def test_rascunho_nao_salta_direto_para_pronto(tmp_path):
    service = _service(tmp_path)
    revisao = _criar(service, **CABECALHO).revisao_atual

    with pytest.raises(InvalidSituacaoTransitionError, match="não é permitida"):
        _avancar(service, revisao.id, SITUACAO_PRONTO_PARA_PROPOSTA)


def test_revisao_emitida_so_pode_ser_inativada(tmp_path):
    service = _service(tmp_path)
    emitido = _avancar(service, _ate_pronto(service).id, SITUACAO_EMITIDO, motivo="emissão")

    with pytest.raises(InvalidSituacaoTransitionError):
        _avancar(service, emitido.id, SITUACAO_EM_REVISAO)

    inativo = _avancar(service, emitido.id, SITUACAO_INATIVO, motivo="substituída")
    assert inativo.situacao == SITUACAO_INATIVO


def test_revisao_inativa_nao_e_reativada_diretamente(tmp_path):
    service = _service(tmp_path)
    revisao = _criar(service).revisao_atual
    _avancar(service, revisao.id, SITUACAO_INATIVO, motivo="cancelado")

    with pytest.raises(InvalidSituacaoTransitionError, match="crie uma nova revisão"):
        _avancar(service, revisao.id, SITUACAO_EM_REVISAO)


def test_situacao_desconhecida_e_rejeitada(tmp_path):
    service = _service(tmp_path)
    revisao = _criar(service).revisao_atual

    with pytest.raises(InvalidOrcamentoInputError, match="Situação desconhecida"):
        _avancar(service, revisao.id, "arquivado")


def test_revisao_historica_nao_pode_mudar_de_situacao(tmp_path):
    service = _service(tmp_path)
    orcamento = _criar(service, **CABECALHO)
    anterior = orcamento.revisao_atual
    service.create_revisao(orcamento.id, {}, autor_user_id="user-2")

    with pytest.raises(InvalidSituacaoTransitionError, match="revisão atual"):
        _avancar(service, anterior.id, SITUACAO_EM_REVISAO)

    assert service.get_revisao(anterior.id).situacao == SITUACAO_RASCUNHO


def test_transicao_rejeita_estado_esperado_obsoleto(tmp_path):
    service = _service(tmp_path)
    revisao = _criar(service, **CABECALHO).revisao_atual
    atualizada = _avancar(service, revisao.id, SITUACAO_EM_REVISAO)

    with pytest.raises(InvalidSituacaoTransitionError, match="alterada por outra operação"):
        service.repository.registrar_situacao(
            revisao_id=atualizada.id,
            situacao=SITUACAO_INATIVO,
            situacao_esperada=SITUACAO_RASCUNHO,
            motivo="estado obsoleto",
            responsavel_user_id="user-1",
            agora=AGORA,
        )

    assert service.get_revisao(revisao.id).situacao == SITUACAO_EM_REVISAO


# ── validade comercial ───────────────────────────────────────────────────


def test_validade_conta_da_emissao_e_o_ultimo_dia_ainda_vale(tmp_path):
    service = _service(tmp_path)
    emitido = _avancar(service, _ate_pronto(service).id, SITUACAO_EMITIDO, motivo="emissão")

    assert emitido.emitido_em == AGORA
    assert emitido.valido_ate == (AGORA.date() + timedelta(days=VALIDADE_PADRAO_DIAS))
    # O último dia integra o período; o vencimento passa a valer no dia seguinte.
    assert emitido.vencida_em(AGORA + timedelta(days=VALIDADE_PADRAO_DIAS)) is False
    assert emitido.vencida_em(AGORA + timedelta(days=VALIDADE_PADRAO_DIAS + 1)) is True


def test_vencimento_nao_altera_a_situacao_gravada(tmp_path):
    service = _service(tmp_path)
    emitido = _avancar(service, _ate_pronto(service).id, SITUACAO_EMITIDO, motivo="emissão")

    assert service.get_revisao(emitido.id).situacao == SITUACAO_EMITIDO


# ── revisões ─────────────────────────────────────────────────────────────


def test_nova_revisao_preserva_as_anteriores(tmp_path):
    service = _service(tmp_path)
    orcamento = _criar(
        service,
        escopo="Escopo original",
        modalidade="Spot",
        regiao="Anápolis/GO",
        prazo_execucao_dias=10,
        saldo_mao_de_obra=4,
        dados_contratante="AMBEV S.A.",
        mobilizacao="Equipe mobilizada",
    )

    nova = service.create_revisao(
        orcamento.id, {"escopo": "Escopo revisado"}, autor_user_id="user-2"
    )

    recarregado = service.get_orcamento(orcamento.id)
    assert nova.numero == 1
    assert nova.situacao == SITUACAO_RASCUNHO
    assert nova.modalidade == "Spot"
    assert nova.regiao == "Anápolis/GO"
    assert nova.prazo_execucao_dias == 10
    assert nova.saldo_mao_de_obra == 4
    assert nova.dados_contratante == "AMBEV S.A."
    assert nova.mobilizacao == "Equipe mobilizada"
    assert len(recarregado.revisoes) == 2
    assert recarregado.revisoes[0].escopo == "Escopo original"
    assert recarregado.revisao_atual.escopo == "Escopo revisado"


def test_nova_revisao_herda_todo_cabecalho_omitido_e_respeita_sobrescritas(tmp_path):
    service = _service(tmp_path)
    orcamento = _criar(
        service,
        **CABECALHO,
        mobilizacao="Mobilização original",
        desmobilizacao="Desmobilização original",
        area_unidade_base="Área fabril",
        regime_tributario="Lucro presumido",
    )
    original = orcamento.revisao_atual

    herdada = service.create_revisao(
        orcamento.id,
        {},
        autor_user_id="user-2",
    )
    sobrescrita = service.create_revisao(
        orcamento.id,
        {
            "modalidade": "HH",
            "saldo_mao_de_obra": 0,
            "mobilizacao": None,
            "regime_tributario": "Simples Nacional",
        },
        autor_user_id="user-3",
    )

    for campo in (
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
    ):
        assert getattr(herdada, campo) == getattr(original, campo)
    assert sobrescrita.escopo == original.escopo
    assert sobrescrita.modalidade == "HH"
    assert sobrescrita.saldo_mao_de_obra == 0
    assert sobrescrita.mobilizacao is None
    assert sobrescrita.regime_tributario == "Simples Nacional"
    assert sobrescrita.desmobilizacao == original.desmobilizacao
    assert sobrescrita.area_unidade_base == original.area_unidade_base


def test_snapshot_dfp_nasce_com_todas_as_secao_principais_do_modelo(tmp_path):
    service = _service(tmp_path)

    revisao = _criar(service, **CABECALHO).revisao_atual

    assert "metadata" in revisao.dfp
    assert revisao.dfp["metadata"]["titulo"] == "DEMONSTRATIVO DE FORMAÇÃO DE PREÇOS"
    assert len(revisao.dfp["mao_de_obra_direta"]["items"]) >= 27
    assert any(item["label"] == "PINTOR" for item in revisao.dfp["mao_de_obra_direta"]["items"])
    assert any(item["label"] == "ISS" for item in revisao.dfp["impostos"]["items"])
    assert any(
        item["label"] == "VERBA MONTAGEM DE CANTEIRO (CAMPO/ADM)"
        for item in revisao.dfp["outros_custos_diretos"]["items"]
    )


def test_edicao_da_revisao_atual_persiste_snapshot_dfp_sem_perder_demais_blocos(tmp_path):
    service = _service(tmp_path)
    revisao = _criar(service, **CABECALHO).revisao_atual
    snapshot = revisao.dfp
    snapshot["metadata"]["area_total"] = 858
    snapshot["mao_de_obra_direta"]["items"][11]["quantity"] = 2
    snapshot["mao_de_obra_direta"]["items"][11]["hours_per_employee"] = 88
    snapshot["mao_de_obra_direta"]["items"][11]["salary_real"] = 3064.64
    snapshot["equipamentos"]["items"][2]["quantity"] = 0.35
    snapshot["equipamentos"]["items"][2]["unit_cost"] = 7500

    editada = service.update_cabecalho(
        revisao.id,
        {"dfp": snapshot, "escopo": CABECALHO["escopo"]},
        responsavel_user_id="user-2",
    )

    assert editada.dfp["metadata"]["codigo_dfp"] == "ORC-0001-R0"
    assert editada.dfp["metadata"]["area_total"] == 858
    assert editada.dfp["mao_de_obra_direta"]["items"][11]["label"] == "PINTOR"
    assert editada.dfp["mao_de_obra_direta"]["items"][11]["quantity"] == 2
    assert editada.dfp["equipamentos"]["items"][2]["label"] == "MÁQUINA DE HIDROJATO"
    assert editada.dfp["equipamentos"]["items"][2]["unit_cost"] == 7500
    assert editada.dfp["impostos"]["items"][1]["label"] == "ISS"


def test_nova_revisao_herda_tambem_snapshot_dfp(tmp_path):
    service = _service(tmp_path)
    orcamento = _criar(service, **CABECALHO)
    revisao = orcamento.revisao_atual
    snapshot = revisao.dfp
    snapshot["materiais_consumo"]["items"][0]["quantity"] = 45
    snapshot["materiais_consumo"]["items"][0]["unit_cost"] = 266.51
    service.update_cabecalho(
        revisao.id,
        {"dfp": snapshot, "escopo": CABECALHO["escopo"]},
        responsavel_user_id="user-2",
    )

    nova = service.create_revisao(
        orcamento.id,
        {"escopo": "Escopo revisado"},
        autor_user_id="user-3",
    )

    assert nova.dfp["metadata"]["codigo_dfp"] == "ORC-0001-R1"
    assert nova.dfp["materiais_consumo"]["items"][0]["label"] == "HARDTOP XP AMARELO SEGURANÇA"
    assert nova.dfp["materiais_consumo"]["items"][0]["quantity"] == 45
    assert nova.escopo == "Escopo revisado"


def test_versao_de_regras_acompanha_versao_de_calculo(tmp_path):
    service = _service(tmp_path)
    atual = _criar(service).revisao_atual
    assert atual.dfp["calculation_version"] == 2
    assert atual.versao_regras == "orcamento.regras.v2"

    legado = build_default_dfp_snapshot(calculation_version=1)
    nova = service.create_revisao(
        atual.orcamento_id,
        {"dfp": legado},
        autor_user_id="user-2",
    )
    assert nova.dfp["calculation_version"] == 1
    assert nova.versao_regras == "orcamento.regras.v1"


def test_edicao_nao_troca_versao_de_calculo_da_mesma_revisao(tmp_path):
    service = _service(tmp_path)
    revisao = _criar(service).revisao_atual
    legado = build_default_dfp_snapshot(calculation_version=1)

    with pytest.raises(InvalidOrcamentoInputError, match="calculation_version"):
        service.update_cabecalho(
            revisao.id,
            {"dfp": legado},
            responsavel_user_id="user-2",
        )

    recarregada = service.get_revisao(revisao.id)
    assert recarregada.dfp["calculation_version"] == 2
    assert recarregada.versao_regras == "orcamento.regras.v2"


def test_codigo_dfp_v2_e_derivado_e_nao_aceita_alteracao_manual(tmp_path):
    service = _service(tmp_path)
    manual = build_default_dfp_snapshot(calculation_version=2)
    manual["metadata"]["codigo_dfp"] = "DFP-MANUAL"
    with pytest.raises(InvalidOrcamentoInputError, match="codigo_dfp"):
        service.create_orcamento(
            {"contratante": "Cliente", "dfp": manual},
            autor_user_id="user-1",
        )

    budget = _criar(service)
    atual = budget.revisao_atual
    snapshot = atual.dfp
    snapshot["metadata"]["codigo_dfp"] = "ORC-9999-R9"
    with pytest.raises(InvalidOrcamentoInputError, match="codigo_dfp"):
        service.update_cabecalho(
            atual.id,
            {"dfp": snapshot},
            responsavel_user_id="user-2",
        )
    assert service.get_revisao(atual.id).dfp["metadata"]["codigo_dfp"] == "ORC-0001-R0"


def test_nova_revisao_aceita_codigo_dfp_herdado_e_deriva_proximo(tmp_path):
    service = _service(tmp_path)
    budget = _criar(service)
    snapshot = budget.revisao_atual.dfp
    assert snapshot["metadata"]["codigo_dfp"] == "ORC-0001-R0"

    nova = service.create_revisao(
        budget.id,
        {"dfp": snapshot},
        autor_user_id="user-2",
    )
    assert nova.dfp["metadata"]["codigo_dfp"] == "ORC-0001-R1"

    arbitrario = nova.dfp
    arbitrario["metadata"]["codigo_dfp"] = "DFP-LIVRE"
    with pytest.raises(InvalidOrcamentoInputError, match="codigo_dfp"):
        service.create_revisao(
            budget.id,
            {"dfp": arbitrario},
            autor_user_id="user-3",
        )


def test_patch_v1_preserva_codigo_dfp_historico_e_rejeita_troca(tmp_path):
    service = _service(tmp_path)
    legado = build_default_dfp_snapshot(calculation_version=1)
    legado["metadata"]["codigo_dfp"] = "DFP 0055-26"
    budget = service.create_orcamento(
        {"contratante": "Cliente legado", "dfp": legado},
        autor_user_id="user-1",
    )
    revisao = budget.revisao_atual

    mesmo = revisao.dfp
    mesmo["equipamentos"]["items"][0]["unit_cost"] = 123
    editada = service.update_cabecalho(
        revisao.id,
        {"dfp": mesmo},
        responsavel_user_id="user-2",
    )
    assert editada.dfp["metadata"]["codigo_dfp"] == "DFP 0055-26"
    assert editada.dfp["equipamentos"]["items"][0]["unit_cost"] == 123

    alterado = editada.dfp
    alterado["metadata"]["codigo_dfp"] = "DFP ALTERADO"
    with pytest.raises(InvalidOrcamentoInputError, match="histórico"):
        service.update_cabecalho(
            revisao.id,
            {"dfp": alterado},
            responsavel_user_id="user-2",
        )
    assert service.get_revisao(revisao.id).dfp["metadata"]["codigo_dfp"] == "DFP 0055-26"


# ── validação de entrada ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "dados, mensagem",
    [
        ({"contratante": "   "}, "contratante é obrigatório"),
        (
            {"contratante": "AIDEAL", "prazo_execucao_dias": 0},
            "prazo_execucao_dias deve ser inteiro positivo",
        ),
        (
            {"contratante": "AIDEAL", "saldo_mao_de_obra": -1},
            "saldo_mao_de_obra não pode ser negativo",
        ),
        (
            {"contratante": "AIDEAL", "saldo_mao_de_obra": float("nan")},
            "saldo_mao_de_obra deve ser finito",
        ),
        (
            {"contratante": "AIDEAL", "saldo_mao_de_obra": float("inf")},
            "saldo_mao_de_obra deve ser finito",
        ),
        (
            {"contratante": "AIDEAL", "saldo_mao_de_obra": 1_000_000_001},
            "saldo_mao_de_obra excede o limite",
        ),
    ],
)
def test_entradas_invalidas_sao_rejeitadas(tmp_path, dados, mensagem):
    service = _service(tmp_path)

    with pytest.raises(InvalidOrcamentoInputError, match=mensagem):
        service.create_orcamento(dados, autor_user_id="user-1")


def test_alvos_inexistentes_levantam_erro_de_dominio(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(OrcamentoNotFoundError):
        service.get_orcamento("inexistente")
    with pytest.raises(RevisaoNotFoundError):
        service.get_revisao("inexistente")
    with pytest.raises(OrcamentoNotFoundError):
        service.create_revisao("inexistente", {}, autor_user_id="user-1")


def test_listagem_ordena_do_mais_recente_para_o_mais_antigo(tmp_path):
    horarios = iter([AGORA, AGORA + timedelta(hours=1)])
    service = _service(tmp_path, clock=lambda: next(horarios))

    _criar(service)
    _criar(service)

    assert [item.codigo for item in service.list_orcamentos()] == ["ORC-0002", "ORC-0001"]
