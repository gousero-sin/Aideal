"""In-memory, database-independent exports of one saved budget revision."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from .dfp import compute_dfp_summary, normalize_dfp_payload
from .hh import compute_hh

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


def _number(value: Any) -> str:
    return f"{float(value or 0):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _text(value: Any) -> str:
    return str(value) if value is not None and value != "" else "N/A"


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
    fields = (
        (
            "Contratante",
            meta.get("cliente_unidade")
            or meta.get("contratante_override")
            or budget.get("contratante"),
        ),
        ("Dados da contratante", revision.get("dados_contratante")),
        ("Modalidade", revision.get("modalidade")),
        ("Região da obra", revision.get("regiao")),
        (
            "Data de início",
            "N/A"
            if meta.get("data_inicio_na")
            else meta.get("data_inicio") or meta.get("previsao_inicio"),
        ),
        ("Prazo de execução em dias", revision.get("prazo_execucao_dias")),
        ("Prazo para mobilização", revision.get("mobilizacao") or meta.get("mobilizacao_text")),
        ("Prazo para desmobilização", revision.get("desmobilizacao") or
         meta.get("desmobilizacao_text")),
        ("Área", f"{_number(meta['area_total'])} {meta.get('area_unidade', 'm²')}"
         if meta.get("area_total") is not None else None),
        ("Emitido em", revision.get("emitido_em")),
        ("Válido até", revision.get("valido_ate")),
    )
    if hh_ativo:
        return {"code": code, "fields": fields, "tables": _hh_tables(dfp["hh"]),
                "summary": summary, "summary_rows": HH_SUMMARY,
                "scope": revision.get("escopo") or meta.get("descricao_projeto") or "N/A",
                "notes": dfp.get("informacoes_adicionais", {}).get("observacoes"),
                "rules": revision.get("versao_regras")}
    tables = []
    sections = SECTIONS if dfp.get("calculation_version") == 2 else (
        SECTIONS[0], ("mao_de_obra_indireta", "Mão de obra indireta"), *SECTIONS[2:])
    for key, label in sections:
        items = dfp.get(key, {}).get("items", [])
        if key == "veiculos_hospedagem" and dfp.get("calculation_version") != 2:
            items = [*items, *dfp[key].get("lodging_assets", [])]
        rows = [(_text(item.get("label")), _number(item.get("quantity")),
                 _number(item.get("salary_real") if key.startswith("mao_de_obra")
                         else item.get("unit_cost")))
                for item in items if item.get("quantity") or item.get("unit_cost")
                or item.get("salary_real") or item.get("manual_total") or item.get("notes")]
        if rows or summary.get(f"{key}_total"):
            headers = ("Item", "Quantidade", "Salário real (R$)" if key.startswith("mao_de_obra")
                       else "Valor unitário (R$)")
            tables.append((label, headers, rows, summary.get(f"{key}_total", 0)))
    return {"code": code, "fields": fields, "tables": tables, "summary": summary,
            "summary_rows": SUMMARY,
            "scope": revision.get("escopo") or meta.get("descricao_projeto") or "N/A",
            "notes": dfp.get("informacoes_adicionais", {}).get("observacoes"),
            "rules": revision.get("versao_regras")}


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
        tables.append((grupo["label"], ("Função", "Quantidade", "Total unitário mensal (R$)"),
                       linhas, resultado["total_mensal"]))
    if taxas:
        # Valores por hora não somam: a tabela sai sem linha de subtotal.
        tables.append(("Valores de Homem-Hora",
                       ("Função", "Hora normal (R$)", "Hora noturna (R$)"), taxas, None))
    return tables


def _summary_value(model: dict, key: str) -> str:
    valor = _number(model["summary"].get(key))
    if key in {"hh_meses", "hh_colaboradores"}:
        return valor
    return valor + (" %" if key in UNIDADES_SEM_MOEDA else " BRL")


def _docx_table(doc, headers, rows):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    widths = (9, 3, 5) if len(headers) == 3 else (11, 6)
    for cell, text, width in zip(table.rows[0].cells, headers, widths):
        cell.text = text
        cell.width = Cm(width)
        cell.paragraphs[0].runs[0].bold = True
        shade = OxmlElement("w:shd")
        shade.set(qn("w:fill"), "E8EDF2")
        cell._tc.get_or_add_tcPr().append(shade)
    repeat = OxmlElement("w:tblHeader")
    table.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        for cell, text, width in zip(table.add_row().cells, row, widths):
            cell.text = str(text)
            cell.width = Cm(width)
    doc.add_paragraph()


def _docx(model: dict) -> bytes:
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(2)
    section.top_margin = section.bottom_margin = Cm(2)
    for name in ("Normal", "Title", "Heading 1", "Heading 2"):
        doc.styles[name].font.name = "Arial"
        doc.styles[name].font.color.rgb = RGBColor(0, 0, 0)
    doc.styles["Normal"].font.size = Pt(10)
    doc.add_paragraph("Orçamento comercial", "Title")
    doc.add_paragraph(model["code"])
    for label, value in model["fields"]:
        paragraph = doc.add_paragraph()
        paragraph.add_run(f"{label}: ").bold = True
        paragraph.add_run(_text(value))
    doc.add_heading("Identificação e escopo", 1)
    doc.add_paragraph(model["scope"])
    for label, headers, rows, total in model["tables"]:
        doc.add_heading(label, 1)
        if rows:
            _docx_table(doc, headers, rows)
        if total is not None:
            doc.add_paragraph(f"Subtotal: R$ {_number(total)}")
    doc.add_heading("Impostos e resumo", 1)
    _docx_table(doc, ("Indicador", "Valor"), [
        (label, _summary_value(model, key)) for key, label in model["summary_rows"]
    ])
    if model["notes"]:
        doc.add_heading("Observações", 1)
        doc.add_paragraph(model["notes"])
    footer = section.footer.paragraphs[0]
    footer.add_run(f"{model['code']} | Página ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


def _pdf(model: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    def para(text):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), styles["BodyText"])

    story = [Paragraph("Orçamento comercial", styles["Title"]), para(model["code"]), Spacer(1, 12)]
    story.extend(para(f"{label}: {_text(value)}") for label, value in model["fields"])
    story += [Spacer(1, 12), Paragraph("Identificação e escopo", styles["Heading1"]),
              para(model["scope"])]

    def add_table(headers, rows):
        data = [[para(cell) for cell in row] for row in (headers, *rows)]
        widths = [258, 75, 138] if len(headers) == 3 else [318, 153]
        table = Table(data, colWidths=widths, repeatRows=1, splitInRow=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF2")),
            ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#D9D9D9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([table, Spacer(1, 10)])

    for label, headers, rows, total in model["tables"]:
        # Rótulos HH vêm do usuário: o Paragraph interpreta marcação (<img>, <a>), então escapa.
        story.append(Paragraph(escape(str(label)), styles["Heading1"]))
        if rows:
            add_table(headers, rows)
        if total is not None:
            story.append(para(f"Subtotal: R$ {_number(total)}"))
    story.append(Paragraph("Impostos e resumo", styles["Heading1"]))
    add_table(("Indicador", "Valor"), [
        (label, _summary_value(model, key)) for key, label in model["summary_rows"]
    ])
    if model["notes"]:
        story += [Paragraph("Observações", styles["Heading1"]), para(model["notes"])]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(56, 30, f"{model['code']} | Página {document.page}")
        canvas.restoreState()

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=56, rightMargin=56,
                                 topMargin=45, bottomMargin=50, title=model["code"])
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def export_orcamento_document(
    orcamento: dict[str, Any], revisao: dict[str, Any], formato: str,
) -> tuple[bytes, str, str]:
    """Return bytes, content type and safe filename for an authorized saved revision."""
    if formato not in {"docx", "pdf"}:
        raise ValueError("Formato deve ser docx ou pdf")
    model = _export_safe_text(_model(orcamento, revisao))
    content_type = "application/pdf" if formato == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return (_pdf(model) if formato == "pdf" else _docx(model), content_type,
            f"{model['code']}.{formato}")
