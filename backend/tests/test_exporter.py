"""Testes para Exporter (exportacao/exporter.py)."""

from app.contracts.common import FlowType, ProcessingStatus
from app.exportacao.exporter import Exporter


class TestExporterCriarLog:
    def test_cria_log_com_id(self, tmp_path):
        exp = Exporter(
            logs_dir=tmp_path / "logs", temp_dir=tmp_path / "tmp", output_dir=tmp_path / "out"
        )
        log = exp.criar_log(FlowType.DRE, ["arquivo.xls"])
        assert log.id
        assert log.fluxo == FlowType.DRE
        assert log.status == ProcessingStatus.PENDING
        assert "arquivo.xls" in log.arquivo_entrada


class TestExporterNomeSaida:
    def test_nome_contem_tipo_e_competencia(self, tmp_path):
        exp = Exporter(logs_dir=tmp_path / "l", temp_dir=tmp_path / "t", output_dir=tmp_path / "o")
        nome = exp.gerar_nome_saida(FlowType.DRE, "05-2025")
        assert "DRE" in nome
        assert "05-2025" in nome
        assert nome.endswith(".xlsx")

    def test_nome_fluxo_caixa(self, tmp_path):
        exp = Exporter(logs_dir=tmp_path / "l", temp_dir=tmp_path / "t", output_dir=tmp_path / "o")
        nome = exp.gerar_nome_saida(FlowType.FLUXO_CAIXA, "07-2025")
        assert "Fluxo_Caixa" in nome


class TestExporterSalvarCarregar:
    def test_salvar_e_carregar_log(self, tmp_path):
        exp = Exporter(
            logs_dir=tmp_path / "logs", temp_dir=tmp_path / "tmp", output_dir=tmp_path / "out"
        )
        log = exp.criar_log(FlowType.DRE, ["input.xls"])
        log.finalizar(ProcessingStatus.COMPLETED, arquivo_saida="output.xlsx")
        log.total_registros = 42

        exp.salvar_log(log)
        loaded = exp.carregar_log(log.id)

        assert loaded is not None
        assert loaded.id == log.id
        assert loaded.status == ProcessingStatus.COMPLETED
        assert loaded.total_registros == 42
        assert loaded.arquivo_saida == "output.xlsx"

    def test_carregar_log_inexistente(self, tmp_path):
        exp = Exporter(
            logs_dir=tmp_path / "logs", temp_dir=tmp_path / "tmp", output_dir=tmp_path / "out"
        )
        assert exp.carregar_log("id_que_nao_existe") is None


class TestExporterLimpeza:
    def test_limpar_temporarios(self, tmp_path):
        temp = tmp_path / "tmp"
        temp.mkdir()
        (temp / "file1.tmp").write_text("x")
        (temp / "file2.tmp").write_text("y")

        exp = Exporter(logs_dir=tmp_path / "logs", temp_dir=temp, output_dir=tmp_path / "out")
        count = exp.limpar_temporarios()
        assert count == 2
        assert list(temp.iterdir()) == []
