"""The gradation: five steps of growing strength, marked and measured.

From the script to the numbers: the script the acquisition runs (steps,
times, marks, words in both languages), the measurement of each step from
its marks (the level held after the reach, its RMS and MDF), the analysis
worker giving one contraction row per step, the bar chart, the report's
section and the phones' line. And, with the simulated board, a gradation
recorded in the acquisition tab and analysed.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from emgteach.charts import draw_steps_chart
from emgteach.guided import (
    MARGIN_S,
    SETTLE_S,
    StepResult,
    gradation_steps,
    is_monotonic,
    spans_in_analysis_time,
)
from emgteach.i18n import _ES, tr
from emgteach.io import BufferedEdfWriter, ChannelInfo, read_edf_markers
from emgteach.mvc import mvc_ref_marker
from emgteach.phases import cal_end_marker, cal_start_marker, prep_start_marker, rec_start_marker
from emgteach.sessions import (
    EFFORT,
    GRADATION_STEPS_PCT,
    MeasuredSpan,
    end_marker,
    gradation_script,
    header_marker,
    parse_session_markers,
    span_end_marker,
    span_start_marker,
)

# The acquisition tab on the simulated board, from the session tests.
from tests.test_sesion_guiada_en_la_pestana import tab, tonos  # noqa: F401

FS = 1000

# ── The script ────────────────────────────────────────────────────────────


def test_five_steps_from_twenty_to_the_maximum() -> None:
    g = gradation_script()
    pasos = [f for f in g.phases if f.kind == EFFORT]
    assert GRADATION_STEPS_PCT == (20, 40, 60, 80, 100)
    assert [f.level for f in pasos] == [0.2, 0.4, 0.6, 0.8, 1.0]
    assert [f.opens for f in pasos] == [
        span_start_marker("GRAD", "step", k=k, pct=p)
        for k, p in enumerate(GRADATION_STEPS_PCT, start=1)]
    assert all(f.seconds == 4.0 for f in pasos)
    assert g.header == "GRAD start steps=5 v=1"


def test_it_calibrates_first_and_lasts_under_a_minute() -> None:
    """Ángel's decision of 24 October: without the bar there is no grading."""
    g = gradation_script()
    assert g.needs_mvc and g.family == "GRAD" and g.slug == "graduales"
    assert g.title == "Graded contractions" and _ES[g.title] == "Contracciones graduales"
    assert g.total_seconds == 54.0


def test_every_step_aims_at_a_band_around_its_target() -> None:
    for f in gradation_script().phases:
        if f.kind == EFFORT:
            lo, hi = f.target_pct
            assert lo < f.level * 100 <= hi


def test_the_marks_of_a_run_read_back_as_five_steps() -> None:
    marcas = [(0.0, gradation_script().header)]
    for f in gradation_script().timed():
        if f.opens:
            marcas.append((f.start, f.opens))
        if f.closes:
            marcas.append((f.end, f.closes))
    marcas.append((54.0, end_marker("GRAD")))
    s = parse_session_markers(marcas)
    assert s is not None and s.completed
    assert [t.number("pct") for t in s.spans] == [20, 40, 60, 80, 100]


def _sesiones():
    from emgteach.gui.tabs.acquisition import GUIDED_SESSIONS

    return [construir() for construir in GUIDED_SESSIONS.values()]


def test_the_gradation_is_offered() -> None:
    from emgteach.gui.tabs.acquisition import GUIDED_SESSIONS

    assert "gradacion" in GUIDED_SESSIONS


def test_every_word_of_every_session_is_in_spanish_and_in_usted() -> None:
    """The catalogue test looks for tr("…") literals; a session's words are
    data, translated when shown, so they are checked here."""
    for script in _sesiones():
        textos = [script.title, script.summary]
        for f in script.phases:
            textos += [f.title, f.text]
        for texto in filter(None, textos):
            assert texto in _ES, texto
        for f in script.phases:
            campos = dict(f.fmt)
            # The placeholders survive the translation.
            _ES[f.title].format(**campos)
            if f.text:
                _ES[f.text].format(**campos)


