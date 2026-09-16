"""The report and the CSV fit the page and say what they describe.

The tables of the session report used to be built with two column widths
for any number of columns, so the table of contractions — the one a
laboratory report is copied from — lost its last four columns off the right
edge of the paper, and no test noticed because the tests only checked for
``%PDF``. These read the text back out of the page streams.
"""

from __future__ import annotations

import base64
import csv
import re
import zlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from reportlab.lib.units import cm

from emgteach import __version__, reports
from emgteach.coactivation import CoactivationResult
from emgteach.contractions import Contraction
from emgteach.exports import csv_dialect, write_analysis_csv
from emgteach.i18n import get_language, set_language
from emgteach.io import BufferedEdfWriter, ChannelInfo, RecordingMetadata
from emgteach.phases import (
    FROM_CACHE,
    RepValue,
    cal_end_marker,
    cal_start_marker,
    warmup_start_marker,
)
from emgteach.reports import (
    TABLE_WIDTH_CM,
    _styled_table,
    build_mvc_report,
    build_session_report,
)

FS = 1000


def _pdf_text(path: Path) -> str:
    """The strings the PDF draws, page streams inflated: enough to look for a word.

    reportlab writes every stream ``[/ASCII85Decode /FlateDecode]`` (see
    ``rl_config.pageCompression``): the bytes between ``stream``/``endstream``
    are ASCII85 first, the ``zlib`` payload underneath — an image stream
    with no text yields no ``Tj`` and is skipped either way.
    """
    data = Path(path).read_bytes()
    out: list[str] = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        raw = m.group(1).strip()
        if raw.endswith(b"~>"):
            raw = raw[:-2]
        try:
            raw = base64.a85decode(raw, adobe=False)
        except ValueError:
            pass
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        for s in re.findall(rb"\((.*?)\)\s*Tj", raw, re.S):
            out.append(s.decode("latin-1").replace(r"\(", "(").replace(r"\)", ")"))
    return "\n".join(out)


def _resultado_de_par(n_frag: int = 8) -> dict:
    """A two-muscle analysis with everything the report prints, eight fragments."""
    n = 60 * FS
    t = np.arange(n) / FS
    x = 0.3 * np.sin(2 * np.pi * 80.0 * t)
    k = 40
    t_seg = np.linspace(0.5, 59.5, k)
    frag = [(30.0 + 4 * i, 32.0 + 4 * i) for i in range(n_frag)]
    n1, n2 = "Flexor radial", "Extensor radial"
    return {
        "times": t, "emg_raw": x, "emg_filtered": x, "emg_rectified": np.abs(x),
        "emg_envelope": np.abs(x), "rms_sliding": np.abs(x) * 0.7,
        "emg_envelope_normalised": np.abs(x) / 0.3,
        "frequencies": np.linspace(0, 500, 256), "psd": np.ones(256), "f_high": 450.0,
        "t_seg": t_seg, "rms_seg": 0.2 - 0.001 * t_seg, "mdf_seg": 90 - 0.2 * t_seg,
        "fat_fitted": 90 - 0.2 * t_seg, "rms_seg_2": 0.1 + 0 * t_seg, "mdf_seg_2": 95 + 0 * t_seg,
        "rms_mdf_range": np.linspace(80, 92, k), "rms_mdf_fitted": np.linspace(0.1, 0.2, k),
        "channel_name": n1, "channel_name_2": n2,
        "edf_path": "C:/Users/someone/Records/P07.edf",
        "duration": 2.0 * n_frag, "full_duration_s": 60.0, "roi_segments": frag,
        "rms_global": 0.2123, "mnf": 95.3, "mdf": 88.1, "iemg": 1.234, "mdf_slope": -0.42,
        "fat_r_squared": 0.87, "fat_pct_decline": 12.3, "fat_verdict": "fatigue",
        "rms_global_2": 0.0990, "mnf_2": 101.0, "mdf_2": 90.5, "iemg_2": 0.456,
        "mdf_slope_2": 0.01, "fat_r_squared_2": 0.05, "fat_pct_decline_2": 0.2,
        "fat_verdict_2": "inconclusive",
        "fs": FS,
        "config": {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0,
                   "rms_window_ms": 50.0, "seg_len_s": 1.0, "overlap": 0.5},
        "detection": {"k": 3.0, "both_ratio": 0.5},
        "mvc_ref": 0.9, "mvc_ref_source": FROM_CACHE,
        "mvc_ref_2": 0.7, "mvc_ref_source_2": FROM_CACHE,
        "cal_reps": {0: [1, 2, 3], 1: [1, 2, 3]},
        "task_peak_pct": {n1: 88.0, n2: 41.0},
        "cal_rep_values": {0: [RepValue(1, 0.8, 30.0), RepValue(2, 0.9, 35.0)],
                           1: [RepValue(1, 0.7, 20.0)]},
        "cal_channel_names": {0: n1, 1: n2},
        "cal_keep": {0: {1, 2}, 1: {1}},
        "contractions": [
            Contraction(i + 1, a, b, n1 if i % 2 == 0 else n2, 0.25, 80.0, 90.0, emd_ms=45.0,
                        channel=1 if i % 2 == 0 else 2, rms_mv_other=0.1, peak_pct_other=30.0)
            for i, (a, b) in enumerate(frag)
        ],
        "emd_ms_mean": 45.0,
        "coactivation": [
            CoactivationResult(index=35.0, mean_1=60.0, mean_2=25.0, window_s=(a, b),
                               label=f"Grip {i + 1}")
            for i, (a, b) in enumerate(frag)
        ],
        "coactivation_from_markers": True,
    }


