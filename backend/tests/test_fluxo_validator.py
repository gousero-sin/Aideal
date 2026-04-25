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
    df = pd.DataFrame({
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
    })

    result = FluxoCaixaValidator().validar(_dados_fluxo(df))

    assert result.valido is True
    assert all(w.campo != "data_movimento" for w in result.warnings)


def test_validar_lote_ignora_relatorio_sem_movimentos_quando_ha_arquivo_valido():
    df_valido = pd.DataFrame({
        "Data Mov.": ["01/08/2025"],
        "Tipo": ["Crédito"],
        "Desc. Mov.": ["Recebimento cliente"],
        "Valor (R$)": [1000.0],
        "Saldo (R$)": [1000.0],
        "Conta Gerencial Mov": ["Recebimento de Clientes"],
    })
    df_sem_movimentos = pd.DataFrame({
        "Empresa": ["A IDEAL SOLUÇÕES ANTICORROSIVAS LTDA"],
        "Relatório": ["Nenhum registro encontrado"],
    })

    result = FluxoCaixaValidator().validar_lote([
        _dados_fluxo(df_valido, "RELATORIO DE MOVIMENTO SIMPLES caix a.xls"),
        _dados_fluxo(df_sem_movimentos, "RELATORIO DE MOVIMENTO SIMPLES itau isolamento.xls"),
    ])

    assert result.valido is True
    assert result.erros == []
    assert "cef" in result.bancos_identificados
    assert any("foi ignorado" in warning.mensagem for warning in result.warnings)


def test_validar_lote_bloqueia_quando_todos_os_arquivos_nao_tem_movimentos():
    df_sem_movimentos = pd.DataFrame({
        "Empresa": ["A IDEAL SOLUÇÕES ANTICORROSIVAS LTDA"],
        "Relatório": ["Nenhum registro encontrado"],
    })

    result = FluxoCaixaValidator().validar_lote([
        _dados_fluxo(df_sem_movimentos, "RELATORIO DE MOVIMENTO SIMPLES itau isolamento.xls"),
    ])

    assert result.valido is False
    assert any(erro.campo == "arquivos" for erro in result.erros)
    assert any("Nenhum arquivo válido" in erro.mensagem for erro in result.erros)
