"""Ponto unico que transforma um XML fiscal em PDF.

Para suportar um novo documento (NFC-e, CT-e, MDF-e) basta:
  1. criar um pacote como `danfe_viewer/cte/` com `parse_*` e `render_*`;
  2. registrar uma funcao em `_BUILDERS` abaixo, indexada pela tag raiz do XML.
A janela e a linha de comando nao precisam mudar.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .core.xmlload import DocumentError, load_xml
from .nfe.danfe import render_danfe
from .nfe.parser import parse_nfe


@dataclass
class Rendered:
    pdf: bytes
    title: str                         # texto curto para a aba, ex.: "NF-e 27349"
    suggested_name: str                # nome sugerido para salvar o PDF (sem pasta)
    warnings: list[str] = field(default_factory=list)


def _build_nfe(root: ET.Element) -> Rendered:
    nfe = parse_nfe(root)
    if nfe.model == "65":
        raise DocumentError("Este XML é de NFC-e (modelo 65). O DANFE NFC-e ainda não foi implementado.")
    if nfe.model and nfe.model != "55":
        raise DocumentError(f"Modelo de NF-e {nfe.model} não suportado (só o modelo 55 por enquanto).")
    return Rendered(
        pdf=render_danfe(nfe),
        title=f"NF-e {nfe.number}",
        suggested_name=f"DANFE_{nfe.key or nfe.number}.pdf",
        warnings=nfe.warnings,
    )


def _unsupported(label: str):
    def build(_root: ET.Element) -> Rendered:
        raise DocumentError(f"Este XML é de {label}, que ainda não foi implementado nesta versão.")
    return build


_BUILDERS = {
    "nfeProc": _build_nfe,
    "NFe": _build_nfe,
    "cteProc": _unsupported("CT-e (DACTE)"),
    "CTe": _unsupported("CT-e (DACTE)"),
    "cteOSProc": _unsupported("CT-e OS (DACTE OS)"),
    "mdfeProc": _unsupported("MDF-e (DAMDFE)"),
    "MDFe": _unsupported("MDF-e (DAMDFE)"),
}


def render_xml_file(path: str | Path) -> Rendered:
    root = load_xml(path)
    builder = _BUILDERS.get(root.tag)
    if builder is None:
        raise DocumentError(f"Documento fiscal não reconhecido (tag raiz <{root.tag}>).")
    return builder(root)


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name)
