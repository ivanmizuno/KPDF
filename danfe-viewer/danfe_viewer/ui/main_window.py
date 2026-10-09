"""Janela principal: abas, barra de ferramentas, abrir / salvar PDF / imprimir."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QLabel, QMainWindow, QMessageBox, QTabWidget, QToolBar, QWidget)

from .. import __version__
from ..core.xmlload import DocumentError
from ..documents import Rendered, render_xml_file, safe_filename
from .pdf_view import PdfView
from .printing import ask_and_print


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DANFE Viewer")
        self.resize(1000, 900)
        self.setAcceptDrops(True)
        self._settings = QSettings("DanfeViewer", "DanfeViewer")
        self._tab_info: dict[PdfView, Rendered] = {}

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._refresh_state)
        self.setCentralWidget(self.tabs)

        self.page_label = QLabel("")
        self.zoom_label = QLabel("")
        self.statusBar().addPermanentWidget(self.page_label)
        self.statusBar().addPermanentWidget(self.zoom_label)
        self._build_actions()
        self._refresh_state()
        self.statusBar().showMessage("Abra um XML (Ctrl+O) ou arraste o arquivo para cá.")

    # ------------------------------------------------------------ montagem da interface
    def _action(self, text: str, slot, shortcut=None, tip: str = "") -> QAction:
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        if tip:
            act.setStatusTip(tip)
            act.setToolTip(f"{tip} ({QKeySequence(shortcut).toString()})" if shortcut else tip)
        act.triggered.connect(slot)
        return act

    def _build_actions(self) -> None:
        self.act_open = self._action("Abrir XML…", self.open_dialog, QKeySequence.StandardKey.Open, "Abrir XML")
        self.act_save = self._action("Salvar PDF…", self.save_pdf, QKeySequence.StandardKey.Save, "Salvar como PDF")
        self.act_print = self._action("Imprimir…", self.print_current, QKeySequence.StandardKey.Print, "Imprimir")
        self.act_close = self._action("Fechar aba", lambda: self._close_tab(self.tabs.currentIndex()), "Ctrl+W")
        self.act_quit = self._action("Sair", self.close, "Ctrl+Q")
        self.act_zoom_in = self._action("Zoom +", lambda: self._view_do("zoom_by", 1.2), "Ctrl+=", "Aumentar zoom")
        self.act_zoom_out = self._action("Zoom −", lambda: self._view_do("zoom_by", 1 / 1.2), "Ctrl+-", "Diminuir zoom")
        self.act_fit_width = self._action("Ajustar largura", lambda: self._view_do("fit_width"), "Ctrl+0", "Ajustar à largura")
        self.act_fit_page = self._action("Página inteira", lambda: self._view_do("fit_page"), "Ctrl+9", "Mostrar a folha inteira")
        self.act_100 = self._action("100%", lambda: self._view_do("set_zoom", 1.0), "Ctrl+1", "Tamanho real")
        self.act_prev = self._action("◀ Folha anterior", lambda: self._goto(-1), "Alt+Left", "Folha anterior")
        self.act_next = self._action("Próxima folha ▶", lambda: self._goto(+1), "Alt+Right", "Próxima folha")
        self.act_about = self._action("Sobre", self.about)

        file_menu = self.menuBar().addMenu("&Arquivo")
        for a in (self.act_open, self.act_save, self.act_print, None, self.act_close, self.act_quit):
            file_menu.addSeparator() if a is None else file_menu.addAction(a)
        view_menu = self.menuBar().addMenu("&Exibir")
        for a in (self.act_zoom_in, self.act_zoom_out, self.act_100, self.act_fit_width, self.act_fit_page, None,
                  self.act_prev, self.act_next):
            view_menu.addSeparator() if a is None else view_menu.addAction(a)
        self.menuBar().addMenu("A&juda").addAction(self.act_about)

        bar = QToolBar("Principal")
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(bar)
        for a in (self.act_open, self.act_save, self.act_print, None, self.act_zoom_out, self.act_zoom_in,
                  self.act_fit_width, self.act_fit_page, self.act_100, None, self.act_prev, self.act_next):
            bar.addSeparator() if a is None else bar.addAction(a)

    # ------------------------------------------------------------ abrir arquivos
    def current_view(self) -> PdfView | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, PdfView) else None

    def open_dialog(self) -> None:
        start = self._settings.value("last_dir", str(Path.home()))
        files, _ = QFileDialog.getOpenFileNames(self, "Abrir XML fiscal", start, "XML (*.xml *.XML);;Todos (*.*)")
        if files:
            self._settings.setValue("last_dir", str(Path(files[0]).parent))
            self.open_files(files)

    def open_files(self, files: list[str]) -> None:
        errors: list[str] = []
        for name in files:
            try:
                rendered = render_xml_file(name)
                view = PdfView(rendered.pdf)
            except DocumentError as exc:
                errors.append(f"{Path(name).name}: {exc}")
                continue
            except Exception as exc:      # bug inesperado: nao derruba o programa
                errors.append(f"{Path(name).name}: erro inesperado ({type(exc).__name__}: {exc})")
                continue
            view.pageChanged.connect(self._on_page_changed)
            view.zoomChanged.connect(self._on_zoom_changed)
            self._tab_info[view] = rendered
            index = self.tabs.addTab(view, rendered.title)
            self.tabs.setTabToolTip(index, str(name))
            self.tabs.setCurrentIndex(index)
            view.setFocus()
            if rendered.warnings:
                self.statusBar().showMessage("Atenção: " + " | ".join(rendered.warnings), 15000)
        if errors:
            QMessageBox.warning(self, "Não foi possível abrir", "\n\n".join(errors))
        self._refresh_state()

    def _close_tab(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is not None:
            self.tabs.removeTab(index)
            self._tab_info.pop(widget, None)
            widget.deleteLater()
        self._refresh_state()

    # ------------------------------------------------------------ acoes
    def save_pdf(self) -> None:
        view = self.current_view()
        if view is None:
            return
        info = self._tab_info[view]
        start = str(Path(self._settings.value("save_dir", str(Path.home()))) / safe_filename(info.suggested_name))
        path, _ = QFileDialog.getSaveFileName(self, "Salvar PDF", start, "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            Path(path).write_bytes(view.pdf_bytes)
        except OSError as exc:
            QMessageBox.critical(self, "Erro ao salvar", f"Não foi possível salvar o PDF:\n{exc}")
            return
        self._settings.setValue("save_dir", str(Path(path).parent))
        self.statusBar().showMessage(f"PDF salvo em {path}", 8000)

    def print_current(self) -> None:
        view = self.current_view()
        if view is None:
            return
        result = ask_and_print(self, view.pdf_document, self._tab_info[view].title)
        if result is False:
            QMessageBox.critical(self, "Erro de impressão", "Não foi possível iniciar a impressão. Verifique a impressora.")
        elif result:
            self.statusBar().showMessage("Enviado para a impressora.", 6000)

    def _view_do(self, method: str, *args) -> None:
        view = self.current_view()
        if view is not None:
            getattr(view, method)(*args)

    def _goto(self, step: int) -> None:
        view = self.current_view()
        if view is not None:
            view.go_to_page(view.current_page() + step)

    def about(self) -> None:
        QMessageBox.about(self, "Sobre o DANFE Viewer", f"<b>DANFE Viewer {__version__}</b><br>"
                          "Visualiza, imprime e converte em PDF o XML da NF-e (modelo 55).<br><br>"
                          "Atalhos: Ctrl+O abrir, Ctrl+S salvar PDF, Ctrl+P imprimir,<br>"
                          "Ctrl+roda do mouse = zoom, arrastar = mover, PgUp/PgDn = folhas.")

    # ------------------------------------------------------------ estado da interface
    def _on_page_changed(self, page: int, total: int) -> None:
        if self.sender() is self.current_view():
            self.page_label.setText(f"Folha {page}/{total}   ")

    def _on_zoom_changed(self, zoom: float) -> None:
        if self.sender() is self.current_view():
            self.zoom_label.setText(f"{zoom * 100:.0f}%  ")

    def _refresh_state(self, *_args) -> None:
        view = self.current_view()
        has_doc = view is not None
        for act in (self.act_save, self.act_print, self.act_close, self.act_zoom_in, self.act_zoom_out,
                    self.act_fit_width, self.act_fit_page, self.act_100, self.act_prev, self.act_next):
            act.setEnabled(has_doc)
        if view is not None:
            self.page_label.setText(f"Folha {view.current_page() + 1}/{view.page_count}   ")
            self.zoom_label.setText(f"{view.zoom * 100:.0f}%  ")
            self.setWindowTitle(f"{self._tab_info[view].title} - DANFE Viewer")
        else:
            self.page_label.setText("")
            self.zoom_label.setText("")
            self.setWindowTitle("DANFE Viewer")

    # ------------------------------------------------------------ arrastar e soltar
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        files = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile().lower().endswith(".xml")]
        if files:
            self.open_files(files)
