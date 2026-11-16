"""Renderizador PDF (ReportLab) do orçamento comercial. Recebe o modelo de ``documents``."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .documents import LOGO_PATH

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 48
FRAME_PADDING = 6  # o Frame do ReportLab recua o conteúdo em 6 pt de cada lado
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
INK = colors.HexColor("#16202B")
MUTED = colors.HexColor("#5B6875")
HAIRLINE = colors.HexColor("#D5DCE4")
ZEBRA = colors.HexColor("#F5F7FA")
BLUE = colors.HexColor("#1F6FB8")
BRAND_STROKES = ("#D9232B", "#F2A900", "#1F6FB8")
COMPANY = "AIDEAL Engenharia de Superfície"

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=8.5, leading=12, textColor=INK)
STYLES = {
    "body": BASE,
    "body_right": ParagraphStyle("body_right", parent=BASE, alignment=TA_RIGHT),
    "bold": ParagraphStyle("bold", parent=BASE, fontName="Helvetica-Bold"),
    "bold_right": ParagraphStyle("bold_right", parent=BASE, fontName="Helvetica-Bold",
                                 alignment=TA_RIGHT),
    "head": ParagraphStyle("head", parent=BASE, fontName="Helvetica-Bold", fontSize=7.5,
                           leading=10, textColor=MUTED),
    "head_right": ParagraphStyle("head_right", parent=BASE, fontName="Helvetica-Bold",
                                 fontSize=7.5, leading=10, textColor=MUTED, alignment=TA_RIGHT),
    "label": ParagraphStyle("label", parent=BASE, fontSize=7.5, leading=10, textColor=MUTED),
    "kicker": ParagraphStyle("kicker", parent=BASE, fontSize=8.5, leading=11, textColor=MUTED),
    "kicker_right": ParagraphStyle("kicker_right", parent=BASE, fontSize=8.5, leading=11,
                                   textColor=MUTED, alignment=TA_RIGHT),
    "code": ParagraphStyle("code", parent=BASE, fontName="Helvetica-Bold", fontSize=15,
                           leading=19, alignment=TA_RIGHT),
    "client": ParagraphStyle("client", parent=BASE, fontName="Helvetica-Bold", fontSize=20,
                             leading=24, spaceAfter=2),
    "h2": ParagraphStyle("h2", parent=BASE, fontName="Helvetica-Bold", fontSize=11.5,
                         leading=15, spaceBefore=16, spaceAfter=6),
    "price_label": ParagraphStyle("price_label", parent=BASE, fontSize=8.5, leading=11,
                                  textColor=colors.HexColor("#B9C6D3")),
    "price": ParagraphStyle("price", parent=BASE, fontName="Helvetica-Bold", fontSize=24,
                            leading=29, textColor=colors.white),
    "price_side_label": ParagraphStyle("price_side_label", parent=BASE, fontSize=7.5,
                                       leading=10, textColor=colors.HexColor("#B9C6D3")),
    "price_side": ParagraphStyle("price_side", parent=BASE, fontName="Helvetica-Bold",
                                 fontSize=10, leading=13, textColor=colors.white),
    "total": ParagraphStyle("total", parent=BASE, fontName="Helvetica-Bold", fontSize=9.5,
                            leading=13, textColor=colors.white),
    "total_right": ParagraphStyle("total_right", parent=BASE, fontName="Helvetica-Bold",
                                  fontSize=9.5, leading=13, textColor=colors.white,
                                  alignment=TA_RIGHT),
}


def _p(text: object, style: str = "body") -> Paragraph:
    """Todo texto do usuário é escapado: o Paragraph interpreta marcação (<img>, <a>)."""
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), STYLES[style])


class BrandRule(Flowable):
    """As três pinceladas da marca seguidas de um fio até a margem."""

    def __init__(self, width: float) -> None:
        super().__init__()
        self.width, self.height = width, 3

    def wrap(self, *_args: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        x = 0.0
        for color in BRAND_STROKES:
            self.canv.setFillColor(colors.HexColor(color))
            self.canv.rect(x, 0, 30, 3, stroke=0, fill=1)
            x += 33
        self.canv.setStrokeColor(HAIRLINE)
        self.canv.setLineWidth(0.6)
        self.canv.line(x + 3, 1.5, self.width, 1.5)


class CompositionBar(Flowable):
    """Faixa empilhada com as partes do preço e a legenda de cada parte."""

    BAR_HEIGHT = 9
    LEGEND_HEIGHT = 30

    def __init__(self, parts: list[dict], width: float) -> None:
        super().__init__()
        self.parts, self.width = parts, width
        self.height = self.BAR_HEIGHT + self.LEGEND_HEIGHT

    def wrap(self, *_args: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        canv, gap = self.canv, 1.5
        usable = self.width - gap * (len(self.parts) - 1)
        x = 0.0
        for part in self.parts:
            canv.setFillColor(colors.HexColor(f"#{part['color']}"))
            segment = max(usable * part["share"], 1.5)
            canv.rect(x, self.LEGEND_HEIGHT, segment, self.BAR_HEIGHT, stroke=0, fill=1)
            x += segment + gap
        column = self.width / len(self.parts)
        for index, part in enumerate(self.parts):
            left = index * column
            canv.setFillColor(colors.HexColor(f"#{part['color']}"))
            canv.rect(left, 13.5, 6, 6, stroke=0, fill=1)
            canv.setFillColor(MUTED)
            canv.setFont("Helvetica", 7.5)
            canv.drawString(left + 10, 14, f"{part['label']} · {part['percent']}")
            canv.setFillColor(INK)
            canv.setFont("Helvetica-Bold", 9)
            canv.drawString(left + 10, 2, part["value"])


class NumberedCanvas(pdf_canvas.Canvas):
    """Adia a gravação das páginas para escrever "Página X de Y" no rodapé."""

    def __init__(self, *args: object, footer_text: str = "", **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._pages: list[dict] = []
        self._footer_text = footer_text

    def showPage(self) -> None:  # noqa: N802 - API do ReportLab
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int) -> None:
        self.saveState()
        self.setStrokeColor(HAIRLINE)
        self.setLineWidth(0.6)
        self.line(MARGIN, 40, PAGE_WIDTH - MARGIN, 40)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(MUTED)
        self.drawString(MARGIN, 28, self._footer_text)
        self.drawRightString(PAGE_WIDTH - MARGIN, 28, f"Página {self._pageNumber} de {total}")
        self.restoreState()


def _logo(width: float) -> Flowable:
    if not LOGO_PATH.exists():
        return _p(COMPANY, "bold")
    image_width, image_height = ImageReader(str(LOGO_PATH)).getSize()
    return Image(str(LOGO_PATH), width=width, height=width * image_height / image_width)


def _header(model: dict) -> Table:
    detail = " · ".join(part for part in (model["status"], model["fields"][2][1]) if part
                        and part != "N/A")
    right = [_p("Orçamento comercial", "kicker_right"), _p(model["code"], "code")]
    if detail:
        right.append(_p(detail, "kicker_right"))
    table = Table([[_logo(132), right]], colWidths=[CONTENT_WIDTH * 0.45, CONTENT_WIDTH * 0.55],
                  hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _price_box(model: dict) -> Table:
    side = []
    for label, value in model["highlights"]:
        side += [_p(label, "price_side_label"), _p(value, "price_side"), Spacer(1, 4)]
    table = Table(
        [[[_p(model["price_label"], "price_label"), _p(model["price"], "price")], side[:-1]]],
        colWidths=[CONTENT_WIDTH * 0.62, CONTENT_WIDTH * 0.38], cornerRadii=(5, 5, 5, 5),
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16), ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LINEBEFORE", (1, 0), (1, 0), 0.6, colors.HexColor("#3A4756")),
    ]))
    return table


def _fields(model: dict) -> Table:
    """Dados contratuais em duas colunas de rótulo sobre valor."""
    cells = [[_p(label, "label"), _p(value)] for label, value in model["fields"][1:]]
    if len(cells) % 2:
        cells.append("")
    rows = [cells[index:index + 2] for index in range(0, len(cells), 2)]
    table = Table(rows, colWidths=[CONTENT_WIDTH / 2] * 2, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, HAIRLINE),
    ]))
    return table


def _column_widths(count: int) -> list[float]:
    numeric = {2: [170], 3: [80, 120], 4: [70, 92, 92]}[count]
    return [CONTENT_WIDTH - sum(numeric), *numeric]


def _item_table(headers: list, rows: list, footer: list) -> Table:
    count = len(headers)
    data = [[_p(text, "head" if index == 0 else "head_right")
             for index, text in enumerate(headers)]]
    data += [[_p(cell, "body" if index == 0 else "body_right")
              for index, cell in enumerate(row)] for row in rows]
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, len(rows)), [colors.white, ZEBRA]),
    ]
    for label, value in footer:
        index = len(data)
        data.append([_p(label, "bold"), *[""] * (count - 2), _p(value, "bold_right")])
        style += [("SPAN", (0, index), (count - 2, index)),
                  ("LINEABOVE", (0, index), (-1, index), 0.6, HAIRLINE)]
    if footer:
        style.append(("LINEABOVE", (0, len(rows) + 1), (-1, len(rows) + 1), 0.9, INK))
        # O subtotal nunca vai sozinho para a página seguinte: leva a última linha junto.
        style.append(("NOSPLIT", (0, max(len(rows), 1)), (-1, len(data) - 1)))
    table = Table(data, colWidths=_column_widths(count), repeatRows=1, splitInRow=1,
                  hAlign="LEFT")
    table.setStyle(TableStyle(style))
    return table


def _summary_table(rows: list) -> Table:
    data = [[_p(label), _p(value, "body_right")] for label, value in rows[:-1]]
    label, value = rows[-1]
    data.append([_p(label, "total"), _p(value, "total_right")])
    last = len(data) - 1
    table = Table(data, colWidths=_column_widths(2), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, last - 1), 0.5, HAIRLINE),
        ("BACKGROUND", (0, last), (-1, last), INK),
        ("TOPPADDING", (0, last), (-1, last), 9), ("BOTTOMPADDING", (0, last), (-1, last), 9),
    ]))
    return table


def _story(model: dict) -> list:
    story: list = [_header(model), BrandRule(CONTENT_WIDTH), Spacer(1, 18),
                   _p("Proposta para", "kicker"), _p(model["client"], "client"), Spacer(1, 10),
                   _price_box(model)]
    if model["composition"]:
        story += [Spacer(1, 12), CompositionBar(model["composition"], CONTENT_WIDTH)]
    story += [Spacer(1, 10), _fields(model),
              _p("Identificação e escopo", "h2"), _p(model["scope"])]
    for table in model["tables"]:
        heading = _p(table["title"], "h2")
        if not table["rows"] and not table["footer"]:
            story.append(heading)
            continue
        body = _item_table(table["headers"], table["rows"], table["footer"])
        # Tabelas curtas não se separam do título; nas longas o título só fica na página se
        # couber com o cabeçalho e as primeiras linhas, e o cabeçalho se repete nas quebras.
        if len(table["rows"]) <= 6:
            story.append(KeepTogether([heading, body]))
        else:
            story += [CondPageBreak(110), heading, body]
    story.append(KeepTogether([_p("Impostos e resumo", "h2"), _summary_table(model["summary"])]))
    if model["notes"]:
        story += [_p("Observações", "h2"), _p(model["notes"])]
    return story


def render_pdf(model: dict) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=MARGIN - FRAME_PADDING,
        rightMargin=MARGIN - FRAME_PADDING, topMargin=44,
        bottomMargin=56, title=model["code"], author=COMPANY,
        subject=f"Orçamento comercial {model['code']}",
    )
    footer_text = f"{COMPANY} · {model['code']}"

    def later_pages(canvas: pdf_canvas.Canvas, _document: object) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 30, model["code"])
        canvas.restoreState()

    document.build(
        _story(model), onLaterPages=later_pages,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, footer_text=footer_text, **kwargs),
    )
    return output.getvalue()
