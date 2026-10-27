"""The bench with exe #143 (Ángel, 27 October 2026): where a row starts, and
a contraction with two humps.

1. A row of the one-muscle practical starts the same 0.5 s before its
   contraction leaves rest — the baseline plus 5 % of its peak, the rule its
   end is found by. On a lower line, steps 1, 4 and 5 began half a second
   before their flank and 2 and 3 on it; the train's row, from a fifth of the
   peak, cut the beginning of its first contraction. The rows of the train
   and of the held load too.
2. Two peaks of a train are two contractions only if the trace between them
   falls below 40 % of the lower one or they are 0.25 s apart: three
   contractions with two humps were counted twice (20 for some 17) and the
   floor between the humps, at half the peak, made the floor jump.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.dsp import process_offline
from emgteach.fragments import suggest_fragments
from emgteach.guided import load_row, load_span, rapid_train, train_span
from emgteach.selection import REST_FRACTION, ROW_LEAD_S, activity_threshold
from emgteach.sessions import parse_session_markers
from tests.test_contracciones_rapidas import _tren_sintetico
from tests.test_fatiga_guiada import _marcas
from tests.test_gradacion import REC_S, _gradacion_edf

FS = 1000
FILTROS = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}


def test_the_lead_is_half_a_second_before_the_flank() -> None:
    assert ROW_LEAD_S == pytest.approx(0.5)
    assert REST_FRACTION == pytest.approx(0.05)


def test_every_step_s_row_starts_the_same_lead_before_its_flank(tmp_path: Path) -> None:
    from emgteach.fragments import read_channels

    edf = _gradacion_edf(tmp_path / "grad.edf", ruido=True, arranque=True)
    raw, fs, _ = read_channels(edf, "FCR", None)
    tramo = (REC_S, REC_S + 54.0)
    env = process_offline(raw, fs, **FILTROS)["emg_envelope"]
    base, _u = activity_threshold(env[int(tramo[0] * fs):int(tramo[1] * fs)], 3.0)
    filas = suggest_fragments(raw, fs, FILTROS, span=tramo, default_k=3.0,
                              rest_fraction=REST_FRACTION)
    assert len(filas) == 5
    for f in filas:
        trozo = env[int(f.start_s * fs):int(f.end_s * fs)]
        nivel = base + REST_FRACTION * (float(trozo.max()) - base)
        flanco = f.start_s + int(np.argmax(trozo > nivel)) / fs
        assert flanco - f.start_s == pytest.approx(ROW_LEAD_S, abs=0.02), (f, flanco)


def test_a_row_s_lead_never_reaches_into_the_row_before() -> None:
    """Two contractions 1.2 s apart: two rows, and the second one's lead is
    cut where the first one ends."""
    from emgteach.fragments import default_detection, fit_to_envelope
    from emgteach.selection import Segment

    n = 12 * FS
    amp = np.full(n, 0.004)
    amp[2 * FS:5 * FS] = 0.3
    amp[int(6.2 * FS):9 * FS] = 0.3
    raw = np.random.default_rng(1).normal(0.0, 1.0, n) * amp
    filas = suggest_fragments(raw, FS, FILTROS, span=(0.0, 12.0), default_k=3.0,
                              rest_fraction=REST_FRACTION)
    assert len(filas) == 2
    assert filas[1].start_s >= filas[0].end_s
    # Fitted again over rows that touch, the lead stops at the row before.
    env = process_offline(raw, FS, **FILTROS)["emg_envelope"]
    pegadas = [Segment(2.0, 5.9), Segment(5.9, 9.2)]
    ajustadas = fit_to_envelope(pegadas, [env], FS, (0.0, 12.0),
                                default_detection(3.0, REST_FRACTION))
    assert ajustadas[1].start_s >= ajustadas[0].end_s


def test_the_train_s_row_starts_before_its_first_contraction() -> None:
    sesion, senal, _m = _tren_sintetico(tarde=(0.4, 0.5), rate=3.0)
    tramo = sesion.spans_named("train")[0]
    ventana = train_span(sesion, process_offline(senal, FS)["emg_envelope"], FS)
    assert ventana is not None
    # The subject began 0.4 s after the cue: the row, half a second before.
    assert ventana[0] == pytest.approx(tramo.start_s + 0.4 - ROW_LEAD_S, abs=0.1)


def test_the_load_s_row_is_the_whole_contraction_and_its_reading_stays() -> None:
    g, marcas = _marcas(0.0, 30.0)
    sesion = parse_session_markers(marcas)
    assert sesion is not None
    esfuerzo = sesion.spans_named("effort")[-1]
    env = np.full(int((g.total_seconds + 1) * FS), 0.004)
    a, b = esfuerzo.start_s + 0.6, esfuerzo.end_s - 8.0
    env[int(a * FS): int(b * FS)] = 0.15
    fila, lectura = load_row(sesion, env, FS), load_span(sesion, env, FS)
    assert fila is not None and lectura is not None
    assert fila[0] == pytest.approx(a - ROW_LEAD_S, abs=0.02)
    assert fila[1] == pytest.approx(lectura[1], abs=0.02)
    # Never into the rest the session measured.
    assert fila[0] >= sesion.spans_named("rest")[-1].end_s
    assert load_row(None, env, FS) is None


def _carga_que_sigue(tras: float, *, destello: bool = False, hasta_el_final: bool = False):
    """A load session whose weight is still held *tras* seconds after the
    effort's end mark, as the bench's forearm (the space bar at 79.8 s, the
    activity on to 81.5 and back at rest at 83); with *destello*, a flicker
    of 50 ms in the rest after it; with *hasta_el_final*, held to the
    session's end."""
    g, marcas = _marcas(0.0, 30.0)
    sesion = parse_session_markers(marcas)
    assert sesion is not None
    esfuerzo = sesion.spans_named("effort")[-1]
    env = np.full(int((g.total_seconds + 1) * FS), 0.004)
    a = esfuerzo.start_s + 0.6
    b = (sesion.end_s or g.total_seconds) + 1.0 if hasta_el_final else esfuerzo.end_s + tras
    env[int(a * FS): int(b * FS)] = 0.15
    if destello:
        c = esfuerzo.end_s + tras + 0.5
        env[int(c * FS): int((c + 0.05) * FS)] = 0.15
    return sesion, env, esfuerzo, b


