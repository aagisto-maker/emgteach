"""The fatigue sessions: a maximum held for 30 s, and ten of 5 s with 1 s between.

From the scripts to the numbers. The sustained maximum is analysed on the
effort alone — its windows, its MDF line, its verdict — with the MDF and the
RMS of its first and last five seconds and the seconds until each fell 10 and
20 %. The intermittent one is measured contraction by contraction, by the RMS
after the first second and not by the peak (the peak is the start of each
contraction and does not fall: Ángel's pilots of 24 October 2026). And the
envelope filter's own share of the level between quick contractions, which
the manuals' note on successive contractions quotes.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from emgteach.dsp import process_offline
from emgteach.guided import (
    RepResult,
    change_pct,
    hold_result,
    intermittent_reps,
    reps_trend_pct,
    time_to_decline,
)
from emgteach.i18n import _ES, tr
from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.phases import prep_start_marker, rec_start_marker
from emgteach.sessions import (
    EFFORT,
    HOLD_MAX_S,
    READY,
    end_marker,
    hold_script,
    intermittent_script,
    parse_session_markers,
)

# The acquisition tab on the simulated board, from the session tests.
from tests.test_sesion_guiada_en_la_pestana import tab, tonos  # noqa: F401

FS = 1000

# ── The scripts ─────────────────────────────────────────────────────────────


def test_the_sustained_contraction_is_ten_seconds_and_never_more_than_45() -> None:
    """Ángel, 25 Oct 2026, after trying 30 s: with a maximal effort the fall
    is seen in ten."""
    g = hold_script()
    esfuerzo = [f for f in g.phases if f.kind == EFFORT]
    assert len(esfuerzo) == 1 and esfuerzo[0].seconds == 10.0 and esfuerzo[0].level == 1.0
    assert esfuerzo[0].opens == "HOLD effort start secs=10"
    assert esfuerzo[0].closes == "HOLD effort end"
    assert g.header == "HOLD start mode=sustained secs=10 v=1"
    assert not g.needs_mvc and g.family == "HOLD"
    assert _ES[g.title] == "Fatiga por contracción mantenida"
    assert _ES[intermittent_script().title] == "Fatiga por contracciones intermitentes"
    assert hold_script(45.0).total_seconds == g.total_seconds + 35.0
    assert HOLD_MAX_S == 45.0
    with pytest.raises(ValueError):
        hold_script(46.0)


def test_it_is_preceded_by_a_countdown_and_says_to_breathe() -> None:
    g = hold_script()
    assert [f.kind for f in g.phases][:3] == ["rest", READY, EFFORT]
    assert "Breathe" in next(f for f in g.phases if f.kind == EFFORT).text


def test_the_intermittent_maximum_is_six_of_five_seconds_one_apart() -> None:
    """Ten at first; six after Ángel tried it (25 Oct 2026)."""
    g = intermittent_script()
    esfuerzos = [f for f in g.phases if f.kind == EFFORT]
    pausas = [f for f in g.phases if f.key.startswith("off_")]
    assert len(esfuerzos) == 6 and all(f.seconds == 5.0 for f in esfuerzos)
    assert len(pausas) == 5 and all(f.seconds == 1.0 and f.kind == READY for f in pausas)
    assert [f.opens for f in esfuerzos][:2] == ["HOLD rep start n=1", "HOLD rep start n=2"]
    assert g.header == "HOLD start mode=intermittent reps=6 on=5 off=1 v=1"
    assert g.total_seconds == 5 + 3 + 30 + 5 + 10


def test_a_tone_at_the_start_and_at_the_end_of_every_contraction() -> None:
    """A tone with every phase change, and between two contractions the
    phase changes twice: the end of one, the start of the next."""
    fases = intermittent_script().phases
    for i, f in enumerate(fases):
        if f.kind == EFFORT:
            assert f.cue and fases[i + 1].cue


def test_both_are_offered_in_the_chooser() -> None:
    from emgteach.gui.tabs.acquisition import GUIDED_SESSIONS

    assert list(GUIDED_SESSIONS) == ["gradacion", "fatiga", "fatiga_intermitente"]


def test_every_word_of_both_is_in_spanish() -> None:
    for g in (hold_script(), intermittent_script()):
        _ES[g.title]
        _ES[g.summary].format(**dict(g.fmt))
        for f in g.phases:
            _ES[f.title].format(**dict(f.fmt))
            if f.text:
                _ES[f.text].format(**dict(f.fmt))


# ── When it fell ────────────────────────────────────────────────────────────


def test_the_time_to_fall_ten_and_twenty_per_cent() -> None:
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


def test_the_sustained_maximum_from_its_windows() -> None:
    t0 = np.arange(0.0, 29.5, 0.5)                 # window starts, 1 s windows
    centro = t0 + 0.5
    mdf = 100.0 - (20.0 / 30.0) * centro
    rms = 0.5 - (0.15 / 30.0) * centro
    h = hold_result(t0, mdf, rms, np.ones(t0.size, bool))
    assert h is not None
    assert h.seconds == pytest.approx(30.0, abs=0.6)
    assert h.mdf_start_hz == pytest.approx(98.0, abs=1.0)
    assert h.mdf_end_hz == pytest.approx(82.0, abs=1.0)
    assert h.mdf_change_pct == pytest.approx(-16.0, abs=2.0)
    assert h.t_mdf_10 == pytest.approx(14.5, abs=1.5)
    assert h.t_mdf_20 is None
    assert h.rms_change_pct == pytest.approx(-25.0, abs=3.0)
    assert h.t_rms_10 is not None and h.t_rms_20 is not None


def test_change_in_per_cent() -> None:
    assert change_pct(0.108, 0.085) == pytest.approx(-21.3, abs=0.1)
    assert change_pct(None, 1.0) is None and change_pct(0.0, 1.0) is None


# ── The intermittent maximum, contraction by contraction ────────────────────


def _intermitente(t0: float = 0.0, *, caida: float = 0.21):
    """The marks of a run starting at *t0*, and a signal whose contractions
    open on a peak that does not fall, then hold a level that does."""
    g = intermittent_script()
    marcas = [(t0, g.header)]
    for f in g.timed():
        if f.opens:
            marcas.append((t0 + f.start, f.opens))
        if f.closes:
            marcas.append((t0 + f.end, f.closes))
    marcas.append((t0 + g.total_seconds, end_marker("HOLD")))
    sesion = parse_session_markers(marcas)
    assert sesion is not None
    n = int((t0 + g.total_seconds + 2) * FS)
    amp = np.full(n, 0.005)
    tramos = sesion.spans_named("rep")
    for k, tramo in enumerate(tramos):
        a, b = int(tramo.start_s * FS), int(tramo.end_s * FS)
        amp[a:b] = 0.108 * (1.0 - caida * k / (len(tramos) - 1))
        amp[a: a + int(0.3 * FS)] = 0.25             # the peak of the start
    rng = np.random.default_rng(5)
    return sesion, rng.normal(0.0, 1.0, n) * amp, marcas


def test_each_contraction_is_its_rms_after_the_first_second() -> None:
    sesion, filt, _m = _intermitente()
    reps = intermittent_reps(sesion, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt)
    assert [r.n for r in reps] == list(range(1, 7))
    assert reps[0].rms_mv == pytest.approx(0.108, rel=0.05)
    assert reps[-1].rms_mv == pytest.approx(0.085, rel=0.05)
    assert change_pct(reps[0].rms_mv, reps[-1].rms_mv) == pytest.approx(-21, abs=4)
    assert all(r.mdf_hz is not None for r in reps)
    assert reps_trend_pct(reps) == pytest.approx(-21 / 5, abs=1.2)


def test_only_an_intermittent_session_has_contractions() -> None:
    _sesion, filt, _m = _intermitente()
    sostenida = parse_session_markers([(0.0, hold_script().header), (1.0, "HOLD end")])
    assert intermittent_reps(sostenida, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt) == []
    assert intermittent_reps(None, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt) == []


def test_the_bars_draw() -> None:
    from matplotlib.figure import Figure

    from emgteach.charts import draw_reps_chart

    reps = [RepResult(k, k * 6.0, k * 6.0 + 5.0, 0.1 - 0.002 * k, 90.0 - k) for k in range(1, 11)]
    fig = Figure()
    draw_reps_chart(fig, reps)
    assert len(fig.axes[0].patches) == 10
    assert "-18 %" in fig.axes[0].get_title()
    fig = Figure()
    draw_reps_chart(fig, [])
    assert fig.axes[0].texts


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


# ── The analysis worker, on sessions written to a file ──────────────────────

REC_S = 10.0


def _edf(path: Path, marcas, senal: np.ndarray) -> str:
    with BufferedEdfWriter(str(path), channels=[
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(senal)
        w.add_annotation(REC_S - 5.0, prep_start_marker())
        w.add_annotation(REC_S, rec_start_marker())
        for t, m in marcas:
            w.add_annotation(t, m)
    return str(path)


def _sostenida_edf(path: Path) -> str:
    """Rest, a 30 s maximum (the session allows up to 45) whose spectrum slides
    down and whose amplitude
    falls a third, and rest. Broadband noise, a high band giving way to a low
    one: a pure tone sweeping down crosses the mains notch's harmonics and
    its RMS dips there."""
    g = hold_script(30.0)
    marcas = [(REC_S, g.header)]
    for f in g.timed():
        if f.opens:
            marcas.append((REC_S + f.start, f.opens))
        if f.closes:
            marcas.append((REC_S + f.end, f.closes))
    marcas.append((REC_S + g.total_seconds, end_marker("HOLD")))
    esfuerzo = next(f for f in g.timed() if f.kind == EFFORT)
    n = int((REC_S + g.total_seconds + 1) * FS)
    t = np.arange(n) / FS
    a, b = REC_S + esfuerzo.start, REC_S + esfuerzo.end
    dentro = (t >= a) & (t < b)
    frac = np.clip((t - a) / (b - a), 0, 1)
    from scipy.signal import butter, sosfiltfilt

    rng = np.random.default_rng(8)
    alta = sosfiltfilt(butter(4, (150, 300), "bandpass", fs=FS, output="sos"),
                       rng.normal(0, 1, n))
    baja = sosfiltfilt(butter(4, (40, 90), "bandpass", fs=FS, output="sos"),
                       rng.normal(0, 1, n))
    alta /= np.std(alta)
    baja /= np.std(baja)
    amp = np.where(dentro, 0.6 - 0.2 * frac, 0.01)
    senal = amp * (np.sqrt(1 - frac) * alta + np.sqrt(frac) * baja)
    return _edf(path, marcas, senal)


def _analizar(qapp, edf: str) -> dict:
    from tests.test_gradacion import _analizar as analizar

    return analizar(qapp, edf)


@pytest.mark.gui
def test_the_sustained_maximum_is_analysed_on_the_effort_alone(qapp, tmp_path: Path) -> None:
    r = _analizar(qapp, _sostenida_edf(tmp_path / "sost.edf"))
    assert r["roi_end_s"] - r["roi_start_s"] == pytest.approx(30.0, abs=0.05)
    h = r["hold"]
    assert h is not None and h.seconds == pytest.approx(30.0, abs=1.0)
    assert h.mdf_change_pct is not None and h.mdf_change_pct < -20
    assert h.t_mdf_10 is not None and h.t_mdf_10 < 20
    assert h.rms_change_pct is not None and h.rms_change_pct < -15
    assert r["fat_verdict"] == "fatigue"
    assert len(r["contractions"]) == 1 and r["reps"] == [] and r["grad_steps"] == []


@pytest.mark.gui
def test_the_intermittent_maximum_is_analysed_by_contraction(qapp, tmp_path: Path) -> None:
    _s, filt, marcas = _intermitente(t0=REC_S)
    r = _analizar(qapp, _edf(tmp_path / "inter.edf", marcas, filt))
    assert len(r["reps"]) == 6 and len(r["contractions"]) == 6
    assert change_pct(r["reps"][0].rms_mv, r["reps"][-1].rms_mv) == pytest.approx(-21, abs=6)
    assert r["hold"] is None


@pytest.mark.gui
def test_the_report_and_the_phones_carry_the_fatigue(qapp, tmp_path: Path) -> None:
    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.reports import build_session_report
    from tests.test_informes_y_csv import _pdf_text
    from tests.test_manejo_en_aula import _Difusion

    for edf, titulo in (
        (_sostenida_edf(tmp_path / "s.edf"), "Guided session: fatigue by sustained contraction"),
        (_edf(tmp_path / "i.edf", _intermitente(t0=REC_S)[2], _intermitente(t0=REC_S)[1]),
         "Guided session: fatigue by intermittent contractions"),
    ):
        r = _analizar(qapp, edf)
        pdf = tmp_path / (Path(edf).stem + ".pdf")
        build_session_report(pdf, r, meta={})
        assert tr(titulo) in _pdf_text(pdf)

        dif = _Difusion()

        class _Tab:
            _broadcast = dif

            def _broadcast_on(self) -> bool:
                return True

        AnalysisTab._bcast_results(_Tab(), r)       # type: ignore[arg-type]
        m = dif.mensajes[-1]
        if r["hold"] is not None:
            assert m["hold"]["mdf"] < -20 and m["hold"]["t10"] is not None
        else:
            assert len(m["reps"]) == 6


@pytest.mark.gui
def test_the_analysis_tab_offers_and_ticks_panels_6_and_7_for_a_sustained_maximum(
    main_window
) -> None:
    ana = main_window._tab_ana

    def marcados() -> set[int]:
        return {pid for pid, c in zip(ana._panel_pids, ana._chk_paneles, strict=True)
                if c.isChecked() and not c.isHidden()}

    antes = marcados()
    assert not {5, 6} & antes
    ana._aplicar_paneles_de_sesion({"hold": object()})
    assert {5, 6} <= marcados()
    ana._aplicar_paneles_de_sesion({"hold": None})
    assert not {5, 6} & marcados()


# ── Recorded in the acquisition tab, with the simulated board ──────────────


@pytest.mark.gui
@pytest.mark.parametrize("clave", ["fatiga", "fatiga_intermitente"])
def test_a_fatigue_session_recorded_with_the_simulated_board(
    qapp, request, tmp_path: Path, monkeypatch, clave
) -> None:
    """Shortened (0.4 s a phase): the marks in the file, the automatic stop,
    and a tone at every change — at the start and the end of every
    contraction in the intermittent one."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.io import read_edf_markers
    from tests.test_marcas_manuales import _until
    from tests.test_sesion_guiada_en_la_pestana import _choose, _record

    pestana = request.getfixturevalue("tab")
    oidos = request.getfixturevalue("tonos")
    corta = acq_mod.GUIDED_SESSIONS[clave]().with_seconds(0.4)
    monkeypatch.setitem(acq_mod.GUIDED_SESSIONS, clave, lambda: corta)
    pestana._rellenar_sesiones()
    _choose(pestana, clave)
    path = tmp_path / f"{clave}.edf"
    _record(qapp, pestana, path)
    _until(qapp, lambda: not pestana.is_recording(), 0.5 + corta.total_seconds + 10.0,
           "the session to end")
    _until(qapp, lambda: pestana._eventos is None, 5.0, "the event log")
    sesion = parse_session_markers(read_edf_markers(path))
    assert sesion is not None and sesion.completed and sesion.family == "HOLD"
    if clave == "fatiga":
        assert [t.name for t in sesion.spans] == ["effort"]
    else:
        assert [t.number("n") for t in sesion.spans] == list(range(1, 7))
    anunciadas = sum(1 for f in corta.phases if f.cue)
    # The countdown before the recording phase, every announced phase, the end.
    assert oidos == ["phase"] * (1 + anunciadas) + ["end"]


def test_the_shortened_script_keeps_its_marks() -> None:
    corta = dataclasses.replace(intermittent_script().with_seconds(0.4))
    assert [f.opens for f in corta.phases] == [f.opens for f in intermittent_script().phases]
