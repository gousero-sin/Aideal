"""Testes do serviço de ingestão DRE."""

import tempfile
from pathlib import Path

from openpyxl import Workbook

from app.db.connection import DatabaseConnection
from app.db.manager import MigrationManager
from app.ingestao.dre_ingestao import DREIngestaoService


def _criar_relatorio_mes(path: Path, mes: int, ano: int = 2025) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "RELATORIO"
    ws.append(["metadata"])
    ws.append(["Emissão", "Descri.", "Vlr.bruto (R$)", "CLASSIFICAÇÃO"])
    ws.append([f"01/{mes:02d}/{ano}", f"Lancamento {mes}", 100.0, "1 - ENTRADA"])
    wb.save(path)


def _novo_servico() -> DREIngestaoService:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseConnection(tmp.name)
    MigrationManager(db).migrate()
    return DREIngestaoService(db)


def test_ingestao_nao_bloqueia_hash_repetido_em_outra_competencia(tmp_path):
    """Mesmo hash em competência diferente não deve retornar already_processed."""
    service = _novo_servico()
    arquivo = tmp_path / "relatorio_mes_06.xlsx"
    _criar_relatorio_mes(arquivo, mes=6, ano=2025)

    result_ok = service.ingestar(
        arquivo_path=arquivo,
        arquivo_nome=arquivo.name,
        competencia="06/2025",
        replace=True,
    )
    assert result_ok["success"] is True
    assert result_ok["status"] == "completed"

    # Mesmo arquivo (mesmo hash), competência diferente: deve processar com sucesso.
    # A competência é definida pelo upload, não pela data de emissão das linhas;
    # relatórios mensais podem conter linhas com data no mês seguinte.
    result_outro_mes = service.ingestar(
        arquivo_path=arquivo,
        arquivo_nome=arquivo.name,
        competencia="07/2025",
        replace=True,
    )
    assert result_outro_mes["success"] is True
    assert result_outro_mes["status"] == "completed"
    assert result_outro_mes["competencia_salva"] == "07/2025"


def test_ingestao_persiste_linhas_com_data_fora_da_competencia(tmp_path):
    """Linhas com data de emissão em mês diferente devem ser mantidas no upload."""
    service = _novo_servico()
    arquivo = tmp_path / "relatorio_mes_05.xlsx"
    # Relatório de maio mas com linha datada de junho (caso VLI MULTIMODAL real).
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "RELATORIO"
    ws.append(["metadata"])
    ws.append(["Emissão", "Descri.", "Vlr.bruto (R$)", "CLASSIFICAÇÃO"])
    ws.append(["15/05/2025", "Recebimento maio", 100.0, "1 - ENTRADA"])
    ws.append(["02/06/2025", "Recebimento tardio", 612659.54, "1 - ENTRADA"])
    wb.save(arquivo)

    result = service.ingestar(
        arquivo_path=arquivo,
        arquivo_nome=arquivo.name,
        competencia="05/2025",
        replace=True,
    )
    assert result["success"] is True
    assert result["inseridos"] == 2
    assert result["linhas_outro_mes"] == 0  # não rejeitamos mais por data
