from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

import app.main as main_module
from app.processamento.fluxo_caixa import FluxoCaixaProcessamentoService


def _criar_arquivo_fluxo(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.append(["Relatório de movimentos financeiros"])
    ws.append(["Conta:", "BANCO"])
    ws.append([])
    ws.append([
        "Data Mov.",
        "Tipo",
        "Desc. Mov.",
        "Valor (R$)",
        "Saldo (R$)",
        "Conta Gerencial Mov",
    ])
    ws.append([
        "01/05/2025",
        "Crédito",
        "Recebimento Cliente",
        1000.0,
        1000.0,
        "Recebimento de Clientes",
    ])
    ws.append(["02/05/2025", "Débito", "Pagamento Fornecedor", 200.0, 800.0, "Fornecedores"])
    ws.append([
        "03/05/2025",
        "Transferência - BANCO SAFRA",
        "TRANSFERÊNCIA ENTRE BANCOS ITAÚ X SAFRA",
        300.0,
        500.0,
        "Transferência entre Bancos",
    ])
    wb.save(path)


def _criar_arquivo_contas_atraso(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.append([
        "Fornecedor",
        "Número",
        "Doc.",
        "Descri.",
        "Venc.",
        "C. gerencial",
        "Total líquido (R$)",
    ])
    ws.append([
        "PGFN",
        "",
        "001",
        "Parcelamento",
        "30/07/2025",
        "17.1 - PARCELAMENTO",
        1029.44,
    ])
    wb.save(path)


def test_api_fluxo_processamento_status_e_download(tmp_path, monkeypatch):
    service = FluxoCaixaProcessamentoService(
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        temp_dir=tmp_path / "tmp",
    )
    monkeypatch.setattr(main_module, "fluxo_service", service)

    client = TestClient(main_module.app)
    arquivo_itau = tmp_path / "RELATORIO DE MOVIMENTO ITAU SISTEMA.xlsx"
    arquivo_cef = tmp_path / "RELATORIO DE MOVIMENTO CAIXA SISTEMA.xlsx"
    _criar_arquivo_fluxo(arquivo_itau)
    _criar_arquivo_fluxo(arquivo_cef)

    with open(arquivo_itau, "rb") as f1, open(arquivo_cef, "rb") as f2:
        resp = client.post(
            "/api/processar/fluxo_caixa",
            files=[
                (
                    "arquivos",
                    (
                        arquivo_itau.name,
                        f1,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                (
                    "arquivos",
                    (
                        arquivo_cef.name,
                        f2,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
            ],
            data={"periodo": "05/2025"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["fluxo"] == "fluxo_caixa"
    assert body["total_registros"] == 6
    assert body["download_url"] == f"/api/processamentos/{body['id']}/download"

    status_resp = client.get(f"/api/processamentos/{body['id']}")
    assert status_resp.status_code == 200
    status_payload = status_resp.json()
    assert status_payload["id"] == body["id"]
    assert status_payload["status"] == "completed"
    assert sorted(status_payload["metadata"]["bancos_identificados"]) == ["cef", "itau"]

    download_resp = client.get(f"/api/processamentos/{body['id']}/download")
    assert download_resp.status_code == 200
    assert (
        download_resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(download_resp.content) > 1024


def test_api_fluxo_gerar_alias(tmp_path, monkeypatch):
    service = FluxoCaixaProcessamentoService(
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        temp_dir=tmp_path / "tmp",
    )
    monkeypatch.setattr(main_module, "fluxo_service", service)

    client = TestClient(main_module.app)
    arquivo = tmp_path / "RELATORIO DE MOVIMENTO ITAU SISTEMA.xlsx"
    _criar_arquivo_fluxo(arquivo)

    with open(arquivo, "rb") as fh:
        resp = client.post(
            "/api/fluxo_caixa/gerar",
            files=[
                (
                    "arquivos",
                    (
                        arquivo.name,
                        fh,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
            ],
            data={"periodo": "05/2025"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["fluxo"] == "fluxo_caixa"
    assert body["total_registros"] == 3


def test_api_fluxo_ignora_arquivo_nao_bancario_sem_bloquear_lote(tmp_path, monkeypatch):
    service = FluxoCaixaProcessamentoService(
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        temp_dir=tmp_path / "tmp",
    )
    monkeypatch.setattr(main_module, "fluxo_service", service)

    client = TestClient(main_module.app)
    arquivo_fluxo = tmp_path / "RELATORIO DE MOVIMENTO ITAU SISTEMA.xlsx"
    arquivo_apoio = tmp_path / "RELATORIO DE CONTAS EM ATRASO MES 07.xlsx"
    _criar_arquivo_fluxo(arquivo_fluxo)
    _criar_arquivo_contas_atraso(arquivo_apoio)

    with open(arquivo_fluxo, "rb") as f1, open(arquivo_apoio, "rb") as f2:
        resp = client.post(
            "/api/fluxo_caixa/gerar",
            files=[
                (
                    "arquivos",
                    (
                        arquivo_fluxo.name,
                        f1,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                (
                    "arquivos",
                    (
                        arquivo_apoio.name,
                        f2,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
            ],
            data={"periodo": "07/2025"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["total_registros"] == 3

    ignored = body.get("metadata", {}).get("arquivos_ignorados", [])
    assert len(ignored) == 1
    assert ignored[0]["arquivo"] == arquivo_apoio.name


class _FakeFluxoGeracaoDBService:
    def __init__(self):
        self.verificar_args = None
        self.gerar_args = None

    def verificar_dados(self, competencia, meses_incluir=None, ano_todo=False):
        self.verificar_args = {
            "competencia": competencia,
            "meses_incluir": meses_incluir,
            "ano_todo": ano_todo,
        }
        return {
            "valido": True,
            "competencia": competencia,
            "meses_utilizados": meses_incluir or [8],
        }

    def gerar_arquivo(self, competencia, meses_incluir=None, ano_todo=False):
        self.gerar_args = {
            "competencia": competencia,
            "meses_incluir": meses_incluir,
            "ano_todo": ano_todo,
        }
        return {
            "arquivo_saida": "AIDEAL_Fluxo_Caixa_08-2025_teste.xlsx",
            "output_path": "/tmp/AIDEAL_Fluxo_Caixa_08-2025_teste.xlsx",
            "total_movimentos": 2,
            "total_creditos": 1000.0,
            "total_debitos": 200.0,
            "saldo_liquido": 800.0,
            "fonte_dados": "db",
            "estrategia_meses": "meses_incluir",
            "ano_todo": ano_todo,
            "meses_incluir": meses_incluir or [],
            "meses_disponiveis": [7, 8],
            "meses_utilizados": meses_incluir or [8],
            "meses_solicitados": meses_incluir or [8],
            "meses_ocultos": [1, 2, 3, 4, 5, 6, 9, 10, 11, 12],
        }


def test_api_fluxo_gerar_do_banco_recebe_flags_de_meses(monkeypatch):
    fake_service = _FakeFluxoGeracaoDBService()
    monkeypatch.setattr(main_module, "fluxo_geracao_db_service", fake_service)
    client = TestClient(main_module.app)

    resp = client.post(
        "/api/fluxo_caixa/gerar",
        data={
            "competencia": "08/2025",
            "meses_incluir": ["8"],
            "ano_todo": "false",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["fonte_dados"] == "db"
    assert body["total_lancamentos"] == 2
    assert body["meses_utilizados"] == [8]
    assert fake_service.verificar_args["meses_incluir"] == [8]
    assert fake_service.gerar_args["meses_incluir"] == [8]
