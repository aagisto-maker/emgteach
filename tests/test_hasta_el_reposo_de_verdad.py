"""A fragment reaches the muscle's real rest, tails included (Ángel's
gradation of 6 November 2026).

On the bench the review shaded the session's phases — what the application
asked — and the signal went on 0.5-1.5 s past them: the subject lets go after
the tone. In the fragment editor each row ended where the envelope fell below
5 % of its peak, which on a strong step is many times the rest, and what
followed — the end of the letting go and a tail drawn dotted beside the row,
at ~60.5 s and ~90.5 s — was left out. And the gradation came in six rows for
five steps: a jerk at the start of the recording was one.

Now, where fragments end only at rest (the one-muscle practical), a row runs
on over the dotted rest line and takes every tail over it of at least 0.5 s
that starts less than a second after it, to where the envelope is back at rest
for a second; a gradation is proposed one row per step, with five expected;
and the review draws, under both plots, the rows the editor will propose. The
fixed load and the quick contractions keep the one row their analysis reads,
and every number of theirs is what it was.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach import fragments
from emgteach.fragments import (
    _COLITA_MIN_S,
    default_detection,
    one_per_step,
    recording_proposal,
    suggest_fragments,
)
from emgteach.guided import MARGIN_S, step_windows
from emgteach.io import BufferedEdfWriter, ChannelInfo, read_edf_markers
from emgteach.modes import MODE_SINGLE, mode_detection_k, mode_rest_fraction
from emgteach.mvc import mvc_ref_marker
from emgteach.phases import cal_end_marker, cal_start_marker, prep_start_marker, rec_start_marker
from emgteach.selection import REST_MIN_S, Segment
from emgteach.sessions import (
    GRADATION_STEPS_PCT,
    end_marker,
    header_marker,
    parse_session_markers,
    span_end_marker,
    span_start_marker,
)

FS = 1000
FILTROS = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}
REPOSO = 0.004


def _relajacion(amp: np.ndarray, t: np.ndarray, fin: float, nivel: float,
                dura: float) -> None:
    """The letting go after the cue: the level held 0.2 s more, then an
    exponential fall over *dura* seconds."""
    s = (t >= fin) & (t < fin + 0.2)
    amp[s] = nivel
    s = (t >= fin + 0.2) & (t < fin + 0.2 + dura)
    amp[s] = np.maximum(REPOSO, nivel * np.exp(-(t[s] - fin - 0.2) / (dura / 4)))


def _colita(amp: np.ndarray, t: np.ndarray, a: float, dura: float,
            alto: float = 0.008) -> None:
    """A small hump after the letting go, below the detector's line."""
    s = (t >= a) & (t < a + dura)
    amp[s] = np.maximum(amp[s], REPOSO + alto * np.sin(np.pi * (t[s] - a) / dura))


def _ruido(amp: np.ndarray, seed: int = 8) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, 1.0, amp.size) * amp


def _una_contraccion(*, hueco: float, colita: float, dur: float = 20.0) -> np.ndarray:
    """Rest, a contraction at 0.6 from 5 to 9 s, its letting go over 1 s,
    and a tail of *colita* seconds starting *hueco* seconds after it."""
    n = int(dur * FS)
    t = np.arange(n) / FS
    amp = np.full(n, REPOSO)
    amp[(t >= 5.0) & (t < 9.0)] = 0.6
    _relajacion(amp, t, 9.0, 0.6, 1.0)
    if colita > 0:
        _colita(amp, t, 10.2 + hueco, colita)
    return _ruido(amp)


def _filas(senal, rest_fraction: float = 0.05) -> list[tuple[float, float]]:
    return [(f.start_s, f.end_s) for f in suggest_fragments(
        senal, FS, FILTROS, default_k=3.0, rest_fraction=rest_fraction)
        if f.reason != "whole"]


