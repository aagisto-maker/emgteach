"""CSV export of an offline-analysis result.

The analysis tab produces a single result dictionary (see
:class:`emgteach.workers.analysis.AnalysisWorker`). This module turns it
into a spreadsheet-friendly CSV so students can re-plot or tabulate the
numbers in Excel/LibreOffice without re-running the app.

The file has two parts:

* a metadata + summary header written as ``#``-prefixed comment lines
  (file, channel, analysed window, and every scalar metric), which
  spreadsheets and :func:`pandas.read_csv` skip with ``comment='#'``; and
* the per-segment table (``t_s``, ``rms_mv``, ``mdf_hz``) as the actual
  CSV body, ready to import and plot directly.

It is written UTF-8 with BOM (``utf-8-sig``) so Excel on Windows shows the
``·`` and accented units correctly.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING, Any

from emgteach.i18n import tr

if TYPE_CHECKING:
    from collections.abc import Mapping
    from os import PathLike

__all__ = ["write_analysis_csv"]


def _fatigue_verdict(result: Mapping[str, Any]) -> str:
    sign = int(result.get("fat_slope_sign", 0))
    if sign < 0:
        return tr("fatigue (MDF decreasing)")
    if sign > 0:
        return tr("no fatigue (MDF stable/increasing)")
    return tr("undetermined")


def write_analysis_csv(
    result: Mapping[str, Any], path: str | PathLike[str]
) -> None:
    """Write an analysis ``result`` to ``path`` as CSV.

    Parameters
    ----------
    result : mapping
        The dictionary emitted by :class:`AnalysisWorker` (or a subset
        of it). Missing keys are tolerated and written as blanks/zeros.
    path : str or path-like
        Destination file. Overwritten if it exists.
    """
    full_dur = float(result.get("full_duration_s", result.get("duration", 0.0)))
    roi_a = result.get("roi_start_s")
    roi_b = result.get("roi_end_s")
    if roi_a is not None and roi_b is not None and (
        float(roi_a) > 0.0 or float(roi_b) < full_dur - 1e-6
    ):
        window = tr("{a:.2f}-{b:.2f} s of {d:.1f} s").format(
            a=float(roi_a), b=float(roi_b), d=full_dur
        )
    else:
        window = tr("whole recording")

    summary = [
        (tr("File"), str(result.get("edf_path", ""))),
        (tr("Channel"), str(result.get("channel_name", ""))),
        (tr("Sampling rate (Hz)"), f"{float(result.get('fs', 0.0)):.0f}"),
        (tr("Analysed window"), window),
        (tr("Duration (s)"), f"{float(result.get('duration', 0.0)):.3f}"),
        (tr("Global RMS (mV)"), f"{float(result.get('rms_global', 0.0)):.6f}"),
        (tr("MNF (Hz)"), f"{float(result.get('mnf', 0.0)):.3f}"),
        (tr("MDF (Hz)"), f"{float(result.get('mdf', 0.0)):.3f}"),
        ("iEMG (mV*s)", f"{float(result.get('iemg', 0.0)):.4f}"),
        (tr("MDF slope (Hz/s)"), f"{float(result.get('mdf_slope', 0.0)):.5f}"),
        (tr("MDF slope (Hz/min)"), f"{float(result.get('fat_slope_per_min', 0.0)):.4f}"),
        (tr("MDF R2"), f"{float(result.get('fat_r_squared', 0.0)):.4f}"),
        (tr("MDF decline (%)"), f"{float(result.get('fat_pct_decline', 0.0)):.3f}"),
        (tr("Fatigue"), _fatigue_verdict(result)),
    ]

    t_seg = result.get("t_seg", [])
    rms_seg = result.get("rms_seg", [])
    mdf_seg = result.get("mdf_seg", [])

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        f.write("# emgteach analysis export\n")
        for label, value in summary:
            f.write(f"# {label}: {value}\n")
        f.write("#\n# " + tr("Per-segment metrics") + "\n")
        writer = csv.writer(f)
        writer.writerow(["t_s", "rms_mv", "mdf_hz"])
        for t, rms, mdf in zip(t_seg, rms_seg, mdf_seg, strict=False):
            writer.writerow([f"{float(t):.4f}", f"{float(rms):.6f}", f"{float(mdf):.4f}"])
