"""In-memory, database-independent exports of one saved budget revision.

Este módulo monta o modelo neutro do documento (textos já formatados em pt-BR); os
renderizadores ficam em ``documents_pdf`` e ``documents_docx`` e só cuidam de layout.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .dfp import compute_dfp_summary, normalize_dfp_payload
from .hh import compute_hh

LOGO_PATH = Path(__file__).parent / "assets" / "logo-aideal.png"

SECTIONS = (
    ("mao_de_obra_direta", "Mão de obra direta"),
    ("custos_administrativos", "Custos administrativos"),
    ("veiculos_hospedagem", "Veículos e hospedagem"),
    ("alimentacao", "Alimentação"),
    ("equipamentos", "Equipamentos"),
    ("epis_epcs", "EPIs e EPCs"),
    ("materiais_consumo", "Materiais de consumo"),
    ("ferramental", "Ferramental"),
    ("outros_custos_diretos", "Outros custos diretos"),
)
SUMMARY = (
    ("custos_diretos_total", "Custos diretos"),
    ("custos_indiretos_total", "Custos indiretos"),
    ("lucro_total", "Lucro e BDI"),
    ("custos_totais", "Custos totais"),
    ("aliquota_impostos_total", "Impostos (%)"),
    ("preco_por_area", "Preço por área"),
    ("valor_dia_colaborador", "Valor por dia e colaborador"),
    ("preco_total_faturamento", "Preço total de faturamento"),
)
HH_SUMMARY = (
    ("hh_colaboradores", "Colaboradores"),
    ("hh_encargos_percent", "Encargos sociais (%)"),
    ("hh_total_mensal", "Total mensal"),
    ("hh_meses", "Prazo do contrato (meses)"),
    ("custos_diretos_total", "Custos diretos no prazo"),
    ("custos_indiretos_total", "Despesas indiretas no prazo"),
    ("lucro_total", "Lucro no prazo"),
    ("aliquota_impostos_total", "Tributos (%)"),
    ("preco_total_faturamento", "Preço total estimado do contrato"),
)
UNIDADES_SEM_MOEDA = {"aliquota_impostos_total", "hh_encargos_percent", "hh_meses",
                      "hh_colaboradores"}
SITUACOES = {
    "rascunho": "Rascunho",
    "em_revisao": "Em revisão",
    "pronto_para_proposta": "Pronto para proposta",
    "emitido": "Emitido",
    "inativo": "Inativo",
}
# Cores da faixa de composição do preço; as mesmas do painel (orcamento.css, --orc-comp-*).
COMPOSITION = (
    ("custos_diretos_total", "Custos diretos", "1F6FB8"),
    ("custos_indiretos_total", "Custos indiretos", "6BB7E8"),
    ("lucro_total", "Lucro e BDI", "F2A900"),
    ("impostos", "Impostos", "D9232B"),
)


def _number(value: Any) -> str:
    return f"{float(value or 0):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _count(value: Any) -> str:
    """Contagens sem casas decimais quando o valor é inteiro (10, não 10,00)."""
    number = float(value or 0)
    return f"{number:,.0f}".replace(",", ".") if number.is_integer() else _number(number)


def _money(value: Any) -> str:
    return f"R$ {_number(value)}"


def _text(value: Any) -> str:
    return str(value) if value is not None and value != "" else "N/A"


def _date(value: Any) -> Any:
    """Datas ISO viram dd/mm/aaaa; qualquer outro texto passa como está."""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d/%m/%Y")
        except ValueError:
            return value
    return value


def _export_safe_text(value: Any) -> Any:
    """Strip XML-invalid controls only in the export copy, never stored revisions."""
    if isinstance(value, str):
        return ''.join(char for char in value if char in '\t\n\r'
                       or 0x20 <= ord(char) <= 0xD7FF
                       or 0xE000 <= ord(char) <= 0xFFFD
                       or 0x10000 <= ord(char) <= 0x10FFFF)
    if isinstance(value, dict):
        return {key: _export_safe_text(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_export_safe_text(item) for item in value]
    return value


def _table(title: str, headers: tuple, rows: list, total: Any, discount: Any = 0) -> dict:
    """Linha de fechamento: o subtotal vem do cálculo oficial, já com o desconto da seção."""
    footer = []
    if discount:
        footer.append((f"Desconto aplicado ({_number(discount)} %)", ""))
    if total is not None:
        footer.append(("Subtotal", _money(total)))
    return {"title": title, "headers": headers, "rows": rows, "footer": footer}


def _dfp_tables(dfp: dict, summary: dict) -> list:
    tables = []
    sections = SECTIONS if dfp.get("calculation_version") == 2 else (
        SECTIONS[0], ("mao_de_obra_indireta", "Mão de obra indireta"), *SECTIONS[2:])
    for key, label in sections:
        section = dfp.get(key, {})
        items = section.get("items", [])
        if key == "veiculos_hospedagem" and dfp.get("calculation_version") != 2:
            items = [*items, *section.get("lodging_assets", [])]
        labor = key.startswith("mao_de_obra")
        filled = [item for item in items if item.get("quantity") or item.get("unit_cost")
                  or item.get("salary_real") or item.get("manual_total") or item.get("notes")]
        if labor:
            headers = ("Item", "Quantidade", "Salário real (R$)")
            rows = [(_text(item.get("label")), _number(item.get("quantity")),
                     _number(item.get("salary_real"))) for item in filled]
        else:
            headers = ("Item", "Quantidade", "Valor unitário (R$)", "Total (R$)")
            rows = [(_text(item.get("label")), _number(item.get("quantity")),
                     _number(item.get("unit_cost")),
                     _number(float(item.get("quantity") or 0) * float(item.get("unit_cost") or 0)))
                    for item in filled]
        total = summary.get(f"{key}_total", 0)
        if rows or total:
            tables.append(_table(label, headers, rows, total, section.get("discount_percent")))
    return tables


def _hh_tables(hh: dict) -> list:
    """Uma tabela por grupo de funções e outra com os valores de Homem-Hora."""
    calculo = compute_hh(hh)
    tables = []
    taxas = []
    for grupo, resultado in zip(hh["grupos"], calculo["grupos"]):
        linhas = []
        for funcao, valores in zip(grupo["funcoes"], resultado["funcoes"]):
            linhas.append((_text(funcao["label"]), _number(funcao["quantidade"]),
                           _number(valores["total_unitario"])))
            taxas.append((_text(funcao["label"]), _number(valores["hora_normal"]),
                          _number(valores["hora_noturna"])))
        tables.append(_table(grupo["label"],
                             ("Função", "Quantidade", "Total unitário mensal (R$)"),
                             linhas, resultado["total_mensal"]))
    if taxas:
        # Valores por hora não somam: a tabela sai sem linha de subtotal.
        tables.append(_table("Valores de Homem-Hora",
                             ("Função", "Hora normal (R$)", "Hora noturna (R$)"), taxas, None))
    return tables


def _summary_value(summary: dict, key: str) -> str:
    valor = _number(summary.get(key))
    if key in {"hh_meses", "hh_colaboradores"}:
        return _count(summary.get(key))
    return f"{valor} %" if key in UNIDADES_SEM_MOEDA else f"R$ {valor}"


def _composition(summary: dict) -> list:
    """Partes do preço: custos diretos, indiretos, lucro e impostos (preço menos custos)."""
    price = float(summary.get("preco_total_faturamento") or 0)
    values = {key: float(summary.get(key) or 0) for key, _, _ in COMPOSITION}
    values["impostos"] = max(price - float(summary.get("custos_totais") or 0), 0.0)
    if price <= 0:
        return []
    return [{"label": label, "value": _money(values[key]), "share": values[key] / price,
             "percent": f"{_number(values[key] / price * 100)} %", "color": color}
            for key, label, color in COMPOSITION if values[key] > 0]


def _highlights(summary: dict, hh_ativo: bool, meta: dict) -> list:
    if hh_ativo:
        return [("Total mensal", _money(summary.get("hh_total_mensal"))),
                ("Prazo do contrato", f"{_count(summary.get('hh_meses'))} meses"),
                ("Colaboradores", _count(summary.get("hh_colaboradores")))]
    items = []
    if summary.get("preco_por_area"):
        items.append((f"Preço por {meta.get('area_unidade') or 'm²'}",
                      _money(summary["preco_por_area"])))
    if summary.get("valor_dia_colaborador"):
        items.append(("Valor por dia e colaborador", _money(summary["valor_dia_colaborador"])))
    items.append(("Impostos", f"{_number(summary.get('aliquota_impostos_total'))} %"))
    return items


def _model(budget: dict, revision: dict) -> dict:
    code = str(budget.get("codigo", ""))
    if not re.fullmatch(r"ORC-\d{4,}(?:-R\d+)?", code):
        raise ValueError("Código de orçamento inválido")
    number = revision.get("numero")
    if isinstance(number, bool) or not isinstance(number, int) or number < 0:
        raise ValueError("Número de revisão inválido")
    code = f"{code.split('-R')[0]}-R{number}"
    dfp = normalize_dfp_payload(revision.get("dfp"))
    meta = dfp["metadata"]
    hh_ativo = revision.get("modalidade") == "HH" and dfp.get("hh") is not None
    summary = compute_dfp_summary(dfp, modalidade=revision.get("modalidade"))
    client = (meta.get("cliente_unidade") or meta.get("contratante_override")
              or budget.get("contratante"))
    fields = (
        ("Contratante", client),
        ("Dados da contratante", revision.get("dados_contratante")),
        ("Modalidade", revision.get("modalidade")),
        ("Região da obra", revision.get("regiao")),
        (
            "Data de início",
            "N/A"
            if meta.get("data_inicio_na")
            else _date(meta.get("data_inicio") or meta.get("previsao_inicio")),
        ),
        ("Prazo de execução em dias", revision.get("prazo_execucao_dias")),
        ("Prazo para mobilização", revision.get("mobilizacao") or meta.get("mobilizacao_text")),
        ("Prazo para desmobilização", revision.get("desmobilizacao") or
         meta.get("desmobilizacao_text")),
        ("Área", f"{_number(meta['area_total'])} {meta.get('area_unidade', 'm²')}"
         if meta.get("area_total") is not None else None),
        ("Emitido em", _date(revision.get("emitido_em"))),
        ("Válido até", _date(revision.get("valido_ate"))),
    )
    summary_rows = HH_SUMMARY if hh_ativo else SUMMARY
    return {
        "code": code,
        "client": _text(client),
        "status": SITUACOES.get(str(revision.get("situacao") or ""), ""),
        "fields": [(label, _text(value)) for label, value in fields],
        "price_label": summary_rows[-1][1],
        "price": _money(summary.get("preco_total_faturamento")),
        "highlights": _highlights(summary, hh_ativo, meta),
        "composition": _composition(summary),
        "tables": _hh_tables(dfp["hh"]) if hh_ativo else _dfp_tables(dfp, summary),
        "summary": [(label, _summary_value(summary, key)) for key, label in summary_rows],
        "scope": revision.get("escopo") or meta.get("descricao_projeto") or "N/A",
        "notes": dfp.get("informacoes_adicionais", {}).get("observacoes"),
        "rules": revision.get("versao_regras"),
    }


def export_orcamento_document(
    orcamento: dict[str, Any], revisao: dict[str, Any], formato: str,
) -> tuple[bytes, str, str]:
    """Return bytes, content type and safe filename for an authorized saved revision."""
    if formato not in {"docx", "pdf"}:
        raise ValueError("Formato deve ser docx ou pdf")
    model = _export_safe_text(_model(orcamento, revisao))
    if formato == "pdf":
        from .documents_pdf import render_pdf

        return render_pdf(model), "application/pdf", f"{model['code']}.pdf"
    from .documents_docx import render_docx

    return (render_docx(model),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            f"{model['code']}.docx")
