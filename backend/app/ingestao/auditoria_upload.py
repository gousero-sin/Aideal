"""Preservação auditável dos arquivos-fonte recebidos pela aplicação."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from uuid import uuid4


def calcular_sha256(file_path: Path) -> str:
    """Calcula o SHA256 do arquivo sem carregar todo o conteúdo em memória."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as file_handle:
        for byte_block in iter(lambda: file_handle.read(1024 * 1024), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def arquivar_upload(
    file_path: Path,
    arquivo_nome: str,
    fluxo: str,
    ano: int,
    mes: int,
    arquivo_sha256: str,
    archive_dir: Path,
) -> Path:
    """Copia o upload para arquivo imutável identificado pelo hash.

    O destino é determinístico. Reprocessar o mesmo binário não cria cópias
    adicionais, e uma colisão de conteúdo no caminho esperado bloqueia a carga.
    """
    nome_seguro = Path(str(arquivo_nome).replace("\\", "/")).name
    destino_dir = Path(archive_dir) / fluxo / str(ano) / f"{mes:02d}"
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"{arquivo_sha256}_{nome_seguro}"

    if destino.exists():
        if calcular_sha256(destino) != arquivo_sha256:
            raise RuntimeError(f"Conflito no arquivo de auditoria: {destino}")
        return destino

    temporario = destino.with_name(f".{destino.name}.{uuid4().hex}.tmp")
    try:
        shutil.copy2(file_path, temporario)
        if calcular_sha256(temporario) != arquivo_sha256:
            raise RuntimeError(f"Falha de integridade ao arquivar upload: {arquivo_nome}")
        os.replace(temporario, destino)
    finally:
        if temporario.exists():
            temporario.unlink()

    return destino
