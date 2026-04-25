"""Módulo de templates — escrita controlada em templates Excel preservando estrutura."""

from .integrity import (
    WorkbookBaseline,
    capture_baseline,
    compare_with_baseline,
    load_baseline,
    save_baseline,
)
from .writer import TemplateWriter

__all__ = [
    "TemplateWriter",
    "WorkbookBaseline",
    "capture_baseline",
    "save_baseline",
    "load_baseline",
    "compare_with_baseline",
]
