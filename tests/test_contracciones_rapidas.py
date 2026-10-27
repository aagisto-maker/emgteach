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


def test_a_train_in_the_fragment_round_it_is_counted_whole() -> None:
    """The final bench (B2): with fragments chosen, the «Train» view vanished.
    The fragment proposed for a train is its activity, which begins some
    tenths after the cue, and a stretch counted only with its cue inside a
    fragment. Measured over the part the fragment keeps, the train is whole."""
    sesion, senal, _m = _tren_sintetico(tarde=(0.4, 0.5), rate=3.0)
    filt = process_offline(senal, FS)["emg_filtered"]
    tramo = sesion.spans_named("train")[0]
    a, b = tramo.start_s + 0.4, tramo.end_s + 0.6
    trozo = filt[round(a * FS):round(b * FS)]
    tren = rapid_train(sesion, [(a, b, 0.0)], fs=FS, emg_filtered=trozo)
    assert tren is not None
    assert tren.n == pytest.approx(31, abs=1)
    assert tren.rate_hz == pytest.approx(3.0, abs=0.15)


def test_the_train_s_window_is_from_its_first_contraction_to_its_last() -> None:
    """What the fragment editor proposes for a train, as one row (the bench
    with exe #139, B2): its detector made one row per contraction."""
    from emgteach.guided import train_span

    sesion, senal, _m = _tren_sintetico(tarde=(0.4, 0.5), rate=3.0)
    env = process_offline(senal, FS)["emg_envelope"]
    tramo = sesion.spans_named("train")[0]
    ventana = train_span(sesion, env, FS)
    assert ventana is not None
    assert ventana[0] == pytest.approx(tramo.start_s + 0.4, abs=0.3)
    assert ventana[1] == pytest.approx(tramo.end_s + 0.5, abs=0.3)
    assert train_span(None, env, FS) is None


def _con_una_larga_al_final(t0: float = 0.0):
    """The bench's late subject (begun 0.4 s after the cue, stopped 0.5 s
    after its end), and two contractions more: one of 0.6 s begun 1.2 s
    after the end mark, inside the margin, that ends past it; and one begun
    2.2 s after the mark, past the margin, which is not the train's."""
    sesion, senal, marcas = _tren_sintetico(t0, tarde=(0.4, 0.5), rate=3.0)
    fin = sesion.spans_named("train")[0].end_s
    rng = np.random.default_rng(7)
    for ini, dur in ((fin + 1.2, 0.6), (fin + 2.2, 0.3)):
        i0, i1 = round(ini * FS), round((ini + dur) * FS)
        senal[i0:i1] = rng.normal(0, 0.3, i1 - i0)
    return sesion, senal, fin, marcas


def test_the_last_contraction_begun_in_the_margin_is_the_trains_whole() -> None:
    """Ángel, 3.10.1 (plan §15): the margin of 1.5 s says where a contraction
    of the train may begin; the proposed row and the measure end where the
    last one that begins inside it ends — cut at the margin, it was left in
    two. One begun past the margin is not the train's."""
    from emgteach.guided import fragments_hull, train_span

    sesion, senal, fin, _m = _con_una_larga_al_final()
    ventana = train_span(sesion, process_offline(senal, FS)["emg_envelope"], FS)
    assert ventana is not None
    assert ventana[1] == pytest.approx(fin + 1.8, abs=0.2)
    assert ventana[1] < fin + 2.2
    filt = process_offline(senal, FS)["emg_filtered"]
    tren = rapid_train(sesion, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt)
    assert tren is not None
    inicio = sesion.spans_named("train")[0].start_s + 0.4
    # 31 contractions at three a second, and the long one; not the one after.
    assert tren.n == 32
    assert tren.seconds == pytest.approx(fin + 1.8 - inicio, abs=0.15)
    assert tren.peak_times[-1] < fin + 2.2 - (inicio - 0.4)      # from the window start
    # With fragments, one round each: the hull keeps the long one to its
    # end and leaves the one after the margin out.
    trozos = ([(inicio + k / 3.0 - 0.05, inicio + k / 3.0 + 0.25) for k in range(31)]
              + [(fin + 1.15, fin + 1.85), (fin + 2.15, fin + 2.55)])
    casco = fragments_hull(sesion, trozos, "train")
    assert casco is not None and casco[1] == pytest.approx(fin + 1.85)
    tren = rapid_train(sesion, [(casco[0], casco[1], casco[0])], fs=FS, emg_filtered=filt)
    assert tren is not None and tren.n == 32


