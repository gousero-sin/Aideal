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
from ..validacao.codigos_gerenciais import extrair_codigo_gerencial, montar_rotulo_gerencial

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


def _optional_decimal(value) -> Decimal | None:
    """Converte saldo opcional sem perder o fechamento bancário igual a zero."""
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    return _safe_decimal(value)


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


def _safe_codigo_gerencial(value) -> str:
    """Normaliza código gerencial vindo de texto combinado ou coluna dedicada."""
    texto = _safe_str(value)
    if not texto:
        return ""

    codigo = extrair_codigo_gerencial(texto)
    if codigo:
        return codigo

    match = re.fullmatch(r"\d+(?:\.\d+)*", texto)
    return match.group(0) if match else ""


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


def _extrair_classificacao_valida(value, aceitar_numero_solto: bool = True) -> str:
    """Extrai classificação apenas quando o valor parece um indicador válido.

    Args:
        aceitar_numero_solto: quando ``True`` aceita ``"1"``/``"2"`` isolados
            como flag. Deve ser ``False`` ao varrer colunas arbitrárias, para
            não confundir uma célula numérica qualquer com a flag.
    """
    texto = _safe_str(value).upper()
    if not texto:
        return ""

    texto = texto.replace("SAÍDA", "SAIDA").replace("–", "-")
    texto = " ".join(texto.split())

    entrada = bool(re.fullmatch(r"1\s*-\s*ENTRADA", texto)) or texto == "ENTRADA"
    saida = bool(re.fullmatch(r"2\s*-\s*SAIDA", texto)) or texto == "SAIDA"
    if aceitar_numero_solto:
        entrada = entrada or texto == "1"
        saida = saida or texto == "2"

    if entrada:
        return "1 - ENTRADA"
    if saida:
        return "2 - SAIDA"
    return ""


def _detectar_indicador_classif(row: pd.Series, col_classif: str | None) -> str:
    """Detecta a flag ENTRADA/SAIDA na linha, sem depender do título da coluna.

    A flag (``1 - ENTRADA`` / ``2 - SAIDA``) é a fonte de verdade onde quer que
    apareça na linha. Primeiro tenta a coluna Classificação mapeada (aceitando
    ``1``/``2`` isolados); se vazia, varre as demais colunas aceitando apenas o
    padrão textual completo, evitando falso positivo de colunas numéricas.
    """
    if col_classif:
        cls = _extrair_classificacao_valida(row.get(col_classif))
        if cls:
            return cls

    for valor in row:
        cls = _extrair_classificacao_valida(valor, aceitar_numero_solto=False)
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
                    valor_bruto=valor,
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
        col_liquido = mapeamento.get("total_liquido")  # valor líquido da linha
        col_nat = mapeamento.get("natureza")  # C. gerencial — o que vai na col F
        # A flag (1 - ENTRADA / 2 - SAIDA) determina crédito/débito.
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

        # Classificação ENTRADA/SAIDA pela flag (1 - ENTRADA / 2 - SAIDA),
        # detectada na linha independentemente do título da coluna.
        classificacao_str = _detectar_indicador_classif(row, col_classif)
        if not classificacao_str:
            # Sem flag válida, a linha não pode ser classificada e é ignorada.
            return None

        # Havendo flag, usa o valor líquido da linha; se vazio, cai para o bruto.
        valor_liquido = _safe_decimal(row.get(col_liquido)) if col_liquido else Decimal("0")
        valor_bruto = _safe_decimal(row.get(col_cred) if col_cred else 0)
        valor = valor_liquido if valor_liquido != 0 else valor_bruto
        credito, debito = classificar_valores(valor, classificacao_str)

        return DRELancamento(
            data=data,
            historico=historico,
            valor_bruto=valor_bruto,
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
                row.get(mapeamento.get("rubrica", "")) if mapeamento.get("rubrica") else None
            ),
            conta_pai=_safe_str(
                row.get(mapeamento.get("conta_pai", "")) if mapeamento.get("conta_pai") else None
            ),
            linha_origem=idx + 2,
            aba_origem=aba,
        )


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
                    row, mapeamento, idx, aba_principal, banco_origem, dados_arquivo["arquivo"]
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
        self, row: pd.Series, mapeamento: dict, idx: int, aba: str, banco: str, arquivo: str
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
        classificacao = self._conta_gerencial_canonica(row, mapeamento)
        conta_gerencial = classificacao
        if self._eh_transferencia(row, mapeamento, descricao):
            if tipo == TipoMovimento.DEBITO:
                classificacao = "Transferência Emitida"
            elif tipo == TipoMovimento.CREDITO:
                classificacao = "Transferência Recebida"
            tipo = TipoMovimento.TRANSFERENCIA

        return FCMovimento(
            data_movimento=data,
            tipo=tipo,
            descricao=descricao,
            valor=valor,
            saldo=_optional_decimal(
                row.get(mapeamento.get("saldo", "")) if mapeamento.get("saldo") else None
            ),
            classificacao=classificacao,
            conta_gerencial=conta_gerencial,
            banco_origem=banco,
            arquivo_origem=arquivo,
            linha_origem=idx + 2,
            aba_origem=aba,
        )

    @staticmethod
    def _conta_gerencial_canonica(row: pd.Series, mapeamento: dict) -> str:
        col_classificacao = mapeamento.get("classificacao")
        nome = _safe_str(row.get(col_classificacao) if col_classificacao else None)

        col_codigo = mapeamento.get("codigo_conta_gerencial")
        codigo = _safe_codigo_gerencial(row.get(col_codigo) if col_codigo else None)
        if codigo and nome:
            return montar_rotulo_gerencial(codigo, nome)
        if codigo:
            return codigo
        return nome

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
