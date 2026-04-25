"""Testes unitários para ExcelParser (ingestao/parser.py)."""

import pandas as pd
import pytest
from openpyxl import Workbook

from app.ingestao.parser import ExcelParser


class TestExcelParserInit:
    def test_carrega_mapping_dre(self):
        parser = ExcelParser("dre")
        assert "entrada" in parser.mapping
        assert "saida" in parser.mapping
        assert "validacao" in parser.mapping

    def test_carrega_mapping_fluxo(self):
        parser = ExcelParser("fluxo")
        assert "entrada" in parser.mapping


class TestMapearColunas:
    def test_mapeia_aliases_dre_padrao(self):
        parser = ExcelParser("dre")
        df = pd.DataFrame({
            "Emissão": [],
            "Descri.": [],
            "Vlr.bruto (R$)": [],
            "CLASSIFICAÇÃO": [],
        })
        mapeamento = parser.mapear_colunas(df)
        assert mapeamento["data"] == "Emissão"
        assert mapeamento["historico"] == "Descri."
        assert mapeamento["credito"] == "Vlr.bruto (R$)"
        assert mapeamento["natureza"] == "CLASSIFICAÇÃO"

    def test_mapeia_alias_com_quebra_de_linha(self):
        parser = ExcelParser("dre")
        df = pd.DataFrame({
            "Emissão": [],
            "Descri.\n": [],
            "Vlr.bruto (R$)": [],
            "CLASSIFICAÇÃO": [],
            "Obra/\nCentro custo": [],
        })
        mapeamento = parser.mapear_colunas(df)
        assert mapeamento["centro_custo"] == "Obra/\nCentro custo"

    def test_coluna_nao_encontrada_retorna_none(self):
        parser = ExcelParser("dre")
        df = pd.DataFrame({"Coluna_Inexistente": []})
        mapeamento = parser.mapear_colunas(df)
        assert mapeamento["data"] is None
        assert mapeamento["historico"] is None

    def test_case_insensitive(self):
        parser = ExcelParser("dre")
        df = pd.DataFrame({
            "emissão": [],
            "descri.": [],
            "vlr.bruto (r$)": [],
            "classificação": [],
        })
        mapeamento = parser.mapear_colunas(df)
        assert mapeamento["data"] == "emissão"
        assert mapeamento["credito"] == "vlr.bruto (r$)"


class TestDetectarAbaPrincipal:
    def test_maior_numero_linhas(self):
        parser = ExcelParser("dre")
        dados = {
            "abas": ["Pequena", "Grande"],
            "dados": {
                "Pequena": pd.DataFrame({"A": [1]}),
                "Grande": pd.DataFrame({"A": range(100)}),
            },
        }
        assert parser.detectar_aba_principal(dados) == "Grande"

    def test_aba_unica(self):
        parser = ExcelParser("dre")
        dados = {
            "abas": ["Sheet1"],
            "dados": {"Sheet1": pd.DataFrame({"A": [1, 2]})},
        }
        assert parser.detectar_aba_principal(dados) == "Sheet1"


class TestLerArquivo:
    def test_ler_xlsx_valido(self, tmp_path):
        parser = ExcelParser("dre")
        path = tmp_path / "teste.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Dados"
        ws.append(["metadata"])
        ws.append(["Emissão", "Descri.", "Vlr.bruto (R$)", "CLASSIFICAÇÃO"])
        ws.append(["01/05/2025", "Teste", 100.0, "1 - ENTRADA"])
        wb.save(path)

        resultado = parser.ler_arquivo(path)
        assert "Dados" in resultado["abas"]
        assert resultado["formato"] == ".xlsx"
        assert not resultado["dados"]["Dados"].empty

    def test_rejeita_formato_invalido(self, tmp_path):
        parser = ExcelParser("dre")
        path = tmp_path / "teste.csv"
        path.write_text("a,b,c")
        with pytest.raises(ValueError, match="não aceito"):
            parser.ler_arquivo(path)

    def test_fluxo_detecta_cabecalho_com_metadados_nas_primeiras_linhas(self, tmp_path):
        parser = ExcelParser("fluxo")
        path = tmp_path / "fluxo_operacional.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet"
        ws.append(["Relatório gerencial"])
        ws.append(["Conta:", "BANCO ITAU"])
        ws.append([])
        ws.append(["Data Mov.", None, "Tipo", "Desc. Mov.", "Valor (R$)", "Saldo (R$)", "Conta Gerencial Mov"])
        ws.append(["01/05/2025", None, "Débito", "Pagamento fornecedor", 1500.0, 20000.0, "Fornecedores"])
        wb.save(path)

        resultado = parser.ler_arquivo(path)
        df = resultado["dados"]["Sheet"]
        mapeamento = parser.mapear_colunas(df)

        assert mapeamento["data_movimento"] == "Data Mov."
        assert mapeamento["tipo"] == "Tipo"
        assert mapeamento["descricao"] == "Desc. Mov."
        assert mapeamento["valor"] == "Valor (R$)"
        assert mapeamento["saldo"] == "Saldo (R$)"
        assert mapeamento["classificacao"] == "Conta Gerencial Mov"
        assert len(df) == 1


class TestDetectarBanco:
    def test_dre_parser_retorna_none(self):
        parser = ExcelParser("dre")
        assert parser.detectar_banco("qualquer_arquivo.xls") is None

    def test_fluxo_detecta_marcantil_por_nome_arquivo(self):
        parser = ExcelParser("fluxo")
        assert parser.detectar_banco("RELATORIO DE MOVIMENTO MARCANTIL.xls") == "mercantil"
