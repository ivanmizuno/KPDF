"""Linha de comando. Sem argumentos de conversao, abre a janela."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core.xmlload import DocumentError
from .documents import render_xml_file, safe_filename


def convert(files: list[str], out: str | None, out_dir: str | None) -> int:
    """Converte XML(s) em PDF sem abrir janela. Devolve o codigo de saida (0 = tudo certo)."""
    if out and len(files) != 1:
        print("--pdf aceita um unico XML; para varios use --pdf-dir.", file=sys.stderr)
        return 2
    failures = 0
    for name in files:
        try:
            result = render_xml_file(name)
        except DocumentError as exc:
            print(f"ERRO  {name}: {exc}", file=sys.stderr)
            failures += 1
            continue
        target = Path(out) if out else Path(out_dir or ".") / safe_filename(result.suggested_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.pdf)
        for warning in result.warnings:
            print(f"AVISO {name}: {warning}", file=sys.stderr)
        print(f"OK    {name} -> {target}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="danfe-viewer", description="Visualiza, imprime e converte XML fiscal em PDF.")
    parser.add_argument("files", nargs="*", help="XML(s) para abrir")
    parser.add_argument("--pdf", metavar="SAIDA.pdf", help="converte o XML em PDF, sem abrir a janela")
    parser.add_argument("--pdf-dir", metavar="PASTA", help="converte todos os XMLs para PDF dentro da pasta")
    parser.add_argument("--version", action="version", version=f"DANFE Viewer {__version__}")
    args = parser.parse_args(argv)

    if args.pdf or args.pdf_dir:
        if not args.files:
            parser.error("informe ao menos um XML para converter.")
        return convert(args.files, args.pdf, args.pdf_dir)

    from .ui.app import run_gui   # import tardio: a conversao nao precisa do Qt
    return run_gui(args.files)
