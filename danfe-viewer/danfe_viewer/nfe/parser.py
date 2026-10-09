"""Converte o XML da NF-e (nfeProc ou NFe) em um objeto Nfe."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from ..core import formatting as fmt
from ..core.xmlload import DocumentError, find_text
from .model import Duplicate, Item, Nfe, Party, Totals, Transport


def _party(node: ET.Element | None, addr_tag: str) -> Party:
    if node is None:
        return Party()
    addr = node.find(addr_tag)
    return Party(
        name=find_text(node, "xNome"),
        fantasy=find_text(node, "xFant"),
        doc=find_text(node, "CNPJ") or find_text(node, "CPF") or find_text(node, "idEstrangeiro"),
        ie=find_text(node, "IE"),
        ie_st=find_text(node, "IEST"),
        street=find_text(addr, "xLgr"),
        number=find_text(addr, "nro"),
        complement=find_text(addr, "xCpl"),
        district=find_text(addr, "xBairro"),
        city=find_text(addr, "xMun"),
        uf=find_text(addr, "UF"),
        cep=find_text(addr, "CEP"),
        phone=find_text(addr, "fone"),
    )


def _place_text(node: ET.Element | None, title: str) -> str:
    """Texto do local de retirada/entrega (a norma manda ir nos dados adicionais)."""
    if node is None:
        return ""
    doc = fmt.cnpj_cpf(find_text(node, "CNPJ") or find_text(node, "CPF"))
    parts = [find_text(node, "xNome"), f"CNPJ/CPF {doc}" if doc else "",
             ", ".join(p for p in (find_text(node, "xLgr"), find_text(node, "nro"), find_text(node, "xCpl")) if p),
             find_text(node, "xBairro"),
             " - ".join(p for p in (find_text(node, "xMun"), find_text(node, "UF")) if p),
             f"CEP {fmt.cep(find_text(node, 'CEP'))}" if find_text(node, "CEP") else "",
             f"IE {find_text(node, 'IE')}" if find_text(node, "IE") else ""]
    return f"{title}: " + " | ".join(p for p in parts if p)


def _item(det: ET.Element) -> Item:
    prod = det.find("prod")
    imposto = det.find("imposto")
    icms_group = imposto.find("ICMS") if imposto is not None else None
    icms = icms_group[0] if icms_group is not None and len(icms_group) else None
    ipi = imposto.find("IPI/IPITrib") if imposto is not None else None

    cst = find_text(icms, "CST") or find_text(icms, "CSOSN")
    lots = []
    for r in (prod.findall("rastro") if prod is not None else []):
        line = f"Lote: {find_text(r, 'nLote')}"
        if find_text(r, "qLote"):
            line += f"  Qtd: {fmt.number(find_text(r, 'qLote'), 2, 3)}"
        if find_text(r, "dFab"):
            line += f"  Fab: {fmt.date_br(find_text(r, 'dFab'))}"
        if find_text(r, "dVal"):
            line += f"  Val: {fmt.date_br(find_text(r, 'dVal'))}"
        lots.append(line)

    return Item(
        number=det.get("nItem", ""),
        code=find_text(prod, "cProd"),
        description=find_text(prod, "xProd"),
        extra_info=find_text(det, "infAdProd"),
        ncm=find_text(prod, "NCM"),
        cst=find_text(icms, "orig") + cst,
        cfop=find_text(prod, "CFOP"),
        unit=find_text(prod, "uCom"),
        qty=find_text(prod, "qCom"),
        unit_price=find_text(prod, "vUnCom"),
        total=find_text(prod, "vProd"),
        icms_bc=find_text(icms, "vBC"),
        icms_value=find_text(icms, "vICMS"),
        icms_rate=find_text(icms, "pICMS"),
        ipi_value=find_text(ipi, "vIPI"),
        ipi_rate=find_text(ipi, "pIPI"),
        lots=lots,
    )


def _transport(transp: ET.Element | None) -> Transport:
    if transp is None:
        return Transport()
    t = transp.find("transporta")
    veic = transp.find("veicTransp")
    vols = transp.findall("vol")
    qty = sum((fmt.to_decimal(find_text(v, "qVol")) or 0) for v in vols)
    gross = sum((fmt.to_decimal(find_text(v, "pesoB")) or 0) for v in vols)
    net = sum((fmt.to_decimal(find_text(v, "pesoL")) or 0) for v in vols)
    first = vols[0] if vols else None
    return Transport(
        freight_mode=find_text(transp, "modFrete"),
        name=find_text(t, "xNome"),
        doc=find_text(t, "CNPJ") or find_text(t, "CPF"),
        ie=find_text(t, "IE"),
        address=find_text(t, "xEnder"),
        city=find_text(t, "xMun"),
        uf=find_text(t, "UF"),
        plate=find_text(veic, "placa"),
        plate_uf=find_text(veic, "UF"),
        antt=find_text(veic, "RNTC"),
        volumes=str(qty) if vols else "",
        species=find_text(first, "esp"),
        brand=find_text(first, "marca"),
        numbering=find_text(first, "nVol"),
        gross_weight=str(gross) if vols and gross else "",
        net_weight=str(net) if vols and net else "",
    )


def _totals(total: ET.Element | None) -> Totals:
    t = Totals()
    icms = total.find("ICMSTot") if total is not None else None
    if icms is not None:
        t.icms_bc = find_text(icms, "vBC", "0")
        t.icms = find_text(icms, "vICMS", "0")
        t.icms_deson = find_text(icms, "vICMSDeson", "0")
        t.fcp = find_text(icms, "vFCP", "0")
        t.icms_st_bc = find_text(icms, "vBCST", "0")
        t.icms_st = find_text(icms, "vST", "0")
        t.products = find_text(icms, "vProd", "0")
        t.freight = find_text(icms, "vFrete", "0")
        t.insurance = find_text(icms, "vSeg", "0")
        t.discount = find_text(icms, "vDesc", "0")
        t.import_tax = find_text(icms, "vII", "0")
        t.ipi = find_text(icms, "vIPI", "0")
        t.other = find_text(icms, "vOutro", "0")
        t.total = find_text(icms, "vNF", "0")
        t.approx_taxes = find_text(icms, "vTotTrib")
    ibscbs = total.find("IBSCBSTot") if total is not None else None
    if ibscbs is not None:
        t.ibs_cbs_bc = find_text(ibscbs, "vBCIBSCBS")
        t.ibs = find_text(ibscbs, "gIBS/vIBS")
        t.cbs = find_text(ibscbs, "gCBS/vCBS")
    iss = total.find("ISSQNtot") if total is not None else None
    if iss is not None:
        t.iss_services = find_text(iss, "vServ")
        t.iss_bc = find_text(iss, "vBC")
        t.iss_value = find_text(iss, "vISS")
    return t


def parse_nfe(root: ET.Element) -> Nfe:
    """Aceita <nfeProc> (com protocolo) ou <NFe> solto (sem protocolo)."""
    nfe_node = root if root.tag == "NFe" else root.find("NFe")
    if nfe_node is None:
        raise DocumentError("Nao encontrei a tag <NFe> neste XML.")
    inf = nfe_node.find("infNFe")
    if inf is None:
        raise DocumentError("Nao encontrei a tag <infNFe> neste XML.")

    ide = inf.find("ide")
    model = find_text(ide, "mod")
    key = (inf.get("Id") or "").removeprefix("NFe")

    prot = root.find("protNFe/infProt") if root.tag != "NFe" else None
    if prot is not None and find_text(prot, "chNFe"):
        key = key or find_text(prot, "chNFe")

    n = Nfe(
        key=key,
        model=model,
        series=find_text(ide, "serie"),
        number=find_text(ide, "nNF"),
        nature=find_text(ide, "natOp"),
        kind=find_text(ide, "tpNF", "1"),
        issued=find_text(ide, "dhEmi") or find_text(ide, "dEmi"),
        left=find_text(ide, "dhSaiEnt") or find_text(ide, "dSaiEnt"),
        environment=find_text(ide, "tpAmb", "1"),
        emission_type=find_text(ide, "tpEmis", "1"),
        emitter=_party(inf.find("emit"), "enderEmit"),
        recipient=_party(inf.find("dest"), "enderDest"),
        items=[_item(d) for d in inf.findall("det")],
        transport=_transport(inf.find("transp")),
        totals=_totals(inf.find("total")),
        additional_info=find_text(inf, "infAdic/infCpl"),
        fisco_info=find_text(inf, "infAdic/infAdFisco"),
        pickup=_place_text(inf.find("retirada"), "LOCAL DE RETIRADA"),
        delivery=_place_text(inf.find("entrega"), "LOCAL DE ENTREGA"),
        iss_municipal_registration=find_text(inf, "emit/IM"),
    )

    fat = inf.find("cobr/fat")
    if fat is not None:
        n.invoice_number = find_text(fat, "nFat")
        n.invoice_original = find_text(fat, "vOrig")
        n.invoice_discount = find_text(fat, "vDesc")
        n.invoice_net = find_text(fat, "vLiq")
    n.duplicates = [
        Duplicate(find_text(d, "nDup"), find_text(d, "dVenc"), find_text(d, "vDup"))
        for d in inf.findall("cobr/dup")
    ]

    if prot is not None:
        n.protocol = find_text(prot, "nProt")
        n.protocol_date = find_text(prot, "dhRecbto")
        n.status_code = find_text(prot, "cStat")
        n.status_text = find_text(prot, "xMotivo")

    # --- avisos (nao impedem de mostrar o DANFE) ---
    if model and model != "55":
        n.warnings.append(f"Modelo {model}: este layout de DANFE e do modelo 55.")
    if not fmt.access_key_is_valid(n.key):
        n.warnings.append("Chave de acesso com digito verificador invalido.")
    if prot is None:
        n.warnings.append("XML sem protocolo de autorizacao (nao e um nfeProc).")
    elif find_text(prot, "chNFe") and find_text(prot, "chNFe") != n.key:
        n.warnings.append("Chave do protocolo diferente da chave da NF-e.")
    if n.environment == "2":
        n.warnings.append("Ambiente de HOMOLOGACAO: sem valor fiscal.")
    return n
