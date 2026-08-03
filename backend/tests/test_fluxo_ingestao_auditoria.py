"""Regressões de auditoria para ingestão e conciliação do Fluxo de Caixa."""

import hashlib
import tempfile
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from openpyxl import Workbook

from app.contracts.persistence import FluxoMovimentoDB, FluxoUpload
from app.db.connection import DatabaseConnection
from app.db.manager import MigrationManager
from app.ingestao.fluxo_caixa_ingestao import FluxoCaixaIngestaoService
from app.processamento.fluxo_caixa_db import FluxoCaixaGeracaoService


def _novo_db() -> DatabaseConnection:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseConnection(tmp.name)
    MigrationManager(db).migrate()
    return db


def _criar_extrato(path: Path, linhas: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Resultado da consulta"
    ws.append(
        [
            "Data Mov.",
            "Tipo",
            "Descrição",
            "Valor",
            "Saldo",
            "Cód. Conta Gerencial",
            "Conta Gerencial",
        ]
    )
    for linha in linhas:
        ws.append(linha)
    wb.save(path)


def test_reupload_de_um_banco_preserva_outros_bancos_da_competencia(tmp_path):
    db = _novo_db()
    archive_dir = tmp_path / "archive"
    service = FluxoCaixaIngestaoService(db, archive_dir=archive_dir)
    itau = tmp_path / "movimentos_2025-08_itau_.xlsx"
    mercantil = tmp_path / "movimentos_2025-08_mercantil_.xlsx"
    _criar_extrato(
        itau,
        [["04/08/2025", "Crédito", "Cliente Itaú", 100.0, 100.0, "1.1.1", "Clientes"]],
    )
    _criar_extrato(
        mercantil,
        [
            [
                "04/08/2025",
                "Crédito",
                "Cliente Mercantil",
                200.0,
                200.0,
                "1.1.1",
                "Clientes",
            ]
        ],
    )

    inicial = service.ingestar_lote(
        [(itau, itau.name), (mercantil, mercantil.name)],
        competencia="08/2025",
        replace=True,
    )
    assert inicial["success"] is True

    _criar_extrato(
        itau,
        [["04/08/2025", "Crédito", "Cliente Itaú corrigido", 150.0, 150.0, "1.1.1", "Clientes"]],
    )
    reupload = service.ingestar_lote(
        [(itau, itau.name)],
        competencia="08/2025",
        replace=True,
    )

    uploads = service.repository.uploads.get_by_competencia(2025, 8)
    movimentos = service.repository.movimentos.get_by_meses(2025, [8])
    assert reupload["success"] is True
    assert reupload["escopo_substituicao"] == "bancos"
    assert reupload["removidos"] == 1
    assert {upload.banco for upload in uploads} == {"itau", "mercantil"}
    assert {(mov.banco_origem, mov.valor) for mov in movimentos} == {
        ("itau", 150),
        ("mercantil", 200),
    }


def test_reupload_remove_versao_legada_do_banco_gravada_como_desconhecido(tmp_path):
    db = _novo_db()
    service = FluxoCaixaIngestaoService(db, archive_dir=tmp_path / "archive")
    arquivo = tmp_path / "movimentos_2025-08_caixa_.xlsx"
    upload_id = str(uuid4())
    upload_legado = FluxoUpload(
        id=upload_id,
        arquivo_nome=arquivo.name,
        arquivo_sha256="hash-legado-caixa",
        competencia_ano=2025,
        competencia_mes=8,
        banco="desconhecido",
        status="completed",
        total_linhas=1,
        linhas_validas=1,
    )
    movimento_legado = FluxoMovimentoDB(
        upload_id=upload_id,
        competencia_ano=2025,
        competencia_mes=8,
        data_movimento="2025-08-04",
        tipo="credito",
        descricao="Cliente legado",
        valor=Decimal("100"),
        saldo=Decimal("100"),
        classificacao="1.1.1 - Clientes",
        conta_gerencial="1.1.1 - Clientes",
        banco_origem="desconhecido",
        arquivo_origem=arquivo.name,
        hash_linha="hash-linha-legada-caixa",
    )
    service.repository.upsert_competencia([(upload_legado, [movimento_legado])])

    _criar_extrato(
        arquivo,
        [["04/08/2025", "Crédito", "Cliente corrigido", 150.0, 150.0, "1.1.1", "Clientes"]],
    )
    resultado = service.ingestar_lote(
        [(arquivo, arquivo.name)],
        competencia="08/2025",
        replace=True,
    )

    uploads = service.repository.uploads.get_by_competencia(2025, 8)
    movimentos = service.repository.movimentos.get_by_meses(2025, [8])
    assert resultado["success"] is True
    assert resultado["removidos"] == 1
    assert len(uploads) == 1
    assert uploads[0].banco == "cef"
    assert [(mov.banco_origem, mov.valor) for mov in movimentos] == [("cef", 150)]


def test_ingestao_bloqueia_nome_de_arquivo_com_competencia_divergente(tmp_path):
    db = _novo_db()
    service = FluxoCaixaIngestaoService(db, archive_dir=tmp_path / "archive")
    arquivo = tmp_path / "movimentos_2025-09_itau_.xlsx"
    _criar_extrato(
        arquivo,
        [["04/08/2025", "Crédito", "Cliente", 100.0, 100.0, "1.1.1", "Clientes"]],
    )

    resultado = service.ingestar_lote(
        [(arquivo, arquivo.name)],
        competencia="08/2025",
        replace=True,
    )

    assert resultado["success"] is False
    assert resultado["status"] == "validation_error"
    assert "09/2025" in resultado["error"]
    assert "08/2025" in resultado["error"]
    assert service.repository.uploads.get_by_competencia(2025, 8) == []


def test_ingestao_bloqueia_nome_de_exportacao_com_competencia_malformada(tmp_path):
    db = _novo_db()
    service = FluxoCaixaIngestaoService(db, archive_dir=tmp_path / "archive")
    arquivo = tmp_path / "movimentos_2025-083_caixa_.xlsx"
    _criar_extrato(
        arquivo,
        [["04/08/2025", "Crédito", "Cliente", 100.0, 100.0, "1.1.1", "Clientes"]],
    )

    resultado = service.ingestar_lote(
        [(arquivo, arquivo.name)],
        competencia="08/2025",
        replace=True,
    )

    assert resultado["success"] is False
    assert resultado["status"] == "validation_error"
    assert "nome malformado" in resultado["error"].lower()
    assert service.repository.uploads.get_by_competencia(2025, 8) == []


def test_ingestao_arquiva_fonte_original_por_hash(tmp_path):
    db = _novo_db()
    service = FluxoCaixaIngestaoService(db, archive_dir=tmp_path / "archive")
    arquivo = tmp_path / "movimentos_2025-08_itau_.xlsx"
    _criar_extrato(
        arquivo,
        [["04/08/2025", "Crédito", "Cliente", 100.0, 100.0, "1.1.1", "Clientes"]],
    )

    resultado = service.ingestar_lote(
        [(arquivo, arquivo.name)],
        competencia="08/2025",
        replace=True,
    )

    arquivado = Path(resultado["arquivos_arquivados"][0]["caminho"])
    assert arquivado.exists()
    assert hashlib.sha256(arquivado.read_bytes()).hexdigest() == hashlib.sha256(
        arquivo.read_bytes()
    ).hexdigest()


def test_transferencia_sem_contrapartida_e_sinalizada_mas_permanece_neutra(tmp_path):
    db = _novo_db()
    service = FluxoCaixaIngestaoService(db, archive_dir=tmp_path / "archive")
    arquivo = tmp_path / "movimentos_2025-08_itau_.xlsx"
    _criar_extrato(
        arquivo,
        [
            [
                "04/08/2025",
                "Crédito",
                "TRANSFERÊNCIA ENTRE BANCOS CEF X ITAÚ",
                100000.0,
                100000.0,
                "2.1",
                "Transferência entre Bancos",
            ]
        ],
    )

    resultado = service.ingestar_lote(
        [(arquivo, arquivo.name)],
        competencia="08/2025",
        replace=True,
    )

    conciliacao = resultado["conciliacao_transferencias"]
    assert resultado["success"] is True
    assert conciliacao["nao_pareadas"] == 1
    assert conciliacao["diferenca_recebidas_emitidas"] == 100000.0
    assert conciliacao["impacta_saldo_financeiro"] is False
    assert any("contrapartida" in warning["mensagem"].lower() for warning in resultado["warnings"])


def test_transferencia_caixa_itau_e_pareada_com_direcao_correta(tmp_path):
    db = _novo_db()
    service = FluxoCaixaIngestaoService(db, archive_dir=tmp_path / "archive")
    caixa = tmp_path / "movimentos_2025-08_caixa_.xlsx"
    itau = tmp_path / "movimentos_2025-08_itau_.xlsx"
    _criar_extrato(
        caixa,
        [
            [
                "04/08/2025",
                "Transferência",
                "TRANSFERÊNCIA ENTRE BANCOS CAIXA X ITAU",
                500000.0,
                0.0,
                "2.1",
                "Transferência entre Bancos",
            ]
        ],
    )
    _criar_extrato(
        itau,
        [
            [
                "04/08/2025",
                "Crédito",
                "TRANSFERÊNCIA ENTRE BANCOS CAIXA X ITAU",
                500000.0,
                500000.0,
                "2.1",
                "Transferência entre Bancos",
            ]
        ],
    )

    resultado = service.ingestar_lote(
        [(caixa, caixa.name), (itau, itau.name)],
        competencia="08/2025",
        replace=True,
    )

    movimentos = service.repository.movimentos.get_by_meses(2025, [8])
    movimento_caixa = next(mov for mov in movimentos if mov.banco_origem == "cef")
    assert resultado["conciliacao_transferencias"]["pares"] == 1
    assert resultado["conciliacao_transferencias"]["nao_pareadas"] == 0
    assert movimento_caixa.classificacao == "Transferência Emitida"


def test_ano_todo_bloqueia_lacuna_entre_janeiro_e_competencia(tmp_path):
    db = _novo_db()
    service = FluxoCaixaIngestaoService(db, archive_dir=tmp_path / "archive")
    for mes in (1, 3):
        arquivo = tmp_path / f"movimentos_2025-{mes:02d}_itau_.xlsx"
        _criar_extrato(
            arquivo,
            [
                [
                    f"04/{mes:02d}/2025",
                    "Crédito",
                    f"Cliente {mes}",
                    100.0,
                    100.0,
                    "1.1.1",
                    "Clientes",
                ]
            ],
        )
        assert service.ingestar_lote(
            [(arquivo, arquivo.name)],
            competencia=f"{mes:02d}/2025",
            replace=True,
        )["success"]

    verificacao = FluxoCaixaGeracaoService(db).verificar_dados(
        "03/2025",
        ano_todo=True,
    )

    assert verificacao["valido"] is False
    assert verificacao["meses_faltantes"] == [2]
