"""The review shows the stretch each number was measured on (Ángel,
7 November 2026, before the bench of 10 November).

The bars of the review (#171) mark each contraction the fragment editor will
propose, whole. Inside each, a taller light green stretch edged in dark now
marks the part the analysis read its number on: in a gradation, each step's
plateau — from 1.5 s after it begins, without its rise or its letting go —
where its % MVC, RMS and MDF come from; with a fixed load, the held load its
fatigue was read on; in a free recording, each row of the contraction table.
Not for the quick contractions: the train is measured whole, which is the bar.
In the one-muscle practical only, for now.

What is drawn is read from the analysis's own result
(:func:`emgteach.guided.measured_in_file`), never worked out again: these
tests check that the numbers are computed on exactly those samples, that the
review draws exactly those stretches, and that no number of the analysis
changed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from emgteach.fragments import default_detection, recording_proposal
from emgteach.guided import measured_in_file
from emgteach.io import BufferedEdfWriter, ChannelInfo, list_edf_emg_channels
from tests.test_hasta_el_reposo_de_verdad import _gradacion, _gradacion_edf, _una_contraccion

pytestmark = pytest.mark.gui

FS = 1000
DETECCION = default_detection(3.0, 0.05)       # the one-muscle practical's
CIFRAS_ANTES = Path(__file__).with_name("cifras_antes_del_tramo_medido.json")


def _analizar(qapp, edf: str, fragmentos=None) -> dict:
    from emgteach.workers import AnalysisWorker

    worker = AnalysisWorker(edf_path=edf, channel_name=list_edf_emg_channels(edf)[0],
                            roi_segments=fragmentos, detection_kwargs=DETECCION)
    salida: list[dict] = []
    errores: list[str] = []
    worker.result_ready.connect(salida.append)
    worker.error.connect(errores.append)
    worker.start()
    worker.wait(120000)
    qapp.processEvents()
    assert salida, f"the worker gave no result: {errores}"
    return salida[0]


def _libre_edf(path: Path) -> str:
    with BufferedEdfWriter(str(path), channels=[
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(_una_contraccion(hueco=0.3, colita=0.8))
    return str(path)


def _sesiones(tmp_path: Path) -> dict[str, str]:
    from tests.test_contracciones_rapidas import _tren_sintetico
    from tests.test_fatiga_guiada import _carga_edf, _edf

    _s, senal, marcas = _tren_sintetico(10.0)
    return {
        "gradacion": _gradacion_edf(tmp_path / "g.edf", _gradacion()),
        "carga": _carga_edf(tmp_path / "carga.edf"),
        "tren": _edf(tmp_path / "tren.edf", marcas, senal),
        "libre": _libre_edf(tmp_path / "libre.edf"),
    }


def _iguales(a, b, tol: float = 1e-6) -> bool:
    """Two lists of ``(start, end)`` the same to within *tol* seconds."""
    return len(a) == len(b) and bool(np.allclose(np.asarray(a, dtype=float).reshape(-1, 2),
                                                 np.asarray(b, dtype=float).reshape(-1, 2),
                                                 atol=tol))


def _muestras(t0: float, t1: float) -> slice:
    return slice(round(t0 * FS), round(t1 * FS))


# ── What is measured is what is drawn ─────────────────────────────────────


def test_a_step_s_numbers_are_read_on_its_plateau_exactly(qapp, tmp_path: Path) -> None:
    r = _analizar(qapp, _gradacion_edf(tmp_path / "g.edf", _gradacion()))
    env, filt = r["emg_envelope"], r["emg_filtered"]
    assert len(r["grad_steps"]) == 5
    for p in r["grad_steps"]:
        tramo = _muestras(p.plateau_start_s, p.plateau_end_s)
        assert p.held_mv == float(np.mean(env[tramo]))
        assert p.rms_mv == float(np.sqrt(np.mean(filt[tramo] ** 2)))
        # Without its rise and its letting go.
        assert p.plateau_start_s >= p.start_s + 1.5 - 1e-9
        assert p.plateau_end_s < p.end_s
    # Analysed whole, the analysed signal starts at «recording»: the plateaus
    # in the file are those times moved by it.
    rec = r["kept_pieces"][0][0]
    assert _iguales(measured_in_file(r),
                    [(rec + p.plateau_start_s, rec + p.plateau_end_s) for p in r["grad_steps"]])


def test_a_free_recording_s_rows_are_read_on_their_stretch(qapp, tmp_path: Path) -> None:
    r = _analizar(qapp, _libre_edf(tmp_path / "libre.edf"))
    filt = r["emg_filtered"]
    assert r["contractions"]
    for c in r["contractions"]:
        assert c.rms_mv == float(np.sqrt(np.mean(filt[_muestras(c.start_s, c.end_s)] ** 2)))
    assert _iguales(measured_in_file(r), [(c.start_s, c.end_s) for c in r["contractions"]])


def test_with_fragments_chosen_the_stretches_go_back_to_the_file(qapp, tmp_path: Path) -> None:
    edf = _gradacion_edf(tmp_path / "g.edf", _gradacion())
    filas = [(f.start_s, f.end_s) for f in recording_proposal(edf, k=3.0, rest_fraction=0.05)]
    r = _analizar(qapp, edf, filas)
    tramos = measured_in_file(r)
    assert len(tramos) == len(r["grad_steps"]) == 5
    for (a, b), p, (x, y) in zip(tramos, r["grad_steps"], filas, strict=True):
        # Each inside its own fragment, as long as the plateau measured.
        assert x - 1e-6 <= a < b <= y + 1e-6
        assert b - a == pytest.approx(p.plateau_end_s - p.plateau_start_s, abs=1e-6)


def test_the_load_is_its_held_stretch_and_the_train_nothing(qapp, tmp_path: Path) -> None:
    sesiones = _sesiones(tmp_path)
    r = _analizar(qapp, sesiones["carga"])
    (a, b), = measured_in_file(r)
    assert (a, b) == pytest.approx(r["load_span"])
    assert b - a == pytest.approx(r["load"].seconds, abs=2e-3)
    assert measured_in_file(_analizar(qapp, sesiones["tren"])) == []
    assert measured_in_file({}) == []


# ── No number changes ─────────────────────────────────────────────────────


def _cifras(r: dict) -> dict:
    def f(x):
        return None if x is None else round(float(x), 6)

    return {
        "rms": f(r["rms_global"]), "mdf": f(r["mdf"]), "mnf": f(r["mnf"]),
        "dur": f(r["duration"]), "veredicto": r["fat_verdict"],
        "tabla": [[f(c.start_s), f(c.end_s), f(c.rms_mv), f(c.peak_pct), f(c.mdf_hz)]
                  for c in r["contractions"]],
        "escalones": [[p.k, f(p.start_s), f(p.end_s), f(p.held_mv), f(p.held_pct),
                       f(p.rms_mv), f(p.mdf_hz)] for p in r["grad_steps"]],
        "carga": None if r.get("load") is None else [
            f(r["load"].seconds), f(r["load"].mdf_trend.change_pct)],
        "tren": None if r.get("train") is None else [
            r["train"].n, f(r["train"].rate_hz), f(r["train"].seconds)],
    }


def test_no_number_of_the_analysis_changes(qapp, tmp_path: Path) -> None:
    """The four sessions analysed whole and on the fragments the editor
    proposes, against what main (7428a27) gave before this change."""
    antes = json.loads(CIFRAS_ANTES.read_text(encoding="utf-8"))
    for nombre, edf in _sesiones(tmp_path).items():
        filas = [(f.start_s, f.end_s) for f in recording_proposal(edf, k=3.0, rest_fraction=0.05)]
        assert _cifras(_analizar(qapp, edf)) == antes[nombre]["sin"], nombre
        assert _cifras(_analizar(qapp, edf, filas)) == antes[nombre]["con"], nombre


# ── The review ────────────────────────────────────────────────────────────


@pytest.fixture
def revision(qapp, tmp_path: Path):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget
    from emgteach.modes import MODE_SINGLE

    ajustes = QSettings("emgteach-test", "tramo-medido")
    ajustes.clear()
    log = LoggerWidget()
    tab = AcquisitionTab(log, ajustes)
    tab._mode = MODE_SINGLE
    yield tab
    tab.cleanup()
    tab.deleteLater()
    log.deleteLater()
    qapp.processEvents()


def _franjas(tab) -> list[tuple[float, float]]:
    import pyqtgraph as pg

    from emgteach.gui.acquisition.plots import _MEDIDO_ALTO

    return sorted(it.getRegion() for pw, it in tab._trazado._revision_items
                  if pw is tab._trazado._plot_env and isinstance(it, pg.LinearRegionItem)
                  and it.span == (0.0, _MEDIDO_ALTO))


def test_the_review_draws_what_the_analysis_measured(qapp, tmp_path: Path, revision) -> None:
    edf = _gradacion_edf(tmp_path / "g.edf", _gradacion())
    revision._trazado.show_recording(edf, revision._etiqueta_tramo,
                                     revision._contracciones_del_registro(edf))
    leyenda = revision._trazado._leyenda
    assert leyenda.isHidden()                  # nothing measured to explain yet
    r = _analizar(qapp, edf)
    revision.show_measured(edf, r)
    assert _iguales(_franjas(revision), measured_in_file(r))
    assert len(_franjas(revision)) == 5
    assert not leyenda.isHidden()
    assert not revision._trazado._leyenda_barra.isHidden()
    assert not revision._trazado._leyenda_medido.isHidden()
    # Analysed again on fragments, the stretches follow, the old ones gone.
    filas = [(f.start_s, f.end_s) for f in recording_proposal(edf, k=3.0, rest_fraction=0.05)]
    r2 = _analizar(qapp, edf, filas)
    revision.show_measured(edf, r2)
    assert _iguales(_franjas(revision), measured_in_file(r2))
    # Back to live: nothing of it is left, the legend neither.
    revision._trazado.leave_review()
    assert _franjas(revision) == [] and leyenda.isHidden()


def test_another_file_or_another_practical_draws_nothing(qapp, tmp_path: Path,
                                                          revision) -> None:
    from emgteach.modes import MODE_PAIR

    edf = _gradacion_edf(tmp_path / "g.edf", _gradacion())
    r = _analizar(qapp, edf)
    revision._trazado.show_recording(edf, revision._etiqueta_tramo,
                                     revision._contracciones_del_registro(edf))
    revision.show_measured(str(tmp_path / "otro.edf"), r)
    assert _franjas(revision) == []
    revision._mode = MODE_PAIR
    revision.show_measured(edf, r)
    assert _franjas(revision) == []
    # And the review is as it was: no legend under it.
    assert revision._trazado._leyenda.isHidden()
    # And with no review on, nothing either.
    revision._trazado.leave_review()
    revision._mode = "single"
    revision.show_measured(edf, r)
    assert _franjas(revision) == []


def test_the_analysis_tab_says_when_it_has_a_result(qapp, tmp_path: Path) -> None:
    """The window wires it to the review (app.py); the tab emits the file and
    its result when its first analysis ends."""
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget
    from tests.test_eventos_y_capturas import _until

    edf = _libre_edf(tmp_path / "libre.edf")
    ajustes = QSettings("emgteach-test", "tramo-medido-analisis")
    ajustes.clear()
    log = LoggerWidget()
    ana = AnalysisTab(log, ajustes)
    oido: list[tuple[str, dict]] = []
    ana.analysed.connect(lambda ruta, r: oido.append((ruta, r)))
    try:
        ana.adopt_recording(edf)
        _until(qapp, lambda: bool(oido), 60.0, "the first analysis")
        ruta, r = oido[0]
        assert Path(ruta) == Path(edf)
        assert measured_in_file(r)
    finally:
        if ana._worker is not None:
            ana._worker.wait(60000)
        ana.deleteLater()
        log.deleteLater()
        qapp.processEvents()


def test_the_window_wires_the_analysis_to_the_review() -> None:
    texto = Path(__file__).resolve().parents[1].joinpath(
        "src", "emgteach", "gui", "app.py").read_text(encoding="utf-8")
    assert "self._tab_ana.analysed.connect(self._tab_adq.show_measured)" in texto
