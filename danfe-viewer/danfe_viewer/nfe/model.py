"""Estruturas de dados da NF-e. So guardam texto exatamente como veio no XML."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Party:
    """Emitente ou destinatario."""
    name: str = ""
    fantasy: str = ""
    doc: str = ""            # CNPJ ou CPF (so digitos)
    ie: str = ""
    ie_st: str = ""
    street: str = ""
    number: str = ""
    complement: str = ""
    district: str = ""
    city: str = ""
    uf: str = ""
    cep: str = ""
    phone: str = ""


@dataclass
class Item:
    number: str = ""
    code: str = ""
    description: str = ""
    extra_info: str = ""     # infAdProd
    ncm: str = ""
    cst: str = ""            # origem + CST/CSOSN, ex.: "520"
    cfop: str = ""
    unit: str = ""
    qty: str = ""
    unit_price: str = ""
    total: str = ""
    icms_bc: str = ""
    icms_value: str = ""
    icms_rate: str = ""
    ipi_value: str = ""
    ipi_rate: str = ""
    lots: list[str] = field(default_factory=list)   # linhas ja descritas: "Lote: ..."


@dataclass
class Duplicate:
    number: str = ""
    due: str = ""
    value: str = ""


@dataclass
class Transport:
    freight_mode: str = ""
    name: str = ""
    doc: str = ""
    ie: str = ""
    address: str = ""
    city: str = ""
    uf: str = ""
    plate: str = ""
    plate_uf: str = ""
    antt: str = ""
    volumes: str = ""
    species: str = ""
    brand: str = ""
    numbering: str = ""
    gross_weight: str = ""
    net_weight: str = ""


@dataclass
class Totals:
    icms_bc: str = "0"
    icms: str = "0"
    icms_deson: str = "0"
    fcp: str = "0"
    icms_st_bc: str = "0"
    icms_st: str = "0"
    products: str = "0"
    freight: str = "0"
    insurance: str = "0"
    discount: str = "0"
    import_tax: str = "0"
    ipi: str = "0"
    other: str = "0"
    total: str = "0"
    approx_taxes: str = ""
    # IBS/CBS (reforma tributaria) - informativo
    ibs_cbs_bc: str = ""
    ibs: str = ""
    cbs: str = ""
    # ISSQN
    iss_services: str = ""
    iss_bc: str = ""
    iss_value: str = ""


@dataclass
class Nfe:
    key: str = ""
    model: str = "55"
    series: str = ""
    number: str = ""
    nature: str = ""
    kind: str = "1"                  # tpNF: 0 entrada, 1 saida
    issued: str = ""
    left: str = ""                   # dhSaiEnt
    environment: str = "1"           # tpAmb
    emission_type: str = "1"         # tpEmis
    emitter: Party = field(default_factory=Party)
    recipient: Party = field(default_factory=Party)
    items: list[Item] = field(default_factory=list)
    duplicates: list[Duplicate] = field(default_factory=list)
    invoice_number: str = ""
    invoice_original: str = ""
    invoice_discount: str = ""
    invoice_net: str = ""
    transport: Transport = field(default_factory=Transport)
    totals: Totals = field(default_factory=Totals)
    additional_info: str = ""        # infCpl
    fisco_info: str = ""             # infAdFisco
    pickup: str = ""                 # retirada (texto pronto)
    delivery: str = ""               # entrega (texto pronto)
    iss_municipal_registration: str = ""
    # protocolo de autorizacao
    protocol: str = ""
    protocol_date: str = ""
    status_code: str = ""
    status_text: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def authorized(self) -> bool:
        return self.status_code in ("100", "150")

    @property
    def cancelled(self) -> bool:
        return self.status_code in ("101", "151", "155")
