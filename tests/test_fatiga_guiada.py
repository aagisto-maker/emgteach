"""The fatigue session: a fixed weight held with the biceps until it tires.

From the script to the numbers. The bench of 26 October 2026 (Ángel's biceps,
a fixed weight, elbow at 90°) showed what the session must read: the MDF fell
16-20 % in 90 s with p ~ 1e-8 and an R² of only 0.3, while the RMS rose. So
the verdict is the MDF's slope, significant (p < 0.01) and of at least 10 %,
not an R² threshold; the analysis starts 2 s after the activity does (picking
up the weight is not the contraction that tires) and ends where the activity
falls; and the student may end the effort early with the space bar. And the
envelope filter's own share of the level between quick contractions, which
the manuals' note on successive contractions quotes.
"""

from __future__ import annotations

import dataclasses
import math
import time
from pathlib import Path

import numpy as np
import pytest

from emgteach.dsp import compute_psd_mnf_mdf, process_offline
from emgteach.fatigue import FATIGUE, INCONCLUSIVE, NO_FATIGUE
from emgteach.guided import (
    LOAD_SKIP_S,
    REST_WARN_MV,
    Trend,
    change_pct,
    effort_ratio,
    load_fatigue,
    load_piece,
    load_span,
    load_verdict,
    rest_level,
    time_to_decline,
    weak_signal_warning,
)
from emgteach.i18n import _ES, tr
from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.phases import prep_start_marker, rec_start_marker
from emgteach.sessions import (
    EFFORT,
    LOAD_DEFAULT_S,
    LOAD_MAX_S,
    READY,
    end_marker,
    load_script,
    parse_session_markers,
)

# The acquisition tab on the simulated board, from the session tests.
from tests.test_sesion_guiada_en_la_pestana import tab, tonos  # noqa: F401

FS = 1000

# ── The script ──────────────────────────────────────────────────────────────


def test_the_load_is_held_ninety_seconds_and_never_more_than_180() -> None:
    g = load_script()
    esfuerzo = [f for f in g.phases if f.kind == EFFORT]
    assert len(esfuerzo) == 1 and esfuerzo[0].seconds == LOAD_DEFAULT_S == 90.0
    assert esfuerzo[0].opens == "HOLD effort start secs=90"
    assert esfuerzo[0].closes == "HOLD effort end"
    assert g.header == "HOLD start mode=load secs=90 v=1"
    assert not g.needs_mvc and g.family == "HOLD" and g.slug == "fatiga_biceps"
    assert _ES[g.title] == "Fatiga: bíceps con carga fija"
    assert load_script(LOAD_MAX_S).total_seconds == g.total_seconds + 90.0
    with pytest.raises(ValueError):
        load_script(LOAD_MAX_S + 1)


def test_a_measured_rest_then_a_countdown_then_the_load() -> None:
    g = load_script()
    assert [f.kind for f in g.phases][:3] == ["rest", READY, EFFORT]
    reposo = g.phases[0]
    assert reposo.check_rest and reposo.opens == "HOLD rest start"
    assert "Breathe normally" in g.phases[2].text


def test_the_effort_may_end_early_and_shows_no_bar() -> None:
    """A fixed load is not a level to reach: the bar would only distract.
    The student ends the effort with the space bar when they cannot go on."""
    fases = load_script().phases
    esfuerzo = next(f for f in fases if f.kind == EFFORT)
    assert esfuerzo.early_stop and not esfuerzo.bar
    assert not any(f.early_stop for f in fases if f is not esfuerzo)
    assert "Space" in esfuerzo.text


def test_the_chooser_offers_the_load_and_no_maximum() -> None:
    from emgteach.gui.tabs.acquisition import GUIDED_SESSIONS

    assert list(GUIDED_SESSIONS)[:3] == ["gradacion", "fatiga", "rapidas"]
    assert GUIDED_SESSIONS["fatiga"]().header == load_script().header


def test_every_word_of_it_is_in_spanish() -> None:
    g = load_script()
    _ES[g.title]
    _ES[g.summary].format(**dict(g.fmt))
    _ES[g.gesture]
    for f in g.phases:
        _ES[f.title].format(**dict(f.fmt))
        if f.text:
            _ES[f.text].format(**dict(f.fmt))


