"""Signal profiles: the extension point for new biopotential modalities.

A :class:`SignalProfile` bundles everything that defines *what a signal
is* — independent of the hardware that records it: the sampling rate,
the DSP filter band, the offline-analysis windows, the derived EDF
channel schema, the on-screen display ranges and the marker vocabulary.

The rest of the package (the workers and the GUI) reads its defaults
from a profile instead of from hardcoded literals scattered across
several files. Supporting a new biopotential type (ECG, EEG, EOG, ...)
is therefore a matter of defining a new ``SignalProfile`` instance; no
worker or GUI code needs to change. This is the extension point asked
for in the Hito 1 refactor (see ``DECISIONS.md``).

``EMG_PROFILE`` reproduces the exact values that were previously
hardcoded across the workers and the acquisition tab, so wiring the
package to it is behaviour-preserving by construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from emgteach.io import ChannelInfo

__all__ = [
    "EMG_PROFILE",
    "SignalProfile",
]


@dataclass(frozen=True)
class SignalProfile:
    """Immutable description of one biopotential modality.

    Attributes
    ----------
    name : str
        Human-readable modality name, e.g. ``"EMG"``.
    sample_frequency : int
        Nominal sampling rate in Hz. Used as the EDF samples-per-record
        and as the realtime display time base.
    f_low, f_high : float
        Band-pass cut-off frequencies (Hz) for the informative band.
    f_notch : float
        Mains-interference notch frequency (Hz).
    f_env : float
        Envelope low-pass cut-off (Hz).
    rms_window_ms : float
        Sliding-RMS window length (ms) for offline analysis.
    seg_len_s : float
        Segment length (s) for the segment-wise RMS/MDF fatigue analysis.
    overlap : float
        Fractional overlap between consecutive analysis segments.
    mvc_percentile : float
        Percentile of the envelope used as the MVC reference amplitude.
    onset_k : float
        Threshold sensitivity for automatic onset detection, in baseline
        standard deviations (threshold = baseline mean + ``onset_k``*SD).
    onset_baseline_s : float
        Resting window (s) used to estimate the onset-detection baseline.
    onset_refractory_s : float
        Minimum time (s) between consecutive automatic onsets.
    onset_min_duration_s : float
        Minimum time (s) the signal must stay above threshold before an
        onset is declared (debounces noise spikes).
    raw_label : str
        EDF label of the single, default sensor (used when no explicit
        per-sensor labels are supplied).
    dimension : str
        Physical unit written to the EDF header, e.g. ``"mV"``.
    ylim_raw, ylim_filtered, ylim_envelope : tuple of float
        Initial vertical display ranges for the realtime acquisition
        plots, in :attr:`dimension` units.
    marker_presets : tuple of str
        User-facing (Spanish) preset labels offered by the acquisition
        tab's event-marker control.
    """

    name: str

    # -- acquisition --
    sample_frequency: int = 1000

    # -- DSP filter band (Hz) --
    f_low: float = 20.0
    f_high: float = 450.0
    f_notch: float = 50.0
    f_env: float = 5.0

    # -- offline analysis --
    rms_window_ms: float = 50.0
    seg_len_s: float = 1.0
    overlap: float = 0.5
    mvc_percentile: float = 95.0

    # -- automatic onset detection (baseline + k*SD threshold) --
    onset_k: float = 3.0
    onset_baseline_s: float = 1.0
    onset_refractory_s: float = 0.5
    onset_min_duration_s: float = 0.05

    # -- EDF channel schema (one raw channel per sensor) --
    raw_label: str = "EMG"
    dimension: str = "mV"

    # -- realtime display ranges (dimension units) --
    ylim_raw: tuple[float, float] = (-3.3, 3.3)
    ylim_filtered: tuple[float, float] = (-0.8, 0.8)
    ylim_envelope: tuple[float, float] = (0.0, 0.5)

    # -- UI marker vocabulary (user-facing, Spanish) --
    marker_presets: tuple[str, ...] = (
        "Contraction onset",
        "Contraction end",
        "Fatigue",
        "Rest",
        "Other…",
    )

    def __post_init__(self) -> None:
        if self.sample_frequency <= 0:
            raise ValueError("sample_frequency must be a positive integer.")
        if not 0.0 < self.f_low < self.f_high:
            raise ValueError(
                f"Require 0 < f_low < f_high; got f_low={self.f_low}, "
                f"f_high={self.f_high}."
            )
        if self.f_env <= 0:
            raise ValueError("f_env must be positive.")
        if not 0.0 <= self.overlap < 1.0:
            raise ValueError(f"overlap must be in [0, 1); got {self.overlap}.")

    def filter_kwargs(self) -> dict[str, float]:
        """Return the four filter cut-offs as keyword arguments.

        Suitable for ``RealtimeFilterState(fs, **profile.filter_kwargs())``
        and for the filtering arguments of :func:`emgteach.dsp.process_offline`.
        """
        return {
            "f_low": self.f_low,
            "f_high": self.f_high,
            "f_notch": self.f_notch,
            "f_env": self.f_env,
        }

    def onset_kwargs(self) -> dict[str, float]:
        """Onset-detection parameters as kwargs for :class:`OnsetDetector`."""
        return {
            "k": self.onset_k,
            "baseline_s": self.onset_baseline_s,
            "refractory_s": self.onset_refractory_s,
            "min_duration_s": self.onset_min_duration_s,
        }

    def build_channels(
        self, sensor_labels: Sequence[str] | None = None, fs: int | None = None
    ) -> list[ChannelInfo]:
        """Build one raw EDF channel per sensor.

        Only the raw signal is stored. The filtered signal and the
        envelope are deterministic functions of the raw channel and are
        recomputed on analysis (see :func:`emgteach.dsp.process_offline`),
        so persisting them would be redundant and would overflow the
        16-character EDF label limit once descriptive multi-sensor labels
        are used.

        Parameters
        ----------
        sensor_labels : sequence of str, optional
            One EDF label per hardware channel (e.g. ``["Agonista",
            "Antagonista"]``). Defaults to a single sensor named
            :attr:`raw_label`.
        fs : int, optional
            Samples-per-record for every channel. Defaults to the
            profile's :attr:`sample_frequency`; pass the device's actual
            ``fs`` when it may differ from the nominal rate.

        Returns
        -------
        list of ChannelInfo
            One entry per sensor, in the given order.
        """
        labels = list(sensor_labels) if sensor_labels else [self.raw_label]
        sf = int(fs) if fs is not None else self.sample_frequency
        return [
            ChannelInfo(label, dimension=self.dimension, sample_frequency=sf)
            for label in labels
        ]


#: Default profile for surface EMG. Reproduces the exact filter, analysis,
#: channel and display parameters that the package used before the Hito 1
#: refactor, so consuming it changes no behaviour.
EMG_PROFILE = SignalProfile(name="EMG")
