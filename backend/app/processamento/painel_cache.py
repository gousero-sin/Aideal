"""Cache de respostas dos painéis com invalidação por versão dos dados.

A chave combina os filtros normalizados com uma "versão" que muda sempre que
os dados de origem mudam:

- ``PRAGMA data_version`` lido por uma conexão SQLite dedicada e de longa
  duração. O SQLite altera esse número quando qualquer *outra* conexão confirma
  uma escrita — inclusive de outro worker do uvicorn. Isso cobre ingestões,
  limpezas e indicadores manuais sem depender de quem fez a escrita.
- ``mtime`` dos templates usados no cálculo (PLANO_CONTAS e Fluxo).
- Um contador de geração local, incrementado por ``invalidar()`` nas rotas de
  escrita, que garante a invalidação imediata no próprio processo.

O TTL é só um teto de segurança para dados que dependem do relógio (ex.: ano
corrente quando o banco está vazio).
"""

from __future__ import annotations

import copy
import logging
import sqlite3
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VersaoBancoSQLite:
    """Lê ``PRAGMA data_version`` de uma conexão dedicada e segura entre threads."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def atual(self) -> int | None:
        with self._lock:
            try:
                if self._conn is None:
                    self._conn = sqlite3.connect(
                        self._db_path, timeout=5, check_same_thread=False
                    )
                row = self._conn.execute("PRAGMA data_version").fetchone()
                return int(row[0]) if row else None
            except sqlite3.Error as exc:
                logger.warning("Versão do banco indisponível; cache de painel ignorado: %s", exc)
                self._fechar_sem_lock()
                return None

    def fechar(self) -> None:
        with self._lock:
            self._fechar_sem_lock()

    def _fechar_sem_lock(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None


def assinatura_arquivo(path: Path) -> tuple[str, int | None]:
    try:
        return str(path), path.stat().st_mtime_ns
    except OSError:
        return str(path), None


class PainelRespostaCache:
    """LRU + TTL com deduplicação de cálculos simultâneos da mesma chave."""

    def __init__(
        self,
        *,
        max_itens: int = 32,
        ttl_segundos: float = 120.0,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_itens = max_itens
        self._ttl = ttl_segundos
        self._relogio = relogio
        self._lock = threading.Lock()
        self._itens: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._em_calculo: dict[Hashable, threading.Event] = {}
        self._geracao = 0
        self.acertos = 0
        self.falhas = 0

    @property
    def geracao(self) -> int:
        with self._lock:
            return self._geracao

    def invalidar(self) -> None:
        with self._lock:
            self._geracao += 1
            self._itens.clear()

    def obter_ou_calcular(self, chave: Hashable, calcular: Callable[[], Any]) -> Any:
        """Devolve uma cópia do valor em cache ou calcula uma única vez por chave."""
        while True:
            with self._lock:
                agora = self._relogio()
                item = self._itens.get(chave)
                if item is not None and agora - item[0] <= self._ttl:
                    self._itens.move_to_end(chave)
                    self.acertos += 1
                    return copy.deepcopy(item[1])
                if item is not None:
                    del self._itens[chave]
                evento = self._em_calculo.get(chave)
                if evento is None:
                    evento = threading.Event()
                    self._em_calculo[chave] = evento
                    geracao_inicio = self._geracao
                    break
            # Outra thread já calcula esta chave: espera e tenta de novo.
            evento.wait()

        try:
            valor = calcular()
        except BaseException:
            with self._lock:
                self._em_calculo.pop(chave, None)
            evento.set()
            raise

        with self._lock:
            self.falhas += 1
            self._em_calculo.pop(chave, None)
            # Se houve invalidação durante o cálculo, o valor pode estar velho.
            if geracao_inicio == self._geracao:
                self._itens[chave] = (self._relogio(), valor)
                self._itens.move_to_end(chave)
                while len(self._itens) > self._max_itens:
                    self._itens.popitem(last=False)
        evento.set()
        return copy.deepcopy(valor)
