"""Resolução complexa de filtro por centro de custo (obra).

O filtro de obra deve encontrar a linha mesmo quando o termo informado difere
da grafia armazenada (acentos, caixa, pontuação, ordem das palavras ou apenas
parte do nome). A resolução é feita em camadas, da mais estrita para a mais
permissiva, retornando os valores ORIGINAIS de centro de custo que casam.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


def normalizar_centro_custo(value: object) -> str:
    """Normaliza para comparação: maiúsculas, sem acento/pontuação, espaços simples."""
    texto = "" if value is None else str(value)
    texto = unicodedata.normalize("NFKD", texto.upper())
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    return " ".join(texto.split())


def resolver_centros_custo(termo: str, candidatos: Iterable[str]) -> list[str]:
    """Resolve o termo de filtro para os centros de custo reais correspondentes.

    Estratégia em camadas (usa o primeiro nível que produzir resultado):
        1. Igualdade normalizada.
        2. Todos os tokens do termo presentes no centro (ordem livre).
        3. Substring normalizada (termo no centro ou centro no termo).

    Returns:
        Lista de valores originais de centro de custo que casam, sem duplicar e
        preservando a ordem de entrada. Vazia quando nada corresponde.
    """
    termo_norm = normalizar_centro_custo(termo)
    if not termo_norm:
        return []

    # Preserva ordem e remove candidatos vazios/duplicados.
    unicos: list[str] = []
    vistos: set[str] = set()
    for candidato in candidatos:
        if candidato is None:
            continue
        bruto = str(candidato).strip()
        if bruto and bruto not in vistos:
            vistos.add(bruto)
            unicos.append(bruto)

    normalizados = {original: normalizar_centro_custo(original) for original in unicos}
    termo_tokens = set(termo_norm.split())

    exatos = [orig for orig, norm in normalizados.items() if norm == termo_norm]
    if exatos:
        return exatos

    por_tokens = [
        orig
        for orig, norm in normalizados.items()
        if norm and termo_tokens.issubset(set(norm.split()))
    ]
    if por_tokens:
        return por_tokens

    por_substring = [
        orig
        for orig, norm in normalizados.items()
        if norm and (termo_norm in norm or norm in termo_norm)
    ]
    return por_substring
