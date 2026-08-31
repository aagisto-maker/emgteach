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
    "ECG_PROFILE",
    "EMG_PROFILE",
    "PROFILES",
    "SignalProfile",
    "get_profile",
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
    apda_static_limit, apda_median_limit, apda_peak_limit : float
        Recommended maximum loads (% MVC) for the static / median / peak
        levels of Jonsson's APDF muscle-load analysis (see
        :mod:`emgteach.apda`).
    apda_mean_limit : float
        Guideline maximum for the average sustained activation (% MVC), used
        to flag the mean-activation readout.
    apda_warning_limit, apda_danger_limit : float
        Load thresholds (% MVC) for the online monitor's tiredness (warning)
        and fatigue (danger) zones.
    apda_calib_s : float
        Duration (s) of the quick in-app MVC calibration.
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

    # -- muscle-load analysis (Jonsson APDF recommended maxima, % MVC) --
    apda_static_limit: float = 5.0
    apda_median_limit: float = 14.0
    apda_peak_limit: float = 70.0
    # Guideline maximum for the average sustained activation (% MVC); used only
    # to flag the "mean activation" readout, not part of the APDF computation.
    apda_mean_limit: float = 10.0
    # Online (real-time) muscle-load monitoring during acquisition.
    # -- is this "maximum" a maximum? --
    # A calibration that barely rises above the muscle's own resting level did
    # not capture a maximal contraction, and every later % MVC is then wrong by
    # the same factor. Warn below this ratio of reference to resting level.
    mvc_min_rest_ratio: float = 5.0
    # The reference is the strongest window the subject actually held, not
    # an instantaneous peak. Anything compared against it has to be
    # measured the same way or the comparison inflates by itself.
    mvc_peak_window_s: float = 0.5
    # And after the fact, by definition: the reference IS the strongest half
    # second of a maximal effort, so if the task beats it the effort was not
    # maximal. What is compared is the task's own strongest half second,
    # measured the same way.
    #
    # The margin is not fitted, it sits in a gap. Across 21 bench recordings,
    # every session whose calibration was sound peaked at 91-124 % of its own
    # reference, and every session with a bad one peaked at 179-1308 %.
    # Nothing landed in between.
    mvc_implausible_pct: float = 150.0     # % MVC, on the peak
    # (A second condition — "and for more than 10 % of the analysed time" —
    # was removed. It is strictly stronger than the peak test at the same
    # threshold, so it never fired alone, and it silenced the cases that
    # matter most: a burst task with a three-fold submaximal calibration
    # spends only 3 % of its time up there. Six of the twenty-one recordings
    # were bad and quiet enough to slip through.)
    # -- are the two channels looking at two muscles? --
    # While one muscle is calibrated the other one is never silent: it stabilises
    # the joint, and some of its signal is the first muscle's, conducted through
    # the tissue. On the bench, with the electrodes correctly sited over FCR and
    # ECR, the resting channel reached 20-26 % of its own reference during the
    # other muscle's maximum. Above this share the two channels are no longer
    # telling two muscles apart — an electrode is mis-sited, too close to the
    # other pair, or the subject is bracing the whole forearm.
    mvc_crosstalk_pct: float = 50.0        # % of the other muscle's own reference
    # (A "was the effort held?" check lived here and was withdrawn. It
    # measured the share of the window above half the window's own peak,
    # which separated one bench session cleanly — and then fired on the
    # best calibration of the next one. A maximal contraction held for
    # four seconds decays, which that measure punishes exactly as it
    # punishes a brief movement; no threshold separated the two sessions
    # at any floor. A reference that is too low is still caught after the
    # fact by mvc_implausible_pct, which is where the evidence for it is.)

    # -- co-activation (Falconer-Winter) --
    # Below this mean activation the index measures the likeness of two
    # baselines rather than shared effort, so it is not reported at all.
    # Measured on a forearm pair with both references maximal: a quiet window
    # gave a mean of 0.2-0.8 % MVC above rest, an active one 19-30 %. The floor
    # sits in a gap of about thirtyfold, which is why a round number is enough.
    # (The muscles' own resting levels were 2 % MVC for the flexor and 4 % for
    # the extensor, which is what the subtraction removes before this test.)
    coact_floor_pct: float = 5.0       # % MVC
    apda_warning_limit: float = 40.0   # % MVC — tiredness (warning) zone
    apda_danger_limit: float = 70.0    # % MVC — fatigue (danger) zone
    apda_calib_s: float = 4.0          # s — quick MVC-calibration duration
    # -- the pause between the two phases of a session --
    # The acquisition does not stop: the file stays continuous and EDF+ never
    # has to represent a gap. These seconds are recorded, marked PREP, and
    # excluded from every analysis — a few kilobytes of disk against the whole
    # complexity of a discontinuous recording.
    prep_countdown_s: float = 5.0
    # -- warming up before the first maximal effort --
    # The first maximal contraction of a session is genuinely submaximal:
    # on the bench the three flexor repetitions came out 57 %, 68 % and
    # 100 % of each other, still rising at the third, so best-of-three had
    # nothing better to fall back on. Recorded and marked like the pause,
    # and out of the analysis for the same reason.
    warmup_s: float = 10.0

    # -- fatigue verdict (MDF-vs-time regression) --
    # The median frequency of a resting segment is amplifier noise, and mixing
    # those into the regression is what let an intermittent forearm recording
    # report a 26 % MDF decline. Only segments reaching this share of the
    # selection's own strong-segment RMS are fitted…
    fatigue_active_ratio: float = 0.30
    # …and the trend is only called a trend when the line explains this much of
    # the variance. That same recording, fitted through its active segments,
    # gave R² = 0.08.
    fatigue_min_r2: float = 0.30
    fatigue_min_segments: int = 4

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
        if not 0.0 < self.apda_static_limit <= self.apda_median_limit <= self.apda_peak_limit:
            raise ValueError(
                "Require 0 < apda_static_limit <= apda_median_limit <= "
                f"apda_peak_limit; got {self.apda_static_limit}, "
                f"{self.apda_median_limit}, {self.apda_peak_limit}."
            )
        if not 0.0 < self.apda_warning_limit <= self.apda_danger_limit:
            raise ValueError(
                "Require 0 < apda_warning_limit <= apda_danger_limit; got "
                f"{self.apda_warning_limit}, {self.apda_danger_limit}."
            )
        if self.apda_calib_s <= 0:
            raise ValueError("apda_calib_s must be positive.")

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

    def apda_kwargs(self) -> dict[str, float]:
        """APDF recommended maxima (% MVC) as kwargs for
        :func:`emgteach.apda.compute_apdf`."""
        return {
            "static_limit": self.apda_static_limit,
            "median_limit": self.apda_median_limit,
            "peak_limit": self.apda_peak_limit,
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
        self,
        sensor_labels: Sequence[str] | None = None,
        fs: int | None = None,
        physical_min: float | None = None,
        physical_max: float | None = None,
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
        # Fall back to the ChannelInfo defaults (BITalino-compatible ±3.3 mV)
        # when the caller does not pass a device-specific range.
        pmin = -3.3 if physical_min is None else float(physical_min)
        pmax = 3.3 if physical_max is None else float(physical_max)
        return [
            ChannelInfo(
                label,
                dimension=self.dimension,
                sample_frequency=sf,
                physical_min=pmin,
                physical_max=pmax,
            )
            for label in labels
        ]


#: Default profile for surface EMG. Reproduces the exact filter, analysis,
#: channel and display parameters that the package used before the Hito 1
#: refactor, so consuming it changes no behaviour.
EMG_PROFILE = SignalProfile(name="EMG")


#: Profile for single-lead ECG, added to demonstrate that a new biopotential
#: modality is a matter of instantiating :class:`SignalProfile` — no worker or
#: GUI code needs to change. The DSP band (0.5-40 Hz) is the standard
#: "monitoring" band that keeps the QRS/P/T morphology while removing baseline
#: wander and high-frequency muscle noise; the 50 Hz mains notch is shared with
#: EMG. The APDF/MVC fields are EMG-specific and left at their defaults (they
#: are simply unused for ECG). Display ranges reflect the ~1 mV ECG amplitude.
ECG_PROFILE = SignalProfile(
    name="ECG",
    f_low=0.5,
    f_high=40.0,
    f_notch=50.0,
    f_env=5.0,
    raw_label="ECG",
    dimension="mV",
    ylim_raw=(-2.0, 2.0),
    ylim_filtered=(-2.0, 2.0),
    ylim_envelope=(0.0, 2.0),
    marker_presets=(
        "P wave",
        "QRS complex",
        "T wave",
        "Arrhythmia",
        "Rest",
        "Other…",
    ),
)


#: Registry of the available signal profiles, keyed by their ``name``.
PROFILES: dict[str, SignalProfile] = {
    EMG_PROFILE.name: EMG_PROFILE,
    ECG_PROFILE.name: ECG_PROFILE,
}


def get_profile(name: str) -> SignalProfile:
    """Return the registered profile whose ``name`` matches (case-insensitive).

    Raises
    ------
    KeyError
        If no profile with that name is registered. The message lists the
        available names to help the caller.
    """
    for key, profile in PROFILES.items():
        if key.lower() == name.lower():
            return profile
    raise KeyError(
        f"Unknown signal profile {name!r}. Available: {sorted(PROFILES)}."
    )