# ── When it fell ────────────────────────────────────────────────────────────


def test_the_time_to_fall_ten_per_cent() -> None:
    t = np.arange(0.5, 30.0, 0.5)
    mdf = 100.0 - (20.0 / 30.0) * t                 # 100 Hz falling to 80 Hz
    assert time_to_decline(t, mdf, 10.0) == pytest.approx(15.0, abs=1.5)
    assert time_to_decline(t, mdf, 30.0) is None
    assert time_to_decline(t, np.full(t.size, 90.0), 10.0) is None


def test_a_single_low_window_does_not_end_the_count() -> None:
    t = np.arange(0.5, 30.0, 0.5)
    mdf = np.full(t.size, 100.0)
    mdf[10] = 50.0                                  # a breath, a shift of the grip
    assert time_to_decline(t, mdf, 10.0) is None


def test_change_in_per_cent() -> None:
    assert change_pct(0.108, 0.085) == pytest.approx(-21.3, abs=0.1)
    assert change_pct(None, 1.0) is None and change_pct(0.0, 1.0) is None


# ── The verdict ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("inicio", "final", "p", "n", "veredicto"), [
    (90.0, 75.0, 1e-8, 170, FATIGUE),        # the bench: -16 %, p ~ 1e-8
    (90.0, 82.0, 1e-8, 170, NO_FATIGUE),     # significant, but under 10 %
    (90.0, 75.0, 0.05, 170, INCONCLUSIVE),   # a fall the scatter could make
    (90.0, 100.0, 1e-6, 170, NO_FATIGUE),    # it rose
    (90.0, 70.0, 1e-8, 8, INCONCLUSIVE),     # too few windows
])
def test_fatigue_is_a_significant_fall_of_at_least_a_tenth(inicio, final, p, n, veredicto) -> None:
    tend = Trend(slope=(final - inicio) / 90.0, start=inicio, end=final, r2=0.3, p=p)
    assert load_verdict(tend, n) == veredicto
    assert load_verdict(None, 170) == INCONCLUSIVE


def test_a_low_r2_does_not_hide_the_fall() -> None:
    """The bench's R² was 0.3: a real fall under a spectrum's own scatter."""
    tend = Trend(slope=-0.15, start=90.0, end=76.5, r2=0.25, p=1e-6)
    assert load_verdict(tend, 170) == FATIGUE


# ── The spectrum of a held load ─────────────────────────────────────────────


def _bandas(n: int, seed: int):
    from scipy.signal import butter, sosfiltfilt

    rng = np.random.default_rng(seed)
    alta = sosfiltfilt(butter(4, (120, 250), "bandpass", fs=FS, output="sos"),
                       rng.normal(0, 1, n))
    baja = sosfiltfilt(butter(4, (40, 90), "bandpass", fs=FS, output="sos"),
                       rng.normal(0, 1, n))
    return alta / np.std(alta), baja / np.std(baja)


def _carga(segundos: float, *, cae: bool, seed: int = 8) -> np.ndarray:
    """A held contraction of constant amplitude whose spectrum slides down
    (or stays): broadband noise, a high band giving way to a low one."""
    n = int(segundos * FS)
    frac = np.linspace(0.0, 1.0, n) if cae else np.zeros(n)
    alta, baja = _bandas(n, seed)
    return 0.2 * (np.sqrt(1 - 0.6 * frac) * alta + np.sqrt(0.6 * frac) * baja)


def test_a_falling_spectrum_at_a_constant_amplitude_is_fatigue() -> None:
    r = load_fatigue(_carga(60.0, cae=True), FS)
    assert r is not None and r.seconds == pytest.approx(60.0)
    assert len(r.t) == 119                           # 1 s windows every 0.5 s
    assert len(r.block_t) == 11                      # their means over 5 s
    assert r.mdf_trend is not None and r.mdf_trend.p < 1e-6
    assert r.mdf_trend.change_pct < -20
    assert r.mnf_trend is not None and r.mnf_trend.change_pct < -15
    assert r.rms_trend is not None and abs(r.rms_trend.change_pct) < 5
    assert r.t_mdf_10 is not None and r.t_mdf_10 < 40
    assert r.verdict == FATIGUE


