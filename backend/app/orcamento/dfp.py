"""Estrutura e saneamento do snapshot DFP persistido em cada revisão."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal
from numbers import Real
from typing import Any

from .exceptions import InvalidOrcamentoInputError

MAX_TEXT_LENGTH = 4000
MAX_COLLECTION_ITEMS = 250
MAX_NUMERIC_VALUE = 10_000_000_000_000

DIRECT_LABOR_ITEMS = (
    "SUPERVISOR DE OBRAS (NOTURNO)",
    "ENCARREGADO DE PINTURA",
    "AUXILIAR ADM",
    "ASSISTENTE ADM",
    "AUXILIAR GERAL (NOTURNO)",
    "AUXILIAR GERAL",
    "AUXILIAR ANDAIME",
    "VIGIA ESPAÇO CONFINADO",
    "ALPINISTA N1",
    "ALPINISTA N3",
    "PINTOR (NOTURNO)",
    "PINTOR",
    "PINTOR LETREIRO",
    "PINTOR LÍDER (NOTURNO)",
    "JATISTA",
    "HIDROJATISTA",
    "ENCARREGADO DE ANDAIMES",
    "MONTADOR DE ANDAIME",
    "MECÂNICO MONTADOR",
    "MONTADOR DE CHAPA",
    "FUNILEIRO",
    "ISOLADOR",
    "PEDREIRO",
    "TÉCNICO DE PLANEJAMENTO",
    "TÉCNICO DE SEGURANÇA",
    "INSPETOR PINT. N1",
    "ENGENHEIRO",
)

INDIRECT_LABOR_ITEMS = (
    "BASE ADMINISTRATIVA",
    "COORDENAÇÃO ADMINISTRATIVA",
    "GESTÃO DE CONTRATO",
    "PLANEJAMENTO",
    "SEGURANÇA DO TRABALHO",
    "QUALIDADE",
    "RECURSOS HUMANOS",
    "DEPARTAMENTO PESSOAL",
    "SUPRIMENTOS",
    "LOGÍSTICA",
    "FINANCEIRO",
    "APOIO ADMINISTRATIVO",
    "RESERVA",
)

TRANSPORT_ITEMS = (
    "CARRO APOIO CUSTO MANUTENÇÃO",
    "CARRO TRANSPORTE COLABORADORES",
    "VAN",
    "HOSPEDAGEM",
    "MÓVEIS DA CASA",
    "COMBUSTÍVEL CARRO APOIO",
)

LODGING_ASSET_ITEMS = (
    "COLCHÃO + CAMA",
    "GELADEIRA",
    "TV",
    "SOFÁ",
    "BEBEDOURO",
    "MESAS",
)

FOOD_ITEMS = ("CAFÉ", "ALMOÇO", "CEIA NOTURNA", "JANTAR")

EQUIPMENT_ITEMS = (
    "COMPRESSOR ELÉTRICO",
    "FRETE COMPRESSOR",
    "MÁQUINA DE HIDROJATO",
    "RESERVA 1",
    "RESERVA 2",
    "RESERVA 3",
    "RESERVA 4",
    "RESERVA 5",
    "RESERVA 6",
    "RESERVA 7",
    "VERBA P/ EQUIPAMENTOS",
)

EPI_ITEMS = (
    "PROTETOR TIPO CONCHA",
    "CAPACETE",
    "UNIFORME",
    "LUVA VAQUETA",
    "LUVA NITRÍLICA",
    "ÓCULOS AMPLA VISÃO",
    "RESPIRADOR PINTOR",
    "CINTO DE SEGURANÇA",
    "KIT JATISTA",
    "BOTA SEG",
    "MÁSCARA DESCARTÁVEL",
    "VERBA EPIs E EPCs",
)

MATERIAL_ITEMS = (
    "HARDTOP XP AMARELO SEGURANÇA",
    "HARDTOP XP BRANCO",
    "HARDTOP XP VERMELHO SEGURANÇA",
    "PRIMER / RESERVA",
    "DILUENTE",
    "THINNER 18L",
    "MATERIAL RESERVA 1",
    "MATERIAL RESERVA 2",
    "MATERIAL RESERVA 3",
    "MATERIAL RESERVA 4",
    "FRETE PARA TINTAS",
    "ABRASIVO",
    "FRETE PARA ABRASIVO",
    "CONSUMÍVEIS",
)

TOOL_ITEMS = (
    "CONTAINER ADM",
    "CONTAINER ALMOXARIFADO",
    "FRETE CONTAINER",
    "BEBEDOURO",
    "GAIOLÃO DE TINTAS",
    "TENDA PARA VIVÊNCIA",
    "VERBA PARA FERRAMENTAL",
)

OTHER_DIRECT_COST_ITEMS = (
    "VIAGENS SUPERVISÃO IDA E VOLTA",
    "MOBILIZAÇÃO E DESMOBILIZAÇÃO",
    "TRANSLADOS FUNCIONÁRIOS",
    "OUTROS (ART, LAUDOS CASO NECESSÁRIOS)",
    "EXAMES",
    "TREINAMENTOS (NR 35, NR20)",
    "PROGRAMAS (PGR, PCMSO)",
    "PLANO DE SAÚDE",
    "VALE ALIMENTAÇÃO",
    "VERBA PARA DESTINAÇÃO DE RESÍDUOS",
    "VERBA PARA ANDAIMES",
    "FRETE PARA ANDAIMES",
    "VERBA MONTAGEM DE CANTEIRO (CAMPO/ADM)",
)

INDIRECT_COST_ITEMS = ("ADM CENTRAL", "TAXA COMERCIAL", "PARTICIPAÇÃO", "TAXA DE ANTECIPAÇÃO")
TAX_ITEMS = ("IRPJ", "ISS", "CSLL", "PIS", "INSS", "COFINS", "ICMS")
FORMA_TRIBUTACAO_OPTIONS = ("LUCRO REAL", "PRESUMIDO", "SIMPLES", "IMUNE")
BRAZILIAN_UFS = frozenset(
    {
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    }
)
MACROREGIONS = frozenset({"Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"})
REGION_PATTERN = re.compile(r"^(?P<macro>[^—]+?)\s*—\s*(?P<municipio>[^/]+?)/(?P<uf>[A-Za-z]{2})$")


def _trim_text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        value = str(value)
    trimmed = value.strip()
    return trimmed[:MAX_TEXT_LENGTH]


def _non_negative_number(
    value: Any,
    *,
    default: float = 0.0,
    field: str = "valor",
    percent: bool = False,
) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise InvalidOrcamentoInputError(f"DFP: {field} deve ser numérico")
    try:
        numeric = float(value)
    except (OverflowError, ValueError) as exc:
        raise InvalidOrcamentoInputError(f"DFP: {field} excede o limite permitido") from exc
    if not math.isfinite(numeric):
        raise InvalidOrcamentoInputError(f"DFP: {field} deve ser finito")
    if numeric < 0:
        raise InvalidOrcamentoInputError(f"DFP: {field} não pode ser negativo")
    if numeric > MAX_NUMERIC_VALUE:
        raise InvalidOrcamentoInputError(f"DFP: {field} excede o limite permitido")
    if percent and numeric >= 100:
        raise InvalidOrcamentoInputError(f"DFP: {field} deve ser menor que 100")
    return numeric


def _nullable_number(value: Any, *, field: str = "valor") -> float | None:
    if value is None or value == "":
        return None
    return _non_negative_number(value, field=field)


def _location_from_seed(seed: dict[str, Any]) -> dict[str, str]:
    empty = {"pais": "Brasil", "uf": "", "municipio": "", "macrorregiao": ""}
    region = seed.get("regiao")
    if not isinstance(region, str):
        return empty
    match = REGION_PATTERN.fullmatch(region.strip())
    if match is None:
        return empty
    macro = match.group("macro").strip()
    municipio = match.group("municipio").strip()
    uf = match.group("uf").upper()
    if macro not in MACROREGIONS or uf not in BRAZILIAN_UFS or not municipio:
        return empty
    return {"pais": "Brasil", "uf": uf, "municipio": municipio, "macrorregiao": macro}


def _bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _slugify(text: str) -> str:
    letters = []
    for char in text.casefold():
        if char.isalnum():
            letters.append(char)
        elif letters and letters[-1] != "_":
            letters.append("_")
    return "".join(letters).strip("_") or "item"


def _labor_item(label: str) -> dict[str, Any]:
    return {
        "id": _slugify(label),
        "label": label,
        "quantity": 0.0,
        "hours_per_employee": 0.0,
        "worked_hours": 0.0,
        "worked_days": 0.0,
        "mobilization_days": 0.0,
        "months": 0.0,
        "salary_real": 0.0,
        "salary_base_hours": 0.0,
        "hourly_rate": 0.0,
        "manual_total": 0.0,
        "notes": "",
    }


def _cost_item(label: str) -> dict[str, Any]:
    return {
        "id": _slugify(label),
        "label": label,
        "quantity": 0.0,
        "unit_cost": 0.0,
        "notes": "",
    }


def _percent_item(label: str, percent: float = 0.0) -> dict[str, Any]:
    return {
        "id": _slugify(label),
        "label": label,
        "aliquot_percent": percent,
        "notes": "",
    }


def build_default_dfp_snapshot(
    seed: dict[str, Any] | None = None, *, calculation_version: int = 1
) -> dict[str, Any]:
    referencia = seed or {}
    location = _location_from_seed(referencia)
    snapshot = {
        "calculation_version": calculation_version,
        "metadata": {
            "codigo_dfp": _trim_text(referencia.get("codigo_dfp")),
            "titulo": "DEMONSTRATIVO DE FORMAÇÃO DE PREÇOS",
            "cliente_unidade": _trim_text(referencia.get("contratante")),
            "folha": "1 de 5",
            "previsao_inicio": None,
            "mobilizacao_text": _trim_text(referencia.get("mobilizacao")),
            "desmobilizacao_text": _trim_text(referencia.get("desmobilizacao")),
            "prazo_execucao_text": _trim_text(
                referencia.get("prazo_execucao_dias"),
                default="",
            ),
            "descricao_projeto": _trim_text(referencia.get("escopo")),
            **location,
            "zona_salarial": "",
            "area_total": _nullable_number(
                referencia.get("area_total"), field="metadata.area_total"
            ),
            "area_unidade": _trim_text(referencia.get("area_unidade_base"), default="m²"),
            "sabado_fator": 0.0,
            "domingo_fator": 0.0,
            "semana_fator": 0.0,
            "quantidade_sabado": 0.0,
            "quantidade_domingo": 0.0,
            "quantidade_dias_semana": 0.0,
            "horas_sabado": 0.0,
            "horas_domingo": 0.0,
            "horas_semana": 0.0,
        },
        "mao_de_obra_direta": {
            "items": [_labor_item(label) for label in DIRECT_LABOR_ITEMS],
            "adjustments": [
                {"id": "adicional_noturno", "label": "Adicional noturno", "percent": 0.0},
                {
                    "id": "adicional_transferencia",
                    "label": "Adicional de transferência",
                    "percent": 0.0,
                },
                {"id": "aviso_previo", "label": "Aviso prévio", "percent": 0.0},
            ],
            "social_charges_percent": 0.0,
        },
        "mao_de_obra_indireta": {
            "items": [_labor_item(label) for label in INDIRECT_LABOR_ITEMS],
            "adjustments": [
                {
                    "id": "adicional_periculosidade",
                    "label": "Adicional de periculosidade",
                    "percent": 0.0,
                },
                {
                    "id": "adicional_transferencia",
                    "label": "Adicional de transferência",
                    "percent": 0.0,
                },
                {"id": "aviso_previo", "label": "Aviso prévio", "percent": 0.0},
            ],
            "social_charges_percent": 0.0,
        },
        "veiculos_hospedagem": {
            "items": [_cost_item(label) for label in TRANSPORT_ITEMS],
            "lodging_assets": [_cost_item(label) for label in LODGING_ASSET_ITEMS],
        },
        "alimentacao": {
            "items": [_cost_item(label) for label in FOOD_ITEMS],
            "total_funcionarios": 0.0,
            "total_dias_mobilizacao": 0.0,
        },
        "equipamentos": {"items": [_cost_item(label) for label in EQUIPMENT_ITEMS]},
        "epis_epcs": {"items": [_cost_item(label) for label in EPI_ITEMS]},
        "materiais_consumo": {"items": [_cost_item(label) for label in MATERIAL_ITEMS]},
        "ferramental": {"items": [_cost_item(label) for label in TOOL_ITEMS]},
        "outros_custos_diretos": {
            "items": [_cost_item(label) for label in OTHER_DIRECT_COST_ITEMS]
        },
        "custos_indiretos": {
            "items": [
                _percent_item("ADM CENTRAL", 0.0),
                _percent_item("TAXA COMERCIAL", 0.0),
                _percent_item("PARTICIPAÇÃO", 0.0),
                _percent_item("TAXA DE ANTECIPAÇÃO", 0.0),
            ]
        },
        "bdi": {"factor_percent": 0.0},
        "impostos": {
            "items": [
                _percent_item("IRPJ", 0.0),
                _percent_item("ISS", 0.0),
                _percent_item("CSLL", 0.0),
                _percent_item("PIS", 0.0),
                _percent_item("INSS", 0.0),
                _percent_item("COFINS", 0.0),
                _percent_item("ICMS", 0.0),
            ]
        },
        "informacoes_adicionais": {
            "regime_tributacao": _trim_text(referencia.get("regime_tributario")),
            "possui_beneficio_fiscal": False,
            "inss_isento": False,
            "observacoes": "",
        },
    }
    if calculation_version == 2:
        # Jornada padrão de 8 h no dia de semana: zerada, a mão de obra sairia R$ 0,00
        # sem nenhum sinal. Sábado e domingo variam por contrato e seguem em branco.
        snapshot = {
            **snapshot,
            "metadata": {**snapshot["metadata"], "horas_semana": 8.0},
            "mao_de_obra_direta": {
                **snapshot["mao_de_obra_direta"],
                "adjustments": [
                    {"id": "adicional_noturno", "label": "Adicional noturno", "percent": 0},
                    {"id": "adicional_periculosidade", "label": "Periculosidade", "percent": 0},
                ],
                "items": [{**item, "worked_days": None, "saturday_days": None, "sunday_days": None}
                          for item in snapshot["mao_de_obra_direta"]["items"]],
            },
        }
        return _normalize_v2(snapshot, snapshot)
    return snapshot


def get_dfp_window_schema(*, calculation_version: int = 2) -> dict[str, Any]:
    """Metadados suficientes para a UI montar as janelas do DFP."""
    schema = {
        "template_code": "DFP 0055-26",
        "version": "dfp.window.v1",
        "profile": {
            "code": "dfp-0055-26",
            "compatibility": True,
            "description": "Estrutura compatível com DFP 0055-26; não é regra universal.",
        },
        "defaults": build_default_dfp_snapshot(),
        "options": {
            "forma_tributacao": list(FORMA_TRIBUTACAO_OPTIONS),
        },
        "sections": [
            {
                "id": "metadata",
                "title": "Identificação e Escopo",
                "kind": "fields",
                "fields": [
                    {"key": "codigo_dfp", "label": "Código DFP", "type": "text"},
                    {"key": "cliente_unidade", "label": "Contratante / unidade", "type": "text"},
                    {"key": "folha", "label": "Folha", "type": "text"},
                    {"key": "previsao_inicio", "label": "Previsão de início", "type": "date"},
                    {"key": "mobilizacao_text", "label": "Mobilização", "type": "text"},
                    {"key": "desmobilizacao_text", "label": "Desmobilização", "type": "text"},
                    {"key": "prazo_execucao_text", "label": "Prazo da obra", "type": "text"},
                    {
                        "key": "descricao_projeto",
                        "label": "Descrição do projeto",
                        "type": "textarea",
                    },
                    {"key": "pais", "label": "País", "type": "text"},
                    {"key": "uf", "label": "UF", "type": "text"},
                    {"key": "municipio", "label": "Município", "type": "text"},
                    {"key": "macrorregiao", "label": "Macrorregião", "type": "text"},
                    {"key": "zona_salarial", "label": "Zona salarial", "type": "text"},
                    {"key": "area_total", "label": "Área total", "type": "number", "step": "0.01"},
                    {"key": "area_unidade", "label": "Unidade da área", "type": "text"},
                    {
                        "key": "sabado_fator",
                        "label": "Fator sábado",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "domingo_fator",
                        "label": "Fator domingo",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "semana_fator",
                        "label": "Fator semana",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "quantidade_sabado",
                        "label": "Qtd. sábado",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "quantidade_domingo",
                        "label": "Qtd. domingo",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "quantidade_dias_semana",
                        "label": "Qtd. dias semana",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "horas_sabado",
                        "label": "Horas sábado",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "horas_domingo",
                        "label": "Horas domingo",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "horas_semana",
                        "label": "Horas semana",
                        "type": "number",
                        "step": "0.01",
                    },
                ],
            },
            {
                "id": "mao_de_obra_direta",
                "title": "Mão de Obra Direta",
                "kind": "labor-table",
                "columns": [
                    {"key": "quantity", "label": "Qtd. média", "type": "number", "step": "0.01"},
                    {
                        "key": "hours_per_employee",
                        "label": "Horas / empregado",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "worked_hours",
                        "label": "Horas trabalhadas",
                        "type": "number",
                        "step": "0.01",
                    },
                    {"key": "worked_days", "label": "Qtd. dias", "type": "number", "step": "0.01"},
                    {
                        "key": "mobilization_days",
                        "label": "Dias mob.",
                        "type": "number",
                        "step": "0.01",
                    },
                    {"key": "months", "label": "Meses", "type": "number", "step": "0.01"},
                    {
                        "key": "salary_real",
                        "label": "Salário real",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "salary_base_hours",
                        "label": "Horas base",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "hourly_rate",
                        "label": "Salário/hora",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "manual_total",
                        "label": "Total adicional",
                        "type": "number",
                        "step": "0.01",
                    },
                    {"key": "notes", "label": "Notas", "type": "text"},
                ],
                "rows": [{"id": _slugify(label), "label": label} for label in DIRECT_LABOR_ITEMS],
                "adjustments": [
                    {"id": "adicional_noturno", "label": "Adicional noturno"},
                    {"id": "adicional_transferencia", "label": "Adicional de transferência"},
                    {"id": "aviso_previo", "label": "Aviso prévio"},
                ],
                "footer_field": {
                    "key": "social_charges_percent",
                    "label": "Encargos sociais (%)",
                    "type": "number",
                    "step": "0.01",
                },
            },
            {
                "id": "mao_de_obra_indireta",
                "title": "Mão de Obra Indireta",
                "kind": "labor-table",
                "columns": [
                    {"key": "quantity", "label": "Qtd. média", "type": "number", "step": "0.01"},
                    {
                        "key": "hours_per_employee",
                        "label": "Horas / empregado",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "salary_real",
                        "label": "Salário real",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "salary_base_hours",
                        "label": "Horas base",
                        "type": "number",
                        "step": "0.01",
                    },
                    {
                        "key": "manual_total",
                        "label": "Total adicional",
                        "type": "number",
                        "step": "0.01",
                    },
                    {"key": "notes", "label": "Notas", "type": "text"},
                ],
                "rows": [{"id": _slugify(label), "label": label} for label in INDIRECT_LABOR_ITEMS],
                "adjustments": [
                    {"id": "adicional_periculosidade", "label": "Adicional de periculosidade"},
                    {"id": "adicional_transferencia", "label": "Adicional de transferência"},
                    {"id": "aviso_previo", "label": "Aviso prévio"},
                ],
                "footer_field": {
                    "key": "social_charges_percent",
                    "label": "Encargos sociais (%)",
                    "type": "number",
                    "step": "0.01",
                },
            },
            *[
                {
                    "id": section_id,
                    "title": title,
                    "kind": "cost-table",
                    "columns": [
                        {
                            "key": "quantity",
                            "label": "Quantidade",
                            "type": "number",
                            "step": "0.01",
                        },
                        {
                            "key": "unit_cost",
                            "label": "Custo unitário",
                            "type": "number",
                            "step": "0.01",
                        },
                        {"key": "notes", "label": "Notas", "type": "text"},
                    ],
                    "rows": [{"id": _slugify(label), "label": label} for label in labels],
                }
                for section_id, title, labels in (
                    ("veiculos_hospedagem", "Veículos e Hospedagem", TRANSPORT_ITEMS),
                    ("alimentacao", "Alimentação", FOOD_ITEMS),
                    ("equipamentos", "Equipamentos", EQUIPMENT_ITEMS),
                    ("epis_epcs", "EPI / EPC", EPI_ITEMS),
                    ("materiais_consumo", "Materiais de Consumo", MATERIAL_ITEMS),
                    ("ferramental", "Ferramental", TOOL_ITEMS),
                    ("outros_custos_diretos", "Outros Custos Diretos", OTHER_DIRECT_COST_ITEMS),
                )
            ],
            {
                "id": "lodging_assets",
                "title": "Móveis do Alojamento",
                "kind": "cost-table",
                "state_key": "veiculos_hospedagem.lodging_assets",
                "columns": [
                    {"key": "quantity", "label": "Quantidade", "type": "number", "step": "0.01"},
                    {"key": "unit_cost", "label": "Valor real", "type": "number", "step": "0.01"},
                    {"key": "notes", "label": "Notas", "type": "text"},
                ],
                "rows": [{"id": _slugify(label), "label": label} for label in LODGING_ASSET_ITEMS],
            },
            {
                "id": "precificacao",
                "title": "Precificação e Impostos",
                "kind": "percent-groups",
                "groups": [
                    {
                        "state_key": "custos_indiretos",
                        "title": "Custos indiretos",
                        "rows": [
                            {"id": _slugify(label), "label": label} for label in INDIRECT_COST_ITEMS
                        ],
                    },
                    {
                        "state_key": "impostos",
                        "title": "Impostos",
                        "rows": [{"id": _slugify(label), "label": label} for label in TAX_ITEMS],
                    },
                ],
                "field": {
                    "state_key": "bdi",
                    "key": "factor_percent",
                    "label": "Fator BDI (%)",
                    "type": "number",
                    "step": "0.01",
                },
            },
            {
                "id": "informacoes_adicionais",
                "title": "Informações Adicionais",
                "kind": "fields",
                "fields": [
                    {"key": "regime_tributacao", "label": "Forma de tributação", "type": "select"},
                    {
                        "key": "possui_beneficio_fiscal",
                        "label": "Possui benefício fiscal",
                        "type": "boolean",
                    },
                    {"key": "inss_isento", "label": "Isento de INSS", "type": "boolean"},
                    {"key": "observacoes", "label": "Observações", "type": "textarea"},
                ],
            },
        ],
    }
    return _schema_v2(schema) if calculation_version == 2 else schema


def _schema_v2(schema: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(schema)
    result["version"] = "dfp.window.v2"
    result["defaults"] = build_default_dfp_snapshot(calculation_version=2)
    excluded = {"mao_de_obra_indireta", "lodging_assets"}
    result["sections"] = [
        section for section in result["sections"] if section["id"] not in excluded
    ]
    for section in result["sections"]:
        if section["id"] == "metadata":
            removidos = {"zona_salarial", "codigo_dfp", "folha", "previsao_inicio"}
            section["fields"] = [
                field for field in section["fields"] if field["key"] not in removidos
            ]
            # O multiplicador é o pagamento integral da hora (1,5 = hora e meia): as horas
            # extras são lançadas à parte e não estão dentro das horas normais.
            labels = {
                "sabado_fator": "Multiplicador hora extra sábado (1,5 = hora e meia)",
                "domingo_fator": "Multiplicador hora extra domingo (2 = hora dobrada)",
                "semana_fator": "Multiplicador hora extra semanal (1,5 = hora e meia)",
                "horas_semana": "Horas por dia de semana",
                "quantidade_dias_semana": "Qtd. dias de semana",
                "quantidade_sabado": "Qtd. de sábados",
                "quantidade_domingo": "Qtd. de domingos",
                "mobilizacao_text": "Prazo para Mobilização",
                "desmobilizacao_text": "Prazo para Desmobilização",
            }
            for field in section["fields"]:
                field["label"] = labels.get(field["key"], field["label"])
                if field["key"].startswith("quantidade_"):
                    field["step"] = "1"
        if section["id"] == "mao_de_obra_direta":
            ocultas = {"hours_per_employee", "salary_base_hours", "manual_total"}
            section["columns"] = [
                column for column in section["columns"] if column["key"] not in ocultas
            ]
            section["columns"] += [
                {"key": key, "label": label, "type": "number", "step": step}
                for key, label, step in (
                    ("saturday_days", "Sábados", "1"), ("sunday_days", "Domingos", "1"),
                    ("overtime_week_hours", "Horas extras semanais", "0.01"),
                    ("overtime_saturday_hours", "Horas extras sábado", "0.01"),
                    ("overtime_sunday_hours", "Horas extras domingo", "0.01"),
                )]
            rotulos_v2 = {
                "quantity": "Quantidade de pessoas",
                "worked_days": "Qtd. dias",
                "worked_hours": "Horas trabalhadas (equipe)",
            }
            for column in section["columns"]:
                column["label"] = rotulos_v2.get(column["key"], column["label"])
                if column["key"] in {"quantity", "worked_days", "mobilization_days"}:
                    column["step"] = "1"
                if column["key"] in {"worked_hours", "hourly_rate"}:
                    column["readonly"] = True
            section["adjustments"] = []
        if section["id"] == "alimentacao":
            section["columns"] = [{**column, "readonly": column["key"] == "quantity"}
                                  for column in section["columns"]]
        if section["id"] == "informacoes_adicionais":
            section["fields"] = [
                field for field in section["fields"] if field["key"] != "regime_tributacao"
            ]
    result["sections"][2:2] = [
        {"id": "adicionais", "title": "Adicionais por função", "kind": "labor-adjustments"},
        {
            "id": "custos_administrativos",
            "title": "Custos Administrativos",
            "kind": "fields",
            "fields": [
                {"key": key, "label": label, "type": "number", "step": step}
                for key, label, step in (
                    ("daily_cost", "Custo administrativo por dia (R$)", "0.01"),
                    ("days", "Quantidade de dias", "1"),
                    ("considered_percent", "Percentual considerado (%)", "0.01"),
                    ("multiplier", "Multiplicador", "0.01"),
                    ("discount_percent", "Desconto do subtópico (%)", "0.01"),
                )
            ],
        },
    ]
    return result


def _incoming_list(items: Any, *, field: str) -> list[dict[str, Any]]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise InvalidOrcamentoInputError(f"DFP: {field} deve ser uma lista")
    if any(not isinstance(item, dict) for item in items):
        raise InvalidOrcamentoInputError(f"DFP: cada item de {field} deve ser um objeto")
    if len(items) > MAX_COLLECTION_ITEMS:
        raise InvalidOrcamentoInputError(
            f"DFP: {field} aceita no máximo {MAX_COLLECTION_ITEMS} itens"
        )
    return items


def _section(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise InvalidOrcamentoInputError(f"DFP: {name} deve ser um objeto")
    return value


def _normalize_labor_items(
    items: Any, defaults: list[dict[str, Any]], *, field: str
) -> list[dict[str, Any]]:
    incoming = _incoming_list(items, field=field)
    merged = []
    for index in range(max(len(defaults), len(incoming))):
        current = incoming[index] if index < len(incoming) else {}
        if index < len(defaults):
            default = defaults[index]
        else:
            default = _labor_item(_trim_text(current.get("label"), default=f"ITEM {index + 1}"))
        prefix = f"{field}[{index}]"
        merged.append(
            {
                "id": _trim_text(current.get("id"), default=default["id"]) or default["id"],
                "label": _trim_text(current.get("label"), default=default["label"])
                or default["label"],
                "quantity": _non_negative_number(
                    current.get("quantity"), default=default["quantity"], field=f"{prefix}.quantity"
                ),
                "hours_per_employee": _non_negative_number(
                    current.get("hours_per_employee"),
                    default=default["hours_per_employee"],
                    field=f"{prefix}.hours_per_employee",
                ),
                "worked_hours": _non_negative_number(
                    current.get("worked_hours"),
                    default=default["worked_hours"],
                    field=f"{prefix}.worked_hours",
                ),
                "worked_days": _non_negative_number(
                    current.get("worked_days"),
                    default=default["worked_days"],
                    field=f"{prefix}.worked_days",
                ),
                "mobilization_days": _non_negative_number(
                    current.get("mobilization_days"),
                    default=default["mobilization_days"],
                    field=f"{prefix}.mobilization_days",
                ),
                "months": _non_negative_number(
                    current.get("months"), default=default["months"], field=f"{prefix}.months"
                ),
                "salary_real": _non_negative_number(
                    current.get("salary_real"),
                    default=default["salary_real"],
                    field=f"{prefix}.salary_real",
                ),
                "salary_base_hours": _non_negative_number(
                    current.get("salary_base_hours"),
                    default=default["salary_base_hours"],
                    field=f"{prefix}.salary_base_hours",
                ),
                "hourly_rate": _non_negative_number(
                    current.get("hourly_rate"),
                    default=default["hourly_rate"],
                    field=f"{prefix}.hourly_rate",
                ),
                "manual_total": _non_negative_number(
                    current.get("manual_total"),
                    default=default["manual_total"],
                    field=f"{prefix}.manual_total",
                ),
                "notes": _trim_text(current.get("notes")),
            }
        )
    return merged


def _normalize_cost_items(
    items: Any, defaults: list[dict[str, Any]], *, field: str
) -> list[dict[str, Any]]:
    incoming = _incoming_list(items, field=field)
    merged = []
    for index in range(max(len(defaults), len(incoming))):
        current = incoming[index] if index < len(incoming) else {}
        if index < len(defaults):
            default = defaults[index]
        else:
            default = _cost_item(_trim_text(current.get("label"), default=f"ITEM {index + 1}"))
        prefix = f"{field}[{index}]"
        merged.append(
            {
                "id": _trim_text(current.get("id"), default=default["id"]) or default["id"],
                "label": _trim_text(current.get("label"), default=default["label"])
                or default["label"],
                "quantity": _non_negative_number(
                    current.get("quantity"), default=default["quantity"], field=f"{prefix}.quantity"
                ),
                "unit_cost": _non_negative_number(
                    current.get("unit_cost"),
                    default=default["unit_cost"],
                    field=f"{prefix}.unit_cost",
                ),
                "notes": _trim_text(current.get("notes")),
            }
        )
    return merged


def _normalize_adjustments(
    items: Any, defaults: list[dict[str, Any]], *, field: str
) -> list[dict[str, Any]]:
    incoming = _incoming_list(items, field=field)
    merged = []
    for index in range(max(len(defaults), len(incoming))):
        current = incoming[index] if index < len(incoming) else {}
        default = (
            defaults[index]
            if index < len(defaults)
            else {"id": f"ajuste_{index + 1}", "label": f"AJUSTE {index + 1}", "percent": 0.0}
        )
        merged.append(
            {
                "id": _trim_text(current.get("id"), default=default["id"]) or default["id"],
                "label": _trim_text(current.get("label"), default=default["label"])
                or default["label"],
                "percent": _non_negative_number(
                    current.get("percent"),
                    default=default["percent"],
                    field=f"{field}[{index}].percent",
                    percent=True,
                ),
            }
        )
    return merged


def _normalize_percent_items(
    items: Any, defaults: list[dict[str, Any]], *, field: str
) -> list[dict[str, Any]]:
    incoming = _incoming_list(items, field=field)
    merged = []
    for index in range(max(len(defaults), len(incoming))):
        current = incoming[index] if index < len(incoming) else {}
        if index < len(defaults):
            default = defaults[index]
        else:
            default = _percent_item(_trim_text(current.get("label"), default=f"ITEM {index + 1}"))
        merged.append(
            {
                "id": _trim_text(current.get("id"), default=default["id"]) or default["id"],
                "label": _trim_text(current.get("label"), default=default["label"])
                or default["label"],
                "aliquot_percent": _non_negative_number(
                    current.get("aliquot_percent"),
                    default=default["aliquot_percent"],
                    field=f"{field}[{index}].aliquot_percent",
                    percent=True,
                ),
                "notes": _trim_text(current.get("notes")),
            }
        )
    return merged


def normalize_dfp_payload(
    payload: dict[str, Any] | None,
    *,
    seed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    defaults = build_default_dfp_snapshot(seed)
    if payload is None:
        return defaults
    if not isinstance(payload, dict):
        raise InvalidOrcamentoInputError("DFP deve ser um objeto")

    metadata = _section(payload, "metadata")
    result = deepcopy(defaults)
    result["metadata"] = {
        **defaults["metadata"],
        "codigo_dfp": _trim_text(
            metadata.get("codigo_dfp"), default=defaults["metadata"]["codigo_dfp"]
        ),
        "titulo": _trim_text(metadata.get("titulo"), default=defaults["metadata"]["titulo"]),
        "cliente_unidade": _trim_text(
            metadata.get("cliente_unidade"),
            default=defaults["metadata"]["cliente_unidade"],
        ),
        "folha": _trim_text(metadata.get("folha"), default=defaults["metadata"]["folha"]),
        "previsao_inicio": _trim_text(metadata.get("previsao_inicio")) or None,
        "mobilizacao_text": _trim_text(
            metadata.get("mobilizacao_text"),
            default=defaults["metadata"]["mobilizacao_text"],
        ),
        "desmobilizacao_text": _trim_text(
            metadata.get("desmobilizacao_text"),
            default=defaults["metadata"]["desmobilizacao_text"],
        ),
        "prazo_execucao_text": _trim_text(
            metadata.get("prazo_execucao_text"),
            default=defaults["metadata"]["prazo_execucao_text"],
        ),
        "descricao_projeto": _trim_text(
            metadata.get("descricao_projeto"),
            default=defaults["metadata"]["descricao_projeto"],
        ),
        "pais": _trim_text(metadata.get("pais"), default=defaults["metadata"]["pais"]),
        "uf": _trim_text(metadata.get("uf"), default=defaults["metadata"]["uf"]),
        "municipio": _trim_text(
            metadata.get("municipio"), default=defaults["metadata"]["municipio"]
        ),
        "macrorregiao": _trim_text(
            metadata.get("macrorregiao"), default=defaults["metadata"]["macrorregiao"]
        ),
        "zona_salarial": _trim_text(
            metadata.get("zona_salarial"), default=defaults["metadata"]["zona_salarial"]
        ),
        "area_total": _nullable_number(metadata.get("area_total"), field="metadata.area_total"),
        "area_unidade": _trim_text(
            metadata.get("area_unidade"),
            default=defaults["metadata"]["area_unidade"],
        ),
        "sabado_fator": _non_negative_number(
            metadata.get("sabado_fator"),
            default=defaults["metadata"]["sabado_fator"],
            field="metadata.sabado_fator",
        ),
        "domingo_fator": _non_negative_number(
            metadata.get("domingo_fator"),
            default=defaults["metadata"]["domingo_fator"],
            field="metadata.domingo_fator",
        ),
        "semana_fator": _non_negative_number(
            metadata.get("semana_fator"),
            default=defaults["metadata"]["semana_fator"],
            field="metadata.semana_fator",
        ),
        "quantidade_sabado": _non_negative_number(
            metadata.get("quantidade_sabado"),
            default=defaults["metadata"]["quantidade_sabado"],
            field="metadata.quantidade_sabado",
        ),
        "quantidade_domingo": _non_negative_number(
            metadata.get("quantidade_domingo"),
            default=defaults["metadata"]["quantidade_domingo"],
            field="metadata.quantidade_domingo",
        ),
        "quantidade_dias_semana": _non_negative_number(
            metadata.get("quantidade_dias_semana"),
            default=defaults["metadata"]["quantidade_dias_semana"],
            field="metadata.quantidade_dias_semana",
        ),
        "horas_sabado": _non_negative_number(
            metadata.get("horas_sabado"),
            default=defaults["metadata"]["horas_sabado"],
            field="metadata.horas_sabado",
        ),
        "horas_domingo": _non_negative_number(
            metadata.get("horas_domingo"),
            default=defaults["metadata"]["horas_domingo"],
            field="metadata.horas_domingo",
        ),
        "horas_semana": _non_negative_number(
            metadata.get("horas_semana"),
            default=defaults["metadata"]["horas_semana"],
            field="metadata.horas_semana",
        ),
    }

    for section_name in ("mao_de_obra_direta", "mao_de_obra_indireta"):
        current = _section(payload, section_name)
        default = defaults[section_name]
        result[section_name] = {
            "items": _normalize_labor_items(
                current.get("items"), default["items"], field=f"{section_name}.items"
            ),
            "adjustments": _normalize_adjustments(
                current.get("adjustments"),
                default["adjustments"],
                field=f"{section_name}.adjustments",
            ),
            "social_charges_percent": _non_negative_number(
                current.get("social_charges_percent"),
                default=default["social_charges_percent"],
                field=f"{section_name}.social_charges_percent",
                percent=True,
            ),
        }

    for section_name in (
        "veiculos_hospedagem",
        "alimentacao",
        "equipamentos",
        "epis_epcs",
        "materiais_consumo",
        "ferramental",
        "outros_custos_diretos",
    ):
        current = _section(payload, section_name)
        default = defaults[section_name]
        result[section_name] = {
            "items": _normalize_cost_items(
                current.get("items"), default["items"], field=f"{section_name}.items"
            )
        }
        if section_name == "veiculos_hospedagem":
            result[section_name]["lodging_assets"] = _normalize_cost_items(
                current.get("lodging_assets"),
                default["lodging_assets"],
                field="veiculos_hospedagem.lodging_assets",
            )
        if section_name == "alimentacao":
            result[section_name]["total_funcionarios"] = _non_negative_number(
                current.get("total_funcionarios"),
                default=default["total_funcionarios"],
                field="alimentacao.total_funcionarios",
            )
            result[section_name]["total_dias_mobilizacao"] = _non_negative_number(
                current.get("total_dias_mobilizacao"),
                default=default["total_dias_mobilizacao"],
                field="alimentacao.total_dias_mobilizacao",
            )

    for section_name in ("custos_indiretos", "impostos"):
        current = _section(payload, section_name)
        default = defaults[section_name]
        result[section_name] = {
            "items": _normalize_percent_items(
                current.get("items"), default["items"], field=f"{section_name}.items"
            )
        }

    bdi = _section(payload, "bdi")
    result["bdi"] = {
        "factor_percent": _non_negative_number(
            bdi.get("factor_percent"),
            default=defaults["bdi"]["factor_percent"],
            field="bdi.factor_percent",
            percent=True,
        )
    }

    info = _section(payload, "informacoes_adicionais")
    result["informacoes_adicionais"] = {
        "regime_tributacao": _trim_text(
            info.get("regime_tributacao"),
            default=defaults["informacoes_adicionais"]["regime_tributacao"],
        ),
        "possui_beneficio_fiscal": _bool(
            info.get("possui_beneficio_fiscal"),
            default=defaults["informacoes_adicionais"]["possui_beneficio_fiscal"],
        ),
        "inss_isento": _bool(
            info.get("inss_isento"),
            default=defaults["informacoes_adicionais"]["inss_isento"],
        ),
        "observacoes": _trim_text(info.get("observacoes")),
    }
    total_tax_percent = sum(item["aliquot_percent"] for item in result["impostos"]["items"])
    if total_tax_percent >= 100:
        raise InvalidOrcamentoInputError("Soma das alíquotas de impostos deve ser menor que 100")
    version = payload.get("calculation_version", 1)
    if isinstance(version, bool) or version not in (1, 2):
        raise InvalidOrcamentoInputError("DFP: calculation_version deve ser 1 ou 2")
    result["calculation_version"] = version
    return _normalize_v2(result, payload) if version == 2 else result


CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def _decimal(value: int | float | Decimal) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    if not value.is_finite() or abs(value) > MAX_NUMERIC_VALUE:
        raise InvalidOrcamentoInputError("DFP: resultado calculado excede o limite permitido")
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _count(value: Any, *, field: str) -> float:
    number = _non_negative_number(value, field=field)
    if not number.is_integer():
        raise InvalidOrcamentoInputError(f"DFP: {field} deve ser um número inteiro")
    return number


def _bounded_percent(value: Any, *, field: str, default: float = 0) -> float:
    number = _non_negative_number(value, field=field, default=default)
    if number > 100:
        raise InvalidOrcamentoInputError(f"DFP: {field} deve estar entre 0 e 100")
    return number


def _ensure_unique_item_identity(
    items: list[dict[str, Any]], *, field: str, unique_labels: bool = True
) -> None:
    ids: set[str] = set()
    labels: set[str] = set()
    for index, item in enumerate(items):
        item_id = item.get("id")
        label = item.get("label")
        if not isinstance(item_id, str) or not item_id.strip():
            raise InvalidOrcamentoInputError(f"DFP: {field}[{index}].id é obrigatório")
        if not isinstance(label, str) or not label.strip():
            raise InvalidOrcamentoInputError(f"DFP: {field}[{index}].label é obrigatório")
        id_key = item_id.strip().casefold()
        label_key = label.strip().casefold()
        if id_key in ids:
            raise InvalidOrcamentoInputError(f"DFP: identificadores duplicados em {field}")
        if unique_labels and label_key in labels:
            raise InvalidOrcamentoInputError(f"DFP: rótulos duplicados em {field}")
        ids.add(id_key)
        labels.add(label_key)


def _validate_incoming_item_identity(
    items: list[dict[str, Any]], *, field: str, unique_labels: bool = True
) -> None:
    """Rejeita identidade explicitamente vazia antes de aplicar defaults de linhas fixas."""
    ids: set[str] = set()
    labels: set[str] = set()
    for index, item in enumerate(items):
        if "id" in item:
            item_id = item["id"]
            if not isinstance(item_id, str) or not item_id.strip():
                raise InvalidOrcamentoInputError(f"DFP: {field}[{index}].id é obrigatório")
            id_key = item_id.strip().casefold()
            if id_key in ids:
                raise InvalidOrcamentoInputError(f"DFP: identificadores duplicados em {field}")
            ids.add(id_key)
        if "label" in item:
            label = item["label"]
            if not isinstance(label, str) or not label.strip():
                raise InvalidOrcamentoInputError(f"DFP: {field}[{index}].label é obrigatório")
            label_key = label.strip().casefold()
            if unique_labels and label_key in labels:
                raise InvalidOrcamentoInputError(f"DFP: rótulos duplicados em {field}")
            labels.add(label_key)


def _labor_v2_values(item: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Decimal]:
    """Dias de execução excluem mobilização; extras são horas adicionais por pessoa."""
    def _herdado(chave: str, padrao: str) -> Decimal:
        valor = item.get(chave)
        return _decimal(metadata[padrao] if valor is None else valor)

    days = _herdado("worked_days", "quantidade_dias_semana")
    saturday = _herdado("saturday_days", "quantidade_sabado")
    sunday = _herdado("sunday_days", "quantidade_domingo")
    mobilization = _decimal(item["mobilization_days"])
    quantity = _decimal(item["quantity"])
    hourly = _decimal(item["salary_real"]) / Decimal("220")
    hours = (
        (days + mobilization) * _decimal(metadata["horas_semana"])
        + saturday * _decimal(metadata["horas_sabado"])
        + sunday * _decimal(metadata["horas_domingo"])
    ) * quantity
    overtime = quantity * hourly * sum(
        (_decimal(item.get(key, 0)) * _decimal(metadata[factor]) for key, factor in (
            ("overtime_week_hours", "semana_fator"),
            ("overtime_saturday_hours", "sabado_fator"),
            ("overtime_sunday_hours", "domingo_fator"),
        )), start=Decimal("0"),
    )
    return {
        "hours": hours,
        "hourly": hourly,
        "salary": hours * hourly,
        "overtime": overtime,
        "person_days": (days + mobilization + saturday + sunday) * quantity,
    }


def _normalize_v2_adjustments(
    section: dict[str, Any], incoming: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = {item["id"]: item for item in section["items"]}
    defaults = [
        {"id": "adicional_noturno", "label": "Adicional noturno", "percent": 0},
        {"id": "adicional_periculosidade", "label": "Periculosidade", "percent": 0},
    ]
    adjustments = _incoming_list(incoming.get("adjustments", defaults), field="adjustments")
    _validate_incoming_item_identity(
        adjustments, field="mao_de_obra_direta.adjustments", unique_labels=False
    )
    result = []
    for index, adjustment in enumerate(adjustments):
        if adjustment.get("id") in ("aviso_previo", "adicional_transferencia"):
            continue
        normalized = _normalize_adjustments([adjustment], [], field="adjustments")[0]
        target = _trim_text(adjustment.get("labor_item_id"))
        quantity = _count(adjustment.get("quantity"), field=f"adjustments[{index}].quantity")
        base = adjustment.get("base", "salary")
        if base not in ("salary", "salary_and_overtime"):
            raise InvalidOrcamentoInputError("DFP: base de adicional inválida")
        if quantity and (target not in rows or quantity > rows[target]["quantity"]):
            raise InvalidOrcamentoInputError(
                "DFP: quantidade de adicional excede a função selecionada"
            )
        result.append({**normalized, "labor_item_id": target, "quantity": quantity, "base": base})
    return result


def _normalize_v2(result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Extensão versionada: nunca converte implicitamente os cálculos históricos."""
    metadata = result["metadata"]
    incoming_metadata = _section(payload, "metadata")
    raw_data_inicio = incoming_metadata.get("data_inicio")
    data_inicio_text = _trim_text(raw_data_inicio) or None
    literal_na = isinstance(raw_data_inicio, str) and raw_data_inicio.strip().upper() == "N/A"
    metadata["data_inicio"] = data_inicio_text
    metadata["contratante_override"] = _trim_text(
        incoming_metadata.get("contratante_override")
    ) or None
    metadata["data_inicio_na"] = _bool(
        incoming_metadata.get("data_inicio_na"), default=False
    ) or literal_na
    if metadata["data_inicio_na"]:
        metadata["data_inicio"] = None
    elif metadata["data_inicio"]:
        from datetime import date
        try:
            date.fromisoformat(metadata["data_inicio"])
        except ValueError as exc:
            raise InvalidOrcamentoInputError(
                "Data de início deve ser uma data válida ou N/A"
            ) from exc
    for key in ("quantidade_dias_semana", "quantidade_sabado", "quantidade_domingo"):
        _count(metadata[key], field=f"metadata.{key}")
    section = result["mao_de_obra_direta"]
    incoming = _section(payload, "mao_de_obra_direta")
    raw_items = _incoming_list(incoming.get("items"), field="mao_de_obra_direta.items")
    _validate_incoming_item_identity(raw_items, field="mao_de_obra_direta.items")
    if "items" in incoming:
        section = {**section, "items": section["items"][:len(raw_items)]}
    rows = []
    for index, item in enumerate(section["items"]):
        raw = raw_items[index] if index < len(raw_items) else {}
        row = {**item}
        for key in ("quantity", "mobilization_days"):
            row[key] = _count(raw.get(key, row.get(key, 0)), field=f"items[{index}].{key}")
        for key in ("worked_days", "saturday_days", "sunday_days"):
            row[key] = (
                None
                if raw.get(key) in (None, "")
                else _count(raw[key], field=f"items[{index}].{key}")
            )
        for key in ("overtime_week_hours", "overtime_saturday_hours", "overtime_sunday_hours"):
            row[key] = _non_negative_number(raw.get(key), field=f"items[{index}].{key}")
        values = _labor_v2_values(row, metadata)
        row.update(
            worked_hours=_non_negative_number(
                values["hours"], field=f"items[{index}].worked_hours"
            ),
            hourly_rate=float(values["hourly"]),
        )
        rows.append(row)
    _ensure_unique_item_identity(rows, field="mao_de_obra_direta.items")
    result["mao_de_obra_direta"] = {**section, "items": rows}
    result["mao_de_obra_direta"]["adjustments"] = _normalize_v2_adjustments(
        result["mao_de_obra_direta"], incoming,
    )
    _ensure_unique_item_identity(
        result["mao_de_obra_direta"]["adjustments"],
        field="mao_de_obra_direta.adjustments",
        unique_labels=False,
    )
    admin = _section(payload, "custos_administrativos")
    result["custos_administrativos"] = {
        "daily_cost": _non_negative_number(admin.get("daily_cost"), field="daily_cost"),
        "days": _count(admin.get("days"), field="custos_administrativos.days"),
        "considered_percent": _bounded_percent(
            admin.get("considered_percent"), field="considered_percent", default=100
        ),
        "multiplier": _non_negative_number(admin.get("multiplier"), field="multiplier", default=1),
    }
    for name in ("mao_de_obra_direta", "custos_administrativos", "veiculos_hospedagem",
                 "alimentacao", "equipamentos", "epis_epcs", "materiais_consumo", "ferramental",
                 "outros_custos_diretos", "custos_indiretos", "bdi"):
        result[name]["discount_percent"] = _bounded_percent(
            _section(payload, name).get("discount_percent"), field=f"{name}.discount_percent",
        )
        incoming_section = _section(payload, name)
        if name != "mao_de_obra_direta" and "items" in incoming_section:
            if "items" not in result[name]:
                raise InvalidOrcamentoInputError(f"DFP: {name} não aceita items")
            raw_section_items = _incoming_list(
                incoming_section["items"], field=f"{name}.items"
            )
            _validate_incoming_item_identity(raw_section_items, field=f"{name}.items")
            result[name]["items"] = result[name]["items"][:len(raw_section_items)]
    taxes = _section(payload, "impostos")
    if "items" in taxes:
        tax_items = _incoming_list(taxes["items"], field="impostos.items")
        _validate_incoming_item_identity(tax_items, field="impostos.items")
        result["impostos"]["items"] = result["impostos"]["items"][:len(tax_items)]
    for name in (
        "veiculos_hospedagem",
        "alimentacao",
        "equipamentos",
        "epis_epcs",
        "materiais_consumo",
        "ferramental",
        "outros_custos_diretos",
        "custos_indiretos",
        "impostos",
    ):
        _ensure_unique_item_identity(result[name]["items"], field=f"{name}.items")
    person_days = sum(
        (_labor_v2_values(row, metadata)["person_days"] for row in rows), Decimal("0")
    )
    result["alimentacao"]["items"] = [
        {**item, "quantity": float(person_days)} for item in result["alimentacao"]["items"]
    ]
    return result


