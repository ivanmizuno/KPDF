"""Leitura segura de XML fiscal e deteccao do tipo de documento."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


class DocumentError(Exception):
    """Erro 'amigavel': a mensagem pode ser mostrada direto ao usuario."""


def _strip_namespaces(root: ET.Element) -> None:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def parse_xml_bytes(data: bytes) -> ET.Element:
    head = data[:4096].lower()
    # XMLs fiscais nunca usam DTD/entidades; recusar evita ataques de "bomba XML".
    if b"<!doctype" in head or b"<!entity" in head:
        raise DocumentError("XML recusado: contem DTD/entidades, o que nao existe em documento fiscal.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise DocumentError(f"O arquivo nao e um XML valido ({exc}).") from exc
    _strip_namespaces(root)
    return root


def load_xml(path: str | Path) -> ET.Element:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise DocumentError(f"Nao foi possivel ler o arquivo: {exc}") from exc
    return parse_xml_bytes(data)


def find_text(node: ET.Element | None, path: str, default: str = "") -> str:
    if node is None:
        return default
    found = node.find(path)
    if found is None or found.text is None:
        return default
    return found.text.strip()