def _iguales(a, b, tol: float = 0.011) -> bool:
    """Two lists of ``(start, end)`` the same to within *tol* seconds."""
    return len(a) == len(b) and bool(np.allclose(np.asarray(a, dtype=float),
                                                 np.asarray(b, dtype=float), atol=tol))


def _en_reposo_tras(senal, fin: float) -> bool:
    """Whether, in the second after *fin*, the envelope has no stretch over
    the dotted rest line as long as a tail."""
    env = fragments.envelope(senal, FS, FILTROS)
    linea = fragments.rest_level(env, FS, (0.0, senal.size / FS), 3.0)
    sobre = env[round(fin * FS):round((fin + REST_MIN_S) * FS)] > linea
    bordes = np.flatnonzero(np.diff(np.r_[0, sobre.astype(np.int8), 0]))
    return all(b - a < _COLITA_MIN_S * FS for a, b in zip(bordes[::2], bordes[1::2],
                                                         strict=True))


# ── The edge at rest ──────────────────────────────────────────────────────


def test_the_rules_numbers_are_the_ones_agreed() -> None:
    assert _COLITA_MIN_S == pytest.approx(0.5)
    assert REST_MIN_S == pytest.approx(1.0)


def test_a_row_takes_the_letting_go_and_a_tail_close_after_it() -> None:
    """The tail runs from 10.5 to 11.3 s, 0.3 s after the letting go."""
    senal = _una_contraccion(hueco=0.3, colita=0.8)
    filas = _filas(senal)
    assert len(filas) == 1
    a, b = filas[0]
    assert a == pytest.approx(5.0 - 0.5, abs=0.25)     # ROW_LEAD_S before it
    assert b >= 11.3
    # And it ends where the envelope is back at rest for a second: on this
    # noise, a stretch of it over the line of 0.54 s, 0.3 s after the tail,
    # is one more — the editor draws it dotted too.
    assert _en_reposo_tras(senal, b - 0.05)


def test_without_a_tail_the_row_ends_where_the_letting_go_does() -> None:
    senal = _una_contraccion(hueco=0.0, colita=0.0)
    _a, b = _filas(senal)[0]
    # The fall reaches rest at about 10.2 s; 5 % of the peak, 0.03 mV, is
    # crossed at about 9.9 s.
    assert b >= 10.2
    assert _en_reposo_tras(senal, b - 0.05)


def test_a_tail_a_second_or_more_after_is_not_the_row_s() -> None:
    _a, b = _filas(_una_contraccion(hueco=1.6, colita=0.8))[0]
    assert b < 11.0                                    # the tail starts at 11.8


def test_a_blip_shorter_than_half_a_second_is_not_a_tail() -> None:
    _a, b = _filas(_una_contraccion(hueco=0.3, colita=0.25))[0]
    assert b < 10.7                                    # the blip ends at 10.75


def test_a_row_never_runs_into_the_next() -> None:
    """A second contraction 1.2 s after the first one's letting go: two rows,
    the first one's tail taken, and the two apart."""
    n = int(25 * FS)
    t = np.arange(n) / FS
    amp = np.full(n, REPOSO)
    amp[(t >= 5.0) & (t < 9.0)] = 0.6
    _relajacion(amp, t, 9.0, 0.6, 0.6)
    _colita(amp, t, 10.0, 0.6)
    amp[(t >= 11.8) & (t < 15.0)] = 0.5
    _relajacion(amp, t, 15.0, 0.5, 0.6)
    filas = _filas(_ruido(amp))
    assert len(filas) == 2
    assert filas[0][1] >= 10.55
    assert filas[0][1] < filas[1][0]


