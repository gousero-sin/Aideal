"""Carregamento de template com os pivot caches lidos uma única vez.

No openpyxl 3.1.5, ``ExcelReader.read_worksheets`` consulta a propriedade
``WorkbookParser.pivot_caches`` uma vez por aba, e cada consulta relê e reparsa
todos os pivotCacheDefinition/records do pacote. No template do DRE isso é
cerca de 80% do tempo de abertura (5 abas = 5 leituras completas).

Aqui o parser memoiza o resultado da primeira consulta. As abas passam a
apontar para o mesmo objeto de cache por ``cacheId``; na gravação o openpyxl já
deduplica caches iguais, então o conteúdo carregado é o mesmo. Usado apenas nos
caminhos de leitura dos painéis, que nunca salvam o workbook.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl.reader.excel import ExcelReader
from openpyxl.reader.workbook import WorkbookParser
from openpyxl.workbook import Workbook

_ATRIBUTO_MEMO = "_aideal_pivot_caches_memo"


class _WorkbookParserPivotsUnicos(WorkbookParser):
    @property
    def pivot_caches(self):  # type: ignore[override]
        memo = self.__dict__.get(_ATRIBUTO_MEMO)
        if memo is None:
            memo = WorkbookParser.pivot_caches.fget(self)
            self.__dict__[_ATRIBUTO_MEMO] = memo
        return memo


class _ExcelReaderPivotsUnicos(ExcelReader):
    def read_workbook(self):
        super().read_workbook()
        self.parser.__class__ = _WorkbookParserPivotsUnicos


def carregar_workbook_pivots_unicos(
    caminho: Path | str,
    *,
    keep_vba: bool = False,
    keep_links: bool = True,
    data_only: bool = False,
) -> Workbook:
    """Equivalente a ``load_workbook`` (modo edição) sem reler pivots por aba."""
    leitor = _ExcelReaderPivotsUnicos(
        caminho,
        read_only=False,
        keep_vba=keep_vba,
        data_only=data_only,
        keep_links=keep_links,
    )
    leitor.read()
    return leitor.wb