def test_a_steady_spectrum_is_not_fatigue() -> None:
    r = load_fatigue(_carga(60.0, cae=False), FS)
    assert r is not None and r.verdict in (NO_FATIGUE, INCONCLUSIVE)
    assert r.t_mdf_10 is None
    assert abs(r.mdf_trend.change_pct) < 5


def test_too_short_a_load_is_not_read() -> None:
    assert load_fatigue(np.zeros(2 * FS), FS) is None


# ── Where it is read, in a session ──────────────────────────────────────────


def _marcas(t0: float, segundos: float = 30.0, *, temprano: float | None = None):
    """The marks of a run starting at *t0*; with *temprano*, the student
    ended the effort that many seconds after it began."""
    g = load_script(segundos)
    marcas = [(t0, g.header)]
    for f in g.timed():
        fin = f.end
        if temprano is not None and f.kind == EFFORT:
            fin = f.start + temprano
        if f.opens:
            marcas.append((t0 + f.start, f.opens))
        if f.closes:
            marcas.append((t0 + fin, f.closes + (" early" if temprano is not None else "")))
    marcas.append((t0 + g.total_seconds, end_marker("HOLD")))
    return g, marcas


def test_the_load_is_read_from_two_seconds_after_the_activity_to_its_fall() -> None:
    """The student picks the weight up 0.6 s after the cue and lets it drop
    8 s before the effort's mark ends: the span is the contraction, and its
    first two seconds are left out."""
    g, marcas = _marcas(0.0, 30.0)
    sesion = parse_session_markers(marcas)
    assert sesion is not None
    esfuerzo = sesion.spans_named("effort")[-1]
    n = int((g.total_seconds + 1) * FS)
    env = np.full(n, 0.004)
    a, b = esfuerzo.start_s + 0.6, esfuerzo.end_s - 8.0
    env[int(a * FS): int(b * FS)] = 0.15
    tramo = load_span(sesion, env, FS)
    assert tramo is not None
    assert tramo[0] == pytest.approx(a + LOAD_SKIP_S, abs=0.15)
    assert tramo[1] == pytest.approx(b, abs=0.15)
    assert rest_level(sesion, env, FS) == pytest.approx(0.004)


def test_an_early_end_still_closes_the_effort() -> None:
    _g, marcas = _marcas(0.0, 90.0, temprano=40.0)
    sesion = parse_session_markers(marcas)
    assert sesion is not None and sesion.completed
    assert [t.name for t in sesion.spans] == ["rest", "effort"]
    esfuerzo = sesion.spans_named("effort")[-1]
    assert esfuerzo.end_s - esfuerzo.start_s == pytest.approx(40.0)


def test_no_span_outside_a_load_session() -> None:
    env = np.ones(10 * FS)
    assert load_span(None, env, FS) is None
    otra = parse_session_markers([(0.0, "HOLD start mode=sustained secs=10 v=1"),
                                  (1.0, "HOLD effort start secs=10"),
                                  (9.0, "HOLD effort end"), (10.0, "HOLD end")])
    assert load_span(otra, env, FS) is None
    assert rest_level(otra, env, FS) is None


def test_with_fragments_the_load_is_their_longest_piece_of_it() -> None:
    """Ángel, 26 October 2026: a student who tunes the fragments must not
    lose the view the practical is about. The longest stretch a fragment
    keeps of the load, if it is three windows long; never two glued."""
    carga = (20.0, 60.0)
    assert load_piece(carga, [(0.0, 25.0), (30.0, 50.0), (55.0, 70.0)]) == (30.0, 50.0)
    assert load_piece(carga, [(0.0, 90.0)]) == carga
    assert load_piece(carga, [(0.0, 22.0), (58.0, 70.0)]) is None
    assert load_piece(None, [(0.0, 90.0)]) is None


def test_the_effort_over_the_rest_and_its_warning() -> None:
    """The bench: the good biceps held at 3.7 times its rest, the bad one at
    1.5. The warning names both causes and the ratio."""
    assert effort_ratio(np.full(100, 0.072), 0.019) == pytest.approx(3.79, abs=0.01)
    assert effort_ratio(np.full(100, 0.07), None) is None
    assert effort_ratio([], 0.02) is None
    assert weak_signal_warning(3.7) is None and weak_signal_warning(None) is None
    aviso = weak_signal_warning(1.5)
    assert aviso is not None and "×1.5" in aviso  # noqa: RUF001
    assert "contact" in aviso and "heavier weight" in aviso
    assert _ES[tr("Weak signal: the effort barely exceeds the rest (×{x:.1f}). Check the "  # noqa: RUF001
                  "electrodes' contact or use a heavier weight.")].format(x=1.5) == (
        "Señal débil: el esfuerzo apenas supera el reposo (×1.5). Revise el contacto "  # noqa: RUF001
        "de los electrodos o use un peso mayor.")