def test_a_subject_who_goes_on_past_the_margin_is_cut_between_contractions() -> None:
    """At four a second the trace does not fall to a fifth of the peak
    between contractions: the train ends at the trough before the first
    contraction begun past the margin, not where the subject stopped."""
    from emgteach.guided import MARGIN_S, train_span

    sesion, senal, _m = _tren_sintetico(tarde=(0.0, 3.0), rate=4.0, suelo=0.3)
    tramo = sesion.spans_named("train")[0]
    hasta = tramo.end_s + MARGIN_S + 0.25 + 0.15        # one period, and the trough
    ventana = train_span(sesion, process_offline(senal, FS)["emg_envelope"], FS)
    assert ventana is not None and tramo.end_s + MARGIN_S - 0.1 < ventana[1] < hasta
    filt = process_offline(senal, FS)["emg_filtered"]
    tren = rapid_train(sesion, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt)
    assert tren is not None
    # 11.5 s at four a second: 46 contractions begun before the margin's end.
    assert tren.n == pytest.approx(46, abs=1)
    assert tren.seconds < hasta - tramo.start_s


def test_fragments_chosen_one_per_contraction_keep_the_train() -> None:
    """The bench with exe #139, B2: «Select fragments» proposed one fragment
    per contraction, no one of them 60 % of the train, and the «Train» view
    vanished. The train is read from the first fragment to the last inside
    it, on the recording — glued, they would keep no rest between them."""
    from emgteach.guided import fragments_hull

    sesion, senal, _m = _tren_sintetico(tarde=(0.4, 0.5), rate=3.0)
    tramo = sesion.spans_named("train")[0]
    t0 = tramo.start_s + 0.4
    una_por_contraccion = [(t0 + k / 3.0 - 0.05, t0 + k / 3.0 + 0.25) for k in range(30)]
    casco = fragments_hull(sesion, una_por_contraccion, "train")
    assert casco is not None
    assert casco[0] == pytest.approx(t0 - 0.05, abs=0.01)
    filt = process_offline(senal, FS)["emg_filtered"]
    tren = rapid_train(sesion, [(casco[0], casco[1], casco[0])], fs=FS, emg_filtered=filt)
    assert tren is not None
    assert tren.n == pytest.approx(30, abs=1)
    assert tren.rate_hz == pytest.approx(3.0, abs=0.15)
    # The rest before the train is the recording's, not a fragment's edge.
    assert tren.rest_mv is not None and tren.rest_mv < 0.02
    # Half the train is not the train.
    assert fragments_hull(sesion, una_por_contraccion[:12], "train") is None


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
def test_with_the_fragment_round_the_train_the_view_stays(qapp, tmp_path: Path) -> None:
    """B2 in the worker: the fragment the editor proposes for the train — its
    activity, from after the cue — and the train is measured in it."""
    from emgteach.io import list_edf_emg_channels
    from emgteach.workers import AnalysisWorker
    from tests.test_fatiga_guiada import _edf

    sesion, senal, marcas = _tren_sintetico(t0=REC_S, tarde=(0.4, 0.5), rate=3.0)
    edf = _edf(tmp_path / "rapidas.edf", marcas, senal)
    tramo = sesion.spans_named("train")[0]
    worker = AnalysisWorker(edf_path=edf, channel_name=list_edf_emg_channels(edf)[0],
                            roi_segments=[(tramo.start_s + 0.4, tramo.end_s + 0.6)])
    salida: list[dict] = []
    worker.result_ready.connect(salida.append)
    worker.start()
    worker.wait(120000)
    qapp.processEvents()
    assert salida
    tren = salida[0]["train"]
    assert tren is not None and tren.n == pytest.approx(31, abs=1)