def _resultado_basico() -> dict:
    return {
        "edf_path": "C:/data/emg_20260702.edf", "channel_name": "EMG", "fs": 1000.0,
        "duration": 3.0, "full_duration_s": 3.0, "rms_global": 0.1234, "mnf": 95.5,
        "mdf": 88.2, "iemg": 1.23, "mdf_slope": -0.42, "fat_slope_per_min": -25.2,
        "fat_r_squared": 0.87, "fat_pct_decline": 12.3, "fat_slope_sign": -1,
        "fat_verdict": "fatigue",
        "t_seg": np.array([0.0, 0.5, 1.0]), "rms_seg": np.array([0.10, 0.12, 0.11]),
        "mdf_seg": np.array([100.0, 95.0, 90.0]),
    }


def _resultado_cvm() -> dict:
    n = 4000
    t = np.arange(n) / FS
    base = 0.3 * np.sin(2 * np.pi * 80.0 * t)
    env = np.abs(np.sin(2 * np.pi * 0.3 * t)) * 40.0 + 3.0
    from emgteach.apda import compute_apdf

    return {
        "emg_filtered": base, "emg_rectified": np.abs(base), "emg_envelope": env / 100.0 * 0.5,
        "emg_norm": env, "mean_norm": float(np.mean(env)), "apdf": compute_apdf(env),
        "t_plot": t, "n_plot": n, "tiempo": t, "mvc_amplitude_ref": 0.5,
        "mvc_ref_source": FROM_CACHE, "cal_reps_n": 3, "dimension": "mV",
        "edf_path": "C:/data/cvm.edf", "fs": FS,
        "f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0,
    }


def _edf(path: Path, labels: list[str], seconds: int = 20, *, student_code: str = "",
         equipment: str = "BITalino 44:E4", marks: list[tuple[float, str]] = ()) -> str:
    t = np.arange(seconds * FS) / FS
    signals = [0.3 / (i + 1) * np.sin(2 * np.pi * 80.0 * t) for i in range(len(labels))]
    with BufferedEdfWriter(
        str(path), channels=[ChannelInfo(lb, dimension="mV", sample_frequency=FS) for lb in labels],
        metadata=RecordingMetadata(student_code=student_code, equipment=equipment,
                                   protocol="pair"),
    ) as w:
        w.add_samples(*signals)
        for at, label in marks:
            w.add_annotation(at, label)
    return str(path)


# -- the session report ------------------------------------------------------

def test_every_table_fits_the_frame_and_the_wide_ones_reach_the_paper(
    tmp_path: Path, monkeypatch,
) -> None:
    seen: list[tuple[int, float]] = []
    original = reports._styled_table

    def spy(data, widths=None, size=9, spans=()):
        table = original(data, widths, size, spans)
        seen.append((len(data[0]), float(sum(table._colWidths))))
        return table

    monkeypatch.setattr(reports, "_styled_table", spy)
    out = tmp_path / "par.pdf"
    build_session_report(out, _resultado_de_par(), meta={"device": "BITalino 44:E4"}, panels=[])
    assert len(seen) >= 6, "metrics, calibration, repetitions, contractions, co-activation, configuration"
    assert max(w for _n, w in seen) <= TABLE_WIDTH_CM * cm + 1e-6
    assert max(n for n, _w in seen) == 8, "the contractions: #, start, duration, muscle, RMS, peak, MDF, EMD"
    text = _pdf_text(out)
    for word in ("Muscle", "RMS (mV)", "Peak (% MVC)", "MDF (Hz)", "EMD (ms)",
                 "Task maximum", "Other muscle during it", "58.00-60.00"):
        assert word in text, word


