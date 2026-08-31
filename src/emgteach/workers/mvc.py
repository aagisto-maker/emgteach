"""Background worker for MVC (Maximum Voluntary Contraction) normalisation.

Loads one EDF — the session — runs the same offline DSP pipeline as the
analysis tab, and expresses its envelope as a percentage of the maximum the
subject actually produced.

**One file, and the reference comes out of it.** The session marks its own
calibration (:mod:`emgteach.phases`), so the reference is recomputed from
those spans; a recording made before that flow falls back to the cached
``MVC ref`` annotation. Nothing is asked of the operator, and there is no
third place to look.

There used to be two more routes and both are gone:

* **A separate reference recording, chosen by hand.** It answered a question
  the file already answers, and it made the two tabs disagree — the analysis
  recomputing from the spans while this one used whatever file was in the
  box.
* **Auto-normalisation against the test signal itself.** Dividing a recording
  by its own 95th percentile always yields something near 100 %, so the
  Jonsson limits then say the subject is overloaded whatever they did. It was
  labelled rather than removed, in red, everywhere it appeared; a failure mode
  that has to be sign-posted in five places is a failure mode to delete. Note
  what is *not* removed: panel 2's "normalised to its own maximum" is the same
  arithmetic under an honest name, and for the time course of one channel it
  is correct. What goes is its use as a **reference for muscle load**.

Without a calibration, then, there is no % MVC and no APDF — and the signal
and its envelope are still drawn, because those do not depend on a reference.

The muscle-load analysis is about the *task*, so the analysed span defaults to
the session's ``REC`` phase: a recording that opens with three maximal
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
    normalise_to_mvc,
    parse_mvc_ref_markers,
)
from emgteach.phases import (
    mvc_reference,
    parse_phase_markers,
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

    def _recortar(self, emg_raw, fs: float, time_axis, *, por_defecto=None):
        """Keep the selected fragments only, concatenated and re-based to 0.

        ``por_defecto`` is the span to use when nothing was chosen — the
        session's recording phase. Falling back to the whole file is right only
        for a recording that has no phases marked, which is every file made
        before the guided flow.

        Returns ``(None, None)`` after emitting :attr:`error` when the kept
        time falls below the 1 s the DSP pipeline needs. Same rule and the same
        wording as the analysis tab, because it is the same decision.
        """
        tramos = self._roi_segments or (
            [por_defecto] if por_defecto is not None else None
        )
        if not tramos:
            return emg_raw, time_axis

        duracion = float(time_axis[-1]) if time_axis.size else 0.0
        segs = normalise_segments([Segment(a, b) for a, b in tramos], duracion)
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
        if self._roi_segments:
            self.log.emit(
                tr(
                    "Muscle load computed over {n} selected fragment(s) "
                    "({d:.2f} s of {full:.2f} s)."
                ).format(n=len(segs), d=total, full=duracion)
            )
        else:
            self.log.emit(
                tr(
                    "Muscle load computed over the recording phase "
                    "({d:.2f} s of {full:.2f} s); the calibration and the "
                    "pause are outside it."
                ).format(d=total, full=duracion)
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
            marcas = edf.get("markers", [])
            fases = parse_phase_markers(marcas)
            cacheadas = parse_mvc_ref_markers(marcas)
            duracion_total = float(time_axis[-1]) if time_axis.size else 0.0

            self.log.emit(
                tr("Signal loaded — {fs:.0f} Hz — {dur:.1f} s — units: {units}").format(
                    fs=fs, dur=time_axis[-1], units=dimension
                )
            )

            # The reference is measured on the whole recording, before any
            # trimming: the calibration lies *outside* the analysed span by
            # design — that is what the two-phase session is for — and it is
            # still this muscle's maximum. One extra pass of the DSP, and only
            # when there are spans in the file to measure.
            env_calibracion = None
            if fases.cal_reps:
                env_calibracion = process_offline(
                    emg_raw, fs,
                    f_low=self._f_low, f_high=self._f_high,
                    f_notch=self._f_notch, f_env=self._f_env,
                )["emg_envelope"]
            mvc_amplitude_ref, mvc_ref_source = mvc_reference(
                self._channel_index,
                phases=fases, envelope=env_calibracion, fs=fs,
                cached=cacheadas, percentile=self._percentile,
                window_s=self._profile.mvc_peak_window_s,
            )
            if self._cancelled:
                return

            # Keep only the selected fragments, concatenated into one signal.
            # With none chosen the session's own recording phase is the answer:
            # the application knows where the calibration was, so separating it
            # from the work is not left to the operator's eye.
            emg_raw, time_axis = self._recortar(
                emg_raw, fs, time_axis,
                por_defecto=fases.rec_span(duracion_total),
            )
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

            # 4) Normalise, when there is a maximum to normalise against.
            #
            # There is no fallback. Dividing the recording by its own 95th
            # percentile would produce a number for every panel, and every one
            # of them would be wrong in the same direction: a task always
            # reaches about 100 % of itself, so the Jonsson limits would report
            # an overloaded subject whatever they did.
            emg_norm = None
            apdf = None
            mean_norm = None
            ylim_max = None
            if mvc_amplitude_ref:
                self.log.emit(
                    tr("MVC reference amplitude: {value:.4f} {units}").format(
                        value=mvc_amplitude_ref, units=dimension
                    )
                )
                emg_norm = normalise_to_mvc(emg_envelope, mvc_amplitude_ref)
                ylim_max = adaptive_ylim(emg_norm, n_plot)
                mean_norm = float(np.mean(emg_norm))
                self.log.emit(
                    tr("Mean normalised activation: {value:.1f} % MVC")
                    .format(value=mean_norm)
                )
                apdf = compute_apdf(emg_norm, **self._profile.apda_kwargs())
                self.log.emit(
                    tr(
                        "Muscle load (Jonsson) — static {st:.1f} %, "
                        "median {md:.1f} %, peak {pk:.1f} % MVC"
                    ).format(
                        st=apdf.static.value, md=apdf.median.value,
                        pk=apdf.peak.value
                    )
                )
            else:
                self.log.emit(tr(
                    "This recording carries no calibration, so there is no "
                    "maximum to express it as a percentage of: no % MVC and "
                    "no muscle-load analysis. The signal and its envelope do "
                    "not depend on a reference and are drawn as usual."
                ))

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
                #: Where the reference came from, as a token from
                #: emgteach.phases. The interface branches on this and words it
                #: with reference_source_text(); it must never branch on
                #: translated text. It replaces the old ``mvc_source``
                #: sentence and the ``mvc_is_auto`` flag that had to be carried
                #: beside it precisely because that sentence was translated.
                "mvc_ref_source": mvc_ref_source,
                #: How many calibration repetitions the file holds for this
                #: channel, so the provenance can say "(3 repetitions)".
                "cal_reps_n": len(fases.reps_for(self._channel_index)),
                "ylim_max": ylim_max,
                "dimension": dimension,
                "fs": fs,
                "f_high": self._f_high,
                "edf_path": self._edf_path,
            }

            self.result_ready.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))
