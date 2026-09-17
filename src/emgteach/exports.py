"""CSV export of an offline-analysis result.

The analysis tab produces a single result dictionary (see
:class:`emgteach.workers.analysis.AnalysisWorker`). This module turns it
into a spreadsheet-friendly CSV so students can re-plot or tabulate the
numbers in Excel/LibreOffice without re-running the app.

The file has these parts:

* a metadata + summary header written as ``#``-prefixed comment lines
  (file name, version, channel, analysed window, the MVC reference and
  every scalar metric, of both muscles when there are two), which
  spreadsheets and :func:`pandas.read_csv` skip with ``comment='#'``;
* the per-segment table (``t_s``, ``rms_mv``, ``mdf_hz``, plus
  ``rms_mv_2`` and ``mdf_hz_2`` with a second muscle) as the CSV body,
  ready to import and plot directly;
* and, when the analysis found them, one block per table the report
  prints — the contractions and the co-activation windows — each after a
  blank line and a ``#`` heading.

The separator and the decimal mark follow the interface's language
(:func:`csv_dialect`): a comma and a point in English, a semicolon and a
comma in Spanish, which is what a spreadsheet set to each locale expects —
with the English dialect, Excel in Spanish opened everything in one column.
It is written UTF-8 with BOM (``utf-8-sig``) so Excel on Windows shows the
``·`` and accented units correctly.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any

from emgteach.fatigue import FATIGUE, INCONCLUSIVE, NO_FATIGUE
from emgteach.i18n import get_language, tr
from emgteach.phases import NO_CALIBRATION, reference_source_text

if TYPE_CHECKING:
    from collections.abc import Mapping
    from os import PathLike

__all__ = ["csv_dialect", "write_analysis_csv"]


def csv_dialect() -> tuple[str, str]:
    """``(separator, decimal mark)`` of the CSV in the active language."""
    return (";", ",") if get_language() == "es" else (",", ".")


def _app_version() -> str:
    try:
        import emgteach

        return str(getattr(emgteach, "__version__", "?"))
    except Exception:  # pragma: no cover — defensive
        return "?"


def _fatigue_verdict(result: Mapping[str, Any], suffix: str = "") -> str:
    verdict = result.get("fat_verdict" + suffix, INCONCLUSIVE)
    if verdict == FATIGUE:
        return tr("fatigue (MDF decreasing)")
    if verdict == NO_FATIGUE:
        return tr("no fatigue (MDF stable/increasing)")
    return tr("not conclusive (the MDF trend does not fit)")


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
    sep, dec = csv_dialect()

    def num(x: Any, fmt: str) -> str:
        """A number in the file's dialect; a missing one is a blank."""
        if x is None:
            return ""
        return format(float(x), fmt).replace(".", dec)

    full_dur = float(result.get("full_duration_s", result.get("duration", 0.0)))
    segments = result.get("roi_segments")
    roi_a = result.get("roi_start_s")
    roi_b = result.get("roi_end_s")
    if segments and len(segments) > 1:
        frag_txt = "; ".join(f"{num(a, '.2f')}-{num(b, '.2f')}" for a, b in segments)
        window = tr("{n} fragments: {list} s").format(n=len(segments), list=frag_txt)
    elif roi_a is not None and roi_b is not None and (
        float(roi_a) > 0.0 or float(roi_b) < full_dur - 1e-6
    ):
        window = tr("{a:.2f}-{b:.2f} s of {d:.1f} s").format(
            a=float(roi_a), b=float(roi_b), d=full_dur
        ).replace(".", dec)
    else:
        window = tr("whole recording")

    name_1 = str(result.get("channel_name", ""))
    name_2 = str(result.get("channel_name_2") or "")
    dos = bool(name_2) and result.get("mnf_2") is not None

    summary: list[tuple[str, str]] = [
        # The name alone: the full path carries the operator's user name.
        (tr("File"), Path(str(result.get("edf_path", ""))).name),
        (tr("Channel"), name_1),
    ]
    if name_2:
        summary.append((tr("Second channel"), name_2))
    summary += [
        (tr("Sampling rate (Hz)"), num(result.get("fs", 0.0), ".0f")),
        (tr("Analysed window"), window),
        (tr("Duration (s)"), num(result.get("duration", 0.0), ".3f")),
    ]
    k = (result.get("detection") or {}).get("k")
    if k is not None:
        # Beside the window it helped decide: the contractions, and the
        # co-activation windows read off them, move with it.
        summary.insert(len(summary) - 2, (tr("Detection sensitivity (k)"), num(k, ".1f")))

    # One block of metrics per muscle; with one muscle the labels are bare,
    # with two each carries its muscle's name.
    picos = result.get("task_peak_pct", {}) or {}
    reps = result.get("cal_reps", {}) or {}
    for suffix, name, canal in (("", name_1, 0), ("_2", name_2, 1)):
        if suffix and not dos:
            break
        tag = f" [{name}]" if dos else ""
        ref = result.get("mvc_ref" + suffix)
        if ref:
            fuente = reference_source_text(
                str(result.get("mvc_ref_source" + suffix, NO_CALIBRATION)),
                len(reps.get(canal, ()) or ()),
            )
            summary.append((tr("MVC reference (mV)") + tag, f"{num(ref, '.4f')} ({fuente})"))
            pico = picos.get(name)
            if pico is not None:
                summary.append((tr("Task maximum (% MVC)") + tag, num(pico, ".0f")))
        summary += [
            (tr("Global RMS (mV)") + tag, num(result.get("rms_global" + suffix, 0.0), ".6f")),
            (tr("MNF (Hz)") + tag, num(result.get("mnf" + suffix, 0.0), ".3f")),
            (tr("MDF (Hz)") + tag, num(result.get("mdf" + suffix, 0.0), ".3f")),
            (tr("iEMG (mV*s)") + tag, num(result.get("iemg" + suffix, 0.0), ".4f")),
            (tr("MDF slope (Hz/s)") + tag, num(result.get("mdf_slope" + suffix, 0.0), ".5f")),
            (tr("MDF slope (Hz/min)") + tag,
             num(result.get("fat_slope_per_min" + suffix, 0.0), ".4f")),
            (tr("MDF R2") + tag, num(result.get("fat_r_squared" + suffix, 0.0), ".4f")),
            (tr("MDF decline (%)") + tag, num(result.get("fat_pct_decline" + suffix, 0.0), ".3f")),
            (tr("Fatigue") + tag, _fatigue_verdict(result, suffix)),
        ]

    t_seg = result.get("t_seg", [])
    rms_seg = result.get("rms_seg", [])
    mdf_seg = result.get("mdf_seg", [])
    rms_seg_2 = result.get("rms_seg_2") if dos else None
    mdf_seg_2 = result.get("mdf_seg_2") if dos else None
    con_segunda = (
        rms_seg_2 is not None and mdf_seg_2 is not None
        and len(rms_seg_2) == len(t_seg) and len(mdf_seg_2) == len(t_seg)
    )

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        f.write(f"# emgteach analysis export (emgteach v{_app_version()})\n")
        f.write("# " + tr("Separator: {sep} — decimal: {dec}").format(sep=sep, dec=dec) + "\n")
        for label, value in summary:
            f.write(f"# {label}: {value}\n")
        f.write("#\n# " + tr("Per-segment metrics") + "\n")
        writer = csv.writer(f, delimiter=sep)
        cab = ["t_s", "rms_mv", "mdf_hz"]
        if con_segunda:
            cab += ["rms_mv_2", "mdf_hz_2"]
        writer.writerow(cab)
        for i, (t, rms, mdf) in enumerate(zip(t_seg, rms_seg, mdf_seg, strict=False)):
            fila = [num(t, ".4f"), num(rms, ".6f"), num(mdf, ".4f")]
            if con_segunda:
                fila += [num(rms_seg_2[i], ".6f"), num(mdf_seg_2[i], ".4f")]
            writer.writerow(fila)

        # The tables the report prints, as blocks a spreadsheet can take one
        # at a time: the contractions, and the co-activation windows.
        filas = result.get("contractions") or []
        if filas:
            f.write("\n# " + tr("Contractions") + "\n")
            writer.writerow(["n", "start_s", "duration_s", "muscle", "rms_mv",
                             "peak_pct", "mdf_hz", "emd_ms"])
            for c in filas:
                writer.writerow([
                    str(c.n), num(c.start_s, ".3f"), num(c.duration_s, ".3f"),
                    str(c.muscle), num(c.rms_mv, ".6f"), num(c.peak_pct, ".1f"),
                    num(c.mdf_hz, ".2f"), num(c.emd_ms, ".1f"),
                ])
        coact = result.get("coactivation") or []
        if coact:
            f.write("\n# " + tr("Co-activation (Falconer-Winter)") + "\n")
            writer.writerow(["window", "start_s", "end_s", "mean_1_pct", "mean_2_pct",
                             "index_pct", "note"])
            for res in coact:
                writer.writerow([
                    str(res.label), num(res.window_s[0], ".3f"), num(res.window_s[1], ".3f"),
                    num(res.mean_1, ".1f"), num(res.mean_2, ".1f"), num(res.index, ".1f"),
                    str(res.reason or ""),
                ])
