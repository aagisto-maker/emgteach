"""Lo que la aplicación ya sabía y no enseñaba.

Cuatro cosas se calculaban en cada análisis y no llegaban a la pantalla ni
al informe: hasta dónde llegó la tarea respecto a la referencia (y si eso
delata una calibración que no fue máxima), qué hizo el otro músculo en cada
repetición de la calibración, dónde está el 100 % en un panel en % CVM, y
qué hay que hacer cuando el panel está vacío. Y el resumen numérico era una
fila de «Etiqueta: valor» a 11 px, con barras entre medias, que obligaba a
leer una frase para encontrar un número.
"""

from __future__ import annotations

import pytest
from matplotlib.figure import Figure
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel, QToolButton
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table

from emgteach import i18n
from emgteach.gui.tabs.analysis import AnalysisTab
from emgteach.gui.tabs.mvc import MvcTab
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.mvc import mark_excess_over_100
from emgteach.phases import FROM_REPS, RepValue
from emgteach.reports import _seccion_calibracion

tr = i18n.tr


@pytest.fixture
def tab(qapp):
    t = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "sabido"))
    yield t
    t.deleteLater()
    qapp.processEvents()


@pytest.fixture
def cvm(qapp):
    t = MvcTab(LoggerWidget(), QSettings("emgteach-test", "sabido-cvm"))
    yield t
    t.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# The 100 % line on a % MVC axis
# ---------------------------------------------------------------------------


def _eje(top: float):
    ax = Figure().add_subplot(111)
    ax.plot([0.0, 1.0], [0.0, top])
    return ax


class TestTheHundredPercentLine:
    """A curve at 200 % of the reference used to look like any other peak."""

    def test_drawn_when_the_curve_goes_past_100(self) -> None:
        ax = _eje(150.0)
        antes = ax.get_ylim()
        mark_excess_over_100(ax, "Activation (% MVC)")
        assert any(float(ln.get_ydata()[0]) == 100.0 for ln in ax.lines[1:])
        assert ax.patches, "the excess above 100 % is shaded"
        assert ax.get_ylim() == antes, "the mark does not move the axis"

    def test_not_drawn_on_a_millivolt_axis(self) -> None:
        ax = _eje(150.0)
        mark_excess_over_100(ax, "Amplitude (mV)")
        assert len(ax.lines) == 1 and not ax.patches

    def test_not_drawn_when_nothing_exceeds_it(self) -> None:
        ax = _eje(80.0)
        mark_excess_over_100(ax, "% MVC")
        assert len(ax.lines) == 1 and not ax.patches


# ---------------------------------------------------------------------------
# The summary is a grid of cards
# ---------------------------------------------------------------------------


class TestTheSummaryIsCards:
    def test_captions_are_their_own_labels(self, tab) -> None:
        textos = {w.text() for w in tab.findChildren(QLabel)}
        for caption in ("Task maximum", "Mean frequency (MNF)", "Fatigue", "MVC"):
            assert tr(caption) in textos, caption

    def test_values_start_as_a_dash_with_no_caption_in_them(self, tab) -> None:
        for lbl in (tab._lbl_mnf, tab._lbl_mdf, tab._lbl_fatiga,
                    tab._lbl_pendiente, tab._lbl_rms_global, tab._lbl_iemg,
                    tab._lbl_duracion, tab._lbl_pico, tab._lbl_cvm):
            assert lbl.text() == "—"

    def test_the_fatigue_verdict_has_a_help_button(self, tab, monkeypatch) -> None:
        boton = tab._btn_ayuda_fatiga
        assert isinstance(boton, QToolButton) and boton.text() == "?"
        abiertos: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "emgteach.gui.tabs.analysis.QMessageBox.information",
            staticmethod(lambda parent, title, text, *a, **k: abiertos.append((title, text))),
        )
        boton.click()
        assert len(abiertos) == 1
        titulo, texto = abiertos[0]
        assert titulo == tr("Fatigue")
        assert "MDF" in texto and "R²" in texto


