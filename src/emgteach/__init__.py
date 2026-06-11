"""emgteach — open-source teaching platform for surface electromyography."""

from __future__ import annotations

from emgteach.devices import AcquisitionDevice, ArduinoDevice, BitalinoDevice
from emgteach.dsp import (
    OnsetDetector,
    RealtimeFilterState,
    compute_psd_mnf_mdf,
    compute_segments,
    design_bandpass,
    design_lowpass,
    design_notch,
    detect_acquisition_problems,
    detect_onsets,
    process_offline,
)
from emgteach.fatigue import fit_mdf_vs_time, fit_rms_vs_mdf
from emgteach.io import (
    BufferedEdfWriter,
    ChannelInfo,
    build_timestamped_path,
    create_edf_writer,
    list_edf_channels,
    read_edf_mne,
    read_edf_pyedflib,
    write_edf_block,
)
from emgteach.mvc import adaptive_ylim, compute_mvc, normalise_to_mvc
from emgteach.profiles import EMG_PROFILE, SignalProfile
from emgteach.workers import AcquisitionWorker, AnalysisWorker, MvcWorker

__version__ = "0.2.0"

__all__ = [
    "EMG_PROFILE",
    "AcquisitionDevice",
    "AcquisitionWorker",
    "AnalysisWorker",
    "ArduinoDevice",
    "BitalinoDevice",
    "BufferedEdfWriter",
    "ChannelInfo",
    "MvcWorker",
    "OnsetDetector",
    "RealtimeFilterState",
    "SignalProfile",
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
    "detect_onsets",
    "fit_mdf_vs_time",
    "fit_rms_vs_mdf",
    "list_edf_channels",
    "normalise_to_mvc",
    "process_offline",
    "read_edf_mne",
    "read_edf_pyedflib",
    "write_edf_block",
]
