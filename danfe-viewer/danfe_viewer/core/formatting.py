"""Funcoes de formatacao no padrao brasileiro (CNPJ, datas, valores...).

Todas recebem texto (como vem no XML) e devolvem texto pronto para imprimir.
Valor vazio/invalido devolve "" para o DANFE simplesmente deixar o campo em branco.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


def only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def to_decimal(value: str | None) -> Decimal | None:
    try:
        return Decimal((value or "").strip())
    except InvalidOperation:
        return None


def number(value: str | None, min_decimals: int = 2, max_decimals: int = 2) -> str:
    """'1234.5' -> '1.234,50'. Com max_decimals > min_decimals, tira zeros a direita."""
    dec = to_decimal(value)
    if dec is None:
        return ""
    text = f"{dec:.{max_decimals}f}"
    if max_decimals > min_decimals and "." in text:
        whole, frac = text.split(".")
        frac = frac.rstrip("0").ljust(min_decimals, "0")
        text = f"{whole}.{frac}"
    whole, _, frac = text.partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    whole = f"{int(whole):,}".replace(",", ".")
    return f"{sign}{whole},{frac}" if frac else f"{sign}{whole}"


def money(value: str | None) -> str:
    return number(value, 2, 2)


def quantity(value: str | None) -> str:
    return number(value, 2, 4)


def unit_price(value: str | None) -> str:
    return number(value, 2, 10)


def percent(value: str | None) -> str:
    return number(value, 2, 2)


def cnpj_cpf(value: str | None) -> str:
    d = only_digits(value)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return value or ""


def cep(value: str | None) -> str:
    d = only_digits(value)
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else (value or "")


def phone(value: str | None) -> str:
    d = only_digits(value)
    if len(d) == 11 and d.startswith("0"):  # '01138580789' -> DDD com zero a esquerda
        d = d[1:]
    if len(d) in (12, 13) and d.startswith("55"):  # codigo do pais (Brasil)
        d = d[2:]
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    return d


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def date_br(value: str | None) -> str:
    dt = parse_datetime(value)
    return dt.strftime("%d/%m/%Y") if dt else ""


def time_br(value: str | None) -> str:
    dt = parse_datetime(value)
    return dt.strftime("%H:%M:%S") if dt and "T" in value else ""


def datetime_br(value: str | None) -> str:
    dt = parse_datetime(value)
    return dt.strftime("%d/%m/%Y %H:%M:%S") if dt else ""


def zero_pad_number(value: str | None) -> str:
    """'27349' -> '000.027.349' (numero da NF-e com 9 digitos)."""
    d = only_digits(value)
    if not d:
        return ""
    d = d.zfill(9)
    return f"{d[:3]}.{d[3:6]}.{d[6:]}"


def access_key_groups(key: str | None) -> str:
    d = only_digits(key)
    return " ".join(d[i : i + 4] for i in range(0, len(d), 4))


def access_key_is_valid(key: str | None) -> bool:
    """Confere o digito verificador (modulo 11) da chave de acesso de 44 digitos."""
    d = only_digits(key)
    if len(d) != 44:
        return False
    total, weight = 0, 2
    for ch in reversed(d[:43]):
        total += int(ch) * weight
        weight = 2 if weight == 9 else weight + 1
    rest = total % 11
    dv = 0 if rest in (0, 1) else 11 - rest
    return dv == int(d[43])