def test_the_chart_draws() -> None:
    from matplotlib.figure import Figure

    from emgteach.charts import draw_load_chart

    fig = Figure()
    draw_load_chart(fig, load_fatigue(_carga(60.0, cae=True), FS))
    ax = fig.axes[0]
    assert "R²" in ax.get_title() and "p < 0.001" in ax.get_title()
    assert len(fig.axes) == 2                        # the RMS on its own axis
    fig = Figure()
    draw_load_chart(fig, None)
    assert fig.axes[0].texts


# ── The simulated subject tires ─────────────────────────────────────────────


def test_the_simulated_subject_s_spectrum_falls_while_it_holds() -> None:
    """So that the session can be rehearsed without hardware: a held level
    moves the spectrum down with the seconds held, and its amplitude does
    not fall."""
    from emgteach.devices.bitalino_sim import _SyntheticSubject

    sujeto = _SyntheticSubject(None, seed=3)
    sujeto.instruct(0, 0.4, at_s=0.0)

    def tramo(t0: float) -> np.ndarray:
        # ADC counts: neither the MDF nor the ratio of two SDs needs mV.
        return np.array([float(sujeto.sample(t0 + i / FS, FS, [0])[0])
                         for i in range(int(5 * FS))])

    inicio, final = tramo(1.0), tramo(85.0)
    mdf_0 = compute_psd_mnf_mdf(inicio - inicio.mean(), FS)["mdf"]
    mdf_1 = compute_psd_mnf_mdf(final - final.mean(), FS)["mdf"]
    assert change_pct(mdf_0, mdf_1) < -15
    assert np.std(final) > 0.9 * np.std(inicio)


def test_a_relaxed_simulated_subject_does_not_tire() -> None:
    from emgteach.devices.bitalino_sim import _SyntheticSubject

    sujeto = _SyntheticSubject(None, seed=3)
    sujeto.instruct(0, 0.0, at_s=0.0)
    assert sujeto._tiring(0, 80.0) == 0.0
    sujeto.instruct(0, 0.4, at_s=0.0)
    assert sujeto._tiring(0, 60.0) == pytest.approx(
        sujeto.fatigue_rho * (1 - math.exp(-1)), rel=1e-6)


# ── The filter's share of the level between quick contractions ─────────────


@pytest.mark.parametrize(("periodo", "encendido"), [(3.0, 1.0), (2.0, 1.0), (1.5, 0.75)])
def test_the_envelope_filter_raises_nothing_between_contractions(periodo, encendido) -> None:
    """Quoted in the manuals: at 3, 2 and 1.5 s a period the analysis'
    envelope (5 Hz, zero phase) leaves the gap between two contractions at
    the resting level; what rises there in a recording is the subject's."""
    rng = np.random.default_rng(1)
    n = int(14 * periodo * FS)
    t = np.arange(n) / FS
    activa = ((t % periodo) < encendido) & (t >= 2 * periodo)
    senal = rng.normal(0.0, 1.0, n) * np.where(activa, 1.0, 0.02)
    env = process_offline(senal, FS, f_env=5.0)["emg_envelope"]
    reposo = float(np.median(env[int(0.2 * periodo * FS): int(1.8 * periodo * FS)]))
    picos, huecos = [], []
    for k in range(6, 12):
        a = int(k * periodo * FS)
        b = int((k * periodo + encendido) * FS)
        c = int((k + 1) * periodo * FS)
        picos.append(float(env[a:b].max()))
        huecos.append(float(np.median(env[b:c])))
    assert (np.mean(huecos) - reposo) / np.mean(picos) < 0.005


# ── The analysis worker, on a session written to a file ─────────────────────

REC_S = 10.0