@pytest.mark.gui
def test_the_analysed_span_reaches_the_end_of_the_last_contraction(qapp, tmp_path: Path) -> None:
    """Without fragments the analysed span ended at the margin too: it now
    runs to the end of the train's last contraction."""
    from tests.test_fatiga_guiada import _edf
    from tests.test_gradacion import _analizar

    _s, senal, fin, marcas = _con_una_larga_al_final(t0=REC_S)
    r = _analizar(qapp, _edf(tmp_path / "rapidas.edf", marcas, senal))
    assert r["roi_end_s"] == pytest.approx(fin + 1.8, abs=0.2)
    assert r["train"] is not None and r["train"].n == 32
    assert r["train_span"][1] == pytest.approx(fin + 1.8, abs=0.2)


@pytest.mark.gui
def test_fragments_one_per_contraction_in_the_worker(qapp, tmp_path: Path) -> None:
    """B2 with exe #139 in the worker: the fragments the detector proposes,
    one per contraction, and the train is measured; half of them, and the
    view says why there is none; and the window the editor proposes."""
    from matplotlib.figure import Figure

    from emgteach.charts import draw_train_chart
    from emgteach.io import list_edf_emg_channels
    from emgteach.workers import AnalysisWorker
    from tests.test_fatiga_guiada import _edf

    sesion, senal, marcas = _tren_sintetico(t0=REC_S, tarde=(0.4, 0.5), rate=3.0)
    edf = _edf(tmp_path / "rapidas.edf", marcas, senal)
    tramo = sesion.spans_named("train")[0]
    t0 = tramo.start_s + 0.4
    trocitos = [(t0 + k / 3.0 - 0.05, t0 + k / 3.0 + 0.25) for k in range(30)]

    def analizar(fragmentos):
        worker = AnalysisWorker(edf_path=edf, channel_name=list_edf_emg_channels(edf)[0],
                                roi_segments=fragmentos)
        salida: list[dict] = []
        worker.result_ready.connect(salida.append)
        worker.start()
        worker.wait(120000)
        qapp.processEvents()
        assert salida
        return salida[0]

    r = analizar(trocitos)
    assert r["train"] is not None and r["train"].n == pytest.approx(30, abs=1)
    assert r["train_piece"] is not None and r["train_note"] is None
    assert r["train_span"][0] == pytest.approx(t0, abs=0.3)

    r = analizar(trocitos[:12])
    assert r["train"] is None and r["train_note"]
    fig = Figure()
    draw_train_chart(fig, None, note=r["train_note"])
    assert fig.axes[0].texts[0].get_text() == r["train_note"]


@pytest.mark.gui
def test_the_editor_proposes_the_train_as_one_row(qapp) -> None:
    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

    _s, senal, _m = _tren_sintetico(tarde=(0.4, 0.5), rate=3.0)
    filtros = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}
    dlg = FragmentSelectionDialog(senal, FS, filtros, naming=False,
                                  session_window=(13.1, 24.3))
    assert dlg.selected_segments() == [pytest.approx((13.1, 24.3))]
    dlg.deleteLater()


@pytest.mark.gui
def test_a_pressed_button_has_room_for_its_bold_text(qapp) -> None:
    """The bench with exe #139: «Descartar» lost its first letter when
    pressed, the text turning bold in a button sized for the regular."""
    from PySide6.QtGui import QFontMetrics

    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

    _s, senal, _m = _tren_sintetico()
    filtros = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}
    dlg = FragmentSelectionDialog(senal, FS, filtros, naming=False)
    for boton in (dlg._btn_eliminar, dlg._btn_mantener):
        negrita = boton.font()
        negrita.setBold(True)
        assert boton.minimumWidth() >= QFontMetrics(negrita).horizontalAdvance(boton.text()) + 24
    dlg.deleteLater()


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
    # ten, three of them after the end mark, on an idle machine. The marks
    # are written at the samples the worker has received and the subject
    # changes at the ones the board has made, so on a loaded runner the
    # whole train lands later and the 1.5 s margin cuts its tail (CI,
    # Windows, Python 3.10, 26 October 2026: 7 counted). What this test is
    # for holds whatever the delay: contractions after the end mark are
    # counted. The exact count is test_a_late_subject_s_last_contractions_are_counted's.
    assert tren.n >= 5, tren.n
    assert tren.peak_times[-1] > tramo.duration_s
