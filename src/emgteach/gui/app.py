"""
EMG App — entry point.

Creates the QApplication, shows a brief splash screen, builds the
QMainWindow with three tabs (Acquisition, Analysis, MVC) and starts the
event loop. On close, it calls cleanup() on each tab to ensure all
workers finish before exiting.

The interface language (English/Spanish) is set at start-up; the selector
changes it for the next restart (see emgteach.i18n).
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QSettings, Qt, QTimer, qInstallMessageHandler
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplashScreen,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from emgteach import __version__
from emgteach.broadcast import BroadcastServer
from emgteach.gui.tabs.acquisition import AcquisitionTab
from emgteach.gui.tabs.analysis import AnalysisTab
from emgteach.gui.tabs.mvc import MvcTab
from emgteach.gui.tour import build_tour
from emgteach.gui.widgets.coach import CoachMark
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.i18n import get_language, resolve_startup_language, set_language, tr
from emgteach.modes import DEFAULT_MODE, MODES, mode_label, normalise_mode

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
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, tr("EMG Bioinstrumentation"))

    sub_font = QFont("Arial", 11)
    p.setFont(sub_font)
    p.setPen(QColor("#aaccee"))
    sub_rect = px.rect().adjusted(0, 80, 0, 0)
    p.drawText(sub_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
               tr("Surface EMG acquisition"))

    author_font = QFont("Arial", 9)
    p.setFont(author_font)
    p.setPen(QColor(220, 220, 220))
    author_rect = px.rect().adjusted(0, 152, 0, 0)
    p.drawText(author_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
               "Dr. Agis-Torres et al. — UCM")

    p.end()

    splash = QSplashScreen(px, Qt.WindowType.WindowStaysOnTopHint)
    return splash


# ---------------------------------------------------------------------------
# Shared styling for all tabs
# ---------------------------------------------------------------------------
# Light-gray window background, steel-blue boxes (QGroupBox) and white plot
# areas (plot frames use the objectName "plotsBox"; the matplotlib canvases
# of the Analysis/MVC tabs are already white). The title's top margin keeps
# the first control row from overlapping the title.
_APP_STYLESHEET = (
    "AcquisitionTab, AnalysisTab, MvcTab { background-color: #E1E6EB; }"
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
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.setWindowTitle(tr("EMG Bioinstrumentation"))
        self.resize(1100, 780)

        self._settings = settings

        # Logger shared by all tabs
        self._logger = LoggerWidget()

        # Classroom broadcast — shared so the Analysis tab can also push its
        # results/report to the student followers (the Acquisition tab owns the
        # on/off toggle and the live stream).
        self._broadcast = BroadcastServer(parent=self)

        # Tabs
        self._tab_adq = AcquisitionTab(self._logger, settings, broadcast=self._broadcast)
        self._tab_ana = AnalysisTab(self._logger, settings, broadcast=self._broadcast)
        self._tab_cvm = MvcTab(self._logger, settings)

        # Shared styling: each tab's gray background (class selector) is only
        # painted if the widget has WA_StyledBackground.
        for tab in (self._tab_adq, self._tab_ana, self._tab_cvm):
            tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_APP_STYLESHEET)

        tabs = QTabWidget()
        tabs.addTab(self._tab_adq, tr("Acquisition"))
        tabs.addTab(self._tab_ana, tr("Analysis"))
        tabs.addTab(self._tab_cvm, tr("MVC normalisation"))

        # Tab-bar corner: mode, advanced toggle, language and "About" (no
        # status bar, zero vertical cost).
        # The mode says which practical this is. It fixes the channel count and
        # whether the accelerometer is used, and the tabs offer only what that
        # practical needs. Unlike the language, it applies without restarting.
        self._combo_mode = QComboBox()
        for mode in MODES:
            self._combo_mode.addItem(mode_label(mode), mode)
        self._combo_mode.setCurrentIndex(MODES.index(self._mode()))
        self._combo_mode.setToolTip(tr("Which practical the app is set up for"))
        self._combo_mode.currentIndexChanged.connect(self._on_mode_changed)

        # Orthogonal to the mode: the fine controls that apply to all three
        # practicals alike (filter cut-offs, region of interest, thresholds,
        # onset detection, classroom broadcast).
        self._chk_advanced = QCheckBox(tr("Advanced options"))
        self._chk_advanced.setChecked(self._advanced())
        self._chk_advanced.setToolTip(
            tr("Show the fine controls shared by every mode")
        )
        self._chk_advanced.toggled.connect(self._on_advanced_changed)

        self._combo_lang = QComboBox()
        self._combo_lang.addItem("English", "en")
        self._combo_lang.addItem("Español", "es")
        self._combo_lang.setCurrentIndex(0 if get_language() == "en" else 1)
        self._combo_lang.setToolTip(tr("Interface language"))
        self._combo_lang.currentIndexChanged.connect(self._on_language_changed)

        # Relaunches the guided tour at any time. Offered once on a first run
        # and then never again by itself: a tour that reappears becomes a
        # formality to dismiss rather than something anyone reads.
        btn_tour = QToolButton()
        btn_tour.setText(tr("Guide"))
        btn_tour.setAutoRaise(True)
        btn_tour.setToolTip(tr("Walk through the app and what it measures"))
        btn_tour.clicked.connect(self.start_tour)

        btn_about = QToolButton()
        btn_about.setText("?")
        btn_about.setAutoRaise(True)
        btn_about.setToolTip(tr("About EMG Bioinstrumentation"))
        btn_about.clicked.connect(self._show_about)

        # New-session button: clears all three tabs back to a just-opened state
        # (e.g. when switching to a new student) without restarting the app.
        btn_reset = QToolButton()
        btn_reset.setText(tr("New session"))
        btn_reset.setToolTip(tr("Clear everything and start over (e.g. a new student)"))
        btn_reset.clicked.connect(self._on_reset_all)

        corner = QWidget()
        corner_lay = QHBoxLayout(corner)
        corner_lay.setContentsMargins(0, 0, 4, 0)
        corner_lay.setSpacing(2)
        corner_lay.addWidget(btn_reset)
        corner_lay.addWidget(self._combo_mode)
        corner_lay.addWidget(self._chk_advanced)
        corner_lay.addWidget(self._combo_lang)
        corner_lay.addWidget(btn_tour)
        corner_lay.addWidget(btn_about)
        tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.addWidget(tabs, stretch=1)
        self.setCentralWidget(central)

        # Apply the stored mode once every tab exists and is laid out.
        self._apply_mode()

        self._tabs = tabs
        self._coach = CoachMark(self)

    # ------------------------------------------------------------------
    # Guided tour
    # ------------------------------------------------------------------

    def maybe_offer_tour(self) -> None:
        """Offer the tour at start-up, unless it has been turned off.

        Kept on by default rather than shown once: a teaching machine sees a
        different student most sessions, and each of them is a first run. The
        tick box is how the person who owns the machine turns it off, so the
        decision belongs to them and not to whoever happened to open the app
        first.
        """
        if not self._settings.value("app/tour_offer", True, type=bool):
            return

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(tr("A quick guide?"))
        msg.setText(
            tr(
                "This is a teaching application: it records the electrical "
                "activity of a muscle and turns it into measurements you can "
                "interpret. It works with either of two sensors — a BITalino "
                "over Bluetooth, or an Arduino + MyoWare 2.0 over USB — and "
                "behaves the same way with both.\n\nWould you like a short "
                "walkthrough of what each control does and what it means "
                "physiologically? It takes a couple of minutes, and you can "
                "reopen it later with the \"Guide\" button."
            )
        )
        chk = QCheckBox(tr("Offer this guide next time"))
        chk.setChecked(True)
        msg.setCheckBox(chk)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        answer = msg.exec()

        self._settings.setValue("app/tour_offer", chk.isChecked())
        if answer == QMessageBox.StandardButton.Yes:
            self.start_tour()

    def start_tour(self) -> None:
        """Run the walkthrough for the mode currently selected."""
        if self._tab_adq.is_recording():
            QMessageBox.information(
                self,
                tr("Guide"),
                tr("Stop the recording before starting the guide."),
            )
            return
        self._coach.start(build_tour(self), on_tab=self._tabs.setCurrentIndex)

    def _mode(self) -> str:
        """Stored recording mode, defaulting to the single-muscle practical."""
        return normalise_mode(self._settings.value("app/mode", DEFAULT_MODE))

    def _advanced(self) -> bool:
        return bool(self._settings.value("app/advanced", False, type=bool))

    def _apply_mode(self) -> None:
        mode, advanced = self._mode(), self._advanced()
        for tab in (self._tab_adq, self._tab_ana, self._tab_cvm):
            tab.apply_mode(mode, advanced)

    def _on_mode_changed(self, index: int) -> None:
        self._settings.setValue("app/mode", self._combo_mode.itemData(index))
        self._apply_mode()

    def _on_advanced_changed(self, checked: bool) -> None:
        self._settings.setValue("app/advanced", checked)
        self._apply_mode()

    def _on_language_changed(self, index: int) -> None:
        code = self._combo_lang.itemData(index)
        self._settings.setValue("app/language", code)
        QMessageBox.information(
            self,
            tr("Language"),
            tr("The language change will take effect when you restart the application."),
        )

    def _on_reset_all(self) -> None:
        """Clear all tabs to a fresh state (new student) without restarting.

        Refuses while a recording is in progress; the saved EDF files on disk
        are never deleted. Asks for confirmation first.
        """
        if self._tab_adq.is_recording():
            QMessageBox.information(
                self,
                tr("New session"),
                tr("Stop the recording before starting a new session."),
            )
            return
        resp = QMessageBox.question(
            self,
            tr("New session"),
            tr(
                "Clear everything and start a new session?\n\n"
                "This clears the on-screen data, markers, log, calibration and "
                "the loaded analysis. The EDF files already saved on disk are "
                "not deleted."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        self._tab_adq.reset()
        self._tab_ana.reset()
        self._tab_cvm.reset()
        self._logger.clear()
        self._logger.append_log(tr("New session started."))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("About EMG Bioinstrumentation"),
            f"<b>{tr('EMG Bioinstrumentation')}</b><br>"
            f"{tr('Version')} {__version__}<br><br>"
            "Dr. Agis-Torres et al. — UCM<br>"
            f"{tr('Physiology Department, Complutense University of Madrid')}",
        )

    def closeEvent(self, event) -> None:
        self._tab_adq.cleanup()
        self._tab_ana.cleanup()
        self._tab_cvm.cleanup()
        self._broadcast.stop()
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _install_qt_message_filter() -> None:
    """Drop a benign, noisy Qt/pyqtgraph font warning seen on some systems
    ("QFont::setPointSize: Point size <= 0 (-1)"), emitted while pyqtgraph
    renders axis labels. Everything else is forwarded to stderr unchanged so
    real Qt diagnostics are still visible.
    """
    def _handler(mode, context, message) -> None:
        if "Point size <= 0" in message:
            return
        sys.stderr.write(message + "\n")

    qInstallMessageHandler(_handler)


def main() -> None:
    _install_qt_message_filter()
    app = QApplication(sys.argv)
    app.setApplicationName("EMG Bioinstrumentacion")
    app.setOrganizationName("Bioinstrumentacion")

    settings = QSettings("Bioinstrumentacion", "EMGApp")
    # Set the language (saved or auto-detected) before building the interface.
    set_language(resolve_startup_language(settings))

    splash = _make_splash()
    splash.show()
    app.processEvents()

    window = MainWindow(settings)

    # Close the splash and show the window after 1.5 s. Start maximised so the
    # whole interface fits the screen (and toggling the ACC plot redistributes
    # space within the window instead of pushing it off-screen).
    QTimer.singleShot(1500, splash.close)
    QTimer.singleShot(1500, window.showMaximized)
    # Offered from here rather than from the window's constructor: it is
    # start-up behaviour, and a modal opened while the window is still being
    # built would block anything that creates a MainWindow without a user in
    # front of it. It also has to wait until the controls have a position, or
    # the coach mark would have nothing to point at.
    QTimer.singleShot(1600, window.maybe_offer_tour)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
