"""Os atalhos de desempenho dos painéis devem dar o mesmo resultado do caminho original."""

from __future__ import annotations

import itertools

import pytest

from app.config import settings
from app.processamento.dre_geracao_completa import DREGeracaoCompletaService
from app.processamento.paineis import PainelDREService, _row_dre_matches_memo
from app.templates.writer import TemplateWriter


def _plano(rapido: bool) -> dict:
    with TemplateWriter(settings.template_dre_path, ler_pivots_uma_vez=rapido) as writer:
        return DREGeracaoCompletaService._ler_plano_contas(
            writer, aplicar_overrides_dre_gerado=True
        )


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_leitura_rapida_do_template_preserva_plano_de_contas():
    assert _plano(rapido=True) == _plano(rapido=False)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_leitura_rapida_le_pivots_uma_vez_e_preserva_as_tabelas():
    normal = TemplateWriter(settings.template_dre_path)
    rapido = TemplateWriter(settings.template_dre_path, ler_pivots_uma_vez=True)
    normal.abrir()
    rapido.abrir()
    try:
        assert rapido._wb.sheetnames == normal._wb.sheetnames
        for nome in normal._wb.sheetnames:
            pivots_normais = normal._wb[nome]._pivots
            pivots_rapidos = rapido._wb[nome]._pivots
            assert [p.cacheId for p in pivots_rapidos] == [p.cacheId for p in pivots_normais]
            assert [p.cache for p in pivots_rapidos] == [p.cache for p in pivots_normais]
    finally:
        normal.fechar()
        rapido.fechar()


# Códigos de conta e nomes reais do PLANO_CONTAS cobrindo receita (1.1.x),
# deduções, custos, investimentos e linhas sem código.
_CODIGOS = [None, "1.1.01", "1.2.01", "2.1.01", "3.1.02", "4.2.01", "6.1.01"]
_TEXTOS = [None, "Receita Bruta", "Deduções", "Custos Variáveis", "Investimentos", "Marketing"]
_PAIS = [None, "Receita Bruta", "Gastos Fixos", "Resultado Financeiro", "Investimentos"]


@pytest.mark.parametrize("componente", sorted(PainelDREService.COMPONENTES_DRE))
def test_match_memoizado_igual_ao_calculo_direto(componente):
    aliases = PainelDREService.COMPONENTES_DRE[componente]
    _row_dre_matches_memo.cache_clear()
    for codigo, texto, pai, resolvido in itertools.product(
        _CODIGOS, _TEXTOS, _PAIS, (False, True)
    ):
        row = {
            "codigo_conta": codigo,
            "natureza_raw": texto,
            "rubrica": texto,
            "conta_filho": texto,
            "conta_pai": pai,
            "natureza_norm": texto,
            "_plano_contas_resolvido": resolvido,
            "credito": 10.0,
            "debito": 0.0,
        }
        esperado = PainelDREService._row_dre_matches_calcular(row, aliases, componente)
        assert PainelDREService._row_dre_matches(row, aliases, componente) is esperado
        # Segunda chamada vem do cache e continua igual.
        assert PainelDREService._row_dre_matches(row, aliases, componente) is esperado


def test_match_com_aliases_customizados_nao_usa_cache():
    _row_dre_matches_memo.cache_clear()
    row = {"conta_pai": "Marketing", "codigo_conta": None}
    assert PainelDREService._row_dre_matches(row, {"marketing"}, "gastos_fixos") in (True, False)
    assert _row_dre_matches_memo.cache_info().currsize == 0
