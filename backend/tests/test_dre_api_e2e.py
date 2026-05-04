from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

import app.main as main_module
from app.processamento.dre import DREProcessamentoService


def _criar_arquivo_dre_cumulativo(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "RELATORIO"
    ws.append(["metadata"])
    ws.append(["Emissão", "Descri.", "Vlr.bruto (R$)", "CLASSIFICAÇÃO"])
    for mes in range(1, 6):
        ws.append(
            [
                f"01/{mes:02d}/2025",
                f"Lancamento {mes}",
                float(100 * mes),
                "1 - ENTRADA" if mes % 2 else "2 - SAIDA",
            ]
        )
    wb.save(path)


def test_api_dre_processamento_status_e_download(tmp_path, monkeypatch):
    service = DREProcessamentoService(
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        temp_dir=tmp_path / "tmp",
    )
    monkeypatch.setattr(main_module, "dre_service", service)

    client = TestClient(main_module.app)
    arquivo = tmp_path / "DRE_CUMULATIVO_01_A_05_2025.xlsx"
    _criar_arquivo_dre_cumulativo(arquivo)

    with open(arquivo, "rb") as fh:
        resp = client.post(
            "/api/processar/dre",
            files={
                "arquivo": (
                    arquivo.name,
                    fh,
                    "application/vnd.ms-excel",
                )
            },
            data={"competencia": "05/2025"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["id"]
    assert body["download_url"] == f"/api/processamentos/{body['id']}/download"

    status_resp = client.get(f"/api/processamentos/{body['id']}")
    assert status_resp.status_code == 200
    status_payload = status_resp.json()
    assert status_payload["id"] == body["id"]
    assert status_payload["status"] == "completed"
    assert status_payload["metadata"]["dre_periodo_meses_faltantes_ano_competencia"] == []

    download_resp = client.get(f"/api/processamentos/{body['id']}/download")
    assert download_resp.status_code == 200
    assert (
        download_resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(download_resp.content) > 1024


def test_api_dre_processamento_aceita_modo_nao_cumulativo(tmp_path, monkeypatch):
    service = DREProcessamentoService(
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        temp_dir=tmp_path / "tmp",
    )
    monkeypatch.setattr(main_module, "dre_service", service)

    client = TestClient(main_module.app)
    arquivo = main_module.settings.base_dir / "RELATORIO DRE MES 05.xls"

    with open(arquivo, "rb") as fh:
        resp = client.post(
            "/api/processar/dre",
            files={
                "arquivo": (
                    arquivo.name,
                    fh,
                    "application/vnd.ms-excel",
                )
            },
            data={"competencia": "05/2025", "modo_cumulativo": "false"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["metadata"]["dre_periodo_modo_cumulativo"] is False
