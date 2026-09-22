"""Contrato financeiro e de persistência do perfil DFP compatível."""

import sqlite3
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.orcamento import (
    InvalidOrcamentoInputError,
    InvalidSituacaoTransitionError,
    compute_dfp_summary,
    create_orcamento_service,
    get_dfp_window_schema,
    normalize_dfp_payload,
)
from app.orcamento.dfp import build_default_dfp_snapshot

AGORA = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _v2_snapshot():
    snapshot = build_default_dfp_snapshot()
    snapshot["calculation_version"] = 2
    snapshot["metadata"].update(horas_semana=8, horas_sabado=4, horas_domingo=0)
    snapshot["mao_de_obra_direta"]["items"][0].update(
        quantity=2, salary_real=2200, worked_days=5, mobilization_days=1,
        saturday_days=1, sunday_days=0, overtime_week_hours=2,
    )
    snapshot["metadata"].update(semana_fator=1.5, sabado_fator=2, domingo_fator=2)
    return snapshot


def test_v2_horas_salario_extras_e_adicional_seletivo():
    snapshot = _v2_snapshot()
    row = snapshot["mao_de_obra_direta"]["items"][0]
    row.update(hourly_rate=999, salary_base_hours=1, hours_per_employee=999)
    snapshot["mao_de_obra_direta"]["adjustments"] = [
        {"id": "periculosidade", "label": "Periculosidade", "percent": 30,
         "labor_item_id": row["id"], "quantity": 1, "base": "salary"}
    ]
    snapshot["mao_de_obra_direta"]["social_charges_percent"] = 10
    normalized = normalize_dfp_payload(snapshot)
    assert normalized["calculation_version"] == 2
    assert normalized["mao_de_obra_direta"]["items"][0]["hourly_rate"] == 10
    assert normalized["mao_de_obra_direta"]["items"][0]["worked_hours"] == 104
    # 104h * 10 + 2 pessoas * 2h * 1.5 * 10 + 520 * 30%; encargos 10%.
    assert compute_dfp_summary(snapshot)["mao_de_obra_direta_total"] == 1381.6


def test_v2_admin_alimentacao_desconto_e_denominador_pessoa_dia():
    snapshot = _v2_snapshot()
    snapshot["custos_administrativos"] = {
        "daily_cost": 100, "days": 7, "considered_percent": 50, "multiplier": 2,
    }
    snapshot["alimentacao"]["items"][0].update(quantity=999, unit_cost=10)
    snapshot["equipamentos"]["items"][0].update(quantity=2, unit_cost=100)
    snapshot["equipamentos"]["discount_percent"] = 25
    snapshot["mao_de_obra_indireta"]["items"][0]["manual_total"] = 99999
    snapshot["veiculos_hospedagem"]["lodging_assets"][0].update(quantity=1, unit_cost=99999)
    summary = compute_dfp_summary(snapshot)
    assert summary["custos_administrativos_total"] == 700
    assert summary["alimentacao_total"] == 140
    assert summary["equipamentos_total"] == 150
    assert summary["mao_de_obra_indireta_total"] == 700
    assert summary["custos_diretos_total"] == 2090
    assert summary["valor_dia_colaborador"] == 149.29


@pytest.mark.parametrize(
    "field",
    ["quantity", "worked_days", "mobilization_days", "saturday_days", "sunday_days"],
)
def test_v2_contagens_fracionarias_rejeitadas(field):
    snapshot = _v2_snapshot()
    snapshot["mao_de_obra_direta"]["items"][0][field] = 1.5
    with pytest.raises(InvalidOrcamentoInputError, match="inteiro"):
        normalize_dfp_payload(snapshot)


def test_v2_adicional_nao_pode_exceder_quantidade_da_funcao():
    snapshot = _v2_snapshot()
    snapshot["mao_de_obra_direta"]["adjustments"] = [{
        "id": "noturno",
        "percent": 20,
        "labor_item_id": snapshot["mao_de_obra_direta"]["items"][0]["id"],
        "quantity": 3, "base": "salary",
    }]
    with pytest.raises(InvalidOrcamentoInputError, match="quantidade"):
        normalize_dfp_payload(snapshot)


def test_v2_desconto_total_permitido_e_acima_cem_rejeitado():
    snapshot = _v2_snapshot()
    snapshot["mao_de_obra_direta"]["discount_percent"] = 100
    assert compute_dfp_summary(snapshot)["mao_de_obra_direta_total"] == 0
    snapshot["mao_de_obra_direta"]["discount_percent"] = 101
    with pytest.raises(InvalidOrcamentoInputError, match="100"):
        normalize_dfp_payload(snapshot)


