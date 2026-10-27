"""A fragment ends where the muscle is back at rest (Ángel, 27 October 2026).

With the exe of 3.10.1's short bench the proposal came «fragmented»: the
detector cut each active run at the valleys between its peaks, and a
gradation's step — a brief peak at its start, the ripples of its plateau —
came in two or three rows. Each step was then measured on the piece that
kept most of it: on the bench's gradation, four steps of five, the 80 %
below the 60 %. In the one-muscle practical a fragment now ends only where
the envelope is back at its baseline plus 5 % of the peak's height, for at
least a second; and, in every practical, fragments that touch in the file
are measured as the one stretch of signal they are.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.fragments import default_detection, suggest_fragments
from emgteach.guided import contiguous_pieces, load_piece
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE, mode_rest_fraction
from emgteach.selection import REST_MIN_S, suggest_significant_segments
from tests.test_gradacion import REC_S, _gradacion_edf

FS = 1000
FILTROS = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}


def _senal(trozos, dur: float = 20.0, seed: int = 3) -> np.ndarray:
    """Noise at 0.004 mV of rest, and each ``(a, b, amplitude)`` on it."""
    n = int(dur * FS)
    amp = np.full(n, 0.004)
    for a, b, v in trozos:
        amp[int(a * FS):int(b * FS)] = v
    return np.random.default_rng(seed).normal(0.0, 1.0, n) * amp


def _filas(senal, rest_fraction: float, **kw) -> list[tuple[float, float]]:
    det = default_detection(3.0, rest_fraction)
    det.update(kw)
    segs = suggest_significant_segments(
        senal, FS, **FILTROS, k=det["k"], min_duration_s=det["min_duration_s"],
        merge_gap_s=det["merge_gap_s"], prominence=det["prominence"],
        rest_fraction=det["rest_fraction"])
    return [(s.start_s, s.end_s) for s in segs if s.reason != "whole"]


#: A step as the bench's: a brief peak, a dip, and the plateau.
_ESCALON = [(5.0, 5.8, 0.48), (5.8, 6.2, 0.12), (6.2, 9.0, 0.3)]


def test_it_is_the_one_muscle_practical_s_rule_and_only_its() -> None:
    assert mode_rest_fraction(MODE_SINGLE) == pytest.approx(0.05)
    assert mode_rest_fraction(MODE_PAIR) == 0.0
    assert mode_rest_fraction(MODE_KINEMATICS) == 0.0
    det = default_detection(3.0, 0.05)
    assert det["rest_fraction"] == pytest.approx(0.05)
    assert det["merge_gap_s"] == pytest.approx(REST_MIN_S) == pytest.approx(1.0)
    assert default_detection(3.0)["rest_fraction"] == 0.0


def test_a_step_with_a_peak_at_its_start_is_one_fragment() -> None:
    senal = _senal(_ESCALON)
    # Cut at the valleys, as the bench's proposal was: the peak apart.
    assert len(_filas(senal, 0.0)) >= 2
    filas = _filas(senal, 0.05)
    assert len(filas) == 1
    assert filas[0][0] == pytest.approx(5.0, abs=0.3)
    assert filas[0][1] == pytest.approx(9.0, abs=0.3)


def test_a_rest_ends_a_fragment_only_if_it_lasts_a_second() -> None:
    corto = _senal([(3.0, 6.0, 0.3), (6.6, 9.6, 0.3)])
    assert len(_filas(corto, 0.05)) == 1
    largo = _senal([(3.0, 6.0, 0.3), (7.5, 10.5, 0.3)])
    filas = _filas(largo, 0.05)
    assert len(filas) == 2
    assert filas[0][1] < 7.0 < filas[1][0]


def test_a_light_contraction_is_judged_against_its_own_peak() -> None:
    """5 % of a maximal contraction is above a light one: each run is
    measured against its own peak, so the light one is still a fragment."""
    senal = _senal([(3.0, 6.0, 1.0), (10.0, 13.0, 0.04)])
    filas = _filas(senal, 0.05)
    assert len(filas) == 2
    assert filas[1][0] == pytest.approx(10.0, abs=0.3)


def test_flickers_of_the_resting_noise_are_not_a_fragment() -> None:
    """The bench's gradation: in its first rest, flickers over the line
    (0.005 mV, steps of 0.35), joined over the gaps a rest must outlast,
    made a row of their own."""
    rng = np.random.default_rng(5)
    senal = _senal(_ESCALON, seed=6)
    for c in rng.uniform(0.5, 4.0, 12):
        i = int(c * FS)
        senal[i:i + 40] = rng.normal(0.0, 0.012, 40)
    filas = _filas(senal, 0.05)
    assert len(filas) == 1 and filas[0][0] > 4.5


def test_the_gradation_s_steps_are_proposed_one_row_each(tmp_path: Path) -> None:
    from emgteach.fragments import read_channels

    edf = _gradacion_edf(tmp_path / "grad.edf", ruido=True, arranque=True)
    raw, fs, _ = read_channels(edf, "FCR", None)
    tramo = (REC_S, REC_S + 54.0)
    partidas = suggest_fragments(raw, fs, FILTROS, span=tramo, default_k=3.0)
    assert len(partidas) > 5
    filas = suggest_fragments(raw, fs, FILTROS, span=tramo, default_k=3.0,
                              rest_fraction=mode_rest_fraction(MODE_SINGLE))
    assert len(filas) == 5
    # Each row holds its whole step, and nothing of the next.
    for k, f in enumerate(filas):
        inicio = REC_S + 5.0 + 10.0 * k
        assert inicio - 1.0 < f.start_s <= inicio + 0.3, (k, f)
        assert inicio + 3.7 <= f.end_s < inicio + 5.0, (k, f)


def test_fragments_that_touch_are_one_piece() -> None:
    kept = [(10.0, 12.0, 0.0), (12.01, 15.0, 2.0), (20.0, 22.0, 4.99)]
    assert contiguous_pieces(kept) == [(10.0, 15.0, 0.0), (20.0, 22.0, 4.99)]
    assert contiguous_pieces(list(reversed(kept)))[0] == (10.0, 15.0, 0.0)
    # The held load in two touching rows is read on both.
    assert load_piece((10.0, 40.0), [(10.0, 20.0), (20.01, 39.0)]) == (10.0, 39.0)


@pytest.mark.gui
def test_a_step_chosen_in_pieces_is_measured_whole(qapp, tmp_path: Path) -> None:
    """The bench's gradation, with the rows the old proposal made: a step in
    two or three touching rows, measured whole — five steps, each above the
    last, as without fragments."""
    from emgteach.fragments import read_channels
    from emgteach.guided import is_monotonic
    from tests.test_gradacion import _analizar, _analizar_fragmentos

    edf = _gradacion_edf(tmp_path / "grad.edf", ruido=True, arranque=True)
    raw, fs, _ = read_channels(edf, "FCR", None)
    partidas = suggest_fragments(raw, fs, FILTROS, span=(REC_S, REC_S + 54.0), default_k=3.0)
    assert len(partidas) > 5
    r = _analizar_fragmentos(qapp, edf, [(f.start_s, f.end_s) for f in partidas])
    pasos = r["grad_steps"]
    assert len(pasos) == 5 and is_monotonic(pasos), [p.held_pct for p in pasos]
    enteros = _analizar(qapp, edf)["grad_steps"]
    for p, q in zip(pasos, enteros, strict=True):
        assert p.held_pct == pytest.approx(q.held_pct, rel=0.05)


@pytest.mark.gui
def test_the_editor_of_the_one_muscle_practical_ends_fragments_at_rest(
    qapp, tmp_path: Path
) -> None:
    from emgteach.fragments import read_channels
    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog
    from emgteach.i18n import tr

    edf = _gradacion_edf(tmp_path / "grad.edf", ruido=True, arranque=True)
    raw, fs, _ = read_channels(edf, "FCR", None)
    dlg = FragmentSelectionDialog(raw, fs, FILTROS, naming=False,
                                  span=(REC_S, REC_S + 54.0), default_k=3.0,
                                  default_rest_fraction=mode_rest_fraction(MODE_SINGLE))
    assert len(dlg.selected_segments()) == 5
    # The valleys play no part, and the gap is the rest that ends a row.
    assert not dlg._sld_prom.isEnabled()
    assert dlg.detection_kwargs()["merge_gap_s"] == pytest.approx(1.0)
    textos = [w.text() for w in dlg.findChildren(type(dlg._lbl_k))]
    assert tr("A fragment ends after a rest of (s)") in textos
    dlg._reset_detection()
    assert dlg.detection_kwargs()["rest_fraction"] == pytest.approx(0.05)
    dlg.deleteLater()
    # The pair's editor still cuts at the valleys.
    par = FragmentSelectionDialog(raw, fs, FILTROS, naming=False,
                                  span=(REC_S, REC_S + 54.0), default_k=3.0)
    assert par._sld_prom.isEnabled() and len(par.selected_segments()) > 5
    par.deleteLater()
