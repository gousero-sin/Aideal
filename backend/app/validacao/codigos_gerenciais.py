"""Utilitários para validar e classificar códigos de conta gerencial."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

DEFAULT_CODIGOS_GERENCIAIS_VALIDOS: tuple[str, ...] = tuple(str(i) for i in range(1, 19))
DEFAULT_CODIGOS_GERENCIAIS_ENTRADA: tuple[str, ...] = ("1", "2.2")
_ALOCACAO_PERCENTUAL_RE = re.compile(r"\s*\(\s*\d+(?:[,.]\d+)?\s*%\s*\)\s*$")


@dataclass(frozen=True)
class ContaGerencial:
    codigo: str
    nome: str

    @property
    def rotulo(self) -> str:
        return montar_rotulo_gerencial(self.codigo, self.nome)


def extrair_codigo_gerencial(valor: object) -> str:
    """Extrai códigos como ``11.2`` ou ``1.1.1`` do início do texto."""
    if valor is None:
        return ""
    match = re.match(r"^\s*(\d+(?:\.\d+)+)\b", str(valor).strip())
    return match.group(1) if match else ""


def separar_conta_gerencial(valor: object) -> ContaGerencial | None:
    """Separa ``11.2 - AGUA ADM`` em código e nome gerencial."""
    if valor is None:
        return None

    texto = str(valor).strip().split(";")[0].strip()
    match = re.match(r"^\s*(\d+(?:\.\d+)+)\b(?:\s*[-–—]\s*|\s+)?(.*?)\s*$", texto)
    if not match:
        return None

    codigo = match.group(1)
    nome = _ALOCACAO_PERCENTUAL_RE.sub("", match.group(2)).strip(" -–—\t\r\n")
    nome = re.sub(r"\s+", " ", nome)
    if not nome:
        return None
    return ContaGerencial(codigo=codigo, nome=nome)


def montar_rotulo_gerencial(codigo: str, nome: str) -> str:
    codigo_limpo = str(codigo or "").strip()
    nome_limpo = re.sub(r"\s+", " ", str(nome or "").strip())
    return f"{codigo_limpo} - {nome_limpo}" if nome_limpo else codigo_limpo


def normalizar_rotulos_gerenciais_texto(
    valor: str | None,
    rotulos_por_codigo: dict[str, str],
) -> str | None:
    """Troca nomes por rotulos canonicos, preservando alocacoes percentuais."""
    if valor is None:
        return None

    texto = str(valor).strip()
    if not texto:
        return valor

    segmentos = [segmento.strip() for segmento in texto.split(";") if segmento.strip()]
    if not segmentos:
        return valor

    normalizados: list[str] = []
    alterado = False
    for segmento in segmentos:
        codigo = extrair_codigo_gerencial(segmento)
        rotulo = rotulos_por_codigo.get(codigo)
        if not rotulo:
            normalizados.append(segmento)
            continue

        sufixo_match = _ALOCACAO_PERCENTUAL_RE.search(segmento)
        sufixo = sufixo_match.group(0).strip() if sufixo_match else ""
        normalizado = f"{rotulo} {sufixo}".strip()
        normalizados.append(normalizado)
        alterado = alterado or normalizado != segmento

    if not alterado:
        return valor

    resultado = "; ".join(normalizados)
    if texto.endswith(";"):
        return f"{resultado};"
    return resultado


def codigo_corresponde(codigo: str, prefixo: str) -> bool:
    """Compara por componentes: prefixo ``1`` casa ``1.1``, mas não ``11.1``."""
    codigo = str(codigo or "").strip()
    prefixo = str(prefixo or "").strip()
    return bool(codigo and prefixo and (codigo == prefixo or codigo.startswith(f"{prefixo}.")))


def codigo_gerencial_valido(
    codigo: str,
    codigos_validos: Iterable[str] | None = None,
) -> bool:
    validos = tuple(codigos_validos or DEFAULT_CODIGOS_GERENCIAIS_VALIDOS)
    return any(codigo_corresponde(codigo, prefixo) for prefixo in validos)


def classificar_codigo_gerencial(
    codigo: str,
    codigos_validos: Iterable[str] | None = None,
    codigos_entrada: Iterable[str] | None = None,
) -> str:
    """Retorna ``1 - ENTRADA``, ``2 - SAIDA`` ou vazio quando o código é desconhecido."""
    if not codigo_gerencial_valido(codigo, codigos_validos):
        return ""

    entradas = tuple(codigos_entrada or DEFAULT_CODIGOS_GERENCIAIS_ENTRADA)
    if any(codigo_corresponde(codigo, prefixo) for prefixo in entradas):
        return "1 - ENTRADA"
    return "2 - SAIDA"