def _service(tmp_path):
    return create_orcamento_service(tmp_path / "orcamento.db", clock=lambda: AGORA)


def _custom_item(kind: str, suffix: str) -> dict:
    base = {"id": f"custom_{suffix}", "label": f"ITEM CUSTOMIZADO {suffix}", "notes": "preservar"}
    if kind == "labor":
        return {
            **base,
            "quantity": 1,
            "hours_per_employee": 2,
            "worked_hours": 2,
            "worked_days": 1,
            "mobilization_days": 1,
            "months": 1,
            "salary_real": 300,
            "salary_base_hours": 220,
            "hourly_rate": 0,
            "manual_total": 10,
        }
    if kind == "percent":
        return {**base, "aliquot_percent": 1.25}
    return {**base, "quantity": 2, "unit_cost": 3.45}


def test_calculo_financeiro_usa_precisao_decimal_e_arredondamento_half_up():
    snapshot = build_default_dfp_snapshot()
    snapshot["mao_de_obra_direta"]["social_charges_percent"] = 0
    snapshot["mao_de_obra_indireta"]["social_charges_percent"] = 0
    for item in snapshot["custos_indiretos"]["items"]:
        item["aliquot_percent"] = 0
    for item in snapshot["impostos"]["items"]:
        item["aliquot_percent"] = 0
    snapshot["bdi"]["factor_percent"] = 0
    snapshot["equipamentos"]["items"][0].update(quantity=1, unit_cost=2.675)
    snapshot["equipamentos"]["items"][1].update(quantity=3, unit_cost=0.1)

    summary = compute_dfp_summary(snapshot)

    assert summary["equipamentos_total"] == 2.98
    assert summary["custos_diretos_total"] == 2.98
    assert summary["preco_total_faturamento"] == 2.98


def test_calculo_composto_fecha_subtotais_bdi_impostos_e_indicadores():
    snapshot = build_default_dfp_snapshot()
    direct = snapshot["mao_de_obra_direta"]
    direct["items"][0].update(quantity=2, hours_per_employee=10, worked_days=4, hourly_rate=5)
    direct["adjustments"][0]["percent"] = 10
    direct["social_charges_percent"] = 20
    snapshot["mao_de_obra_indireta"]["items"][0]["manual_total"] = 50
    snapshot["equipamentos"]["items"][0].update(quantity=2, unit_cost=10)
    snapshot["custos_indiretos"]["items"][0]["aliquot_percent"] = 5
    snapshot["bdi"]["factor_percent"] = 10
    snapshot["impostos"]["items"][0]["aliquot_percent"] = 10
    snapshot["metadata"]["area_total"] = 2

    summary = compute_dfp_summary(snapshot)

    assert summary["mao_de_obra_direta_total"] == 132
    assert summary["mao_de_obra_indireta_total"] == 50
    assert summary["custos_diretos_total"] == 202
    assert summary["custos_indiretos_total"] == 10.10
    assert summary["lucro_total"] == 20.20
    assert summary["custos_totais"] == 232.30
    assert summary["preco_total_faturamento"] == 258.11
    assert summary["preco_por_area"] == 129.06
    assert summary["valor_dia_colaborador"] == 32.26


@pytest.mark.parametrize(
    "invalid", [-0.01, float("nan"), float("inf"), float("-inf"), 10_000_000_000_001]
)
def test_valores_financeiros_invalidos_sao_rejeitados_em_vez_de_zerados(invalid):
    snapshot = build_default_dfp_snapshot()
    snapshot["equipamentos"]["items"][0]["unit_cost"] = invalid

    with pytest.raises(InvalidOrcamentoInputError, match="unit_cost"):
        normalize_dfp_payload(snapshot)


def test_lista_dfp_tem_limite_para_evitar_payload_desproporcional():
    snapshot = build_default_dfp_snapshot()
    snapshot["equipamentos"]["items"] = [
        _custom_item("cost", str(index)) for index in range(251)
    ]

    with pytest.raises(InvalidOrcamentoInputError, match="no máximo 250"):
        normalize_dfp_payload(snapshot)


def test_numero_textual_e_booleano_nao_sao_aceitos_como_valor_financeiro():
    for invalid in ("10.50", True):
        snapshot = build_default_dfp_snapshot()
        snapshot["equipamentos"]["items"][0]["quantity"] = invalid
        with pytest.raises(InvalidOrcamentoInputError, match="quantity"):
            normalize_dfp_payload(snapshot)


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("mao_de_obra_direta", "social_charges_percent"),
        ("mao_de_obra_indireta", "social_charges_percent"),
        ("bdi", "factor_percent"),
    ],
)
def test_percentuais_de_secao_devem_ser_menores_que_cem(section, field):
    snapshot = build_default_dfp_snapshot()
    snapshot[section][field] = 100

    with pytest.raises(InvalidOrcamentoInputError, match="menor que 100"):
        normalize_dfp_payload(snapshot)


