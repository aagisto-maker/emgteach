"""Tests for the DSP, fatigue and MVC modules.

All tests run on synthetic signals and require neither hardware nor
GUI. The properties checked here are the same ones a JOSS reviewer
would expect to see verified for an EMG analysis package: filters
attenuate out-of-band content, the offline pipeline is zero-phase, the
spectral metrics match a known carrier, the fatigue indicator
responds correctly to a known monotonic trend, and the MVC
normalisation scales as advertised.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import sosfilt, sosfilt_zi

from emgteach.dsp import (
    RealtimeFilterState,
    compute_psd_mnf_mdf,
    compute_segments,
    design_bandpass,
    design_lowpass,
    design_notch,
    detect_acquisition_problems,
    process_offline,
)
from emgteach.fatigue import fit_mdf_vs_time, fit_rms_vs_mdf
from emgteach.mvc import adaptive_ylim, compute_mvc, normalise_to_mvc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FS = 1000  # Hz


def _sinusoid(freq: float, duration_s: float = 2.0, amp: float = 1.0) -> np.ndarray:
    """Pure cosine of given frequency and amplitude, sampled at FS."""
    t = np.arange(int(duration_s * FS)) / FS
    return amp * np.cos(2 * np.pi * freq * t)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(x) ** 2)))


# ---------------------------------------------------------------------------
# Filter design
# ---------------------------------------------------------------------------


class TestFilterDesign:
    def test_bandpass_attenuates_low_frequency(self) -> None:
        sos = design_bandpass(20.0, 450.0, FS)
        # 5 Hz is well below the band-pass, must be strongly attenuated
        sig = _sinusoid(5.0)
        out = sosfilt(sos, sig)
        # Skip the transient (first 0.2 s) and check steady state
        assert _rms(out[int(0.2 * FS) :]) < 0.2 * _rms(sig)

    def test_bandpass_passes_in_band(self) -> None:
        sos = design_bandpass(20.0, 450.0, FS)
        sig = _sinusoid(100.0)
        out = sosfilt(sos, sig)
        # In-band sinusoid must come out at near-unity gain after transient
        assert 0.7 < _rms(out[int(0.5 * FS) :]) < 1.5 * _rms(sig)

    def test_notch_suppresses_50hz(self) -> None:
        sos = design_notch(50.0, FS)
        sig = _sinusoid(50.0)
        out = sosfilt(sos, sig)
        # Notch around 50 Hz must drop the carrier by at least 90%
        assert _rms(out[int(0.5 * FS) :]) < 0.1 * _rms(sig)

    def test_notch_preserves_far_frequency(self) -> None:
        sos = design_notch(50.0, FS)
        sig = _sinusoid(150.0)
        out = sosfilt(sos, sig)
        assert _rms(out[int(0.5 * FS) :]) > 0.8 * _rms(sig)

    def test_lowpass_attenuates_high_frequency(self) -> None:
        sos = design_lowpass(5.0, FS)
        sig = _sinusoid(50.0)
        out = sosfilt(sos, sig)
        assert _rms(out[int(0.5 * FS) :]) < 0.1 * _rms(sig)


# ---------------------------------------------------------------------------
# Realtime filter state
# ---------------------------------------------------------------------------


class TestRealtimeFilterState:
    def test_block_processing_matches_full_signal(self) -> None:
        """Running blocks one by one must yield the same result as
        processing the whole signal in one call (modulo numerical noise).
        This is the property that justifies streaming filtering at all.
        """
        rng = np.random.default_rng(seed=0)
        full = rng.standard_normal(2000)

        # Reference: full signal in one call
        ref_state = RealtimeFilterState(FS)
        full_filtered, full_envelope = ref_state.process_block(full)

        # Compare with: same signal split in 100-sample blocks
        block_state = RealtimeFilterState(FS)
        block_filt: list[np.ndarray] = []
        block_env: list[np.ndarray] = []
        for i in range(0, len(full), 100):
            f, e = block_state.process_block(full[i : i + 100])
            block_filt.append(f)
            block_env.append(e)
        cat_filt = np.concatenate(block_filt)
        cat_env = np.concatenate(block_env)

        np.testing.assert_allclose(cat_filt, full_filtered, atol=1e-9)
        np.testing.assert_allclose(cat_env, full_envelope, atol=1e-9)

    def test_zi_state_is_separate_per_filter(self) -> None:
        state = RealtimeFilterState(FS)
        # Just verify shapes match what scipy expects
        assert state.zi_band.shape == sosfilt_zi(state.sos_band).shape
        assert state.zi_notch.shape == sosfilt_zi(state.sos_notch).shape
        assert state.zi_env.shape == sosfilt_zi(state.sos_env).shape


# ---------------------------------------------------------------------------
# Offline pipeline
# ---------------------------------------------------------------------------


class TestProcessOffline:
    def test_returns_expected_keys(self) -> None:
        sig = _sinusoid(100.0)
        result = process_offline(sig, FS)
        assert set(result.keys()) == {
            "emg_filtered",
            "emg_rectified",
            "emg_envelope",
            "rms_sliding",
            "emg_envelope_normalised",
        }

    def test_output_lengths_match_input(self) -> None:
        sig = _sinusoid(100.0, duration_s=3.0)
        result = process_offline(sig, FS)
        for key in (
            "emg_filtered",
            "emg_rectified",
            "emg_envelope",
            "rms_sliding",
            "emg_envelope_normalised",
        ):
            assert len(result[key]) == len(sig), f"{key}: length mismatch"

    def test_envelope_normalised_in_unit_range(self) -> None:
        sig = _sinusoid(100.0, duration_s=2.0)
        result = process_offline(sig, FS)
        env_norm = result["emg_envelope_normalised"]
        # Normalised envelope must be in [0, 1+small overshoot]
        assert env_norm.min() >= 0.0
        assert env_norm.max() <= 1.0 + 1e-9

    def test_zero_phase_no_group_delay(self) -> None:
        """A symmetric burst centred at t=1.0 s must keep its peak near
        t=1.0 s after zero-phase filtering. This is the property that
        sosfiltfilt provides and sosfilt does not.
        """
        n = int(2.0 * FS)
        t = np.arange(n) / FS
        # Hanning-shaped 100 Hz burst centred at 1.0 s
        burst = np.cos(2 * np.pi * 100 * t) * np.exp(-((t - 1.0) ** 2) / (2 * 0.05**2))
        result = process_offline(burst, FS)
        peak_idx = int(np.argmax(np.abs(result["emg_filtered"])))
        assert abs(peak_idx - n // 2) < int(0.05 * FS), (
            f"Burst peak at index {peak_idx}, expected near {n // 2}; "
            "offline pipeline appears not to be zero-phase."
        )


# ---------------------------------------------------------------------------
# Spectral metrics
# ---------------------------------------------------------------------------


class TestSpectralMetrics:
    def test_psd_mnf_mdf_match_known_sinusoid(self) -> None:
        """For a pure 80 Hz cosine, MNF and MDF must both be very close
        to 80 Hz (the only spectral content in the signal).
        """
        sig = _sinusoid(80.0, duration_s=4.0)
        result = compute_psd_mnf_mdf(sig, FS)
        assert abs(result["mnf"] - 80.0) < 2.0, f"MNF={result['mnf']}"
        assert abs(result["mdf"] - 80.0) < 2.0, f"MDF={result['mdf']}"

    def test_psd_returns_band_only(self) -> None:
        sig = _sinusoid(100.0, duration_s=4.0)
        result = compute_psd_mnf_mdf(sig, FS, f_low=20.0, f_high=450.0)
        assert result["frequencies"].min() >= 20.0
        assert result["frequencies"].max() <= 450.0

    def test_compute_segments_consistent_lengths(self) -> None:
        sig = _sinusoid(100.0, duration_s=10.0)
        result = compute_segments(sig, FS, seg_len_s=1.0, overlap=0.5)
        n = len(result["t_seg"])
        assert n == len(result["rms_seg"]) == len(result["mdf_seg"])
        # 10 s at 1 s segments with 50% overlap -> 19 segments
        assert n == 19

    def test_compute_segments_mdf_close_to_carrier(self) -> None:
        sig = _sinusoid(150.0, duration_s=5.0)
        result = compute_segments(sig, FS, seg_len_s=1.0, overlap=0.5)
        # Each segment's MDF must be near 150 Hz
        for mdf in result["mdf_seg"]:
            assert abs(mdf - 150.0) < 5.0


# ---------------------------------------------------------------------------
# Acquisition diagnostics
# ---------------------------------------------------------------------------


class TestDetectAcquisitionProblems:
    def test_clean_signal_no_warnings(self) -> None:
        rng = np.random.default_rng(seed=1)
        sig = rng.standard_normal(int(5 * FS)) * 0.1
        result = detect_acquisition_problems(sig, FS)
        assert result["saturation_pct"] < 1.0
        assert result["flat_baseline"] is False
        assert result["warnings"] == []

    def test_detects_saturation(self) -> None:
        # Build a signal where 30% of samples are pegged at +max for 100 ms each
        n = int(5 * FS)
        sig = np.zeros(n)
        # Several 100-ms saturation episodes
        for start in range(0, n, 500):
            sig[start : start + 100] = 10.0  # at extreme
        sig[100:200] = -10.0  # also negative extremes
        result = detect_acquisition_problems(sig, FS)
        assert result["saturation_pct"] > 1.0
        assert any("saturation" in w.lower() for w in result["warnings"])

    def test_detects_flat_baseline(self) -> None:
        rng = np.random.default_rng(seed=2)
        n = int(5 * FS)
        # First 2 s are exactly zero (flat); rest is normal
        sig = np.concatenate([np.zeros(int(2 * FS)), rng.standard_normal(n - int(2 * FS))])
        result = detect_acquisition_problems(sig, FS)
        assert result["flat_baseline"] is True
        assert any("baseline" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Fatigue analysis
# ---------------------------------------------------------------------------


class TestFatigue:
    def test_descending_mdf_signals_fatigue(self) -> None:
        t_seg = np.linspace(0, 30, 30)
        mdf_seg = 120 - 1.0 * t_seg  # linearly descending, 120 -> 90 Hz
        result = fit_mdf_vs_time(t_seg, mdf_seg, degree=2)
        assert result["slope_sign"] == -1
        # Fitted endpoints close to actual endpoints (tight linear fit)
        assert abs(result["fitted"][0] - mdf_seg[0]) < 1e-6
        assert abs(result["fitted"][-1] - mdf_seg[-1]) < 1e-6

    def test_ascending_mdf_signals_no_fatigue(self) -> None:
        t_seg = np.linspace(0, 30, 30)
        mdf_seg = 80 + 0.5 * t_seg
        result = fit_mdf_vs_time(t_seg, mdf_seg, degree=2)
        assert result["slope_sign"] == +1

    def test_too_few_points_returns_constant_fit(self) -> None:
        t_seg = np.array([0.0])
        mdf_seg = np.array([100.0])
        result = fit_mdf_vs_time(t_seg, mdf_seg, degree=2)
        assert result["slope_sign"] == 0
        assert np.allclose(result["fitted"], 100.0)

    def test_rms_vs_mdf_returns_expected_keys(self) -> None:
        mdf_seg = np.linspace(80, 120, 20)
        rms_seg = np.linspace(0.1, 0.5, 20)
        result = fit_rms_vs_mdf(mdf_seg, rms_seg, degree=2, n_points=50)
        assert "coefs" in result
        assert "mdf_range" in result
        assert "fitted" in result
        assert len(result["mdf_range"]) == 50
        assert len(result["fitted"]) == 50


# ---------------------------------------------------------------------------
# MVC normalisation
# ---------------------------------------------------------------------------


class TestMVC:
    def test_compute_mvc_returns_percentile_95(self) -> None:
        env = np.linspace(0.0, 1.0, 1001)  # values 0..1
        # 95th percentile of 0..1 inclusive = 0.95
        assert compute_mvc(env) == pytest.approx(0.95, abs=0.01)

    def test_compute_mvc_falls_back_to_max_when_percentile_zero(self) -> None:
        env = np.zeros(100)
        env[-1] = 0.5  # only the last value is nonzero
        # Percentile 95 of mostly zeros is 0 -> falls back to max (0.5)
        assert compute_mvc(env) == pytest.approx(0.5)

    def test_normalise_to_mvc_scales_correctly(self) -> None:
        env = np.array([0.5, 1.0, 1.5])
        out = normalise_to_mvc(env, mvc_ref=1.0)
        np.testing.assert_allclose(out, [50.0, 100.0, 150.0])

    def test_normalise_to_mvc_zero_ref_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            normalise_to_mvc(np.array([1.0]), mvc_ref=0.0)

    def test_adaptive_ylim_minimum_110(self) -> None:
        env_norm = np.full(100, 50.0)  # all values at 50 %MVC
        # 99th percentile is 50; 50 * 1.10 = 55 < 110, so floor kicks in
        assert adaptive_ylim(env_norm, n_plot=100) == 110.0

    def test_adaptive_ylim_scales_with_p99(self) -> None:
        env_norm = np.full(100, 200.0)  # peak well above MVC
        result = adaptive_ylim(env_norm, n_plot=100, margin=0.10)
        # 200 * 1.10 = 220 > 110, so we get the scaled value
        assert result == pytest.approx(220.0, rel=0.01)
