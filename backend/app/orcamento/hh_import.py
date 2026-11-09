"""Importa a planilha "MODELO COMPOSIÇÃO DE CUSTO" (.xlsx) para o bloco HH do orçamento.

Lê apenas as células de entrada (funções, quantidades, salários, custos mensais, encargos e BDI);
os totais são sempre recalculados pelo sistema. Fórmulas valem pelo valor salvo no arquivo.
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from io import BytesIO
from typing import Any

from .exceptions import InvalidOrcamentoInputError
from .hh import CUSTO_COLUNAS, ENCARGOS_PADRAO, TRIBUTOS_PADRAO, normalize_hh

MAX_ARQUIVO_BYTES = 5 * 1024 * 1024
# O modelo real tem ~95 KB compactado, ~470 KB descompactado e nenhuma parte acima de
# 130 KB. Os limites por parte barram
# planilhas "infladas" (milhões de células/estilos) que custariam GB de RAM ao openpyxl.
MAX_DESCOMPACTADO_BYTES = 8 * 1024 * 1024
MAX_PARTE_BYTES = 2 * 1024 * 1024
MAX_PARTES = 300
MAX_LINHAS = 600
PERICULOSIDADE_PLANILHA = 30.0
MAX_COLUNAS = 120


def _chave(texto: Any) -> str:
    """Compara rótulos sem acento, caixa ou espaços repetidos."""
    if not isinstance(texto, str):
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(char for char in sem_acento if not unicodedata.combining(char))
    return " ".join(sem_acento.casefold().replace("\n", " ").split())


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        limpo = valor.strip().rstrip(".").replace("R$", "").replace(" ", "")
        if re.fullmatch(r"\d{1,3}(\.\d{3})*(,\d+)?", limpo):
            limpo = limpo.replace(".", "").replace(",", ".")
        else:
            limpo = limpo.replace(",", ".")
        try:
            return float(limpo)
        except ValueError:
            return None
    return None


def _percentual(valor: Any) -> float:
    """Planilha guarda 20% como 0,2; valores acima de 1 já estão em pontos percentuais."""
    numero = _numero(valor)
    if numero is None:
        return 0.0
    return round(numero * 100, 8) if abs(numero) <= 1 else numero


def _validar_zip(conteudo: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(conteudo)) as arquivo:
            partes = arquivo.infolist()
    except zipfile.BadZipFile as exc:
        raise InvalidOrcamentoInputError("Arquivo não é uma planilha .xlsx válida") from exc
    if (
        len(partes) > MAX_PARTES
        or sum(info.file_size for info in partes) > MAX_DESCOMPACTADO_BYTES
        or any(info.file_size > MAX_PARTE_BYTES for info in partes)
    ):
        raise InvalidOrcamentoInputError("Planilha grande demais para importação")


def _linhas(planilha) -> list[tuple[Any, ...]]:
    return [
        tuple(linha)
        for linha in planilha.iter_rows(
            max_row=MAX_LINHAS, max_col=MAX_COLUNAS, values_only=True
        )
    ]


def _aba(livro, *trechos: str):
    for planilha in livro.worksheets:
        nome = _chave(planilha.title)
        if any(trecho in nome for trecho in trechos):
            return planilha
    return None


def _composicao(linhas: list[tuple[Any, ...]]) -> dict[str, Any]:
    cabecalho = next(
        (indice for indice, linha in enumerate(linhas)
         if any(_chave(valor) == "funcao" for valor in linha)),
        None,
    )
    if cabecalho is None:
        raise InvalidOrcamentoInputError("Cabeçalho FUNÇÃO não encontrado na composição")
    titulos = linhas[cabecalho]
    colunas: dict[str, int] = {}
    custos_por_rotulo = {_chave(label): coluna_id for coluna_id, label, _ in CUSTO_COLUNAS}
    for indice, titulo in enumerate(titulos):
        chave = _chave(titulo)
        if chave == "funcao":
            colunas["label"] = indice
        elif chave.startswith("qtde"):
            colunas["quantidade"] = indice
        elif chave.startswith("horas trabalhadas"):
            colunas["horas_mes"] = indice
        elif chave.startswith("salario base"):
            colunas["salario_base"] = indice
        elif chave.startswith("periculosidade"):
            colunas["periculosidade"] = indice
        elif "noturno" in chave and "adic" in chave:
            colunas["noturno"] = indice
        elif chave in custos_por_rotulo:
            colunas[custos_por_rotulo[chave]] = indice
        elif chave.startswith("total estimado"):
            meses = re.search(r"(\d+)\s*mes", chave)
            if meses:
                colunas["_meses"] = int(meses.group(1))
    if "salario_base" not in colunas or "quantidade" not in colunas:
        raise InvalidOrcamentoInputError("Colunas de quantidade e salário não encontradas")

    def celula(linha: tuple[Any, ...], chave: str) -> Any:
        indice = colunas.get(chave)
        return linha[indice] if indice is not None and indice < len(linha) else None

    grupos: list[dict[str, Any]] = []
    for linha in linhas[cabecalho + 2:]:
        rotulo = celula(linha, "label")
        if isinstance(rotulo, str) and _chave(rotulo).startswith("total geral"):
            break
        if not isinstance(rotulo, str) or not rotulo.strip():
            continue
        salario = _numero(celula(linha, "salario_base"))
        if salario is None and _numero(celula(linha, "quantidade")) is None:
            grupos.append({"id": f"grupo_{len(grupos) + 1}", "label": rotulo.strip(),
                           "funcoes": []})
            continue
        if not grupos:
            grupos.append({"id": "grupo_1", "label": "Funções", "funcoes": []})
        funcoes = grupos[-1]["funcoes"]
        # Na planilha: H = SE(G = 30%; salário × 30%; 0). Outro percentual não gera adicional.
        incidencia = _percentual(celula(linha, "periculosidade"))
        periculosidade = abs(incidencia - PERICULOSIDADE_PLANILHA) < 1e-6
        funcoes.append({
            "id": f"{grupos[-1]['id']}_funcao_{len(funcoes) + 1}",
            "label": rotulo.strip(),
            "quantidade": _numero(celula(linha, "quantidade")) or 0.0,
            "horas_mes": _numero(celula(linha, "horas_mes")) or 220.0,
            "salario_base": salario or 0.0,
            "periculosidade": periculosidade,
            "adicional_noturno_percent": _percentual(celula(linha, "noturno")),
            "custos": {
                coluna_id: _numero(celula(linha, coluna_id)) or 0.0
                for coluna_id, _label, _base in CUSTO_COLUNAS
            },
        })
    grupos = [grupo for grupo in grupos if grupo["funcoes"]]
    if not grupos:
        raise InvalidOrcamentoInputError("Nenhuma função encontrada na composição")
    resultado: dict[str, Any] = {"grupos": grupos}
    if "_meses" in colunas:
        resultado["meses"] = float(colunas["_meses"])
    for linha in linhas[:cabecalho]:
        for indice, valor in enumerate(linha[:-1]):
            if _chave(valor) == "% noturno":
                resultado["percentual_noturno"] = _percentual(linha[indice + 1])
            elif _chave(valor) == "salario minimo":
                minimo = _numero(linha[indice + 1])
                if minimo is not None:
                    resultado["salario_minimo"] = minimo
    return resultado


def _encargos(linhas: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    ids = {item_id for item_id, *_ in ENCARGOS_PADRAO}
    valores: dict[str, float] = {}
    for linha in linhas:
        textos = [_chave(valor) for valor in linha]
        codigo = next((texto for texto in textos if re.fullmatch(r"[abc]\.\d+\*?", texto)), None)
        numeros = [_numero(valor) for valor in linha if _numero(valor) is not None]
        if codigo:
            item_id = codigo.replace(".", "").rstrip("*")
            if item_id in ids:
                valores[item_id] = _percentual(numeros[0]) if numeros else 0.0
    return [{"id": item_id, "percent": valores.get(item_id, 0.0)} for item_id in ids
            if item_id in valores] if valores else []


def _bdi(linhas: list[tuple[Any, ...]]) -> dict[str, Any]:
    tributos_por_rotulo = {"iss": "iss", "pis": "pis", "cofins": "cofins", "csll": "csll",
                           "i.r.": "ir", "ir": "ir", "irpj": "ir"}
    bdi: dict[str, float] = {}
    tributos: dict[str, float] = {}
    for linha in linhas:
        rotulo = next((_chave(valor) for valor in linha if isinstance(valor, str)), "")
        numeros = [_numero(valor) for valor in linha
                   if not isinstance(valor, str) and _numero(valor) is not None]
        if not numeros:
            continue
        rotulo_limpo = re.sub(r"^\d+\s+", "", rotulo)
        if rotulo_limpo.startswith("lucro"):
            bdi["lucro_percent"] = _percentual(numeros[0])
        elif rotulo_limpo.startswith("despesas indiretas"):
            bdi["despesas_indiretas_percent"] = _percentual(numeros[0])
        elif rotulo_limpo in tributos_por_rotulo:
            tributos[tributos_por_rotulo[rotulo_limpo]] = _percentual(numeros[0])
    resultado: dict[str, Any] = {}
    if bdi:
        resultado["bdi"] = bdi
    if tributos:
        resultado["tributos"] = [
            {"id": item_id, "percent": tributos.get(item_id, 0.0)}
            for item_id, _label, _padrao in TRIBUTOS_PADRAO
        ]
    return resultado


def import_hh_workbook(conteudo: bytes) -> dict[str, Any]:
    """Converte o .xlsx no bloco HH validado; recusa arquivos fora do formato esperado."""
    if not conteudo:
        raise InvalidOrcamentoInputError("Envie a planilha .xlsx")
    if len(conteudo) > MAX_ARQUIVO_BYTES:
        raise InvalidOrcamentoInputError("Planilha excede 5 MB")
    _validar_zip(conteudo)
    from openpyxl import load_workbook

    try:
        livro = load_workbook(BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl levanta tipos variados para arquivos corrompidos
        raise InvalidOrcamentoInputError("Não foi possível ler a planilha .xlsx") from exc
    try:
        if not livro.worksheets:
            raise InvalidOrcamentoInputError("A planilha não tem abas para importar")
        composicao = _aba(livro, "composicao") or livro.worksheets[0]
        payload = _composicao(_linhas(composicao))
        encargos = _aba(livro, "encargo")
        if encargos is not None:
            itens = _encargos(_linhas(encargos))
            if itens:
                payload["encargos"] = itens
        bdi = _aba(livro, "bdi")
        if bdi is not None:
            payload.update(_bdi(_linhas(bdi)))
    except InvalidOrcamentoInputError:
        raise
    except Exception as exc:  # read_only lê as abas sob demanda: XML quebrado aparece aqui
        raise InvalidOrcamentoInputError("Não foi possível ler a planilha .xlsx") from exc
    finally:
        livro.close()
    return normalize_hh(payload)
