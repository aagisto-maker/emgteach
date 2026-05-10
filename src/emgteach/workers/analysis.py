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

from emgteach.dsp import (
    compute_psd_mnf_mdf,
    compute_segments,
    detect_acquisition_problems,
    process_offline,
)
from emgteach.fatigue import fit_mdf_vs_time, fit_rms_vs_mdf
from emgteach.io import read_edf_mne


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
        channel_name: str = "EMG",
        f_low: float = 20.0,
        f_high: float = 450.0,
        f_notch: float = 50.0,
        f_env: float = 5.0,
        rms_window_ms: float = 50.0,
        seg_len_s: float = 1.0,
        overlap: float = 0.5,
        plot_duration_s: float = 10.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._edf_path = edf_path
        self._channel_name = channel_name
        self._f_low = float(f_low)
        self._f_high = float(f_high)
        self._f_notch = float(f_notch)
        self._f_env = float(f_env)
        self._rms_window_ms = float(rms_window_ms)
        self._seg_len_s = float(seg_len_s)
        self._overlap = float(overlap)
        self._plot_duration_s = float(plot_duration_s)
        self._cancelled = False

    def stop(self) -> None:
        """Request that the next checkpoint abandon the run."""
        self._cancelled = True

    def run(self) -> None:
        try:
            # 1) Load EDF
            self.log.emit(f"Loading file: {self._edf_path}")
            self.progress.emit(5)
            edf = read_edf_mne(self._edf_path, self._channel_name)
            emg_raw = edf["emg_raw"]
            fs = edf["sfreq"]
            times = edf["times"]
            markers = edf.get("markers", [])

            duration = float(times[-1])
            self.log.emit(
                f"Channel '{self._channel_name}' - {fs:.0f} Hz - {duration:.1f} s"
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
            self.log.emit("Applying DSP pipeline...")
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
            self.log.emit("Computing PSD, MNF and MDF...")
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
            self.log.emit("Computing segment-wise RMS and MDF...")
            segs = compute_segments(
                proc["emg_filtered"],
                fs,
                seg_len_s=self._seg_len_s,
                overlap=self._overlap,
            )
            self.progress.emit(75)
            if self._cancelled:
                return

            # 6) Fatigue polynomial fits
            self.log.emit("Polynomial fatigue fit (degree 2)...")
            fat_time = fit_mdf_vs_time(segs["t_seg"], segs["mdf_seg"])
            fat_rms = fit_rms_vs_mdf(segs["mdf_seg"], segs["rms_seg"])

            if fat_time["slope_sign"] < 0:
                self.log.emit("Fatigue trend detected (MDF decreases over time).")
            elif fat_time["slope_sign"] > 0:
                self.log.emit("No fatigue (MDF increases or remains stable).")
            else:
                self.log.emit("MDF trend undefined (signal too short or constant).")
            self.progress.emit(90)

            # 7) Pack result
            rms_global = float(np.sqrt(np.mean(proc["emg_filtered"] ** 2)))
            iemg = float(trapezoid(proc["emg_rectified"], dx=1.0 / fs))
            t_seg = segs["t_seg"]
            if len(t_seg) >= 2:
                mdf_slope = float(
                    (fat_time["fitted"][-1] - fat_time["fitted"][0])
                    / (t_seg[-1] - t_seg[0])
                )
            else:
                mdf_slope = 0.0

            result = {
                # time-domain arrays (full length)
                "emg_raw": emg_raw,
                "emg_filtered": proc["emg_filtered"],
                "emg_rectified": proc["emg_rectified"],
                "emg_envelope": proc["emg_envelope"],
                "rms_sliding": proc["rms_sliding"],
                "emg_envelope_normalised": proc["emg_envelope_normalised"],
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
                "fat_slope_sign": fat_time["slope_sign"],
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
                "edf_path": self._edf_path,
                "channel_name": self._channel_name,
                "markers": markers,
            }

            self.progress.emit(100)
            self.result_ready.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))
