"""Tests for the force-velocity / load-velocity study helpers.

Synthetic signals only — no hardware or GUI.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np

from emgteach.force_velocity import (
    force_velocity_curves,
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
