"""Tests for the Jonsson APDF muscle-load analysis (``emgteach.apda``)."""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.apda import (
    ApdfResult,
    LoadLevel,
    OnlineLoad,
    classify_load,
    compute_apdf,
)


def test_uniform_distribution_recovers_percentiles():
    # Uniform load on [0, 100] %MVC: P10≈10, P50≈50, P90≈90.
    arr = np.linspace(0.0, 100.0, 10_001)
    res = compute_apdf(arr)
    assert res.static.value == pytest.approx(10.0, abs=0.5)
    assert res.median.value == pytest.approx(50.0, abs=0.5)
    assert res.peak.value == pytest.approx(90.0, abs=0.5)
    assert res.static.percentile == 10.0
    assert res.median.percentile == 50.0
    assert res.peak.percentile == 90.0


def test_constant_signal_all_levels_equal():
    res = compute_apdf(np.full(1000, 20.0))
    for level in res.levels:
        assert level.value == pytest.approx(20.0, abs=1e-6)


def test_classification_against_limits():
    # Constant 20 %MVC vs default limits 5 / 14 / 70.
    res = compute_apdf(np.full(1000, 20.0))
    assert res.static.exceeds is True       # 20 > 5
    assert res.median.exceeds is True       # 20 > 14
    assert res.peak.exceeds is False        # 20 < 70
    assert res.any_exceeds is True

    # A very light, low-variability load stays within every limit.
    light = compute_apdf(np.full(1000, 2.0))
    assert not any(level.exceeds for level in light.levels)
    assert light.any_exceeds is False


def test_custom_limits():
    res = compute_apdf(np.full(1000, 20.0), static_limit=25.0,
                       median_limit=25.0, peak_limit=25.0)
    assert not res.any_exceeds
    assert res.static.limit == 25.0


def test_cumulative_curve_is_monotonic_and_bounded():
    rng = np.random.default_rng(0)
    arr = np.abs(rng.normal(10.0, 5.0, 5000))
    res = compute_apdf(arr, n_points=128)
    assert isinstance(res, ApdfResult)
    assert res.load.shape == (128,)
    assert res.cumulative.shape == (128,)
    # Cumulative distribution: non-decreasing and within [0, 100] %.
    assert np.all(np.diff(res.cumulative) >= -1e-9)
    assert res.cumulative.min() >= 0.0
    assert res.cumulative.max() <= 100.0 + 1e-9
    # The load axis starts at 0 and is ascending.
    assert res.load[0] == 0.0
    assert np.all(np.diff(res.load) > 0)


def test_negative_values_are_clipped():
    # A few negative samples (e.g. from numeric noise) must not break the CDF.
    arr = np.concatenate([np.full(900, 10.0), np.full(100, -3.0)])
    res = compute_apdf(arr)
    assert res.static.value >= 0.0
    assert res.load[0] == 0.0


def test_empty_input_raises():
    with pytest.raises(ValueError):
        compute_apdf(np.array([]))
    with pytest.raises(ValueError):
        compute_apdf(np.array([np.nan, np.nan]))


def test_loadlevel_fields():
    res = compute_apdf(np.full(500, 8.0))
    lvl = res.median
    assert isinstance(lvl, LoadLevel)
    assert lvl.name == "median"
    assert lvl.value == pytest.approx(8.0)


def test_classify_load_zones():
    assert classify_load(10.0, 30.0, 50.0) == "normal"
    assert classify_load(30.0, 30.0, 50.0) == "warning"
    assert classify_load(45.0, 30.0, 50.0) == "warning"
    assert classify_load(50.0, 30.0, 50.0) == "danger"
    assert classify_load(80.0, 30.0, 50.0) == "danger"


def test_online_load_tracks_levels_and_status():
    ol = OnlineLoad(warning_limit=30.0, danger_limit=50.0, recent_n=100)
    assert ol.n == 0
    assert ol.current == 0.0
    assert ol.status == "normal"

    ol.add(np.full(500, 60.0))
    assert ol.current == pytest.approx(60.0, abs=1e-6)
    assert ol.status == "danger"
    assert ol.static == pytest.approx(60.0, abs=1e-6)
    assert ol.peak == pytest.approx(60.0, abs=1e-6)

    ol.reset()
    assert ol.n == 0
    assert ol.status == "normal"


def test_online_load_current_uses_recent_window_only():
    ol = OnlineLoad(warning_limit=30.0, danger_limit=50.0, recent_n=100)
    ol.add(np.full(1000, 5.0))    # old, scrolls out of the recent window
    ol.add(np.full(100, 40.0))    # recent fills the window
    assert ol.current == pytest.approx(40.0, abs=1e-6)
    assert ol.status == "warning"
    assert 5.0 <= ol.peak <= 40.0


def test_online_load_ignores_nonfinite():
    ol = OnlineLoad()
    ol.add([1.0, np.nan, 3.0, np.inf])
    assert ol.n == 2
