"""Apresentação visual da aba DRE nos arquivos gerados.

Aplica, só na saída (o template não muda):

- rótulos da coluna A em caixa alta, sem strip nem espaços extras;
- recuo hierárquico por ``Alignment.indent``.

O recuo nunca vai para o texto: espaços na coluna A quebrariam o
``VLOOKUP($A6, APOIO!...)`` da própria DRE e o ``VLOOKUP(..., DRE!A:A, ...)`` da
APOIO. Caixa alta é segura porque VLOOKUP/MATCH do Excel não diferenciam
maiúsculas, e o código Python compara rótulos com ``_normalizar_rotulo``
(casefold). O cálculo continua chaveado pelo código de conta do PLANO_CONTAS; o
rótulo é só exibição.

O nível vem do estilo do template, nunca do nome da conta:

- rótulo em negrito (totais, contas pai, grupos): recuo atual + 1, o que leva
  os níveis 0, 1 e 2 do template a 1, 2 e 3;
- rótulo sem negrito (rubrica de detalhe): recuo 5, inclusive as rubricas que
  o template deixou com recuo 0 (ex.: AUXILIO MORADIA, Marketing).

Chamar depois de materializar os valores e antes de salvar; a função é
idempotente (o nível final não depende de quantas vezes rodou).
"""

from __future__ import annotations

from typing import Any

from openpyxl.styles import Alignment

DRE_PRIMEIRA_LINHA_DADOS = 6
RECUO_DETALHE = 5
RECUO_MAXIMO_ESTRUTURA = RECUO_DETALHE - 1
_MARCA_APRESENTACAO = "_aideal_apresentacao_dre"


def nivel_recuo(recuo_atual: float | int | None, negrito: bool) -> int:
    """Recuo final de um rótulo da DRE a partir do estilo do template."""
    if not negrito:
        return RECUO_DETALHE
    return min(int(recuo_atual or 0) + 1, RECUO_MAXIMO_ESTRUTURA)


def _alinhamento_com_recuo(atual: Alignment, recuo: int) -> Alignment:
    return Alignment(
        horizontal="left",
        vertical=atual.vertical,
        wrap_text=atual.wrap_text,
        shrink_to_fit=atual.shrink_to_fit,
        text_rotation=atual.text_rotation,
        relativeIndent=atual.relativeIndent,
        justifyLastLine=atual.justifyLastLine,
        readingOrder=atual.readingOrder,
        indent=recuo,
    )


def aplicar_apresentacao_dre(ws: Any) -> dict[str, int]:
    """Caixa alta e recuo hierárquico nos rótulos da aba DRE (linhas >= 6).

    Retorna contagens para log/metadados. Uma segunda chamada sobre o mesmo
    objeto de aba não muda nada (o recuo não é somado de novo).
    """
    if getattr(ws, _MARCA_APRESENTACAO, False):
        return {"rotulos_formatados": 0}

    rotulos = 0
    for linha in range(DRE_PRIMEIRA_LINHA_DADOS, ws.max_row + 1):
        celula = ws.cell(row=linha, column=1)
        valor = celula.value
        if not isinstance(valor, str) or not valor.strip():
            continue
        celula.value = valor.upper()
        recuo = nivel_recuo(celula.alignment.indent, bool(celula.font and celula.font.b))
        celula.alignment = _alinhamento_com_recuo(celula.alignment, recuo)
        rotulos += 1

    setattr(ws, _MARCA_APRESENTACAO, True)
    return {"rotulos_formatados": rotulos}
