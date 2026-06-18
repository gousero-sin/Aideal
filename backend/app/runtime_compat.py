"""Verificações de paridade do runtime Python usado na geração Excel."""

from dataclasses import dataclass
from importlib import metadata

EXCEL_RUNTIME_REQUIREMENTS: dict[str, str] = {
    "openpyxl": "3.1.5",
    "et_xmlfile": "2.0.0",
}


@dataclass(frozen=True)
class RuntimeDependencyMismatch:
    """Divergência entre a versão instalada e a versão validada."""

    package: str
    expected: str
    installed: str | None


def _installed_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def check_runtime_compatibility() -> list[RuntimeDependencyMismatch]:
    """Retorna divergências das libs sensíveis para o OOXML do DRE."""
    mismatches: list[RuntimeDependencyMismatch] = []
    for package, expected in EXCEL_RUNTIME_REQUIREMENTS.items():
        installed = _installed_version(package)
        if installed != expected:
            mismatches.append(
                RuntimeDependencyMismatch(
                    package=package,
                    expected=expected,
                    installed=installed,
                )
            )
    return mismatches


def require_runtime_compatibility() -> None:
    """Falha cedo quando o servidor roda fora do lock validado."""
    mismatches = check_runtime_compatibility()
    if not mismatches:
        return

    details = "; ".join(
        f"{item.package} instalado={item.installed or 'ausente'} esperado={item.expected}"
        for item in mismatches
    )
    raise RuntimeError(
        "Runtime Python incompatível com geração Excel do DRE: "
        f"{details}. Reinstale o backend com `pip install -r backend/requirements.txt`."
    )
