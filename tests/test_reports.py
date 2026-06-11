"""Tests for :mod:`emgteach.reports` (PDF session reports).

These run headless: the signal figure is rendered with matplotlib's Agg
backend and the document with reportlab, so no Qt/display is needed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.reports import build_session_report, git_commit_hash


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


class TestGitCommitHash:
    def test_returns_str_or_none(self) -> None:
        h = git_commit_hash()
        assert h is None or isinstance(h, str)
