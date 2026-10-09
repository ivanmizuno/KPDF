"""Impressao: pega cada folha do PDF, rasteriza na resolucao da impressora e envia ao Qt."""
from __future__ import annotations

import pypdfium2 as pdfium
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QWidget

from .pdf_view import render_page_image

MAX_PRINT_DPI = 600       # acima disso so aumenta o tempo; 600 dpi ja deixa o codigo de barras nitido


def new_printer() -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    printer.setFullPage(False)
    return printer


def print_document(doc: pdfium.PdfDocument, printer: QPrinter, job_name: str) -> bool:
    """Envia todas as folhas ao `printer`. Devolve False se o spool nao puder ser iniciado."""
    printer.setDocName(job_name)
    painter = QPainter()
    if not painter.begin(printer):
        return False
    try:
        dpi = min(printer.resolution(), MAX_PRINT_DPI)
        area = printer.pageRect(QPrinter.Unit.DevicePixel)         # area imprimivel, em pixels da impressora
        for index in range(len(doc)):
            if index:
                printer.newPage()
            image = render_page_image(doc, index, dpi / 72.0)
            # cabe na area imprimivel mantendo a proporcao (a margem da impressora encolhe ~2-3%)
            scaled = image.size().scaled(area.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(area.x() + (area.width() - scaled.width()) / 2, area.y(), scaled.width(), scaled.height())
            painter.drawImage(target, image)
    finally:
        painter.end()
    return True


def ask_and_print(parent: QWidget, doc: pdfium.PdfDocument, job_name: str) -> bool | None:
    """Mostra o dialogo de impressao. None = usuario cancelou; True/False = enviado/falhou."""
    printer = new_printer()
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Imprimir DANFE")
    dialog.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, False)
    if dialog.exec() != QPrintDialog.DialogCode.Accepted:
        return None
    return print_document(doc, printer, job_name)
