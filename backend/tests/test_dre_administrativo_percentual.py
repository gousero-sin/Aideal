"""Percentuais do DRE gerado somente para a obra ADMINISTRATIVO.

A ADMINISTRATIVO é centro de custo de apoio: não fatura (nenhum lançamento
1.1.x). Todo percentual do DRE divide pela receita do período, então sem
receita não existe base. Centavos de imposto lançados em contas que não são
receita (ex.: juros 1.2.3 com ISS/INSS/PIS/COFINS) deixavam a Receita Líquida
em -0,02 e geravam percentuais de bilhões. Para a ADM, sem Receita Bruta no
período, a coluna de % fica vazia.
"""

import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from app.config import settings
from app.contracts.persistence import DRELancamentoDB, DREUpload
from app.db.connection import DatabaseConnection
from app.db.manager import MigrationManager
from app.processamento.dre_geracao_completa import (
    DREGeracaoCompletaService,
    _eh_somente_administrativo,
)
from app.repository.dre_repository import DRERepository
from app.templates.writer import TemplateWriter

_ADM = "ADMINISTRATIVO"
_PRIMEIRA_LINHA_DRE = 6
# Colunas do template: Jan = B (valor) / C (%); Jul = R / S; ANO = AH / AI.
_COLUNAS_PERCENTUAL_JULHO_E_ANO = ("S", "AI")


def _novo_service() -> tuple[DREGeracaoCompletaService, DRERepository]:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseConnection(tmp.name)
    MigrationManager(db).migrate()
    return DREGeracaoCompletaService(db), DRERepository(db)


def _plano(service: DREGeracaoCompletaService) -> dict:
    with TemplateWriter(settings.template_dre_path) as writer:
        return service._ler_plano_contas(writer, aplicar_overrides_dre_gerado=True)


def _copiar_template(tmp_path: Path) -> Path:
    destino = tmp_path / "template_dre_adm.xlsx"
    shutil.copyfile(settings.template_dre_path, destino)
    return destino


def _linha_por_rotulo(ws, rotulo: str) -> int:
    # O arquivo gerado sai com rótulos em caixa alta (dre_apresentacao); o
    # template não. Comparar sem caixa, como o _normalizar_rotulo do serviço.
    alvo = rotulo.casefold()
    for linha in range(1, ws.max_row + 1):
        valor = ws.cell(linha, 1).value
        if isinstance(valor, str) and valor.casefold() == alvo:
            return linha
    raise AssertionError(f"Rótulo DRE ausente: {rotulo}")


def _lanc(
    *,
    mes: int,
    historico: str,
    natureza: str,
    centro_custo: str,
    credito: str = "0",
    debito: str = "0",
    valor_bruto: str = "0",
    rubrica: str | None = None,
) -> DRELancamentoDB:
    return DRELancamentoDB(
        upload_id="u-adm",
        competencia_ano=2026,
        competencia_mes=mes,
        data_lancamento=f"2026-{mes:02d}-13",
        historico=historico,
        valor_bruto=Decimal(valor_bruto),
        credito=Decimal(credito),
        debito=Decimal(debito),
        natureza_raw=natureza,
        rubrica=rubrica,
        centro_custo=centro_custo,
        hash_linha=f"h-{uuid4()}",
    )


def _lancamentos_julho_sem_receita(centro_custo: str) -> list[DRELancamentoDB]:
    """Reproduz julho/2026 da ADM: juros de R$ 0,01 vindos do ERP com impostos."""
    base = {"mes": 7, "historico": "AIDEAL SOLUÇÕES ANTICORROSIVAS", "centro_custo": centro_custo}
    return [
        _lanc(
            **base, natureza="1.2.3 - Origens Financeiras", credito="0.00847", valor_bruto="0.01"
        ),
        _lanc(**base, natureza="ISS", debito="0.0005", rubrica="ISS"),
        _lanc(**base, natureza="INSS", debito="0.00035", rubrica="INSS"),
        _lanc(**base, natureza="PIS", debito="0.000065", rubrica="PIS"),
        _lanc(**base, natureza="COFINS", debito="0.0003", rubrica="COFINS"),
        _lanc(
            mes=7,
            historico="Papelaria",
            natureza="8.10 - MATERIAS DE ESCRITORIO",
            centro_custo=centro_custo,
            debito="342137.87",
        ),
    ]


def _materializar(
    tmp_path: Path,
    lancamentos: list[DRELancamentoDB],
    *,
    somente_administrativo: bool,
):
    service, _ = _novo_service()
    plano = _plano(service)
    writer = TemplateWriter(_copiar_template(tmp_path))
    writer.__enter__()
    service._escrever_apoio(writer, lancamentos, plano)
    service._materializar_dre(writer, somente_administrativo=somente_administrativo)
    return writer


class TestEhSomenteAdministrativo:
    def test_todos_os_lancamentos_da_adm(self):
        lancs = _lancamentos_julho_sem_receita(_ADM)
        assert _eh_somente_administrativo(lancs) is True

    def test_grafia_diferente_ainda_e_adm(self):
        lancs = _lancamentos_julho_sem_receita(" Administrativo ")
        assert _eh_somente_administrativo(lancs) is True

    def test_mistura_com_outra_obra_nao_e_somente_adm(self):
        lancs = _lancamentos_julho_sem_receita(_ADM) + _lancamentos_julho_sem_receita("OBRA A")
        assert _eh_somente_administrativo(lancs) is False

    def test_lista_vazia_nao_e_adm(self):
        assert _eh_somente_administrativo([]) is False


