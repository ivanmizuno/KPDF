"""Cria a aplicacao Qt e a janela principal."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def run_gui(files: list[str]) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("DANFE Viewer")
    icon = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    if files:
        window.open_files(files)
    return app.exec()
