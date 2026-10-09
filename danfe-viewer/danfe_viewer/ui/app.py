"""Cria a aplicacao Qt e a janela principal."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def run_gui(files: list[str]) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("DANFE Viewer")
    window = MainWindow()
    window.show()
    if files:
        window.open_files(files)
    return app.exec()
