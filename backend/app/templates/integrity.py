"""Ferramentas de baseline e comparação de integridade de templates Excel.

Objetivo da Etapa 1:
- Capturar baseline estrutural dos templates oficiais.
- Detectar adições/remoções/alterações indevidas após qualquer escrita.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile


@dataclass
class ZipEntryFingerprint:
    name: str
    file_size: int
    compress_size: int
    crc: int
    sha256: str


@dataclass
class WorkbookBaseline:
    workbook_name: str
    captured_at_utc: str
    file_size_bytes: int
    file_sha256: str
    entries: list[ZipEntryFingerprint]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def capture_baseline(workbook_path: Path) -> WorkbookBaseline:
    workbook_path = Path(workbook_path)
    entries: list[ZipEntryFingerprint] = []

    with ZipFile(workbook_path, "r") as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            payload = zf.read(info.filename)
            entries.append(
                ZipEntryFingerprint(
                    name=info.filename,
                    file_size=info.file_size,
                    compress_size=info.compress_size,
                    crc=info.CRC,
                    sha256=_sha256_bytes(payload),
                )
            )

    return WorkbookBaseline(
        workbook_name=workbook_path.name,
        captured_at_utc=datetime.now(timezone.utc).isoformat(),
        file_size_bytes=workbook_path.stat().st_size,
        file_sha256=_sha256_file(workbook_path),
        entries=entries,
    )


def save_baseline(baseline: WorkbookBaseline, target_path: Path) -> Path:
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(baseline), f, ensure_ascii=False, indent=2)
    return target_path


def load_baseline(path: Path) -> WorkbookBaseline:
    with Path(path).open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return WorkbookBaseline(
        workbook_name=raw["workbook_name"],
        captured_at_utc=raw["captured_at_utc"],
        file_size_bytes=raw["file_size_bytes"],
        file_sha256=raw["file_sha256"],
        entries=[ZipEntryFingerprint(**entry) for entry in raw["entries"]],
    )


def compare_with_baseline(workbook_path: Path, baseline: WorkbookBaseline) -> dict:
    current = capture_baseline(Path(workbook_path))
    base_map = {e.name: e for e in baseline.entries}
    cur_map = {e.name: e for e in current.entries}

    removed = sorted(name for name in base_map if name not in cur_map)
    added = sorted(name for name in cur_map if name not in base_map)
    changed = sorted(
        name
        for name in base_map
        if name in cur_map and base_map[name].sha256 != cur_map[name].sha256
    )

    return {
        "workbook": Path(workbook_path).name,
        "baseline_workbook": baseline.workbook_name,
        "removed_entries": removed,
        "added_entries": added,
        "changed_entries": changed,
        "is_identical": not (removed or added or changed),
    }

