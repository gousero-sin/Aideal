"""Validadores estruturais para arquivos de entrada DRE e Fluxo de Caixa.

Política de erro (Apêndice B):
- Erro de estrutura de entrada: bloquear e informar coluna/aba ausente.
- Erro de mapeamento de classificação: bloquear e listar pendências.
- Erro de consistência numérica: bloquear e apresentar reconciliação mínima.
- Warning de qualidade: permitir geração, registrando no log.
"""

import logging
import re
import unicodedata

import pandas as pd

from ..contracts.common import ErrorSeverity, ValidationError
from ..contracts.dre import DREValidationResult
from ..contracts.fluxo_caixa import FCValidationResult
from ..ingestao.parser import ExcelParser

logger = logging.getLogger(__name__)


class BaseValidator:
    """Validador base com lógica compartilhada."""

    def __init__(self, parser: ExcelParser):
        self.parser = parser
        self.mapping = parser.mapping

    def _validar_formato(self, filepath_ext: str) -> list[ValidationError]:
        formatos = self.mapping["entrada"]["formatos_aceitos"]
        if filepath_ext.lower() not in formatos:
            return [
                ValidationError(
                    campo="formato",
                    mensagem=f"Formato '{filepath_ext}' não suportado. Use: {formatos}",
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao=f"Converta o arquivo para um dos formatos: {', '.join(formatos)}",
                )
            ]
        return []

    def _validar_abas(
        self, abas_encontradas: list[str], aba_esperada: str | None
    ) -> list[ValidationError]:
        if not abas_encontradas:
            return [
                ValidationError(
                    campo="abas",
                    mensagem="Arquivo sem abas/sheets detectadas.",
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao="Verifique se o arquivo Excel não está corrompido.",
                )
            ]
        if aba_esperada and aba_esperada not in abas_encontradas:
            return [
                ValidationError(
                    campo="abas",
                    mensagem=(
                        f"Aba esperada '{aba_esperada}' não encontrada. "
                        f"Abas: {abas_encontradas}"
                    ),
                    severidade=ErrorSeverity.WARNING,
                    sugestao="O sistema tentará detectar a aba principal automaticamente.",
                )
            ]
        return []

    def _validar_colunas_obrigatorias(
        self, mapeamento: dict[str, str | None], colunas_obrigatorias: list[str]
    ) -> list[ValidationError]:
        erros = []
        for campo in colunas_obrigatorias:
            if mapeamento.get(campo) is None:
                aliases = self.mapping["entrada"]["colunas"].get(campo, {}).get("aliases", [])
                erros.append(
                    ValidationError(
                        campo=campo,
                        mensagem=f"Coluna obrigatória '{campo}' não encontrada no arquivo.",
                        severidade=ErrorSeverity.BLOQUEANTE,
                        sugestao=(
                            "Verifique se o arquivo possui uma das colunas: "
                            f"{', '.join(aliases[:5])}"
                        ),
                    )
                )
        return erros

    def _validar_dados_vazios(self, df: pd.DataFrame, aba: str) -> list[ValidationError]:
        if df.empty:
            return [
                ValidationError(
                    campo="dados",
                    mensagem=f"Aba '{aba}' está vazia ou sem dados válidos.",
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao="Verifique se a planilha contém dados na aba principal.",
                )
            ]
        return []

    @staticmethod
    def _normalizar_texto(valor) -> str:
        """Normaliza texto para comparações estruturais de cabeçalho."""
        if pd.isna(valor) or valor is None:
            return ""
        return str(valor).replace("\n", " ").strip().lower()

    def _mask_linhas_cabecalho_repetido(
        self, df: pd.DataFrame, mapeamento: dict[str, str | None]
    ) -> pd.Series:
        """Detecta linhas onde o cabeçalho foi repetido no corpo da planilha."""
        mask = pd.Series(False, index=df.index)
        for coluna in mapeamento.values():
            if coluna is None or coluna not in df.columns:
                continue
            nome_coluna = self._normalizar_texto(coluna)
            valores = df[coluna].map(self._normalizar_texto)
            mask |= valores == nome_coluna
        return mask

    @staticmethod
    def _mask_linhas_rodape_relatorio(df: pd.DataFrame) -> pd.Series:
        """Detecta linhas estruturais de rodapé que não representam lançamentos.

        Ex.: "Filtros utilizados:" e linha descritiva com parâmetros aplicados.
        """
        if df.empty:
            return pd.Series(False, index=df.index)

        padroes_rodape = (
            "filtros utilizados",
            "empresa:",
            "conta banc",
            "data inicial:",
            "data final:",
        )

        texto_linhas = (
            df.fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
            .str.replace("\n", " ", regex=False)
            .str.strip()
            .str.lower()
        )
        mask = pd.Series(False, index=df.index)
        for padrao in padroes_rodape:
            mask |= texto_linhas.str.contains(padrao, regex=False, na=False)
        return mask

    @staticmethod
    def _mask_placeholder(serie: pd.Series) -> pd.Series:
        """Marca valores vazios/placeholders que não devem gerar warning de tipo."""
        placeholders = {"", "-", "--", "n/a", "na", "none", "null", "nan"}
        texto = (
            serie.fillna("")
            .astype(str)
            .str.replace("\n", " ", regex=False)
            .str.strip()
            .str.lower()
        )
        return texto.isin(placeholders)

    @staticmethod
    def _mask_rotulo_estrutural(serie: pd.Series) -> pd.Series:
        """Marca rótulos de seção (ex.: '2 - SAIDA') em colunas numéricas opcionais."""
        texto = (
            serie.fillna("")
            .astype(str)
            .str.replace("\n", " ", regex=False)
            .str.strip()
            .str.upper()
        )
        return texto.str.match(r"^\d+\s*-\s*[A-ZÀ-Ü ]+$", na=False)

    @staticmethod
    def _coerce_decimal(serie: pd.Series) -> pd.Series:
        """Converte série para numérico aceitando vírgula como separador decimal."""
        direto = pd.to_numeric(serie, errors="coerce")

        texto = (
            serie.fillna("")
            .astype(str)
            .str.replace(" ", "", regex=False)
            .str.strip()
        )
        mask_milhar = texto.str.contains(",", na=False) & texto.str.contains(".", na=False)
        texto = texto.where(~mask_milhar, texto.str.replace(".", "", regex=False))
        texto = texto.str.replace(",", ".", regex=False)
        ajustado = pd.to_numeric(texto, errors="coerce")

        return direto.fillna(ajustado)

    @staticmethod
    def _normalizar_classificacao(valor) -> str:
        """Normaliza classificação/natureza para comparação por dicionário."""
        if pd.isna(valor) or valor is None:
            return ""
        texto = str(valor).strip().upper()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
        texto = " ".join(texto.split())
        return texto

    def _validar_tipos_dados(
        self, df: pd.DataFrame, mapeamento: dict[str, str | None]
    ) -> list[ValidationError]:
        warnings = []
        colunas_config = self.mapping["entrada"]["colunas"]
        mask_cabecalho_repetido = self._mask_linhas_cabecalho_repetido(df, mapeamento)
        mask_rodape_relatorio = self._mask_linhas_rodape_relatorio(df)

        for campo, coluna in mapeamento.items():
            if coluna is None or coluna not in df.columns:
                continue

            config = colunas_config.get(campo, {})
            tipo = config.get("tipo")
            obrigatorio = bool(config.get("obrigatorio", False))
            serie = df[coluna]
            mask_ignorar = (
                self._mask_placeholder(serie)
                | mask_cabecalho_repetido
                | mask_rodape_relatorio
            )

            if tipo == "decimal":
                non_numeric = self._coerce_decimal(serie).isna() & ~mask_ignorar

                # Em campos opcionais, ignorar rótulos estruturais de seção.
                if not obrigatorio:
                    non_numeric = non_numeric & ~self._mask_rotulo_estrutural(serie)

                count = non_numeric.sum()
                if count > 0:
                    warnings.append(
                        ValidationError(
                            campo=campo,
                            mensagem=f"Coluna '{coluna}' possui {count} valor(es) não numérico(s).",
                            severidade=ErrorSeverity.WARNING,
                            sugestao="Valores não numéricos serão tratados como zero.",
                        )
                    )

            elif tipo == "date":
                non_date = (
                    pd.to_datetime(serie, errors="coerce", dayfirst=True).isna() & ~mask_ignorar
                )
                count = non_date.sum()
                if count > 0:
                    warnings.append(
                        ValidationError(
                            campo=campo,
                            mensagem=(
                                f"Coluna '{coluna}' possui {count} valor(es) com formato "
                                "de data inválido."
                            ),
                            severidade=ErrorSeverity.WARNING,
                            sugestao="Verifique o formato das datas (DD/MM/AAAA esperado).",
                        )
                    )

        return warnings


