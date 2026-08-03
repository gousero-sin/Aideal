"""Serviço de ingestão mensal de Fluxo de Caixa."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..contracts.common import ErrorSeverity, ValidationError
from ..contracts.fluxo_caixa import FCMovimento
from ..contracts.persistence import FluxoMovimentoDB, FluxoUpload
from ..db.connection import DatabaseConnection
from ..ingestao.parser import ExcelParser
from ..processamento.competencia import CompetenciaDetectorService
from ..repository.fluxo_repository import FluxoCaixaRepository
from ..transformacao.engine import FluxoCaixaTransformer
from ..validacao.transferencias import conciliar_transferencias
from ..validacao.validators import FluxoCaixaValidator
from .auditoria_upload import arquivar_upload, calcular_sha256

logger = logging.getLogger(__name__)


class FluxoCaixaIngestaoService:
    """Ingestão de extratos bancários mensais para persistência no banco."""

    def __init__(
        self,
        db: DatabaseConnection | None = None,
        archive_dir: Path | None = None,
    ):
        self.db = db or DatabaseConnection()
        self.repository = FluxoCaixaRepository(self.db)
        self.parser = ExcelParser("fluxo")
        self.validator = FluxoCaixaValidator()
        self.transformer = FluxoCaixaTransformer()
        self.archive_dir = (
            Path(archive_dir)
            if archive_dir
            else self.db.db_path.parent / "uploads_archive"
        )

    def _calcular_sha256(self, file_path: Path) -> str:
        return calcular_sha256(file_path)

    @staticmethod
    def _parse_competencia(competencia: str) -> tuple[int, int]:
        parts = competencia.replace("-", "/").replace("\\", "/").split("/")
        if len(parts) != 2:
            raise ValueError(f"Competência deve estar no formato MM/AAAA: {competencia}")

        mes = int(parts[0])
        ano = int(parts[1])
        if mes < 1 or mes > 12:
            raise ValueError(f"Mês da competência inválido: {mes:02d}. Use valores entre 01 e 12.")
        return ano, mes

    @staticmethod
    def _nome_exportacao_malformado(arquivo_nome: str) -> bool:
        nome = Path(arquivo_nome).name
        aparenta_exportacao = re.match(r"^movimentos_\d{4}[-_]", nome, re.IGNORECASE)
        if not aparenta_exportacao:
            return False
        return (
            re.match(
                r"^movimentos_\d{4}-(?:0[1-9]|1[0-2])(?:_|$)",
                nome,
                re.IGNORECASE,
            )
            is None
        )

    @staticmethod
    def _warning_arquivo_ignorado(arquivo: str) -> ValidationError:
        return ValidationError(
            campo="arquivo",
            mensagem=(
                f"Arquivo '{arquivo}' foi ignorado por não possuir estrutura de movimento bancário."
            ),
            severidade=ErrorSeverity.WARNING,
            sugestao=(
                "Se o relatório contém 'Nenhum registro encontrado', ele pode ser mantido "
                "no lote; o consolidado será gerado com os demais extratos válidos."
            ),
        )

    @staticmethod
    def _filtrar_movimentos_competencia(
        movimentos: list[FCMovimento],
        ano: int,
        mes: int,
    ) -> tuple[list[FCMovimento], int]:
        filtrados = [
            mov
            for mov in movimentos
            if mov.data_movimento.year == ano and mov.data_movimento.month == mes
        ]
        return filtrados, len(movimentos) - len(filtrados)

    def _movimento_to_db(
        self,
        movimento: FCMovimento,
        upload_id: str,
        ano: int,
        mes: int,
    ) -> FluxoMovimentoDB:
        return FluxoMovimentoDB.from_movimento(
            movimento=movimento,
            upload_id=upload_id,
            ano=ano,
            mes=mes,
            hash_linha="",
        )

    def ingestar_lote(
        self,
        arquivos: list[tuple[Path, str]],
        competencia: str,
        replace: bool = True,
        replace_scope: str = "bancos",
    ) -> dict[str, Any]:
        """Persiste um lote mensal de extratos bancários do Fluxo de Caixa."""
        logger.info("Iniciando ingestão Fluxo de Caixa: %s arquivo(s)", len(arquivos))

        try:
            ano, mes = self._parse_competencia(competencia)
        except ValueError as exc:
            return {
                "success": False,
                "error": str(exc),
                "competencia": competencia,
                "upload_id": None,
            }

        if not replace and self.repository.uploads.get_by_competencia(ano, mes):
            return {
                "success": False,
                "error": f"Já existem dados de Fluxo de Caixa para {mes:02d}/{ano}.",
                "competencia": competencia,
            }
        if replace_scope not in {"bancos", "competencia"}:
            return {
                "success": False,
                "status": "validation_error",
                "error": "Escopo de substituição inválido. Use 'bancos' ou 'competencia'.",
                "competencia": competencia,
            }

        uploads_movimentos: list[tuple[FluxoUpload, list[FluxoMovimentoDB]]] = []
        warnings: list[ValidationError] = []
        arquivos_ignorados: list[dict[str, str]] = []
        arquivos_arquivados: list[dict[str, str]] = []
        bancos_identificados: set[str] = set()
        linhas_total = 0
        linhas_validas = 0
        linhas_rejeitadas = 0

        for arquivo_path, arquivo_nome in arquivos:
            arquivo_hash = self._calcular_sha256(arquivo_path)
            try:
                caminho_arquivado = arquivar_upload(
                    file_path=arquivo_path,
                    arquivo_nome=arquivo_nome,
                    fluxo="fluxo_caixa",
                    ano=ano,
                    mes=mes,
                    arquivo_sha256=arquivo_hash,
                    archive_dir=self.archive_dir,
                )
                arquivos_arquivados.append(
                    {
                        "arquivo": arquivo_nome,
                        "sha256": arquivo_hash,
                        "caminho": str(caminho_arquivado),
                    }
                )
            except Exception as exc:
                return {
                    "success": False,
                    "status": "archive_error",
                    "error": f"Não foi possível preservar '{arquivo_nome}': {exc}",
                    "competencia": competencia,
                    "arquivos_arquivados": arquivos_arquivados,
                }

            if self._nome_exportacao_malformado(arquivo_nome):
                return {
                    "success": False,
                    "status": "validation_error",
                    "error": (
                        f"O arquivo '{arquivo_nome}' possui nome malformado. "
                        "Use o padrão movimentos_AAAA-MM_banco_.xlsx."
                    ),
                    "competencia": competencia,
                    "arquivo": arquivo_nome,
                    "arquivos_arquivados": arquivos_arquivados,
                }

            competencia_nome = CompetenciaDetectorService._detectar_por_nome(arquivo_nome)
            if competencia_nome and competencia_nome != (ano, mes):
                ano_nome, mes_nome = competencia_nome
                return {
                    "success": False,
                    "status": "validation_error",
                    "error": (
                        f"O arquivo '{arquivo_nome}' indica {mes_nome:02d}/{ano_nome}, "
                        f"mas a competência selecionada é {mes:02d}/{ano}."
                    ),
                    "competencia": competencia,
                    "arquivo": arquivo_nome,
                    "arquivos_arquivados": arquivos_arquivados,
                }

            try:
                dados = self.parser.ler_arquivo(arquivo_path)
                dados["arquivo"] = arquivo_nome
            except Exception as exc:
                return {
                    "success": False,
                    "status": "read_error",
                    "error": f"Erro ao ler arquivo '{arquivo_nome}': {exc}",
                    "competencia": competencia,
                    "arquivos_arquivados": arquivos_arquivados,
                }

            validacao = self.validator.validar(dados)
            if validacao.erros:
                if self.validator._deve_ignorar_arquivo_por_estrutura(validacao.erros):
                    arquivos_ignorados.append(
                        {
                            "arquivo": arquivo_nome,
                            "motivo": "arquivo_sem_colunas_de_movimento_bancario",
                        }
                    )
                    warnings.append(self._warning_arquivo_ignorado(arquivo_nome))
                    continue

                return {
                    "success": False,
                    "status": "validation_error",
                    "competencia": competencia,
                    "arquivo": arquivo_nome,
                    "erros": [erro.model_dump(mode="json") for erro in validacao.erros],
                    "warnings": [w.model_dump(mode="json") for w in validacao.warnings],
                    "arquivos_arquivados": arquivos_arquivados,
                }

            warnings.extend(validacao.warnings)
            banco = self.parser.detectar_banco(arquivo_nome) or "desconhecido"
            bancos_identificados.add(banco)

            lote = self.transformer.transformar(dados, banco_origem=banco, periodo=competencia)
            warnings.extend(self.transformer.erros)
            movimentos_mes, rejeitadas_outro_mes = self._filtrar_movimentos_competencia(
                lote.movimentos,
                ano,
                mes,
            )
            linhas_total += lote.total_registros
            linhas_validas += len(movimentos_mes)
            linhas_rejeitadas += rejeitadas_outro_mes
            if rejeitadas_outro_mes:
                warnings.append(
                    ValidationError(
                        campo="competencia",
                        mensagem=(
                            f"Arquivo '{arquivo_nome}' contém {rejeitadas_outro_mes} "
                            f"movimento(s) fora de {mes:02d}/{ano}; essas linhas não foram salvas."
                        ),
                        severidade=ErrorSeverity.WARNING,
                        sugestao="Confira se a exportação foi gerada para uma única competência.",
                    )
                )

            if not movimentos_mes:
                arquivos_ignorados.append(
                    {
                        "arquivo": arquivo_nome,
                        "motivo": "sem_movimentos_na_competencia",
                    }
                )
                warnings.append(
                    ValidationError(
                        campo="arquivo",
                        mensagem=(
                            f"Arquivo '{arquivo_nome}' não possui movimentos em {mes:02d}/{ano}."
                        ),
                        severidade=ErrorSeverity.WARNING,
                        sugestao="Confira a competência selecionada para este extrato.",
                    )
                )
                continue

            upload_id = str(uuid4())
            upload = FluxoUpload(
                id=upload_id,
                arquivo_nome=arquivo_nome,
                arquivo_sha256=arquivo_hash,
                competencia_ano=ano,
                competencia_mes=mes,
                banco=banco,
                status="processing",
                total_linhas=lote.total_registros,
                linhas_validas=len(movimentos_mes),
                linhas_rejeitadas=rejeitadas_outro_mes,
            )
            movimentos_db = [
                self._movimento_to_db(mov, upload_id, ano, mes) for mov in movimentos_mes
            ]
            uploads_movimentos.append((upload, movimentos_db))

        if not uploads_movimentos:
            return {
                "success": False,
                "status": "validation_error",
                "error": "Nenhum movimento válido encontrado para salvar no Fluxo de Caixa.",
                "competencia": competencia,
                "warnings": [w.model_dump(mode="json") for w in warnings],
                "arquivos_ignorados": arquivos_ignorados,
                "arquivos_arquivados": arquivos_arquivados,
            }

        uploads_anteriores = self.repository.uploads.get_by_competencia(ano, mes)
        bancos_conhecidos = {
            banco
            for banco in bancos_identificados
            if banco.strip().lower() not in {"", "desconhecido", "sem banco"}
        }
        arquivos_substituidos = {
            upload.arquivo_nome
            for upload, _ in uploads_movimentos
        }
        for upload_anterior in uploads_anteriores:
            banco_detectado = self.parser.detectar_banco(upload_anterior.arquivo_nome)
            if banco_detectado in bancos_conhecidos:
                arquivos_substituidos.add(upload_anterior.arquivo_nome)

        removidos, inseridos = self.repository.upsert_competencia(
            uploads_movimentos,
            substituir_bancos=bancos_conhecidos if replace_scope == "bancos" else None,
            substituir_arquivos=arquivos_substituidos if replace_scope == "bancos" else None,
        )
        uploads_persistidos = self.repository.uploads.get_by_competencia(ano, mes)
        bancos_persistidos = {
            str(upload.banco or "").strip().lower()
            for upload in uploads_persistidos
            if upload.banco
        }
        movimentos_persistidos = self.transformer.normalizar_movimentos_persistidos(
            [
                movimento.to_movimento()
                for movimento in self.repository.movimentos.get_by_meses(ano, [mes])
            ]
        )
        conciliacao_transferencias = conciliar_transferencias(movimentos_persistidos)
        if conciliacao_transferencias["nao_pareadas"]:
            warnings.append(
                ValidationError(
                    campo="transferencias",
                    mensagem=(
                        f"{conciliacao_transferencias['nao_pareadas']} transferência(s) "
                        "entre bancos ficaram sem contrapartida conciliada. Elas permanecem "
                        "neutras no saldo financeiro geral."
                    ),
                    severidade=ErrorSeverity.WARNING,
                    sugestao=(
                        "Revise os dois extratos bancários e a classificação 2.1 "
                        "no sistema de origem."
                    ),
                )
            )
        meses_disponiveis = self.repository.get_meses_disponiveis(ano)

        return {
            "success": True,
            "competencia": competencia,
            "competencia_salva": f"{mes:02d}/{ano}",
            "ano": ano,
            "mes": mes,
            "status": "completed",
            "total_linhas": linhas_total,
            "linhas_validas": linhas_validas,
            "linhas_rejeitadas": linhas_rejeitadas,
            "substituido": removidos > 0,
            "removidos": removidos,
            "inseridos": inseridos,
            "escopo_substituicao": replace_scope,
            "bancos_substituidos": sorted(bancos_identificados),
            "bancos_preservados": (
                sorted(bancos_persistidos - bancos_identificados)
                if replace_scope == "bancos"
                else []
            ),
            "bancos_identificados": sorted(bancos_identificados),
            "meses_disponiveis_ano": meses_disponiveis,
            "warnings": [w.model_dump(mode="json") for w in warnings],
            "arquivos_ignorados": arquivos_ignorados,
            "arquivos_arquivados": arquivos_arquivados,
            "conciliacao_transferencias": conciliacao_transferencias,
        }

    def listar_ingestoes(
        self, ano: int | None = None, mes: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Lista uploads de Fluxo de Caixa persistidos."""
        if ano and mes:
            uploads = self.repository.uploads.get_by_competencia(ano, mes)
        elif ano:
            uploads = self.repository.uploads.get_by_ano(ano)
        else:
            uploads = self.repository.uploads.list_all(limit=limit)

        return [
            {
                "upload_id": upload.id,
                "arquivo_nome": upload.arquivo_nome,
                "competencia": f"{upload.competencia_mes:02d}/{upload.competencia_ano}",
                "status": upload.status,
                "created_at": upload.created_at.isoformat(),
                "banco": upload.banco,
                "total_linhas": upload.total_linhas,
                "linhas_validas": upload.linhas_validas,
            }
            for upload in uploads
        ]
