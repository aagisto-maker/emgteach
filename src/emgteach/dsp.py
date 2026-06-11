"""Digital signal processing for the surface-EMG pipeline.

Two complementary processing paths are kept strictly separate so the
methodological distinction is explicit:

- **Offline** (:func:`process_offline`) uses ``sosfiltfilt`` (zero-phase,
  no group delay) on the entire recording. This is the path used by
  the analysis tab when reviewing a saved EDF file.
- **Real-time** (:class:`RealtimeFilterState`) uses ``sosfilt`` with
  persistent ``zi`` state (causal, stateful). This is the path used by
  the acquisition tab so each newly arrived block is processed
  seamlessly with the running history.

The same Butterworth design (order 2 by default) is used by both paths
to keep the displayed waveforms comparable.

Pipeline
--------
1. **Notch 50 Hz** to suppress mains interference.
2. **Band-pass 20-450 Hz** to remove motion artefacts and high-frequency
   noise outside the surface-EMG informative band.
3. **Rectification** (absolute value).
4. **Low-pass 5 Hz** to extract the envelope.
5. **Sliding RMS** as a power-based amplitude estimate.
6. **Welch PSD** for MNF and MDF computation.

References
----------
.. [1] De Luca CJ. The Use of Surface Electromyography in Biomechanics.
   *J Appl Biomech* (1997).
.. [2] Phinyomark A, Phukpattaranont P, Limsakul C. Feature reduction
   and selection for EMG signal classification. *Expert Syst Appl* (2012).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.integrate import simpson
from scipy.signal import iirfilter, sosfilt, sosfilt_zi, sosfiltfilt, welch

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]


__all__ = [
    "OnsetDetector",
    "RealtimeFilterState",
    "compute_psd_mnf_mdf",
    "compute_segments",
    "design_bandpass",
    "design_lowpass",
    "design_notch",
    "detect_acquisition_problems",
    "detect_onsets",
    "process_offline",
]


# ---------------------------------------------------------------------------
# Filter design
# ---------------------------------------------------------------------------


def design_bandpass(
    f_low: float, f_high: float, fs: float, order: int = 2
) -> FloatArray:
    """Butterworth band-pass SOS coefficients for the EMG informative band."""
    return iirfilter(
        order, [f_low, f_high], btype="band", fs=fs, ftype="butter", output="sos"
    )


def design_notch(
    f_notch: float, fs: float, order: int = 2, bandwidth: float = 1.0
) -> FloatArray:
    """Butterworth notch SOS coefficients (50 Hz mains by default)."""
    return iirfilter(
        order,
        [f_notch - bandwidth, f_notch + bandwidth],
        btype="bandstop",
        fs=fs,
        ftype="butter",
        output="sos",
    )


def design_lowpass(f_cut: float, fs: float, order: int = 2) -> FloatArray:
    """Butterworth low-pass SOS coefficients (envelope smoothing)."""
    return iirfilter(
        order, f_cut, btype="low", fs=fs, ftype="butter", output="sos"
    )


# ---------------------------------------------------------------------------
# Real-time path (causal, stateful)
# ---------------------------------------------------------------------------


class RealtimeFilterState:
    """Stateful filter chain for the real-time acquisition path.

    Holds notch, band-pass and envelope filter coefficients along with
    their ``zi`` initial-conditions state, so that each call to
    :meth:`process_block` continues seamlessly from the previous block.

    Parameters
    ----------
    fs : float
        Sampling frequency (Hz).
    f_low, f_high : float, optional
        Band-pass cut-off frequencies (Hz). Defaults 20 and 450.
    f_notch : float, optional
        Mains notch frequency (Hz). Default 50.
    f_env : float, optional
        Envelope low-pass cut-off (Hz). Default 5.
    order : int, optional
        Butterworth order for band-pass and envelope filters. Default 2.
    """

    def __init__(
        self,
        fs: float,
        f_low: float = 20.0,
        f_high: float = 450.0,
        f_notch: float = 50.0,
        f_env: float = 5.0,
        order: int = 2,
    ) -> None:
        self.sos_band = design_bandpass(f_low, f_high, fs, order)
        self.sos_notch = design_notch(f_notch, fs)
        self.sos_env = design_lowpass(f_env, fs, order)

        # Initial conditions are zeroed so the first samples do not see
        # a spurious step. ``sosfilt_zi`` returns shape (n_sections, 2);
        # multiplied by 0.0 gives a same-shape zero array.
        self.zi_band = sosfilt_zi(self.sos_band) * 0.0
        self.zi_notch = sosfilt_zi(self.sos_notch) * 0.0
        self.zi_env = sosfilt_zi(self.sos_env) * 0.0

    def process_block(
        self, emg_mv: FloatArray | np.ndarray
    ) -> tuple[FloatArray, FloatArray]:
        """Apply notch -> band-pass -> rectify -> low-pass envelope.

        The ``zi`` states are mutated in place so the next call continues
        seamlessly from the current end of the buffer.

        Parameters
        ----------
        emg_mv : array-like
            Raw EMG block in millivolts.

        Returns
        -------
        emg_filtered : ndarray
            Notch + band-pass filtered EMG (mV).
        emg_envelope : ndarray
            Rectified + low-pass envelope (mV).
        """
        emg = np.asarray(emg_mv, dtype=np.float64)

        emg_notched, self.zi_notch = sosfilt(self.sos_notch, emg, zi=self.zi_notch)
        emg_filtered, self.zi_band = sosfilt(
            self.sos_band, emg_notched, zi=self.zi_band
        )
        emg_rect = np.abs(emg_filtered)
        emg_envelope, self.zi_env = sosfilt(self.sos_env, emg_rect, zi=self.zi_env)

        return emg_filtered, emg_envelope


# ---------------------------------------------------------------------------
# Offline path (zero-phase, sosfiltfilt)
# ---------------------------------------------------------------------------


def process_offline(
    emg_raw: FloatArray | np.ndarray,
    fs: float,
    f_low: float = 20.0,
    f_high: float = 450.0,
    f_notch: float = 50.0,
    f_env: float = 5.0,
    rms_window_ms: float = 50.0,
    order: int = 2,
) -> dict[str, FloatArray]:
    """Run the full zero-phase EMG pipeline on a complete recording.

    Order: notch 50 Hz -> band-pass 20-450 Hz -> rectify -> low-pass
    -> sliding RMS. Reflective padding of 500 ms is added before each
    ``sosfiltfilt`` to avoid border artefacts.

    Parameters
    ----------
    emg_raw : array-like
        Raw EMG signal in millivolts.
    fs : float
        Sampling frequency (Hz).
    f_low, f_high : float, optional
        Band-pass cut-off frequencies (default 20, 450 Hz).
    f_notch : float, optional
        Mains notch frequency (default 50 Hz).
    f_env : float, optional
        Envelope low-pass cut-off (default 5 Hz).
    rms_window_ms : float, optional
        Sliding-RMS window in milliseconds (default 50).
    order : int, optional
        Butterworth order (default 2).

    Returns
    -------
    dict
        Keys: ``emg_filtered``, ``emg_rectified``, ``emg_envelope``,
        ``rms_sliding``, ``emg_envelope_normalised``.
    """
    emg_raw = np.asarray(emg_raw, dtype=np.float64)

    sos_notch = design_notch(f_notch, fs)
    sos_band = design_bandpass(f_low, f_high, fs, order)
    sos_env = design_lowpass(f_env, fs, order)

    # Reflective padding of 500 ms on each side keeps sosfiltfilt's
    # forward+backward pass clean of border artefacts.
    pad_len = int(fs * 0.5)
    emg_padded = np.concatenate(
        [emg_raw[:pad_len][::-1], emg_raw, emg_raw[-pad_len:][::-1]]
    )

    emg_notched_full = sosfiltfilt(sos_notch, emg_padded)
    emg_filt_full = sosfiltfilt(sos_band, emg_notched_full)
    emg_filtered = emg_filt_full[pad_len:-pad_len]
    emg_rectified = np.abs(emg_filtered)

    emg_rect_padded = np.concatenate(
        [emg_rectified[:pad_len][::-1], emg_rectified, emg_rectified[-pad_len:][::-1]]
    )
    emg_env_full = sosfiltfilt(sos_env, emg_rect_padded)
    emg_envelope = emg_env_full[pad_len:-pad_len]

    rms_window = max(1, int(rms_window_ms / 1000.0 * fs))
    kernel = np.ones(rms_window) / rms_window
    rms_sliding = np.sqrt(np.convolve(emg_filtered**2, kernel, mode="same"))

    max_env = float(np.max(emg_envelope))
    if max_env <= 0:
        max_env = 1.0
    emg_envelope_normalised = emg_envelope / max_env

    return {
        "emg_filtered": emg_filtered,
        "emg_rectified": emg_rectified,
        "emg_envelope": emg_envelope,
        "rms_sliding": rms_sliding,
        "emg_envelope_normalised": emg_envelope_normalised,
    }


# ---------------------------------------------------------------------------
# Spectral analysis
# ---------------------------------------------------------------------------


def compute_psd_mnf_mdf(
    emg_filtered: FloatArray | np.ndarray,
    fs: float,
    f_low: float = 20.0,
    f_high: float = 450.0,
) -> dict[str, Any]:
    """Welch PSD and the two fatigue-related spectral metrics.

    Parameters
    ----------
    emg_filtered : array-like
        Filtered EMG signal (post notch + band-pass).
    fs : float
        Sampling frequency (Hz).
    f_low, f_high : float, optional
        Frequency band over which MNF and MDF are computed.

    Returns
    -------
    dict
        ``frequencies`` (1-D array, Hz), ``psd`` (1-D array, mV**2/Hz),
        ``mnf`` (mean frequency, Hz), ``mdf`` (median frequency, Hz).
    """
    emg = np.asarray(emg_filtered, dtype=np.float64)
    nperseg = int(fs)
    frequencies, psd = welch(emg, fs=fs, nperseg=nperseg, noverlap=nperseg // 2)

    band_mask = (frequencies >= f_low) & (frequencies <= f_high)
    f_band = frequencies[band_mask]
    psd_band = psd[band_mask]

    total_power = float(simpson(psd_band, x=f_band))
    if total_power > 0:
        mnf = float(simpson(f_band * psd_band, x=f_band) / total_power)
    else:
        mnf = 0.0

    cumulative = np.cumsum(psd_band)
    mdf_idx = np.where(cumulative >= total_power / 2.0)[0]
    mdf = float(f_band[mdf_idx[0]]) if mdf_idx.size > 0 else 0.0

    return {
        "frequencies": f_band,
        "psd": psd_band,
        "mnf": mnf,
        "mdf": mdf,
    }


def compute_segments(
    emg_filtered: FloatArray | np.ndarray,
    fs: float,
    seg_len_s: float = 1.0,
    overlap: float = 0.5,
) -> dict[str, FloatArray]:
    """Sliding-window RMS and MDF, suitable for fatigue trend analysis.

    Parameters
    ----------
    emg_filtered : array-like
        Filtered EMG signal.
    fs : float
        Sampling frequency (Hz).
    seg_len_s : float, optional
        Segment length in seconds (default 1.0).
    overlap : float, optional
        Fraction of overlap between consecutive segments (default 0.5).

    Returns
    -------
    dict
        ``t_seg`` (segment start times, seconds), ``rms_seg`` (mV),
        ``mdf_seg`` (Hz).
    """
    emg = np.asarray(emg_filtered, dtype=np.float64)
    points = int(seg_len_s * fs)
    step = max(1, int(points * (1.0 - overlap)))

    rms_seg: list[float] = []
    mdf_seg: list[float] = []

    for start in range(0, len(emg) - points + 1, step):
        segment = emg[start : start + points]
        rms_seg.append(float(np.sqrt(np.mean(segment**2))))

        f, pxx = welch(segment, fs=fs, nperseg=points)
        total = float(np.sum(pxx))
        cumulative = 0.0
        median_freq = 0.0
        for freq, power in zip(f, pxx, strict=False):
            cumulative += power
            if cumulative >= total / 2.0:
                median_freq = float(freq)
                break
        mdf_seg.append(median_freq)

    t_seg = np.arange(len(rms_seg)) * (step / fs)

    return {
        "t_seg": t_seg,
        "rms_seg": np.asarray(rms_seg, dtype=np.float64),
        "mdf_seg": np.asarray(mdf_seg, dtype=np.float64),
    }


# ---------------------------------------------------------------------------
# Acquisition quality diagnostics
# ---------------------------------------------------------------------------


def detect_acquisition_problems(
    emg_raw: FloatArray | np.ndarray, fs: float
) -> dict[str, Any]:
    """Flag two common acquisition failure modes used in the teaching lab.

    Detected problems:

    1. **Saturation** -- the signal hits a flat plateau at the ADC's
       extremes for at least 10 ms (see De Luca 1997). Usually means
       the gain is too high or the electrode lost contact momentarily.
    2. **Flat baseline** -- the standard deviation of the first 2 s of
       the recording is less than 1% of the global standard deviation.
       A genuine surface EMG always shows +/-5-20 microvolt baseline
       noise even at rest, so a perfectly flat baseline strongly
       suggests a disconnected electrode or a misconfigured gain.

    Parameters
    ----------
    emg_raw : array-like
        Raw EMG signal in any units (mV or ADC counts both work).
    fs : float
        Sampling frequency (Hz).

    Returns
    -------
    dict
        ``saturation_pct`` (float, %), ``flat_baseline`` (bool),
        ``warnings`` (list of human-readable warning strings).
    """
    emg = np.asarray(emg_raw, dtype=np.float64)
    warnings: list[str] = []

    # 1) Saturation: contiguous runs of >= 10 ms at ADC extremes
    v_max = float(np.max(emg))
    v_min = float(np.min(emg))
    threshold_max = v_max - 0.01 * (v_max - v_min)
    threshold_min = v_min + 0.01 * (v_max - v_min)
    extreme = (emg >= threshold_max) | (emg <= threshold_min)

    min_run = max(1, int(0.010 * fs))
    saturation_count = 0
    run = 0
    for at_extreme in extreme:
        if at_extreme:
            run += 1
        else:
            if run >= min_run:
                saturation_count += run
            run = 0
    if run >= min_run:
        saturation_count += run

    saturation_pct = 100.0 * saturation_count / len(emg) if len(emg) > 0 else 0.0

    if saturation_pct > 1.0:
        warnings.append(
            f"Possible saturation: {saturation_pct:.1f}% of samples sit at ADC "
            "extremes for runs >= 10 ms. Check electrode contact and gain."
        )

    # 2) Flat baseline in the first 2 s (before any contraction)
    n_initial = min(int(2.0 * fs), len(emg))
    std_initial = float(np.std(emg[:n_initial])) if n_initial > 0 else 0.0
    std_global = float(np.std(emg))

    flat_baseline = std_global > 0 and std_initial < 0.01 * std_global
    if flat_baseline:
        warnings.append(
            "Suspiciously flat baseline at the start of the recording. "
            "May indicate a disconnected electrode or misconfigured gain."
        )

    return {
        "saturation_pct": saturation_pct,
        "flat_baseline": flat_baseline,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Contraction-onset detection
# ---------------------------------------------------------------------------


class OnsetDetector:
    """Stateful, real-time detector of contraction onsets on the envelope.

    The detector implements the classical single-threshold surface-EMG
    onset rule: it estimates a resting baseline from the first
    ``baseline_s`` seconds of signal, sets the threshold to
    ``mean + k * std`` of that baseline, and flags an **onset** on each
    rising crossing of the threshold. A refractory period suppresses
    repeated detections within the same contraction.

    It is fed the same envelope blocks the acquisition worker produces,
    so detection runs live; :meth:`process` returns the onset times found
    in each block. The sample counter is global, so onset times are
    expressed in seconds from the start of the stream and line up with
    the EDF time base.

    Parameters
    ----------
    fs : float
        Sampling frequency (Hz).
    k : float, optional
        Threshold sensitivity in baseline standard deviations (default 3).
        Lower ``k`` detects weaker contractions.
    baseline_s : float, optional
        Length of the initial resting window used to estimate the
        baseline mean and standard deviation (default 1.0 s). The subject
        must be at rest during this window.
    refractory_s : float, optional
        Minimum time between consecutive onsets (default 0.5 s).
    min_duration_s : float, optional
        The envelope must stay above the threshold for at least this long
        before an onset is declared, which debounces brief noise spikes
        (default 0.05 s).
    """

    def __init__(
        self,
        fs: float,
        k: float = 3.0,
        baseline_s: float = 1.0,
        refractory_s: float = 0.5,
        min_duration_s: float = 0.05,
    ) -> None:
        self.fs = float(fs)
        self.k = float(k)
        self._baseline_n = max(1, int(baseline_s * fs))
        self._refractory_n = max(1, int(refractory_s * fs))
        self._min_duration_n = max(1, int(min_duration_s * fs))
        self._n = 0
        self._sum = 0.0
        self._sumsq = 0.0
        self._count = 0
        self._threshold: float | None = None
        self._above_run = 0
        self._last_onset_n = -(10**12)

    @property
    def threshold(self) -> float | None:
        """The calibrated threshold, or ``None`` while still in baseline."""
        return self._threshold

    def process(self, envelope_block: FloatArray | np.ndarray) -> list[float]:
        """Feed one envelope block; return onset times (s) found in it.

        Parameters
        ----------
        envelope_block : array-like
            A block of envelope samples, contiguous with previous blocks.

        Returns
        -------
        list of float
            Onset times in seconds from the start of the stream.
        """
        block = np.asarray(envelope_block, dtype=np.float64).ravel()
        onsets: list[float] = []
        for x in block:
            if self._threshold is None:
                # Baseline calibration phase.
                self._sum += x
                self._sumsq += x * x
                self._count += 1
                if self._count >= self._baseline_n:
                    mean = self._sum / self._count
                    var = max(self._sumsq / self._count - mean * mean, 0.0)
                    self._threshold = mean + self.k * (var**0.5)
            elif x > self._threshold:
                self._above_run += 1
                # Declare an onset once the signal has stayed above the
                # threshold for the minimum duration (debounces noise spikes),
                # timed at the crossing that started the run.
                if self._above_run == self._min_duration_n:
                    onset_n = self._n - (self._min_duration_n - 1)
                    if (onset_n - self._last_onset_n) >= self._refractory_n:
                        onsets.append(onset_n / self.fs)
                        self._last_onset_n = onset_n
            else:
                self._above_run = 0
            self._n += 1
        return onsets


def detect_onsets(
    envelope: FloatArray | np.ndarray,
    fs: float,
    k: float = 3.0,
    baseline_s: float = 1.0,
    refractory_s: float = 0.5,
    min_duration_s: float = 0.05,
) -> list[float]:
    """Detect contraction onsets in a complete envelope (offline helper).

    Convenience wrapper that runs :class:`OnsetDetector` over the whole
    signal in one call. Because the detector is stateful, feeding the
    signal in blocks via :meth:`OnsetDetector.process` yields identical
    results.

    Parameters
    ----------
    envelope : array-like
        Envelope (rectified, low-pass filtered EMG).
    fs : float
        Sampling frequency (Hz).
    k, baseline_s, refractory_s, min_duration_s : float, optional
        Forwarded to :class:`OnsetDetector`.

    Returns
    -------
    list of float
        Onset times in seconds.
    """
    detector = OnsetDetector(
        fs,
        k=k,
        baseline_s=baseline_s,
        refractory_s=refractory_s,
        min_duration_s=min_duration_s,
    )
    return detector.process(envelope)
