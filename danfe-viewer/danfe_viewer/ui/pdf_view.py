"""Visualizador de PDF com rolagem continua e zoom (pypdfium2 desenha, Qt mostra)."""
from __future__ import annotations

from collections import OrderedDict

import pypdfium2 as pdfium
from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QAbstractScrollArea

PDF_DPI = 72.0
SCREEN_DPI = 96.0
MIN_ZOOM, MAX_ZOOM = 0.2, 5.0
GAP = 14            # espaco entre folhas (px)
MARGIN = 14         # margem em volta (px)
CACHE_SIZE = 10


def render_page_image(doc: pdfium.PdfDocument, index: int, scale: float) -> QImage:
    """Desenha uma folha do PDF como QImage (scale 1.0 = 72 dpi)."""
    bitmap = doc[index].render(scale=scale)           # BGR, fundo branco
    image = QImage(bitmap.buffer, bitmap.width, bitmap.height, bitmap.stride, QImage.Format.Format_BGR888)
    return image.copy()                               # copia: o buffer do pdfium some depois


class PdfView(QAbstractScrollArea):
    pageChanged = Signal(int, int)        # (folha atual, total) - base 1
    zoomChanged = Signal(float)

    FIT_WIDTH, FIT_PAGE, CUSTOM = "width", "page", "custom"

    def __init__(self, pdf_bytes: bytes, parent=None):
        super().__init__(parent)
        self._bytes = pdf_bytes                       # o pdfium precisa que estes bytes continuem vivos
        self._doc = pdfium.PdfDocument(pdf_bytes)
        self._sizes = [self._doc[i].get_size() for i in range(len(self._doc))]   # (largura, altura) em pontos
        self._cache: OrderedDict[tuple[int, int], QImage] = OrderedDict()
        self._mode = self.FIT_WIDTH
        self._zoom = 1.0
        self._offsets: list[int] = []
        self._drag_origin: QPoint | None = None
        self._last_page = -1
        self.viewport().setBackgroundRole(self.backgroundRole())
        self.viewport().setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.horizontalScrollBar().setSingleStep(30)
        self.verticalScrollBar().setSingleStep(40)
        self._relayout()

    # ------------------------------------------------------------ propriedades
    @property
    def page_count(self) -> int:
        return len(self._sizes)

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def pdf_bytes(self) -> bytes:
        return self._bytes

    @property
    def pdf_document(self) -> pdfium.PdfDocument:
        return self._doc

    def current_page(self) -> int:
        """Folha que ocupa o centro da janela (base 0)."""
        center = self.verticalScrollBar().value() + self.viewport().height() // 3
        page = 0
        for i, top in enumerate(self._offsets):
            if top <= center:
                page = i
        return page

    # ------------------------------------------------------------ zoom
    def _px_per_pt(self) -> float:
        return self._zoom * SCREEN_DPI / PDF_DPI

    def set_zoom(self, zoom: float) -> None:
        self._mode = self.CUSTOM
        self._apply_zoom(zoom)

    def fit_width(self) -> None:
        self._mode = self.FIT_WIDTH
        self._relayout()

    def fit_page(self) -> None:
        self._mode = self.FIT_PAGE
        self._relayout()

    def zoom_by(self, factor: float) -> None:
        self.set_zoom(self._zoom * factor)

    def _apply_zoom(self, zoom: float) -> None:
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        bar = self.verticalScrollBar()
        ratio = bar.value() / max(1, bar.maximum()) if bar.maximum() else 0.0
        self._zoom = zoom
        self._relayout()
        bar.setValue(int(ratio * bar.maximum()))

    def _relayout(self) -> None:
        vp = self.viewport()
        if self._mode == self.FIT_WIDTH:
            widest = max(w for w, _ in self._sizes)
            self._zoom = self._clamp((vp.width() - 2 * MARGIN) / (widest * SCREEN_DPI / PDF_DPI))
        elif self._mode == self.FIT_PAGE:
            w, h = self._sizes[0]
            kx = (vp.width() - 2 * MARGIN) / (w * SCREEN_DPI / PDF_DPI)
            ky = (vp.height() - 2 * MARGIN) / (h * SCREEN_DPI / PDF_DPI)
            self._zoom = self._clamp(min(kx, ky))
        k = self._px_per_pt()
        y, self._offsets = MARGIN, []
        for _, h in self._sizes:
            self._offsets.append(y)
            y += int(h * k) + GAP
        total_h = y - GAP + MARGIN
        total_w = int(max(w for w, _ in self._sizes) * k) + 2 * MARGIN
        self.verticalScrollBar().setRange(0, max(0, total_h - vp.height()))
        self.verticalScrollBar().setPageStep(vp.height())
        self.horizontalScrollBar().setRange(0, max(0, total_w - vp.width()))
        self.horizontalScrollBar().setPageStep(vp.width())
        self.viewport().update()
        self.zoomChanged.emit(self._zoom)
        self._emit_page()

    @staticmethod
    def _clamp(zoom: float) -> float:
        return max(MIN_ZOOM, min(MAX_ZOOM, zoom))

    # ------------------------------------------------------------ navegacao
    def go_to_page(self, index: int) -> None:
        index = max(0, min(self.page_count - 1, index))
        self.verticalScrollBar().setValue(self._offsets[index] - MARGIN)

    def _emit_page(self) -> None:
        page = self.current_page()
        if page != self._last_page:
            self._last_page = page
        self.pageChanged.emit(page + 1, self.page_count)

    # ------------------------------------------------------------ desenho
    def _page_image(self, index: int) -> QImage:
        dpr = self.devicePixelRatioF()
        scale = self._px_per_pt() * dpr
        key = (index, int(scale * 1000))
        image = self._cache.get(key)
        if image is None:
            image = render_page_image(self._doc, index, scale)
            image.setDevicePixelRatio(dpr)
            self._cache[key] = image
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        else:
            self._cache.move_to_end(key)
        return image

    def paintEvent(self, _event) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), QColor(88, 91, 96))
        sx, sy = self.horizontalScrollBar().value(), self.verticalScrollBar().value()
        k = self._px_per_pt()
        view_h = self.viewport().height()
        for i, (w, h) in enumerate(self._sizes):
            top = self._offsets[i] - sy
            height = int(h * k)
            if top + height < 0 or top > view_h:
                continue                               # fora da tela: nem desenha
            width = int(w * k)
            left = max(MARGIN, (self.viewport().width() - width) // 2) - sx
            painter.fillRect(left + 3, top + 3, width, height, QColor(0, 0, 0, 70))   # sombra
            painter.drawImage(QRectF(left, top, width, height), self._page_image(i))
        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        self.viewport().update()
        self._emit_page()

    # ------------------------------------------------------------ mouse e teclado
    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.zoom_by(1.15 if delta > 0 else 1 / 1.15)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None:
            now = event.position().toPoint()
            delta = now - self._drag_origin
            self._drag_origin = now
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())

    def mouseReleaseEvent(self, event) -> None:
        self._drag_origin = None
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)

    def enterEvent(self, event) -> None:
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)

    def keyPressEvent(self, event) -> None:
        bar = self.verticalScrollBar()
        key = event.key()
        if key == Qt.Key.Key_PageDown:
            self.go_to_page(self.current_page() + 1)
        elif key == Qt.Key.Key_PageUp:
            self.go_to_page(self.current_page() - 1)
        elif key == Qt.Key.Key_Home:
            bar.setValue(0)
        elif key == Qt.Key.Key_End:
            bar.setValue(bar.maximum())
        elif key == Qt.Key.Key_Down:
            bar.setValue(bar.value() + bar.singleStep())
        elif key == Qt.Key.Key_Up:
            bar.setValue(bar.value() - bar.singleStep())
        else:
            super().keyPressEvent(event)
