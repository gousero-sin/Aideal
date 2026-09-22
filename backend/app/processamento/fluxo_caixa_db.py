"""Geração do Fluxo de Caixa a partir dos dados persistidos no banco."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from ..config import settings
from ..contracts.common import FlowType
from ..contracts.fluxo_caixa import FCLote, FCMovimento
from ..contracts.persistence import FluxoMovimentoDB
from ..db.connection import DatabaseConnection
from ..exportacao.exporter import Exporter
from ..repository.fluxo_indicadores_manuais import FluxoIndicadoresManuaisRepository
from ..repository.fluxo_repository import FluxoCaixaRepository
from ..validacao.transferencias import conciliar_transferencias
from .fluxo_caixa import FluxoCaixaProcessamentoService


class FluxoCaixaGeracaoService:
    """Gera workbook do Fluxo de Caixa usando o banco como fonte de verdade."""

    def __init__(
        self,
        db: DatabaseConnection | None = None,
        template_path: Path | None = None,
        output_dir: Path | None = None,
        logs_dir: Path | None = None,
        temp_dir: Path | None = None,
    ):
        self.db = db or DatabaseConnection()
        self.repository = FluxoCaixaRepository(self.db)
        self.indicadores_manuais = FluxoIndicadoresManuaisRepository(self.db)
        self.template_path = Path(template_path) if template_path else settings.template_fluxo_path
        self.exporter = Exporter(
            base_dir=settings.base_dir,
            output_dir=output_dir,
            logs_dir=logs_dir,
            temp_dir=temp_dir,
        )
        self.processamento = FluxoCaixaProcessamentoService(
            template_path=self.template_path,
            output_dir=output_dir,
            logs_dir=logs_dir,
            temp_dir=temp_dir,
        )

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
    def _normalizar_meses(meses: list[int] | None) -> list[int]:
        if not meses:
            return []
        normalizados = sorted({int(m) for m in meses if 1 <= int(m) <= 12})
        if len(normalizados) != len(set(meses)):
            return normalizados
        return normalizados

    @staticmethod
    def _valor_monetario(valor: Decimal | float | int | None) -> float:
        """Publica valores financeiros em centavos sem alterar os lançamentos-fonte."""
        decimal = Decimal(str(valor or 0))
        return float(decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def _normalizar_movimentos_persistidos(
        self,
        movimentos_db: list[FluxoMovimentoDB],
    ) -> list[FCMovimento]:
        return self.processamento.transformer.normalizar_movimentos_persistidos(
            [movimento.to_movimento() for movimento in movimentos_db]
        )

    def _obter_saldos_iniciais_por_banco(
        self,
        ano: int,
        mes: int,
    ) -> dict[str, Decimal]:
        """Obtém o fechamento anterior após normalizar bancos legados."""
        ano_anterior = ano - 1 if mes == 1 else ano
        mes_anterior = 12 if mes == 1 else mes - 1
        movimentos_db = self.repository.movimentos.get_by_meses(
            ano_anterior,
            [mes_anterior],
        )
        ultimos_por_banco: dict[
            str,
            tuple[tuple[date, int, int], Decimal],
        ] = {}

        for movimento_db, movimento in zip(
            movimentos_db,
            self._normalizar_movimentos_persistidos(movimentos_db),
        ):
            if movimento.saldo is None:
                continue
            banco = movimento.banco_origem.strip().lower()
            if not banco:
                continue
            ordem = (
                movimento.data_movimento,
                movimento_db.linha_origem or 0,
                movimento_db.id or 0,
            )
            anterior = ultimos_por_banco.get(banco)
            if anterior is None or ordem > anterior[0]:
                ultimos_por_banco[banco] = (ordem, movimento.saldo)

        return {banco: saldo for banco, (_, saldo) in ultimos_por_banco.items()}

    def _resolver_meses(
        self,
        competencia: str,
        meses_incluir: list[int] | None = None,
        ano_todo: bool = False,
    ) -> tuple[int, int, list[int], list[int], str]:
        ano, mes = self._parse_competencia(competencia)
        disponiveis = self.repository.get_meses_disponiveis(ano)
        if self._tem_saldo_ano_anterior(ano):
            disponiveis = sorted({1, *disponiveis})

        meses_solicitados = self._normalizar_meses(meses_incluir)
        if ano_todo:
            meses_utilizados = [m for m in range(1, mes + 1) if m in disponiveis]
            estrategia = "ano_todo"
        elif meses_solicitados:
            meses_utilizados = [m for m in meses_solicitados if m in disponiveis]
            estrategia = "meses_incluir"
        else:
            meses_utilizados = [mes] if mes in disponiveis else []
            estrategia = "competencia"

        return ano, mes, disponiveis, meses_utilizados, estrategia

    def _tem_saldo_ano_anterior(self, ano: int) -> bool:
        indicadores = self.indicadores_manuais.get_by_ano(ano)
        return bool(
            indicadores
            and indicadores.saldo_ano_anterior
            and indicadores.saldo_ano_anterior != Decimal("0")
        )

    def verificar_dados(
        self,
        competencia: str,
        meses_incluir: list[int] | None = None,
        ano_todo: bool = False,
    ) -> dict[str, Any]:
        ano, mes, disponiveis, meses_utilizados, estrategia = self._resolver_meses(
            competencia,
            meses_incluir=meses_incluir,
            ano_todo=ano_todo,
        )
        solicitados = self._normalizar_meses(meses_incluir) or (
            [mes] if not ano_todo else list(range(1, mes + 1))
        )
        faltantes = [m for m in solicitados if m not in disponiveis]

        return {
            "valido": bool(meses_utilizados) and not faltantes,
            "competencia": competencia,
            "ano": ano,
            "mes": mes,
            "estrategia_meses": estrategia,
            "ano_todo": ano_todo,
            "meses_disponiveis": disponiveis,
            "meses_solicitados": solicitados,
            "meses_utilizados": meses_utilizados,
            "meses_faltantes": faltantes,
            "error": (
                "Nenhum mês selecionado possui dados salvos no banco."
                if not meses_utilizados
                else f"Mês(es) sem dados no banco: {', '.join(f'{m:02d}' for m in faltantes)}."
                if faltantes
                else None
            ),
        }

    def gerar_arquivo(
        self,
        competencia: str,
        meses_incluir: list[int] | None = None,
        ano_todo: bool = False,
    ) -> dict[str, Any]:
        verificacao = self.verificar_dados(
            competencia,
            meses_incluir=meses_incluir,
            ano_todo=ano_todo,
        )
        if not verificacao["valido"]:
            raise ValueError(verificacao.get("error") or "Dados insuficientes para geração.")

        ano = int(verificacao["ano"])
        meses_utilizados = list(verificacao["meses_utilizados"])
        movimentos_db = self.repository.movimentos.get_by_meses(ano, meses_utilizados)
        movimentos = self._normalizar_movimentos_persistidos(movimentos_db)
        saldos_iniciais_por_banco = self._obter_saldos_iniciais_por_banco(
            ano,
            min(meses_utilizados),
        )
        indicadores_manuais = self.indicadores_manuais.get_by_ano(ano)
        saldo_ano_anterior_cadastrado = (
            indicadores_manuais.saldo_ano_anterior if indicadores_manuais else None
        )
        saldo_ano_anterior = saldo_ano_anterior_cadastrado if 1 in meses_utilizados else None
        lote = FCLote(
            periodo=competencia,
            arquivos_origem=sorted(
                {mov.arquivo_origem for mov in movimentos if mov.arquivo_origem}
            ),
            bancos=sorted({mov.banco_origem for mov in movimentos}),
            movimentos=movimentos,
        )

        nome_saida = self.exporter.gerar_nome_saida(
            FlowType.FLUXO_CAIXA,
            competencia.replace("/", "-").replace("\\", "-").strip(),
        )
        output_path = self.exporter.caminho_saida(nome_saida)
        totais_saida = self.processamento._escrever_template(
            lote,
            output_path,
            meses_visiveis=meses_utilizados,
            preservar_historico=False,
            saldo_ano_anterior=saldo_ano_anterior,
            saldos_iniciais_por_banco=saldos_iniciais_por_banco,
        )

        total_creditos = lote.total_creditos
        total_debitos = lote.total_debitos
        meses_ocultos = [m for m in range(1, 13) if m not in meses_utilizados]
        bancos_identificados = sorted({mov.banco_origem for mov in movimentos})
        bancos_sem_conciliacao = [
            banco
            for banco in bancos_identificados
            if banco.strip().lower() in {"desconhecido", "sem banco", ""}
        ]
        avisos_conciliacao = (
            [
                "Existem movimentos com banco de origem desconhecido. "
                "O saldo financeiro geral foi calculado, mas a conciliação por banco "
                "precisa ser revisada."
            ]
            if bancos_sem_conciliacao
            else []
        )
        conciliacao_transferencias = conciliar_transferencias(movimentos)
        warnings = []
        if bancos_sem_conciliacao:
            warnings.append(
                {
                    "campo": "banco",
                    "mensagem": avisos_conciliacao[0],
                    "severidade": "warning",
                    "sugestao": "Reingeste os arquivos com nomes bancários reconhecíveis.",
                }
            )
        if conciliacao_transferencias["nao_pareadas"]:
            warnings.append(
                {
                    "campo": "transferencias",
                    "mensagem": (
                        f"{conciliacao_transferencias['nao_pareadas']} transferência(s) "
                        "estão sem contrapartida conciliada, mas continuam neutras no saldo geral."
                    ),
                    "severidade": "warning",
                    "sugestao": "Confira os extratos dos bancos envolvidos e a conta 2.1.",
                }
            )

        return {
            "arquivo_saida": output_path.name,
            "output_path": str(output_path),
            "download_url": f"/api/fluxo_caixa/download/{output_path.name}",
            "total_movimentos": len(movimentos),
            "total_lancamentos": len(movimentos),
            "total_creditos": self._valor_monetario(total_creditos),
            "total_debitos": self._valor_monetario(total_debitos),
            "saldo_liquido": self._valor_monetario(total_creditos - total_debitos),
            "saldo_ano_anterior": self._valor_monetario(saldo_ano_anterior),
            "saldo_com_ano_anterior": self._valor_monetario(
                (saldo_ano_anterior or 0) + total_creditos - total_debitos
            ),
            "total_creditos_apresentacao": self._valor_monetario(totais_saida["creditos"]),
            "total_debitos_apresentacao": self._valor_monetario(totais_saida["debitos"]),
            "saldo_liquido_apresentacao": self._valor_monetario(totais_saida["saldo_liquido"]),
            "fonte_dados": "db",
            "estrategia_meses": verificacao["estrategia_meses"],
            "ano_todo": bool(ano_todo),
            "meses_incluir": self._normalizar_meses(meses_incluir),
            "meses_disponiveis": verificacao["meses_disponiveis"],
            "meses_utilizados": meses_utilizados,
            "meses_solicitados": verificacao["meses_solicitados"],
            "meses_ocultos": meses_ocultos,
            "bancos_identificados": bancos_identificados,
            "bancos_sem_conciliacao": bancos_sem_conciliacao,
            "avisos_conciliacao": avisos_conciliacao,
            "conciliacao_transferencias": conciliacao_transferencias,
            "warnings": warnings,
        }
