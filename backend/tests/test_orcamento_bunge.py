"""Reconciliation with MODELO DFP in REV.01 DFP 0075-26, read 2026-09-14.

Reference inputs are transcribed by cell, without requiring the private workbook
at test time. This is the legacy worksheet model, not a migration to version 2.
"""

from decimal import Decimal

import pytest

from app.orcamento import compute_dfp_summary
from app.orcamento.dfp import build_default_dfp_snapshot


def bunge_legacy_snapshot():
    """Snapshot fiel à planilha DFP 0075-26 BUNGE (REV.01)."""
    snapshot = build_default_dfp_snapshot()
    snapshot["calculation_version"] = 1
    snapshot["metadata"].update({
        "titulo": "DEMONSTRATIVO DE FORMAÇÃO DE PREÇOS",
        "cliente_unidade": "BUNGE - PONTA GROSSA/PR.",
        "folha": "1 de 5",
        "previsao_inicio": "XXX",
        "mobilizacao_text": "15 dias de mobilização",
        "desmobilizacao_text": "XXX dias",
        "prazo_execucao_text": "30 dias corridos",
        "descricao_projeto": (
            "Fornecimento de mão de obra, equipementos para atividade de jateamento e pintura "
            "das partes interna e externa do estrator EXT3T. Totalizando 2.200m². "
            "(Obs.: A quantidade de metros quadrados considerada no orçamento foi obtida por "
            "meio de levantamento realizado enviado pela contratante.)"
        ),
        "pais": "Brasil",
        "uf": "PR",
        "municipio": "Ponta Grossa",
        "macrorregiao": "Sul",
        "area_total": 2200,
        "area_unidade": "m²",
        "sabado_fator": 1.7,
        "domingo_fator": 2,
        "semana_fator": 1.7,
        "quantidade_sabado": 5,
        "quantidade_domingo": 0,
        "quantidade_dias_semana": 0,
        "horas_sabado": 8.8,
        "horas_domingo": 10,
        "horas_semana": 2,
    })

    # A14:O40. O12=1,15 está incorporado no salário/hora das funções noturnas.
    direct = [
        (14, "SUPERVISOR DE OBRAS (NOTURNO)", 0, 32.99072954545455, 0, 6311.27),
        (15, "ENCARREGADO DE PINTURA (NOTURNO)", 1, 25.149454545454542, 1881.1792, 4811.2),
        (16, "AUXILIAR ADM", 0, 10.523, 0, 2315.06),
        (17, "ASSISTENTE ADM", 0, 13.079299774999999, 0, 2877.4459505),
        (18, "AUXILIAR GERAL (NOTURNO)", 0, 12.619452567250002, 0, 2414.1561433000006),
        (19, "AUXILIAR GERAL", 0, 10.973437015000004, 0, 2414.1561433000006),
        (20, "AUXILIAR ANDAIME", 0, 10.973437015000004, 0, 2414.1561433000006),
        (21, "VIGIA ESPAÇO CONFINADO", 0, 10.973437015000004, 0, 2414.1561433000006),
        (22, "ALPINISTA N1", 0, 20.691863636363635, 0, 4552.21),
        (23, "ALPINISTA N3", 0, 61.173863636363635, 0, 13458.25),
        (24, "PINTOR (NOTURNO)", 4, 16.01970909090909, 4793.09696, 3064.64),
        (25, "PINTOR", 0, 13.930181818181818, 0, 3064.64),
        (26, "PINTOR LETREIRO", 0, 13.930181818181818, 0, 3064.64),
        (27, "PINTOR LÍDER (NOTURNO)", 0, 20.961154545454544, 0, 4009.96),
        (28, "JATISTA (NOTURNO)", 5, 16.088813636363636, 6017.2163, 3077.86),
        (29, "HIDROJATISTA", 0, 13.990272727272728, 0, 3077.86),
        (30, "ENCARREGADO DE ANDAIMES", 0, 21.869090909090907, 0, 4811.2),
        (31, "MONTADOR DE ANDAIME", 0, 14.278079935000001, 0, 3141.1775857000002),
        (32, "MECÂNICO MONTADOR", 0, 13.930181818181818, 0, 3064.64),
        (33, "MONTADOR DE CHAPA", 0, 13.5605, 0, 2983.31),
        (34, "FUNILEIRO", 0, 14.968727272727273, 0, 3293.12),
        (35, "ISOLADOR", 0, 11.2175, 0, 2467.85),
        (36, "PEDREIRO", 0, 11.559999999999999, 0, 2543.2),
        (37, "TÉCNICO DE PLANEJAMENTO", 0, 25.87781818181818, 0, 5693.12),
        (38, "TÉCNICO DE SEGURANÇA (NOTURNO)", 1, 20.195672727272726, 1510.63632, 3863.52),
        (39, "INSPETOR PINT. N1 (NOTURNO)", 1, 37.37667272727272, 2795.77512, 7150.32),
        (40, "ENGENHEIRO", 0, 0, 0, 0),
    ]
    snapshot["mao_de_obra_direta"]["items"] = [
        {
            "id": f"dfp_row_{row}", "label": label, "quantity": quantity,
            "hours_per_employee": 330, "worked_hours": 8.8,
            "worked_days": 30, "mobilization_days": 15, "months": 0,
            "salary_real": salary, "salary_base_hours": 220,
            "hourly_rate": hourly, "manual_total": saturday_total,
            "notes": "",
        }
        for row, label, quantity, hourly, saturday_total, salary in direct
    ]
    snapshot["mao_de_obra_direta"]["adjustments"] = [
        {"id": "adicional_noturno", "label": "Adicional noturno", "percent": 0},
        {"id": "adicional_transferencia", "label": "Adicional de transferência", "percent": 0},
        {"id": "aviso_previo", "label": "Aviso prévio", "percent": 0},
    ]
    snapshot["mao_de_obra_direta"]["social_charges_percent"] = 90

    # A54:M65: alocação administrativa de 33 h por pessoa, com 76% de encargos.
    indirect = [
        (54, "GABRIELLY", 12.195454545454545, 2683),
        (55, "DANIELLY", 32.26234458983636, 7097.7158097639995),
        (56, "GECYKA", 32.26234458983636, 7097.7158097639995),
        (57, "WILLIAM", 18.864916922727268, 4150.281722999999),
        (58, "MARCOS", 18.86490909090909, 4150.28),
        (59, "RICARDO", 40.90909090909091, 9000),
        (60, "EDUARDO", 32.26236363636364, 7097.72),
        (61, "PATRICIA", 12.195454545454545, 2683),
        (62, "BRUNA", 12.195454545454545, 2683),
        (63, "RENATO", 8.863636363636363, 1950),
        (64, "YCARO", 31.818181818181817, 7000),
    ]
    snapshot["mao_de_obra_indireta"]["items"] = [
        {
            "id": f"dfp_row_{row}", "label": label, "quantity": 1,
            "hours_per_employee": 33, "worked_hours": 0, "worked_days": 0,
            "mobilization_days": 0, "months": 0, "salary_real": salary,
            "salary_base_hours": 220, "hourly_rate": hourly,
            "manual_total": 0, "notes": "",
        }
        for row, label, hourly, salary in indirect
    ]
    snapshot["mao_de_obra_indireta"]["adjustments"] = [
        {"id": "adicional_periculosidade", "label": "Adicional de periculosidade", "percent": 0},
        {"id": "adicional_transferencia", "label": "Adicional de transferência", "percent": 0},
        {"id": "aviso_previo", "label": "Aviso prévio", "percent": 0},
    ]
    snapshot["mao_de_obra_indireta"]["social_charges_percent"] = 76

    def costs(section, start, rows):
        snapshot[section]["items"] = [
            {"id": f"dfp_row_{start + index}", "label": label,
             "quantity": quantity, "unit_cost": unit_cost, "notes": notes}
            for index, (label, quantity, unit_cost, notes) in enumerate(rows)
        ]

    costs("veiculos_hospedagem", 90, [
        ("CARRO APOIO CUSTO MANUTENÇÃO", 30, 100, ""),
        ("CARRO LOCAÇÃO SPIN 7 LUGARES", 1, 7000, ""),
        ("VAN", 0, 13000, ""),
        ("HOSPEDAGEM", 1, 2500, "01 CASA"),
        ("MÓVEIS DA CASA", 1, 8100, "Detalhamento em móveis; valor já incluído neste item."),
        ("COMBUSTIVEL CARRO APOIO", 1, 3000, ""),
    ])
    snapshot["veiculos_hospedagem"]["lodging_assets"] = [
        {"id": f"dfp_movel_{index}", "label": label, "quantity": 0,
         "unit_cost": value, "notes": "Detalhamento informativo; já incluído em MÓVEIS DA CASA."}
        for index, (label, value) in enumerate([
            ("COLCHÃO +CAMA", 4800), ("GELADEIRA", 1000), ("TV", 1000),
            ("SOFÁ", 500), ("BEBEDOURO", 500), ("MESAS", 300),
        ], start=1)
    ]
    costs("alimentacao", 102, [
        ("CAFÉ", 540, 10, ""), ("ALMOÇO", 540, 25, ""),
        ("CEIA NOTURNA", 540, 0, ""), ("JANTAR", 540, 25, ""),
    ])
    snapshot["alimentacao"]["total_funcionarios"] = 12
    snapshot["alimentacao"]["total_dias_mobilizacao"] = 45
    costs("equipamentos", 113, [
        ("MAQUINA DE JATO ABRASIVO", 1, 14000, "CONSIDERADO 4 MAQUINAS DE JATO"),
        ("COMPRESSOR DE 900 PCM", 1, 14000, ""),
        ("DIESEL PARA COMPRESSOR", 1, 14000, "CONSIDERADO 100 LITROS POR DIA POR 20 DIAS"),
        ("FRETE PARA EQUIPAMENTOS", 1, 10000, ""),
        ("VERBA P/ EQUIPAMENTOS", 1, 3000, ""),
        ("VERBA P/ RADIO COMUNICAÇÃO", 1, 1000, ""),
    ])
    costs("epis_epcs", 126, [
        ("PROTETOR TIPO CONCHA", 12, 170, ""), ("CAPACETE", 12, 51, ""),
        ("UNIFORME", 12, 120, ""), ("LUVA VAQUETA", 50, 15, ""),
        ("LUVA NITRÍLICA", 75, 7.5, ""), ("OCULOS AMPLA VISÃO", 12, 38, ""),
        ("RESPIRADOR PINTOR", 6, 250, ""),
        ("CINTO DE SEGURANÇA", 10, 2000, "valor considerado cinto de segurança padrão BUNGE."),
        ("KIT JATISTA", 5, 720, ""), ("BOTA SEG", 12, 150, ""),
        ("MASCARA DESCAR", 270, 3.5, ""), ("VERBA EPIs E EPCs", 0, 500, ""),
    ])
    costs("materiais_consumo", 146, [
        ("TINTA PENGUARD UNIVERSAL 3,6L", 453, 195, ""),
        ("DILUENTES PARA TINTAS", 66, 105, ""),
        ("FRETE PARA TINTAS", 1, 10500, ""), ("ABRASIVO COBRAU", 30, 700, ""),
        ("FRENTE PARA ABRASIVO", 2, 10000, ""), ("CONSUMÍVEIS", 1, 4000, ""),
    ])
    costs("ferramental", 159, [
        ("CONTAINER ADM", 0, 1500, ""), ("CONTAINER ALMOXARIFADO", 1, 1400, ""),
        ("FRETE CONTAINER", 2, 5000, ""), ("BEBEDOURO", 0, 5000, ""),
        ("TENDA PARA VIVÊNCIA", 0, 5000, ""), ("VERBA PARA FERRAMENTAL", 1, 2000, ""),
    ])
    costs("outros_custos_diretos", 172, [
        ("VIAGENS SUPERVISÃO IDA E VOLTA", 3, 1000, ""),
        ("MOBILIZAÇÃO E DESMOBI", 2, 2000, "CONSIDERADO MOB. E DESMOB."),
        ("TRANSLADOS FUNCIONÁRIOS", 12, 700, ""),
        ("OUTROS (ART, LAUDOS CASO NESCESSÁRIOS)", 1, 700, ""),
        ("EXAMES", 12, 500, ""), ("TREINAMENTOS (NR 35, NR20)", 12, 500, ""),
        ("PROGRAMAS (PGR, PCMSO) (por contrato)", 1, 2000, ""),
        ("PLANO DE SAÚDE", 12, 40, ""), ("VALE ALIMENTAÇÃO", 12, 640, ""),
        ("VERBA PARA ILUMINAÇÃO", 1, 1000, ""),
        ("VERBA PARA DESTINAÇÃO DE RESIDUOS", 1, 30000, "INCLUSOS LAUDOS AMBIENTAIS"),
    ])

    snapshot["custos_indiretos"]["items"] = [
        {"id": "adm_central", "label": "ADM CENTRAL", "aliquot_percent": 7, "notes": ""},
        {"id": "linha_191", "label": "", "aliquot_percent": 0, "notes": ""},
        {"id": "participacao", "label": "PARTICIPAÇÃO", "aliquot_percent": 0, "notes": ""},
        {
            "id": "taxa_antecipacao",
            "label": "TAXA DE ANTECIPAÇÃO",
            "aliquot_percent": 0,
            "notes": "",
        },
    ]
    snapshot["bdi"]["factor_percent"] = 45
    snapshot["impostos"]["items"] = [
        {"id": key, "label": label, "aliquot_percent": value, "notes": ""}
        for key, label, value in [
            ("irpj", "IRPJ", 4.8), ("iss", "ISS", 5), ("csll", "CSLL", 2.88),
            ("pis", "PIS", 0.65), ("inss", "INSS", 0), ("cofins", "COFINS", 3),
            ("icms", "ICMS", 0),
        ]
    ]
    snapshot["informacoes_adicionais"].update({
        "regime_tributacao": "Presumido",
        "possui_beneficio_fiscal": False,
        "inss_isento": False,
        "observacoes": "Fonte: REV.01 - DFP 0075-26 BUNGE - JAT. E PINT. EXTRATOR EXT3T.xlsx",
    })
    return snapshot


