"""Engine de transformação — converte DataFrames brutos em contratos normalizados."""

import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd

from ..contracts.common import ErrorSeverity, ValidationError
from ..contracts.dre import DRELancamento, DRELote
from ..contracts.fluxo_caixa import FCLote, FCMovimento, TipoMovimento
from ..ingestao.parser import ExcelParser

logger = logging.getLogger(__name__)

_IMPOSTOS_ENTRADA: tuple[tuple[str, str], ...] = (
    ("ir", "IR"),
    ("iss", "ISS"),
    ("inss", "INSS"),
    ("pis", "PIS"),
    ("cofins", "COFINS"),
    ("csll", "CSLL"),
    ("tarifa_antecipacao", "Tarifa de Antecipação"),
)

_BANCO_ALIASES: dict[str, tuple[str, ...]] = {
    "itau_isolamento": ("ITAU ISOLAMENTO", "ITAÚ ISOLAMENTO", "ITAU ISOL", "ITAÚ ISOL"),
    "itau": ("ITAU", "ITAÚ"),
    "cef": ("CEF", "CAIXA", "CAIXA ECONOMICA"),
    "safra": ("SAFRA",),
    "mercantil": ("MERCANTIL", "MARCANTIL"),
}


def _safe_decimal(value) -> Decimal:
    """Converte valor para Decimal de forma segura."""
    if pd.isna(value) or value is None or str(value).strip() == "":
        return Decimal("0")
    try:
        texto = str(value).replace(" ", "").strip()
        if "," in texto and "." in texto:
            texto = texto.replace(".", "")
        texto = texto.replace(",", ".")
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _safe_date(value):
    """Converte valor para date de forma segura."""
    if pd.isna(value) or value is None:
        return None
    try:
        dt = pd.to_datetime(value, dayfirst=True)
        return dt.date()
    except Exception:
        return None


def _safe_str(value) -> str:
    """Converte valor para string de forma segura."""
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def _normalizar_ascii(value) -> str:
    texto = _safe_str(value).upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    return " ".join(texto.split())


def _identificar_banco_lado_transferencia(value: str) -> str | None:
    texto = _normalizar_ascii(value)
    texto = re.sub(r"\b(BANCO|BANCOS)\b", " ", texto)
    texto = " ".join(texto.split())

    for banco_id, aliases in _BANCO_ALIASES.items():
        aliases_norm = {_normalizar_ascii(alias) for alias in aliases}
        if texto in aliases_norm:
            return banco_id
    return None


def classificar_valores(valor: Decimal, natureza: str) -> tuple[Decimal, Decimal]:
    """Aplica a regra de saída do DRE por classificação/natureza."""
    natureza_normalizada = _safe_str(natureza).upper()
    valor_absoluto = abs(valor)

    if "SAIDA" in natureza_normalizada:
        return Decimal("0"), valor_absoluto
    return valor_absoluto, Decimal("0")


def _extrair_classificacao_valida(value) -> str:
    """Extrai classificação apenas quando o valor parece um indicador válido."""
    texto = _safe_str(value).upper()
    if not texto:
        return ""

    texto = texto.replace("SAÍDA", "SAIDA").replace("–", "-")
    texto = " ".join(texto.split())

    if texto == "ENTRADA" or texto == "1" or re.fullmatch(r"1\s*-\s*ENTRADA", texto):
        return "1 - ENTRADA"
    if texto == "SAIDA" or texto == "2" or re.fullmatch(r"2\s*-\s*SAIDA", texto):
        return "2 - SAIDA"
    return ""


def _detectar_indicador_classif(row: pd.Series, col_classif: str | None) -> str:
    """Detecta o indicador ENTRADA/SAIDA mesmo quando em coluna alternativa.

    Alguns relatórios (ex: linhas de folha de pagamento) colocam '2 - SAIDA'
    na coluna IR em vez da coluna CLASSIFICAÇÃO. Verifica todas as colunas
    string do row como fallback.
    """
    if col_classif:
        cls = _extrair_classificacao_valida(row.get(col_classif))
        if cls:
            return cls

    # Fallback: procura por tokens válidos em outras colunas.
    for col_val in row:
        cls = _extrair_classificacao_valida(col_val)
        if cls:
            return cls

    return ""