@pytest.mark.parametrize("section", ["custos_indiretos", "impostos"])
def test_aliquota_de_item_deve_ser_menor_que_cem(section):
    snapshot = build_default_dfp_snapshot()
    snapshot[section]["items"][0]["aliquot_percent"] = 100

    with pytest.raises(InvalidOrcamentoInputError, match="menor que 100"):
        normalize_dfp_payload(snapshot)


def test_soma_de_impostos_deve_ser_menor_que_cem():
    snapshot = build_default_dfp_snapshot()
    for item in snapshot["impostos"]["items"]:
        item["aliquot_percent"] = 0
    snapshot["impostos"]["items"][0]["aliquot_percent"] = 60
    snapshot["impostos"]["items"][1]["aliquot_percent"] = 40

    with pytest.raises(InvalidOrcamentoInputError, match="Soma das alíquotas"):
        compute_dfp_summary(snapshot)


def test_itens_customizados_sao_preservados_em_todas_as_listas_do_snapshot():
    snapshot = build_default_dfp_snapshot()
    lists = (
        ("mao_de_obra_direta", "items", "labor"),
        ("mao_de_obra_indireta", "items", "labor"),
        ("mao_de_obra_direta", "adjustments", "adjustment"),
        ("mao_de_obra_indireta", "adjustments", "adjustment"),
        ("veiculos_hospedagem", "items", "cost"),
        ("veiculos_hospedagem", "lodging_assets", "cost"),
        ("alimentacao", "items", "cost"),
        ("equipamentos", "items", "cost"),
        ("epis_epcs", "items", "cost"),
        ("materiais_consumo", "items", "cost"),
        ("ferramental", "items", "cost"),
        ("outros_custos_diretos", "items", "cost"),
        ("custos_indiretos", "items", "percent"),
        ("impostos", "items", "percent"),
    )
    expected_ids = []
    for index, (section, list_name, kind) in enumerate(lists):
        item = (
            {"id": f"custom_{index}", "label": f"AJUSTE {index}", "percent": 1.5}
            if kind == "adjustment"
            else _custom_item(kind, str(index))
        )
        snapshot[section][list_name].append(item)
        expected_ids.append((section, list_name, item["id"]))

    normalized = normalize_dfp_payload(snapshot)

    for section, list_name, item_id in expected_ids:
        assert any(item["id"] == item_id for item in normalized[section][list_name])


def test_calculo_nao_muta_snapshot_recebido():
    snapshot = build_default_dfp_snapshot()
    snapshot["equipamentos"]["items"].append(_custom_item("cost", "imutavel"))
    original = deepcopy(snapshot)

    compute_dfp_summary(snapshot)

    assert snapshot == original


def test_revisoes_possuem_copias_profundas_independentes_do_dfp(tmp_path):
    service = _service(tmp_path)
    orcamento = service.create_orcamento({"contratante": "AIDEAL"}, autor_user_id="user-1")
    original = orcamento.revisao_atual
    nova = service.create_revisao(orcamento.id, {}, autor_user_id="user-2")

    alterado = nova.dfp
    alterado["equipamentos"]["items"][0]["unit_cost"] = 999
    service.update_cabecalho(nova.id, {"dfp": alterado}, responsavel_user_id="user-2")

    assert service.get_revisao(original.id).dfp["equipamentos"]["items"][0]["unit_cost"] == 0
    assert service.get_revisao(nova.id).dfp["equipamentos"]["items"][0]["unit_cost"] == 999


def test_dfp_de_revisao_historica_nao_pode_ser_editado(tmp_path):
    service = _service(tmp_path)
    orcamento = service.create_orcamento({"contratante": "AIDEAL"}, autor_user_id="user-1")
    historica = orcamento.revisao_atual
    service.create_revisao(orcamento.id, {}, autor_user_id="user-2")

    with pytest.raises(InvalidSituacaoTransitionError, match="revisão atual"):
        service.update_cabecalho(
            historica.id,
            {"dfp": build_default_dfp_snapshot()},
            responsavel_user_id="user-2",
        )


