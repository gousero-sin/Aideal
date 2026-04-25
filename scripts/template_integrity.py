#!/usr/bin/env python3
"""CLI de baseline de integridade para templates Excel oficiais."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
TEMPLATES_DIR = BACKEND_DIR / "app" / "templates"
if str(TEMPLATES_DIR) not in sys.path:
    sys.path.insert(0, str(TEMPLATES_DIR))

from integrity import (  # noqa: E402
    capture_baseline,
    compare_with_baseline,
    load_baseline,
    save_baseline,
)

DEFAULT_DRE_TEMPLATE = ROOT / "templates" / "dre" / "DRE AIDEAL - 05 2025  - obra.xlsx"
DEFAULT_FC_TEMPLATE = ROOT / "templates" / "fluxo_caixa" / "Fluxo de Caixa A Ideal - 07 2025.xlsx"
BASELINE_DIR = ROOT / "backend" / "config" / "template_baselines"
DEFAULT_DRE_BASELINE = BASELINE_DIR / "dre_template_baseline.json"
DEFAULT_FC_BASELINE = BASELINE_DIR / "fluxo_template_baseline.json"


def cmd_capture(args: argparse.Namespace) -> int:
    target_template = Path(args.template)
    target_baseline = Path(args.output)

    baseline = capture_baseline(target_template)
    save_baseline(baseline, target_baseline)
    print(f"[ok] baseline salvo: {target_baseline}")
    print(f"     workbook: {baseline.workbook_name}")
    print(f"     entries:  {len(baseline.entries)}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    target_template = Path(args.template)
    baseline_path = Path(args.baseline)
    baseline = load_baseline(baseline_path)
    report = compare_with_baseline(target_template, baseline)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["is_identical"] else 2


def cmd_capture_defaults(_: argparse.Namespace) -> int:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    dre_baseline = capture_baseline(DEFAULT_DRE_TEMPLATE)
    save_baseline(dre_baseline, DEFAULT_DRE_BASELINE)
    print(f"[ok] baseline DRE salvo: {DEFAULT_DRE_BASELINE}")

    fc_baseline = capture_baseline(DEFAULT_FC_TEMPLATE)
    save_baseline(fc_baseline, DEFAULT_FC_BASELINE)
    print(f"[ok] baseline Fluxo salvo: {DEFAULT_FC_BASELINE}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Baseline de integridade estrutural para templates oficiais",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="captura baseline de um template")
    capture.add_argument("--template", required=True, help="caminho do template .xlsx")
    capture.add_argument("--output", required=True, help="arquivo JSON de saída")
    capture.set_defaults(func=cmd_capture)

    compare = sub.add_parser("compare", help="compara template atual contra baseline")
    compare.add_argument("--template", required=True, help="caminho do template .xlsx")
    compare.add_argument("--baseline", required=True, help="arquivo baseline JSON")
    compare.set_defaults(func=cmd_compare)

    defaults = sub.add_parser(
        "capture-defaults",
        help="captura baseline padrão dos templates oficiais DRE/Fluxo",
    )
    defaults.set_defaults(func=cmd_capture_defaults)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