def test_a_series_less_than_a_second_apart_is_one_row_whole() -> None:
    """The bench's free recording of 6 November: brisk contractions with
    less than a second of rest between them are one fragment (the rule of
    27 October), and the detector found them so; but the row was fitted from
    its peak to the first dip, and kept only its first contraction, the rest
    left dotted beside it."""
    n = int(20 * FS)
    t = np.arange(n) / FS
    amp = np.full(n, REPOSO)
    for i, nivel in enumerate((0.4, 0.25, 0.3, 0.2, 0.3)):
        a = 4.0 + 1.1 * i
        amp[(t >= a) & (t < a + 0.6)] = nivel
    filas = _filas(_ruido(amp))
    assert len(filas) == 1
    assert filas[0][0] < 4.0 and filas[0][1] >= 4.0 + 1.1 * 4 + 0.6


def test_where_rows_are_cut_at_valleys_nothing_changes() -> None:
    """The pair practical and kinematics: no tail is taken."""
    _a, b = _filas(_una_contraccion(hueco=0.3, colita=0.8), rest_fraction=0.0)[0]
    assert b < 10.5                                    # the tail starts at 10.5


# ── The gradation: one row per step ───────────────────────────────────────

CAL = [(2.0, 5.0), (8.0, 11.0), (14.0, 17.0)]
REC = 22.0


def _gradacion(*, sacudida: bool = True, sin_paso: int | None = None) -> np.ndarray:
    """The bench's gradation: a jerk 0.3 s after «recording», five steps of
    4 s reached in a second, each let go over 0.5-1.5 s after its end mark
    and followed 0.3 s later by a tail of 0.6 s. With *sin_paso*, that step
    (from 1) is not made."""
    n = int((REC + 60.0) * FS)
    t = np.arange(n) / FS
    amp = np.full(n, REPOSO)
    for a, b in CAL:
        amp[int(a * FS):int(b * FS)] = 1.0
    if sacudida:
        s = (t >= REC + 0.3) & (t < REC + 1.5)
        amp[s] = np.maximum(amp[s], 0.12 * np.sin(np.pi * (t[s] - REC - 0.3) / 1.2))
    for k, (pct, rel) in enumerate(zip(GRADATION_STEPS_PCT, np.linspace(0.5, 1.5, 5),
                                       strict=True)):
        if sin_paso == k + 1:
            continue
        a = REC + 5.0 + 10.0 * k
        b, nivel = a + 4.0, pct / 100
        s = (t >= a + 0.3) & (t < b)
        amp[s] = nivel * np.clip((t[s] - a - 0.3) / 1.0, 0.0, 1.0)
        _relajacion(amp, t, b, nivel, rel)
        _colita(amp, t, b + 0.2 + rel + 0.3, 0.6)
    return _ruido(amp)


def _fin_de_colita(k: int) -> float:
    """Where step *k*'s tail ends (from 1)."""
    return REC + 9.0 + 10.0 * (k - 1) + 0.2 + float(np.linspace(0.5, 1.5, 5)[k - 1]) + 0.9


