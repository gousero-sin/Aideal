"""Parser genérico para arquivos Excel de entrada (.xls e .xlsx)."""

import json
import logging
from pathlib import Path

import pandas as pd

from ..config import settings

logger = logging.getLogger(__name__)


class ExcelParser:
    """Lê e normaliza arquivos Excel de entrada para DataFrames padronizados."""

    def __init__(self, flow_type: str):
        self.flow_type = flow_type
        self.mapping = self._load_mapping()

    def _load_mapping(self) -> dict:
        mapping_file = f"{self.flow_type}_mapping.json"
        mapping_path = settings.config_dir / mapping_file
        with open(mapping_path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _normalizar_texto_cabecalho(value) -> str:
        if pd.isna(value) or value is None:
            return ""
        return " ".join(str(value).replace("\n", " ").strip().lower().split())

    def _detectar_linha_cabecalho_fluxo(self, df_raw: pd.DataFrame) -> int | None:
        """Detecta automaticamente linha de cabeçalho para relatórios de fluxo.

        Os relatórios operacionais de banco costumam ter metadados nas primeiras
        linhas e o cabeçalho real entre as linhas 10-12.
        """
        colunas_cfg = self.mapping["entrada"]["colunas"]
        obrigatorias = set(self.mapping["validacao"]["colunas_obrigatorias_minimas"])

        aliases_por_campo: dict[str, set[str]] = {}
        for campo, cfg in colunas_cfg.items():
            aliases_por_campo[campo] = {
                self._normalizar_texto_cabecalho(alias)
                for alias in cfg.get("aliases", [])
                if self._normalizar_texto_cabecalho(alias)
            }

        melhor_linha: int | None = None
        melhor_score: tuple[int, int] = (0, 0)  # (hits obrigatórios, hits totais)

        limite = min(len(df_raw), 80)
        for idx in range(limite):
            tokens = {
                self._normalizar_texto_cabecalho(v)
                for v in df_raw.iloc[idx].tolist()
                if self._normalizar_texto_cabecalho(v)
            }
            if not tokens:
                continue

            hits_obrigatorios = 0
            hits_totais = 0
            for campo, aliases in aliases_por_campo.items():
                if any(alias in tokens for alias in aliases):
                    hits_totais += 1
                    if campo in obrigatorias:
                        hits_obrigatorios += 1

            score = (hits_obrigatorios, hits_totais)
            if score > melhor_score:
                melhor_score = score
                melhor_linha = idx

        # Exige match mínimo para evitar escolher linha de metadados.
        if melhor_linha is not None and melhor_score[0] >= 2 and melhor_score[1] >= 3:
            return melhor_linha
        return None

    def ler_arquivo(self, filepath: Path) -> dict:
        """Lê um arquivo Excel e retorna dict com info de abas e DataFrames.

        Returns:
            dict com chaves:
                - abas: list[str] — nomes das abas
                - dados: dict[str, pd.DataFrame] — DataFrame por aba
                - arquivo: str — nome do arquivo
                - formato: str — extensão do arquivo
        """
        filepath = Path(filepath)
        ext = filepath.suffix.lower()

        if ext not in self.mapping["entrada"]["formatos_aceitos"]:
            raise ValueError(
                f"Formato '{ext}' não aceito. "
                f"Formatos válidos: {self.mapping['entrada']['formatos_aceitos']}"
            )

        engine = "xlrd" if ext == ".xls" else "openpyxl"

        xls = pd.ExcelFile(filepath, engine=engine)
        abas = xls.sheet_names

        dados = {}
        for aba in abas:
            try:
                if self.flow_type == "fluxo":
                    df_raw = pd.read_excel(
                        xls,
                        sheet_name=aba,
                        header=None,
                    )
                    linha_detectada = self._detectar_linha_cabecalho_fluxo(df_raw)
                    linha_cfg = self.mapping["entrada"].get("linha_cabecalho", 0)
                    linha_cabecalho = linha_detectada if linha_detectada is not None else linha_cfg

                    if linha_cabecalho is not None:
                        headers = df_raw.iloc[linha_cabecalho].tolist()
                        df = df_raw.iloc[linha_cabecalho + 1 :].copy()
                        df.columns = headers
                        df = df.reset_index(drop=True)
                    else:
                        df = df_raw
                else:
                    df = pd.read_excel(
                        xls,
                        sheet_name=aba,
                        header=self.mapping["entrada"].get("linha_cabecalho", 0),
                    )
                dados[aba] = df
            except Exception as e:
                logger.warning(f"Erro ao ler aba '{aba}' de '{filepath.name}': {e}")
                dados[aba] = pd.DataFrame()

        logger.info(
            f"Arquivo '{filepath.name}' lido: {len(abas)} aba(s), "
            f"formato {ext}"
        )

        return {
            "abas": abas,
            "dados": dados,
            "arquivo": filepath.name,
            "formato": ext,
        }

    def detectar_aba_principal(self, dados: dict) -> str:
        """Detecta a aba principal com base na estratégia de detecção configurada."""
        abas = dados.get("abas") or []
        if not abas:
            raise ValueError("Arquivo sem abas/sheets detectadas.")

        estrategia = self.mapping["entrada"].get("aba_principal_detectar_por")
        aba_fixa = self.mapping["entrada"].get("aba_principal")

        if aba_fixa and aba_fixa in abas:
            return aba_fixa

        if estrategia == "maior_numero_linhas":
            max_linhas = 0
            aba_principal = abas[0]
            for aba, df in dados["dados"].items():
                if len(df) > max_linhas:
                    max_linhas = len(df)
                    aba_principal = aba
            return aba_principal

        return abas[0]

    def mapear_colunas(self, df: pd.DataFrame) -> dict[str, str | None]:
        """Mapeia colunas do DataFrame para os campos normalizados usando aliases.

        Returns:
            dict mapeando campo_normalizado -> nome_coluna_encontrada (ou None)
        """
        colunas_config = self.mapping["entrada"]["colunas"]
        # Normalizar nomes de colunas (remover quebras de linha e espaços extras)
        colunas_df_raw = list(df.columns)
        colunas_df_norm = [str(c).replace("\n", " ").strip() for c in colunas_df_raw]
        mapeamento = {}

        for campo, config in colunas_config.items():
            encontrada = None
            for alias in config["aliases"]:
                alias_norm = alias.replace("\n", " ").strip().lower()
                for raw, norm in zip(colunas_df_raw, colunas_df_norm):
                    if norm.lower() == alias_norm:
                        encontrada = raw
                        break
                if encontrada:
                    break
            mapeamento[campo] = encontrada

        return mapeamento

    def detectar_banco(self, nome_arquivo: str) -> str | None:
        """Detecta o banco de origem a partir do nome do arquivo (fluxo de caixa)."""
        if self.flow_type != "fluxo":
            return None

        bancos = self.mapping["entrada"].get("bancos_conhecidos", {})
        nome_upper = nome_arquivo.upper()

        for banco_id, config in bancos.items():
            for pattern in config.get("detectar_por_nome_arquivo", []):
                if pattern.upper() in nome_upper:
                    return banco_id

        return "desconhecido"
