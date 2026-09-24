"""A proposed row holds the whole contraction, and nothing but it.

In the pair practical every row of the fragment editor had to be widened by
hand at both ends: the detector's run begins where the envelope crosses its
threshold, with the rise already under way, and ends where it crosses back,
with the fall not over. In force-velocity it was the other way round — the
row ran from before the cue to the end of the window, three times the lift.
One rule for both: from the row's peak out to where the envelope returns to
rest, with a small margin, never over the next row.
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.selection import Segment

pytestmark = pytest.mark.gui

FS = 1000
FILTROS = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}


def _senal(contracciones, dur_s: float = 30.0) -> np.ndarray:
    """Noise plus contractions that ramp up and down over *rampa* seconds."""
    rng = np.random.default_rng(3)
    sig = rng.normal(0.0, 0.01, size=int(dur_s * FS))
    t = np.arange(sig.size) / FS
    for a, b, rampa in contracciones:
        amp = np.clip(np.minimum((t - a) / rampa, (b - t) / rampa), 0.0, 1.0)
        sig += 0.5 * amp * np.sin(2 * np.pi * 90.0 * t)
    return sig


def _dialogo(qapp, raw, **kw):
    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

    return FragmentSelectionDialog(raw, FS, FILTROS, naming=False, **kw)


def test_a_row_that_starts_on_the_rise_is_widened_to_its_foot(qapp) -> None:
    """The detector's row, cut where the rise is already half-way."""
    dlg = _dialogo(qapp, _senal([(5.0, 6.0, 0.4)]))
    (fila,) = dlg._a_la_envolvente([Segment(5.25, 5.75)])
    assert fila.start_s < 5.15, "the foot of the rise is inside the row"
    assert fila.end_s > 5.85, "the end of the fall is inside the row"
    assert fila.start_s > 4.6 and fila.end_s < 6.4, "and not much more"
    dlg.deleteLater()


def test_a_row_much_wider_than_its_contraction_is_cut_to_it(qapp) -> None:
    """Force-velocity: a lift of half a second in a row of three."""
    dlg = _dialogo(qapp, _senal([(10.0, 10.5, 0.1)]))
    (fila,) = dlg._a_la_envolvente([Segment(9.0, 12.0)])
    assert 9.7 < fila.start_s < 10.05
    assert 10.45 < fila.end_s < 10.8
    dlg.deleteLater()


def test_a_row_never_reaches_into_its_neighbour(qapp) -> None:
    dlg = _dialogo(qapp, _senal([(5.0, 6.0, 0.4), (6.1, 7.0, 0.4)]))
    uno, dos = dlg._a_la_envolvente([Segment(5.2, 5.9), Segment(6.3, 6.9)])
    assert uno.end_s <= dos.start_s
    dlg.deleteLater()


def test_a_row_with_no_contraction_is_left_alone(qapp) -> None:
    dlg = _dialogo(qapp, _senal([]))
    (fila,) = dlg._a_la_envolvente([Segment(12.0, 13.0)])
    assert (fila.start_s, fila.end_s) == pytest.approx((12.0, 13.0))
    dlg.deleteLater()


def test_the_proposal_itself_follows_the_envelope(qapp) -> None:
    """Not only the helper: what the editor opens with."""
    dlg = _dialogo(qapp, _senal([(5.0, 6.0, 0.4), (9.0, 10.0, 0.4)]))
    filas = dlg.selected_segments()
    for ini, fin in [(5.0, 6.0), (9.0, 10.0)]:
        a, b = next(f for f in filas if f[0] < (ini + fin) / 2 < f[1])
        assert a < ini + 0.15 and b > fin - 0.15
    dlg.deleteLater()


def test_in_force_velocity_the_row_stays_inside_the_lifts_window(qapp) -> None:
    """Half a second before the cue at most, whatever the envelope says."""
    from emgteach.force_velocity import lift_windows_s

    raw = _senal([(47.0, 49.0, 0.3)], dur_s=60.0)   # picking up the weight first
    dlg = _dialogo(qapp, raw, lifts=lift_windows_s([(48.2, 3.0)], 60.0))
    ((a, b),) = dlg.selected_segments()
    assert a == pytest.approx(47.7, abs=0.02)
    assert b < 49.5
    dlg.deleteLater()
