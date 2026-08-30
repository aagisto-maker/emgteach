"""When "Fatigue: DETECTED" was not a finding.

A forearm recording of intermittent flexions and extensions — nothing held,
nothing fatigued — came back from the Analysis tab as **Fatigue: DETECTED
(MDF -26.4 %)** in red, off a regression whose R² was 0.18.

Two things had to be wrong at once for that:

* the segmenter windows the whole selection, rest included, and the median
  frequency of a resting segment is the median frequency of the amplifier —
  broadband, so far above a contraction's. An intermittent recording is
  therefore two populations of points, and any drift in how many of each fall
  early or late comes out as a slope;
* the verdict was the sign of that slope, with nothing asked of the fit.

Both fixtures below are built to fail the old rule on purpose: the
intermittent one has bursts that never change, only crowd closer together, and
that alone produced -2.2 Hz/s and a "40 % decline" — the same shape as the real
recording. The sustained one really does fatigue, and has to keep saying so.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import butter, sosfiltfilt

from emgteach.dsp import compute_segments
from emgteach.fatigue import (
    FATIGUE,
    INCONCLUSIVE,
    NO_FATIGUE,
    active_segments,
    fatigue_verdict,
    fit_mdf_vs_time,
)
from emgteach.profiles import EMG_PROFILE

FS = 1000.0


def _burst(n: int, centre: float, rng) -> np.ndarray:
    """A contraction: noise with an EMG-like band around *centre* Hz."""
    sos = butter(
        4, [max(20.0, centre - 40.0), centre + 40.0], "bandpass", fs=FS, output="sos"
    )
    return sosfiltfilt(sos, rng.normal(0.0, 1.0, n)) * 0.30


def _intermittent(seconds: int = 40, seed: int = 0) -> np.ndarray:
    """Identical bursts, only closer and closer together.

    The muscle does not fatigue here — every burst has the same spectrum. What
    changes is the duty cycle, and that is enough to tilt a regression fitted
    through rest and contraction alike.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * FS)
    x = rng.normal(0.0, 0.004, n)          # rest: amplifier noise
    t = 0.0
    while t < seconds - 1.5:
        i0 = int(t * FS)
        x[i0 : i0 + int(FS)] += _burst(int(FS), 100.0, rng)
        t += 1.0 + (4.0 - 3.7 * t / seconds)   # the gap shrinks 4 s → 0.3 s
    return x


def _sustained_fatigue(seconds: int = 40, seed: int = 1) -> np.ndarray:
    """A held contraction whose spectrum really does slide down, 130 → 70 Hz."""
    rng = np.random.default_rng(seed)
    n = int(seconds * FS)
    x = np.zeros(n)
    step = int(2.0 * FS)
    for i0 in range(0, n - step + 1, step):
        x[i0 : i0 + step] = _burst(step, 130.0 - 60.0 * i0 / n, rng)
    return x


def _fit(signal: np.ndarray, *, mask: bool = True) -> tuple[dict, int, int]:
    """The worker's own three steps: segment, keep the active ones, fit."""
    segs = compute_segments(signal, FS)
    act = (
        active_segments(segs["rms_seg"], EMG_PROFILE.fatigue_active_ratio)
        if mask
        else np.ones(segs["rms_seg"].size, dtype=bool)
    )
    fit = fit_mdf_vs_time(
        segs["t_seg"][act], segs["mdf_seg"][act], t_eval=segs["t_seg"]
    )
    return fit, int(np.count_nonzero(act)), int(act.size)


class TestTheMedianFrequencyOfSilence:
    """Rest segments have no business in a fatigue regression."""

    def test_the_old_rule_calls_a_steady_muscle_fatigued(self) -> None:
        """Without the mask, this recording reports a 40 % MDF decline. It is
        the fixture's whole reason for existing: if this ever stops failing,
        the test below proves nothing."""
        fit, _, _ = _fit(_intermittent(), mask=False)
        assert fit["slope_sign"] < 0
        assert fit["pct_decline"] > 20.0

    def test_fitted_over_the_contractions_the_trend_disappears(self) -> None:
        fit, n_act, n_all = _fit(_intermittent())
        assert n_act < n_all                     # rest really was dropped
        assert abs(fit["slope"]) < 0.5           # and the tilt went with it

    def test_a_sustained_contraction_keeps_every_segment(self) -> None:
        """The mask must not touch the practical it exists to protect."""
        _, n_act, n_all = _fit(_sustained_fatigue())
        assert n_act == n_all

    def test_the_display_curves_still_span_the_whole_recording(self) -> None:
        """The panels draw against every segment even though the fit used
        some of them. A shorter array here is a broken plot."""
        signal = _intermittent()
        segs = compute_segments(signal, FS)
        fit, _, _ = _fit(signal)
        assert fit["fitted"].size == segs["t_seg"].size
        assert fit["linear_fitted"].size == segs["t_seg"].size

    def test_a_recording_with_no_contraction_is_not_an_empty_fit(self) -> None:
        rng = np.random.default_rng(3)
        mask = active_segments(rng.normal(0.01, 0.001, 50), 0.30)
        assert mask.all()

    def test_an_empty_recording_gives_an_empty_mask(self) -> None:
        assert active_segments(np.zeros(0)).size == 0


