"""Quick repeated contractions: the peaks, the floor, and the measure's share.

Ángel, 25 October 2026: after the intermittent contractions, a train of quick
contractions to see the floor rise and the peaks grow — prudently: it is not
the treppe, and the peaks are EMG, not force. At four or five contractions a
second the envelope's 5 Hz filter alone keeps the floor high, so the train is
measured on a 50 ms moving RMS, and what that measure leaves by itself at the
rate achieved is worked out and given apart.
"""

from __future__ import annotations

import dataclasses
import itertools
from pathlib import Path

import numpy as np
import pytest

from emgteach.dsp import process_offline
from emgteach.guided import (
    TRAIN_RMS_MS,
    _moving_rms,
    _peaks_and_floors,
    processing_floor_pct,
    rapid_train,
)
from emgteach.i18n import _ES, tr
from emgteach.sessions import (
    EFFORT,
    FAMILIES,
    end_marker,
    parse_session_markers,
    rapid_script,
)

# The acquisition tab on the simulated board, from the session tests.
from tests.test_sesion_guiada_en_la_pestana import tab, tonos  # noqa: F401

FS = 1000

# ── The script ──────────────────────────────────────────────────────────────


def test_ten_seconds_as_fast_as_possible_with_the_fist() -> None:
    g = rapid_script()
    tren = [f for f in g.phases if f.kind == EFFORT]
    assert len(tren) == 1 and tren[0].seconds == 10.0
    assert tren[0].opens == "FAST train start secs=10" and tren[0].closes == "FAST train end"
    assert g.header == "FAST start secs=10 v=1" and g.family == "FAST" in FAMILIES
    assert not g.needs_mvc and g.gesture
    # The simulated subject is asked for four a second, not for a hold.
    assert tren[0].repeat_s == 0.25


def test_it_is_offered_after_the_fatigue() -> None:
    from emgteach.gui.tabs.acquisition import GUIDED_SESSIONS

    assert list(GUIDED_SESSIONS)[-2:] == ["fatiga", "rapidas"]


def test_every_word_is_in_spanish() -> None:
    g = rapid_script()
    _ES[g.title]
    _ES[g.summary].format(**dict(g.fmt))
    for f in g.phases:
        _ES[f.title].format(**dict(f.fmt))
        if f.text:
            _ES[f.text].format(**dict(f.fmt))


def test_the_simulated_subject_makes_a_train_when_asked_quickly() -> None:
    from emgteach.devices.bitalino_sim import _SyntheticSubject

    s = _SyntheticSubject(None, 0)
    s.instruct(0, 1.0, repeat_s=0.25)
    niveles = [s.activation(t)[0] for t in np.arange(10.0, 11.0, 0.01)]
    # On and off four times in the second, not held.
    assert max(niveles) > 0.9 and min(niveles) == 0.0
    cruces = sum(1 for a, b in itertools.pairwise(niveles) if a < 0.5 <= b)
    assert cruces == 4


# ── The measure's own floor ─────────────────────────────────────────────────


def _floor_pct(sig, rate) -> float:
    i0 = int(2 / rate * FS)
    _p, alturas, suelos = _peaks_and_floors(sig[i0:], FS)
    return 100.0 * float(np.mean(suelos)) / float(np.mean(alturas))


@pytest.mark.parametrize("rate", [4.0, 5.0])
def test_at_four_or_five_a_second_the_envelope_would_keep_the_floor_high(rate) -> None:
    """Why the train is measured on a 50 ms RMS and not on the envelope."""
    rng = np.random.default_rng(0)
    n = 12 * FS
    t = np.arange(n) / FS
    activa = (t % (1 / rate)) < 0.5 / rate
    x = rng.normal(0, 1, n) * np.where(activa, 1.0, 0.0)
    r = process_offline(x, FS, f_env=5.0)
    envolvente = _floor_pct(r["emg_envelope"], rate)
    rms = _floor_pct(_moving_rms(r["emg_filtered"], FS, TRAIN_RMS_MS), rate)
    assert envolvente > 15.0 and rms < envolvente
    assert processing_floor_pct(rate) == pytest.approx(rms, abs=4.0)


def test_the_measures_floor_grows_with_the_rate() -> None:
    suelos = [processing_floor_pct(r) for r in (2.0, 4.0, 6.0)]
    assert suelos == sorted(suelos) and suelos[-1] < 30.0
    assert processing_floor_pct(0.0) == 0.0


# ── The train, measured ─────────────────────────────────────────────────────


