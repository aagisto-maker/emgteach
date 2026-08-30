"""Tests for the CSV export of an analysis result."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from emgteach.exports import write_analysis_csv


def _result() -> dict:
    return {
        "edf_path": "C:/data/emg_20260702.edf",
        "channel_name": "EMG",
        "fs": 1000.0,
        "duration": 3.0,
        "full_duration_s": 3.0,
        "rms_global": 0.1234,
        "mnf": 95.5,
        "mdf": 88.2,
        "iemg": 1.23,
        "mdf_slope": -0.42,
        "fat_slope_per_min": -25.2,
        "fat_r_squared": 0.87,
        "fat_pct_decline": 12.3,
        "fat_slope_sign": -1,
        "fat_verdict": "fatigue",   # R2 0.87: the fit backs the slope
        "t_seg": np.array([0.0, 0.5, 1.0]),
        "rms_seg": np.array([0.10, 0.12, 0.11]),
        "mdf_seg": np.array([100.0, 95.0, 90.0]),
    }


def test_csv_has_comment_header_and_segment_table(tmp_path: Path) -> None:
    out = tmp_path / "export.csv"
    write_analysis_csv(_result(), out)
    text = out.read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    # Metadata/summary is written as comment lines.
    assert lines[0].startswith("# emgteach analysis export")
    assert any("MDF (Hz): 88.200" in ln for ln in lines)
    assert any("R2: 0.8700" in ln for ln in lines)

    # The actual CSV body is the per-segment table.
    header_idx = next(i for i, ln in enumerate(lines) if ln == "t_s,rms_mv,mdf_hz")
    data = lines[header_idx + 1 :]
    assert len(data) == 3
    assert data[0].startswith("0.0000,")
    assert data[-1].split(",")[2] == "90.0000"


def test_csv_is_parseable_skipping_comments(tmp_path: Path) -> None:
    out = tmp_path / "export.csv"
    write_analysis_csv(_result(), out)
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].startswith("#")]
    assert rows[0] == ["t_s", "rms_mv", "mdf_hz"]
    assert len(rows) == 1 + 3  # header + 3 segments


def test_csv_states_roi_window(tmp_path: Path) -> None:
    r = _result()
    r["roi_start_s"] = 0.5
    r["roi_end_s"] = 2.0
    r["full_duration_s"] = 3.0
    out = tmp_path / "roi.csv"
    write_analysis_csv(r, out)
    text = out.read_text(encoding="utf-8-sig")
    assert "0.50-2.00 s of 3.0 s" in text


def test_csv_tolerates_missing_keys(tmp_path: Path) -> None:
    out = tmp_path / "sparse.csv"
    write_analysis_csv({"edf_path": "x.edf"}, out)  # no segments, no metrics
    lines = out.read_text(encoding="utf-8-sig").splitlines()
    assert "t_s,rms_mv,mdf_hz" in lines
