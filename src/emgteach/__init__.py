"""emgteach — open-source teaching platform for surface electromyography."""

from __future__ import annotations

from emgteach.apda import ApdfResult, LoadLevel, OnlineLoad, classify_load, compute_apdf
from emgteach.devices import AcquisitionDevice, ArduinoDevice, BitalinoDevice
from emgteach.dsp import (
    LiveQualityMonitor,
    OnsetDetector,
    QualityStatus,
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
    RecordingMetadata,
    build_timestamped_path,
    create_edf_writer,
    edf_duration,
    list_edf_channels,
    read_edf_metadata,
    read_edf_mne,
    read_edf_pyedflib,
    write_edf_block,
)
from emgteach.mvc import adaptive_ylim, compute_mvc, normalise_to_mvc
from emgteach.profiles import (
    ECG_PROFILE,
    EMG_PROFILE,
    PROFILES,
    SignalProfile,
    get_profile,
)
from emgteach.selection import (
    Segment,
    normalise_segments,
    suggest_significant_segments,
    total_duration_s,
)
from emgteach.workers import AcquisitionWorker, AnalysisWorker, MvcWorker

__version__ = "1.0.0"

__all__ = [
    "ECG_PROFILE",
    "EMG_PROFILE",
    "PROFILES",
    "AcquisitionDevice",
    "AcquisitionWorker",
    "AnalysisWorker",
    "ApdfResult",
    "ArduinoDevice",
    "BitalinoDevice",
    "BufferedEdfWriter",
    "ChannelInfo",
    "LiveQualityMonitor",
    "LoadLevel",
    "MvcWorker",
    "OnlineLoad",
    "OnsetDetector",
    "QualityStatus",
    "RealtimeFilterState",
    "RecordingMetadata",
    "Segment",
    "SignalProfile",
    "__version__",
    "adaptive_ylim",
    "build_timestamped_path",
    "classify_load",
    "compute_apdf",
    "compute_mvc",
    "compute_psd_mnf_mdf",
    "compute_segments",
    "create_edf_writer",
    "design_bandpass",
    "design_lowpass",
    "design_notch",
    "detect_acquisition_problems",
    "detect_onsets",
    "edf_duration",
    "fit_mdf_vs_time",
    "fit_rms_vs_mdf",
    "get_profile",
    "list_edf_channels",
    "normalise_segments",
    "normalise_to_mvc",
    "process_offline",
    "read_edf_metadata",
    "read_edf_mne",
    "read_edf_pyedflib",
    "suggest_significant_segments",
    "total_duration_s",
    "write_edf_block",
]
