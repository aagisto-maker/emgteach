"""
EMG App — entry point.

Crea la QApplication, muestra una splash screen breve, construye el
QMainWindow con tres pestañas (Adquisición, Análisis, CVM) y arranca el
event loop. Al cerrar, llama cleanup() en cada pestaña para garantizar
que todos los workers terminan antes de salir.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QSplashScreen,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from emgteach.gui.tabs.acquisition import AcquisitionTab
from emgteach.gui.tabs.analysis import AnalysisTab
from emgteach.gui.tabs.mvc import MvcTab
from emgteach.gui.widgets.logger import LoggerWidget

# ---------------------------------------------------------------------------
# Splash screen
# ---------------------------------------------------------------------------

def _make_splash() -> QSplashScreen:
    px = QPixmap(480, 240)
    px.fill(QColor("#1a2a3a"))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    title_font = QFont("Arial", 22, QFont.Weight.Bold)
    p.setFont(title_font)
    p.setPen(QColor("#ffffff"))
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "EMG Bioinstrumentación")

    sub_font = QFont("Arial", 11)
    p.setFont(sub_font)
    p.setPen(QColor("#aaccee"))
    sub_rect = px.rect().adjusted(0, 80, 0, 0)
    p.drawText(sub_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
               "Plataformas Arduino (BITalino y MyoWare)")

    author_font = QFont("Arial", 9)
    p.setFont(author_font)
    p.setPen(QColor(220, 220, 220))
    author_rect = px.rect().adjusted(0, 130, 0, 0)
    p.drawText(author_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
               "Dr. Agis-Torres — UCM")

    p.end()

    splash = QSplashScreen(px, Qt.WindowType.WindowStaysOnTopHint)
    return splash


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.setWindowTitle("EMG Bioinstrumentación")
        self.resize(1100, 780)

        self._settings = settings

        # Logger compartido por todas las pestañas
        self._logger = LoggerWidget()

        # Pestañas
        self._tab_adq = AcquisitionTab(self._logger, settings)
        self._tab_ana = AnalysisTab(self._logger, settings)
        self._tab_cvm = MvcTab(self._logger, settings)

        tabs = QTabWidget()
        tabs.addTab(self._tab_adq, "Adquisición")
        tabs.addTab(self._tab_ana, "Análisis")
        tabs.addTab(self._tab_cvm, "Normalización CVM")

        central = QWidget()
        root = QVBoxLayout(central)
        root.addWidget(tabs, stretch=1)
        self.setCentralWidget(central)

        autor = QLabel("Dr. Agis-Torres — UCM")
        autor_font = QFont("Arial", 8)
        autor.setFont(autor_font)
        autor.setStyleSheet("color: #888888; padding: 0 6px;")
        self.statusBar().addPermanentWidget(autor)

    def closeEvent(self, event) -> None:
        self._tab_adq.cleanup()
        self._tab_ana.cleanup()
        self._tab_cvm.cleanup()
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("EMG Bioinstrumentacion")
    app.setOrganizationName("Bioinstrumentacion")

    settings = QSettings("Bioinstrumentacion", "EMGApp")

    splash = _make_splash()
    splash.show()
    app.processEvents()

    window = MainWindow(settings)

    # Cierra la splash y muestra la ventana tras 1.5 s
    QTimer.singleShot(1500, splash.close)
    QTimer.singleShot(1500, window.show)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
