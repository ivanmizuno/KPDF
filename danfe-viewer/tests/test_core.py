import pytest

from danfe_viewer.core import formatting as f
from danfe_viewer.core.xmlload import DocumentError, parse_xml_bytes


def make_key(base43: str) -> str:
    """Monta uma chave de 44 digitos com o DV correto (mesmo calculo da SEFAZ)."""
    total, weight = 0, 2
    for ch in reversed(base43):
        total += int(ch) * weight
        weight = 2 if weight == 9 else weight + 1
    rest = total % 11
    return base43 + str(0 if rest in (0, 1) else 11 - rest)


def test_money_and_quantity():
    assert f.money("13237.75") == "13.237,75"
    assert f.money("0") == "0,00"
    assert f.money("-5.5") == "-5,50"
    assert f.money("") == ""
    assert f.quantity("152.0000") == "152,00"
    assert f.quantity("0.5000") == "0,50"
    assert f.quantity("1.2345") == "1,2345"
    assert f.unit_price("87.0904605263") == "87,0904605263"
    assert f.unit_price("268.7630000000") == "268,763"


def test_masks():
    assert f.cnpj_cpf("43563840000760") == "43.563.840/0007-60"
    assert f.cnpj_cpf("12345678909") == "123.456.789-09"
    assert f.cep("09080511") == "09080-511"
    assert f.phone("1141828500") == "(11) 4182-8500"
    assert f.phone("01138580789") == "(11) 3858-0789"      # zero a esquerda do DDD
    assert f.phone("551733302677") == "(17) 3330-2677"     # com codigo do pais
    assert f.zero_pad_number("27349") == "000.027.349"


def test_dates():
    assert f.date_br("2026-10-01T15:04:38-03:00") == "01/10/2026"
    assert f.time_br("2026-10-01T15:04:38-03:00") == "15:04:38"
    assert f.date_br("2026-09-11") == "11/09/2026"
    assert f.time_br("2026-09-11") == ""
    assert f.date_br("lixo") == ""


def test_access_key():
    key = make_key("3526104356384000076055001000027349121079493")
    assert f.access_key_is_valid(key)
    assert not f.access_key_is_valid(key[:-1] + str((int(key[-1]) + 1) % 10))
    assert not f.access_key_is_valid("123")
    assert f.access_key_groups(key).count(" ") == 10


def test_rejects_dtd_and_garbage():
    with pytest.raises(DocumentError):
        parse_xml_bytes(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>')
    with pytest.raises(DocumentError):
        parse_xml_bytes(b"isto nao e xml")


def test_namespaces_are_stripped():
    root = parse_xml_bytes(b'<a xmlns="http://www.portalfiscal.inf.br/nfe"><b>1</b></a>')
    assert root.tag == "a" and root.find("b").text == "1"