@pytest.mark.parametrize(("key", "cached"), [
    ("mao_de_obra_direta_total", 174778.44716),  # E47
    ("mao_de_obra_indireta_total", 14676.476322427392),  # E72
    ("veiculos_hospedagem_total", 23600), ("alimentacao_total", 32400),
    ("equipamentos_total", 56000), ("epis_epcs_total", 33705.5),
    ("materiais_consumo_total", 150765), ("ferramental_total", 13400),
    ("outros_custos_diretos_total", 69260),
    ("custos_diretos_total", 568585.4234824274),
    ("custos_indiretos_total", 39800.97964376992),
    ("lucro_total", 255863.4405670923),
    ("custos_totais", 864249.8436932896),
    ("preco_total_faturamento", 1032926.7882075888),
    ("preco_por_area", 469.51217645799494),
])
def test_legacy_bunge_reconciles_source_with_cent_rounding(key, cached):
    # Excel carries full precision; application rounds each section to cents.
    assert compute_dfp_summary(bunge_legacy_snapshot())[key] == pytest.approx(cached, abs=0.02)


def test_bunge_tax_sum_and_screenshot_are_distinct_scenarios():
    summary = compute_dfp_summary(bunge_legacy_snapshot())
    assert summary["aliquota_impostos_total"] == 16.33
    assert summary["custos_diretos_total"] != 341986
    assert summary["preco_total_faturamento"] != 633534.48


def test_screenshot_gross_up_from_its_own_inputs():
    snapshot = build_default_dfp_snapshot()
    snapshot["calculation_version"] = 1
    snapshot["metadata"]["area_total"] = 2200
    snapshot["equipamentos"]["items"][0].update(quantity=1, unit_cost=341986)
    snapshot["custos_indiretos"]["items"][0]["aliquot_percent"] = 5
    snapshot["bdi"]["factor_percent"] = 50
    snapshot["impostos"]["items"][0]["aliquot_percent"] = 16.33
    summary = compute_dfp_summary(snapshot)
    assert summary["custos_totais"] == 530078.30
    assert summary["preco_total_faturamento"] == 633534.48
    assert summary["preco_por_area"] == 287.97
    # The screenshot alone does not identify its personnel/day denominator.
    assert Decimal("633534.48") / Decimal("391.07") == pytest.approx(
        Decimal("1620"), abs=Decimal("0.02")
    )
