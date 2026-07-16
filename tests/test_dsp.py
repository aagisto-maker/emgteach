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
    LiveQualityMonitor,
    OnsetDetector,
    RealtimeFilterState,
    compute_psd_mnf_mdf,
    compute_segments,
    design_bandpass,
    design_lowpass,
    design_notch,
    detect_acquisition_problems,
    detect_onsets,
    process_offline,
)
from emgteach.fatigue import fit_mdf_vs_time, fit_rms_vs_mdf
from emgteach.mvc import (
    adaptive_ylim,
    compute_mvc,
    mvc_from_reps,
    mvc_peak_hold,
    normalise_to_mvc,
)

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
        # 175 Hz sits between two mains harmonics (150, 200), so the narrow
        # comb must leave it essentially untouched.
        sos = design_notch(50.0, FS)
        sig = _sinusoid(175.0)
        out = sosfilt(sos, sig)
        assert _rms(out[int(0.5 * FS) :]) > 0.8 * _rms(sig)

    def test_notch_suppresses_harmonics(self) -> None:
        # The comb must also kill the mains harmonics that fall inside the
        # 20-450 Hz band (100, 150, ... Hz), which the old single-band
        # notch left untouched.
        sos = design_notch(50.0, FS)
        for f_harm in (100.0, 150.0, 250.0):
            sig = _sinusoid(f_harm)
            out = sosfilt(sos, sig)
            assert _rms(out[int(0.5 * FS) :]) < 0.1 * _rms(sig), (
                f"harmonic {f_harm} Hz not suppressed"
            )

    def test_notch_without_harmonics_keeps_them(self) -> None:
        # With harmonics disabled only the fundamental is removed.
        sos = design_notch(50.0, FS, harmonics=False)
        fund = _sinusoid(50.0)
        assert _rms(sosfilt(sos, fund)[int(0.5 * FS) :]) < 0.1 * _rms(fund)
        h150 = _sinusoid(150.0)
        assert _rms(sosfilt(sos, h150)[int(0.5 * FS) :]) > 0.8 * _rms(h150)

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


class TestChannelQuality:
    """Whole-channel load-time verdict used to warn on flat/saturated channels."""

    def test_ok_channel(self) -> None:
        from emgteach.dsp import assess_channel_quality

        rng = np.random.default_rng(0)
        sig = 0.1 * rng.standard_normal(int(3 * FS))  # ~0.1 mV RMS EMG
        assert assess_channel_quality(sig, FS, physical_max=1.65) == "ok"

    def test_flat_channel(self) -> None:
        from emgteach.dsp import assess_channel_quality

        sig = np.full(int(3 * FS), 0.001)  # essentially no signal
        assert assess_channel_quality(sig, FS, physical_max=1.65) == "flat"

    def test_saturated_channel(self) -> None:
        from emgteach.dsp import assess_channel_quality

        rng = np.random.default_rng(1)
        # Half the samples pinned at the +full-scale rail (electrode off).
        sig = rng.choice([1.65, -1.65, 0.2], size=int(3 * FS), p=[0.5, 0.2, 0.3])
        assert assess_channel_quality(sig, FS, physical_max=1.65) == "saturated"

    def test_weak_channel(self) -> None:
        from emgteach.dsp import assess_channel_quality

        rng = np.random.default_rng(2)
        sig = 0.02 * rng.standard_normal(int(3 * FS))  # low but non-zero
        assert assess_channel_quality(sig, FS, physical_max=1.65) == "weak"


class TestLiveQualityMonitor:
    """Per-block live quality check against the device's physical rails."""

    def test_clean_block_is_ok(self) -> None:
        mon = LiveQualityMonitor(-12.5, 12.5)
        rng = np.random.default_rng(0)
        status = mon.update(rng.normal(0.0, 0.3, size=100))
        assert status.code == "ok"

    def test_saturating_block_is_flagged(self) -> None:
        mon = LiveQualityMonitor(-12.5, 12.5)
        block = np.full(100, 12.5)  # pegged at the top rail
        status = mon.update(block)
        assert status.code == "saturation"
        assert status.saturation_frac > 0.9

    def test_flat_block_is_flagged(self) -> None:
        mon = LiveQualityMonitor(-12.5, 12.5)
        status = mon.update(np.full(100, 0.0))  # disconnected electrode
        assert status.code == "flat"

    def test_partial_saturation_below_threshold_is_ok(self) -> None:
        mon = LiveQualityMonitor(-12.5, 12.5, sat_frac=0.1)
        block = np.concatenate([np.full(5, 12.5), np.full(95, 1.0) * 0.0 + 2.0])
        # 5% at rail (< 10% threshold), and enough variance -> ok
        block[50:] = np.linspace(-2, 2, 50)
        assert mon.update(block).code == "ok"

    def test_invalid_rails_raise(self) -> None:
        with pytest.raises(ValueError, match="rail_max"):
            LiveQualityMonitor(1.0, 1.0)

    def test_empty_block_is_ok(self) -> None:
        mon = LiveQualityMonitor(-1.0, 1.0)
        assert mon.update(np.array([])).code == "ok"


# ---------------------------------------------------------------------------
# Fatigue analysis
# ---------------------------------------------------------------------------