def test_the_load_s_row_runs_to_where_the_weight_is_put_down() -> None:
    """The bench with exe #145: the row ended at the effort's end mark,
    79.8 s, and the forearm held the weight on to 81.5 s. The row now ends
    where the activity is back at rest, as every row; the load is still
    read to the effort's end."""
    sesion, env, esfuerzo, fin = _carga_que_sigue(1.7)
    fila, lectura = load_row(sesion, env, FS), load_span(sesion, env, FS)
    assert fila is not None and lectura is not None
    assert fila[1] == pytest.approx(fin, abs=0.02)
    assert lectura[1] == pytest.approx(esfuerzo.end_s)
    # A flicker of the noise in the rest after it does not hold it open.
    sesion, env, _e, fin = _carga_que_sigue(1.7, destello=True)
    fila = load_row(sesion, env, FS)
    assert fila is not None and fila[1] == pytest.approx(fin, abs=0.02)
    # Held to the end of the session: the row ends with the session.
    sesion, env, _e, _f = _carga_que_sigue(0.0, hasta_el_final=True)
    fila = load_row(sesion, env, FS)
    assert fila is not None and fila[1] == pytest.approx(sesion.end_s, abs=0.02)


def _con_jorobas(rate: float = 1.75, *, jorobas=(6, 7, 9), valle: float = 0.65):
    """A train as the bench's: at *rate*, full relaxation, and the
    contractions in *jorobas* with two humps 0.15 s apart, the trace between
    them at *valle* of the lower."""
    sesion, _senal, _m = _tren_sintetico(rate=rate, suelo=0.0, crecen=0.0)
    tramo = sesion.spans_named("train")[0]
    n = int((tramo.end_s + 12.0) * FS)
    t = np.arange(n) / FS
    amp = np.full(n, 0.004)
    periodo = 1.0 / rate
    k = 0
    while tramo.start_s + k * periodo < tramo.end_s:
        a = tramo.start_s + k * periodo
        if k in jorobas:
            amp[(t >= a) & (t < a + 0.12)] = 0.3
            amp[(t >= a + 0.12) & (t < a + 0.18)] = 0.3 * valle
            amp[(t >= a + 0.18) & (t < a + 0.3)] = 0.28
        else:
            amp[(t >= a) & (t < a + 0.3)] = 0.3
        k += 1
    senal = np.random.default_rng(9).normal(0.0, 1.0, n) * amp
    return sesion, senal, k


def test_a_contraction_with_two_humps_is_one() -> None:
    sesion, senal, k = _con_jorobas()
    filt = process_offline(senal, FS)["emg_filtered"]
    tren = rapid_train(sesion, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt)
    assert tren is not None
    assert tren.n == k
    # No floor taken between two humps: every floor is a relaxation's.
    assert max(tren.floors_mv) < 0.3 * min(tren.peaks_mv)


def test_quick_contractions_with_full_relaxation_are_all_counted() -> None:
    """Five a second, each relaxed: what the measure leaves between them is
    under 40 % of the peak, so none is taken for another's hump."""
    sesion, senal, _m = _tren_sintetico(rate=5.0, suelo=0.0)
    filt = process_offline(senal, FS)["emg_filtered"]
    tren = rapid_train(sesion, [(0.0, 1e9, 0.0)], fs=FS, emg_filtered=filt)
    assert tren is not None
    assert tren.n == pytest.approx(50, abs=1)
    assert tren.rate_hz == pytest.approx(5.0, abs=0.2)


@pytest.mark.gui
def test_the_editor_opens_on_the_load_s_row(qapp, tmp_path: Path) -> None:
    from tests.test_fatiga_guiada import _analizar, _carga_edf

    r = _analizar(qapp, _carga_edf(tmp_path / "e.edf"))
    fila, lectura = r["load_row"], r["load_span"]
    assert fila is not None and lectura is not None
    assert fila[0] == pytest.approx(lectura[0] - 2.0 - ROW_LEAD_S, abs=0.2)
    assert fila[1] == pytest.approx(lectura[1], abs=0.2)