def _tren_sintetico(t0: float = 0.0, *, rate: float = 4.0, crecen: float = 0.10,
                    suelo: float = 0.25, tarde: tuple[float, float] = (0.0, 0.0)):
    """Rest, then 10 s of contractions at *rate* whose amplitude grows by
    *crecen* and whose relaxation leaves *suelo* of it between them. With
    *tarde*, the subject begins and stops that many seconds after the cues."""
    g = rapid_script()
    marcas = [(t0, g.header)]
    for f in g.timed():
        if f.opens:
            marcas.append((t0 + f.start, f.opens))
        if f.closes:
            marcas.append((t0 + f.end, f.closes))
    marcas.append((t0 + g.total_seconds, end_marker("FAST")))
    sesion = parse_session_markers(marcas)
    assert sesion is not None
    tramo = sesion.spans_named("train")[0]
    n = int((t0 + g.total_seconds + 1) * FS)
    t = np.arange(n) / FS
    ini, fin = tramo.start_s + tarde[0], tramo.end_s + tarde[1]
    dentro = (t >= ini) & (t < fin)
    frac = np.clip((t - ini) / (fin - ini), 0, 1)
    activa = ((t - ini) % (1 / rate)) < 0.5 / rate
    amp = 0.3 * (1 + crecen * frac)
    nivel = np.where(dentro, np.where(activa, amp, suelo * amp), 0.004)
    rng = np.random.default_rng(4)
    senal = rng.normal(0, 1, n) * nivel
    return sesion, senal, marcas


def test_the_train_counts_its_contractions_and_their_rate() -> None:
    sesion, senal, _m = _tren_sintetico()
    filt = process_offline(senal, FS)["emg_filtered"]
    tren = rapid_train(sesion, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt)
    assert tren is not None
    assert tren.n == pytest.approx(40, abs=2)
    assert tren.rate_hz == pytest.approx(4.0, abs=0.2)
    assert tren.peak_change_pct == pytest.approx(10 * 2 / 3, abs=4.0)   # thirds
    # A relaxation that leaves a quarter: well above what the measure leaves.
    assert tren.floor_end_pct is not None and tren.floor_end_pct > tren.processing_floor_pct + 10
    assert tren.rest_mv is not None and tren.rest_mv < 0.02


def test_a_late_subject_s_last_contractions_are_counted() -> None:
    """Ángel's bench, 26 October 2026: begun 0.4 s after the cue and stopped
    0.5 s after the end, the train had 30 contractions and the view counted
    28. The train is the activity inside its marks run on past their end."""
    sesion, senal, _m = _tren_sintetico(tarde=(0.4, 0.5), rate=3.0)
    filt = process_offline(senal, FS)["emg_filtered"]
    tren = rapid_train(sesion, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt)
    assert tren is not None
    # 10.1 s at three a second: 31 contractions, the last after the end mark.
    assert tren.n == 31
    fin = sesion.spans_named("train")[0].end_s - sesion.spans_named("train")[0].start_s
    assert tren.peak_times[-1] > fin
    assert tren.seconds == pytest.approx(10.1, abs=0.3)


def test_a_full_relaxation_leaves_only_the_measures_floor() -> None:
    sesion, senal, _m = _tren_sintetico(suelo=0.0, crecen=0.0)
    filt = process_offline(senal, FS)["emg_filtered"]
    tren = rapid_train(sesion, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt)
    assert tren is not None
    assert tren.floor_end_pct == pytest.approx(tren.processing_floor_pct, abs=5.0)
    assert abs(tren.peak_change_pct or 0.0) < 5.0


def test_only_a_train_is_a_train() -> None:
    _s, senal, _m = _tren_sintetico()
    hold = parse_session_markers([(0.0, "HOLD start mode=sustained v=1"), (1.0, "HOLD end")])
    assert rapid_train(hold, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=senal) is None
    assert rapid_train(None, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=senal) is None


def test_the_mdf_trend_says_nothing_over_a_train() -> None:
    from emgteach.guided import mdf_trend_applies

    sesion, _s, _m = _tren_sintetico()
    assert not mdf_trend_applies(sesion)
    assert mdf_trend_applies(None)
    assert mdf_trend_applies(parse_session_markers(
        [(0.0, "HOLD start mode=sustained v=1"), (1.0, "HOLD end")]))


def test_the_chart_draws() -> None:
    from matplotlib.figure import Figure

    from emgteach.charts import draw_train_chart

    sesion, senal, _m = _tren_sintetico()
    tren = rapid_train(sesion, [(0.0, 1e9, 0.0)], fs=FS,
                       emg_filtered=process_offline(senal, FS)["emg_filtered"])
    fig = Figure()
    draw_train_chart(fig, tren)
    assert "/s" in fig.axes[0].get_title()
    fig = Figure()
    draw_train_chart(fig, None)
    assert fig.axes[0].texts


# ── The analysis worker, the report and the phones ──────────────────────────

REC_S = 10.0


