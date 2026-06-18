"""Testes para FluxoCaixaValidator."""

import pandas as pd

from app.validacao.validators import FluxoCaixaValidator


def _dados_fluxo(df, arquivo="RELATORIO DE MOVIMENTO ITAU SISTEMA.xls"):
    return {
        "arquivo": arquivo,
        "abas": ["Sheet"],
        "dados": {"Sheet": df},
        "formato": ".xls",
    }


def test_ignora_linhas_de_rodape_nos_warnings_de_data():
    df = pd.DataFrame(
        {
            "Data Mov.": [
                "01/05/2025",
                "02/05/2025",
                "Filtros utilizados:",
                (
                    "Empresa:A IDEAL | Conta bancária: BANCO ITAU | "
                    "Data inicial: 01/05/2025 | Data final: 31/05/2025"
                ),
            ],
            "Tipo": ["Crédito", "Débito", "", ""],
            "Desc. Mov.": ["Recebimento", "Pagamento", "", ""],
            "Valor (R$)": [1000.0, 200.0, None, None],
            "Saldo (R$)": [1000.0, 800.0, None, None],
            "Conta Gerencial Mov": ["Recebimento de Clientes", "Fornecedores", "", ""],
        }
    )

    result = FluxoCaixaValidator().validar(_dados_fluxo(df))

    assert result.valido is True
    assert all(w.campo != "data_movimento" for w in result.warnings)


def test_validar_lote_ignora_relatorio_sem_movimentos_quando_ha_arquivo_valido():
    df_valido = pd.DataFrame(
        {
            "Data Mov.": ["01/08/2025"],
            "Tipo": ["Crédito"],
            "Desc. Mov.": ["Recebimento cliente"],
            "Valor (R$)": [1000.0],
            "Saldo (R$)": [1000.0],
            "Conta Gerencial Mov": ["Recebimento de Clientes"],
        }
    )
    df_sem_movimentos = pd.DataFrame(
        {
            "Empresa": ["A IDEAL SOLUÇÕES ANTICORROSIVAS LTDA"],
            "Relatório": ["Nenhum registro encontrado"],
        }
    )

    result = FluxoCaixaValidator().validar_lote(
        [
            _dados_fluxo(df_valido, "RELATORIO DE MOVIMENTO SIMPLES caix a.xls"),
            _dados_fluxo(df_sem_movimentos, "RELATORIO DE MOVIMENTO SIMPLES itau isolamento.xls"),
        ]
    )

    assert result.valido is True
    assert result.erros == []
    assert "cef" in result.bancos_identificados
    assert any("foi ignorado" in warning.mensagem for warning in result.warnings)


def test_validar_lote_bloqueia_quando_todos_os_arquivos_nao_tem_movimentos():
    df_sem_movimentos = pd.DataFrame(
        {
            "Empresa": ["A IDEAL SOLUÇÕES ANTICORROSIVAS LTDA"],
            "Relatório": ["Nenhum registro encontrado"],
        }
    )

    result = FluxoCaixaValidator().validar_lote(
        [
            _dados_fluxo(df_sem_movimentos, "RELATORIO DE MOVIMENTO SIMPLES itau isolamento.xls"),
        ]
    )

    assert result.valido is False
    assert any(erro.campo == "arquivos" for erro in result.erros)
    assert any("Nenhum arquivo válido" in erro.mensagem for erro in result.erros)


def test_fluxo_validacao_aceita_conta_gerencial_por_codigo():
    df = pd.DataFrame(
        {
            "Data Mov.": ["01/07/2025"],
            "Tipo": ["Débito"],
            "Desc. Mov.": ["Água administrativa"],
            "Valor (R$)": [350.0],
            "Saldo (R$)": [1000.0],
            "Conta Gerencial Mov": ["11.2 - AGUA ADM (100,00%);"],
        }
    )

    result = FluxoCaixaValidator().validar(_dados_fluxo(df))

    assert result.valido is True
    assert all(e.campo != "classificacao" for e in result.erros)


def test_fluxo_validacao_aceita_codigo_gerencial_em_coluna_separada():
    df = pd.DataFrame(
        {
            "Data Mov.": ["01/06/2026"],
            "Tipo": ["Débito"],
            "Descrição": ["Pagamento parcelamento"],
            "Valor": [1029.44],
            "Saldo": [5000.0],
            "Cód. Conta Gerencial": ["17.1"],
            "Conta Gerencial": ["PARCELAMENTO"],
        }
    )

    result = FluxoCaixaValidator().validar(_dados_fluxo(df))

    assert result.valido is True
    assert all(e.campo != "classificacao" for e in result.erros)


def test_fluxo_validacao_bloqueia_codigo_gerencial_desconhecido():
    df = pd.DataFrame(
        {
            "Data Mov.": ["01/07/2025"],
            "Tipo": ["Débito"],
            "Desc. Mov.": ["Conta desconhecida"],
            "Valor (R$)": [350.0],
            "Saldo (R$)": [1000.0],
            "Conta Gerencial Mov": ["99.9 - CONTA NOVA (100,00%);"],
        }
    )

    result = FluxoCaixaValidator().validar(_dados_fluxo(df))

    assert result.valido is False
    assert any(e.campo == "classificacao" for e in result.erros)


def test_fluxo_validacao_bloqueia_codigo_separado_desconhecido():
    df = pd.DataFrame(
        {
            "Data Mov.": ["01/06/2026"],
            "Tipo": ["Débito"],
            "Descrição": ["Conta desconhecida"],
            "Valor": [350.0],
            "Saldo": [1000.0],
            "Cód. Conta Gerencial": ["99.9"],
            "Conta Gerencial": ["CONTA NOVA"],
        }
    )

    result = FluxoCaixaValidator().validar(_dados_fluxo(df))

    assert result.valido is False
    assert any(e.campo == "classificacao" for e in result.erros)