class TestTheTaskMaximumCard:
    """Computed on every analysis to decide whether to warn; the warning only
    fired past 150 %, so a task at 135 % of "maximum" got no word at all."""

    def test_shows_the_sustained_peak_of_each_muscle(self, tab) -> None:
        tab._actualizar_pico_tarea({
            "channel_name": "FCR", "channel_name_2": "ECR",
            "task_peak_pct": {"FCR": 135.2, "ECR": 70.4},
        })
        assert tab._lbl_pico.text() == f"135 % / 70 % {tr('MVC')}"
        assert "#B0243A" not in tab._lbl_pico.styleSheet()

    def test_says_so_in_red_when_the_calibration_was_not_a_maximum(self, tab) -> None:
        tab._actualizar_pico_tarea({
            "channel_name": "FCR", "task_peak_pct": {"FCR": 212.0},
            "mvc_implausible": True,
        })
        assert tr("not a maximum") in tab._lbl_pico.text()
        assert "#B0243A" in tab._lbl_pico.styleSheet()

    def test_a_dash_without_a_reference(self, tab) -> None:
        tab._actualizar_pico_tarea({"channel_name": "FCR"})
        assert tab._lbl_pico.text() == "—"


# ---------------------------------------------------------------------------
# Empty panels say what to do
# ---------------------------------------------------------------------------


def _texto_central(fig: Figure) -> str:
    return " ".join(t.get_text() for ax in fig.axes for t in ax.texts)


class TestEmptyPanelsSayWhatToDo:
    def test_the_analysis_panel_before_any_recording(self, tab) -> None:
        assert tr("Open a recording, or record one in Acquisition: it is "
                  "analysed on its own.") in _texto_central(tab._fig)

    def test_and_again_after_a_new_session(self, tab) -> None:
        tab._fig.clear()
        tab.reset()
        assert "Acquisition" in _texto_central(tab._fig) or (
            tr("Acquisition") in _texto_central(tab._fig)
        )

    def test_the_calibration_panel_too(self, cvm) -> None:
        esperado = tr("Open a recording with calibration, or record one in "
                      "Acquisition: the reference is computed on its own.")
        assert esperado in _texto_central(cvm._fig)
        cvm._fig.clear()
        cvm.reset()
        assert esperado in _texto_central(cvm._fig)


# ---------------------------------------------------------------------------
# The report carries the calibration
# ---------------------------------------------------------------------------


def _historia(result: dict) -> list:
    estilos = getSampleStyleSheet()
    story: list = []
    _seccion_calibracion(story, result, estilos["Heading2"], estilos["Normal"])
    return story


def _celdas(story: list) -> list[str]:
    return [
        str(c)
        for item in story if isinstance(item, Table)
        for fila in item._cellvalues
        for c in fila
    ]


def _parrafos(story: list) -> list[str]:
    return [p.text for p in story if isinstance(p, Paragraph)]


class TestTheReportSaysWhatTheCalibrationWas:
    def test_nothing_without_a_reference(self) -> None:
        assert _historia({}) == []
        assert _historia({"channel_name": "FCR", "mvc_ref": None}) == []

    def _resultado(self, **extra) -> dict:
        r = {
            "channel_name": "FCR", "mvc_ref": 0.094, "mvc_ref_source": FROM_REPS,
            "cal_reps": {0: [(1.0, 4.0), (6.0, 9.0), (11.0, 14.0)]},
            "task_peak_pct": {"FCR": 135.2},
            "cal_rep_values": {0: [
                RepValue(1, 0.081, 12.0), RepValue(2, 0.094, 35.0),
                RepValue(3, 0.060, 8.0),
            ]},
            "cal_channel_names": {0: "FCR"},
            "cal_keep": {0: {1, 2}},
        }
        r.update(extra)
        return r

    def test_reference_source_task_peak_and_repetitions(self) -> None:
        story = _historia(self._resultado())
        assert _parrafos(story)[0] == tr("Calibration (maximal voluntary contraction)")
        celdas = _celdas(story)
        assert "FCR" in celdas and "0.094 mV" in celdas
        assert any("3" in c and "repeti" in c for c in celdas), "the source names the reps"
        assert tr("{pct:.0f} % MVC (sustained 0.5 s)").format(pct=135.2) in celdas
        # The repetitions, with the other muscle's share and the discard.
        assert "0.081 mV" in celdas and "35 %" in celdas
        assert f"3 ({tr('discarded')})" in celdas
        assert "1" in celdas and "2" in celdas

    def test_the_warning_only_when_the_maximum_was_not_one(self) -> None:
        aviso = tr("The task exceeds the reference by a wide margin: the "
                   "calibration did not capture a maximum, so every "
                   "percentage in this report is too high in the same "
                   "proportion. Calibrate again with a genuinely maximal "
                   "contraction, against something that cannot move.")
        assert aviso not in _parrafos(_historia(self._resultado()))
        assert aviso in _parrafos(_historia(self._resultado(mvc_implausible=True)))

    def test_a_channel_without_a_name_is_numbered(self) -> None:
        story = _historia(self._resultado(cal_channel_names={}))
        assert tr("Channel {n}").format(n=1) in _celdas(story)
