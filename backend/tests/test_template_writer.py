import re
import shutil
import zipfile
from xml.etree import ElementTree as ET

from app.config import settings
from app.templates.writer import TemplateWriter


def test_limpar_area_preserva_formulas_e_tabela(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        ws = writer._wb["BD_FLUXO"]
        original_h2 = ws["H2"].value

        for col in range(1, 8):
            ws.cell(row=2, column=col, value=f"sentinela-{col}")
            ws.cell(row=3, column=col, value=f"sentinela-{col}")

        writer.limpar_area("BD_FLUXO", 2, 4964, 1, 7)

        assert all(
            ws.cell(row=row, column=col).value is None for row in (2, 3) for col in range(1, 8)
        )
        assert ws["H2"].value == original_h2
        assert "BD_FLUXO1" in ws.tables.keys()
        assert writer.validar_integridade() == []


def test_ocultar_colunas_xml_patch_sincroniza_estado_em_memoria_sem_mesclar_sheet(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        writer.ocultar_colunas_xml_patch("DRE", ["N", "O"], False)
        writer.ocultar_colunas_xml_patch("DRE", ["L", "M"], True)

        ws = writer._wb["DRE"]
        assert ws.column_dimensions["N"].hidden is False
        assert ws.column_dimensions["O"].hidden is False
        assert ws.column_dimensions["L"].hidden is True
        assert ws.column_dimensions["M"].hidden is True
        assert "DRE" not in writer._modified_sheets


def test_mescla_preserva_extlst_e_rel_slicer_quando_rels_editado_ausente(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        part_sheet = "xl/worksheets/sheet2.xml"
        part_rels = "xl/worksheets/_rels/sheet2.xml.rels"
        with zipfile.ZipFile(template_copy, "r") as zf:
            sheet_tpl = zf.read(part_sheet)
            rel_tpl = zf.read(part_rels)

        # Simula sheet editada sem extLst e sem arquivo .rels,
        # cenário observado quando o openpyxl remove extensões de slicer.
        sheet_edit_root = ET.fromstring(sheet_tpl)
        ext_tag = f"{{{writer.NS_MAIN}}}extLst"
        ext = sheet_edit_root.find(ext_tag)
        if ext is not None:
            sheet_edit_root.remove(ext)
        sheet_edit = ET.tostring(sheet_edit_root, encoding="utf-8", xml_declaration=True)

        merged_sheet, merged_rels = writer._mesclar_sheet_com_template(
            sheet_tpl_bytes=sheet_tpl,
            sheet_edit_bytes=sheet_edit,
            rel_tpl_bytes=rel_tpl,
            rel_edit_bytes=None,
        )

        assert merged_rels is not None
        merged_sheet_text = merged_sheet.decode("utf-8", errors="ignore")
        merged_rels_text = merged_rels.decode("utf-8", errors="ignore")
        assert "extLst" in merged_sheet_text
        assert "slicerList" in merged_sheet_text
        assert "mc:Ignorable=" in merged_sheet_text
        assert "xmlns:x14ac=" in merged_sheet_text
        assert "xmlns:xr=" in merged_sheet_text
        assert "relationships/slicer" in merged_rels_text


def test_forcar_recalculo_preserva_prefixos_originais_do_workbook(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        with zipfile.ZipFile(template_copy, "r") as zf:
            workbook_xml = zf.read("xl/workbook.xml")

        ajustado = writer._forcar_recalculo_workbook_xml(workbook_xml).decode(
            "utf-8",
            errors="ignore",
        )

        assert "mc:Ignorable=" in ajustado
        assert "xmlns:x15=" in ajustado
        assert 'Requires="x15"' in ajustado
        assert 'fullCalcOnLoad="1"' in ajustado
        assert 'forceFullCalc="1"' in ajustado


def test_forcar_refresh_pivot_cache_preserva_prefixos(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        with zipfile.ZipFile(template_copy, "r") as zf:
            pivot_xml = zf.read("xl/pivotCache/pivotCacheDefinition1.xml")

        writer.esvaziar_pivot_cache_records()
        ajustado = writer._forcar_refresh_pivot_cache_xml(pivot_xml).decode(
            "utf-8",
            errors="ignore",
        )
        assert "mc:Ignorable" in ajustado
        assert "xmlns:xr=" in ajustado
        assert 'refreshOnLoad="1"' in ajustado
        assert 'saveData="0"' in ajustado
        assert 'invalid="1"' not in ajustado
        assert 'recordCount="0"' in ajustado


def test_remove_rel_pivot_cache_records(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        with zipfile.ZipFile(template_copy, "r") as zf:
            rels_xml = zf.read("xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels")

        ajustado = writer._remover_rel_pivot_cache_records(rels_xml).decode(
            "utf-8",
            errors="ignore",
        )
        assert "pivotCacheRecords" not in ajustado


def test_remove_content_type_pivot_cache_records(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        with zipfile.ZipFile(template_copy, "r") as zf:
            content_types_xml = zf.read("[Content_Types].xml")

        ajustado = writer._remover_content_type_pivot_cache_records(content_types_xml).decode(
            "utf-8",
            errors="ignore",
        )
        assert "pivotCacheRecords" not in ajustado


def test_excel_safe_limpar_sheet_xml_remove_drawing_com_xmlns_rid():
    sheet_xml = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData/>"
        '<drawing xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'r:id="rId1" />'
        "</worksheet>"
    ).encode("utf-8")

    ajustado = TemplateWriter._excel_safe_limpar_sheet_xml(
        sheet_xml,
        "xl/worksheets/sheet5.xml",
    ).decode("utf-8", errors="ignore")

    assert "<drawing" not in ajustado


def test_aplicar_override_table_ref_remove_formulas_calculadas_quando_solicitado(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        with zipfile.ZipFile(template_copy, "r") as zf:
            table_xml = zf.read("xl/tables/table2.xml")

        writer.remover_formulas_calculadas_tabela("BD_FLUXO1")
        ajustado = writer._aplicar_override_table_ref(table_xml).decode("utf-8", errors="ignore")

        assert 'displayName="BD_FLUXO1"' in ajustado
        assert "calculatedColumnFormula" not in ajustado


def test_limpar_items_slicer_cache_xml_zera_count_e_remove_itens(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        with zipfile.ZipFile(template_copy, "r") as zf:
            slicer_xml = zf.read("xl/slicerCaches/slicerCache3.xml")

        ajustado = writer._limpar_items_slicer_cache_xml(slicer_xml).decode(
            "utf-8", errors="ignore"
        )
        assert "slicerCacheDefinition" in ajustado
        assert 'count="0"' in ajustado
        assert "<i " not in ajustado


def test_esvaziar_pivot_cache_records_xml_mantem_root_e_sem_registros(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        with zipfile.ZipFile(template_copy, "r") as zf:
            records_xml = zf.read("xl/pivotCache/pivotCacheRecords1.xml")

        ajustado = writer._esvaziar_pivot_cache_records_xml(records_xml).decode(
            "utf-8",
            errors="ignore",
        )
        assert "pivotCacheRecords" in ajustado
        assert 'count="0"' in ajustado
        assert "<r>" not in ajustado


def test_aplicar_sheet_data_override_preserva_estrutura_template(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        with zipfile.ZipFile(template_copy, "r") as zf:
            sheet_tpl = zf.read("xl/worksheets/sheet3.xml")

        sheet_tpl_text = sheet_tpl.decode("utf-8", errors="ignore")
        sheet_data_tpl = re.search(r"<sheetData\b[^>]*>.*?</sheetData>", sheet_tpl_text, re.DOTALL)
        assert sheet_data_tpl is not None
        sheet_data_edit = (
            "<sheetData>"
            '<row r="1"><c r="A1" t="inlineStr"><is><t>HDR</t></is></c></row>'
            '<row r="2"><c r="A2"><v>123</v></c></row>'
            "</sheetData>"
        )
        sheet_edit = sheet_tpl_text.replace(sheet_data_tpl.group(0), sheet_data_edit, 1).encode(
            "utf-8"
        )

        ajustado = writer._aplicar_sheet_data_override(sheet_tpl, sheet_edit).decode(
            "utf-8",
            errors="ignore",
        )

        assert "<tableParts" in ajustado
        assert 'tablePart r:id="rId2"' in ajustado
        assert "mc:Ignorable" in ajustado
        assert sheet_data_edit in ajustado


def test_remover_slicers_remove_partes_e_referencias_no_pacote_final(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    output = tmp_path / "DRE_sem_slicers.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        writer.remover_slicers()
        writer.salvar(output)

    with zipfile.ZipFile(output, "r") as zf:
        nomes = zf.namelist()
        assert not any(n.startswith("xl/slicerCaches/") for n in nomes)
        assert not any(n.startswith("xl/slicers/") for n in nomes)

        workbook_xml = zf.read("xl/workbook.xml").decode("utf-8", errors="ignore")
        workbook_rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8", errors="ignore")
        sheet2_xml = zf.read("xl/worksheets/sheet2.xml").decode("utf-8", errors="ignore")
        sheet2_rels = zf.read("xl/worksheets/_rels/sheet2.xml.rels").decode(
            "utf-8", errors="ignore"
        )
        content_types = zf.read("[Content_Types].xml").decode("utf-8", errors="ignore")

        assert "slicerCaches" not in workbook_xml
        assert "relationships/slicerCache" not in workbook_rels
        assert "slicerList" not in sheet2_xml
        assert "relationships/slicer" not in sheet2_rels
        assert "/xl/slicerCaches/" not in content_types
        assert "/xl/slicers/" not in content_types


def test_remover_slicers_limpa_defined_names_orfaos(tmp_path):
    """Regressão: workbook.xml não deve conter definedNames órfãos (#N/A / Segmentação)
    após remover_slicers(), pois causam prompt de reparo no Excel Desktop."""
    template_copy = tmp_path / "DRE_template.xlsx"
    output = tmp_path / "DRE_limpo.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        writer.remover_slicers()
        writer.salvar(output)

    with zipfile.ZipFile(output, "r") as zf:
        workbook_xml = zf.read("xl/workbook.xml").decode("utf-8", errors="ignore")

    assert "#N/A" not in workbook_xml, "definedNames órfãos (#N/A) não foram removidos"
    assert "SegmentaçãodeDados" not in workbook_xml
    assert "SegmentacaodeDados" not in workbook_xml


def test_registrar_table_ooxml_gera_table_part_consistente(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    output = tmp_path / "DRE_com_table_detalhe.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        ws = writer._wb.create_sheet(title="DETALHE_MENSAL_DB")
        writer._modified_sheets.add("DETALHE_MENSAL_DB")
        cabecalho = [
            "Data Lancamento",
            "Ano",
            "Mes",
            "Mes Nome",
            "Centro de Custo",
            "Natureza Raw",
            "Rubrica",
            "Conta Filho",
            "Conta Pai",
            "Cod",
            "Historico",
            "Credito",
            "Debito",
            "Saldo Liquido",
            "Upload ID",
            "Linha Origem",
            "Hash Linha",
        ]
        ws.append(cabecalho)
        ws.append(
            [
                "2025-06-15",
                2025,
                6,
                "Jun",
                "ADMINISTRATIVO",
                "NATUREZA",
                "RUBRICA",
                "CONTA FILHO",
                "CONTA PAI",
                10,
                "Historico",
                100.0,
                None,
                100.0,
                "upload-1",
                2,
                "hash-1",
            ]
        )

        writer.registrar_table_ooxml(
            sheet_name="DETALHE_MENSAL_DB",
            table_name="DETALHE_MENSAL_DB",
            ref="A1:Q2",
            colunas=cabecalho,
        )
        writer.salvar(output)

    with zipfile.ZipFile(output, "r") as zf:
        nomes = set(zf.namelist())
        assert "xl/tables/table5.xml" in nomes

        table_xml = zf.read("xl/tables/table5.xml").decode("utf-8", errors="ignore")
        sheet6_xml = zf.read("xl/worksheets/sheet6.xml").decode("utf-8", errors="ignore")
        sheet6_rels = zf.read("xl/worksheets/_rels/sheet6.xml.rels").decode(
            "utf-8",
            errors="ignore",
        )
        content_types = zf.read("[Content_Types].xml").decode("utf-8", errors="ignore")

        assert 'displayName="DETALHE_MENSAL_DB"' in table_xml
        assert 'ref="A1:Q2"' in table_xml
        assert "<tableParts" in sheet6_xml
        assert "tablePart" in sheet6_xml
        assert "relationships/table" in sheet6_rels
        assert "table5.xml" in sheet6_rels
        assert "../tables/table5.xml" in sheet6_rels
        assert "/xl/tables/table5.xml" not in sheet6_rels
        assert "/xl/tables/table5.xml" in content_types


def test_registrar_slicer_sobre_table_gera_partes_e_referencias(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    output = tmp_path / "DRE_com_slicers.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        ws = writer._wb.create_sheet(title="DETALHE_MENSAL_DB")
        writer._modified_sheets.add("DETALHE_MENSAL_DB")
        cabecalho = [
            "Data Lancamento",
            "Ano",
            "Mes",
            "Mes Nome",
            "Centro de Custo",
            "Natureza Raw",
            "Rubrica",
            "Conta Filho",
            "Conta Pai",
            "Cod",
            "Historico",
            "Credito",
            "Debito",
            "Saldo Liquido",
            "Upload ID",
            "Linha Origem",
            "Hash Linha",
        ]
        ws.append(cabecalho)
        ws.append(
            [
                "2025-06-15",
                2025,
                6,
                "Jun",
                "ADMINISTRATIVO",
                "NATUREZA",
                "RUBRICA",
                "CONTA FILHO",
                "CONTA PAI",
                10,
                "Historico",
                100.0,
                None,
                100.0,
                "upload-1",
                2,
                "hash-1",
            ]
        )

        writer.registrar_table_ooxml(
            sheet_name="DETALHE_MENSAL_DB",
            table_name="DETALHE_MENSAL_DB",
            ref="A1:Q2",
            colunas=cabecalho,
        )
        writer.registrar_slicer(
            table_name="DETALHE_MENSAL_DB",
            column_name="Mes Nome",
            caption="Mes",
            sheet_destino="DRE",
        )
        writer.registrar_slicer(
            table_name="DETALHE_MENSAL_DB",
            column_name="Ano",
            caption="Ano",
            sheet_destino="DRE",
        )
        writer.ativar_modo_excel_safe()
        writer.salvar(output)

    with zipfile.ZipFile(output, "r") as zf:
        nomes = set(zf.namelist())
        assert any(n.startswith("xl/slicerCaches/slicerCache") for n in nomes)
        assert any(n.startswith("xl/slicers/slicer") for n in nomes)

        workbook_xml = zf.read("xl/workbook.xml").decode("utf-8", errors="ignore")
        workbook_rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8", errors="ignore")
        sheet2_xml = zf.read("xl/worksheets/sheet2.xml").decode("utf-8", errors="ignore")
        sheet2_rels = zf.read("xl/worksheets/_rels/sheet2.xml.rels").decode(
            "utf-8", errors="ignore"
        )
        sheet6_rels = zf.read("xl/worksheets/_rels/sheet6.xml.rels").decode(
            "utf-8", errors="ignore"
        )
        content_types = zf.read("[Content_Types].xml").decode("utf-8", errors="ignore")
        drawing2_xml = zf.read("xl/drawings/drawing2.xml").decode("utf-8", errors="ignore")

        assert "slicerCaches" in workbook_xml
        assert "relationships/slicerCache" in workbook_rels
        assert "slicerList" in sheet2_xml
        assert "relationships/slicer" in sheet2_rels
        assert "/xl/slicerCaches/" in content_types
        assert "/xl/slicers/" in content_types
        assert "drawing/2010/slicer" in drawing2_xml
        assert "../tables/table5.xml" in sheet6_rels
        assert "/xl/tables/table5.xml" not in sheet6_rels


def test_salvar_preserva_nova_aba_criada_por_openpyxl(tmp_path):
    template_copy = tmp_path / "DRE_template.xlsx"
    output = tmp_path / "DRE_com_nova_aba.xlsx"
    shutil.copyfile(settings.template_dre_path, template_copy)

    with TemplateWriter(template_copy) as writer:
        ws = writer._wb.create_sheet(title="NOVA_ABA_TESTE")
        ws["A1"] = "ok"
        writer._modified_sheets.add("NOVA_ABA_TESTE")
        writer.salvar(output)

    with zipfile.ZipFile(output, "r") as zf:
        workbook_xml = zf.read("xl/workbook.xml").decode("utf-8", errors="ignore")
        assert "NOVA_ABA_TESTE" in workbook_xml
        assert any(
            n.startswith("xl/worksheets/sheet") and n.endswith(".xml") for n in zf.namelist()
        )