def _edf(path: Path, marcas, senal: np.ndarray) -> str:
    with BufferedEdfWriter(str(path), channels=[
            ChannelInfo("BIC", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(senal)
        w.add_annotation(REC_S - 5.0, prep_start_marker())
        w.add_annotation(REC_S, rec_start_marker())
        for t, m in marcas:
            w.add_annotation(t, m)
    return str(path)


def _carga_edf(path: Path, *, reposo_mv: float = 0.004, fuerza: float = 0.3) -> str:
    """Rest, 40 s of a weight picked up 0.5 s after the cue whose spectrum
    slides down at a constant amplitude, let go 3 s before the mark, and rest."""
    g, marcas = _marcas(REC_S, 40.0)
    esfuerzo = next(f for f in g.timed() if f.kind == EFFORT)
    n = int((REC_S + g.total_seconds + 1) * FS)
    t = np.arange(n) / FS
    a, b = REC_S + esfuerzo.start + 0.5, REC_S + esfuerzo.end - 3.0
    dentro = (t >= a) & (t < b)
    frac = np.clip((t - a) / (b - a), 0, 1)
    alta, baja = _bandas(n, 8)
    activo = fuerza * (np.sqrt(1 - 0.6 * frac) * alta + np.sqrt(0.6 * frac) * baja)
    rng = np.random.default_rng(2)
    senal = np.where(dentro, activo, rng.normal(0, reposo_mv * 1.25, n))
    return _edf(path, marcas, senal)


def _analizar(qapp, edf: str) -> dict:
    from tests.test_gradacion import _analizar as analizar

    return analizar(qapp, edf)


@pytest.mark.gui
def test_the_load_is_analysed_on_the_held_contraction(qapp, tmp_path: Path) -> None:
    r = _analizar(qapp, _carga_edf(tmp_path / "carga.edf"))
    carga = r["load"]
    assert carga is not None
    # From 2 s after the pick-up to the drop: 40 - 0.5 - 2 - 3 s.
    assert carga.seconds == pytest.approx(34.5, abs=0.6)
    assert carga.mdf_trend.change_pct < -15 and carga.mdf_trend.p < 0.01
    assert r["fat_verdict"] == FATIGUE
    # The summary card reads the load's line, not the general fit.
    assert r["fat_r_squared"] == pytest.approx(carga.mdf_trend.r2)
    assert r["fat_pct_decline"] == pytest.approx(-carga.mdf_trend.change_pct)
    assert r["rest_mv"] is not None and r["rest_mv"] < REST_WARN_MV
    assert r["load_ratio"] is not None and r["load_ratio"] > 10
    assert r["grad_steps"] == []


def _analizar_fragmentos(qapp, edf: str, fragmentos) -> dict:
    from emgteach.io import list_edf_emg_channels
    from emgteach.workers import AnalysisWorker

    worker = AnalysisWorker(edf_path=edf, channel_name=list_edf_emg_channels(edf)[0],
                            roi_segments=fragmentos)
    salida: list[dict] = []
    errores: list[str] = []
    worker.result_ready.connect(salida.append)
    worker.error.connect(errores.append)
    worker.start()
    worker.wait(120000)
    qapp.processEvents()
    assert salida, f"the worker gave no result: {errores}"
    return salida[0]


@pytest.mark.gui
def test_chosen_fragments_keep_the_view_on_the_longest_piece(qapp, tmp_path: Path) -> None:
    """The load runs from 20.5 s to 55 s of the file; of the two fragments,
    the second keeps 20 s of it and is the one read, and the view says so."""
    from matplotlib.figure import Figure

    from emgteach.charts import draw_load_chart

    r = _analizar_fragmentos(qapp, _carga_edf(tmp_path / "f.edf"), [(5.0, 25.0), (30.0, 50.0)])
    carga = r["load"]
    assert carga is not None and r["load_note"] is None
    assert r["load_piece"] == pytest.approx((30.0, 50.0))
    assert carga.seconds == pytest.approx(20.0, abs=0.1)
    assert carga.mdf_trend.change_pct < 0
    fig = Figure()
    draw_load_chart(fig, carga, piece=r["load_piece"])
    assert "30.0" in fig.axes[0].get_xlabel()


@pytest.mark.gui
def test_fragments_outside_the_load_leave_a_note(qapp, tmp_path: Path) -> None:
    from matplotlib.figure import Figure

    from emgteach.charts import draw_load_chart
    from emgteach.reports import build_session_report
    from tests.test_informes_y_csv import _pdf_text

    r = _analizar_fragmentos(qapp, _carga_edf(tmp_path / "n.edf"), [(1.0, 15.0)])
    assert r["load"] is None and r["load_note"]
    fig = Figure()
    draw_load_chart(fig, None, note=r["load_note"])
    assert fig.axes[0].texts[0].get_text() == r["load_note"]
    pdf = tmp_path / "n.pdf"
    build_session_report(pdf, r, meta={})
    assert "None of the chosen fragments" in _pdf_text(pdf).replace("\n", " ")


#: Pieces of the load under a second each, as the default detection of
#: «Select fragments» cut it at the final bench (B3): 4.8 s in all, none 3 s.
_TROCITOS = [(22.0 + 3.0 * k, 22.8 + 3.0 * k) for k in range(6)]


@pytest.mark.gui
def test_with_the_load_unread_the_summary_gives_no_verdict(qapp, main_window,
                                                          tmp_path: Path) -> None:
    """The final bench, B3 point 7: the view said none of the fragments kept
    3 s of the load, and the summary card «Fatigue: detected (MDF -27 %)»,
    from the general fit over the pieces glued together. The card, the
    report and the phones now give the view's measure or none."""
    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.guided import fatigue_unmeasured
    from emgteach.reports import build_session_report
    from tests.test_informes_y_csv import _pdf_text
    from tests.test_manejo_en_aula import _Difusion

    r = _analizar_fragmentos(qapp, _carga_edf(tmp_path / "t.edf"), _TROCITOS)
    assert r["load"] is None and r["load_note"]
    motivo = fatigue_unmeasured(r)
    assert motivo == tr("Not measured (the chosen fragments keep less than 3 s "
                        "of the held load)")

    ana = main_window._tab_ana
    ana._actualizar_resumen(r)
    assert ana._lbl_pendiente.text() == "—"
    assert ana._lbl_fatiga.text().replace("\n", " ") == motivo

    pdf = tmp_path / "t.pdf"
    build_session_report(pdf, r, meta={})
    texto = _pdf_text(pdf).replace("\n", " ")
    assert "Not measured" in texto and "Yes —" not in texto

    dif = _Difusion()

    class _Tab:
        _broadcast = dif

        def _broadcast_on(self) -> bool:
            return True

    AnalysisTab._bcast_results(_Tab(), r)       # type: ignore[arg-type]
    assert dif.mensajes[-1]["fatigue"] is None and dif.mensajes[-1]["mdf_slope"] is None


@pytest.mark.gui
def test_the_load_chosen_in_two_pieces_is_read_on_the_longer(qapp, tmp_path: Path) -> None:
    """The final bench, B3: one fragment over the whole load kept the view;
    the load chosen in two pieces is read on the longer, not on both glued,
    and the summary's verdict is that one's."""
    from emgteach.guided import fatigue_unmeasured

    r = _analizar_fragmentos(qapp, _carga_edf(tmp_path / "d.edf"),
                             [(20.5, 33.0), (34.0, 55.0)])
    carga = r["load"]
    assert carga is not None and r["load_piece"] == pytest.approx((34.0, 55.0))
    assert carga.seconds == pytest.approx(21.0, abs=0.1)
    assert fatigue_unmeasured(r) is None
    assert r["fat_verdict"] == carga.verdict


@pytest.mark.gui
def test_a_weak_load_is_warned_in_the_analysis(qapp, tmp_path: Path) -> None:
    """A load whose envelope barely rises over the rest, as the bench's bad
    biceps: the summary line, the report and the phones say it."""
    from emgteach.gui.tabs.analysis import AnalysisTab, _resumen_carga
    from emgteach.reports import build_session_report
    from tests.test_informes_y_csv import _pdf_text
    from tests.test_manejo_en_aula import _Difusion

    r = _analizar(qapp, _carga_edf(tmp_path / "d.edf", reposo_mv=0.02, fuerza=0.035))
    assert r["load"] is not None
    assert r["load_ratio"] is not None and r["load_ratio"] < 2.0
    aviso = weak_signal_warning(r["load_ratio"])
    assert aviso and aviso in _resumen_carga(r["load"], r["rest_mv"], None, r["load_ratio"])
    pdf = tmp_path / "d.pdf"
    build_session_report(pdf, r, meta={})
    assert "Weak signal" in _pdf_text(pdf).replace("\n", " ")

    dif = _Difusion()

    class _Tab:
        _broadcast = dif

        def _broadcast_on(self) -> bool:
            return True

    AnalysisTab._bcast_results(_Tab(), r)       # type: ignore[arg-type]
    assert dif.mensajes[-1]["load"]["ratio"] < 2.0


@pytest.mark.gui
def test_the_report_and_the_phones_carry_the_load(qapp, tmp_path: Path) -> None:
    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.reports import build_session_report
    from tests.test_informes_y_csv import _pdf_text
    from tests.test_manejo_en_aula import _Difusion

    r = _analizar(qapp, _carga_edf(tmp_path / "c.edf", reposo_mv=0.06))
    pdf = tmp_path / "c.pdf"
    build_session_report(pdf, r, meta={})
    texto = _pdf_text(pdf)
    assert tr("Guided session: fatigue with a fixed load") in texto
    assert tr("Slope per minute") in texto
    assert "MDF falls" in texto.replace("\n", " ")
    # The rest was high: the report says so.
    assert r["rest_mv"] > REST_WARN_MV
    assert tr("High rest ({mv:.3f} mV): check the electrodes' contact.").split("(")[0] in texto

    dif = _Difusion()

    class _Tab:
        _broadcast = dif

        def _broadcast_on(self) -> bool:
            return True

    AnalysisTab._bcast_results(_Tab(), r)       # type: ignore[arg-type]
    m = dif.mensajes[-1]
    assert m["load"]["mdf"] < -15 and m["load"]["t10"] is not None
    assert m["load"]["r2"] is not None
    assert m["fatigue"] == -1


@pytest.mark.gui
def test_the_analysis_tab_offers_and_ticks_panels_6_and_7_for_a_load(main_window) -> None:
    ana = main_window._tab_ana

    def marcados() -> set[int]:
        return {pid for pid, c in zip(ana._panel_pids, ana._chk_paneles, strict=True)
                if c.isChecked() and not c.isHidden()}

    antes = marcados()
    assert not {5, 6} & antes
    ana._aplicar_paneles_de_sesion({"load": object()})
    assert {5, 6} <= marcados()
    ana._aplicar_paneles_de_sesion({"load": None})
    assert not {5, 6} & marcados()


# ── Recorded in the acquisition tab, with the simulated board ──────────────


def _grabar(qapp, pestana, monkeypatch, tmp_path: Path, segundos: float,
            esfuerzo: float | None = None):
    from emgteach.gui.tabs import acquisition as acq_mod
    from tests.test_sesion_guiada_en_la_pestana import _choose, _record

    corta = acq_mod.GUIDED_SESSIONS["fatiga"]().with_seconds(segundos)
    if esfuerzo is not None:
        corta = dataclasses.replace(corta, phases=tuple(
            dataclasses.replace(f, seconds=esfuerzo) if f.kind == EFFORT else f
            for f in corta.phases))
    monkeypatch.setitem(acq_mod.GUIDED_SESSIONS, "fatiga", lambda: corta)
    pestana._rellenar_sesiones()
    _choose(pestana, "fatiga")
    path = tmp_path / "fatiga.edf"
    _record(qapp, pestana, path)
    return corta, path


@pytest.mark.gui
def test_the_load_session_recorded_with_the_simulated_board(
    qapp, request, tmp_path: Path, monkeypatch
) -> None:
    """Shortened (0.4 s a phase): the marks in the file, the automatic stop,
    and a tone at every change."""
    from emgteach.io import read_edf_markers
    from tests.test_marcas_manuales import _until

    pestana = request.getfixturevalue("tab")
    oidos = request.getfixturevalue("tonos")
    corta, path = _grabar(qapp, pestana, monkeypatch, tmp_path, 0.4)
    _until(qapp, lambda: not pestana.is_recording(), 0.5 + corta.total_seconds + 10.0,
           "the session to end")
    _until(qapp, lambda: pestana._eventos is None, 5.0, "the event log")
    sesion = parse_session_markers(read_edf_markers(path))
    assert sesion is not None and sesion.completed and sesion.family == "HOLD"
    assert [t.name for t in sesion.spans] == ["rest", "effort"]
    anunciadas = sum(1 for f in corta.phases if f.cue)
    assert oidos == ["phase"] * (1 + anunciadas) + ["end"]


@pytest.mark.gui
def test_the_space_bar_ends_the_effort_and_the_session_goes_on(
    qapp, request, tmp_path: Path, monkeypatch
) -> None:
    """The effort would last 30 s; the student cannot go on after about one.
    The button shows during the effort only; the end mark says «early», and
    the last rest still comes before the recording stops."""
    from emgteach.io import read_edf_markers
    from tests.test_marcas_manuales import _until

    pestana = request.getfixturevalue("tab")
    corta, path = _grabar(qapp, pestana, monkeypatch, tmp_path, 0.4, esfuerzo=30.0)
    assert pestana._btn_no_puedo.isHidden()

    def en_el_esfuerzo() -> bool:
        runner = pestana._session_runner
        return (runner is not None and runner.current_phase is not None
                and runner.current_phase.kind == EFFORT)

    _until(qapp, en_el_esfuerzo, 10.0, "the effort")
    assert not pestana._btn_no_puedo.isHidden()
    fin = time.monotonic() + 1.0                    # held for a second
    _until(qapp, lambda: time.monotonic() > fin, 3.0, "a second of effort")
    pestana._paso_siguiente()                       # what the space bar calls
    _until(qapp, lambda: not pestana.is_recording(), 10.0, "the session to end")
    _until(qapp, lambda: pestana._eventos is None, 5.0, "the event log")
    assert pestana._btn_no_puedo.isHidden()
    marcas = [m for _t, m in read_edf_markers(path)]
    assert "HOLD effort end early" in marcas
    sesion = parse_session_markers(read_edf_markers(path))
    assert sesion is not None and sesion.completed
    esfuerzo = sesion.spans_named("effort")[-1]
    assert esfuerzo.end_s - esfuerzo.start_s == pytest.approx(1.0, abs=0.5)
    # The last rest still comes: at least its length after the early end. Not
    # much more is asked, since the marks are written at the samples the
    # worker has received and on a loaded runner they land late (CI, Windows,
    # Python 3.10, 26 October 2026: 0.7 s for a rest of 0.4).
    reposo = corta.phases[-1].seconds
    assert reposo - 0.15 <= sesion.end_s - esfuerzo.end_s <= reposo + 1.5


@pytest.mark.gui
def test_a_high_rest_is_warned(tab) -> None:  # noqa: F811
    logs: list[str] = []
    tab._log = logs.append
    tab._sesion_reposo = [0.05, 0.048, 0.051]
    tab._revisar_reposo()
    assert any(tr("High rest ({mv:.3f} mV): check the electrodes' contact.")
               .format(mv=0.05) in m for m in logs)
    logs.clear()
    # The bench's two biceps rested at 0.019 and 0.022 mV: neither warns.
    for reposo in (0.019, 0.022):
        tab._sesion_reposo = [reposo] * 3
        tab._revisar_reposo()
    assert not logs
    assert REST_WARN_MV == 0.03


@pytest.mark.gui
@pytest.mark.parametrize(("esfuerzo", "avisa"), [(0.078, False), (0.025, True)])
def test_a_weak_load_is_warned_live(tab, esfuerzo, avisa) -> None:  # noqa: F811
    """From the effort's second 2 to 5, against the rest measured before:
    the bench's good biceps rose to about 4 times its rest, the bad one to
    1.1 (0.022 mV of rest, 0.025 of load). Said once, on the panel and in
    the log, with the two causes the student can tell apart."""
    logs: list[str] = []
    tab._log = logs.append
    tab._sesion_reposo = [0.019]
    tab._revisar_reposo()
    for t in (0.5, 1.5):                            # picking the weight up: not read
        tab._env_inst[0] = 0.5
        tab._revisar_senal(t)
    tab._env_inst[0] = esfuerzo
    for t in (2.2, 3.0, 4.0, 4.8, 5.1, 6.0):
        tab._revisar_senal(t)
    assert tab._senal_revisada
    assert (tab._aviso_senal is not None) == avisa
    assert sum("Weak signal" in m for m in logs) == (1 if avisa else 0)
