"""emgteach — open-source teaching platform for surface electromyography."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

__version__ = "3.4.0"

#: Where each export lives. Nothing is imported until it is first asked for:
#: ``import emgteach`` runs before any of its submodules is imported, so an
#: eager list here loaded the whole package — Qt with the workers, scipy with
#: the signal processing, mne and pyedflib with the file readers — for a
#: program that needs only the BITalino backend. The connection diagnostic's
#: executable is built without all of them.
_EXPORTS: dict[str, str] = {
    **dict.fromkeys(
        ("ApdfResult", "LoadLevel", "OnlineLoad", "classify_load", "compute_apdf"),
        "emgteach.apda"),
    **dict.fromkeys(
        ("AcquisitionDevice", "ArduinoDevice", "BitalinoDevice"), "emgteach.devices"),
    **dict.fromkeys(
        ("LiveQualityMonitor", "OnsetDetector", "QualityStatus", "RealtimeFilterState",
         "compute_psd_mnf_mdf", "compute_segments", "design_bandpass", "design_lowpass",
         "design_notch", "detect_acquisition_problems", "detect_onsets", "process_offline"),
        "emgteach.dsp"),
    **dict.fromkeys(("fit_mdf_vs_time", "fit_rms_vs_mdf"), "emgteach.fatigue"),
    **dict.fromkeys(
        ("BufferedEdfWriter", "ChannelInfo", "RecordingMetadata", "build_timestamped_path",
         "create_edf_writer", "edf_duration", "list_edf_channels", "read_edf_metadata",
         "read_edf_mne", "read_edf_pyedflib", "write_edf_block"),
        "emgteach.io"),
    **dict.fromkeys(("adaptive_ylim", "compute_mvc", "normalise_to_mvc"), "emgteach.mvc"),
    **dict.fromkeys(
        ("ECG_PROFILE", "EMG_PROFILE", "PROFILES", "SignalProfile", "get_profile"),
        "emgteach.profiles"),
    **dict.fromkeys(
        ("Segment", "normalise_segments", "suggest_significant_segments", "total_duration_s"),
        "emgteach.selection"),
    **dict.fromkeys(("AcquisitionWorker", "AnalysisWorker", "MvcWorker"), "emgteach.workers"),
}


def __getattr__(name: str) -> object:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module), name)
    globals()[name] = value          # asked once, then an ordinary attribute
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))


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