class TestMaterializarPercentualAdministrativo:
    def test_adm_sem_receita_deixa_percentual_vazio_e_preserva_valores(self, tmp_path):
        writer = _materializar(
            tmp_path, _lancamentos_julho_sem_receita(_ADM), somente_administrativo=True
        )
        try:
            ws = writer._wb["DRE"]
            linha_gastos = _linha_por_rotulo(ws, "(-)Gastos Fixos")
            linha_receita_liquida = _linha_por_rotulo(ws, "(=)Receita Líquida")

            # Os valores em R$ continuam no DRE, inclusive os centavos de dedução
            # que antes viravam base dos percentuais.
            assert ws[f"R{linha_gastos}"].value == pytest.approx(-342137.87, abs=1)
            assert ws[f"R{linha_receita_liquida}"].value == pytest.approx(-0.001215)

            for coluna in _COLUNAS_PERCENTUAL_JULHO_E_ANO:
                preenchidas = {
                    linha: ws[f"{coluna}{linha}"].value
                    for linha in range(_PRIMEIRA_LINHA_DRE, ws.max_row + 1)
                    if ws[f"{coluna}{linha}"].value is not None
                }
                assert preenchidas == {}, f"%{coluna} deveria ficar vazio na ADM sem receita"
        finally:
            writer.__exit__(None, None, None)

    def test_adm_com_receita_calcula_percentual_normalmente(self, tmp_path):
        lancamentos = [
            _lanc(
                mes=1,
                historico="Nota de serviço",
                natureza="1.1.1 - Recebimento de Clientes",
                centro_custo=_ADM,
                credito="1000",
                valor_bruto="1000",
            ),
            _lanc(
                mes=1,
                historico="Papelaria",
                natureza="8.10 - MATERIAS DE ESCRITORIO",
                centro_custo=_ADM,
                debito="100",
            ),
        ]
        writer = _materializar(tmp_path, lancamentos, somente_administrativo=True)
        try:
            ws = writer._wb["DRE"]
            linha_gastos = _linha_por_rotulo(ws, "(-)Gastos Fixos")
            assert ws[f"C{linha_gastos}"].value == pytest.approx(-0.1)
        finally:
            writer.__exit__(None, None, None)

    def test_adm_com_receita_so_em_alguns_meses(self, tmp_path):
        lancamentos = [
            _lanc(
                mes=1,
                historico="Nota de serviço",
                natureza="1.1.1 - Recebimento de Clientes",
                centro_custo=_ADM,
                credito="1000",
                valor_bruto="1000",
            ),
            _lanc(
                mes=1,
                historico="Papelaria",
                natureza="8.10 - MATERIAS DE ESCRITORIO",
                centro_custo=_ADM,
                debito="100",
            ),
            *_lancamentos_julho_sem_receita(_ADM),
        ]
        writer = _materializar(tmp_path, lancamentos, somente_administrativo=True)
        try:
            ws = writer._wb["DRE"]
            linha_gastos = _linha_por_rotulo(ws, "(-)Gastos Fixos")
            # Jan (C) e 1º trimestre (I) têm receita: % calculado.
            assert ws[f"C{linha_gastos}"].value == pytest.approx(-0.1)
            assert ws[f"I{linha_gastos}"].value == pytest.approx(-0.1)
            # Jul (S) e 3º trimestre (Y) sem receita: % vazio.
            assert ws[f"S{linha_gastos}"].value is None
            assert ws[f"Y{linha_gastos}"].value is None
            # O ano tem receita (Jan), então o %ANO é calculado sobre ela.
            receita_liquida_ano = ws[f"AH{_linha_por_rotulo(ws, '(=)Receita Líquida')}"].value
            assert ws[f"AI{linha_gastos}"].value == pytest.approx(
                ws[f"AH{linha_gastos}"].value / receita_liquida_ano
            )
        finally:
            writer.__exit__(None, None, None)

    def test_outra_obra_mantem_regra_do_template(self, tmp_path):
        writer = _materializar(
            tmp_path, _lancamentos_julho_sem_receita("OBRA A"), somente_administrativo=False
        )
        try:
            ws = writer._wb["DRE"]
            linha_gastos = _linha_por_rotulo(ws, "(-)Gastos Fixos")
            receita_liquida = ws[f"R{_linha_por_rotulo(ws, '(=)Receita Líquida')}"].value
            # Fora da ADM nada muda: valor ÷ Receita Líquida, como no template.
            assert ws[f"S{linha_gastos}"].value == pytest.approx(
                ws[f"R{linha_gastos}"].value / receita_liquida
            )
        finally:
            writer.__exit__(None, None, None)


def test_gerar_arquivo_filtrado_pela_adm_sai_sem_percentual_sem_receita(tmp_path):
    service, repo = _novo_service()
    upload = DREUpload(
        id=str(uuid4()),
        arquivo_nome="07_2026.xls",
        arquivo_sha256="hash-adm-07",
        competencia_ano=2026,
        competencia_mes=7,
        status="completed",
    )
    repo.uploads.create(upload)
    for lanc in _lancamentos_julho_sem_receita(_ADM):
        repo.lancamentos.create(lanc.model_copy(update={"upload_id": upload.id}))

    saida = tmp_path / "dre_adm.xlsx"
    service.gerar_arquivo("07/2026", centro_custo="adm", output_path=saida)

    ws = load_workbook(saida)["DRE"]
    linha_gastos = _linha_por_rotulo(ws, "(-)Gastos Fixos")
    assert ws[f"R{linha_gastos}"].value == pytest.approx(-342137.87, abs=1)
    assert ws[f"S{linha_gastos}"].value is None
    assert ws[f"AI{linha_gastos}"].value is None
