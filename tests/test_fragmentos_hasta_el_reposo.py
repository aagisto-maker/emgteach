"""Fragments that touch in the file are measured as one (Ángel, 3.10.1).

A gradation's step proposed in two or three touching rows was measured on the
piece that kept most of it: on the bench's gradation, four steps of five, the
80 % below the 60 %.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from emgteach.fragments import suggest_fragments
from emgteach.guided import contiguous_pieces, load_piece
from tests.test_gradacion import REC_S, _gradacion_edf

FILTROS = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}


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
