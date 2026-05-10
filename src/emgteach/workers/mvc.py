"""Background worker for MVC (Maximum Voluntary Contraction) normalisation.

Loads one or two EDF files (the test signal and an optional MVC
reference), runs the same offline DSP pipeline as the analysis tab,
and normalises the test envelope against the MVC amplitude (95th
percentile by default). When no separate MVC file is provided, the
95th percentile of the test signal's own envelope is used as
reference (didactic auto-normalisation).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal

from emgteach.dsp import detect_acquisition_problems, process_offline
from emgteach.io import read_edf_pyedflib
from emgteach.mvc import adaptive_ylim, compute_mvc, normalise_to_mvc


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
        f_low: float = 20.0,
        f_high: float = 450.0,
        f_notch: float = 50.0,
        f_env: float = 5.0,
        plot_duration_s: float = 10.0,
        mvc_percentile: float = 95.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._edf_path = edf_path
        self._mvc_path = mvc_path.strip()
        self._f_low = float(f_low)
        self._f_high = float(f_high)
        self._f_notch = float(f_notch)
        self._f_env = float(f_env)
        self._plot_duration_s = float(plot_duration_s)
        self._percentile = float(mvc_percentile)
        self._cancelled = False

    def stop(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            # 1) Load test EDF
            self.log.emit(f"Loading EMG signal: {self._edf_path}")
            edf = read_edf_pyedflib(self._edf_path)
            emg_raw = edf["emg_raw"]
            fs = edf["sfreq"]
            dimension = edf["dimension"]
            time_axis = edf["tiempo"]

            self.log.emit(
                f"Signal loaded - {fs:.0f} Hz - {time_axis[-1]:.1f} s - units: {dimension}"
            )

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
            self.log.emit("Processing test signal (notch -> band-pass -> envelope)...")
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

            if self._mvc_path:
                try:
                    self.log.emit(f"Loading MVC file: {self._mvc_path}")
                    mvc_edf = read_edf_pyedflib(self._mvc_path)
                    mvc_fs = mvc_edf["sfreq"]

                    diag_mvc = detect_acquisition_problems(mvc_edf["emg_raw"], mvc_fs)
                    for warning in diag_mvc["warnings"]:
                        self.log.emit(warning)

                    self.log.emit("Processing MVC signal...")
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
                    mvc_source = (
                        f"external MVC file (percentile {self._percentile:.0f})"
                    )
                except Exception as exc:
                    self.log.emit(
                        f"Could not load MVC file ({exc}). "
                        "Falling back to auto-normalisation."
                    )
                    mvc_amplitude_ref = compute_mvc(emg_envelope, self._percentile)
                    mvc_source = (
                        f"auto - percentile {self._percentile:.0f} of the test signal"
                    )
            else:
                mvc_amplitude_ref = compute_mvc(emg_envelope, self._percentile)
                mvc_source = (
                    f"auto - percentile {self._percentile:.0f} of the test signal"
                )

            self.log.emit(
                f"MVC reference amplitude: {mvc_amplitude_ref:.4f} {dimension} "
                f"({mvc_source})"
            )
            if self._cancelled:
                return

            # 5) Normalise
            emg_norm = normalise_to_mvc(emg_envelope, mvc_amplitude_ref)
            ylim_max = adaptive_ylim(emg_norm, n_plot)

            mean_norm = float(np.mean(emg_norm))
            self.log.emit(f"Mean normalised activation: {mean_norm:.1f} %MVC")

            result = {
                "emg_raw": emg_raw,
                "emg_filtered": proc["emg_filtered"],
                "emg_rectified": proc["emg_rectified"],
                "emg_envelope": emg_envelope,
                "emg_norm": emg_norm,
                "t_plot": t_plot,
                "n_plot": n_plot,
                "tiempo": time_axis,
                "mvc_amplitude_ref": mvc_amplitude_ref,
                "mvc_source": mvc_source,
                "ylim_max": ylim_max,
                "dimension": dimension,
                "fs": fs,
                "f_high": self._f_high,
                "edf_path": self._edf_path,
            }

            self.result_ready.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))
