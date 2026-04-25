#!/usr/bin/env python3
"""Gera o PDF executivo da Fase 2 a partir da fonte Markdown."""

from __future__ import annotations

import argparse
import html
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
SOURCE_MD = DOCS_DIR / "fase2_motor_dre_detalhado.md"
OUTPUT_PDF = DOCS_DIR / "Fase_2_Motor_DRE_AIDEAL.pdf"
FONTS_DIR = DOCS_DIR / "assets" / "fonts"
FONT_REGULAR = FONTS_DIR / "Inter-Regular.ttf"
FONT_SEMIBOLD = FONTS_DIR / "Inter-SemiBold.ttf"

VERSION = "v1.0"
TITLE = "Fase 2 - Motor DRE AIDEAL"
SUBTITLE = "Documentacao tecnica e executiva"

PRIMARY = colors.HexColor("#1687E0")
PRIMARY_DARK = colors.HexColor("#0F4C81")
TEXT = colors.HexColor("#2E3640")
TEXT_SOFT = colors.HexColor("#5F6A76")
BORDER = colors.HexColor("#C8D0D9")


def register_fonts() -> tuple[str, str]:
    """Registra as fontes AIDEAL no PDF."""
    regular_name = "Helvetica"
    semibold_name = "Helvetica-Bold"

    if FONT_REGULAR.exists():
        regular_name = "Inter-Regular"
        pdfmetrics.registerFont(TTFont(regular_name, str(FONT_REGULAR)))

    if FONT_SEMIBOLD.exists():
        semibold_name = "Inter-SemiBold"
        pdfmetrics.registerFont(TTFont(semibold_name, str(FONT_SEMIBOLD)))

    return regular_name, semibold_name


def inline_markup(text: str) -> str:
    """Converte marcações simples de Markdown para a sintaxe do reportlab."""
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    return escaped


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def build_styles(regular_font: str, semibold_font: str):
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="AIDEALBody",
            parent=styles["BodyText"],
            fontName=regular_font,
            fontSize=9.3,
            leading=13,
            textColor=TEXT,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDEALBullet",
            parent=styles["BodyText"],
            fontName=regular_font,
            fontSize=9.2,
            leading=13,
            textColor=TEXT,
            leftIndent=13,
            firstLineIndent=0,
            bulletIndent=0,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDEALHeading1",
            parent=styles["Heading1"],
            fontName=semibold_font,
            fontSize=14,
            leading=18,
            textColor=PRIMARY_DARK,
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDEALHeading2",
            parent=styles["Heading2"],
            fontName=semibold_font,
            fontSize=11.8,
            leading=15,
            textColor=PRIMARY,
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDEALTitle",
            parent=styles["Title"],
            fontName=semibold_font,
            fontSize=22,
            leading=26,
            textColor=PRIMARY_DARK,
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDEALSubtitle",
            parent=styles["BodyText"],
            fontName=regular_font,
            fontSize=11,
            leading=15,
            textColor=TEXT_SOFT,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDEALMeta",
            parent=styles["BodyText"],
            fontName=regular_font,
            fontSize=8.6,
            leading=11,
            textColor=TEXT_SOFT,
            alignment=TA_CENTER,
        )
    )
    return styles


def draw_page(canvas, doc, first_page: bool = False):
    canvas.saveState()

    width, height = A4

    if not first_page:
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.7)
        canvas.line(doc.leftMargin, height - 15 * mm, width - doc.rightMargin, height - 15 * mm)
        canvas.setFont(doc._regular_font_name, 8.5)
        canvas.setFillColor(PRIMARY_DARK)
        canvas.drawString(doc.leftMargin, height - 12.8 * mm, "AIDEAL GoFlowOS | Fase 2 Motor DRE")
        canvas.setFillColor(TEXT_SOFT)
        canvas.drawRightString(width - doc.rightMargin, height - 12.8 * mm, f"Versao {VERSION}")

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.7)
    canvas.line(doc.leftMargin, 13 * mm, width - doc.rightMargin, 13 * mm)
    canvas.setFont(doc._regular_font_name, 8.4)
    canvas.setFillColor(TEXT_SOFT)
    canvas.drawString(doc.leftMargin, 8.7 * mm, "Processamento local por padrao | Cloudflare browser-first + local/server")
    canvas.drawCentredString(width / 2, 8.7 * mm, f"Versao {VERSION}")
    canvas.drawRightString(width - doc.rightMargin, 8.7 * mm, f"Pagina {canvas.getPageNumber()}")

    canvas.restoreState()


