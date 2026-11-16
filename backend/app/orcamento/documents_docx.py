"""Renderizador DOCX (python-docx) do orçamento comercial. Recebe o modelo de ``documents``."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .documents import LOGO_PATH

FONT = "Arial"
CONTENT_CM = 17.0
INK = "16202B"
MUTED = "5B6875"
HAIRLINE = "D5DCE4"
ZEBRA = "F5F7FA"
ON_DARK_MUTED = "B9C6D3"
BRAND_STROKES = ("D9232B", "F2A900", "1F6FB8")
COMPANY = "AIDEAL Engenharia de Superfície"
RIGHT = WD_ALIGN_PARAGRAPH.RIGHT


def _rgb(color: str) -> RGBColor:
    return RGBColor.from_string(color)


def _run(paragraph: Any, text: str, *, size: float = 9, bold: bool = False,
         color: str = INK) -> Any:
    run = paragraph.add_run(text)
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)
    return run


def _spacing(paragraph: Any, before: float = 0, after: float = 0) -> Any:
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    return paragraph


TC_PR_ORDER = ("tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap", "tcMar",
               "textDirection", "tcFitText", "vAlign", "hideMark")


def _set_cell_property(cell: Any, element: Any) -> None:
    """Substitui a propriedade e mantém a ordem do schema OOXML (o Word a exige)."""
    properties = cell._tc.get_or_add_tcPr()
    for existing in properties.findall(element.tag):
        properties.remove(existing)
    properties.append(element)
    order = {qn(f"w:{name}"): index for index, name in enumerate(TC_PR_ORDER)}
    properties[:] = sorted(properties, key=lambda child: order.get(child.tag, len(order)))


def _shade(cell: Any, fill: str) -> None:
    shade = OxmlElement("w:shd")
    shade.set(qn("w:val"), "clear")
    shade.set(qn("w:color"), "auto")
    shade.set(qn("w:fill"), fill)
    _set_cell_property(cell, shade)


def _borders(cell: Any, **edges: tuple[int, str] | None) -> None:
    """edges: top/bottom/left/right = (espessura em oitavos de ponto, cor) ou None."""
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        spec = edges.get(edge)
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single" if spec else "nil")
        if spec:
            element.set(qn("w:sz"), str(spec[0]))
            element.set(qn("w:space"), "0")
            element.set(qn("w:color"), spec[1])
        borders.append(element)
    _set_cell_property(cell, borders)


def _margins(cell: Any, top: int = 70, bottom: int = 70, left: int = 100,
             right: int = 100) -> None:
    margins = OxmlElement("w:tcMar")
    for edge, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:w"), str(value))
        element.set(qn("w:type"), "dxa")
        margins.append(element)
    _set_cell_property(cell, margins)


def _thin_row(row: Any, points: float) -> None:
    row.height = Pt(points)
    row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY


def _table(doc: Any, rows: int, widths: list[float]) -> Any:
    table = doc.add_table(rows=rows, cols=len(widths))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    # Largura na grade da tabela: sem isso o LibreOffice divide as colunas por igual.
    for column, width in zip(table.columns, widths):
        column.width = Cm(width)
    for row in table.rows:
        _size_row(row, widths)
    return table


def _size_row(row: Any, widths: list[float]) -> None:
    for cell, width in zip(row.cells, widths):
        cell.width = Cm(width)
        _borders(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _cell_text(cell: Any, text: str, *, align: Any = None, **font: Any) -> Any:
    paragraph = _spacing(cell.paragraphs[0])
    if align is not None:
        paragraph.alignment = align
    _run(paragraph, text, **font)
    return paragraph


def _field(paragraph: Any, instruction: str) -> None:
    """Campo complexo (PAGE, NUMPAGES): mantém a formatação do run ao ser atualizado."""
    for kind, text in (("begin", None), (None, instruction), ("separate", None), (None, "1"),
                       ("end", None)):
        run = _run(paragraph, "", size=7.5, color=MUTED)
        if kind:
            char = OxmlElement("w:fldChar")
            char.set(qn("w:fldCharType"), kind)
            run._element.append(char)
        elif text == instruction:
            code = OxmlElement("w:instrText")
            code.set(qn("xml:space"), "preserve")
            code.text = f" {instruction} "
            run._element.append(code)
        else:
            run.text = text


def _heading(doc: Any, text: str) -> None:
    paragraph = _spacing(doc.add_paragraph(), before=14, after=5)
    paragraph.paragraph_format.keep_with_next = True
    _run(paragraph, text, size=11.5, bold=True)


def _header(doc: Any, model: dict) -> None:
    table = _table(doc, 1, [CONTENT_CM * 0.45, CONTENT_CM * 0.55])
    left, right = table.rows[0].cells
    _margins(left, left=0)
    _margins(right, right=0)
    if LOGO_PATH.exists():
        left.paragraphs[0].add_run().add_picture(str(LOGO_PATH), width=Cm(4.6))
    else:
        _cell_text(left, COMPANY, bold=True, size=12)
    _cell_text(right, "Orçamento comercial", align=RIGHT, size=8.5, color=MUTED)
    code = _spacing(right.add_paragraph())
    code.alignment = RIGHT
    _run(code, model["code"], size=15, bold=True)
    detail = " · ".join(part for part in (model["status"], model["fields"][2][1])
                        if part and part != "N/A")
    if detail:
        line = _spacing(right.add_paragraph())
        line.alignment = RIGHT
        _run(line, detail, size=8.5, color=MUTED)
    # As três pinceladas da marca seguidas de um fio até a margem.
    stroke = 1.05
    rule = _table(doc, 1, [stroke] * 3 + [CONTENT_CM - 3 * stroke])
    for cell, color in zip(rule.rows[0].cells, BRAND_STROKES):
        _borders(cell, top=(24, color))
    _borders(rule.rows[0].cells[3], top=(4, HAIRLINE))
    _thin_row(rule.rows[0], 4)
    for cell in rule.rows[0].cells:
        _margins(cell, top=0, bottom=0)
        _run(_spacing(cell.paragraphs[0]), "", size=2)


def _price_box(doc: Any, model: dict) -> None:
    table = _table(doc, 1, [CONTENT_CM * 0.62, CONTENT_CM * 0.38])
    left, right = table.rows[0].cells
    for cell in (left, right):
        _shade(cell, INK)
        _margins(cell, top=220, bottom=220, left=280, right=280)
    _cell_text(left, model["price_label"], size=8.5, color=ON_DARK_MUTED)
    _run(_spacing(left.add_paragraph()), model["price"], size=24, bold=True, color="FFFFFF")
    first = True
    for label, value in model["highlights"]:
        paragraph = right.paragraphs[0] if first else right.add_paragraph()
        _spacing(paragraph, before=0 if first else 4)
        _run(paragraph, label, size=7.5, color=ON_DARK_MUTED)
        _run(_spacing(right.add_paragraph()), value, size=10, bold=True, color="FFFFFF")
        first = False


def _composition(doc: Any, parts: list[dict]) -> None:
    """Faixa empilhada (células com largura proporcional) e legenda logo abaixo."""
    minimum = 0.25
    shares = [max(part["share"], minimum / CONTENT_CM) for part in parts]
    scale = CONTENT_CM / sum(shares)
    bar = _table(doc, 1, [share * scale for share in shares])
    _thin_row(bar.rows[0], 8)
    for cell, part in zip(bar.rows[0].cells, parts):
        _shade(cell, part["color"])
        _margins(cell, top=0, bottom=0, left=0, right=0)
        _borders(cell, right=(8, "FFFFFF"))
        _run(_spacing(cell.paragraphs[0]), "", size=5)
    legend = _table(doc, 1, [CONTENT_CM / len(parts)] * len(parts))
    for cell, part in zip(legend.rows[0].cells, parts):
        _margins(cell, top=60, bottom=0, left=0, right=80)
        paragraph = _spacing(cell.paragraphs[0])
        _run(paragraph, "■ ", size=8, color=part["color"])
        _run(paragraph, f"{part['label']} · {part['percent']}", size=7.5, color=MUTED)
        _run(_spacing(cell.add_paragraph()), part["value"], size=9, bold=True)


def _fields(doc: Any, model: dict) -> None:
    fields = model["fields"][1:]
    rows = [fields[index:index + 2] for index in range(0, len(fields), 2)]
    table = _table(doc, len(rows), [CONTENT_CM / 2] * 2)
    for row, pair in zip(table.rows, rows):
        for cell, (label, value) in zip(row.cells, pair):
            _margins(cell, left=0, right=200)
            _borders(cell, bottom=(4, HAIRLINE))
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            _set_cell_property(cell, cell._tc.tcPr.find(qn("w:vAlign")))
            _cell_text(cell, label, size=7.5, color=MUTED)
            _run(_spacing(cell.add_paragraph()), value, size=9)
        for cell in row.cells[len(pair):]:
            _borders(cell, bottom=(4, HAIRLINE))


def _column_widths(count: int) -> list[float]:
    numeric = {2: [5.8], 3: [2.7, 4.1], 4: [2.4, 3.1, 3.1]}[count]
    return [CONTENT_CM - sum(numeric), *numeric]


def _item_table(doc: Any, headers: list, rows: list, footer: list) -> None:
    widths = _column_widths(len(headers))
    table = _table(doc, 1, widths)
    head = table.rows[0]
    head._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for index, (cell, text) in enumerate(zip(head.cells, headers)):
        _borders(cell, bottom=(8, INK))
        _margins(cell)
        _cell_text(cell, text, align=RIGHT if index else None, size=7.5, bold=True, color=MUTED)
    for number, values in enumerate(rows):
        row = table.add_row()
        _size_row(row, widths)
        for index, (cell, text) in enumerate(zip(row.cells, values)):
            _margins(cell)
            if number % 2:
                _shade(cell, ZEBRA)
            _cell_text(cell, str(text), align=RIGHT if index else None, size=8.5)
    for position, (label, value) in enumerate(footer):
        row = table.add_row()
        _size_row(row, widths)
        edge = (8, INK) if position == 0 else (4, HAIRLINE)
        merged = row.cells[0].merge(row.cells[-2]) if len(widths) > 2 else row.cells[0]
        for cell in (merged, row.cells[-1]):
            _borders(cell, top=edge)
            _margins(cell)
        _cell_text(merged, label, size=8.5, bold=True)
        _cell_text(row.cells[-1], value, align=RIGHT, size=8.5, bold=True)


def _summary_table(doc: Any, rows: list) -> None:
    widths = _column_widths(2)
    table = _table(doc, len(rows), widths)
    last = len(rows) - 1
    for index, (row, (label, value)) in enumerate(zip(table.rows, rows)):
        final = index == last
        for cell in row.cells:
            _margins(cell, top=130 if final else 80, bottom=130 if final else 80)
            if final:
                _shade(cell, INK)
            else:
                _borders(cell, bottom=(4, HAIRLINE))
        font = {"size": 9.5, "bold": True, "color": "FFFFFF"} if final else {"size": 8.5}
        _cell_text(row.cells[0], label, **font)
        _cell_text(row.cells[1], value, align=RIGHT, **font)


def _footer(section: Any, model: dict) -> None:
    footer = section.footer
    footer.is_linked_to_previous = False
    widths = [CONTENT_CM * 0.7, CONTENT_CM * 0.3]
    table = footer.add_table(rows=1, cols=2, width=Cm(CONTENT_CM))
    table.autofit = False
    for column, width in zip(table.columns, widths):
        column.width = Cm(width)
    _size_row(table.rows[0], widths)
    left, right = table.rows[0].cells
    for cell in (left, right):
        _borders(cell, top=(4, HAIRLINE))
        _margins(cell, top=110, bottom=0, left=0, right=0)
    _cell_text(left, f"{COMPANY} · {model['code']}", size=7.5, color=MUTED)
    page = _spacing(right.paragraphs[0])
    page.alignment = RIGHT
    _run(page, "Página ", size=7.5, color=MUTED)
    _field(page, "PAGE")
    _run(page, " de ", size=7.5, color=MUTED)
    _field(page, "NUMPAGES")
    # O rodapé nasce com um parágrafo vazio antes da tabela, e o Word exige outro depois dela
    # (um rodapé não pode terminar em tabela); nenhum dos dois deve ocupar altura.
    for empty in (footer.paragraphs[0], footer.add_paragraph()):
        _spacing(empty).paragraph_format.line_spacing = Pt(1)


def render_docx(model: dict) -> bytes:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(2)
    section.top_margin, section.bottom_margin = Cm(1.6), Cm(2)
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(9)
    normal.font.color.rgb = _rgb(INK)
    doc.core_properties.title = model["code"]
    doc.core_properties.author = COMPANY

    _header(doc, model)
    _run(_spacing(doc.add_paragraph(), before=16), "Proposta para", size=8.5, color=MUTED)
    _run(_spacing(doc.add_paragraph(), after=10), model["client"], size=20, bold=True)
    _price_box(doc, model)
    if model["composition"]:
        _spacing(doc.add_paragraph(), after=0).paragraph_format.line_spacing = Pt(8)
        _composition(doc, model["composition"])
    _spacing(doc.add_paragraph(), after=0).paragraph_format.line_spacing = Pt(6)
    _fields(doc, model)
    _heading(doc, "Identificação e escopo")
    _run(_spacing(doc.add_paragraph()), model["scope"], size=9)
    for table in model["tables"]:
        _heading(doc, table["title"])
        if table["rows"] or table["footer"]:
            _item_table(doc, table["headers"], table["rows"], table["footer"])
    _heading(doc, "Impostos e resumo")
    _summary_table(doc, model["summary"])
    if model["notes"]:
        _heading(doc, "Observações")
        _run(_spacing(doc.add_paragraph()), model["notes"], size=9)
    _footer(section, model)
    output = BytesIO()
    doc.save(output)
    return output.getvalue()