class DREValidator(BaseValidator):
    """Validador específico para arquivos de entrada DRE."""

    def __init__(self):
        super().__init__(ExcelParser("dre"))

    def validar(
        self,
        dados_arquivo: dict,
        competencia: str | None = None,
        modo_cumulativo: bool | None = None,
    ) -> DREValidationResult:
        """Valida estrutura completa de um arquivo DRE.

        Args:
            dados_arquivo: dict retornado por ExcelParser.ler_arquivo()

        Returns:
            DREValidationResult com status e lista de erros/warnings
        """
        result = DREValidationResult(
            arquivo=dados_arquivo["arquivo"],
            abas_encontradas=dados_arquivo["abas"],
        )

        # 1. Validar formato
        erros_formato = self._validar_formato(dados_arquivo["formato"])
        result.erros.extend(erros_formato)

        # 2. Validar abas
        aba_esperada = self.mapping["entrada"].get("aba_principal")
        erros_abas = self._validar_abas(dados_arquivo["abas"], aba_esperada)
        for e in erros_abas:
            if e.severidade == ErrorSeverity.BLOQUEANTE:
                result.erros.append(e)
            else:
                result.warnings.append(e)
        if any(e.severidade == ErrorSeverity.BLOQUEANTE for e in erros_abas):
            result.valido = False
            return result

        if self._parece_template_saida(dados_arquivo):
            result.erros.append(
                ValidationError(
                    campo="arquivo",
                    mensagem=(
                        "O arquivo enviado parece ser um template/saida final do DRE "
                        "(workbook AIDEAL) e nao um relatorio bruto de entrada."
                    ),
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao=(
                        "Use o arquivo bruto de origem (ex.: RELATORIO DRE MES 05.xls/.xlsx) "
                        "para validar e gerar o DRE final."
                    ),
                )
            )
            result.valido = False
            return result

        # 3. Detectar aba principal e validar colunas
        aba_principal = self.parser.detectar_aba_principal(dados_arquivo)
        df = dados_arquivo["dados"].get(aba_principal, pd.DataFrame())

        erros_vazios = self._validar_dados_vazios(df, aba_principal)
        result.erros.extend(erros_vazios)

        if not df.empty:
            result.total_linhas = len(df)
            result.colunas_encontradas = [str(c) for c in df.columns]

            mapeamento = self.parser.mapear_colunas(df)
            obrigatorias = self.mapping["validacao"]["colunas_obrigatorias_minimas"]
            result.colunas_esperadas = obrigatorias

            erros_colunas = self._validar_colunas_obrigatorias(mapeamento, obrigatorias)
            result.erros.extend(erros_colunas)

            warnings_tipos = self._validar_tipos_dados(df, mapeamento)
            result.warnings.extend(warnings_tipos)
            erros_classificacao = self._validar_classificacao_mapeada(df, mapeamento)
            result.erros.extend(erros_classificacao)
            metadata_periodo, erros_periodo = self._validar_periodo_cumulativo(
                df=df,
                mapeamento=mapeamento,
                competencia=competencia,
                modo_cumulativo_override=modo_cumulativo,
            )
            result.metadata.update(metadata_periodo)
            result.erros.extend(erros_periodo)

        result.valido = len(result.erros) == 0

        logger.info(
            f"Validação DRE '{dados_arquivo['arquivo']}': "
            f"{'VÁLIDO' if result.valido else 'INVÁLIDO'} "
            f"({len(result.erros)} erro(s), {len(result.warnings)} warning(s))"
        )

        return result

    @staticmethod
    def _parse_competencia(competencia: str | None) -> tuple[int, int] | None:
        if not competencia:
            return None
        texto = str(competencia).strip()
        match = re.match(r"^(\d{1,2})[/-](\d{4})$", texto)
        if not match:
            return None
        mes = int(match.group(1))
        ano = int(match.group(2))
        if mes < 1 or mes > 12:
            return None
        return mes, ano

    @staticmethod
    def _fmt_meses(meses: list[int]) -> str:
        if not meses:
            return "-"
        return ", ".join(f"{m:02d}" for m in meses)

    def _validar_periodo_cumulativo(
        self,
        df: pd.DataFrame,
        mapeamento: dict[str, str | None],
        competencia: str | None,
        modo_cumulativo_override: bool | None = None,
    ) -> tuple[dict[str, object], list[ValidationError]]:
        """Valida se o dataset DRE atende ao modo cumulativo Jan..competencia."""
        cfg_validacao = self.mapping.get("validacao", {})
        if modo_cumulativo_override is None:
            modo_cumulativo = bool(cfg_validacao.get("modo_cumulativo", False))
        else:
            modo_cumulativo = bool(modo_cumulativo_override)

        metadata: dict[str, object] = {
            "dre_periodo_modo_cumulativo": modo_cumulativo,
            "dre_periodo_competencia": competencia or "",
            "dre_periodo_anos_encontrados": [],
            "dre_periodo_meses_encontrados_ano_competencia": [],
            "dre_periodo_meses_esperados_ano_competencia": [],
            "dre_periodo_meses_faltantes_ano_competencia": [],
            "dre_periodo_meses_acima_competencia": [],
            "dre_periodo_contagem_linhas_por_mes_ano_competencia": {},
            "dre_periodo_data_min": None,
            "dre_periodo_data_max": None,
        }
        if not modo_cumulativo:
            return metadata, []

        parsed = self._parse_competencia(competencia)
        if parsed is None:
            return metadata, [
                ValidationError(
                    campo="competencia",
                    mensagem=(
                        "Competencia invalida para modo cumulativo. "
                        "Use o formato MM/AAAA."
                    ),
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao="Exemplo valido: 05/2025.",
                )
            ]

        competencia_mes, competencia_ano = parsed
        metadata["dre_periodo_ano_competencia"] = competencia_ano
        metadata["dre_periodo_mes_competencia"] = competencia_mes

        coluna_data = mapeamento.get("data")
        if coluna_data is None or coluna_data not in df.columns:
            return metadata, []

        serie_data = df[coluna_data]
        mask_ignorar = self._mask_placeholder(serie_data) | self._mask_linhas_cabecalho_repetido(
            df, mapeamento
        )
        datas = pd.to_datetime(serie_data, errors="coerce", dayfirst=True)
        datas_validas = datas[(~mask_ignorar) & datas.notna()]
        if datas_validas.empty:
            return metadata, []

        data_min = datas_validas.min()
        data_max = datas_validas.max()
        metadata["dre_periodo_data_min"] = data_min.strftime("%d/%m/%Y")
        metadata["dre_periodo_data_max"] = data_max.strftime("%d/%m/%Y")

        anos_encontrados = sorted(int(v) for v in datas_validas.dt.year.unique())
        metadata["dre_periodo_anos_encontrados"] = anos_encontrados

        datas_ano_competencia = datas_validas[datas_validas.dt.year == competencia_ano]
        meses_encontrados = sorted(int(v) for v in datas_ano_competencia.dt.month.unique())
        metadata["dre_periodo_meses_encontrados_ano_competencia"] = meses_encontrados
        contagem_por_mes = (
            datas_ano_competencia.dt.month.value_counts().sort_index().astype(int).to_dict()
        )
        metadata["dre_periodo_contagem_linhas_por_mes_ano_competencia"] = {
            str(k): int(v) for k, v in contagem_por_mes.items()
        }

        meses_esperados = list(range(1, competencia_mes + 1))
        metadata["dre_periodo_meses_esperados_ano_competencia"] = meses_esperados

        meses_faltantes = [m for m in meses_esperados if m not in meses_encontrados]
        metadata["dre_periodo_meses_faltantes_ano_competencia"] = meses_faltantes

        meses_acima = [m for m in meses_encontrados if m > competencia_mes]
        metadata["dre_periodo_meses_acima_competencia"] = meses_acima

        erros: list[ValidationError] = []
        anos_divergentes = [a for a in anos_encontrados if a != competencia_ano]
        if anos_divergentes and cfg_validacao.get("bloquear_ano_divergente_competencia", True):
            erros.append(
                ValidationError(
                    campo="competencia",
                    mensagem=(
                        f"Arquivo possui ano(s) divergente(s) da competencia {competencia}: "
                        f"{', '.join(str(a) for a in anos_divergentes)}."
                    ),
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao=(
                        "Use arquivo cumulativo somente do mesmo ano da competencia "
                        "(jan..mes atual)."
                    ),
                )
            )

        if meses_acima and cfg_validacao.get("bloquear_mes_superior_competencia", True):
            detalhes = ", ".join(
                f"{m:02d} ({contagem_por_mes.get(m, 0)} linha(s))" for m in meses_acima
            )
            erros.append(
                ValidationError(
                    campo="competencia",
                    mensagem=(
                        f"Arquivo possui mes(es) acima da competencia {competencia}: "
                        f"{detalhes}."
                    ),
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao="Ajuste a competencia ou envie arquivo ate o mes informado.",
                )
            )

        exigir_desde_janeiro = cfg_validacao.get("exigir_meses_desde_janeiro", True)
        if (
            exigir_desde_janeiro
            and meses_faltantes
            and cfg_validacao.get("bloquear_meses_faltantes", True)
        ):
            erros.append(
                ValidationError(
                    campo="competencia",
                    mensagem=(
                        f"Modo cumulativo exige meses 01..{competencia_mes:02d}/{competencia_ano}. "
                        f"Meses encontrados: {self._fmt_meses(meses_encontrados)}. "
                        f"Meses faltantes: {self._fmt_meses(meses_faltantes)}."
                    ),
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao=(
                        "Envie um arquivo acumulado do ano (jan ate a competencia), "
                        "ou reduza a competencia para o ultimo mes disponivel."
                    ),
                )
            )

        return metadata, erros

    @staticmethod
    def _parece_template_saida(dados_arquivo: dict) -> bool:
        abas = set(dados_arquivo.get("abas") or [])
        assinatura_template = {"Painel", "DRE", "BD_FLUXO", "PLANO_CONTAS", "APOIO"}
        return assinatura_template.issubset(abas)

    def _validar_classificacao_mapeada(
        self, df: pd.DataFrame, mapeamento: dict[str, str | None]
    ) -> list[ValidationError]:
        """Valida classificação/natureza contra dicionário configurado."""
        validacao_cfg = self.mapping.get("validacao", {})
        if not validacao_cfg.get("bloquear_natureza_nao_mapeada", False):
            return []

        naturezas_cfg = validacao_cfg.get("naturezas_mapeadas", {})
        if not naturezas_cfg:
            return []

        # Usa classificacao_entrada_saida (coluna CLASSIFICAÇÃO) para validar ENTRADA/SAIDA
        # Fallback para classificacao e depois natureza (compatibilidade com arquivos simples)
        coluna = (
            mapeamento.get("classificacao_entrada_saida")
            or mapeamento.get("classificacao")
            or mapeamento.get("natureza")
        )
        if coluna is None or coluna not in df.columns:
            return []

        serie = df[coluna]
        mask_ignorar = self._mask_placeholder(serie) | self._mask_linhas_cabecalho_repetido(
            df, mapeamento
        )
        normalizado = serie.map(self._normalizar_classificacao)

        permitidas: set[str] = set()
        for chave, aliases in naturezas_cfg.items():
            if chave:
                permitidas.add(self._normalizar_classificacao(chave))
            if isinstance(aliases, list):
                for alias in aliases:
                    permitidas.add(self._normalizar_classificacao(alias))

        if not permitidas:
            return []

        mask_invalida = (~mask_ignorar) & (~normalizado.isin(permitidas))
        total_invalidos = int(mask_invalida.sum())
        if total_invalidos == 0:
            return []

        invalidos = sorted(v for v in normalizado[mask_invalida].unique().tolist() if v)[:8]
        msg = (
            f"Coluna '{coluna}' possui {total_invalidos} linha(s) com classificação/natureza "
            "não mapeada."
        )
        return [
            ValidationError(
                campo="natureza",
                mensagem=msg,
                severidade=ErrorSeverity.BLOQUEANTE,
                sugestao=(
                    "Atualize o dicionário 'validacao.naturezas_mapeadas' no dre_mapping.json. "
                    f"Exemplos não mapeados: {', '.join(invalidos)}"
                ),
            )
        ]


