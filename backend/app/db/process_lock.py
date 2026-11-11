"""Trava exclusiva entre processos para migrações SQLite.

Com `uvicorn --workers N`, cada worker executa o lifespan e chama as migrações ao
mesmo tempo. A leitura da tabela de versões e a aplicação do script não ficam
numa única transação SQLite (``executescript`` faz commit implícito), então dois
processos poderiam aplicar a mesma versão. A trava em arquivo serializa a etapa
inteira; quem chega depois só encontra as versões já registradas.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # POSIX (Linux de produção e macOS de desenvolvimento)
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

try:  # pragma: no cover - Windows
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(path: Path) -> threading.Lock:
    # flock é por descritor: threads do mesmo processo também precisam se excluir.
    key = str(path.resolve())
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.Lock())


def lock_path_for(database_path: Path | str) -> Path:
    path = Path(database_path)
    return path.with_name(f"{path.name}.migrate.lock")


@contextmanager
def interprocess_lock(lock_path: Path | str) -> Iterator[None]:
    """Bloqueia até obter acesso exclusivo ao arquivo de trava indicado."""
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock_for(path):
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_EX)
            elif msvcrt is not None:  # pragma: no cover - Windows
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                elif msvcrt is not None:  # pragma: no cover - Windows
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)


@contextmanager
def migration_lock(database_path: Path | str) -> Iterator[None]:
    """Trava de migração associada a um arquivo de banco SQLite."""
    with interprocess_lock(lock_path_for(database_path)):
        yield
