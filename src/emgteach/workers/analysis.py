"""Background worker for full offline EMG analysis.

Runs the seven-panel analysis pipeline in a QThread so the GUI stays
responsive while a long EDF file is being processed. The result is
emitted as a single dictionary that the analysis tab consumes to draw
all plots.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal
from scipy.integrate import trapezoid

from emgteach.coactivation import coactivation_by_window
from emgteach.dsp import (
    compute_psd_mnf_mdf,
    compute_segments,
    detect_acquisition_problems,
    detect_onsets,
    process_offline,
)
from emgteach.fatigue import (
    FATIGUE,
    NO_FATIGUE,
    active_segments,
    fatigue_verdict,
    fit_mdf_vs_time,
    fit_rms_vs_mdf,
)
from emgteach.force_velocity import parse_fv_load_markers
from emgteach.i18n import tr
from emgteach.io import (
    list_edf_channels,
    list_edf_emg_channels,
    read_edf_mne,
    read_edf_pyedflib,
)
from emgteach.mvc import parse_mvc_ref_markers
from emgteach.profiles import EMG_PROFILE, SignalProfile
from emgteach.selection import Segment, normalise_segments, total_duration_s


def _contracted(envelope, fs: float, profile) -> bool:
    """Did this muscle actually contract, by the application's own definition?

    Reported so the event log can say when a channel never left its baseline —
    a muscle that stayed silent is a finding, and one worth naming rather than
    leaving the reader to infer from a flat line.

    The test is the app's own onset detector rather than a threshold invented
    here, so "a contraction happened" means the same thing everywhere in the
    program.
    """
    try:
        return bool(detect_onsets(
            envelope, fs,
            k=profile.onset_k,
            baseline_s=profile.onset_baseline_s,
            refractory_s=profile.onset_refractory_s,
            min_duration_s=profile.onset_min_duration_s,
        ))
    except Exception:      # a span too short to hold a baseline
        return False


def _sustained(envelope, fs: float, window_s: float):
    """The envelope as a running mean over ``window_s`` seconds.

    The MVC reference is the strongest window of that length the subject
    actually held (:func:`emgteach.mvc.mvc_peak_hold`). Comparing an
    instantaneous envelope against it inflates the ratio for free, so anything
    that judges a recording against the reference smooths the same way first.
    """
    env = np.asarray(envelope, dtype=np.float64)
    w = max(1, round(window_s * fs))
    if env.size < w:
        return env
    csum = np.cumsum(np.insert(env, 0, 0.0))
    return (csum[w:] - csum[:-w]) / w


def _baseline_is_usable(envelope, fs: float, profile) -> bool:
    """Could a resting baseline be measured at all?

    The onset detector takes its baseline from the opening second, so a
    recording that starts with the muscle already working has no baseline to
    take: the threshold comes out above everything that follows and nothing is
    ever detected. That looks identical to a muscle that stayed silent, and
    saying so would be a false statement about the subject rather than about
    the recording — so the two are told apart here.

    The test is self-evident: a threshold higher than the recording's own
    maximum cannot be a resting threshold.
    """
    env = np.asarray(envelope, dtype=np.float64)
    n_base = int(profile.onset_baseline_s * fs)
    if env.size < n_base + 2 or n_base < 2:
        return False
    base = env[:n_base]
    umbral = float(np.mean(base) + profile.onset_k * np.std(base))
    return umbral < float(np.max(env))


def _ref_for(channel_name, emg_channels, refs):
    """The MVC reference belonging to a channel, or None.

    The wizard numbers muscles by their position among the recording's EMG
    channels — which is the order they were labelled in — so that position is
    what maps a channel name back to its annotation.
    """
    if not channel_name or not refs:
        return None
    try:
        return refs.get(list(emg_channels).index(channel_name))
    except ValueError:
        return None


class AnalysisWorker(QThread):
    """QThread that runs :func:`process_offline` plus spectral and fatigue fits.

    Signals
    -------
    result_ready : dict
        Carries the full result for every panel of the analysis tab.
    progress : int
        0..100 progress percentage for a progress bar.
    log : str
        Human-readable status updates.
    error : str
        Emitted on any failure during loading or processing.
    """

    result_ready = Signal(dict)
    progress = Signal(int)
    log = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        edf_path: str,
        channel_name: str | None = None,
        channel_name_2: str | None = None,
        acc_channel: str | None = None,
        acc_placement: str = "unknown",
        f_low: float | None = None,
        f_high: float | None = None,
        f_notch: float | None = None,
        f_env: float | None = None,
        rms_window_ms: float | None = None,
        seg_len_s: float | None = None,
        overlap: float | None = None,
        plot_duration_s: float = 10.0,
        roi_start_s: float | None = None,
        roi_end_s: float | None = None,
        roi_segments: list[tuple[float, float]] | None = None,
        profile: SignalProfile = EMG_PROFILE,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._edf_path = edf_path
        self._roi_start_s = float(roi_start_s) if roi_start_s is not None else None
        self._roi_end_s = float(roi_end_s) if roi_end_s is not None else None
        # Optional multi-fragment selection. When given (and non-empty) it takes
        # precedence over the single roi_start/roi_end window: the kept fragments
        # are concatenated and analysed as one continuous signal.
        self._roi_segments = (
            [(float(a), float(b)) for a, b in roi_segments] if roi_segments else None
        )
        self._channel_name = (
            channel_name if channel_name is not None else profile.raw_label
        )
        # Optional second channel: its envelope is overlaid (agonist/antagonist).
        self._channel_name_2 = channel_name_2
        # Optional accelerometer channel: enables the MMG and tremor panels.
        self._acc_channel = acc_channel
        self._acc_placement = acc_placement
        self._f_low = float(f_low) if f_low is not None else profile.f_low
        self._f_high = float(f_high) if f_high is not None else profile.f_high
        self._f_notch = float(f_notch) if f_notch is not None else profile.f_notch
        self._f_env = float(f_env) if f_env is not None else profile.f_env
        self._rms_window_ms = (
            float(rms_window_ms) if rms_window_ms is not None else profile.rms_window_ms
        )
        self._seg_len_s = float(seg_len_s) if seg_len_s is not None else profile.seg_len_s
        self._overlap = float(overlap) if overlap is not None else profile.overlap
        self._plot_duration_s = float(plot_duration_s)
        self._cancelled = False

    def stop(self) -> None:
        """Request that the next checkpoint abandon the run."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """``True`` once :meth:`stop` has been called."""
        return self._cancelled

    def _resolve_roi(
        self, n_samples: int, fs: float, full_duration: float
    ) -> tuple[int, int, float, float] | None:
        """Clamp and validate the requested region of interest.

        Returns ``(i0, i1, start_s, end_s)`` sample bounds and their times,
        or ``None`` (after emitting :attr:`error`) if the window is invalid.
        When no ROI is requested the full recording ``(0, n_samples, ...)``
        is returned. The analysis needs enough samples for the pipeline's
        500 ms reflective padding, so a window shorter than 1 s is rejected.
        """
        start_s = 0.0 if self._roi_start_s is None else max(0.0, self._roi_start_s)
        end_s = full_duration if self._roi_end_s is None else self._roi_end_s
        end_s = min(end_s, full_duration)
        if end_s - start_s < 1.0:
            self.error.emit(
                tr(
                    "The selected region ({a:.2f}-{b:.2f} s) is shorter than "
                    "the 1 s minimum required for analysis."
                ).format(a=start_s, b=end_s)
            )
            return None
        i0 = round(start_s * fs)
        i1 = round(end_s * fs)
        i0 = max(0, min(i0, n_samples))
        i1 = max(i0, min(i1, n_samples))
        return i0, i1, start_s, end_s

    def _resolve_segments(
        self, n_samples: int, fs: float, full_duration: float
    ) -> list[tuple[int, int, float, float]] | None:
        """Resolve the analysis fragments into ordered sample-index windows.

        Precedence: an explicit multi-fragment ``roi_segments`` list, else the
        single ``roi_start_s``/``roi_end_s`` window, else the whole recording.
        The fragments are clamped to the recording, ordered and merged if they
        overlap. The total kept time must be at least 1 s (the pipeline's
        reflective-padding minimum); otherwise :attr:`error` is emitted and
        ``None`` is returned.

        Returns ``[(i0, i1, start_s, end_s), ...]`` in chronological order.
        """
        if self._roi_segments:
            requested = self._roi_segments
        elif self._roi_start_s is not None or self._roi_end_s is not None:
            start = self._roi_start_s if self._roi_start_s is not None else 0.0
            end = self._roi_end_s if self._roi_end_s is not None else full_duration
            requested = [(start, end)]
        else:
            return [(0, n_samples, 0.0, full_duration)]

        segs = normalise_segments(
            [Segment(a, b) for a, b in requested], full_duration
        )
        total = total_duration_s(segs)
        if not segs or total < 1.0:
            self.error.emit(
                tr(
                    "The selected fragments total {t:.2f} s, below the 1 s "
                    "minimum required for analysis."
                ).format(t=total)
            )
            return None

        bounds: list[tuple[int, int, float, float]] = []
        for s in segs:
            i0 = max(0, min(round(s.start_s * fs), n_samples))
            i1 = max(i0, min(round(s.end_s * fs), n_samples))
            if i1 > i0:
                bounds.append((i0, i1, s.start_s, s.end_s))
        return bounds

    def run(self) -> None:
        try:
            # 1) Load EDF
            self.log.emit(tr("Loading file: {path}").format(path=self._edf_path))
            self.progress.emit(5)
            edf = read_edf_mne(self._edf_path, self._channel_name)
            emg_raw = edf["emg_raw"]
            fs = edf["sfreq"]
            times = edf["times"]
            markers = edf.get("markers", [])
            # Read before any fragment trimming: a calibration made
            # outside the analysed span is still this muscle's
            # maximum, and dropping it would send the panel back to
            # millivolts for no good reason.
            mvc_refs = parse_mvc_ref_markers(markers)
            # The MVC references and the force-velocity loads are facts about
            # the session, not phases of it. Once read they are dropped, so
            # they neither clutter every panel with a marker line nor open a
            # window in the co-activation table — the student's own marks are
            # what divide a recording into phases.
            markers = [
                m for m in markers
                if not parse_mvc_ref_markers([m])
                and not parse_fv_load_markers([m])
            ]
            try:
                emg_channels = list_edf_emg_channels(self._edf_path)
            except Exception:
                emg_channels = []

            # 1b) Restrict to the selected fragment(s), if requested. The kept
            # fragments are concatenated into one continuous signal; everything
            # downstream (DSP, PSD, segments, fatigue) runs on it, time is
            # re-based to 0 and markers are shifted into concatenated time (those
            # in discarded fragments are dropped). The kept windows are recorded
            # in the result so the report states them explicitly.
            full_duration = float(times[-1])
            bounds = self._resolve_segments(len(emg_raw), fs, full_duration)
            if bounds is None:
                return  # error already emitted
            kept_segments = [(s, e) for (_, _, s, e) in bounds]
            is_whole = (
                len(bounds) == 1
                and bounds[0][0] == 0
                and bounds[0][1] == len(emg_raw)
            )
            if not is_whole:
                emg_raw = np.concatenate([emg_raw[i0:i1] for (i0, i1, _, _) in bounds])
                times = np.arange(len(emg_raw), dtype=np.float64) / fs
                new_markers: list[tuple[float, str]] = []
                offset = 0.0
                for i0, i1, seg_a, seg_b in bounds:
                    for t, label in markers:
                        if seg_a <= t < seg_b:
                            new_markers.append((offset + (t - seg_a), label))
                    offset += (i1 - i0) / fs
                markers = sorted(new_markers)
                if len(bounds) == 1:
                    self.log.emit(
                        tr("Region of interest: {a:.2f}-{b:.2f} s ({d:.2f} s).").format(
                            a=kept_segments[0][0],
                            b=kept_segments[0][1],
                            d=kept_segments[0][1] - kept_segments[0][0],
                        )
                    )
                else:
                    kept_total = sum(b - a for a, b in kept_segments)
                    self.log.emit(
                        tr(
                            "Analysing {n} selected fragments "
                            "({d:.2f} s of {full:.2f} s)."
                        ).format(n=len(bounds), d=kept_total, full=full_duration)
                    )

            roi_start_s = kept_segments[0][0]
            roi_end_s = kept_segments[-1][1]
            duration = float(times[-1])
            self.log.emit(
                tr("Channel «{name}» — {fs:.0f} Hz — {dur:.1f} s").format(
                    name=self._channel_name, fs=fs, dur=duration
                )
            )
            self.progress.emit(15)

            # 2) Acquisition diagnostics on the raw signal
            diag = detect_acquisition_problems(emg_raw, fs)
            for warning in diag["warnings"]:
                self.log.emit(warning)

            n_plot = (
                int(self._plot_duration_s * fs)
                if self._plot_duration_s > 0
                else len(emg_raw)
            )
            n_plot = min(n_plot, len(emg_raw))
            t_plot = times[:n_plot]

            # 3) Full DSP pipeline
            self.log.emit(tr("Applying the processing pipeline (DSP)…"))
            proc = process_offline(
                emg_raw,
                fs,
                f_low=self._f_low,
                f_high=self._f_high,
                f_notch=self._f_notch,
                f_env=self._f_env,
                rms_window_ms=self._rms_window_ms,
            )
            self.progress.emit(45)
            if self._cancelled:
                return

            # 4) Spectral analysis
            self.log.emit(tr("Computing PSD, MNF and MDF…"))
            psd_result = compute_psd_mnf_mdf(
                proc["emg_filtered"], fs, f_low=self._f_low, f_high=self._f_high
            )
            self.log.emit(
                f"MNF = {psd_result['mnf']:.1f} Hz   "
                f"MDF = {psd_result['mdf']:.1f} Hz"
            )
            self.progress.emit(60)
            if self._cancelled:
                return

            # 5) Segment-wise RMS and MDF
            self.log.emit(tr("Computing segment-wise RMS and MDF…"))
            segs = compute_segments(
                proc["emg_filtered"],
                fs,
                seg_len_s=self._seg_len_s,
                overlap=self._overlap,
            )
            self.progress.emit(75)
            if self._cancelled:
                return

            # 6) Fatigue fit: linear MDF-vs-time regression (primary index).
            # Fitted over the segments where the muscle was working, not over
            # the whole selection: the median frequency of a resting segment is
            # the median frequency of the amplifier, and mixing the two
            # populations manufactures a slope out of nothing. The curves are
            # still drawn across every segment.
            self.log.emit(tr("Fitting MDF-vs-time regression…"))
            activos = active_segments(
                segs["rms_seg"], self._profile.fatigue_active_ratio
            )
            n_activos = int(np.count_nonzero(activos))
            if n_activos < activos.size:
                self.log.emit(
                    tr(
                        "MDF trend fitted over {n} of {total} segments "
                        "(the rest were below the contraction threshold)."
                    ).format(n=n_activos, total=int(activos.size))
                )
            fat_time = fit_mdf_vs_time(
                segs["t_seg"][activos], segs["mdf_seg"][activos],
                t_eval=segs["t_seg"],
            )
            fat_rms = fit_rms_vs_mdf(
                segs["mdf_seg"][activos], segs["rms_seg"][activos]
            )
            verdict = fatigue_verdict(
                fat_time["slope_sign"], fat_time["r_squared"], n_activos,
                min_r2=self._profile.fatigue_min_r2,
                min_segments=self._profile.fatigue_min_segments,
            )

            if verdict == FATIGUE:
                self.log.emit(
                    tr(
                        "Fatigue trend: MDF slope {slope:.3f} Hz/s "
                        "({decline:.1f}% decline, R²={r2:.2f})."
                    ).format(
                        slope=fat_time["slope"],
                        decline=fat_time["pct_decline"],
                        r2=fat_time["r_squared"],
                    )
                )
            elif verdict == NO_FATIGUE:
                self.log.emit(
                    tr(
                        "No fatigue: MDF slope {slope:+.3f} Hz/s "
                        "(R²={r2:.2f})."
                    ).format(slope=fat_time["slope"], r2=fat_time["r_squared"])
                )
            else:
                # Not "no fatigue": the recording does not answer the question.
                # Saying so is the whole point — a line drawn through a cloud
                # of resting segments used to come out as a red verdict.
                self.log.emit(
                    tr(
                        "MDF trend not conclusive: slope {slope:+.3f} Hz/s but "
                        "R²={r2:.2f} over {n} segment(s). Fatigue needs a "
                        "contraction held long enough for the trend to show."
                    ).format(
                        slope=fat_time["slope"], r2=fat_time["r_squared"],
                        n=n_activos,
                    )
                )
            self.progress.emit(90)

            # 7) Pack result
            rms_global = float(np.sqrt(np.mean(proc["emg_filtered"] ** 2)))
            iemg = float(trapezoid(proc["emg_rectified"], dx=1.0 / fs))
            # Primary fatigue index: slope of the linear MDF-vs-time regression.
            mdf_slope = float(fat_time["slope"])

            result = {
                # time-domain arrays (full length)
                "emg_raw": emg_raw,
                "emg_filtered": proc["emg_filtered"],
                "emg_rectified": proc["emg_rectified"],
                "emg_envelope": proc["emg_envelope"],
                "rms_sliding": proc["rms_sliding"],
                "emg_envelope_normalised": proc["emg_envelope_normalised"],
                "emg_contracted": _contracted(
                    proc["emg_envelope"], fs, self._profile),
                "emg_baseline_usable": _baseline_is_usable(
                    proc["emg_envelope"], fs, self._profile),
                # {channel_index_0based: reference_mV}; empty when the
                # recording carries no calibration.
                "mvc_refs": mvc_refs,
                "mvc_ref": _ref_for(self._channel_name, emg_channels, mvc_refs),
                # plot axis
                "t_plot": t_plot,
                "n_plot": n_plot,
                "times": times,
                # spectral
                "frequencies": psd_result["frequencies"],
                "psd": psd_result["psd"],
                "mnf": psd_result["mnf"],
                "mdf": psd_result["mdf"],
                # segments
                "t_seg": segs["t_seg"],
                "rms_seg": segs["rms_seg"],
                "mdf_seg": segs["mdf_seg"],
                # fatigue fits
                "fat_fitted": fat_time["fitted"],
                "fat_linear_fitted": fat_time["linear_fitted"],
                "fat_slope_sign": fat_time["slope_sign"],
                "fat_r_squared": fat_time["r_squared"],
                "fat_pct_decline": fat_time["pct_decline"],
                "fat_verdict": verdict,
                "fat_n_seg": n_activos,
                "fat_slope_per_min": fat_time["slope_per_min"],
                "rms_mdf_range": fat_rms["mdf_range"],
                "rms_mdf_fitted": fat_rms["fitted"],
                # summary metrics
                "rms_global": rms_global,
                "duration": duration,
                "mdf_slope": mdf_slope,
                "iemg": iemg,
                # metadata
                "fs": fs,
                "f_high": self._f_high,
                "roi_start_s": roi_start_s,
                "roi_end_s": roi_end_s,
                "roi_segments": kept_segments,
                "full_duration_s": full_duration,
                "edf_path": self._edf_path,
                "channel_name": self._channel_name,
                "markers": markers,
                # DSP/analysis parameters actually used, so a report can show
                # the "configuration used" without re-deriving it.
                "config": {
                    "f_low": self._f_low,
                    "f_high": self._f_high,
                    "f_notch": self._f_notch,
                    "f_env": self._f_env,
                    "rms_window_ms": self._rms_window_ms,
                    "seg_len_s": self._seg_len_s,
                    "overlap": self._overlap,
                },
            }

            # Optional second channel: its envelope is overlaid with the first
            # (agonist/antagonist). Same file, so it reuses the fragment bounds;
            # a failure here only drops the overlay, it never fails the run.
            if self._channel_name_2 and self._channel_name_2 != self._channel_name:
                try:
                    edf2 = read_edf_mne(self._edf_path, self._channel_name_2)
                    emg_raw_2 = edf2["emg_raw"]
                    if not is_whole:
                        emg_raw_2 = np.concatenate(
                            [emg_raw_2[i0:i1] for (i0, i1, _, _) in bounds]
                        )
                    proc2 = process_offline(
                        emg_raw_2, fs,
                        f_low=self._f_low, f_high=self._f_high,
                        f_notch=self._f_notch, f_env=self._f_env,
                        rms_window_ms=self._rms_window_ms,
                    )
                    # The raw trace of the second muscle, not just its
                    # envelope: the agonist/antagonist practical shows one raw
                    # panel per muscle before overlaying the two envelopes.
                    result["emg_raw_2"] = emg_raw_2
                    result["emg_envelope_2"] = proc2["emg_envelope"]
                    result["emg_envelope_normalised_2"] = (
                        proc2["emg_envelope_normalised"]
                    )
                    result["emg_contracted_2"] = _contracted(
                        proc2["emg_envelope"], fs, self._profile
                    )
                    result["mvc_ref_2"] = _ref_for(
                        self._channel_name_2, emg_channels, mvc_refs
                    )
                    # Co-activation needs both envelopes as a percentage of
                    # *their own* muscle's maximum; without a reference for
                    # each, the pair cannot be compared at all and no index is
                    # computed rather than one being computed on millivolts.
                    ref1, ref2 = result.get("mvc_ref"), result["mvc_ref_2"]
                    if ref1 and ref2:
                        # Automatic onset markers are events the program found,
                        # not phases the operator declared. Left in, a recording
                        # with auto-onset on produces one table row per burst —
                        # dozens of them — and each row looks like a result.
                        fases = [
                            m for m in markers if "(auto)" not in str(m[1])
                        ]
                        table, from_marks = coactivation_by_window(
                            proc["emg_envelope"] / float(ref1) * 100.0,
                            proc2["emg_envelope"] / float(ref2) * 100.0,
                            fs, fases,
                            floor_pct=self._profile.coact_floor_pct,
                            t0=float(times[0]) if len(times) else 0.0,
                            name_1=self._channel_name or "",
                            name_2=self._channel_name_2 or "",
                        )
                        result["coactivation"] = table
                        result["coactivation_from_markers"] = from_marks

                    # A reference that was never a maximum shows up as a
                    # recording that spends much of its time above 100 % MVC.
                    # Worth saying wherever the file is opened, including the
                    # ones already on disk.
                    for ref, env, name in (
                        (ref1, proc["emg_envelope"], self._channel_name),
                        (ref2, proc2["emg_envelope"], self._channel_name_2),
                    ):
                        if not ref:
                            continue
                        # Like with like: the reference is the strongest
                        # 0.5 s the subject held, so what is compared against
                        # it is the same running mean and not the
                        # instantaneous envelope. On the bench recording that
                        # difference alone accounted for a peak of 384 % where
                        # the honest figure was 234 %.
                        pct = _sustained(
                            env, fs, self._profile.mvc_peak_window_s
                        ) / float(ref) * 100.0
                        share = float(np.mean(
                            pct > self._profile.mvc_implausible_pct))
                        if share > self._profile.mvc_implausible_share:
                            result["mvc_implausible"] = max(
                                share, result.get("mvc_implausible", 0.0))
                            self.log.emit(tr(
                                "⚠ «{name}» is above {limit:.0f} % MVC for "
                                "{share:.0f} % of the recording, peaking at "
                                "{peak:.0f} %. The calibration did not capture a "
                                "maximum, so every percentage here is too high."
                            ).format(name=name,
                                     limit=self._profile.mvc_implausible_pct,
                                     share=share * 100.0, peak=float(pct.max())))
                    else:
                        result["coactivation_reason"] = tr(
                            "not reported — no MVC reference for both channels"
                        )
                    result["emg_baseline_usable_2"] = _baseline_is_usable(
                        proc2["emg_envelope"], fs, self._profile
                    )
                    for usable, contracted, name in (
                        (result["emg_baseline_usable"],
                         result["emg_contracted"], self._channel_name),
                        (result["emg_baseline_usable_2"],
                         result["emg_contracted_2"], self._channel_name_2),
                    ):
                        if not usable:
                            self.log.emit(tr(
                                "⚠ «{name}»: the recording starts with the "
                                "muscle already active, so no resting baseline "
                                "could be measured and contraction onsets were "
                                "not detected. Record a couple of quiet seconds "
                                "before the first contraction."
                            ).format(name=name))
                        elif not contracted:
                            self.log.emit(tr(
                                "No contraction detected in «{name}»: it never "
                                "left its baseline."
                            ).format(name=name))
                    result["channel_name_2"] = self._channel_name_2
                    self.log.emit(
                        tr("2nd channel «{name}» overlaid.").format(
                            name=self._channel_name_2
                        )
                    )
                except Exception as exc:
                    self.log.emit(
                        tr("Could not analyse the 2nd channel «{name}»: {err}")
                        .format(name=self._channel_name_2, err=exc)
                    )

            # Optional accelerometer channel: the MMG (mechanical) envelope and
            # the tremor spectrum. A failure only drops the ACC panels.
            if self._acc_channel:
                try:
                    from emgteach.dsp import (
                        mmg_envelope,
                        movement_envelope,
                        tremor_spectrum,
                    )

                    # The accelerometer is in g, not mV: read it with pyedflib
                    # (physical units as-is) rather than read_edf_mne, which
                    # multiplies by 1000 to turn MNE's volts back into mV.
                    acc_idx = list_edf_channels(self._edf_path).index(
                        self._acc_channel
                    )
                    acc_raw = read_edf_pyedflib(
                        self._edf_path, channel_index=acc_idx
                    )["emg_raw"]
                    if not is_whole:
                        acc_raw = np.concatenate(
                            [acc_raw[i0:i1] for (i0, i1, _, _) in bounds]
                        )
                    mmg_env = mmg_envelope(acc_raw, fs)
                    move_env = movement_envelope(acc_raw, fs)
                    tf, tpsd, tpeak = tremor_spectrum(acc_raw, fs)
                    result["acc_raw"] = acc_raw
                    result["acc_mmg_envelope"] = mmg_env
                    result["acc_mmg_rms"] = float(np.sqrt(np.mean(mmg_env ** 2)))
                    result["acc_movement_envelope"] = move_env
                    result["acc_tremor_freqs"] = tf
                    result["acc_tremor_psd"] = tpsd
                    result["acc_tremor_peak_hz"] = tpeak
                    result["acc_channel_name"] = self._acc_channel
                    result["acc_placement"] = self._acc_placement
                    self.log.emit(
                        tr("Accelerometer «{name}» — tremor peak {hz:.1f} Hz.")
                        .format(name=self._acc_channel, hz=tpeak)
                    )
                except Exception as exc:
                    self.log.emit(
                        tr("Could not analyse the accelerometer «{name}»: {err}")
                        .format(name=self._acc_channel, err=exc)
                    )

            self.progress.emit(100)
            self.result_ready.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))