def test_the_report_names_the_device_the_provenance_and_both_muscles(tmp_path: Path) -> None:
    out = tmp_path / "par.pdf"
    r = _resultado_de_par()
    build_session_report(out, r, panels=[], meta={
        "student_code": "P07", "protocol": "pair", "device": "BITalino simulated",
        "derived": "DERIVED from P07.edf",
    })
    text = _pdf_text(out)
    assert "BITalino simulated" in text and "DERIVED from P07.edf" in text
    assert "Test identifier: P07" in text and "Protocol: pair" in text
    assert "0.0990 mV" in text and "101.0 Hz" in text, "the second muscle's RMS and MNF"
    assert "Flexor radial, Extensor radial" in text, "the configuration names both channels"
    assert "not stored in the EDF" not in text

    build_session_report(out, r, panels=[])
    assert "not stored in the EDF" in _pdf_text(out)


def test_a_table_wider_than_the_frame_is_refused() -> None:
    with pytest.raises(ValueError, match="over 17"):
        _styled_table([["a", "b"], ["1", "2"]], [10.0, 10.0])
    with pytest.raises(ValueError, match="widths"):
        _styled_table([["a", "b", "c"]], [5.0, 5.0])
    table = _styled_table([["a", "b", "c", "d"]])
    assert sum(table._colWidths) == pytest.approx(TABLE_WIDTH_CM * cm)


# -- the MVC report ----------------------------------------------------------

def test_the_mvc_report_says_channel_fragments_filters_and_device(tmp_path: Path) -> None:
    out = tmp_path / "cvm.pdf"
    build_mvc_report(out, _resultado_cvm(), time_range=(0.5, 3.5), meta={
        "channel": "Extensor radial", "fragments": [(1.0, 2.0), (2.5, 3.5)],
        "device": "BITalino 44:E4", "student_code": "P07",
    })
    text = _pdf_text(out)
    for word in ("Extensor radial", "2 fragments (2.00 s of 4.0 s): 1.00-2.00; 2.50-3.50 s",
                 "0.5-3.5 s", "20.0-450.0 Hz", "50.0 Hz", "BITalino 44:E4", "Test identifier: P07"):
        assert word in text, word


def test_the_mvc_figure_is_drawn_at_the_size_it_is_printed() -> None:
    png = reports._render_mvc_figure(_resultado_cvm()).getvalue()
    w, h = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    assert w >= 800 and abs(w / h - 14 / 21) < 0.01


# -- the CSV -----------------------------------------------------------------

def test_the_spanish_csv_uses_semicolons_and_decimal_commas(tmp_path: Path) -> None:
    previo = get_language()
    set_language("es")
    try:
        assert csv_dialect() == (";", ",")
        out = tmp_path / "es.csv"
        write_analysis_csv(_resultado_basico(), out)
        text = out.read_text(encoding="utf-8-sig")
    finally:
        set_language(previo)
    assert csv_dialect() == (",", ".")
    assert "# MDF (Hz): 88,200" in text
    assert "0,0000;0,100000;100,0000" in text
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f, delimiter=";") if r and not r[0].startswith("#")]
    assert rows[0] == ["t_s", "rms_mv", "mdf_hz"] and len(rows) == 4


def test_the_csv_carries_the_name_the_version_the_reference_and_the_tables(tmp_path: Path) -> None:
    out = tmp_path / "par.csv"
    write_analysis_csv(_resultado_de_par(), out)
    text = out.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == f"# emgteach analysis export (emgteach v{__version__})"
    assert "P07.edf" in text and "C:/Users" not in text and "someone" not in text
    assert "# Second channel: Extensor radial" in lines
    assert "# MVC reference (mV) [Flexor radial]: 0.9000 (" in text
    assert "# Task maximum (% MVC) [Extensor radial]: 41" in lines
    assert "# MDF (Hz) [Extensor radial]: 90.500" in lines
    assert "t_s,rms_mv,mdf_hz,rms_mv_2,mdf_hz_2" in lines
    i = lines.index("# Contractions")
    assert lines[i + 1] == "n,start_s,duration_s,muscle,rms_mv,peak_pct,mdf_hz,emd_ms"
    assert lines[i + 2] == "1,30.000,2.000,Flexor radial,0.250000,80.0,90.00,45.0"
    j = lines.index("# Co-activation (Falconer-Winter)")
    assert lines[j + 1] == "window,start_s,end_s,mean_1_pct,mean_2_pct,index_pct,note"
    assert lines[j + 2] == "Grip 1,30.000,32.000,60.0,25.0,35.0,"