class DRETransformer:
    """Transforma dados brutos DRE em lote normalizado."""

    def __init__(self):
        self.parser = ExcelParser("dre")
        self.erros: list[ValidationError] = []

    def transformar(self, dados_arquivo: dict, competencia: str) -> DRELote:
        """Transforma dados brutos em DRELote normalizado.

        Args:
            dados_arquivo: dict retornado por ExcelParser.ler_arquivo()
            competencia: mês/ano de referência (MM/AAAA)

        Returns:
            DRELote com lançamentos normalizados
        """
        self.erros = []
        aba_principal = self.parser.detectar_aba_principal(dados_arquivo)
        df = dados_arquivo["dados"][aba_principal]
        mapeamento = self.parser.mapear_colunas(df)

        lote = DRELote(
            competencia=competencia,
            arquivo_origem=dados_arquivo["arquivo"],
        )

        for idx, row in df.iterrows():
            try:
                lancamento = self._converter_linha(row, mapeamento, idx, aba_principal)
                if lancamento:
                    lote.lancamentos.append(lancamento)
                    lote.lancamentos.extend(
                        self._converter_impostos_linha(
                            row=row,
                            mapeamento=mapeamento,
                            idx=idx,
                            aba=aba_principal,
                            lanc_base=lancamento,
                        )
                    )
            except Exception as e:
                self.erros.append(
                    ValidationError(
                        campo="linha",
                        mensagem=f"Erro ao processar linha {idx + 2}: {e}",
                        severidade=ErrorSeverity.WARNING,
                        linha=idx + 2,
                        aba=aba_principal,
                    )
                )

        logger.info(
            f"DRE transformado: {lote.total_registros} lançamentos, "
            f"{len(self.erros)} erro(s) de conversão"
        )
        return lote

    def _converter_impostos_linha(
        self,
        row: pd.Series,
        mapeamento: dict[str, str | None],
        idx: int,
        aba: str,
        lanc_base: DRELancamento,
    ) -> list[DRELancamento]:
        """Expande colunas de impostos em lançamentos de débito.

        Quando presentes no arquivo de entrada (ex.: aba "Sheet" do relatório DRE),
        IR/ISS/INSS/PIS/COFINS/CSLL/Tarifa devem virar lançamentos próprios no BD.
        """
        impostos: list[DRELancamento] = []

        for campo, rotulo in _IMPOSTOS_ENTRADA:
            coluna = mapeamento.get(campo)
            if not coluna:
                continue

            valor = _safe_decimal(row.get(coluna))
            if valor <= 0:
                continue

            impostos.append(
                DRELancamento(
                    data=lanc_base.data,
                    historico=lanc_base.historico,
                    credito=Decimal("0"),
                    debito=valor,
                    natureza=rotulo,
                    classificacao_entrada_saida="2 - SAIDA",
                    centro_custo=lanc_base.centro_custo,
                    rubrica=rotulo,
                    conta_pai=lanc_base.conta_pai,
                    linha_origem=idx + 2,
                    aba_origem=aba,
                )
            )

        return impostos

    def _converter_linha(
        self, row: pd.Series, mapeamento: dict, idx: int, aba: str
    ) -> DRELancamento | None:
        col_data = mapeamento.get("data")
        col_hist = mapeamento.get("historico")  # Descri. — fallback only
        col_cred = mapeamento.get("credito")
        col_nat = mapeamento.get("natureza")    # C. gerencial — o que vai na col F
        # CLASSIFICAÇÃO determina crédito/débito.
        col_classif = mapeamento.get("classificacao_entrada_saida")
        col_cliente = mapeamento.get("cliente")
        col_num = mapeamento.get("numero")

        data = _safe_date(row.get(col_data) if col_data else None)
        if data is None:
            return None

        # Historico: "Número - Cliente" é o formato do template; usa Descri. como fallback final
        numero = _safe_str(row.get(col_num) if col_num else None)
        cliente = _safe_str(row.get(col_cliente) if col_cliente else None)
        descr = _safe_str(row.get(col_hist) if col_hist else None)

        if numero and cliente:
            historico = f"{numero} - {cliente}"
        elif cliente:
            historico = cliente
        elif descr:
            historico = descr
        else:
            return None  # Linha sem identificação útil

        # Natureza = código C. gerencial (ex: "1.1.1 - Recebimento de Clientes")
        natureza = _safe_str(row.get(col_nat) if col_nat else None)

        # Classificação ENTRADA/SAIDA — usa detector com fallback para outras colunas
        # (algumas linhas de SAIDA colocam '2 - SAIDA' em coluna diferente de CLASSIFICAÇÃO)
        classificacao_str = _detectar_indicador_classif(row, col_classif)
        if not classificacao_str:
            classificacao_str = self._inferir_classificacao_por_natureza(natureza)

        valor_bruto = _safe_decimal(row.get(col_cred) if col_cred else 0)
        credito, debito = classificar_valores(valor_bruto, classificacao_str)

        return DRELancamento(
            data=data,
            historico=historico,
            credito=credito,
            debito=debito,
            natureza=natureza,
            classificacao_entrada_saida=classificacao_str,
            centro_custo=_safe_str(
                row.get(mapeamento.get("centro_custo", ""))
                if mapeamento.get("centro_custo")
                else None
            ),
            rubrica=_safe_str(
                row.get(mapeamento.get("rubrica", ""))
                if mapeamento.get("rubrica")
                else None
            ),
            conta_pai=_safe_str(
                row.get(mapeamento.get("conta_pai", ""))
                if mapeamento.get("conta_pai")
                else None
            ),
            linha_origem=idx + 2,
            aba_origem=aba,
        )

    @staticmethod
    def _inferir_classificacao_por_natureza(natureza: str) -> str:
        """Infere ENTRADA/SAIDA quando CLASSIFICAÇÃO não foi preenchida."""
        natureza_upper = _safe_str(natureza).upper()
        if not natureza_upper:
            return ""

        marcadores_entrada = (
            "ENTRADA",
            "RECEBIMENTO",
            "RECEITA",
        )
        if any(term in natureza_upper for term in marcadores_entrada):
            return "1 - ENTRADA"

        marcadores_saida = (
            "SAIDA",
            "SAÍDA",
            "PARCELAMENTO",
            "DESPESA",
            "CUSTO",
            "GASTO",
            "INVEST",
            "PAGAMENTO",
            "IMPOST",
            "JUROS",
            "SALARIO",
            "INSS",
            "ISS",
            "PIS",
            "COFINS",
            "CSLL",
            "IRPJ",
            "IR ",
        )
        if any(term in natureza_upper for term in marcadores_saida):
            return "2 - SAIDA"

        return ""


