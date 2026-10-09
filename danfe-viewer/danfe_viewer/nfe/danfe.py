"""Desenha o DANFE (retrato, A4) a partir de um objeto Nfe, usando ReportLab.

Visao geral (leia de baixo para cima, de `render_danfe`):
  1. `_plan_pages` decide quais itens e quantas linhas de "dados adicionais" cabem em cada folha;
  2. `render_danfe` desenha cada folha: cabecalho, quadros, tabela de itens e rodape;
  3. cada quadro e montado com `_Pen.field`: retangulo + titulo pequeno + valor.

Medidas em milimetros. O ReportLab conta o Y de baixo para cima; a classe `_Pen` converte
para que a gente raciocine de cima para baixo, como numa folha de papel.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from datetime import datetime

from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas as rl_canvas

from ..core import formatting as fmt
from .model import Item, Nfe, Party

PAGE_W, PAGE_H = 210.0, 297.0
MARGIN = 5.0
CONTENT_W = PAGE_W - 2 * MARGIN                 # 200 mm
BOTTOM = PAGE_H - MARGIN - 3.5                  # limite inferior (deixa 3,5 mm para o rodape)
FONT, BOLD = "Helvetica", "Helvetica-Bold"
LABEL_SIZE = 5.5
FIELD_H = 8.0
TITLE_H = 3.6                                   # altura do titulo de cada quadro
HEADER_H = 32.0
LINE_H = 2.9                                    # altura de uma linha de texto pequeno
ITEM_FONT = 6.5
TABLE_HEAD_H = 6.0
MIN_ADDITIONAL_H = 28.0

FREIGHT_MODES = {
    "0": "0-Remetente (CIF)", "1": "1-Destinatário (FOB)", "2": "2-Terceiros",
    "3": "3-Próprio Rem.", "4": "4-Próprio Dest.", "9": "9-Sem Frete",
}
DENIED_CODES = {"110", "301", "302", "303"}

# (titulo, largura em mm, alinhamento). A soma das larguras e 200.
COLUMNS = [
    ("CÓDIGO", 18, "L"), ("DESCRIÇÃO DO PRODUTO / SERVIÇO", 49, "L"), ("NCM/SH", 14, "C"),
    ("O/CST", 8, "C"), ("CFOP", 8, "C"), ("UN", 7, "C"), ("QUANT.", 14, "R"),
    ("V. UNIT.", 16, "R"), ("V. TOTAL", 16, "R"), ("B.CÁLC\nICMS", 14, "R"),
    ("V. ICMS", 12, "R"), ("V. IPI", 10, "R"), ("ALÍQ.\nICMS", 7, "R"), ("ALÍQ.\nIPI", 7, "R"),
]
DESC_W = COLUMNS[1][1] - 1.6


def _safe(text: str) -> str:
    """Helvetica so desenha Latin-1; o que nao existir vira '?' em vez de quadrado preto."""
    return (text or "").encode("cp1252", "replace").decode("cp1252")


class _Pen:
    """'Pincel' em milimetros, com Y contado do topo da folha."""

    def __init__(self, c: rl_canvas.Canvas):
        self.c = c

    def y(self, top: float) -> float:
        return (PAGE_H - top) * mm

    def rect(self, x, top, w, h, width=0.4, dash=None) -> None:
        self.c.setLineWidth(width)
        self.c.setDash(*(dash or ([],)))
        self.c.rect(x * mm, self.y(top + h), w * mm, h * mm)
        self.c.setDash([])

    def line(self, x1, y1, x2, y2, width=0.4, dash=None) -> None:
        self.c.setLineWidth(width)
        if dash:
            self.c.setDash(*dash)
        self.c.line(x1 * mm, self.y(y1), x2 * mm, self.y(y2))
        self.c.setDash([])

    def text(self, x, top, s, font=FONT, size=7.0, align="L", w=0.0) -> None:
        s = _safe(s)
        self.c.setFont(font, size)
        if align == "R":
            self.c.drawRightString((x + w) * mm, self.y(top), s)
        elif align == "C":
            self.c.drawCentredString((x + w / 2) * mm, self.y(top), s)
        else:
            self.c.drawString(x * mm, self.y(top), s)

    def fit(self, x, top, s, w, font=FONT, size=8.0, align="L", min_size=4.5) -> None:
        """Escreve numa linha so: encolhe a fonte ate caber; se nao der, corta o final."""
        s = _safe(s)
        while size > min_size and self.c.stringWidth(s, font, size) > w * mm:
            size -= 0.25
        while len(s) > 1 and self.c.stringWidth(s, font, size) > w * mm:
            s = s[:-1]
        self.text(x, top, s, font, size, align, w)

    def wrap(self, s: str, w: float, font=FONT, size=7.0) -> list[str]:
        out: list[str] = []
        for paragraph in _safe(s).split("\n"):
            out.extend(simpleSplit(paragraph, font, size, w * mm) or [""])
        return out

    def field(self, x, top, w, h, label, value="", align="L", size=8.0, bold=False) -> None:
        self.rect(x, top, w, h)
        self.fit(x + 0.8, top + 2.0, label, w - 1.2, FONT, LABEL_SIZE, min_size=3.8)
        if value:
            self.fit(x + 0.8, top + h - 1.6, value, w - 1.6, BOLD if bold else FONT, size, align)

    def row(self, x, top, cells, h=FIELD_H) -> float:
        """Desenha uma linha de campos: cells = [(w, label, value, align, bold), ...]."""
        for cell in cells:
            w, label, value, *rest = cell
            align = rest[0] if len(rest) > 0 else "L"
            bold = rest[1] if len(rest) > 1 else False
            self.field(x, top, w, h, label, value, align, bold=bold)
            x += w
        return top + h

    def title(self, top: float, text: str, extra: str = "") -> float:
        self.text(MARGIN, top + 2.6, text, BOLD, 6.5)
        if extra:
            self.text(MARGIN + 52, top + 2.6, extra, FONT, 6.0)
        return top + TITLE_H


# ------------------------------------------------------------------ quadros
def _draw_stub(pen: _Pen, nfe: Nfe, top: float) -> float:
    """Canhoto de recebimento (so na 1a folha)."""
    e = nfe.emitter
    text = (f"RECEBEMOS DE {e.name} OS PRODUTOS E/OU SERVIÇOS CONSTANTES DA NOTA FISCAL ELETRÔNICA "
            f"INDICADA AO LADO. EMISSÃO: {fmt.date_br(nfe.issued)}  VALOR TOTAL: R$ {fmt.money(nfe.totals.total)}  "
            f"DESTINATÁRIO: {nfe.recipient.name}")
    w_main = CONTENT_W - 36
    pen.rect(MARGIN, top, w_main, 9.0)
    for i, line in enumerate(pen.wrap(text, w_main - 1.6, FONT, 6.3)[:3]):
        pen.text(MARGIN + 0.8, top + 2.8 + i * 2.7, line, FONT, 6.3)
    pen.field(MARGIN, top + 9.0, 36, 9.0, "DATA DE RECEBIMENTO")
    pen.field(MARGIN + 36, top + 9.0, w_main - 36, 9.0, "IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR")
    x = MARGIN + w_main
    pen.rect(x, top, 36, 18.0)
    pen.text(x, top + 5.0, "NF-e", BOLD, 11, "C", 36)
    pen.text(x, top + 10.0, f"Nº {fmt.zero_pad_number(nfe.number)}", BOLD, 8.5, "C", 36)
    pen.text(x, top + 14.5, f"Série {nfe.series}", BOLD, 8.5, "C", 36)
    top += 18.0 + 1.5
    pen.line(MARGIN, top, MARGIN + CONTENT_W, top, 0.3, ([2, 1.5], 0))
    return top + 2.0


def _draw_barcode(pen: _Pen, key: str, x: float, top: float, w: float, h: float) -> None:
    digits = fmt.only_digits(key)
    if not digits:
        return
    modules = Code128(digits, barWidth=1, quiet=False).width      # largura em "modulos"
    target = (w - 6.0) * mm
    bar = Code128(digits, barWidth=target / modules, barHeight=(h - 3.0) * mm, quiet=False)
    bar.drawOn(pen.c, (x + (w - bar.width / mm) / 2) * mm, pen.y(top + h - 1.5))


def _draw_header(pen: _Pen, nfe: Nfe, top: float, page: int, pages: int) -> float:
    e = nfe.emitter
    w_emit, w_danfe, w_key = 80.0, 32.0, CONTENT_W - 112.0

    # --- identificacao do emitente
    pen.rect(MARGIN, top, w_emit, HEADER_H)
    pen.text(MARGIN, top + 3.2, "IDENTIFICAÇÃO DO EMITENTE", FONT, LABEL_SIZE, "C", w_emit)
    y = top + 8.0
    for line in pen.wrap(e.name, w_emit - 4, BOLD, 10.5)[:3]:
        pen.text(MARGIN, y, line, BOLD, 10.5, "C", w_emit)
        y += 4.4
    addr = [", ".join(p for p in (e.street, e.number) if p) + (f" - {e.complement}" if e.complement else ""),
            " - ".join(p for p in (e.district, f"{e.city} - {e.uf}" if e.city else e.uf) if p),
            " - ".join(p for p in (f"CEP: {fmt.cep(e.cep)}" if e.cep else "",
                                  f"Fone: {fmt.phone(e.phone)}" if e.phone else "") if p)]
    for line in addr:
        for sub in pen.wrap(line, w_emit - 4, FONT, 7.2)[:2]:
            pen.text(MARGIN, y, sub, FONT, 7.2, "C", w_emit)
            y += 3.2

    # --- caixa DANFE
    x = MARGIN + w_emit
    pen.rect(x, top, w_danfe, HEADER_H)
    pen.text(x, top + 6.0, "DANFE", BOLD, 14, "C", w_danfe)
    for i, line in enumerate(("Documento Auxiliar da", "Nota Fiscal Eletrônica")):
        pen.text(x, top + 9.6 + i * 2.8, line, FONT, 6.3, "C", w_danfe)
    pen.text(x + 2, top + 17.2, "0 - ENTRADA", FONT, 6.3)
    pen.text(x + 2, top + 20.0, "1 - SAÍDA", FONT, 6.3)
    pen.rect(x + w_danfe - 9.5, top + 15.2, 7.0, 6.2, 0.6)
    pen.text(x + w_danfe - 9.5, top + 19.8, nfe.kind, BOLD, 10, "C", 7.0)
    pen.text(x, top + 25.0, f"Nº {fmt.zero_pad_number(nfe.number)}", BOLD, 8.5, "C", w_danfe)
    pen.text(x, top + 28.0, f"SÉRIE {nfe.series}", BOLD, 7.5, "C", w_danfe)
    pen.text(x, top + 31.0 - 0.2, f"FOLHA {page}/{pages}", BOLD, 7.0, "C", w_danfe)

    # --- codigo de barras + chave + consulta
    x += w_danfe
    pen.rect(x, top, w_key, 13.5)
    _draw_barcode(pen, nfe.key, x, top, w_key, 13.5)
    pen.field(x, top + 13.5, w_key, 9.0, "CHAVE DE ACESSO", fmt.access_key_groups(nfe.key), "C", 8.2, True)
    pen.rect(x, top + 22.5, w_key, HEADER_H - 22.5)
    pen.text(x, top + 26.0, "Consulta de autenticidade no portal nacional da NF-e", FONT, 6.3, "C", w_key)
    pen.text(x, top + 29.0, "www.nfe.fazenda.gov.br/portal ou no site da Sefaz Autorizadora", FONT, 6.3, "C", w_key)
    return top + HEADER_H


def _protocol_text(nfe: Nfe) -> str:
    if nfe.protocol:
        return f"{nfe.protocol} - {fmt.datetime_br(nfe.protocol_date)}"
    if nfe.emission_type != "1":
        return "DANFE EM CONTINGÊNCIA - SEM PROTOCOLO DE AUTORIZAÇÃO"
    return "SEM PROTOCOLO DE AUTORIZAÇÃO"


def _draw_first_blocks(pen: _Pen, nfe: Nfe, top: float) -> float:
    e, d, t = nfe.emitter, nfe.recipient, nfe.totals
    top = pen.row(MARGIN, top, [(116, "NATUREZA DA OPERAÇÃO", nfe.nature, "L", True),
                                (84, "PROTOCOLO DE AUTORIZAÇÃO DE USO", _protocol_text(nfe), "C")])
    top = pen.row(MARGIN, top, [(67, "INSCRIÇÃO ESTADUAL", e.ie),
                                (66, "INSCRIÇÃO ESTADUAL DO SUBST. TRIBUT.", e.ie_st),
                                (67, "CNPJ / CPF", fmt.cnpj_cpf(e.doc))])

    top = pen.title(top + 1.2, "DESTINATÁRIO / REMETENTE")
    dt_out = nfe.left or ""
    top = pen.row(MARGIN, top, [(120, "NOME / RAZÃO SOCIAL", d.name, "L", True),
                                (45, "CNPJ / CPF", fmt.cnpj_cpf(d.doc)),
                                (35, "DATA DA EMISSÃO", fmt.date_br(nfe.issued), "C")])
    top = pen.row(MARGIN, top, [(90, "ENDEREÇO", ", ".join(p for p in (d.street, d.number, d.complement) if p)),
                                (45, "BAIRRO / DISTRITO", d.district),
                                (30, "CEP", fmt.cep(d.cep), "C"),
                                (35, "DATA DA SAÍDA/ENTRADA", fmt.date_br(dt_out), "C")])
    top = pen.row(MARGIN, top, [(90, "MUNICÍPIO", d.city),
                                (35, "FONE / FAX", fmt.phone(d.phone), "C"),
                                (10, "UF", d.uf, "C"),
                                (40, "INSCRIÇÃO ESTADUAL", d.ie),
                                (25, "HORA DA SAÍDA", fmt.time_br(dt_out), "C")])

    if nfe.duplicates:
        extra = ""
        if nfe.invoice_number:
            extra = (f"Fatura {nfe.invoice_number}   Valor original: R$ {fmt.money(nfe.invoice_original)}   "
                     f"Desconto: R$ {fmt.money(nfe.invoice_discount or '0')}   Valor líquido: R$ {fmt.money(nfe.invoice_net)}")
        top = pen.title(top + 1.2, "FATURA / DUPLICATA", extra)
        per_row, cw = 5, CONTENT_W / 5
        for i, dup in enumerate(nfe.duplicates):
            r, col = divmod(i, per_row)
            x, y = MARGIN + col * cw, top + r * 8.6
            pen.rect(x, y, cw, 8.6)
            pen.text(x + 1, y + 3.2, f"Nº {dup.number}   Venc.: {fmt.date_br(dup.due)}", FONT, 6.8)
            pen.text(x + 1, y + 6.8, f"Valor: R$ {fmt.money(dup.value)}", BOLD, 7.2)
        top += math.ceil(len(nfe.duplicates) / per_row) * 8.6

    top = pen.title(top + 1.2, "CÁLCULO DO IMPOSTO")
    r = "R"
    top = pen.row(MARGIN, top, [
        (30, "BASE DE CÁLC. DO ICMS", fmt.money(t.icms_bc), r), (28, "VALOR DO ICMS", fmt.money(t.icms), r),
        (28, "V. ICMS DESONERADO", fmt.money(t.icms_deson), r), (28, "VALOR DO FCP", fmt.money(t.fcp), r),
        (28, "BASE CÁLC. ICMS ST", fmt.money(t.icms_st_bc), r), (28, "VALOR DO ICMS ST", fmt.money(t.icms_st), r),
        (30, "VALOR TOTAL DOS PRODUTOS", fmt.money(t.products), r)])
    top = pen.row(MARGIN, top, [
        (26, "VALOR DO FRETE", fmt.money(t.freight), r), (26, "VALOR DO SEGURO", fmt.money(t.insurance), r),
        (26, "DESCONTO", fmt.money(t.discount), r), (30, "OUTRAS DESP. ACESSÓRIAS", fmt.money(t.other), r),
        (26, "VALOR DO IPI", fmt.money(t.ipi), r),
        (32, "V. APROX. TRIBUTOS", fmt.money(t.approx_taxes) if t.approx_taxes else "", r),
        (34, "VALOR TOTAL DA NOTA", fmt.money(t.total), r, True)])
    if t.ibs_cbs_bc or t.ibs or t.cbs:
        top = pen.title(top + 1.2, "IBS / CBS (informativo)")
        top = pen.row(MARGIN, top, [
            (50, "BASE DE CÁLCULO IBS/CBS", fmt.money(t.ibs_cbs_bc), r), (50, "VALOR DO IBS", fmt.money(t.ibs), r),
            (50, "VALOR DO CBS", fmt.money(t.cbs), r), (50, "VALOR TOTAL IBS + CBS",
                                                         fmt.money(str((fmt.to_decimal(t.ibs) or 0) + (fmt.to_decimal(t.cbs) or 0))), r)])

    tr = nfe.transport
    top = pen.title(top + 1.2, "TRANSPORTADOR / VOLUMES TRANSPORTADOS")
    top = pen.row(MARGIN, top, [(62, "NOME / RAZÃO SOCIAL", tr.name), (33, "FRETE", FREIGHT_MODES.get(tr.freight_mode, tr.freight_mode)),
                                (20, "CÓDIGO ANTT", tr.antt, "C"), (25, "PLACA DO VEÍCULO", tr.plate, "C"),
                                (10, "UF", tr.plate_uf, "C"), (50, "CNPJ / CPF", fmt.cnpj_cpf(tr.doc))])
    top = pen.row(MARGIN, top, [(80, "ENDEREÇO", tr.address), (60, "MUNICÍPIO", tr.city),
                                (10, "UF", tr.uf, "C"), (50, "INSCRIÇÃO ESTADUAL", tr.ie)])
    top = pen.row(MARGIN, top, [
        (30, "QUANTIDADE", fmt.number(tr.volumes, 0, 0), r), (50, "ESPÉCIE", tr.species), (50, "MARCA", tr.brand),
        (30, "NUMERAÇÃO", tr.numbering), (20, "PESO BRUTO", fmt.number(tr.gross_weight, 3, 3) if tr.gross_weight else "", r),
        (20, "PESO LÍQUIDO", fmt.number(tr.net_weight, 3, 3) if tr.net_weight else "", r)])
    return pen.title(top + 1.2, "DADOS DOS PRODUTOS / SERVIÇOS")


def _draw_table_head(pen: _Pen, top: float) -> float:
    x = MARGIN
    for label, w, _ in COLUMNS:
        pen.rect(x, top, w, TABLE_HEAD_H)
        parts = label.split("\n")
        for i, part in enumerate(parts):
            base = top + (3.6 if len(parts) == 1 else 2.6 + i * 2.2)
            pen.fit(x + 0.3, base, part, w - 0.6, BOLD, 5.2, "C", min_size=3.8)
        x += w
    return top + TABLE_HEAD_H


def _draw_item_row(pen: _Pen, item: Item, lines: list[str], top: float, h: float) -> None:
    values = [item.code, "", item.ncm, item.cst, item.cfop, item.unit, fmt.quantity(item.qty),
              fmt.unit_price(item.unit_price), fmt.money(item.total), fmt.money(item.icms_bc),
              fmt.money(item.icms_value), fmt.money(item.ipi_value) if item.ipi_value else "",
              fmt.percent(item.icms_rate) if item.icms_rate else "", fmt.percent(item.ipi_rate) if item.ipi_rate else ""]
    x = MARGIN
    for (_, w, align), value in zip(COLUMNS, values):
        if value:
            if align == "R":
                pen.fit(x + 0.6, top + 3.3, value, w - 1.2, FONT, ITEM_FONT, "R")
            elif align == "C":
                pen.fit(x + 0.6, top + 3.3, value, w - 1.2, FONT, ITEM_FONT, "C")
            else:
                pen.fit(x + 0.8, top + 3.3, value, w - 1.6, FONT, ITEM_FONT)
        x += w
    # descricao (varias linhas): a 1a em tamanho normal, o resto menor
    x_desc = MARGIN + COLUMNS[0][1] + 0.8
    for i, line in enumerate(lines):
        pen.text(x_desc, top + 3.3 + i * LINE_H, line, FONT, ITEM_FONT if i < _desc_lines(item, pen) else ITEM_FONT - 0.5)
    # linha de separacao
    pen.line(MARGIN, top + h, MARGIN + CONTENT_W, top + h, 0.15)


def _desc_lines(item: Item, pen: _Pen) -> int:
    return len(pen.wrap(item.description, DESC_W, FONT, ITEM_FONT))


def _draw_table_frame(pen: _Pen, top: float, bottom: float) -> None:
    """Borda externa + linhas verticais das colunas ate o final da area da tabela."""
    pen.rect(MARGIN, top, CONTENT_W, bottom - top)
    x = MARGIN
    for _, w, _ in COLUMNS[:-1]:
        x += w
        pen.line(x, top, x, bottom, 0.15)


def _draw_iss(pen: _Pen, nfe: Nfe, top: float) -> float:
    t = nfe.totals
    top = pen.title(top, "CÁLCULO DO ISSQN")
    return pen.row(MARGIN, top, [
        (50, "INSCRIÇÃO MUNICIPAL", nfe.iss_municipal_registration), (50, "VALOR TOTAL DOS SERVIÇOS", fmt.money(t.iss_services), "R"),
        (50, "BASE DE CÁLCULO DO ISSQN", fmt.money(t.iss_bc), "R"), (50, "VALOR TOTAL DO ISSQN", fmt.money(t.iss_value), "R")])


def _draw_additional(pen: _Pen, top: float, bottom: float, lines: list[str], continues: bool) -> None:
    top = pen.title(top, "DADOS ADICIONAIS")
    w_main = 140.0
    h = bottom - top
    pen.field(MARGIN, top, w_main, h, "INFORMAÇÕES COMPLEMENTARES")
    pen.field(MARGIN + w_main, top, CONTENT_W - w_main, h, "RESERVADO AO FISCO")
    for i, line in enumerate(lines):
        pen.text(MARGIN + 0.8, top + 5.0 + i * LINE_H, line, FONT, 6.5)
    if continues:
        pen.text(MARGIN, bottom - 1.0, "(continua na próxima folha)", FONT, 6.0, "R", w_main)


def _draw_watermark(pen: _Pen, nfe: Nfe) -> None:
    if nfe.cancelled:
        text = "CANCELADA"
    elif nfe.status_code in DENIED_CODES:
        text = "DENEGADA"
    elif nfe.environment == "2":
        text = "SEM VALOR FISCAL"
    elif not nfe.protocol and nfe.emission_type == "1":
        text = "SEM PROTOCOLO"
    else:
        return
    c = pen.c
    c.saveState()
    c.setFillColorRGB(0.85, 0.85, 0.85)
    c.translate(PAGE_W / 2 * mm, PAGE_H / 2 * mm)
    c.rotate(45)
    c.setFont(BOLD, 62)
    c.drawCentredString(0, 0, text)
    c.restoreState()


# ------------------------------------------------------------------ planejamento
@dataclass
class _Page:
    rows: list[tuple[Item, list[str], float]] = field(default_factory=list)
    show_iss: bool = False
    extra: list[str] = field(default_factory=list)
    footer_h: float = 0.0
    continues: bool = False


def _additional_text(nfe: Nfe) -> str:
    parts = [nfe.additional_info]
    if nfe.fisco_info:
        parts.append("INFORMAÇÕES DE INTERESSE DO FISCO: " + nfe.fisco_info)
    parts += [nfe.pickup, nfe.delivery]
    return "\n".join(p.strip() for p in parts if p and p.strip())


def _plan_pages(pen: _Pen, nfe: Nfe, first_table_top: float) -> list[_Page]:
    later_top = MARGIN + HEADER_H + 1.5
    iss_h = TITLE_H + FIELD_H + 1.0 if nfe.totals.iss_value else 0.0
    pages = [_Page()]
    cursor = first_table_top + TABLE_HEAD_H

    for item in nfe.items:
        lines = pen.wrap(item.description, DESC_W, FONT, ITEM_FONT)
        for extra in ([item.extra_info] if item.extra_info else []) + item.lots:
            lines += pen.wrap(extra, DESC_W, FONT, ITEM_FONT - 0.5)
        h = max(1, len(lines)) * LINE_H + 1.4
        if cursor + h > BOTTOM and pages[-1].rows:
            pages.append(_Page())
            cursor = later_top + TABLE_HEAD_H
        pages[-1].rows.append((item, lines, h))
        cursor += h

    remaining = pen.wrap(_additional_text(nfe), 140.0 - 1.6, FONT, 6.5)
    iss_pending = bool(iss_h)
    while True:
        page = pages[-1]
        overhead = TITLE_H + (iss_h if iss_pending else 0.0) + 1.5
        needed = max(MIN_ADDITIONAL_H, len(remaining) * LINE_H + 6.0)
        if cursor + overhead + needed <= BOTTOM:                       # cabe tudo: acabou
            page.show_iss, page.extra = iss_pending, remaining
            page.footer_h = overhead + needed
            return pages
        fit = int((BOTTOM - cursor - overhead - 6.0) // LINE_H)
        if fit >= 8 and remaining:                                      # cabe uma parte
            page.show_iss, page.extra, page.continues = iss_pending, remaining[:fit], True
            page.footer_h = overhead + fit * LINE_H + 6.0
            remaining, iss_pending = remaining[fit:], False
        pages.append(_Page())
        cursor = later_top


# ------------------------------------------------------------------ API publica
def render_danfe(nfe: Nfe) -> bytes:
    """Gera o PDF do DANFE e devolve os bytes."""
    # 1) tela "de mentira" so para medir o quanto a 1a folha ocupa
    dry = _Pen(rl_canvas.Canvas(io.BytesIO()))
    first_table_top = _draw_first_blocks(dry, nfe, MARGIN + 18.0 + 3.5 + HEADER_H)
    pages = _plan_pages(dry, nfe, first_table_top)

    # 2) desenho de verdade
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.setTitle(f"DANFE NF-e {nfe.number} serie {nfe.series}")
    c.setAuthor("DANFE Viewer")
    c.setSubject(f"Chave de acesso {nfe.key}")
    pen = _Pen(c)
    printed = datetime.now().strftime("%d/%m/%Y %H:%M")

    for index, page in enumerate(pages, start=1):
        c.setStrokeGray(0)
        c.setFillGray(0)
        top = MARGIN
        if index == 1:
            top = _draw_stub(pen, nfe, top)
            top = _draw_header(pen, nfe, top, index, len(pages))
            table_top = _draw_first_blocks(pen, nfe, top)
        else:
            top = _draw_header(pen, nfe, top, index, len(pages))
            table_top = top + 1.5

        footer_top = BOTTOM - page.footer_h if page.footer_h else BOTTOM
        if page.rows:
            _draw_table_frame(pen, table_top, footer_top - 1.0 if page.footer_h else BOTTOM)
            y = _draw_table_head(pen, table_top)
            for item, lines, h in page.rows:
                _draw_item_row(pen, item, lines, y, h)
                y += h
        if page.footer_h:
            y = footer_top
            if page.show_iss:
                y = _draw_iss(pen, nfe, y)
            _draw_additional(pen, y + 1.0, BOTTOM, page.extra, page.continues)

        _draw_watermark(pen, nfe)
        c.setFillGray(0.35)
        c.setFont(FONT, 5.5)
        c.drawString(MARGIN * mm, (PAGE_H - PAGE_H + 3.0) * mm, f"DANFE Viewer  |  impresso em {printed}")
        c.drawRightString((PAGE_W - MARGIN) * mm, 3.0 * mm, f"Folha {index}/{len(pages)}")
        c.showPage()
    c.save()
    return buf.getvalue()
