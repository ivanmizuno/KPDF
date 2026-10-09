import copy
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from danfe_viewer.core.xmlload import DocumentError, parse_xml_bytes
from danfe_viewer.documents import render_xml_file
from danfe_viewer.nfe.danfe import render_danfe
from danfe_viewer.nfe.parser import parse_nfe

SAMPLES = sorted(Path(__file__).resolve().parents[1].glob("samples/*.[xX][mM][lL]"))
needs_samples = pytest.mark.skipif(not SAMPLES, reason="sem XMLs em samples/ (nao sao versionados)")

MINIMAL = """<?xml version="1.0"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe35000000000000000000550010000000011000000010" versao="4.00">
<ide><mod>55</mod><serie>1</serie><nNF>1</nNF><natOp>VENDA</natOp><dhEmi>2026-01-02T10:00:00-03:00</dhEmi><tpNF>1</tpNF><tpAmb>2</tpAmb></ide>
<emit><CNPJ>11222333000181</CNPJ><xNome>EMPRESA TESTE</xNome><enderEmit><xLgr>RUA A</xLgr><nro>1</nro><xMun>SAO PAULO</xMun><UF>SP</UF></enderEmit></emit>
<dest><CPF>12345678909</CPF><xNome>CLIENTE</xNome></dest>
<det nItem="1"><prod><cProd>1</cProd><xProd>PRODUTO &lt;TESTE&gt; ÇÃO</xProd><NCM>11111111</NCM><CFOP>5102</CFOP><uCom>UN</uCom><qCom>2.0000</qCom><vUnCom>10.00</vUnCom><vProd>20.00</vProd></prod>
<imposto><ICMS><ICMSSN102><orig>0</orig><CSOSN>102</CSOSN></ICMSSN102></ICMS></imposto></det>
<total><ICMSTot><vProd>20.00</vProd><vNF>20.00</vNF></ICMSTot></total></infNFe></NFe>""".encode("utf-8")


def page_count(pdf: bytes) -> int:
    return len(pdfium.PdfDocument(pdf))


def test_minimal_nfe_without_protocol_still_renders():
    nfe = parse_nfe(parse_xml_bytes(MINIMAL))
    assert nfe.items[0].cst == "0102"                 # origem + CSOSN (Simples Nacional)
    assert nfe.recipient.doc == "12345678909"
    assert any("protocolo" in w.lower() for w in nfe.warnings)
    assert any("homologa" in w.lower() for w in nfe.warnings)
    pdf = render_danfe(nfe)
    assert pdf.startswith(b"%PDF") and page_count(pdf) == 1


def test_missing_infnfe_is_friendly_error():
    with pytest.raises(DocumentError):
        parse_nfe(parse_xml_bytes(b"<NFe><x/></NFe>"))


@needs_samples
@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_real_samples_render_on_one_page(path):
    result = render_xml_file(path)
    assert result.warnings == []                       # chave valida, com protocolo, producao
    assert page_count(result.pdf) == 1
    assert result.suggested_name.startswith("DANFE_35")


@needs_samples
def test_values_of_a_real_sample():
    nfe = parse_nfe(parse_xml_bytes(SAMPLES[0].read_bytes()))
    assert nfe.status_code == "100" and nfe.protocol
    assert float(nfe.totals.total) == pytest.approx(sum(float(i.total) for i in nfe.items))


@needs_samples
def test_many_items_paginate_and_keep_all_rows():
    nfe = parse_nfe(parse_xml_bytes(SAMPLES[0].read_bytes()))
    nfe.items = [copy.deepcopy(nfe.items[0]) for _ in range(120)]
    nfe.additional_info = "texto longo " * 900
    pdf = render_danfe(nfe)
    doc = pdfium.PdfDocument(pdf)
    assert len(doc) > 3
    text = "".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    assert text.count(nfe.items[0].code) >= 120        # nenhum item se perdeu
    assert f"FOLHA {len(doc)}/{len(doc)}" in text.replace("\r", "").replace("\n", " ")


def test_unsupported_documents_give_clear_message(tmp_path):
    for tag, label in (("cteProc", "CT-e"), ("mdfeProc", "MDF-e")):
        f = tmp_path / f"{tag}.xml"
        f.write_text(f'<{tag} xmlns="x"/>', encoding="utf-8")
        with pytest.raises(DocumentError, match=label):
            render_xml_file(f)
    nfce = MINIMAL.replace(b"<mod>55</mod>", b"<mod>65</mod>")
    f = tmp_path / "nfce.xml"
    f.write_bytes(nfce)
    with pytest.raises(DocumentError, match="NFC-e"):
        render_xml_file(f)
