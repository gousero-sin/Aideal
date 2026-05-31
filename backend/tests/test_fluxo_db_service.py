"""Testes de persistência e geração do Fluxo de Caixa a partir do banco."""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.table import Table, TableStyleInfo

from app.contracts.persistence import FluxoMovimentoDB, FluxoUpload
from app.db.connection import DatabaseConnection
from app.db.manager import MigrationManager
from app.ingestao.fluxo_caixa_ingestao import FluxoCaixaIngestaoService
from app.processamento.fluxo_caixa_db import FluxoCaixaGeracaoService
from app.repository.fluxo_repository import FluxoCaixaRepository

HEADERS = [
    "Data",
    "Fornecedor",
    "Crédito",
    "Débito",
    "Saldo",
    "Classificação",
    "Ano",
    "C.M.",
    "Mês",
    "Banco",
    "Empresa",
]


def _novo_db() -> DatabaseConnection:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseConnection(tmp.name)
    MigrationManager(db).migrate()
    return db


def _criar_arquivo_fluxo(path: Path, mes: int = 8) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.append(["Relatório de movimentos financeiros"])
    ws.append(["Conta:", "BANCO ITAU"])
    ws.append([])
    ws.append(
        [
            "Data Mov.",
            "Tipo",
            "Desc. Mov.",
            "Valor (R$)",
            "Saldo (R$)",
            "Conta Gerencial Mov",
        ]
    )
    ws.append(
        [
            f"04/{mes:02d}/2025",
            "Crédito",
            "Recebimento Cliente",
            1000.0,
            1000.0,
            "Recebimento de Clientes",
        ]
    )
    ws.append(
        [
            f"05/{mes:02d}/2025",
            "Débito",
            "Pagamento Fornecedor",
            200.0,
            800.0,
            "Fornecedores",
        ]
    )
    wb.save(path)


def _criar_template_fluxo(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Consolidado"
    ws.append(HEADERS)
    ws.append(
        [
            date(2025, 7, 1),
            "linha antiga de julho",
            1,
            None,
            101,
            "Antiga",
            "=YEAR(A2)",
            "=MONTH(A2)",
            "=INDEX(mês[],Consolidado!H2,2)",
            "ITAU",
            "A IDEAL",
        ]
    )
    table = Table(displayName="FluxoConsol", ref="A1:K2")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)

    apoio = wb.create_sheet("Apoio")
    apoio["B5"] = "Rótulos de Linha"
    apoio["B6"] = "Recebimento de Clientes"
    apoio["B7"] = "Fornecedores"

    fluxo = wb.create_sheet("Fluxo de Caixa ")
    for idx, label in enumerate(
        [
            "JANEIRO",
            "FEVEREIRO",
            "MARÇO",
            "ABRIL",
            "MAIO",
            "JUNHO",
            "JULHO",
            "AGOSTO",
            "SETEMBRO",
            "OUTUBRO",
            "NOVEMBRO",
            "DEZEMBRO",
        ],
        start=4,
    ):
        fluxo.cell(row=5, column=idx, value=label)

    apresentacao = wb.create_sheet("Apresentação GMP")
    for idx, label in enumerate(
        ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
        start=3,
    ):
        apresentacao.cell(row=2, column=idx, value=label)

    wb.save(path)


def test_fluxo_salva_mes_no_banco_e_gera_somente_mes_selecionado(tmp_path):
    db = _novo_db()
    arquivo = tmp_path / "RELATORIO DE MOVIMENTO ITAU SISTEMA.xlsx"
    template = tmp_path / "template_fluxo.xlsx"
    _criar_arquivo_fluxo(arquivo, mes=8)
    _criar_template_fluxo(template)

    ingestao = FluxoCaixaIngestaoService(db)
    resultado_ingestao = ingestao.ingestar_lote(
        arquivos=[(arquivo, arquivo.name)],
        competencia="08/2025",
        replace=True,
    )

    assert resultado_ingestao["success"] is True
    assert resultado_ingestao["status"] == "completed"
    assert resultado_ingestao["inseridos"] == 2
    assert resultado_ingestao["meses_disponiveis_ano"] == [8]

    geracao = FluxoCaixaGeracaoService(
        db=db,
        template_path=template,
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        temp_dir=tmp_path / "tmp",
    )
    resultado_geracao = geracao.gerar_arquivo(
        competencia="08/2025",
        meses_incluir=[8],
    )

    assert resultado_geracao["fonte_dados"] == "db"
    assert resultado_geracao["meses_utilizados"] == [8]
    assert resultado_geracao["meses_ocultos"] == [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12]

    wb = load_workbook(resultado_geracao["output_path"], data_only=False)
    consolidado = wb["Consolidado"]
    meses_consolidado = {
        cell.value.month for cell in consolidado["A"][1:] if getattr(cell.value, "month", None)
    }
    assert meses_consolidado == {8}
    assert wb["Apresentação GMP"].column_dimensions["J"].hidden is False
    assert wb["Apresentação GMP"].column_dimensions["I"].hidden is True
    assert wb["Apresentação GMP"].column_dimensions["P"].hidden is True


def test_fluxo_atualiza_nome_gerencial_por_codigo_em_movimentos_passados():
    db = _novo_db()
    repo = FluxoCaixaRepository(db)

    upload_antigo = FluxoUpload(
        id=str(uuid4()),
        arquivo_nome="fluxo_05.xlsx",
        arquivo_sha256="hash_fluxo_nome_antigo",
        competencia_ano=2025,
        competencia_mes=5,
        banco="itau",
        status="completed",
    )
    movimento_antigo = FluxoMovimentoDB(
        upload_id=upload_antigo.id,
        competencia_ano=2025,
        competencia_mes=5,
        data_movimento="2025-05-10",
        tipo="debito",
        descricao="Conta antiga",
        valor=Decimal("100.00"),
        conta_gerencial="11.2 - AGUA ADM (100,00%);",
        banco_origem="itau",
        hash_linha="hash_fluxo_antigo",
    )
    repo.upsert_competencia([(upload_antigo, [movimento_antigo])])

    upload_novo = FluxoUpload(
        id=str(uuid4()),
        arquivo_nome="fluxo_06.xlsx",
        arquivo_sha256="hash_fluxo_nome_novo",
        competencia_ano=2025,
        competencia_mes=6,
        banco="itau",
    )
    movimento_novo = FluxoMovimentoDB(
        upload_id=upload_novo.id,
        competencia_ano=2025,
        competencia_mes=6,
        data_movimento="2025-06-10",
        tipo="debito",
        descricao="Conta nova",
        valor=Decimal("200.00"),
        conta_gerencial="11.2 - AGUA ADMINISTRATIVA (100,00%);",
        banco_origem="itau",
        hash_linha="hash_fluxo_novo",
    )
    repo.upsert_competencia([(upload_novo, [movimento_novo])])

    movimentos = repo.movimentos.get_by_meses(2025, [5, 6])
    assert [mov.conta_gerencial for mov in movimentos] == [
        "11.2 - AGUA ADMINISTRATIVA (100,00%);",
        "11.2 - AGUA ADMINISTRATIVA (100,00%);",
    ]