class FluxoCaixaValidator(BaseValidator):
    """Validador específico para arquivos de entrada do Fluxo de Caixa."""

    def __init__(self):
        super().__init__(ExcelParser("fluxo"))

    def validar(self, dados_arquivo: dict) -> FCValidationResult:
        """Valida estrutura de um arquivo do Fluxo de Caixa."""
        result = FCValidationResult(
            arquivos=[dados_arquivo["arquivo"]],
        )

        erros_formato = self._validar_formato(dados_arquivo["formato"])
        result.erros.extend(erros_formato)

        aba_esperada = self.mapping["entrada"].get("aba_principal")
        erros_abas = self._validar_abas(dados_arquivo["abas"], aba_esperada)
        for e in erros_abas:
            if e.severidade == ErrorSeverity.BLOQUEANTE:
                result.erros.append(e)
            else:
                result.warnings.append(e)
        if any(e.severidade == ErrorSeverity.BLOQUEANTE for e in erros_abas):
            result.valido = False
            return result

        aba_principal = self.parser.detectar_aba_principal(dados_arquivo)
        df = dados_arquivo["dados"].get(aba_principal, pd.DataFrame())

        erros_vazios = self._validar_dados_vazios(df, aba_principal)
        result.erros.extend(erros_vazios)

        if not df.empty:
            result.colunas_encontradas[dados_arquivo["arquivo"]] = [str(c) for c in df.columns]
            result.total_linhas_por_arquivo[dados_arquivo["arquivo"]] = len(df)

            mapeamento = self.parser.mapear_colunas(df)
            obrigatorias = self.mapping["validacao"]["colunas_obrigatorias_minimas"]
            result.colunas_esperadas = obrigatorias

            erros_colunas = self._validar_colunas_obrigatorias(mapeamento, obrigatorias)
            result.erros.extend(erros_colunas)

            warnings_tipos = self._validar_tipos_dados(df, mapeamento)
            result.warnings.extend(warnings_tipos)

            # Detectar banco de origem
            banco = self.parser.detectar_banco(dados_arquivo["arquivo"])
            if banco:
                result.bancos_identificados.append(banco)

        result.valido = len(result.erros) == 0

        logger.info(
            f"Validação FC '{dados_arquivo['arquivo']}': "
            f"{'VÁLIDO' if result.valido else 'INVÁLIDO'} "
            f"({len(result.erros)} erro(s), {len(result.warnings)} warning(s))"
        )

        return result

    def validar_lote(self, lista_dados: list[dict]) -> FCValidationResult:
        """Valida múltiplos arquivos do Fluxo de Caixa em lote."""
        result_final = FCValidationResult()
        arquivos_ignorados: list[str] = []
        algum_arquivo_valido = False

        for dados in lista_dados:
            result_individual = self.validar(dados)
            result_final.arquivos.extend(result_individual.arquivos)
            if result_individual.colunas_esperadas:
                result_final.colunas_esperadas = result_individual.colunas_esperadas
            result_final.colunas_encontradas.update(result_individual.colunas_encontradas)
            result_final.total_linhas_por_arquivo.update(result_individual.total_linhas_por_arquivo)
            result_final.warnings.extend(result_individual.warnings)

            if result_individual.erros and self._deve_ignorar_arquivo_por_estrutura(
                result_individual.erros
            ):
                arquivo = dados.get("arquivo", "arquivo")
                arquivos_ignorados.append(arquivo)
                result_final.warnings.append(self._warning_arquivo_ignorado(arquivo))
                continue

            result_final.bancos_identificados.extend(result_individual.bancos_identificados)
            result_final.erros.extend(result_individual.erros)
            if result_individual.valido:
                algum_arquivo_valido = True

        if arquivos_ignorados and not algum_arquivo_valido:
            result_final.erros.append(
                ValidationError(
                    campo="arquivos",
                    mensagem="Nenhum arquivo válido para validação do Fluxo de Caixa.",
                    severidade=ErrorSeverity.BLOQUEANTE,
                    sugestao=(
                        "Envie ao menos um relatório de movimento bancário com lançamentos "
                        "para o mês selecionado."
                    ),
                )
            )

        result_final.valido = len(result_final.erros) == 0
        return result_final

    @staticmethod
    def _deve_ignorar_arquivo_por_estrutura(erros: list[ValidationError]) -> bool:
        """Permite tratar relatórios sem grade de movimentos como warning no lote."""
        if not erros:
            return False

        campos_obrigatorios = {"data_movimento", "descricao", "valor"}
        for erro in erros:
            if erro.severidade != ErrorSeverity.BLOQUEANTE:
                return False
            if erro.campo not in campos_obrigatorios:
                return False
            if "coluna obrigatória" not in erro.mensagem.lower():
                return False
        return True

    @staticmethod
    def _warning_arquivo_ignorado(arquivo: str) -> ValidationError:
        return ValidationError(
            campo="arquivo",
            mensagem=(
                f"Arquivo '{arquivo}' foi ignorado por não possuir estrutura de "
                "movimento bancário."
            ),
            severidade=ErrorSeverity.WARNING,
            sugestao=(
                "Se o relatório contém 'Nenhum registro encontrado', ele pode ser mantido "
                "no lote; o consolidado será gerado com os demais extratos válidos."
            ),
        )