# ── Measuring the steps ───────────────────────────────────────────────────


def _sesion_sintetica(t0: float = 0.0):
    marcas = [(t0, header_marker("GRAD", steps=5))]
    for k, pct in enumerate(GRADATION_STEPS_PCT, start=1):
        a = t0 + 5.0 + (k - 1) * 10.0
        marcas += [(a, span_start_marker("GRAD", "step", k=k, pct=pct)),
                   (a + 4.0, span_end_marker("GRAD", "step", k=k))]
    marcas.append((t0 + 54.0, end_marker("GRAD")))
    sesion = parse_session_markers(marcas)
    assert sesion is not None
    return sesion


def _senales(niveles_por_paso, *, alcance: float = 0.0, t0: float = 0.0,
             tarde: tuple[float, float] = (0.0, 0.0)):
    """An envelope with each step at its level, and a filtered signal whose
    RMS is that level, for a 60 s recording starting at *t0*. With *tarde*,
    the subject begins and lets go that many seconds after each cue."""
    n = int((t0 + 60.0) * FS)
    env = np.full(n, 0.01)
    for k, nivel in enumerate(niveles_por_paso):
        a = int((t0 + 5.0 + k * 10.0 + tarde[0]) * FS)
        env[a: a + int((4.0 - tarde[0] + tarde[1]) * FS)] = nivel
        if alcance:
            # The reach: an overshoot in the first second, which the level
            # held must leave out.
            env[a: a + int(alcance * FS)] = 3 * nivel
    rng = np.random.default_rng(3)
    filt = rng.normal(0.0, 1.0, n) * env
    return env, filt


def test_the_level_held_is_the_envelope_after_the_reach() -> None:
    niveles = [0.2, 0.4, 0.6, 0.8, 1.0]
    env, filt = _senales(niveles, alcance=SETTLE_S)
    pasos = gradation_steps(_sesion_sintetica(), [(0.0, 60.0, 0.0)], fs=FS,
                            emg_filtered=filt, envelope=env, mvc_ref=1.0)
    assert [p.k for p in pasos] == [1, 2, 3, 4, 5]
    assert [p.target_pct for p in pasos] == [20, 40, 60, 80, 100]
    for p, nivel in zip(pasos, niveles, strict=True):
        assert p.held_mv == pytest.approx(nivel, rel=1e-6)
        assert p.held_pct == pytest.approx(100 * nivel, rel=1e-6)
        assert p.rms_mv == pytest.approx(nivel, rel=0.05)
        assert p.mdf_hz is not None and 20 < p.mdf_hz < 450
    assert is_monotonic(pasos)


def test_without_a_reference_the_level_is_in_millivolts() -> None:
    env, filt = _senales([0.2, 0.4, 0.6, 0.8, 1.0])
    pasos = gradation_steps(_sesion_sintetica(), [(0.0, 60.0, 0.0)], fs=FS,
                            emg_filtered=filt, envelope=env, mvc_ref=None)
    assert all(p.held_pct is None for p in pasos) and is_monotonic(pasos)


def test_the_steps_are_found_in_the_analysed_signals_time() -> None:
    """The analysis starts at REC start: the steps move with it."""
    env, filt = _senales([0.2, 0.4, 0.6, 0.8, 1.0], t0=20.0)
    env, filt = env[20 * FS:], filt[20 * FS:]          # the analysed span
    pasos = gradation_steps(_sesion_sintetica(t0=20.0), [(20.0, 80.0, 0.0)], fs=FS,
                            emg_filtered=filt, envelope=env, mvc_ref=1.0)
    assert [round(p.held_pct) for p in pasos] == [20, 40, 60, 80, 100]
    assert pasos[0].start_s == pytest.approx(5.0)


