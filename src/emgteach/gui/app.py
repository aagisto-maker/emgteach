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

from PySide6.QtCore import QLibraryInfo, QSettings, Qt, QTimer, QTranslator, qInstallMessageHandler
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
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
from emgteach.modes import (
    DEFAULT_MODE,
    MODES,
    mode_complexity_colour,
    mode_complexity_label,
    mode_label,
    mode_shows_fine_controls,
    normalise_mode,
)

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

        # What a student almost always wants is to analyse and normalise the
        # recording they just made, so it travels between the tabs instead of
        # being hunted for three times. Opening a file by hand in Analysis
        # feeds the MVC tab the same way.
        # One chain, not two branches: the recording reaches the MVC tab
        # *through* the Analysis tab, carrying the muscle chosen there. Wiring
        # both tabs to the acquisition directly made each ask which muscle,
        # so the same question came up twice in a row.
        self._tab_adq.recording_saved.connect(self._tab_ana.adopt_recording)
        self._tab_ana.file_opened.connect(self._tab_cvm.adopt_recording)

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
        self._combo_mode.setToolTip(tr("Practical the app is set up for"))
        self._combo_mode.currentIndexChanged.connect(self._on_mode_changed)

        # The level of detail is a property of the practical, not a second
        # switch beside it: two independent axes meant the user had to hold
        # both in mind to know why a control was on screen or not. The fine
        # controls belong to the kinematics practical, and this says which
        # level the current one is at.
        #
        # It used to be a band across the whole window. That is a lot of
        # emphasis for a caption that repeats what the selector beside it
        # already implies — the practicals are in order, so choosing one is
        # choosing its level — and the emphasis is what a reader takes as
        # importance. It sits beside the selector now, at the selector's own
        # width: same colour, same words, a fifth of the room.
        self._lbl_nivel = QLabel()
        self._lbl_nivel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_nivel.setContentsMargins(8, 3, 8, 3)
        self._lbl_nivel.setFixedWidth(self._combo_mode.sizeHint().width())

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
        btn_tour.setToolTip(tr("App and measures tour"))
        btn_tour.clicked.connect(self.start_tour)

        # The map answers a different question from the tour: not "what does
        # this control do" but "where am I in the process, and what is left".
        btn_mapa = QToolButton()
        btn_mapa.setText(tr("Map"))
        btn_mapa.setAutoRaise(True)
        btn_mapa.setToolTip(tr("Location in the process"))
        btn_mapa.clicked.connect(self.show_mapa)

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
        corner_lay.addWidget(self._lbl_nivel)
        corner_lay.addWidget(self._combo_lang)
        corner_lay.addWidget(btn_tour)
        corner_lay.addWidget(btn_mapa)
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
        msg.setWindowTitle(tr("Quick guide"))
        msg.setText(
            tr(
                "The electrical activity of a muscle is recorded and turned "
                "into measurements that can be interpreted. The application "
                "works with "
                "either of two sensors: a BITalino over Bluetooth or an "
                "Arduino + MyoWare 2.0 over USB.\n\nFor a short walkthrough "
                "of the application, press Yes."
            )
        )
        chk = QCheckBox(tr("Show this guide next time"))
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
                tr("Stop the recording before starting the guide"),
            )
            return
        self._coach.start(build_tour(self), on_tab=self._tabs.setCurrentIndex)

    def _mode(self) -> str:
        """Stored recording mode, defaulting to the single-muscle practical."""
        return normalise_mode(self._settings.value("app/mode", DEFAULT_MODE))

    def _advanced(self) -> bool:
        """Whether the fine controls are on screen — now a property of the mode.

        Kept as a method because the tabs and the tour ask the window for it;
        what changed is that nothing can set it independently of the practical.
        """
        return mode_shows_fine_controls(self._mode())

    def _apply_mode(self) -> None:
        mode = self._mode()
        for tab in (self._tab_adq, self._tab_ana, self._tab_cvm):
            tab.apply_mode(mode, mode_shows_fine_controls(mode))
        self._refresh_nivel_band()

    def _refresh_nivel_band(self) -> None:
        """Colour and caption of the level tag beside the practical selector.

        The full caption is kept as the tooltip: at the selector's width a
        long translation would be elided, and the word that gets cut is the
        one that says the level.
        """
        mode = self._mode()
        color = mode_complexity_colour(mode)
        texto = mode_complexity_label(mode)
        self._lbl_nivel.setText(texto)
        self._lbl_nivel.setToolTip(texto)
        self._lbl_nivel.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: bold; "
            "font-size: 11px; border-radius: 3px;"
        )

    def _on_mode_changed(self, index: int) -> None:
        self._settings.setValue("app/mode", self._combo_mode.itemData(index))
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

    def show_mapa(self) -> None:
        """Open the map at the practical and the tab currently in view."""
        from emgteach.gui.widgets.mapa_dialog import MapaDialog

        dlg = MapaDialog(self._mode(), self._tabs.currentIndex(), self)
        dlg.show()          # modeless: it is for consulting while you work
        self._mapa_dlg = dlg    # keep a reference or Qt collects it at once

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


def install_qt_translations(app: QApplication, language: str) -> QTranslator | None:
    """Translate Qt's own strings — the standard dialog buttons above all.

    "Yes", "No", "OK", "Cancel" and "Save" do not come from
    :mod:`emgteach.i18n`: Qt draws them itself and translates them from its own
    catalogue, so with no translator installed a Spanish interface still
    asks the user to press "Yes". PySide6 ships qtbase_es, which is all it
    takes.

    The translator is returned so the caller can keep a reference to it:
    dropping it uninstalls the translations.
    """
    if language == "en":
        return None
    translator = QTranslator()
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if not translator.load(f"qtbase_{language}", path):
        return None
    app.installTranslator(translator)
    return translator


def main() -> None:
    # Before anything else: a crash from here on leaves a traceback on disk and
    # says so, instead of vanishing into a console the windowed build lacks.
    from emgteach.crash import install_crash_log

    install_crash_log()
    _install_qt_message_filter()
    app = QApplication(sys.argv)
    app.setApplicationName("EMG Bioinstrumentacion")
    app.setOrganizationName("Bioinstrumentacion")

    settings = QSettings("Bioinstrumentacion", "EMGApp")
    # Set the language (saved or auto-detected) before building the interface.
    language = resolve_startup_language(settings)
    set_language(language)
    # Kept on the application so it is not garbage-collected.
    app._qt_translator = install_qt_translations(app, language)

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
