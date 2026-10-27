"""The bench with exe #143 (Ángel, 27 October 2026): where a row starts.

A row of the one-muscle practical starts the same 0.5 s before its
contraction leaves rest — the baseline plus 5 % of its peak, the rule its
end is found by. On a lower line, steps 1, 4 and 5 began half a second
before their flank and 2 and 3 on it; the train's row, from a fifth of the
peak, cut the beginning of its first contraction. The rows of the train
and of the held load too.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.dsp import process_offline
from emgteach.fragments import suggest_fragments
from emgteach.guided import load_row, load_span, train_span
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
 assert fila[1] == lectura[1]
 # Never into the rest the session measured.
 assert fila[0] >= sesion.spans_named("rest")[-1].end_s
 assert load_row(None, env, FS) is None


@pytest.mark.gui
def test_the_editor_opens_on_the_load_s_row(qapp, tmp_path: Path) -> None:
 from tests.test_fatiga_guiada import _analizar, _carga_edf

 r = _analizar(qapp, _carga_edf(tmp_path / "e.edf"))
 fila, lectura = r["load_row"], r["load_span"]
 assert fila is not None and lectura is not None
 assert fila[0] == pytest.approx(lectura[0] - 2.0 - ROW_LEAD_S, abs=0.2)
 assert fila[1] == lectura[1]