def test_a_late_subject_is_measured_on_the_contraction_not_on_the_cues() -> None:
    """Ángel's bench with the board, 26 October 2026: the subject begins some
    tenths of a second after the cue and lets go up to a second after the
    end. Each step is the contraction found inside its marks run on past
    their end, and its level the plateau of that contraction: no rest at its
    start, and its end not lost."""
    niveles = [0.2, 0.4, 0.6, 0.8, 1.0]
    env, filt = _senales(niveles, tarde=(0.4, 0.8))
    pasos = gradation_steps(_sesion_sintetica(), [(0.0, 60.0, 0.0)], fs=FS,
                            emg_filtered=filt, envelope=env, mvc_ref=1.0)
    for k, (p, nivel) in enumerate(zip(pasos, niveles, strict=True)):
        assert p.start_s == pytest.approx(5.4 + 10.0 * k, abs=0.01)
        assert p.end_s == pytest.approx(9.8 + 10.0 * k, abs=0.01)
        assert p.held_mv == pytest.approx(nivel, rel=1e-6)


def test_the_margin_never_reaches_the_next_stretch() -> None:
    from emgteach.guided import MARGIN_S, measured_windows

    sesion = _sesion_sintetica()
    ventanas = measured_windows(sesion, [(0.0, 60.0, 0.0)], ("step",))
    assert [round(b - a, 6) for _t, a, b in ventanas] == [4.0 + MARGIN_S] * 5
    # Two stretches one second apart: the first stops short of the second.
    juntas = parse_session_markers([
        (0.0, "HOLD start mode=intermittent v=1"),
        (1.0, "HOLD rep start n=1"), (6.0, "HOLD rep end n=1"),
        (7.0, "HOLD rep start n=2"), (12.0, "HOLD rep end n=2"),
        (12.5, "HOLD end")])
    (_t1, a1, b1), (_t2, _a2, b2) = measured_windows(juntas, [(0.0, 20.0, 0.0)])
    assert a1 == 1.0 and b1 == pytest.approx(6.75)
    # Nor past the session's end, nor past the piece the analysis kept.
    assert b2 == pytest.approx(12.5)
    (_t, a, b), = measured_windows(juntas, [(6.5, 13.0, 0.0)])
    assert (a, b) == (pytest.approx(0.5), pytest.approx(6.0))


def test_a_step_across_a_cut_is_left_out() -> None:
    tramo = MeasuredSpan("step", 10.0, 14.0, {"k": "1"})
    assert spans_in_analysis_time([tramo], [(0.0, 12.0, 0.0), (13.0, 30.0, 12.0)]) == []
    assert spans_in_analysis_time([tramo], [(8.0, 30.0, 3.0)]) == [(tramo, 5.0, 9.0)]


def test_a_recording_without_a_gradation_has_no_steps() -> None:
    env, filt = _senales([0.5] * 5)
    assert gradation_steps(None, [(0.0, 60.0, 0.0)], fs=FS, emg_filtered=filt,
                           envelope=env, mvc_ref=1.0) == []
    hold = parse_session_markers([(0.0, "HOLD start v=1"), (1.0, "HOLD end")])
    assert gradation_steps(hold, [(0.0, 60.0, 0.0)], fs=FS, emg_filtered=filt,
                           envelope=env, mvc_ref=1.0) == []


def test_a_step_that_fell_short_breaks_the_monotony() -> None:
    def paso(k, nivel):
        return StepResult(k, 20.0 * k, 0, 4, nivel, nivel * 100, nivel, None)

    assert is_monotonic([paso(1, 0.2), paso(2, 0.4)])
    assert not is_monotonic([paso(1, 0.2), paso(2, 0.4), paso(3, 0.35)])
    assert not is_monotonic([paso(1, 0.2)])


