"""Detecção automática de competência a partir dos arquivos enviados."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from ..ingestao.parser import ExcelParser

MESES_NOMES = {
    "JAN": 1,
    "JANEIRO": 1,
    "FEV": 2,
    "FEVEREIRO": 2,
    "MAR": 3,
    "MARCO": 3,
    "MARÇO": 3,
    "ABR": 4,
    "ABRIL": 4,
    "MAI": 5,
    "MAIO": 5,
    "JUN": 6,
    "JUNHO": 6,
    "JUL": 7,
    "JULHO": 7,
    "AGO": 8,
    "AGOSTO": 8,
    "SET": 9,
    "SETEMBRO": 9,
    "OUT": 10,
    "OUTUBRO": 10,
    "NOV": 11,
    "NOVEMBRO": 11,
    "DEZ": 12,
    "DEZEMBRO": 12,
}


def _normalizar_texto(value: str) -> str:
    texto = unicodedata.normalize("NFKD", value.upper())
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", texto).split())


def _fmt_competencia(ano: int, mes: int) -> str:
    return f"{mes:02d}/{ano}"


def _fmt_input(ano: int, mes: int) -> str:
    return f"{ano}-{mes:02d}"


class CompetenciaDetectorService:
    """Detecta a competência mais provável por datas do arquivo ou nome."""

    def detectar(self, fluxo: str, arquivos: list[tuple[Path, str]]) -> dict[str, Any]:
        if fluxo not in {"dre", "fluxo_caixa"}:
            raise ValueError("Fluxo inválido para detecção de competência.")
        if not arquivos:
            raise ValueError("Envie ao menos um arquivo para detectar a competência.")

        parser = ExcelParser("dre" if fluxo == "dre" else "fluxo")
        campo_data = "data" if fluxo == "dre" else "data_movimento"
        datas: list[pd.Timestamp] = []
        detalhes_arquivos: list[dict[str, Any]] = []

        for path, nome in arquivos:
            file_dates: list[pd.Timestamp] = []
            erro: str | None = None
            try:
                dados = parser.ler_arquivo(path)
                dados["arquivo"] = nome
                file_dates = self._extrair_datas(dados, parser, campo_data)
                datas.extend(file_dates)
            except Exception as exc:
                erro = str(exc)

            fallback = self._detectar_por_nome(nome)
            if not file_dates and fallback:
                ano, mes = fallback
                datas.append(pd.Timestamp(year=ano, month=mes, day=1))

            detalhes_arquivos.append(
                {
                    "arquivo": nome,
                    "datas_detectadas": len(file_dates),
                    "fallback_nome": _fmt_competencia(*fallback) if fallback else None,
                    "erro": erro,
                }
            )

        datas_validas = [data for data in datas if pd.notna(data)]
        if not datas_validas:
            return {
                "success": False,
                "detectado": False,
                "competencia": None,
                "competencia_input": None,
                "ano": None,
                "mes": None,
                "total_datas": 0,
                "meses_encontrados": [],
                "arquivos": detalhes_arquivos,
                "message": "Não foi possível detectar a competência pelo conteúdo do arquivo.",
            }

        contagem = Counter((int(data.year), int(data.month)) for data in datas_validas)
        max_total = max(contagem.values())
        ano, mes = max(periodo for periodo, total in contagem.items() if total == max_total)
        meses_encontrados = [
            {
                "ano": item[0][0],
                "mes": item[0][1],
                "competencia": _fmt_competencia(item[0][0], item[0][1]),
                "total": item[1],
            }
            for item in sorted(contagem.items(), key=lambda kv: (kv[0][0], kv[0][1]))
        ]

        return {
            "success": True,
            "detectado": True,
            "competencia": _fmt_competencia(ano, mes),
            "competencia_input": _fmt_input(ano, mes),
            "ano": ano,
            "mes": mes,
            "total_datas": len(datas_validas),
            "meses_encontrados": meses_encontrados,
            "arquivos": detalhes_arquivos,
            "message": "Competência detectada pelo mês predominante do arquivo.",
        }

    @staticmethod
    def _extrair_datas(
        dados_arquivo: dict[str, Any],
        parser: ExcelParser,
        campo_data: str,
    ) -> list[pd.Timestamp]:
        aba_principal = parser.detectar_aba_principal(dados_arquivo)
        df = dados_arquivo["dados"].get(aba_principal, pd.DataFrame())
        if df.empty:
            return []

        mapeamento = parser.mapear_colunas(df)
        coluna_data = mapeamento.get(campo_data)
        if coluna_data is None or coluna_data not in df.columns:
            return []

        serie = pd.to_datetime(df[coluna_data], errors="coerce", dayfirst=True)
        return [data for data in serie if pd.notna(data)]

    @staticmethod
    def _detectar_por_nome(nome_arquivo: str) -> tuple[int, int] | None:
        texto = _normalizar_texto(Path(nome_arquivo).stem)

        match = re.search(r"\b(20\d{2})\s+([0-1]?\d)\b", texto)
        if match:
            ano = int(match.group(1))
            mes = int(match.group(2))
            if 1 <= mes <= 12:
                return ano, mes

        match = re.search(r"\b([0-1]?\d)\s+(20\d{2})\b", texto)
        if match:
            mes = int(match.group(1))
            ano = int(match.group(2))
            if 1 <= mes <= 12:
                return ano, mes

        for nome_mes, mes in MESES_NOMES.items():
            match = re.search(rf"\b{nome_mes}\b.*\b(20\d{{2}})\b", texto)
            if match:
                return int(match.group(1)), mes

        return None
