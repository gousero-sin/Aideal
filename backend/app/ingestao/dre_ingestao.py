"""Serviço de ingestão mensal de DRE."""

import hashlib
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..contracts.dre import DRELancamento
from ..contracts.persistence import DRELancamentoDB, DREUpload
from ..db.connection import DatabaseConnection
from ..ingestao.parser import ExcelParser
from ..repository.dre_repository import DRERepository
from ..transformacao.engine import DRETransformer
from ..validacao.validators import DREValidator

logger = logging.getLogger(__name__)


class DREIngestaoService:
    """Serviço para ingestão mensal de dados DRE no banco."""

    def __init__(self, db: DatabaseConnection | None = None):
        self.db = db or DatabaseConnection()
        self.repository = DRERepository(self.db)
        self.parser = ExcelParser("dre")
        self.validator = DREValidator()
        self.transformer = DRETransformer()

    def _calcular_sha256(self, file_path: Path) -> str:
        """Calcula SHA256 do arquivo."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _parse_competencia(self, competencia: str) -> tuple[int, int]:
        """Converte 'MM/AAAA' ou 'M/AAAA' para (ano, mes)."""
        parts = competencia.replace("-", "/").replace("\\", "/").split("/")
        if len(parts) != 2:
            raise ValueError(f"Competência deve estar no formato MM/AAAA: {competencia}")

        mes_str, ano_str = parts
        mes = int(mes_str)
        ano = int(ano_str)
        if mes < 1 or mes > 12:
            raise ValueError(
                f"Mês da competência inválido: {mes:02d}. Use valores entre 01 e 12."
            )
        return ano, mes

    def _lancamento_to_db(
        self, lanc: DRELancamento, upload_id: str, ano: int, mes: int
    ) -> DRELancamentoDB:
        """Converte lançamento do domínio para modelo DB."""
        return DRELancamentoDB(
            upload_id=upload_id,
            competencia_ano=ano,
            competencia_mes=mes,
            data_lancamento=lanc.data.isoformat(),
            historico=lanc.historico,
            valor_bruto=lanc.credito + lanc.debito,
            credito=lanc.credito,
            debito=lanc.debito,
            natureza_raw=lanc.natureza,
            natureza_norm=self._normalizar_natureza(
                lanc.natureza, lanc.classificacao_entrada_saida
            ),
            centro_custo=lanc.centro_custo,
            rubrica=lanc.rubrica,
            conta_pai=lanc.conta_pai,
            linha_origem=lanc.linha_origem,
            hash_linha=self._calcular_hash_linha(lanc),
        )

    def _normalizar_natureza(self, natureza: str, classificacao_entrada_saida: str = "") -> str:
        """Normaliza classificação de natureza para ENTRADA/SAIDA."""
        # Primeiro tenta usar o indicador direto de CLASSIFICAÇÃO (mais confiável)
        if classificacao_entrada_saida:
            classif = classificacao_entrada_saida.upper().strip()
            if "ENTRADA" in classif or classif.startswith("1 -") or classif == "1":
                return "ENTRADA"
            saida_terms = "SAIDA" in classif or "SAÍDA" in classif
            if saida_terms or classif.startswith("2 -") or classif == "2":
                return "SAIDA"

        # Fallback por heurística no código gerencial
        natureza_upper = natureza.upper().strip()
        if any(term in natureza_upper for term in ["ENTRADA", "RECEITA", "RECEBIMENTO"]):
            return "ENTRADA"
        if any(term in natureza_upper for term in ["SAIDA", "SAÍDA", "DESPESA", "PAGAMENTO"]):
            return "SAIDA"

        return natureza_upper

    def _calcular_hash_linha(self, lanc: DRELancamento) -> str:
        """Calcula hash único para o lançamento."""
        content = (
            f"{lanc.data.isoformat()}|{lanc.historico}|{lanc.credito}"
            f"|{lanc.debito}|{lanc.natureza}|{lanc.centro_custo}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_meses_disponiveis_ano(self, ano: int, mes_alvo: int) -> list[int]:
        """Retorna lista de meses com upload completed no ano até mes_alvo."""
        meses = []
        for m in range(1, mes_alvo + 1):
            uploads = self.repository.uploads.get_by_competencia(ano, m)
            if uploads and any(u.status == "completed" for u in uploads):
                meses.append(m)
        return meses

    def _contar_datas_fora_competencia(
        self, lancamentos: list[DRELancamento], ano: int, mes: int
    ) -> int:
        """Conta lançamentos cuja data de emissão está fora da competência.

        A competência é definida pelo upload (parâmetro do usuário), não pela
        data de emissão de cada linha — o relatório mensal pode conter linhas
        com data no mês seguinte (ex.: recebimento de cliente contabilizado
        como receita do mês do relatório). Retornamos apenas contagem para
        fins de observabilidade.
        """
        return sum(
            1 for lanc in lancamentos
            if lanc.data.year != ano or lanc.data.month != mes
        )

    def ingestar(
        self,
        arquivo_path: Path,
        arquivo_nome: str,
        competencia: str,
        replace: bool = True,
    ) -> dict[str, Any]:
        """
        Realiza ingestão mensal de DRE.

        Args:
            arquivo_path: Caminho para o arquivo Excel
            arquivo_nome: Nome original do arquivo
            competencia: Competência no formato MM/AAAA
            replace: Se True, substitui competência existente

        Returns:
            Dict com resultado da operação
        """
        logger.info("Iniciando ingestão DRE: %s - %s", arquivo_nome, competencia)

        # 1. Parse competência
        try:
            ano, mes = self._parse_competencia(competencia)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "upload_id": None,
                "competencia": competencia,
            }

        # 2. Calcular hash do arquivo
        arquivo_hash = self._calcular_sha256(arquivo_path)

        # 3. Verificar se arquivo já foi processado na MESMA competência (idempotência)
        upload_existente = self.repository.uploads.get_by_sha256_competencia(arquivo_hash, ano, mes)
        if upload_existente and upload_existente.status == "completed":
            logger.info(
                "Arquivo já processado para %02d/%d: %s",
                mes,
                ano,
                upload_existente.id,
            )
            return {
                "success": True,
                "upload_id": upload_existente.id,
                "competencia": (
                    f"{upload_existente.competencia_mes:02d}"
                    f"/{upload_existente.competencia_ano}"
                ),
                "status": "already_processed",
                "message": "Arquivo já foi processado anteriormente",
                "total_linhas": upload_existente.total_linhas,
                "linhas_validas": upload_existente.linhas_validas,
            }
        if upload_existente and upload_existente.status != "completed":
            logger.info(
                "Reprocessando hash já existente na competência %02d/%d com status=%s",
                mes,
                ano,
                upload_existente.status,
            )

        # 4. Ler e validar arquivo
        try:
            dados = self.parser.ler_arquivo(arquivo_path)
            dados["arquivo"] = arquivo_nome
        except Exception as e:
            logger.error("Erro ao ler arquivo: %s", e)
            return {
                "success": False,
                "error": f"Erro ao ler arquivo: {str(e)}",
                "upload_id": None,
                "competencia": competencia,
            }

        # 5. Validar estrutura
        resultado_validacao = self.validator.validar(
            dados,
            competencia=competencia,
            modo_cumulativo=False,  # Ingestão é sempre mensal
        )

        if resultado_validacao.erros:
            erros = [e.model_dump() for e in resultado_validacao.erros]
            logger.warning("Validação falhou: %d erros", len(erros))

            # Criar upload com status error
            upload = DREUpload(
                id=str(uuid4()),
                arquivo_nome=arquivo_nome,
                arquivo_sha256=arquivo_hash,
                competencia_ano=ano,
                competencia_mes=mes,
                status="error",
                total_linhas=resultado_validacao.total_linhas,
                linhas_validas=0,
                linhas_rejeitadas=resultado_validacao.total_linhas,
                observacao=f"Erros: {len(erros)}",
            )
            self.repository.uploads.create(upload)

            return {
                "success": False,
                "upload_id": upload.id,
                "competencia": competencia,
                "status": "validation_error",
                "erros": erros,
                "total_linhas": resultado_validacao.total_linhas,
            }

        # 6. Transformar dados
        lote = self.transformer.transformar(dados, competencia)

        if lote.total_registros == 0:
            return {
                "success": False,
                "error": "Nenhum lançamento válido encontrado no arquivo",
                "upload_id": None,
                "competencia": competencia,
            }

        # 6.1 Todos os lançamentos do lote pertencem à competência do upload.
        # A data de emissão pode variar (relatório de mês X costuma conter
        # linhas com data no mês X+1 — ex.: recebimentos tardios).
        lancamentos_filtrados = list(lote.lancamentos)
        linhas_rejeitadas_outro_mes = 0
        datas_fora = self._contar_datas_fora_competencia(lancamentos_filtrados, ano, mes)
        if datas_fora:
            logger.info(
                "Ingestão %02d/%d: %d lançamento(s) com data fora da competência — mantidos no upload.",
                mes, ano, datas_fora,
            )

        if not lancamentos_filtrados:
            return {
                "success": False,
                "error": (
                    f"Nenhum lançamento encontrado para {mes:02d}/{ano}."
                    " O arquivo contém dados de outros meses?"
                ),
                "upload_id": None,
                "competencia": competencia,
            }

        # 7. Converter para modelo DB
        lancamentos_db = [
            self._lancamento_to_db(lanc, "", ano, mes)  # upload_id será preenchido no upsert
            for lanc in lancamentos_filtrados
        ]

        # 8. Criar upload
        upload = DREUpload(
            id=str(uuid4()),
            arquivo_nome=arquivo_nome,
            arquivo_sha256=arquivo_hash,
            competencia_ano=ano,
            competencia_mes=mes,
            status="processing",
            total_linhas=lote.total_registros,
            linhas_rejeitadas=linhas_rejeitadas_outro_mes,
        )

        # 9. Executar upsert transacional
        try:
            upload_atualizado, removidos, inseridos = self.repository.upsert_competencia(
                upload, lancamentos_db
            )

            logger.info(
                "Ingestão concluída: upload=%s, inseridos=%d, "
                "removidos=%d, rejeitadas_outro_mes=%d",
                upload_atualizado.id,
                inseridos,
                removidos,
                linhas_rejeitadas_outro_mes,
            )

            meses_disponiveis = self._get_meses_disponiveis_ano(ano, mes)

            return {
                "success": True,
                "upload_id": upload_atualizado.id,
                "competencia": competencia,
                "competencia_salva": f"{mes:02d}/{ano}",
                "ano": ano,
                "mes": mes,
                "status": upload_atualizado.status,
                "total_linhas": upload_atualizado.total_linhas,
                "linhas_validas": upload_atualizado.linhas_validas,
                "linhas_rejeitadas": upload_atualizado.linhas_rejeitadas,
                "linhas_outro_mes": linhas_rejeitadas_outro_mes,
                "substituido": removidos > 0,
                "removidos": removidos,
                "inseridos": inseridos,
                "meses_disponiveis_ano": meses_disponiveis,
            }

        except Exception as e:
            logger.exception("Erro durante upsert: %s", e)
            return {
                "success": False,
                "error": f"Erro ao persistir dados: {str(e)}",
                "upload_id": upload.id,
                "competencia": competencia,
            }

    def obter_status(self, upload_id: str) -> dict[str, Any] | None:
        """Obtém status de um upload."""
        upload = self.repository.uploads.get_by_id(upload_id)
        if not upload:
            return None

        # Buscar resumo dos lançamentos
        resumo = self.repository.lancamentos.get_resumo_competencia(
            upload.competencia_ano, upload.competencia_mes
        )

        return {
            "upload_id": upload.id,
            "arquivo_nome": upload.arquivo_nome,
            "competencia": f"{upload.competencia_mes:02d}/{upload.competencia_ano}",
            "status": upload.status,
            "created_at": upload.created_at.isoformat(),
            "total_linhas": upload.total_linhas,
            "linhas_validas": upload.linhas_validas,
            "linhas_rejeitadas": upload.linhas_rejeitadas,
            "observacao": upload.observacao,
            "resumo_lancamentos": resumo.model_dump() if resumo else None,
        }

    def listar_ingestoes(
        self, ano: int | None = None, mes: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Lista ingestões com filtros opcionais."""
        if ano and mes:
            uploads = self.repository.uploads.get_by_competencia(ano, mes)
        elif ano:
            uploads = self.repository.uploads.get_by_ano(ano)
        else:
            uploads = self.repository.uploads.list_all(limit=limit)

        return [
            {
                "upload_id": u.id,
                "arquivo_nome": u.arquivo_nome,
                "competencia": f"{u.competencia_mes:02d}/{u.competencia_ano}",
                "status": u.status,
                "created_at": u.created_at.isoformat(),
                "total_linhas": u.total_linhas,
                "linhas_validas": u.linhas_validas,
            }
            for u in uploads
        ]