@pytest.mark.gui
def test_a_recorded_train_is_analysed_reported_and_sent(qapp, tmp_path: Path) -> None:
    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.reports import build_session_report
    from tests.test_fatiga_guiada import _edf
    from tests.test_gradacion import _analizar
    from tests.test_informes_y_csv import _pdf_text
    from tests.test_manejo_en_aula import _Difusion

    _s, senal, marcas = _tren_sintetico(t0=REC_S)
    r = _analizar(qapp, _edf(tmp_path / "rapidas.edf", marcas, senal))
    tren = r["train"]
    assert tren is not None and tren.n == pytest.approx(40, abs=3)
    # The analysed span is the train, the rest just before it and the 1.5 s
    # after its end mark where a late subject is still contracting.
    assert r["roi_end_s"] - r["roi_start_s"] == pytest.approx(14.5, abs=0.1)

    pdf = tmp_path / "rapidas.pdf"
    build_session_report(pdf, r, meta={})
    texto = _pdf_text(pdf)
    assert tr("Guided session: quick repeated contractions") in texto
    # Ten seconds of brief contractions: no fatigue verdict, no MDF slope
    # (Ángel's bench, 26 October 2026).
    assert tr("Fatigue evidence") not in texto

    dif = _Difusion()

    class _Tab:
        _broadcast = dif

        def _broadcast_on(self) -> bool:
            return True

    AnalysisTab._bcast_results(_Tab(), r)       # type: ignore[arg-type]
    m = dif.mensajes[-1]["train"]
    assert m["n"] == tren.n and m["proc"] is not None
    assert dif.mensajes[-1]["mdf_slope"] is None and dif.mensajes[-1]["fatigue"] is None


@pytest.mark.gui
def test_a_train_recorded_with_the_simulated_board(qapp, request, tmp_path: Path,
                                                   monkeypatch) -> None:
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.io import read_edf_markers
    from tests.test_gradacion import _analizar
    from tests.test_marcas_manuales import _until
    from tests.test_sesion_guiada_en_la_pestana import _choose, _record

    pestana = request.getfixturevalue("tab")
    corta = dataclasses.replace(rapid_script(2.0).with_seconds(0.6))
    # The train itself two seconds: eight contractions at the subject's four
    # a second.
    corta = dataclasses.replace(corta, phases=tuple(
        dataclasses.replace(f, seconds=2.0) if f.kind == EFFORT else f for f in corta.phases))
    monkeypatch.setitem(acq_mod.GUIDED_SESSIONS, "rapidas", lambda: corta)
    pestana._rellenar_sesiones()
    _choose(pestana, "rapidas")
    path = tmp_path / "rapidas_sim.edf"
    _record(qapp, pestana, path)
    _until(qapp, lambda: not pestana.is_recording(), 0.5 + corta.total_seconds + 10.0,
           "the session to end")
    _until(qapp, lambda: pestana._eventos is None, 5.0, "the event log")
    sesion = parse_session_markers(read_edf_markers(path))
    assert sesion is not None and sesion.completed and sesion.family == "FAST"
    r = _analizar(qapp, str(path))
    assert r["train"] is not None and r["train"].n >= 5


@pytest.mark.gui
def test_a_late_subject_on_the_simulated_board_keeps_its_last_contractions(
        qapp, request, tmp_path: Path, monkeypatch) -> None:
    """The same, with a subject who begins 0.4 s late and stops 0.8 s late:
    the contractions made after the end mark are the train's."""
    from emgteach.devices.bitalino_sim import _SyntheticSubject
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.io import read_edf_markers
    from tests.test_gradacion import _analizar
    from tests.test_marcas_manuales import _until
    from tests.test_sesion_guiada_en_la_pestana import _choose, _record

    monkeypatch.setattr(_SyntheticSubject, "reaction_s", 0.4)
    monkeypatch.setattr(_SyntheticSubject, "release_s", 0.8)
    pestana = request.getfixturevalue("tab")
    corta = dataclasses.replace(rapid_script(2.0).with_seconds(2.0))
    monkeypatch.setitem(acq_mod.GUIDED_SESSIONS, "rapidas", lambda: corta)
    pestana._rellenar_sesiones()
    _choose(pestana, "rapidas")
    path = tmp_path / "rapidas_tarde.edf"
    _record(qapp, pestana, path)
    _until(qapp, lambda: not pestana.is_recording(), 0.5 + corta.total_seconds + 10.0,
           "the session to end")
    _until(qapp, lambda: pestana._eventos is None, 5.0, "the event log")
    sesion = parse_session_markers(read_edf_markers(path))
    assert sesion is not None
    tramo = sesion.spans_named("train")[0]
    tren = _analizar(qapp, str(path))["train"]
    assert tren is not None
    # Four a second from 0.4 s after the cue to 0.8 s after the end: about
    # ten, three of them after the end mark.
    assert tren.n >= 9, tren.n
    assert tren.peak_times[-1] > tramo.duration_s