class TestASlopeIsNotEvidence:
    """The fit has to support the verdict it is used for."""

    def test_a_line_through_a_cloud_is_not_a_verdict(self) -> None:
        assert fatigue_verdict(-1, 0.08, 45) == INCONCLUSIVE

    def test_a_real_decline_still_reads_as_fatigue(self) -> None:
        assert fatigue_verdict(-1, 0.92, 79) == FATIGUE

    def test_a_rising_trend_that_fits_reads_as_no_fatigue(self) -> None:
        assert fatigue_verdict(+1, 0.75, 40) == NO_FATIGUE

    def test_a_rising_trend_that_does_not_fit_is_not_a_clean_bill(self) -> None:
        """"No fatigue" is a claim too, and this recording cannot make it."""
        assert fatigue_verdict(+1, 0.05, 40) == INCONCLUSIVE

    def test_too_few_segments_to_fit_anything(self) -> None:
        assert fatigue_verdict(-1, 0.99, 2) == INCONCLUSIVE

    def test_a_flat_signal_stays_inconclusive(self) -> None:
        assert fatigue_verdict(0, 0.0, 40) == INCONCLUSIVE

    def test_the_thresholds_live_in_the_profile(self) -> None:
        assert EMG_PROFILE.fatigue_min_r2 == 0.30
        assert EMG_PROFILE.fatigue_active_ratio == 0.30
        assert EMG_PROFILE.fatigue_min_segments == 4


class TestEndToEnd:
    """The two recordings, through the same steps the worker takes."""

    def test_the_intermittent_recording_is_not_reported_as_fatigued(self) -> None:
        fit, n_act, _ = _fit(_intermittent())
        assert fatigue_verdict(
            fit["slope_sign"], fit["r_squared"], n_act,
            min_r2=EMG_PROFILE.fatigue_min_r2,
            min_segments=EMG_PROFILE.fatigue_min_segments,
        ) == INCONCLUSIVE

    def test_the_sustained_one_still_is(self) -> None:
        fit, n_act, _ = _fit(_sustained_fatigue())
        assert fit["r_squared"] > 0.5
        assert fatigue_verdict(
            fit["slope_sign"], fit["r_squared"], n_act,
            min_r2=EMG_PROFILE.fatigue_min_r2,
            min_segments=EMG_PROFILE.fatigue_min_segments,
        ) == FATIGUE


class TestTheThreeSurfacesReadTheSameVerdict:
    """The tab label, the PDF and the CSV each used to decide for themselves
    off the sign of the slope, so a change in one of them left the other two
    saying something else about the same recording."""

    @staticmethod
    def _result(verdict: str) -> dict:
        return {
            "fat_verdict": verdict, "fat_slope_sign": -1, "mdf_slope": -1.39,
            "fat_r_squared": 0.18, "fat_pct_decline": 26.4,
        }

    def test_the_csv_does_not_say_fatigue_on_an_inconclusive_fit(self) -> None:
        from emgteach.exports import _fatigue_verdict

        assert "fatigue (" not in _fatigue_verdict(self._result(INCONCLUSIVE))
        assert "fatigue (" in _fatigue_verdict(self._result(FATIGUE))

    def test_the_report_does_not_say_yes_on_an_inconclusive_fit(self) -> None:
        from emgteach.reports import _fatigue_text

        assert not _fatigue_text(self._result(INCONCLUSIVE)).startswith("Yes")
        assert _fatigue_text(self._result(FATIGUE)).startswith("Yes")

    def test_the_report_does_not_say_no_either(self) -> None:
        """The trap: an inconclusive recording read as a clean bill of health
        is the same error in the other direction."""
        from emgteach.reports import _fatigue_text

        texto = _fatigue_text(self._result(INCONCLUSIVE))
        assert "stable or rising" not in texto
        assert _fatigue_text(self._result(NO_FATIGUE)).startswith("No —")


@pytest.mark.gui
def test_the_verdict_reaches_the_result_dictionary(qapp, tmp_path) -> None:
    """Wiring: the worker has to put it there, or every surface falls back to
    "inconclusive" and the guard would look like it works when it does not."""
    pytest.importorskip("mne")
    from PySide6.QtCore import QElapsedTimer

    from emgteach.io import BufferedEdfWriter, ChannelInfo
    from emgteach.workers import AnalysisWorker

    path = tmp_path / "fatiga.edf"
    señal = _sustained_fatigue(seconds=20)
    ch = ChannelInfo("EMG", dimension="mV", sample_frequency=int(FS))
    with BufferedEdfWriter(str(path), channels=[ch]) as writer:
        writer.add_samples(señal.reshape(-1, 1).astype(float))

    worker = AnalysisWorker(edf_path=str(path), channel_name="EMG")
    salida: list[dict] = []
    worker.result_ready.connect(salida.append)
    worker.start()
    timer = QElapsedTimer()
    timer.start()
    while not salida and timer.elapsed() < 20000:
        qapp.processEvents()
    worker.wait(5000)

    assert salida, "the analysis produced no result"
    r = salida[0]
    assert r["fat_verdict"] == FATIGUE
    assert r["fat_n_seg"] > 0
    # And the curves the panels draw still match the segment axis.
    assert r["fat_fitted"].size == r["t_seg"].size
    assert r["fat_linear_fitted"].size == r["t_seg"].size