# -- the reference marker, the tuned file ---------------------------------------

def test_the_reference_marker_reads_back_in_scientific_notation() -> None:
    from emgteach.mvc import mvc_ref_marker, parse_mvc_ref_markers

    assert mvc_ref_marker(0, 5e-5) == "MVC ref ch=1 value=5e-05 mV"
    parsed = parse_mvc_ref_markers([(1.0, mvc_ref_marker(0, 5e-5)),
                                    (2.0, mvc_ref_marker(1, 0.4213))])
    assert parsed[0] == pytest.approx(5e-5) and parsed[1] == pytest.approx(0.4213)


def test_tuning_starts_the_task_where_the_analysis_does_without_rec_start(tmp_path: Path) -> None:
    from emgteach.io import edf_duration
    from emgteach.tuning import build_tuned_edf, tuned_path

    cal = [(4.0, 8.0), (12.0, 16.0), (20.0, 24.0)]
    marks = [(0.1, warmup_start_marker())]
    for i, (a, b) in enumerate(cal, start=1):
        marks += [(a, cal_start_marker(0, i)), (b, cal_end_marker(0, i))]
    src = _edf(tmp_path / "solo_cal.edf", ["FCR"], seconds=50, marks=marks)
    dst = tuned_path(src)
    resumen = build_tuned_edf(src, dst, fragments=[(32.0, 36.0)], when=datetime(2026, 9, 16, 12, 0))
    assert resumen.kept_s == pytest.approx(4.0)
    assert edf_duration(dst) == pytest.approx(24.0 + 4.0), "the pre-task, then the fragment"

    plain = _edf(tmp_path / "sin_fases.edf", ["FCR"], seconds=10)
    with pytest.raises(ValueError, match="nothing to tune"):
        build_tuned_edf(plain, tuned_path(plain), fragments=[(2.0, 4.0)])


# -- the tabs ------------------------------------------------------------------

@pytest.mark.gui
def test_the_analysis_report_takes_identifier_and_device_from_the_file_only(
    qapp, tmp_path: Path,
) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "informes")
    settings.setValue("adquisicion/student_code", "P07")     # the previous student's
    edf = _edf(tmp_path / "anon.edf", ["FCR"], equipment="BITalino simulated")
    tab = AnalysisTab(LoggerWidget(), settings)
    tab._populate_channels(edf)
    meta = tab._report_meta()
    assert meta["student_code"] == "" and meta["device"] == "BITalino simulated"
    assert meta["protocol"] == "pair"
    tab.close()


@pytest.mark.gui
def test_the_normalisation_tab_forgets_the_numbers_when_the_channel_changes(
    qapp, tmp_path: Path,
) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.mvc import MvcTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "informes-cvm")
    settings.setValue("adquisicion/student_code", "P07")
    edf = _edf(tmp_path / "par.edf", ["FCR", "ECR"])
    tab = MvcTab(LoggerWidget(), settings)
    tab._edit_path.setText(edf)
    tab._populate_channels(edf, ask=False)
    assert tab._combo_canal.count() == 2
    tab._last_result = {"edf_path": edf}
    tab._btn_informe.setEnabled(True)
    tab._combo_canal.setCurrentIndex(1)
    assert tab._last_result is None and not tab._btn_informe.isEnabled()
    meta = tab._report_meta()
    assert meta["student_code"] == "" and meta["channel"] == "ECR"
    assert meta["device"] == "BITalino 44:E4" and meta["fragments"] == []
    # _olvidar_resultado() schedules a deferred matplotlib repaint
    # (draw_idle); flush it before the tab is torn down, or it fires on a
    # dead C++ widget once this test's qapp iteration moves on.
    qapp.processEvents()
    tab.cleanup()
    qapp.processEvents()


@pytest.mark.gui
def test_the_worker_computes_the_second_muscles_metrics_too(qapp, tmp_path: Path) -> None:
    from emgteach.workers.analysis import AnalysisWorker

    edf = _edf(tmp_path / "par.edf", ["FCR", "ECR"])
    worker = AnalysisWorker(edf_path=edf, channel_name="FCR", channel_name_2="ECR",
                            plot_duration_s=0)
    got: list[dict] = []
    worker.result_ready.connect(got.append)
    worker.run()
    assert got, "no result"
    r = got[0]
    for key in ("rms_global_2", "iemg_2", "fat_verdict_2", "fat_r_squared_2",
                "fat_pct_decline_2", "fat_slope_per_min_2"):
        assert key in r, key
    assert 0.0 < r["rms_global_2"] < r["rms_global"], "the second channel is half the first"
    assert 0.0 < r["iemg_2"] < r["iemg"]