def test_the_bars_draw_in_both_units_and_with_nothing() -> None:
    from matplotlib.figure import Figure

    env, filt = _senales([0.2, 0.4, 0.6, 0.8, 1.0])
    for ref in (1.0, None):
        pasos = gradation_steps(_sesion_sintetica(), [(0.0, 60.0, 0.0)], fs=FS,
                                emg_filtered=filt, envelope=env, mvc_ref=ref)
        fig = Figure()
        draw_steps_chart(fig, pasos)
        assert len(fig.axes[0].patches) == 5
    fig = Figure()
    draw_steps_chart(fig, [])
    assert fig.axes[0].texts


# ── The analysis worker, on a gradation written to a file ─────────────────

CAL_REPS = [(2.0, 5.0), (8.0, 11.0), (14.0, 17.0)]
REC_S = 22.0


def _gradacion_edf(path: Path, *, ruido: bool = False, maximo: float = 1.0) -> str:
    """A one-muscle session: three maximal efforts at amplitude 1, the
    countdown, and the gradation at 20…100 % of it — its maximal step at
    *maximo*. With *ruido*, the signal is noise and not a sine: an envelope
    with the ripple of a real one, whose peak stands above its mean."""
    n = int((REC_S + 60.0) * FS)
    t = np.arange(n) / FS
    amp = np.full(n, 0.01)
    for a, b in CAL_REPS:
        amp[int(a * FS): int(b * FS)] = 1.0
    sesion = _sesion_sintetica(t0=REC_S)
    for tramo in sesion.spans:
        pct = tramo.number("pct") or 0
        amp[int(tramo.start_s * FS): int(tramo.end_s * FS)] = (
            maximo if pct >= 100 else pct / 100)
    portadora = (np.random.default_rng(8).normal(0.0, 0.35, n) if ruido
                 else np.sin(2 * np.pi * 80 * t))
    senal = portadora * amp
    with BufferedEdfWriter(str(path), channels=[
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(senal)
        for i, (a, b) in enumerate(CAL_REPS, start=1):
            w.add_annotation(a, cal_start_marker(0, i))
            w.add_annotation(b, cal_end_marker(0, i))
        w.add_annotation(17.5, mvc_ref_marker(0, 0.6))
        w.add_annotation(REC_S - 2.0, prep_start_marker())
        w.add_annotation(REC_S, rec_start_marker())
        w.add_annotation(REC_S, header_marker("GRAD", steps=5))
        for k, pct in enumerate(GRADATION_STEPS_PCT, start=1):
            a = REC_S + 5.0 + (k - 1) * 10.0
            w.add_annotation(a, span_start_marker("GRAD", "step", k=k, pct=pct))
            w.add_annotation(a + 4.0, span_end_marker("GRAD", "step", k=k))
        w.add_annotation(REC_S + 54.0, end_marker("GRAD"))
    return str(path)


def _analizar(qapp, edf: str) -> dict:
    pytest.importorskip("mne")
    from emgteach.io import list_edf_emg_channels
    from emgteach.workers import AnalysisWorker

    worker = AnalysisWorker(edf_path=edf, channel_name=list_edf_emg_channels(edf)[0])
    errores: list[str] = []
    worker.error.connect(errores.append)
    salida: list[dict] = []
    worker.result_ready.connect(salida.append)
    worker.start()
    worker.wait(120000)
    qapp.processEvents()
    assert salida, f"the worker gave no result: {errores}"
    return salida[0]


@pytest.mark.gui
def test_the_analysis_gives_one_row_per_step_in_percent_of_the_maximum(
    qapp, tmp_path: Path
) -> None:
    r = _analizar(qapp, _gradacion_edf(tmp_path / "grad.edf"))
    assert r["guided_session"] is not None and r["guided_session"].family == "GRAD"
    filas = r["contractions"]
    assert len(filas) == 5
    # The rows are the steps, in the analysed span's time (from REC start).
    for fila, k in zip(filas, range(5), strict=True):
        assert fila.start_s == pytest.approx(5.0 + 10.0 * k, abs=0.6)
    pasos = r["grad_steps"]
    assert [p.target_pct for p in pasos] == [20, 40, 60, 80, 100]
    # Measured against the maximum the calibration spans give, the level
    # each step held is the one it was asked for.
    for p in pasos:
        assert p.held_pct == pytest.approx(p.target_pct, abs=6.0)
    assert is_monotonic(pasos)
    # The session's marks do not draw: they are not the student's.
    assert not any(m.startswith("GRAD") for _t, m in r["markers"])


@pytest.mark.gui
def test_the_report_has_the_gradation_and_the_phones_get_its_steps(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    from emgteach.reports import build_session_report
    from tests.test_informes_y_csv import _pdf_text

    r = _analizar(qapp, _gradacion_edf(tmp_path / "grad.edf"))
    pdf = tmp_path / "grad.pdf"
    build_session_report(pdf, r, meta={})
    texto = _pdf_text(pdf)
    assert tr("Guided session: graded contractions") in texto
    assert tr("Each step held more than the one before.") in texto

    from tests.test_manejo_en_aula import _Difusion

    dif = _Difusion()

    class _Tab:
        _broadcast = dif

        def _broadcast_on(self) -> bool:
            return True

    from emgteach.gui.tabs.analysis import AnalysisTab

    AnalysisTab._bcast_results(_Tab(), r)       # type: ignore[arg-type]
    pasos = dif.mensajes[-1]["steps"]
    assert [p[0] for p in pasos] == [20, 40, 60, 80, 100]
    assert all(abs(a - b) <= 6 for a, b in pasos)


# ── Recorded in the acquisition tab, with the simulated board ──────────────


@pytest.mark.gui
def test_a_gradation_recorded_with_the_simulated_board_is_analysed_by_steps(
    qapp, request, tmp_path: Path, monkeypatch
) -> None:
    """The whole way: the chooser, the countdown, the five steps asked of the
    simulated subject, the automatic stop, the analysis. Shortened (0.8 s
    the countdown and the edges, 1.6 s a step and a rest) and without the
    calibration, which has its own tests: so the level is in millivolts, and
    each step above the last.

    The mark is written at the samples the worker has received and the
    subject changes at the ones the board has made: on a loaded runner the
    change lands up to some tenths of a second after its mark. With 0.8 s
    steps the level was held over the lag (CI, Windows, 25 Oct 2026: step 3
    below step 2); with 0.8 s rests, now that a step is its contraction run
    on past its end, a step and the next merged across a rest the lag had
    eaten (26 Oct 2026: step 5 below step 4). 1.6 s each leaves room for it."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from tests.test_marcas_manuales import _until
    from tests.test_sesion_guiada_en_la_pestana import _choose, _record

    pestana = request.getfixturevalue("tab")
    corta = dataclasses.replace(gradation_script().with_seconds(0.8), needs_mvc=False)
    # The steps and the rests between them; the edges and the countdown stay short.
    entre = {f.key for f in corta.phases if f.kind == EFFORT} | {
        f.key for f in corta.phases[1:-1] if f.key.startswith("rest_")}
    corta = dataclasses.replace(corta, phases=tuple(
        dataclasses.replace(f, seconds=1.6) if f.key in entre else f for f in corta.phases))
    monkeypatch.setitem(acq_mod.GUIDED_SESSIONS, "gradacion", lambda: corta)
    pestana._rellenar_sesiones()
    _choose(pestana, "gradacion")
    path = tmp_path / "grad_sim.edf"
    _record(qapp, pestana, path)
    _until(qapp, lambda: not pestana.is_recording(), 0.5 + corta.total_seconds + 10.0,
           "the gradation to end")
    _until(qapp, lambda: pestana._eventos is None, 5.0, "the event log")
    r = _analizar(qapp, str(path))
    pasos = r["grad_steps"]
    assert len(pasos) == 5 and len(r["contractions"]) == 5
    assert is_monotonic(pasos), [p.held_mv for p in pasos]


@pytest.mark.gui
def test_a_late_subject_on_the_simulated_board_gives_whole_steps(
    qapp, request, tmp_path: Path, monkeypatch
) -> None:
    """Ángel's bench with the board (26 October 2026), rehearsed: a subject
    who begins 0.4 s after each cue and lets go 0.8 s after its end. Each
    step, and each row of the table, is the whole contraction — begun after
    its mark and run on past its end — and not the stretch between the cues."""
    from emgteach.devices.bitalino_sim import _SyntheticSubject
    from emgteach.gui.tabs import acquisition as acq_mod
    from tests.test_marcas_manuales import _until
    from tests.test_sesion_guiada_en_la_pestana import _choose, _record

    monkeypatch.setattr(_SyntheticSubject, "reaction_s", 0.4)
    monkeypatch.setattr(_SyntheticSubject, "release_s", 0.8)
    pestana = request.getfixturevalue("tab")
    corta = dataclasses.replace(gradation_script().with_seconds(2.0), needs_mvc=False)
    monkeypatch.setitem(acq_mod.GUIDED_SESSIONS, "gradacion", lambda: corta)
    pestana._rellenar_sesiones()
    _choose(pestana, "gradacion")
    path = tmp_path / "grad_tarde.edf"
    _record(qapp, pestana, path)
    _until(qapp, lambda: not pestana.is_recording(), 0.5 + corta.total_seconds + 10.0,
           "the gradation to end")
    _until(qapp, lambda: pestana._eventos is None, 5.0, "the event log")
    r = _analizar(qapp, str(path))
    pasos, filas = r["grad_steps"], r["contractions"]
    assert len(pasos) == 5 and len(filas) == 5
    assert is_monotonic(pasos), [p.held_mv for p in pasos]
    marcas = r["guided_session"].spans_named("step")
    for p, fila, marca in zip(pasos, filas, marcas, strict=True):
        inicio = p.start_s + r["roi_start_s"] - marca.start_s
        fin = p.end_s + r["roi_start_s"] - marca.end_s
        # Begun after its cue, and run on past its end: the 0.4 and 0.8 s
        # of the subject, plus whatever the board and the worker add — on a
        # loaded runner up to the margin itself (CI, Windows, 26 Oct 2026).
        assert 0.2 < inicio < 1.5, inicio
        assert 0.4 < fin <= MARGIN_S + 1e-6, fin
        assert fila.start_s == pytest.approx(p.start_s, abs=0.15)
        assert fila.end_s == pytest.approx(p.end_s, abs=0.15)


# ── The tuned recording keeps the session ──────────────────────────────────


@pytest.mark.gui
def test_a_tuned_gradation_keeps_its_steps_and_their_view(qapp, tmp_path: Path) -> None:
    """Ángel's bench, 26 October 2026: after «Select fragments» and «Save
    tuned EDF», the «_tuned» file had lost the session — no «Steps» view, no
    level asked or held — because each step's start mark is its cue, in the
    rest the fragments leave out. The marks are written again round the kept
    fragments, and the tuned file reopens with its five steps."""
    from emgteach.tuning import build_tuned_edf

    origen = _gradacion_edf(tmp_path / "grad.edf")
    # The fragments the editor proposes: round each contraction, with its
    # rise and its fall — a little rest before it and after it.
    fragmentos = [(REC_S + 4.5 + 10.0 * k, REC_S + 9.8 + 10.0 * k) for k in range(5)]
    afinado = tmp_path / "grad_tuned.edf"
    build_tuned_edf(origen, afinado, fragments=fragmentos)

    sesion = parse_session_markers(read_edf_markers(afinado))
    assert sesion is not None and sesion.family == "GRAD" and sesion.completed
    assert [t.number("pct") for t in sesion.spans_named("step")] == [20, 40, 60, 80, 100]

    r = _analizar(qapp, str(afinado))
    pasos = r["grad_steps"]
    assert [p.target_pct for p in pasos] == [20, 40, 60, 80, 100]
    assert len(r["contractions"]) == 5
    for p in pasos:
        assert p.held_pct == pytest.approx(p.target_pct, abs=6.0)
    # Reopened, the tuned file tunes again the same way.
    otra = tmp_path / "grad_tuned_2.edf"
    build_tuned_edf(afinado, otra)
    assert parse_session_markers(read_edf_markers(otra)).spans == sesion.spans


# ── The gradation's maximum, measured like the level held ────────────────


@pytest.mark.gui
def test_the_gradation_measures_its_maximum_as_a_half_second_mean(
    qapp, tmp_path: Path
) -> None:
    """Ángel's bench, 26 October 2026: with the maximum on the envelope's
    peak, a step held at the calibration's own intensity read 85-87 %, so the
    bar's 100 % could not be held. In the gradation the maximum is the
    highest mean over half a second, like the level held: on a noisy
    envelope each step reads what it was asked for."""
    from emgteach.dsp import process_offline
    from emgteach.io import read_edf_mne
    from emgteach.mvc import mvc_peak_hold
    from emgteach.sessions import GRAD_MVC_WINDOW_S

    edf = _gradacion_edf(tmp_path / "grad_ruido.edf", ruido=True)
    r = _analizar(qapp, edf)
    datos = read_edf_mne(edf, "FCR")
    env = process_offline(datos["emg_raw"], FS)["emg_envelope"]
    ventana = round(GRAD_MVC_WINDOW_S * FS)
    medias = [mvc_peak_hold(env[int(a * FS): int(b * FS)], ventana) for a, b in CAL_REPS]
    picos = [float(env[int(a * FS): int(b * FS)].max()) for a, b in CAL_REPS]
    assert r["mvc_ref"] == pytest.approx(max(medias), rel=0.01)
    assert max(picos) > 1.05 * r["mvc_ref"]           # the peak would be another number
    for p in r["grad_steps"]:
        assert p.held_pct == pytest.approx(p.target_pct, abs=6.0), (p.target_pct, p.held_pct)


@pytest.mark.gui
def test_a_maximal_step_above_the_calibration_is_said(qapp, tmp_path: Path) -> None:
    """The reference stays the MVC; a maximal step above it is told, in the
    view and the report, not hidden."""
    from emgteach.guided import gradation_reference_text
    from emgteach.reports import build_session_report
    from tests.test_informes_y_csv import _pdf_text

    r = _analizar(qapp, _gradacion_edf(tmp_path / "grad127.edf", ruido=True, maximo=1.27))
    assert r["grad_steps"][-1].held_pct == pytest.approx(127.0, abs=8.0)
    texto = gradation_reference_text(r)
    assert texto is not None and "0.5 s" in texto and "went above" in texto
    pdf = tmp_path / "grad127.pdf"
    build_session_report(pdf, r, meta={})
    assert "went above the calibration" in _pdf_text(pdf).replace("\n", " ")


def test_only_the_gradation_calibrates_with_a_window() -> None:
    from types import SimpleNamespace

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.modes import MODE_PAIR, MODE_SINGLE
    from emgteach.profiles import EMG_PROFILE
    from emgteach.sessions import GRAD_MVC_WINDOW_S, hold_script

    perfil = EMG_PROFILE
    for modo, guion, esperado in (
        (MODE_SINGLE, gradation_script(), GRAD_MVC_WINDOW_S),
        (MODE_SINGLE, hold_script(), perfil.mvc_peak_window_s),
        (MODE_SINGLE, None, perfil.mvc_peak_window_s),
        (MODE_PAIR, gradation_script(), perfil.mvc_peak_window_s),
    ):
        pestana = SimpleNamespace(_mode=modo, _session_script=guion, _profile=perfil)
        assert AcquisitionTab._ventana_cvm_s(pestana) == esperado    # type: ignore[arg-type]