def test_catalogo_indireto_nao_expoe_nomes_pessoais_e_rotulos_sao_editaveis():
    schema = get_dfp_window_schema(calculation_version=1)
    section = next(item for item in schema["sections"] if item["id"] == "mao_de_obra_indireta")
    labels = {row["label"] for row in section["rows"]}
    nomes_pessoais = {
        "GABRIELLY",
        "DANIELLY",
        "GECYKA",
        "WILLIAM",
        "MARCOS",
        "RICARDO",
        "EDUARDO",
        "PATRICIA",
        "BRUNA",
        "RENATO",
        "YCARO",
    }
    assert labels.isdisjoint(nomes_pessoais)

    snapshot = build_default_dfp_snapshot()
    snapshot["mao_de_obra_indireta"]["items"][1]["label"] = "COORDENAÇÃO LOCAL"
    assert (
        normalize_dfp_payload(snapshot)["mao_de_obra_indireta"]["items"][1]["label"]
        == "COORDENAÇÃO LOCAL"
    )


def test_schema_declara_dfp_como_perfil_de_compatibilidade():
    schema = get_dfp_window_schema()

    assert schema["profile"]["code"] == "dfp-0055-26"
    assert schema["profile"]["compatibility"] is True


def test_snapshot_padrao_tem_parametros_financeiros_neutros():
    snapshot = build_default_dfp_snapshot()

    assert snapshot["mao_de_obra_direta"]["social_charges_percent"] == 0
    assert snapshot["mao_de_obra_indireta"]["social_charges_percent"] == 0
    assert snapshot["bdi"]["factor_percent"] == 0
    assert snapshot["informacoes_adicionais"]["regime_tributacao"] == ""
    assert all(item["aliquot_percent"] == 0 for item in snapshot["custos_indiretos"]["items"])
    assert all(item["aliquot_percent"] == 0 for item in snapshot["impostos"]["items"])


@pytest.mark.parametrize(
    ("regiao", "macrorregiao", "municipio", "uf"),
    [
        ("Norte — Manaus/AM", "Norte", "Manaus", "AM"),
        ("Nordeste — Recife/PE", "Nordeste", "Recife", "PE"),
        ("Centro-Oeste — Anápolis/GO", "Centro-Oeste", "Anápolis", "GO"),
        ("Sudeste — São Paulo/SP", "Sudeste", "São Paulo", "SP"),
        ("Sul — Porto Alegre/RS", "Sul", "Porto Alegre", "RS"),
    ],
)
def test_seed_de_regiao_reconhecida_preenche_localizacao_estruturada(
    regiao, macrorregiao, municipio, uf
):
    metadata = build_default_dfp_snapshot({"regiao": regiao})["metadata"]

    assert metadata["pais"] == "Brasil"
    assert metadata["macrorregiao"] == macrorregiao
    assert metadata["municipio"] == municipio
    assert metadata["uf"] == uf
    assert metadata["zona_salarial"] == ""


@pytest.mark.parametrize("regiao", ["Anápolis/GO", "Exterior — Lisboa/PT", "texto livre"])
def test_seed_de_regiao_nao_reconhecida_nao_inventa_localizacao(regiao):
    metadata = build_default_dfp_snapshot({"regiao": regiao})["metadata"]

    assert metadata["pais"] == "Brasil"
    assert metadata["macrorregiao"] == ""
    assert metadata["municipio"] == ""
    assert metadata["uf"] == ""


def test_localizacao_estruturada_e_preservada_e_editavel():
    snapshot = build_default_dfp_snapshot()
    snapshot["metadata"].update(
        pais="Brasil",
        uf="BA",
        municipio="Salvador",
        macrorregiao="Nordeste",
        zona_salarial="Zona 2",
    )

    metadata = normalize_dfp_payload(snapshot)["metadata"]

    assert metadata["pais"] == "Brasil"
    assert metadata["uf"] == "BA"
    assert metadata["municipio"] == "Salvador"
    assert metadata["macrorregiao"] == "Nordeste"
    assert metadata["zona_salarial"] == "Zona 2"


def test_snapshot_legado_vazio_deriva_localizacao_do_cabecalho_ao_ser_lido(tmp_path):
    database_path = tmp_path / "orcamento.db"
    service = create_orcamento_service(database_path, clock=lambda: AGORA)
    created = service.create_orcamento(
        {"contratante": "TESTE", "regiao": "Norte — Manaus/AM"},
        autor_user_id="user-1",
    )
    revisao_id = created.revisao_atual.id

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE orcamento_revisoes SET dfp_payload = '{}' WHERE id = ?",
            (revisao_id,),
        )

    metadata = service.get_revisao(revisao_id).dfp["metadata"]
    assert metadata["macrorregiao"] == "Norte"
    assert metadata["municipio"] == "Manaus"
    assert metadata["uf"] == "AM"
