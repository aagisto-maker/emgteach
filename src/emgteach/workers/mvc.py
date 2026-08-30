"""Background worker for MVC (Maximum Voluntary Contraction) normalisation.

Loads one or two EDF files (the test signal and an optional MVC
reference), runs the same offline DSP pipeline as the analysis tab,
and normalises the test envelope against the MVC amplitude (95th
percentile by default).

The reference is looked for in three places, in this order:

1. a separate MVC recording, when one is chosen — an explicit decision by
   the operator, so it wins;
2. **the test file's own calibration**, written into the EDF as an
   annotation by the acquisition wizard. A session that calibrates with the
   recording already running carries its own maximum, and asking for a second
   file to say what the first one already knows was busywork that ended in a
   red "not a real %MVC" on a recording that had a perfectly real one;
3. the 95th percentile of the test signal itself — didactic
   auto-normalisation, flagged everywhere it appears because it is not %MVC.

The muscle-load (Jonsson APDF) analysis is about the *task*, so the worker
also accepts the fragments to keep: a recording that opens with three maximal
calibration efforts has an APDF describing those efforts, not the work.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal

from emgteach.apda import compute_apdf
from emgteach.dsp import detect_acquisition_problems, process_offline
from emgteach.i18n import tr
from emgteach.io import read_edf_pyedflib
from emgteach.mvc import (
    adaptive_ylim,
    compute_mvc,
    normalise_to_mvc,
    parse_mvc_ref_markers,
)
from emgteach.profiles import EMG_PROFILE, SignalProfile
from emgteach.selection import Segment, normalise_segments, total_duration_s


class MvcWorker(QThread):
    """QThread that produces an MVC-normalised view of an EMG recording.

    Signals
    -------
    result_ready : dict
        Carries every array and scalar needed by the MVC tab to draw
        its plots.
    log : str
        Status updates.
    error : str
        Emitted on any failure.
    """

    result_ready = Signal(dict)
    log = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        edf_path: str,
        mvc_path: str = "",
        f_low: float | None = None,
        f_high: float | None = None,
        f_notch: float | None = None,
        f_env: float | None = None,
        plot_duration_s: float = 10.0,
        mvc_percentile: float | None = None,
        channel_index: int = 0,
        profile: SignalProfile = EMG_PROFILE,
        roi_segments: list[tuple[float, float]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._edf_path = edf_path
        self._mvc_path = mvc_path.strip()
        self._channel_index = int(channel_index)
        self._roi_segments = (
            [(float(a), float(b)) for a, b in roi_segments] if roi_segments else None
        )
        self._f_low = float(f_low) if f_low is not None else profile.f_low
        self._f_high = float(f_high) if f_high is not None else profile.f_high
        self._f_notch = float(f_notch) if f_notch is not None else profile.f_notch
        self._f_env = float(f_env) if f_env is not None else profile.f_env
        self._plot_duration_s = float(plot_duration_s)
        self._percentile = (
            float(mvc_percentile) if mvc_percentile is not None else profile.mvc_percentile
        )
        self._cancelled = False

    def stop(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """``True`` once :meth:`stop` has been called."""
        return self._cancelled

    def _recortar(self, emg_raw, fs: float, time_axis):
        """Keep the selected fragments only, concatenated and re-based to 0.

        Returns ``(None, None)`` after emitting :attr:`error` when the kept
        time falls below the 1 s the DSP pipeline needs. Same rule and the same
        wording as the analysis tab, because it is the same decision.
        """
        if not self._roi_segments:
            return emg_raw, time_axis

        duracion = float(time_axis[-1]) if time_axis.size else 0.0
        segs = normalise_segments(
            [Segment(a, b) for a, b in self._roi_segments], duracion
        )
        total = total_duration_s(segs)
        if not segs or total < 1.0:
            self.error.emit(
                tr(
                    "The selected fragments total {t:.2f} s, below the 1 s "
                    "minimum required for analysis."
                ).format(t=total)
            )
            return None, None

        trozos = []
        for s in segs:
            i0 = max(0, min(round(s.start_s * fs), emg_raw.size))
            i1 = max(i0, min(round(s.end_s * fs), emg_raw.size))
            if i1 > i0:
                trozos.append(emg_raw[i0:i1])
        recortado = np.concatenate(trozos)
        self.log.emit(
            tr(
                "Muscle load computed over {n} selected fragment(s) "
                "({d:.2f} s of {full:.2f} s)."
            ).format(n=len(segs), d=total, full=duracion)
        )
        return recortado, np.arange(recortado.size, dtype=np.float64) / fs

    def run(self) -> None:
        try:
            # 1) Load test EDF
            self.log.emit(tr("Loading EMG signal: {path}").format(path=self._edf_path))
            edf = read_edf_pyedflib(self._edf_path, self._channel_index)
            emg_raw = edf["emg_raw"]
            fs = edf["sfreq"]
            dimension = edf["dimension"]
            time_axis = edf["tiempo"]
            # Read before any trimming: the calibration is normally *outside*
            # the fragments kept for the muscle-load analysis — that is the
            # whole point of trimming — and it is still this muscle's maximum.
            ref_en_fichero = parse_mvc_ref_markers(edf.get("markers", [])).get(
                self._channel_index
            )

            self.log.emit(
                tr("Signal loaded — {fs:.0f} Hz — {dur:.1f} s — units: {units}").format(
                    fs=fs, dur=time_axis[-1], units=dimension
                )
            )

            # Keep only the selected fragments, concatenated into one signal.
            emg_raw, time_axis = self._recortar(emg_raw, fs, time_axis)
            if emg_raw is None:
                return  # error already emitted

            n_plot = (
                int(self._plot_duration_s * fs)
                if self._plot_duration_s > 0
                else len(emg_raw)
            )
            n_plot = min(n_plot, len(emg_raw))
            t_plot = time_axis[:n_plot]

            # 2) Diagnostics
            diag = detect_acquisition_problems(emg_raw, fs)
            for warning in diag["warnings"]:
                self.log.emit(warning)

            # 3) Process test signal
            self.log.emit(tr("Processing test signal (notch → band-pass → envelope)…"))
            proc = process_offline(
                emg_raw,
                fs,
                f_low=self._f_low,
                f_high=self._f_high,
                f_notch=self._f_notch,
                f_env=self._f_env,
            )
            emg_envelope = proc["emg_envelope"]
            if self._cancelled:
                return

            # 4) MVC reference
            mvc_amplitude_ref: float
            mvc_source: str
            # Whether the reference is the test signal itself. Reported as a
            # flag rather than inferred from mvc_source, which is translated:
            # the interface has to mark these results and must not depend on
            # the wording of a particular language.
            mvc_is_auto: bool = True

            if self._mvc_path:
                try:
                    self.log.emit(tr("Loading MVC file: {path}").format(path=self._mvc_path))
                    mvc_edf = read_edf_pyedflib(self._mvc_path, self._channel_index)
                    mvc_fs = mvc_edf["sfreq"]

                    diag_mvc = detect_acquisition_problems(mvc_edf["emg_raw"], mvc_fs)
                    for warning in diag_mvc["warnings"]:
                        self.log.emit(warning)

                    self.log.emit(tr("Processing MVC signal…"))
                    mvc_proc = process_offline(
                        mvc_edf["emg_raw"],
                        mvc_fs,
                        f_low=self._f_low,
                        f_high=self._f_high,
                        f_notch=self._f_notch,
                        f_env=self._f_env,
                    )
                    mvc_amplitude_ref = compute_mvc(
                        mvc_proc["emg_envelope"], self._percentile
                    )
                    mvc_source = tr(
                        "external MVC file (percentile {p:.0f})"
                    ).format(p=self._percentile)
                    mvc_is_auto = False
                except Exception as exc:
                    self.log.emit(
                        tr(
                            "Could not load the MVC file ({error}). "
                            "Falling back to auto-normalisation."
                        ).format(error=exc)
                    )
                    mvc_amplitude_ref = compute_mvc(emg_envelope, self._percentile)
                    mvc_source = tr(
                        "auto (percentile {p:.0f} of the test signal)"
                    ).format(p=self._percentile)
            elif ref_en_fichero:
                # The session calibrated with the recording already running, so
                # the maximum is an annotation inside this very file. Nothing
                # else to choose, and nothing auto about it.
                mvc_amplitude_ref = float(ref_en_fichero)
                mvc_source = tr("calibration recorded in this file")
                mvc_is_auto = False
                self.log.emit(
                    tr(
                        "MVC reference read from the file's own calibration: "
                        "{value:.4f} {units}."
                    ).format(value=mvc_amplitude_ref, units=dimension)
                )
            else:
                mvc_amplitude_ref = compute_mvc(emg_envelope, self._percentile)
                mvc_source = tr(
                    "auto (percentile {p:.0f} of the test signal)"
                ).format(p=self._percentile)

            self.log.emit(
                tr("MVC reference amplitude: {value:.4f} {units} ({source})").format(
                    value=mvc_amplitude_ref, units=dimension, source=mvc_source
                )
            )
            if self._cancelled:
                return

            # 5) Normalise
            emg_norm = normalise_to_mvc(emg_envelope, mvc_amplitude_ref)
            ylim_max = adaptive_ylim(emg_norm, n_plot)

            mean_norm = float(np.mean(emg_norm))
            self.log.emit(
                tr("Mean normalised activation: {value:.1f} % MVC").format(value=mean_norm)
            )

            # Muscle-load analysis (Jonsson APDF) over the whole recording.
            apdf = compute_apdf(emg_norm, **self._profile.apda_kwargs())
            self.log.emit(
                tr(
                    "Muscle load (Jonsson) — static {st:.1f} %, "
                    "median {md:.1f} %, peak {pk:.1f} % MVC"
                ).format(
                    st=apdf.static.value, md=apdf.median.value, pk=apdf.peak.value
                )
            )

            result = {
                "emg_raw": emg_raw,
                "emg_filtered": proc["emg_filtered"],
                "emg_rectified": proc["emg_rectified"],
                "emg_envelope": emg_envelope,
                "emg_norm": emg_norm,
                "mean_norm": mean_norm,
                "apdf": apdf,
                "t_plot": t_plot,
                "n_plot": n_plot,
                "tiempo": time_axis,
                "mvc_amplitude_ref": mvc_amplitude_ref,
                "mvc_source": mvc_source,
                "mvc_is_auto": mvc_is_auto,
                "ylim_max": ylim_max,
                "dimension": dimension,
                "fs": fs,
                "f_high": self._f_high,
                "edf_path": self._edf_path,
            }

            self.result_ready.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))
