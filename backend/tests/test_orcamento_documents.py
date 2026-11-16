"""Exports use the selected revision, never mutable budget/current defaults."""

from copy import deepcopy
from io import BytesIO

import pytest
from docx import Document
from pypdf import PdfReader

from app.orcamento.documents import export_orcamento_document


@pytest.fixture
def revision():
    return {
        "numero": 0, "escopo": "Pintura industrial <A&B>", "modalidade": "m²",
        "regiao": "Salvador/BA", "prazo_execucao_dias": 10,
        "dfp": {
            "metadata": {"cliente_unidade": "Contratante histórica", "area_total": 100},
            "equipamentos": {"items": [
                {"id": "compressor", "label": "Compressor especial", "quantity": 2,
                 "unit_cost": 123.45},
            ]},
        },
    }


@pytest.mark.parametrize("fmt", ["docx", "pdf"])
def test_selected_revision_is_exported_without_mutation(revision, fmt):
    original = deepcopy(revision)
    data, mime, filename = export_orcamento_document(
        {"codigo": "ORC-0007", "contratante": "Nome atual"}, revision, fmt,
    )
    assert filename == f"ORC-0007-R0.{fmt}"
    if fmt == "docx":
        doc = Document(BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
        text += "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        assert "wordprocessingml" in mime
    else:
        reader = PdfReader(BytesIO(data))
        text = "\n".join(p.extract_text() for p in reader.pages)
        assert mime == "application/pdf"
    assert "ORC-0007-R0" in text
    assert "Contratante histórica" in text
    assert "Compressor especial" in text
    assert "246,90" in text
    assert "Pintura industrial <A&B>" in text
    assert revision == original


def test_invalid_format_is_rejected(revision):
    with pytest.raises(ValueError, match="Formato"):
        export_orcamento_document({"codigo": "ORC-0007"}, revision, "html")


def test_pdf_paginates_long_item_tables(revision):
    revision["dfp"]["equipamentos"]["items"] = [
        {"id": str(i), "label": f"Equipamento {i} " + "detalhes " * 8,
         "quantity": 1, "unit_cost": 10} for i in range(90)
    ]
    data, _, _ = export_orcamento_document({"codigo": "ORC-0007"}, revision, "pdf")
    reader = PdfReader(BytesIO(data))
    assert len(reader.pages) > 2
    assert "Equipamento 89" in "\n".join(p.extract_text() for p in reader.pages)


def test_pdf_accepts_maximum_length_item_label(revision):
    revision['dfp']['equipamentos']['items'][0]['label'] = 'Detalhe ' * 490 + 'FINAL'
    data, _, _ = export_orcamento_document({'codigo': 'ORC-0007'}, revision, 'pdf')
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    assert 'FINAL' in text


@pytest.mark.parametrize('fmt', ['pdf', 'docx'])
def test_legacy_lodging_items_are_not_hidden_in_export(revision, fmt):
    revision['dfp']['veiculos_hospedagem'] = {'lodging_assets': [
        {'id': 'cama', 'label': 'Cama histórica', 'quantity': 2, 'unit_cost': 100},
    ]}
    data, _, _ = export_orcamento_document({'codigo': 'ORC-0007'}, revision, fmt)
    if fmt == 'pdf':
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    else:
        doc = Document(BytesIO(data))
        text = '\n'.join(
            cell.text for table in doc.tables for row in table.rows for cell in row.cells
        )
    assert 'Cama histórica' in text


def test_filename_cannot_use_untrusted_code(revision):
    with pytest.raises(ValueError, match="Código"):
        export_orcamento_document({"codigo": "../../private"}, revision, "pdf")


@pytest.mark.parametrize('fmt', ['docx', 'pdf'])
def test_export_handles_control_characters_from_historical_data(revision, fmt):
    revision['escopo'] = 'Escopo\x00 com\x0b controles'
    revision['dfp']['equipamentos']['items'][0]['label'] = 'Item\x01 histórico'
    original = deepcopy(revision)
    data, _, _ = export_orcamento_document({'codigo': 'ORC-0007'}, revision, fmt)
    assert data
    assert revision == original


def _docx_text(data):
    doc = Document(BytesIO(data))
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    return "\n".join([p.text for p in doc.paragraphs] + cells)


def _pdf_text(data):
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)


@pytest.mark.parametrize("fmt", ["docx", "pdf"])
def test_export_shows_price_composition_and_line_totals(revision, fmt):
    revision["dfp"]["bdi"] = {"factor_percent": 10}
    revision["dfp"]["impostos"] = {"items": [{"id": "iss", "label": "ISS", "aliquot_percent": 5}]}
    data, _, _ = export_orcamento_document({"codigo": "ORC-0007"}, revision, fmt)
    text = _docx_text(data) if fmt == "docx" else _pdf_text(data)
    # 2 x 123,45 = 246,90 de custo direto; lucro de 10 %; preço = 271,59 / 0,95.
    assert "Total (R$)" in text
    assert "Subtotal" in text
    assert "R$ 285,88" in text
    for label in ("Custos diretos", "Lucro e BDI", "Impostos"):
        assert label in text
    assert "86,36 %" in text


def test_export_formats_iso_dates_and_status(revision):
    revision.update(situacao="emitido", emitido_em="2026-11-16T15:04:48+00:00",
                    valido_ate="2026-12-16")
    data, _, _ = export_orcamento_document({"codigo": "ORC-0007"}, revision, "pdf")
    text = _pdf_text(data)
    assert "16/11/2026" in text
    assert "16/12/2026" in text
    assert "Emitido" in text
    assert "2026-12-16" not in text


def test_pdf_numbers_pages_with_total(revision):
    data, _, _ = export_orcamento_document({"codigo": "ORC-0007"}, revision, "pdf")
    reader = PdfReader(BytesIO(data))
    assert f"Página 1 de {len(reader.pages)}" in _pdf_text(data)


def test_section_discount_is_stated_next_to_the_subtotal(revision):
    revision["dfp"]["calculation_version"] = 2
    revision["dfp"]["equipamentos"]["discount_percent"] = 10
    data, _, _ = export_orcamento_document({"codigo": "ORC-0007"}, revision, "docx")
    text = _docx_text(data)
    assert "Desconto aplicado (10,00 %)" in text
    assert "R$ 222,21" in text