def _discount(total: Decimal, section: dict[str, Any]) -> Decimal:
    return _money(total * (HUNDRED - _decimal(section.get("discount_percent", 0))) / HUNDRED)


def _direct_labor_v2(section: dict[str, Any], metadata: dict[str, Any]) -> Decimal:
    values = {item["id"]: _labor_v2_values(item, metadata) for item in section["items"]}
    quantities = {item["id"]: _decimal(item["quantity"]) for item in section["items"]}
    subtotal = sum((value["salary"] + value["overtime"] for value in values.values()), Decimal("0"))
    for adjustment in section["adjustments"]:
        target = adjustment["labor_item_id"]
        if not adjustment["quantity"] or target not in values:
            continue
        base = values[target]["salary"]
        if adjustment["base"] == "salary_and_overtime":
            base += values[target]["overtime"]
        proporcao = _decimal(adjustment["quantity"]) / quantities[target]
        subtotal += base * proporcao * _decimal(adjustment["percent"]) / HUNDRED
    encargos = 1 + _decimal(section["social_charges_percent"]) / HUNDRED
    return _discount(subtotal * encargos, section)


def compute_dfp_summary(dfp: dict[str, Any] | None) -> dict[str, float]:
    """Calcula o perfil DFP sem mutar a entrada e arredonda moeda em half-up."""
    snapshot = normalize_dfp_payload(dfp)

    def labor_total(section: dict[str, Any]) -> Decimal:
        subtotal_a = Decimal("0")
        for item in section["items"]:
            base_hours = _decimal(item["salary_base_hours"])
            hourly = _decimal(item["hourly_rate"]) or (
                (_decimal(item["salary_real"]) / base_hours) if base_hours > 0 else Decimal("0")
            )
            subtotal_a += (
                _decimal(item["quantity"]) * _decimal(item["hours_per_employee"]) * hourly
            ) + _decimal(item["manual_total"])
        subtotal_b = subtotal_a + sum(
            (
                subtotal_a * _decimal(adjustment["percent"]) / HUNDRED
                for adjustment in section["adjustments"]
            ),
            start=Decimal("0"),
        )
        charges = subtotal_b * _decimal(section["social_charges_percent"]) / HUNDRED
        return _money(subtotal_b + charges)

    def item_total(items: list[dict[str, Any]]) -> Decimal:
        return _money(
            sum(
                (_decimal(item["quantity"]) * _decimal(item["unit_cost"]) for item in items),
                start=Decimal("0"),
            )
        )

    v2 = snapshot.get("calculation_version") == 2
    direct_labor_total = (
        _direct_labor_v2(snapshot["mao_de_obra_direta"], snapshot["metadata"])
        if v2 else labor_total(snapshot["mao_de_obra_direta"])
    )
    indirect_labor_total = labor_total(snapshot["mao_de_obra_indireta"])
    if v2:
        admin = snapshot["custos_administrativos"]
        default_days = sum(snapshot["metadata"][key] for key in (
            "quantidade_dias_semana", "quantidade_sabado", "quantidade_domingo",
        ))
        indirect_labor_total = _discount(
            _decimal(admin["daily_cost"])
            * _decimal(admin["days"] or default_days)
            * _decimal(admin["considered_percent"])
            / HUNDRED
            * _decimal(admin["multiplier"]),
            admin,
        )
    transport_total = item_total(snapshot["veiculos_hospedagem"]["items"]) + item_total(
        snapshot["veiculos_hospedagem"]["lodging_assets"]
    )
    # No v2 os móveis do alojamento saíram do escopo e não entram no total.
    food_total = item_total(snapshot["alimentacao"]["items"])
    equipment_total = item_total(snapshot["equipamentos"]["items"])
    epi_total = item_total(snapshot["epis_epcs"]["items"])
    material_total = item_total(snapshot["materiais_consumo"]["items"])
    tool_total = item_total(snapshot["ferramental"]["items"])
    other_direct_total = item_total(snapshot["outros_custos_diretos"]["items"])
    if v2:
        transport_total = _discount(
            item_total(snapshot["veiculos_hospedagem"]["items"]),
            snapshot["veiculos_hospedagem"],
        )
        food_total = _discount(food_total, snapshot["alimentacao"])
        equipment_total = _discount(equipment_total, snapshot["equipamentos"])
        epi_total = _discount(epi_total, snapshot["epis_epcs"])
        material_total = _discount(material_total, snapshot["materiais_consumo"])
        tool_total = _discount(tool_total, snapshot["ferramental"])
        other_direct_total = _discount(other_direct_total, snapshot["outros_custos_diretos"])

    total_direct_costs = _money(
        direct_labor_total
        + indirect_labor_total
        + transport_total
        + food_total
        + equipment_total
        + epi_total
        + material_total
        + tool_total
        + other_direct_total,
    )
    total_indirect_costs = _money(
        sum(
            (
                _decimal(item["aliquot_percent"]) * total_direct_costs / HUNDRED
                for item in snapshot["custos_indiretos"]["items"]
            ),
            start=Decimal("0"),
        )
    )
    total_profit = _money(
        _decimal(snapshot["bdi"]["factor_percent"]) * total_direct_costs / HUNDRED
    )
    if v2:
        total_indirect_costs = _discount(total_indirect_costs, snapshot["custos_indiretos"])
        total_profit = _discount(total_profit, snapshot["bdi"])
    total_costs = _money(total_direct_costs + total_indirect_costs + total_profit)
    total_tax_percent = sum(
        (_decimal(item["aliquot_percent"]) for item in snapshot["impostos"]["items"]),
        start=Decimal("0"),
    )
    # O normalizador já rejeita uma soma que zeraria/inverteria o denominador.
    contract_total = _money(total_costs / ((HUNDRED - total_tax_percent) / HUNDRED))
    area_total = _decimal(snapshot["metadata"]["area_total"] or 0)
    area_price = _money(contract_total / area_total) if area_total > 0 else Decimal("0")
    total_collaborators = _decimal(
        sum(item["quantity"] for item in snapshot["mao_de_obra_direta"]["items"])
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    prazo = _decimal(
        max(
            snapshot["metadata"]["quantidade_dias_semana"],
            sum(item["worked_days"] or 0 for item in snapshot["mao_de_obra_direta"]["items"]),
        )
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    price_per_day_per_collaborator = (
        _money(contract_total / prazo / total_collaborators)
        if prazo > 0 and total_collaborators > 0
        else Decimal("0")
    )
    if v2:
        person_days = sum(
            (
                _labor_v2_values(row, snapshot["metadata"])["person_days"]
                for row in snapshot["mao_de_obra_direta"]["items"]
            ),
            Decimal("0"),
        )
        price_per_day_per_collaborator = (
            _money(contract_total / person_days) if person_days else Decimal("0")
        )
    summary = {
        "mao_de_obra_direta_total": direct_labor_total,
        "mao_de_obra_indireta_total": indirect_labor_total,
        "veiculos_hospedagem_total": transport_total,
        "alimentacao_total": food_total,
        "equipamentos_total": equipment_total,
        "epis_epcs_total": epi_total,
        "materiais_consumo_total": material_total,
        "ferramental_total": tool_total,
        "outros_custos_diretos_total": other_direct_total,
        "custos_diretos_total": total_direct_costs,
        "custos_indiretos_total": total_indirect_costs,
        "lucro_total": total_profit,
        "custos_totais": total_costs,
        "aliquota_impostos_total": total_tax_percent,
        "preco_total_faturamento": contract_total,
        "preco_por_area": area_price,
        "valor_dia_colaborador": price_per_day_per_collaborator,
    }
    if v2:
        summary["custos_administrativos_total"] = indirect_labor_total
    return {key: float(value) for key, value in summary.items()}
