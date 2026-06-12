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
    QMainWindow,
    QMessageBox,
    QSplashScreen,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from emgteach import __version__
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
# Estética compartida por todas las pestañas
# ---------------------------------------------------------------------------
# Fondo de ventana gris claro, cajas (QGroupBox) en azul acero y zona de
# gráficas en blanco (los marcos de gráficas usan objectName "plotsBox"; los
# lienzos matplotlib de Análisis/CVM ya son blancos). El margen superior del
# título evita que la primera fila de controles se solape con el título.
_APP_STYLESHEET = (
    "AcquisitionTab, AnalysisTab, MvcTab { background-color: #D6DCE2; }"
    "QGroupBox {"
    "  background-color: #DCE7F4;"
    "  border: 1px solid #A7C2DF;"
    "  border-radius: 6px;"
    "  margin-top: 16px;"
    "  padding-top: 4px;"
    "  font-weight: bold;"
    "}"
    "QGroupBox::title {"
    "  subcontrol-origin: margin;"
    "  subcontrol-position: top left;"
    "  left: 8px;"
    "  padding: 0 4px;"
    "  color: #1F4E79;"
    "}"
    "QGroupBox#plotsBox { background-color: #FFFFFF; }"
    "QScrollArea { border: none; background: transparent; }"
)


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

        # Estética compartida: el fondo gris de cada pestaña (selector por clase)
        # solo se pinta si el widget tiene WA_StyledBackground.
        for tab in (self._tab_adq, self._tab_ana, self._tab_cvm):
            tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_APP_STYLESHEET)

        tabs = QTabWidget()
        tabs.addTab(self._tab_adq, "Adquisición")
        tabs.addTab(self._tab_ana, "Análisis")
        tabs.addTab(self._tab_cvm, "Normalización CVM")

        # Botón "Acerca de" en la esquina de la barra de pestañas: muestra la
        # autoría y la versión sin ocupar espacio vertical (sin barra de estado).
        btn_about = QToolButton()
        btn_about.setText("?")
        btn_about.setAutoRaise(True)
        btn_about.setToolTip("Acerca de EMG Bioinstrumentación")
        btn_about.clicked.connect(self._show_about)
        tabs.setCornerWidget(btn_about, Qt.Corner.TopRightCorner)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.addWidget(tabs, stretch=1)
        self.setCentralWidget(central)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "Acerca de EMG Bioinstrumentación",
            f"<b>EMG Bioinstrumentación</b><br>"
            f"Versión {__version__}<br><br>"
            "Dr. Agis-Torres — UCM<br>"
            "Facultad de Farmacia, Universidad Complutense de Madrid",
        )

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