def _gradacion_edf(path: Path, senal: np.ndarray) -> str:
    with BufferedEdfWriter(str(path), channels=[
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(senal)
        for i, (a, b) in enumerate(CAL, start=1):
            w.add_annotation(a, cal_start_marker(0, i))
            w.add_annotation(b, cal_end_marker(0, i))
        w.add_annotation(17.5, mvc_ref_marker(0, 0.8))
        w.add_annotation(REC - 2.0, prep_start_marker())
        w.add_annotation(REC, rec_start_marker())
        w.add_annotation(REC, header_marker("GRAD", steps=5))
        for k, pct in enumerate(GRADATION_STEPS_PCT, start=1):
            a = REC + 5.0 + (k - 1) * 10.0
            w.add_annotation(a, span_start_marker("GRAD", "step", k=k, pct=pct))
            w.add_annotation(a + 4.0, span_end_marker("GRAD", "step", k=k))
        w.add_annotation(REC + 54.0, end_marker("GRAD"))
    return str(path)


def _sesion(edf: str):
    sesion = parse_session_markers(read_edf_markers(edf))
    assert sesion is not None
    return sesion


def test_the_step_windows_run_on_past_each_step(tmp_path: Path) -> None:
    ventanas = step_windows(_sesion(_gradacion_edf(tmp_path / "g.edf", _gradacion())))
    assert len(ventanas) == 5
    for k, (a, b) in enumerate(ventanas):
        assert a == pytest.approx(REC + 5.0 + 10.0 * k)
        assert b == pytest.approx(a + 4.0 + MARGIN_S)
    assert step_windows(None) == []


def test_a_gradation_is_one_row_per_step_and_the_jerk_is_left_out(tmp_path: Path) -> None:
    senal = _gradacion()
    ventanas = step_windows(_sesion(_gradacion_edf(tmp_path / "g.edf", senal)))
    span = (REC, REC + 54.0)
    # Without the steps, the jerk is a sixth row — what the bench saw.
    libres = suggest_fragments(senal, FS, FILTROS, span=span, default_k=3.0,
                               rest_fraction=0.05)
    assert len(libres) == 6 and libres[0].start_s < REC + 1.5
    filas = suggest_fragments(senal, FS, FILTROS, span=span, default_k=3.0,
                              rest_fraction=0.05, steps=ventanas)
    assert len(filas) == 5
    for k, (f, (a, _b)) in enumerate(zip(filas, ventanas, strict=True), start=1):
        assert a - 0.5 <= f.start_s < a + 1.0
        # Each to the end of its tail, and not a second further.
        assert _fin_de_colita(k) - 0.05 <= f.end_s <= _fin_de_colita(k) + 0.4


def test_a_step_the_detector_found_nothing_in_is_its_window(tmp_path: Path) -> None:
    senal = _gradacion(sin_paso=3)
    ventanas = step_windows(_sesion(_gradacion_edf(tmp_path / "g.edf", senal)))
    filas = suggest_fragments(senal, FS, FILTROS, span=(REC, REC + 54.0), default_k=3.0,
                              rest_fraction=0.05, steps=ventanas)
    assert len(filas) == 5
    assert filas[2].reason == "marker"
    assert (filas[2].start_s, filas[2].end_s) == pytest.approx(ventanas[2], abs=0.01)


def test_a_step_split_in_two_by_the_detector_is_one_row() -> None:
    env = np.full(30 * FS, 0.002)
    env[5 * FS:8 * FS] = 0.3
    env[int(8.6 * FS):10 * FS] = 0.3
    detectadas = [Segment(5.0, 8.0), Segment(8.6, 10.0), Segment(20.0, 21.0)]
    filas = one_per_step(detectadas, [(5.0, 10.5)], [env], FS, (0.0, 30.0),
                         default_detection(3.0, 0.05))
    assert len(filas) == 1
    assert filas[0].start_s <= 5.0 and filas[0].end_s >= 10.0


@pytest.mark.gui
def test_the_editor_expects_five_and_leaves_the_jerk_dotted(qapp, tmp_path: Path) -> None:
    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

    edf = _gradacion_edf(tmp_path / "g.edf", _gradacion())

    class _Pestana:
        _mode = MODE_SINGLE

        def _escalones_marcados(self, path):
            return AnalysisTab._escalones_marcados(self, path)  # type: ignore[arg-type]

    pestana = _Pestana()
    pasos = pestana._escalones_marcados(edf)
    assert len(pasos) == 5
    assert AnalysisTab._esperadas_de_la_sesion(pestana, edf) == (5,)  # type: ignore[arg-type]
    # The span the analysis tab gives it: from «recording» to the file's end.
    dlg = FragmentSelectionDialog.from_edf(
        edf, "FCR", FILTROS, span=(REC, REC + 60.0), naming=False,
        default_k=mode_detection_k(MODE_SINGLE),
        default_rest_fraction=mode_rest_fraction(MODE_SINGLE),
        expected=(5,), steps=pasos)
    try:
        assert len(dlg.selected_segments()) == 5
        assert dlg.expected_counts() == (5,)
        punteadas = dlg._candidatos_libres()
        assert any(c.start_s < REC + 1.5 for c in punteadas)        # the jerk
        # What the editor opens on is what the review draws.
        assert _iguales(dlg.selected_segments(), [
            (f.start_s, f.end_s) for f in recording_proposal(
                edf, k=mode_detection_k(MODE_SINGLE),
                rest_fraction=mode_rest_fraction(MODE_SINGLE))])
    finally:
        dlg.deleteLater()


@pytest.mark.gui
def test_the_steps_measures_hold_with_the_tails_in(qapp, tmp_path: Path) -> None:
    """The level, RMS and MDF of a step are read on its plateau: the tail
    lengthens the row, not the step."""
    from tests.test_fatiga_guiada import _analizar_fragmentos

    senal = _gradacion()
    edf = _gradacion_edf(tmp_path / "g.edf", senal)
    filas = recording_proposal(edf, k=3.0, rest_fraction=0.05)
    r = _analizar_fragmentos(qapp, edf, [(f.start_s, f.end_s) for f in filas])
    pasos = r["grad_steps"]
    assert [p.target_pct for p in pasos] == list(GRADATION_STEPS_PCT)
    for p in pasos:
        assert p.held_pct == pytest.approx(p.target_pct, abs=6.0)
        assert 3.5 <= p.duration_s <= 4.6
    assert len(r["contractions"]) == 5


# ── The review draws the same rows ────────────────────────────────────────


@pytest.mark.gui
def test_the_review_draws_a_bar_under_each_row_the_editor_proposes(
    qapp, tmp_path: Path
) -> None:
    import pyqtgraph as pg
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    edf = _gradacion_edf(tmp_path / "g.edf", _gradacion())
    ajustes = QSettings("emgteach-test", "hasta-el-reposo")
    ajustes.clear()
    log = LoggerWidget()
    tab = AcquisitionTab(log, ajustes)
    try:
        tab._mode = MODE_SINGLE
        filas = tab._contracciones_del_registro(edf)
        assert _iguales(filas, [
            (f.start_s, f.end_s) for f in recording_proposal(edf, k=3.0, rest_fraction=0.05)])
        assert len(filas) == 5
        tab._trazado.show_recording(edf, tab._etiqueta_tramo, filas)
        barras = [(pw, it) for pw, it in tab._trazado._revision_items
                  if isinstance(it, pg.LinearRegionItem) and it.span == (0.0, 0.07)]
        assert len(barras) == 2 * len(filas)                  # raw and envelope
        assert _iguales(sorted(it.getRegion() for pw, it in barras
                               if pw is tab._trazado._plot_env), filas, 1e-9)
        # The phases are still shaded behind them.
        assert any(isinstance(it, pg.LinearRegionItem) and it.span != (0.0, 0.07)
                   for _pw, it in tab._trazado._revision_items)
        tab._trazado.leave_review()
        assert tab._trazado._revision_items == []
    finally:
        tab.cleanup()
        tab.deleteLater()
        log.deleteLater()
        qapp.processEvents()


def test_a_free_recording_is_proposed_as_the_editor_does(tmp_path: Path) -> None:
    """No session, no phases: the whole file, the practical's rule."""
    senal = _una_contraccion(hueco=0.3, colita=0.8)
    edf = tmp_path / "libre.edf"
    with BufferedEdfWriter(str(edf), channels=[
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(senal)
    filas = recording_proposal(str(edf), k=3.0, rest_fraction=0.05)
    leida, _fs, _otra = fragments.read_channels(str(edf), "FCR")
    assert _iguales([(f.start_s, f.end_s) for f in filas], _filas(leida), 1e-9)


# ── The fixed load and the quick contractions are what they were ──────────

#: Measured on main (ce5229a) before this change, with the same synthetic
#: sessions: the window the editor proposes, and the analysis with no
#: fragment chosen and with that window chosen.
_ANTES = {
    "carga": {"ventana": (17.946, 55.077), "rms": 0.26358, "mdf": 153.31,
              "veredicto": "fatigue", "carga_s": 34.538, "carga_mdf_pct": -57.22,
              "con_fragmentos": {"rms": 0.26052, "mdf": 156.31,
                                 "carga_mdf_pct": -57.219}},
    "tren": {"ventana": (17.5, 27.951), "rms": 0.13985, "mdf": 190.91,
             "veredicto": "inconclusive", "tren_n": 39, "tren_hz": 4.021,
             "con_fragmentos": {"rms": 0.16469, "mdf": 191.04, "tren_n": 40}},
}


def _carga_y_tren(tmp_path: Path) -> dict[str, str]:
    from tests.test_contracciones_rapidas import _tren_sintetico
    from tests.test_fatiga_guiada import _carga_edf, _edf

    _s, senal, marcas = _tren_sintetico(10.0)
    return {"carga": _carga_edf(tmp_path / "carga.edf"),
            "tren": _edf(tmp_path / "tren.edf", marcas, senal)}


@pytest.mark.gui
def test_the_fixed_load_and_the_quick_contractions_do_not_change(
    qapp, tmp_path: Path
) -> None:
    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog
    from tests.test_fatiga_guiada import _analizar_fragmentos
    from tests.test_gradacion import _analizar

    for nombre, edf in _carga_y_tren(tmp_path).items():
        antes = _ANTES[nombre]
        r = _analizar(qapp, edf)
        ventana = r.get("load_row") or r.get("train_span")
        assert ventana == pytest.approx(antes["ventana"], abs=1e-3)
        assert r["rms_global"] == pytest.approx(antes["rms"], abs=1e-5)
        assert r["mdf"] == pytest.approx(antes["mdf"], abs=0.01)
        assert r["fat_verdict"] == antes["veredicto"]
        if nombre == "carga":
            assert r["load"].seconds == pytest.approx(antes["carga_s"], abs=1e-3)
            assert r["load"].mdf_trend.change_pct == pytest.approx(
                antes["carga_mdf_pct"], abs=1e-3)
        else:
            assert r["train"].n == antes["tren_n"]
            assert r["train"].rate_hz == pytest.approx(antes["tren_hz"], abs=1e-3)
        # The editor opens on that one window, as before, and so does the
        # review's bar.
        dlg = FragmentSelectionDialog.from_edf(
            edf, "BIC", FILTROS, naming=False, default_k=3.0,
            default_rest_fraction=0.05, session_window=ventana)
        filas = dlg.selected_segments()
        dlg.deleteLater()
        assert _iguales(filas, [ventana], 0.006)
        revision = recording_proposal(edf, k=3.0, rest_fraction=0.05)
        assert _iguales([(f.start_s, f.end_s) for f in revision], [ventana], 0.006)
        # Analysed on it, the numbers are those of before.
        r2 = _analizar_fragmentos(qapp, edf, filas)
        despues = antes["con_fragmentos"]
        assert r2["rms_global"] == pytest.approx(despues["rms"], abs=1e-5)
        assert r2["mdf"] == pytest.approx(despues["mdf"], abs=0.01)
        if nombre == "carga":
            assert r2["load"].mdf_trend.change_pct == pytest.approx(
                despues["carga_mdf_pct"], abs=1e-3)
        else:
            assert r2["train"].n == despues["tren_n"]


def test_the_rows_of_a_load_or_a_train_do_not_use_the_tail_rule(tmp_path: Path) -> None:
    """They end by their own rule (guided._fin_de_fila), checked on the bench
    with exe #145: the review's bar is that row."""
    for edf in _carga_y_tren(tmp_path).values():
        filas = recording_proposal(edf, k=3.0, rest_fraction=0.05)
        assert len(filas) == 1 and filas[0].reason == "session"
    assert fragments.recording_proposal is recording_proposal