class TestOnsetDetection:
    """Baseline + k*SD onset detection on a rest/burst envelope."""

    @staticmethod
    def _rest_burst_envelope() -> np.ndarray:
        """1.5 s rest, 0.5 s burst, 0.5 s rest, 0.5 s burst (envelope-like)."""
        rng = np.random.default_rng(0)

        def rest(n: int) -> np.ndarray:
            return 0.02 + 0.005 * np.abs(rng.standard_normal(n))

        return np.concatenate(
            [
                rest(int(1.5 * FS)),
                np.full(int(0.5 * FS), 0.5),
                rest(int(0.5 * FS)),
                np.full(int(0.5 * FS), 0.5),
            ]
        )

    def test_detects_the_two_burst_onsets(self) -> None:
        env = self._rest_burst_envelope()
        onsets = detect_onsets(env, FS, k=3.0, baseline_s=1.0, refractory_s=0.3)
        assert len(onsets) == 2
        assert onsets[0] == pytest.approx(1.5, abs=0.05)
        assert onsets[1] == pytest.approx(2.5, abs=0.05)

    def test_blockwise_matches_oneshot(self) -> None:
        env = self._rest_burst_envelope()
        oneshot = detect_onsets(env, FS, k=3.0, baseline_s=1.0, refractory_s=0.3)

        detector = OnsetDetector(FS, k=3.0, baseline_s=1.0, refractory_s=0.3)
        blockwise: list[float] = []
        for i in range(0, len(env), 100):  # 100-sample blocks, as the device
            blockwise.extend(detector.process(env[i : i + 100]))
        assert blockwise == oneshot

    def test_sustained_burst_is_a_single_onset(self) -> None:
        rng = np.random.default_rng(1)
        env = np.concatenate(
            [0.02 + 0.005 * np.abs(rng.standard_normal(FS)), np.full(3 * FS, 0.6)]
        )
        onsets = detect_onsets(env, FS, k=3.0, baseline_s=1.0)
        assert len(onsets) == 1

    def test_rest_only_has_no_onset(self) -> None:
        rng = np.random.default_rng(2)
        env = 0.02 + 0.005 * np.abs(rng.standard_normal(3 * FS))
        assert detect_onsets(env, FS, k=3.0, baseline_s=1.0) == []

    def test_threshold_calibrates_above_baseline(self) -> None:
        detector = OnsetDetector(FS, k=3.0, baseline_s=1.0)
        assert detector.threshold is None
        detector.process(0.1 + np.zeros(FS))  # 1 s of constant baseline
        assert detector.threshold is not None
        assert detector.threshold >= 0.1


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

    def test_linear_regression_index(self) -> None:
        # MDF = 120 - 1.0*t over 0..30 s: slope -1 Hz/s, perfect fit,
        # decline = 30/120 = 25%.
        t_seg = np.linspace(0, 30, 30)
        mdf_seg = 120 - 1.0 * t_seg
        result = fit_mdf_vs_time(t_seg, mdf_seg, degree=2)
        assert result["slope"] == pytest.approx(-1.0, abs=1e-6)
        assert result["slope_per_min"] == pytest.approx(-60.0, abs=1e-4)
        assert result["intercept"] == pytest.approx(120.0, abs=1e-6)
        assert result["r_squared"] == pytest.approx(1.0, abs=1e-9)
        assert result["pct_decline"] == pytest.approx(25.0, abs=1e-6)
        assert len(result["linear_fitted"]) == len(t_seg)

    def test_r_squared_drops_with_noise(self) -> None:
        rng = np.random.default_rng(0)
        t_seg = np.linspace(0, 30, 60)
        clean = 120 - 1.0 * t_seg
        noisy = clean + rng.normal(0, 15, size=t_seg.shape)
        r2_clean = fit_mdf_vs_time(t_seg, clean)["r_squared"]
        r2_noisy = fit_mdf_vs_time(t_seg, noisy)["r_squared"]
        assert r2_clean > 0.99
        assert r2_noisy < r2_clean

    def test_too_few_points_zero_regression(self) -> None:
        result = fit_mdf_vs_time(np.array([0.0]), np.array([100.0]))
        assert result["slope"] == 0.0
        assert result["r_squared"] == 0.0
        assert result["pct_decline"] == 0.0

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

    def test_peak_hold_picks_strongest_sustained_window(self) -> None:
        # A long weak plateau (0.6) plus a brief strong burst (1.0) that is
        # under 5 % of the trace, so it is missed by the whole-trace P95.
        env = np.concatenate([np.full(300, 0.6), np.full(8, 1.0)])
        assert compute_mvc(env) == pytest.approx(0.6, abs=0.02)  # burst too brief
        # peak-hold over an 8-sample window recovers the true strong level.
        assert mvc_peak_hold(env, window_samples=8) == pytest.approx(1.0, abs=0.02)

    def test_peak_hold_falls_back_when_shorter_than_window(self) -> None:
        env = np.array([0.4, 0.8])
        assert mvc_peak_hold(env, window_samples=50) == pytest.approx(
            compute_mvc(env)
        )

    def test_mvc_from_reps_uses_peak_hold_and_takes_best(self) -> None:
        weak = np.full(100, 0.5)
        strong = np.concatenate([np.full(30, 1.2), np.full(70, 0.5)])
        best = mvc_from_reps([weak, strong], window_samples=30)
        assert best == pytest.approx(1.2, abs=0.02)   # best-of-N across reps

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
