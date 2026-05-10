"""emgteach — open-source teaching platform for surface electromyography."""

from __future__ import annotations

from emgteach.devices import AcquisitionDevice, ArduinoDevice, BitalinoDevice
from emgteach.dsp import (
    RealtimeFilterState,
    compute_psd_mnf_mdf,
    compute_segments,
    design_bandpass,
    design_lowpass,
    design_notch,
    detect_acquisition_problems,
    process_offline,
)
from emgteach.fatigue import fit_mdf_vs_time, fit_rms_vs_mdf
from emgteach.io import (
    BufferedEdfWriter,
    ChannelInfo,
    build_timestamped_path,
    create_edf_writer,
    read_edf_mne,
    read_edf_pyedflib,
    write_edf_block,
)
from emgteach.mvc import adaptive_ylim, compute_mvc, normalise_to_mvc
from emgteach.workers import AcquisitionWorker, AnalysisWorker, MvcWorker

__version__ = "0.1.0"

__all__ = [
    "AcquisitionDevice",
    "AcquisitionWorker",
    "AnalysisWorker",
    "ArduinoDevice",
    "BitalinoDevice",
    "BufferedEdfWriter",
    "ChannelInfo",
    "MvcWorker",
    "RealtimeFilterState",
    "__version__",
    "adaptive_ylim",
    "build_timestamped_path",
    "compute_mvc",
    "compute_psd_mnf_mdf",
    "compute_segments",
    "create_edf_writer",
    "design_bandpass",
    "design_lowpass",
    "design_notch",
    "detect_acquisition_problems",
    "fit_mdf_vs_time",
    "fit_rms_vs_mdf",
    "normalise_to_mvc",
    "process_offline",
    "read_edf_mne",
    "read_edf_pyedflib",
    "write_edf_block",
]
