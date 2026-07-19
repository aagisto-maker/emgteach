"""Tests for the force-velocity / load-velocity study helpers.

Synthetic signals only — no hardware or GUI.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np

from emgteach.force_velocity import (
    assign_loads_to_reps,
    force_velocity_curves,
    fv_load_marker,
    parse_fv_load_markers,
    rep_metrics,
    segment_contractions,
    velocity_from_acc,
)

FS = 1000


def test_velocity_from_acc_integrates_and_is_zero_mean() -> None:
    t = np.arange(int(3 * FS)) / FS
    acc = np.sin(2 * np.pi * 2.0 * t)          # 2 Hz acceleration
    vel = velocity_from_acc(acc, FS)
    assert vel.shape == acc.shape
    assert abs(float(np.mean(vel))) < 0.05     # drift removed
    assert float(np.max(np.abs(vel))) > 0.0    # non-trivial


def test_velocity_from_acc_short_signal_is_safe() -> None:
    assert velocity_from_acc(np.zeros(3), FS).shape == (3,)


def test_segment_contractions_finds_three_bursts() -> None:
    n = int(9 * FS)
    env = np.full(n, 0.01)                      # quiet baseline
    rng = np.random.default_rng(0)
    env += 0.002 * rng.standard_normal(n)
    for start_s in (2.0, 4.0, 6.0):            # three 0.6 s bursts
        i0 = int(start_s * FS)
        env[i0:i0 + int(0.6 * FS)] += 0.4
    windows = segment_contractions(np.abs(env), FS)
    assert len(windows) == 3
    # Windows are ordered and non-overlapping.
    assert all(a[1] <= b[0] for a, b in pairwise(windows))


def test_rep_metrics_matches_windows() -> None:
    n = int(4 * FS)
    env = np.zeros(n)
    vel = np.zeros(n)
    env[1000:1500] = 0.5
    vel[1000:1500] = 2.0
    env[2000:2500] = 0.2
    vel[2000:2500] = 1.0
    emg_amp, peak_vel = rep_metrics(env, vel, [(1000, 1500), (2000, 2500)])
    np.testing.assert_allclose(emg_amp, [0.5, 0.2])
    np.testing.assert_allclose(peak_vel, [2.0, 1.0])


def test_force_velocity_curves_sorted_power_and_normalised() -> None:
    loads = np.array([3.0, 1.0, 2.0])
    vels = np.array([0.2, 0.9, 0.5])           # heavier -> slower
    c = force_velocity_curves(loads, vels)
    np.testing.assert_allclose(c["load"], [1.0, 2.0, 3.0])       # sorted by load
    np.testing.assert_allclose(c["velocity"], [0.9, 0.5, 0.2])
    np.testing.assert_allclose(c["power"], [0.9, 1.0, 0.6])      # load x velocity
    assert c["force_norm"].max() == 1.0 and c["velocity_norm"].max() == 1.0


# -- Guided-wizard load markers ------------------------------------------------

def test_fv_load_marker_roundtrips_through_parse() -> None:
    markers = [(0.0, "start"), (2.0, fv_load_marker(5.0)),
               (8.0, fv_load_marker(7.5)), (14.0, fv_load_marker(10.0))]
    parsed = parse_fv_load_markers(markers)
    assert parsed == [(2.0, 5.0), (8.0, 7.5), (14.0, 10.0)]


def test_parse_fv_load_markers_ignores_other_annotations() -> None:
    parsed = parse_fv_load_markers([(1.0, "M"), (2.0, "biceps"), (3.0, "note")])
    assert parsed == []


def test_parse_fv_load_markers_sorts_by_onset() -> None:
    markers = [(8.0, fv_load_marker(7.5)), (2.0, fv_load_marker(5.0))]
    assert parse_fv_load_markers(markers) == [(2.0, 5.0), (8.0, 7.5)]


def test_assign_loads_to_reps_maps_windows_to_preceding_marker() -> None:
    # Loads marked at 2 s, 8 s, 14 s; rep windows fall just after each marker.
    load_markers = [(2.0, 5.0), (8.0, 7.5), (14.0, 10.0)]
    windows = [
        (int(2.3 * FS), int(2.9 * FS)),   # -> 5 kg
        (int(8.4 * FS), int(9.0 * FS)),   # -> 7.5 kg
        (int(14.5 * FS), int(15.0 * FS)),  # -> 10 kg
    ]
    loads = assign_loads_to_reps(windows, FS, load_markers)
    assert loads == [5.0, 7.5, 10.0]


def test_assign_loads_to_reps_multiple_reps_per_load() -> None:
    load_markers = [(2.0, 5.0), (10.0, 8.0)]
    windows = [
        (int(2.3 * FS), int(2.8 * FS)),   # -> 5 kg
        (int(4.0 * FS), int(4.5 * FS)),   # -> 5 kg (still under the 5 kg marker)
        (int(10.4 * FS), int(11.0 * FS)),  # -> 8 kg
    ]
    assert assign_loads_to_reps(windows, FS, load_markers) == [5.0, 5.0, 8.0]


def test_windows_from_markers_one_window_per_marker() -> None:
    from emgteach.force_velocity import windows_from_markers

    # Markers ~12 s apart; each becomes a window from the marker onward.
    markers = [(12.5, 2.0), (24.7, 2.0), (49.0, 3.0)]
    windows, loads = windows_from_markers(markers, FS, n_samples=120 * FS)
    assert loads == [2.0, 2.0, 3.0]
    assert len(windows) == 3
    # Each window starts at its marker and does not overlap the next.
    assert windows[0][0] == int(12.5 * FS)
    assert all(a[1] <= b[0] for a, b in pairwise(windows))
    # Default max window is 6 s, so a widely-spaced marker gets the full 6 s.
    assert windows[2][1] - windows[2][0] == int(6.0 * FS)


def test_windows_from_markers_clipped_by_next_marker() -> None:
    from emgteach.force_velocity import windows_from_markers

    # Close markers (2 s apart): the window is clipped before the next one.
    markers = [(1.0, 5.0), (3.0, 7.0)]
    windows, loads = windows_from_markers(markers, FS, n_samples=10 * FS)
    assert loads == [5.0, 7.0]
    assert windows[0][1] <= int((3.0 - 0.5) * FS)   # clipped by next marker - gap


def test_assign_loads_to_reps_none_before_first_marker() -> None:
    load_markers = [(5.0, 5.0)]
    windows = [(int(1.0 * FS), int(1.5 * FS))]   # before any marker
    assert assign_loads_to_reps(windows, FS, load_markers) == [None]


def test_parse_loads_accepts_commas_spaces_and_semicolons() -> None:
    from emgteach.gui.widgets.force_velocity_plan_dialog import parse_loads

    # The bug the user hit: comma-separated loads with no spaces returned [].
    assert parse_loads("2,4,6,8") == [2.0, 4.0, 6.0, 8.0]
    assert parse_loads("2 4 6 8") == [2.0, 4.0, 6.0, 8.0]
    assert parse_loads("2, 4, 6, 8") == [2.0, 4.0, 6.0, 8.0]
    assert parse_loads("5;7.5;10") == [5.0, 7.5, 10.0]   # dot decimal, semicolons
    assert parse_loads("") == []
    assert parse_loads("a 3 -1 0 5") == [3.0, 5.0]        # ignore junk/non-positive
    assert parse_loads("4 4 6") == [4.0, 4.0, 6.0]        # duplicates + order kept
