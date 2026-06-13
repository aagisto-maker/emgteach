"""Tests for :mod:`emgteach.reports` (PDF session reports).

These run headless: the signal figure is rendered with matplotlib's Agg
backend and the document with reportlab, so no Qt/display is needed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.apda import compute_apdf
from emgteach.reports import build_mvc_report, build_session_report, git_commit_hash


@pytest.fixture
def analysis_result() -> dict:
    fs = 1000
    n = 3000
    t = np.arange(n) / fs
    sig = 0.3 * np.sin(2 * np.pi * 80.0 * t)
    return {
        "times": t,
        "emg_filtered": sig,
        "emg_envelope": np.abs(sig),
        "markers": [(1.0, "Inicio contracción"), (2.0, "Fatiga aparente")],
        "channel_name": "EMG",
        "edf_path": "C:/data/session.edf",
        "duration": 3.0,
        "rms_global": 0.212,
        "mnf": 95.3,
        "mdf": 88.1,
        "iemg": 1.234,
        "fat_slope_sign": -1,
        "mdf_slope": -0.42,
        "fs": fs,
        "config": {
            "f_low": 20.0,
            "f_high": 450.0,
            "f_notch": 50.0,
            "f_env": 5.0,
            "rms_window_ms": 50.0,
            "seg_len_s": 1.0,
            "overlap": 0.5,
        },
    }


@pytest.fixture
def full_analysis_result(analysis_result: dict) -> dict:
    """``analysis_result`` plus every array the 8 report panels need."""
    r = dict(analysis_result)
    t = r["times"]
    filt = r["emg_filtered"]
    k = 20
    t_seg = np.linspace(0.5, float(t[-1]) - 0.5, k)
    r.update(
        {
            "emg_raw": filt + 0.02,
            "emg_rectified": np.abs(filt),
            "rms_sliding": np.abs(filt) * 0.7,
            "emg_envelope_normalised": np.abs(filt) / (np.abs(filt).max() or 1.0),
            "frequencies": np.linspace(0, 500, 256),
            "psd": np.exp(-((np.linspace(0, 500, 256) - 90) ** 2) / 2000),
            "f_high": 450.0,
            "t_seg": t_seg,
            "rms_seg": 0.2 - 0.03 * t_seg,
            "mdf_seg": 90 - 2 * t_seg,
            "fat_fitted": 90 - 2 * t_seg,
            "rms_mdf_range": np.linspace(80, 92, k),
            "rms_mdf_fitted": np.linspace(0.1, 0.2, k),
        }
    )
    return r


class TestBuildSessionReport:
    def test_produces_a_valid_pdf(self, analysis_result: dict, tmp_path: Path) -> None:
        out = tmp_path / "informe.pdf"
        path = build_session_report(
            out,
            analysis_result,
            meta={"student": "Ana Pérez", "student_code": "FARM-12", "commit": "abc1234"},
        )
        data = Path(path).read_bytes()
        assert data[:4] == b"%PDF"
        assert len(data) > 2000  # has the embedded plot + tables

    def test_works_without_markers_or_config(
        self, analysis_result: dict, tmp_path: Path
    ) -> None:
        result = dict(analysis_result)
        result["markers"] = []
        result.pop("config")
        out = tmp_path / "informe_min.pdf"
        build_session_report(out, result)
        assert out.read_bytes()[:4] == b"%PDF"

    def test_handles_no_fatigue_trend(
        self, analysis_result: dict, tmp_path: Path
    ) -> None:
        result = dict(analysis_result)
        result["fat_slope_sign"] = 0
        out = tmp_path / "informe_nofat.pdf"
        build_session_report(out, result)
        assert out.exists()

    def test_panels_selection_produces_pdf(
        self, full_analysis_result: dict, tmp_path: Path
    ) -> None:
        """Selecting analysis panels renders each as a graph in the report."""
        out = tmp_path / "informe_paneles.pdf"
        build_session_report(out, full_analysis_result, panels=[0, 1, 4, 6, 7])
        assert out.read_bytes()[:4] == b"%PDF"

    def test_empty_panels_still_valid(
        self, full_analysis_result: dict, tmp_path: Path
    ) -> None:
        """An empty panel selection yields a graph-less but valid report."""
        out = tmp_path / "informe_sin_graficos.pdf"
        build_session_report(out, full_analysis_result, panels=[])
        assert out.read_bytes()[:4] == b"%PDF"

    def test_time_range_restricts_panels(
        self, full_analysis_result: dict, tmp_path: Path
    ) -> None:
        """A time range plots only that window on the time-domain panels."""
        out = tmp_path / "informe_rango.pdf"
        build_session_report(
            out, full_analysis_result, panels=[0, 1, 5], time_range=(0.5, 1.5)
        )
        assert out.read_bytes()[:4] == b"%PDF"


class TestGitCommitHash:
    def test_returns_str_or_none(self) -> None:
        h = git_commit_hash()
        assert h is None or isinstance(h, str)


@pytest.fixture
def mvc_result() -> dict:
    fs = 1000
    n = 4000
    t = np.arange(n) / fs
    base = 0.3 * np.sin(2 * np.pi * 80.0 * t)
    env = np.abs(np.sin(2 * np.pi * 0.3 * t)) * 40.0 + 3.0  # % MVC envelope
    return {
        "emg_filtered": base,
        "emg_rectified": np.abs(base),
        "emg_envelope": env / 100.0 * 0.5,
        "emg_norm": env,
        "mean_norm": float(np.mean(env)),
        "apdf": compute_apdf(env),
        "t_plot": t,
        "n_plot": n,
        "tiempo": t,
        "mvc_amplitude_ref": 0.5,
        "mvc_source": "auto (percentile 95)",
        "dimension": "mV",
        "edf_path": "C:/data/cvm.edf",
    }


class TestMvcReport:
    def test_writes_valid_pdf(self, mvc_result: dict, tmp_path: Path) -> None:
        out = tmp_path / "informe_cvm.pdf"
        returned = build_mvc_report(out, mvc_result)
        assert Path(returned) == out
        assert out.read_bytes()[:4] == b"%PDF"

    def test_includes_student_meta(self, mvc_result: dict, tmp_path: Path) -> None:
        out = tmp_path / "informe_cvm_alumno.pdf"
        build_mvc_report(out, mvc_result, {"student": "Ada", "student_code": "X1"})
        assert out.read_bytes()[:4] == b"%PDF"

    def test_time_range(self, mvc_result: dict, tmp_path: Path) -> None:
        out = tmp_path / "informe_cvm_rango.pdf"
        build_mvc_report(out, mvc_result, time_range=(1.0, 4.0))
        assert out.read_bytes()[:4] == b"%PDF"