class FluxoCaixaTransformer:
    """Transforma dados brutos de Fluxo de Caixa em lote normalizado."""

    def __init__(self):
        self.parser = ExcelParser("fluxo")
        self.erros: list[ValidationError] = []

    def transformar(self, dados_arquivo: dict, banco_origem: str, periodo: str) -> FCLote:
        """Transforma dados brutos de um arquivo em FCLote.

        Args:
            dados_arquivo: dict retornado por ExcelParser.ler_arquivo()
            banco_origem: identificação do banco
            periodo: período de referência (MM/AAAA)

        Returns:
            FCLote com movimentos normalizados
        """
        self.erros = []
        aba_principal = self.parser.detectar_aba_principal(dados_arquivo)
        df = dados_arquivo["dados"][aba_principal]
        mapeamento = self.parser.mapear_colunas(df)

        lote = FCLote(
            periodo=periodo,
            arquivos_origem=[dados_arquivo["arquivo"]],
            bancos=[banco_origem],
        )

        for idx, row in df.iterrows():
            try:
                movimento = self._converter_linha(
                    row, mapeamento, idx, aba_principal,
                    banco_origem, dados_arquivo["arquivo"]
                )
                if movimento:
                    lote.movimentos.append(movimento)
            except Exception as e:
                self.erros.append(
                    ValidationError(
                        campo="linha",
                        mensagem=f"Erro ao processar linha {idx + 2}: {e}",
                        severidade=ErrorSeverity.WARNING,
                        linha=idx + 2,
                        aba=aba_principal,
                    )
                )

        logger.info(
            f"FC transformado ({banco_origem}): {lote.total_registros} movimentos, "
            f"{len(self.erros)} erro(s) de conversão"
        )
        return lote

    def _converter_linha(
        self, row: pd.Series, mapeamento: dict, idx: int,
        aba: str, banco: str, arquivo: str
    ) -> FCMovimento | None:
        col_data = mapeamento.get("data_movimento")
        col_desc = mapeamento.get("descricao")
        col_valor = mapeamento.get("valor")

        data = _safe_date(row.get(col_data) if col_data else None)
        if data is None:
            return None

        descricao = _safe_str(row.get(col_desc) if col_desc else None)
        valor = _safe_decimal(row.get(col_valor) if col_valor else 0)

        if valor == Decimal("0") and not descricao:
            return None

        tipo = self._inferir_tipo(row, mapeamento, valor, descricao, banco)
        classificacao = _safe_str(
            row.get(mapeamento.get("classificacao", ""))
            if mapeamento.get("classificacao")
            else None
        )
        conta_gerencial = classificacao
        if self._eh_transferencia(row, mapeamento, descricao):
            if tipo == TipoMovimento.DEBITO:
                classificacao = "Transferência Emitida"
            elif tipo == TipoMovimento.CREDITO:
                classificacao = "Transferência Recebida"

        return FCMovimento(
            data_movimento=data,
            tipo=tipo,
            descricao=descricao,
            valor=valor,
            saldo=_safe_decimal(
                row.get(mapeamento.get("saldo", ""))
                if mapeamento.get("saldo")
                else None
            ) or None,
            classificacao=classificacao,
            conta_gerencial=conta_gerencial,
            banco_origem=banco,
            arquivo_origem=arquivo,
            linha_origem=idx + 2,
            aba_origem=aba,
        )

    def _inferir_tipo(
        self,
        row: pd.Series,
        mapeamento: dict,
        valor: Decimal,
        descricao: str = "",
        banco_origem: str = "",
    ) -> TipoMovimento:
        col_tipo = mapeamento.get("tipo")
        tipo_str = ""
        if col_tipo:
            tipo_raw = _safe_str(row.get(col_tipo))
            tipo_str = (
                tipo_raw.upper()
                .replace("CRÉDITO", "CREDITO")
                .replace("DÉBITO", "DEBITO")
                .replace("TRANSFERÊNCIA", "TRANSFERENCIA")
                .replace("–", "-")
            )

            if "TRANSFER" in tipo_str:
                direcao = self._inferir_transferencia_por_descricao(descricao, banco_origem)
                if direcao:
                    return direcao

                # Relatórios bancários operacionais usam:
                # - "Transferência - BANCO X" => saída (débito)
                # - "Transferência -"          => entrada (crédito)
                if "-" in tipo_str:
                    sufixo = tipo_str.split("-", 1)[1].strip()
                    if sufixo:
                        return TipoMovimento.DEBITO
                return TipoMovimento.CREDITO

            normalizar = self.parser.mapping["consolidacao"]["normalizar_tipo_movimento"]
            for tipo_enum, aliases in normalizar.items():
                aliases_norm = [
                    a.upper()
                    .replace("CRÉDITO", "CREDITO")
                    .replace("DÉBITO", "DEBITO")
                    .replace("TRANSFERÊNCIA", "TRANSFERENCIA")
                    for a in aliases
                ]
                if tipo_str in aliases_norm:
                    return TipoMovimento(tipo_enum)
                # Aceita prefixos como "DEBITO - ...", "CREDITO - ..."
                if any(tipo_str.startswith(f"{alias} -") for alias in aliases_norm):
                    return TipoMovimento(tipo_enum)

            if "DEBITO" in tipo_str:
                return TipoMovimento.DEBITO
            if "CREDITO" in tipo_str:
                return TipoMovimento.CREDITO

        if "TRANSFER" in _normalizar_ascii(descricao):
            direcao = self._inferir_transferencia_por_descricao(descricao, banco_origem)
            if direcao:
                return direcao

        if valor > 0:
            return TipoMovimento.CREDITO
        elif valor < 0:
            return TipoMovimento.DEBITO
        return TipoMovimento.CREDITO

    @staticmethod
    def _eh_transferencia(row: pd.Series, mapeamento: dict, descricao: str) -> bool:
        col_tipo = mapeamento.get("tipo")
        tipo = _safe_str(row.get(col_tipo)) if col_tipo else ""
        return "TRANSFER" in _normalizar_ascii(tipo) or "TRANSFER" in _normalizar_ascii(descricao)

    @staticmethod
    def _inferir_transferencia_por_descricao(
        descricao: str, banco_origem: str
    ) -> TipoMovimento | None:
        texto = _normalizar_ascii(descricao)
        if " X " not in f" {texto} ":
            return None

        texto = re.sub(r"^TRANSFERENCIA ENTRE BANCOS?\s+", "", texto)
        partes = re.split(r"\s+X\s+", texto, maxsplit=1)
        if len(partes) != 2:
            return None

        origem = _identificar_banco_lado_transferencia(partes[0])
        destino = _identificar_banco_lado_transferencia(partes[1])
        banco = banco_origem.lower().strip()

        if origem == banco:
            return TipoMovimento.DEBITO
        if destino == banco:
            return TipoMovimento.CREDITO
        return None