def parse_markdown(md_text: str, styles):
    story = []
    lines = md_text.splitlines()
    i = 0
    first_title = True

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 3.5))
            i += 1
            continue

        if stripped.startswith("# "):
            if first_title:
                first_title = False
                story.extend(
                    [
                        Spacer(1, 18 * mm),
                        Paragraph(inline_markup(stripped[2:]), styles["AIDEALTitle"]),
                    ]
                )
            else:
                story.append(Paragraph(inline_markup(stripped[2:]), styles["AIDEALHeading1"]))
            i += 1
            continue

        if stripped.startswith("## "):
            story.append(Paragraph(inline_markup(stripped[3:]), styles["AIDEALHeading1"]))
            i += 1
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(inline_markup(stripped[4:]), styles["AIDEALHeading2"]))
            i += 1
            continue

        if stripped.startswith("- "):
            story.append(Paragraph(inline_markup(stripped[2:]), styles["AIDEALBullet"], bulletText="•"))
            i += 1
            continue

        if stripped == "---":
            story.append(Spacer(1, 4))
            i += 1
            continue

        story.append(Paragraph(inline_markup(stripped), styles["AIDEALBody"]))
        i += 1

    return story


def build_pdf(source_md: Path, output_pdf: Path) -> Path:
    if not source_md.exists():
        raise FileNotFoundError(f"Fonte Markdown nao encontrada: {source_md}")

    regular_font, semibold_font = register_fonts()
    styles = build_styles(regular_font, semibold_font)
    markdown = source_md.read_text(encoding="utf-8")

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=TITLE,
        author="AIDEAL",
        subject="Plano detalhado da Fase 2 - Motor DRE",
        creator="Codex",
    )
    doc._regular_font_name = regular_font  # type: ignore[attr-defined]

    story = [
        Paragraph("AIDEAL GoFlowOS", styles["AIDEALMeta"]),
        Spacer(1, 4),
        Paragraph(TITLE, styles["AIDEALTitle"]),
        Paragraph(SUBTITLE, styles["AIDEALSubtitle"]),
        Paragraph(
            f"Versao {VERSION} | Gerado em {datetime.now().strftime('%d/%m/%Y')}",
            styles["AIDEALMeta"],
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            "Documento tecnico-executivo para orientar a implementacao da Fase 2 do MVP, com foco no Motor DRE.",
            styles["AIDEALBody"],
        ),
        PageBreak(),
    ]
    story.extend(parse_markdown(markdown, styles))

    doc.build(
        story,
        onFirstPage=lambda canvas, doc: draw_page(canvas, doc, first_page=True),
        onLaterPages=lambda canvas, doc: draw_page(canvas, doc, first_page=False),
    )

    return output_pdf


def validate_pdf(pdf_path: Path) -> dict:
    if PdfReader is None:
        return {"pages": None, "checks": {}}

    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    text_norm = strip_accents(text).lower()
    return {
        "pages": len(reader.pages),
        "checks": {
            "contains_title": strip_accents(TITLE).lower() in text_norm,
            "contains_inventory": "inventario de caminhos" in text_norm,
            "contains_backend_path": "/users/gousero/abiente dev/scriptpyaideal/backend/config/dre_mapping.json"
            in text_norm,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o PDF da Fase 2 do Motor DRE AIDEAL.")
    parser.add_argument("--source", default=str(SOURCE_MD), help="Arquivo Markdown fonte")
    parser.add_argument("--output", default=str(OUTPUT_PDF), help="Arquivo PDF de saida")
    args = parser.parse_args()

    pdf_path = build_pdf(Path(args.source), Path(args.output))
    validation = validate_pdf(pdf_path)

    print(f"[ok] PDF gerado: {pdf_path}")
    if validation["pages"] is not None:
        print(f"[ok] Paginas: {validation['pages']}")
        print(f"[ok] Validacao: {validation['checks']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
