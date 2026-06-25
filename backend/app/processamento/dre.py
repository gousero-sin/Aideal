"""Servico de processamento ponta a ponta do fluxo DRE."""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from ..config import settings
from ..contracts.common import ErrorSeverity, FlowType, ProcessingLog, ProcessingStatus
from ..contracts.dre import DRELote
from ..contracts.persistence import DRELancamentoDB, DREUpload
from ..contracts.processamento import DREProcessamentoResponse
from ..db.connection import DatabaseConnection
from ..db.manager import run_migrations
from ..exportacao.exporter import Exporter
from ..ingestao.parser import ExcelParser
from ..repository.dre_repository import DRERepository
from ..templates.writer import TemplateWriter
from ..transformacao.engine import DRETransformer
from ..validacao.validators import DREValidator
from .dre_geracao_completa import DREGeracaoCompletaService

logger = logging.getLogger(__name__)


class DREProcessamentoService:
    """Orquestra validação, transformacao e escrita do DRE."""

    def __init__(
        self,
        template_path: Path | None = None,
        output_dir: Path | None = None,
        logs_dir: Path | None = None,
        temp_dir: Path | None = None,
    ):
        self.template_path = Path(template_path) if template_path else settings.template_dre_path
        self.exporter = Exporter(
            base_dir=settings.base_dir,
            output_dir=output_dir,
            logs_dir=logs_dir,
            temp_dir=temp_dir,
        )
        self.parser = ExcelParser("dre")
        self.validator = DREValidator()
        self.transformer = DRETransformer()
        self.mapping = self.parser.mapping
        self.saida_cfg = self.mapping.get("saida", {})

    def processar(
        self,
        arquivo_path: Path,
        arquivo_nome: str,
        competencia: str,
        modo_cumulativo: bool | None = None,
    ) -> DREProcessamentoResponse:
        """Processa um arquivo DRE de ponta a ponta."""
        log = self.exporter.criar_log(FlowType.DRE, [arquivo_nome])
        log.metadata.update(
            {
                "competencia": competencia,
                "template": self.template_path.name,
                "linha_inicio_dados": self._linha_inicio_dados(),
                "faixa_limpa": self._faixa_limpa(),
                "aba_saida": self._aba_saida(),
                "modo_cumulativo_solicitado": modo_cumulativo,
            }
        )

        try:
            dados = self.parser.ler_arquivo(arquivo_path)
            dados["arquivo"] = arquivo_nome

            log.status = ProcessingStatus.VALIDATING
            resultado_validacao = self.validator.validar(
                dados,
                competencia=competencia,
                modo_cumulativo=modo_cumulativo,
            )
            log.total_registros = resultado_validacao.total_linhas
            log.metadata.update(resultado_validacao.metadata)
            log.erros.extend(resultado_validacao.erros)
            log.warnings.extend(resultado_validacao.warnings)

            if resultado_validacao.erros:
                log.finalizar(ProcessingStatus.ERROR)
                self.exporter.salvar_log(log)
                return self._to_response(log)

            log.status = ProcessingStatus.PROCESSING
            lote = self.transformer.transformar(dados, competencia)
            log.total_registros = lote.total_registros
            log.registros_processados = lote.total_registros

            if lote.total_registros == 0:
                log.adicionar_erro(
                    campo="processamento",
                    mensagem="Nenhum lancamento valido foi encontrado para gerar o DRE.",
                    severidade=ErrorSeverity.BLOQUEANTE,
                )
                log.finalizar(ProcessingStatus.ERROR)
                self.exporter.salvar_log(log)
                return self._to_response(log)

            limite = self._limite_linhas_uteis()
            if lote.total_registros > limite:
                log.adicionar_erro(
                    campo="linhas",
                    mensagem=(
                        f"Arquivo DRE excede o limite suportado de {limite} linha(s) uteis. "
                        f"Encontrado: {lote.total_registros}."
                    ),
                    severidade=ErrorSeverity.BLOQUEANTE,
                )
                log.finalizar(ProcessingStatus.ERROR)
                self.exporter.salvar_log(log)
                return self._to_response(log)

            output_path = self.exporter.caminho_saida(
                self.exporter.gerar_nome_saida(
                    FlowType.DRE, self._competencia_para_nome(competencia)
                )
            )
            self._escrever_template(lote, output_path)

            # Persistir no banco de dados (não bloqueante)
            self._persistir_no_banco(lote, arquivo_nome, arquivo_path, competencia)

            log.metadata.update(self._metadata_bd_fluxo(lote.total_registros))
            log.metadata.update(
                {
                    "output_path": str(output_path),
                    "download_url": f"/api/processamentos/{log.id}/download",
                    "registros_transformados": lote.total_registros,
                }
            )
            log.finalizar(ProcessingStatus.COMPLETED, arquivo_saida=output_path.name)
            self.exporter.salvar_log(log)
            return self._to_response(log)

        except Exception as exc:
            logger.exception("Falha ao processar DRE: %s", exc)
            if log.fim is None:
                log.adicionar_erro(
                    campo="processamento",
                    mensagem=str(exc),
                    severidade=ErrorSeverity.BLOQUEANTE,
                )
                log.finalizar(ProcessingStatus.ERROR)
                try:
                    self.exporter.salvar_log(log)
                except Exception:
                    logger.exception("Falha ao persistir log de erro")
            raise

    def obter_processamento(self, processamento_id: str) -> DREProcessamentoResponse | None:
        """Carrega o estado de um processamento a partir do log persistido."""
        log = self.exporter.carregar_log(processamento_id)
        if not log or log.fluxo != FlowType.DRE:
            return None
        return self._to_response(log)

    def obter_arquivo_saida(self, processamento_id: str) -> Path | None:
        """Retorna o arquivo final gerado, se existir."""
        log = self.exporter.carregar_log(processamento_id)
        if not log or not log.arquivo_saida:
            return None

        path = self.exporter.caminho_saida(log.arquivo_saida)
        return path if path.exists() else None

    def _linha_inicio_dados(self) -> int:
        return int(self.saida_cfg.get("linha_inicio_dados") or 2)

    def _coluna_inicio_dados(self) -> int:
        return int(self.saida_cfg.get("coluna_inicio_dados") or 1)

    def _faixa_limpa(self) -> str:
        return str(
            self.saida_cfg.get("faixa_limpa") or self.saida_cfg.get("faixa_limpar") or "A2:G4964"
        )

    def _aba_saida(self) -> str:
        return str(self.saida_cfg.get("aba_dados") or "BD_FLUXO")

    def _limite_linhas_uteis(self) -> int:
        return int(self.saida_cfg.get("limite_linhas_uteis") or 4963)

    def _faixa_formulas(self) -> str:
        return str(self.saida_cfg.get("preservar_faixa_formulas") or "").strip()

    def _limpar_faixa_saida(self) -> bool:
        return bool(self.saida_cfg.get("limpar_faixa_saida", False))

    def _ocultar_linhas_sem_lancamento(self) -> bool:
        return bool(self.saida_cfg.get("ocultar_linhas_sem_lancamento", False))

    def _competencia_para_nome(self, competencia: str) -> str:
        return competencia.replace("/", "-").replace("\\", "-").strip()

    def _faixa_limpa_bounds(self) -> tuple[int, int, int, int]:
        inicio, fim = self._faixa_limpa().split(":")
        col_inicio = self._coluna_de_celula(inicio)
        col_fim = self._coluna_de_celula(fim)
        row_inicio = self._linha_da_celula(inicio)
        row_fim = self._linha_da_celula(fim)
        return row_inicio, row_fim, col_inicio, col_fim

    def _metadata_bd_fluxo(self, registros_reais: int) -> dict[str, int | str | None]:
        row_inicio, row_fim, col_inicio, col_fim_dados = self._faixa_limpa_bounds()
        col_fim_fisico = col_fim_dados
        limpeza_aplicada = self._limpar_faixa_saida()
        faixa_formulas = self._faixa_formulas()
        if ":" in faixa_formulas:
            _, col_fim_texto = faixa_formulas.split(":", 1)
            col_fim_fisico = max(col_fim_fisico, self._coluna_de_celula(col_fim_texto))

        capacidade = max(row_fim - row_inicio + 1, 0)
        ultima_linha_real = (
            (row_inicio + registros_reais - 1) if registros_reais > 0 else row_inicio - 1
        )

        linhas_sem_inicio: int | None = None
        linhas_sem_fim: int | None = None
        faixa_sem_lancamento: str | None = None
        if limpeza_aplicada and registros_reais < capacidade:
            linhas_sem_inicio = row_inicio + registros_reais
            linhas_sem_fim = row_fim
            faixa_sem_lancamento = f"{linhas_sem_inicio}:{linhas_sem_fim}"

        return {
            "bd_fluxo_range_fisico": (
                f"{self._indice_para_coluna(col_inicio)}1:"
                f"{self._indice_para_coluna(col_fim_fisico)}{row_fim}"
            ),
            "bd_fluxo_total_linhas_template": capacidade,
            "bd_fluxo_registros_reais": registros_reais,
            "bd_fluxo_linhas_entrada_reescritas": registros_reais,
            "bd_fluxo_limpeza_faixa_aplicada": limpeza_aplicada,
            "bd_fluxo_cabecalho_linha": row_inicio - 1,
            "bd_fluxo_ultima_linha_dados_reais": ultima_linha_real,
            "bd_fluxo_linhas_sem_lancamento_inicio": linhas_sem_inicio,
            "bd_fluxo_linhas_sem_lancamento_fim": linhas_sem_fim,
            "bd_fluxo_linhas_sem_lancamento_faixa": faixa_sem_lancamento,
            "bd_fluxo_linhas_sem_lancamento_ocultadas": (
                bool(faixa_sem_lancamento) and self._ocultar_linhas_sem_lancamento()
            ),
            "bd_fluxo_nota": (
                "Nao tratar contagem fisica da sheet como contagem de registros. "
                "Linhas sem lancamento mantem formulas/estrutura do template."
            ),
        }

    def _to_response(self, log: ProcessingLog) -> DREProcessamentoResponse:
        download_url = None
        if log.status == ProcessingStatus.COMPLETED and log.arquivo_saida:
            download_url = f"/api/processamentos/{log.id}/download"
        elif log.metadata.get("download_url"):
            download_url = str(log.metadata["download_url"])

        return DREProcessamentoResponse(
            id=log.id,
            fluxo=log.fluxo,
            status=log.status,
            valido=not log.tem_bloqueante and log.status == ProcessingStatus.COMPLETED,
            arquivo_entrada=log.arquivo_entrada,
            arquivo_saida=log.arquivo_saida,
            download_url=download_url,
            total_registros=log.total_registros,
            registros_processados=log.registros_processados,
            erros=log.erros,
            warnings=log.warnings,
            inicio=log.inicio,
            fim=log.fim,
            metadata=log.metadata,
        )

    def _converter_lote_para_linhas(self, lote: DRELote) -> list[list]:
        linhas = []
        for lancamento in lote.lancamentos:
            linhas.append(
                [
                    lancamento.data,
                    lancamento.historico,
                    float(lancamento.credito),
                    float(lancamento.debito),
                    float(lancamento.valor_liquido),
                    lancamento.natureza,
                    lancamento.centro_custo,
                ]
            )
        return linhas

    def _ler_plano_contas(self, writer: TemplateWriter) -> dict[str, dict]:
        """Lê o mesmo plano canônico usado pela geração DRE persistida."""
        return DREGeracaoCompletaService._ler_plano_contas(
            writer,
            aplicar_overrides_dre_gerado=True,
        )

    def _resolver_conta_pai(
        self,
        natureza: str,
        rubrica_lanc: str,
        plano: dict[str, dict],
        valor: float | None = None,
    ) -> tuple[str, str, str, int | None]:
        """Resolve pelo código gerencial e aplica as regras vigentes do DRE."""
        return DREGeracaoCompletaService._resolver_conta_pai(
            natureza,
            rubrica_lanc,
            plano,
            valor,
        )

    def _agregar_para_apoio(self, lote: DRELote, plano: dict[str, dict]) -> list[list]:
        """Agrega lançamentos por Conta Pai/Rubrica x Mês para preencher APOIO.

        Retorna linhas no formato: [cod, conta_pai_ou_rubrica, jan, fev, ..., mai, total]
        """
        # Estrutura: chave=(cod, label) → {mes: valor}
        agregado: dict[tuple[int | None, str], dict[int, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        meses_encontrados = set()

        for lanc in lote.lancamentos:
            valor = float(lanc.valor_liquido)
            rubrica, conta_filho, conta_pai, cod = self._resolver_conta_pai(
                lanc.natureza,
                lanc.rubrica,
                plano,
                valor,
            )
            mes = lanc.data.month
            meses_encontrados.add(mes)

            # Agrega por rubrica (detalhe)
            if rubrica:
                agregado[(cod, rubrica)][mes] += valor

            # Agrega por conta_filho (subtotal)
            if conta_filho:
                agregado[(cod, conta_filho)][mes] += valor

            # Agrega por conta_pai (total)
            if conta_pai:
                agregado[(cod, conta_pai)][mes] += valor

        # Monta linhas (ordenadas por cod, depois label)
        max_mes = max(meses_encontrados) if meses_encontrados else 5

        linhas = []
        for (cod, label), meses_vals in sorted(
            agregado.items(), key=lambda x: (x[0][0] if x[0][0] is not None else 99, x[0][1])
        ):
            row: list = [cod, label]
            total = 0.0
            for m in range(1, max_mes + 1):
                val = meses_vals.get(m)
                row.append(val)
                if val:
                    total += val
            row.append(total)  # Total Geral
            linhas.append(row)

        return (linhas, max_mes)

    def _escrever_apoio(
        self, writer: TemplateWriter, lote: DRELote, plano: dict[str, dict]
    ) -> None:
        """Reescreve aba APOIO com dados agregados frescos."""
        meses_nomes = [
            "Jan",
            "Fev",
            "Mar",
            "Abr",
            "Mai",
            "Jun",
            "Jul",
            "Ago",
            "Set",
            "Out",
            "Nov",
            "Dez",
        ]

        linhas_apoio, max_mes = self._agregar_para_apoio(lote, plano)

        if not linhas_apoio:
            logger.warning("Nenhum dado para escrever na APOIO")
            return

        # Reescrever cabeçalho APOIO (row 5)
        header: list = ["Rótulos de Linha", "Conta Pai"]
        for m in range(max_mes):
            header.append(meses_nomes[m])
        header.append("Total Geral")

        writer.escrever_area("APOIO", [header], linha_inicio=5, coluna_inicio=1)

        # Limpar dados antigos da APOIO (linhas 6 até 200)
        writer.limpar_area("APOIO", 6, 200, 1, 2 + max_mes + 1)

        # Escrever dados novos
        writer.escrever_area("APOIO", linhas_apoio, linha_inicio=6, coluna_inicio=1)

        logger.info("APOIO reescrita: %d linhas, %d meses", len(linhas_apoio), max_mes)

    def _persistir_no_banco(
        self, lote: DRELote, arquivo_nome: str, arquivo_path: Path, competencia: str
    ) -> None:
        """Persiste lançamentos no banco de dados (opcional, não bloqueia se falhar)."""
        try:
            db = DatabaseConnection()
            run_migrations(db)
            repo = DRERepository(db)

            # Parse competência
            parts = competencia.replace("-", "/").replace("\\", "/").split("/")
            if len(parts) != 2:
                return
            mes, ano = int(parts[0]), int(parts[1])

            # Calcular SHA256
            sha256_hash = hashlib.sha256()
            with open(arquivo_path, "rb") as f:
                for block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(block)
            arquivo_sha256 = sha256_hash.hexdigest()

            # Verificar se já processado para a mesma competência
            existente = repo.uploads.get_by_sha256_competencia(arquivo_sha256, ano, mes)
            if existente and existente.status == "completed":
                logger.info("Arquivo já persistido no banco: %s", existente.id)
                return

            # Criar upload
            upload = DREUpload(
                id=str(uuid4()),
                arquivo_nome=arquivo_nome,
                arquivo_sha256=arquivo_sha256,
                competencia_ano=ano,
                competencia_mes=mes,
                status="processing",
                total_linhas=lote.total_registros,
            )

            # Converter lançamentos
            lancamentos_db = []
            for lanc in lote.lancamentos:
                content = (
                    f"{lanc.data.isoformat()}|{lanc.historico}|{lanc.valor_bruto}|"
                    f"{lanc.credito}|{lanc.debito}|{lanc.natureza}|{lanc.centro_custo}|"
                    f"{lanc.linha_origem or 0}"
                )
                hash_linha = hashlib.sha256(content.encode()).hexdigest()[:32]

                lancamentos_db.append(
                    DRELancamentoDB(
                        upload_id=upload.id,
                        competencia_ano=ano,
                        competencia_mes=mes,
                        data_lancamento=lanc.data.isoformat(),
                        historico=lanc.historico,
                        valor_bruto=lanc.valor_bruto or (lanc.credito + lanc.debito),
                        credito=lanc.credito,
                        debito=lanc.debito,
                        natureza_raw=lanc.natureza,
                        natureza_norm=lanc.natureza.upper().strip(),
                        centro_custo=lanc.centro_custo,
                        rubrica=lanc.rubrica,
                        conta_pai=lanc.conta_pai,
                        linha_origem=lanc.linha_origem,
                        hash_linha=hash_linha,
                    )
                )

            repo.upsert_competencia(upload, lancamentos_db)
            logger.info(
                "Persistido no banco: upload=%s, lancamentos=%d", upload.id, len(lancamentos_db)
            )

        except Exception as e:
            logger.warning("Falha ao persistir no banco (não bloqueante): %s", e)

    def _escrever_template(self, lote: DRELote, output_path: Path) -> None:
        sheet_name = self._aba_saida()
        linha_inicio = self._linha_inicio_dados()
        coluna_inicio = self._coluna_inicio_dados()
        faixa_limpa = self._faixa_limpa()

        with TemplateWriter(self.template_path) as writer:
            # 1. Ler PLANO_CONTAS para mapeamento
            plano = self._ler_plano_contas(writer)

            # 2. Limpar e escrever BD_FLUXO
            inicio, fim = faixa_limpa.split(":")
            col_inicio = self._coluna_de_celula(inicio)
            col_fim = self._coluna_de_celula(fim)
            row_inicio = self._linha_da_celula(inicio)
            row_fim = self._linha_da_celula(fim)

            if self._limpar_faixa_saida():
                writer.limpar_area(sheet_name, row_inicio, row_fim, col_inicio, col_fim)
            writer.escrever_area(
                sheet_name,
                self._converter_lote_para_linhas(lote),
                linha_inicio,
                coluna_inicio,
            )

            # 3. Reescrever APOIO com dados agregados
            self._escrever_apoio(writer, lote, plano)
            DREGeracaoCompletaService._proteger_formulas_apoio(writer)

            # 4. Gerenciar linhas ocultas
            writer.definir_linhas_ocultas(sheet_name, row_inicio, row_fim, ocultar=False)
            if self._ocultar_linhas_sem_lancamento():
                primeira_sem_lancamento = row_inicio + lote.total_registros
                writer.definir_linhas_ocultas(
                    sheet_name,
                    primeira_sem_lancamento,
                    row_fim,
                    ocultar=True,
                )

            problemas = writer.validar_integridade()
            if problemas:
                raise RuntimeError("; ".join(problemas))

            writer.salvar(output_path)

    @staticmethod
    def _linha_da_celula(referencia: str) -> int:
        return int("".join(ch for ch in referencia if ch.isdigit()))

    @staticmethod
    def _coluna_de_celula(referencia: str) -> int:
        texto = "".join(ch for ch in referencia if ch.isalpha()).upper()
        resultado = 0
        for char in texto:
            resultado = resultado * 26 + (ord(char) - ord("A") + 1)
        return resultado

    @staticmethod
    def _indice_para_coluna(indice: int) -> str:
        if indice < 1:
            raise ValueError("Indice de coluna deve ser >= 1")
        col = []
        atual = indice
        while atual > 0:
            atual, resto = divmod(atual - 1, 26)
            col.append(chr(ord("A") + resto))
        return "".join(reversed(col))
