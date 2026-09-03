"""PDF session reports for EMG recordings.

Builds a one-click, self-contained PDF from the offline-analysis result
dictionary produced by :class:`emgteach.workers.AnalysisWorker`:

- a header (title, generation date, optional student name/code, source
  file),
- the main signal plot (filtered EMG + envelope) with the event
  annotations marked,
- a metrics table (RMS, MNF, MDF, fatigue evidence, IEMG, duration),
- the processing configuration that was used (filters, sampling rate,
  channel),
- a reproducible footer (package version, git commit, generation
  timestamp).

The layout uses ``reportlab``; the signal figure is rendered with
matplotlib's Agg backend into an in-memory PNG. The module is therefore
Qt-free and unit-testable without a display.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from emgteach.fatigue import FATIGUE, INCONCLUSIVE, NO_FATIGUE
from emgteach.figures import draw_emd_note, draw_spectrum_before_filter
from emgteach.i18n import tr
from emgteach.mvc import (
    AUTO_COLOR,
    NO_LOAD_MSG,
    mark_excess_over_100,
    overlay_curves,
)
from emgteach.phases import NO_CALIBRATION, reference_source_text
from emgteach.profiles import EMG_PROFILE

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "build_mvc_report",
    "build_session_report",
    "git_commit_hash",
]

_HEADER_BG = colors.HexColor("#1a2a3a")
_ROW_ALT = colors.HexColor("#eef3f8")

# Distinct colour per Jonsson load level (matches the MVC tab); out-of-range
# values get a red ring.
_LEVEL_COLORS = {"static": "#2E86C1", "median": "#E67E22", "peak": "#8E44AD"}
_OUT_COLOR = "#cc0000"


def git_commit_hash(short: bool = True) -> str | None:
    """Return the current git commit hash, or ``None`` if unavailable.

    Runs ``git rev-parse`` in the package directory, so it resolves the
    hash when running from a source checkout and quietly returns ``None``
    when the package was installed without the repository (e.g. a wheel).
    """
    cmd = ["git", "rev-parse"]
    if short:
        cmd.append("--short")
    cmd.append("HEAD")
    try:
        proc = subprocess.run(
            cmd,
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:  # pragma: no cover — git missing / sandboxed
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _app_version() -> str:
    try:
        import emgteach

        return getattr(emgteach, "__version__", "?")
    except Exception:  # pragma: no cover — defensive
        return "?"


def _fatigue_text(result: Mapping[str, Any]) -> str:
    slope = float(result.get("mdf_slope", 0.0))
    r2 = float(result.get("fat_r_squared", 0.0))
    decline = float(result.get("fat_pct_decline", 0.0))
    verdict = result.get("fat_verdict", INCONCLUSIVE)
    if verdict == FATIGUE:
        return tr(
            "Yes — MDF falls {slope:+.2f} Hz/s "
            "({decline:.1f}% decline, R²={r2:.2f})"
        ).format(slope=slope, decline=decline, r2=r2)
    if verdict == NO_FATIGUE:
        return tr(
            "No — MDF stable or rising ({slope:+.2f} Hz/s, R²={r2:.2f})"
        ).format(slope=slope, r2=r2)
    # The report is what the student hands in, so this cannot read as "no".
    return tr(
        "Not conclusive — the trend does not fit ({slope:+.2f} Hz/s, R²={r2:.2f}). "
        "Fatigue needs a contraction held long enough for the trend to show."
    ).format(slope=slope, r2=r2)


def _render_signal_figure(result: Mapping[str, Any]) -> BytesIO:
    """Render the filtered EMG + envelope with markers into a PNG buffer."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7.2, 4.2), dpi=150)
    FigureCanvasAgg(fig)
    ax1, ax2 = fig.subplots(2, 1, sharex=True)

    times = result["times"]
    markers = list(result.get("markers", []))

    ax1.plot(times, result["emg_filtered"], color="#4169E1", linewidth=0.6)
    ax1.set_ylabel(tr("Filtered (mV)"))
    ax1.set_title(
        tr("EMG signal — channel «{name}»").format(name=result.get("channel_name", ""))
    )

    ax2.plot(times, result["emg_envelope"], color="#D6620C", linewidth=0.9)
    ax2.set_ylabel(tr("Envelope (mV)"))
    ax2.set_xlabel(tr("Time (s)"))

    for ax in (ax1, ax2):
        ax.grid(True, alpha=0.3)
        ax.set_xlim(float(times[0]), float(times[-1]))
        for t_mark, _lbl in markers:
            ax.axvline(t_mark, color="#E67E22", linestyle="--", linewidth=1.0, alpha=0.8)

    ymax = ax1.get_ylim()[1]
    for t_mark, lbl in markers:
        ax1.text(
            t_mark, ymax, str(lbl)[:14], fontsize=6, rotation=90,
            va="top", ha="right", color="#E67E22",
        )

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf


# Report panel titles keyed by canonical panel index (0-7). The display
# numbers match the teaching renumbering used in the Analysis tab: the three
# teaching panels are 1A/2/3 and the rest 4-8.
_PANEL_REPORT_TITLES = {
    0: "1A. Raw EMG signal",
    1: "4. Filtered + rectified EMG signal",
    2: "5. EMG signal envelope",
    3: "2. Envelope normalised to maximum",
    4: "3. Power spectral density (PSD)",
    5: "6. RMS amplitude over time",
    6: "7. Fatigue: median frequency (MDF) vs time",
    7: "8. Amplitude (RMS) vs median frequency (MDF)",
    # 8 is titled by overlay_curves(), which also picks its unit.
    8: "9. Overlaid envelopes (agonist/antagonist)",
    9: "10. EMG vs MMG (electrical vs mechanical)",
    10: "11. Tremor — accelerometer spectrum",
    11: "12. Movement vs EMG (limb kinematics)",
}


def _draw_report_markers(ax: Any, markers: list, x0: float, x1: float) -> None:
    for t_mark, _lbl in markers:
        if x0 <= float(t_mark) <= x1:
            ax.axvline(float(t_mark), color="#E67E22", ls="--", lw=1.0, alpha=0.8)


def _draw_analysis_panel(
    fig: Any, ax: Any, idx: int, result: Mapping[str, Any],
    x_range: tuple[float, float] | None = None,
) -> None:
    """Draw one analysis panel (0-7) onto ``ax``, mirroring the on-screen
    panels of the Analysis tab so the report shows the same graphs.

    ``x_range`` restricts the time axis of the time-domain panels (0-3, 5, 6)
    to ``(start, end)`` seconds; ``None`` uses the whole recording. The PSD (4)
    and RMS-vs-MDF (7) panels are not time-domain and ignore it.
    """
    r = result
    times = r["times"]
    x0, x1 = float(times[0]), float(times[-1])
    if x_range is not None:
        x0, x1 = float(x_range[0]), float(x_range[1])
    markers = list(r.get("markers", []))
    grid = dict(ls="--", color="#DDDDDD", alpha=0.8)

    if idx == 0:
        ax.plot(times, r["emg_raw"], color="#333333", lw=0.8, alpha=0.7)
        ax.set_ylabel(tr("Amplitude (mV)"), fontsize=8)
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_xlim(x0, x1)
        _draw_report_markers(ax, markers, x0, x1)
    elif idx == 1:
        ax.plot(times, r["emg_filtered"], color="#1f77b4", lw=1.0,
                label=tr("Filtered (20-450 Hz)"))
        ax.plot(times, r["emg_rectified"], color="#d62728", lw=1.0, alpha=0.9,
                label=tr("Rectified"))
        ax.set_ylabel(tr("Amplitude (mV)"), fontsize=8)
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_xlim(x0, x1)
        ax.legend(loc="upper right", fontsize=7)
        _draw_report_markers(ax, markers, x0, x1)
    elif idx == 2:
        ax.plot(times, r["emg_rectified"], color="#E74C3C", lw=1.0, alpha=0.6,
                label=tr("Rectified"))
        ax.plot(times, r["emg_envelope"], color="#9467bd", lw=1.8,
                label=tr("LP envelope"))
        ax.plot(times, r["rms_sliding"], color="#2ca02c", lw=1.3, ls="--",
                label=tr("RMS envelope"))
        ax.set_ylabel(tr("Amplitude (mV)"), fontsize=8)
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_xlim(x0, x1)
        ax.legend(loc="upper right", fontsize=7)
        _draw_report_markers(ax, markers, x0, x1)
    elif idx == 3:
        ax.plot(times, r["emg_envelope_normalised"], color="#9467bd", lw=1.6,
                label=tr("Normalised envelope (max=1)"))
        ax.axhline(1.0, color="#E74C3C", ls=":", lw=1.3, alpha=0.8)
        ax.set_ylabel(tr("Amplitude (0-1)"), fontsize=8)
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_xlim(x0, x1)
        ax.set_ylim(0, 1.15)
        ax.legend(loc="upper right", fontsize=7)
        _draw_report_markers(ax, markers, x0, x1)
    elif idx == 4:
        if r.get("psd_2") is not None:
            n1 = r.get("channel_name") or tr("Muscle {n}").format(n=1)
            n2 = r.get("channel_name_2") or tr("Muscle {n}").format(n=2)
            ax.plot(r["frequencies"], r["psd"], color="#4169E1", lw=1.6,
                    label=f"{n1}  (MDF {float(r['mdf']):.0f} Hz)")
            ax.plot(r["frequencies_2"], r["psd_2"], color="#D62728", lw=1.6,
                    label=f"{n2}  (MDF {float(r['mdf_2']):.0f} Hz)")
            ax.axvline(r["mdf"], color="#4169E1", ls="--", lw=1.2, alpha=0.8)
            ax.axvline(r["mdf_2"], color="#D62728", ls="--", lw=1.2, alpha=0.8)
        else:
            draw_spectrum_before_filter(ax, r)
            ax.plot(r["frequencies"], r["psd"], color="#0047AB", lw=1.6,
                    label=tr("After the filter"))
            ax.axvline(r["mnf"], color="#FF8C00", ls="--", lw=1.8,
                       label=f"MNF: {float(r['mnf']):.1f} Hz")
            ax.axvline(r["mdf"], color="#C71585", ls="--", lw=1.8,
                       label=f"MDF: {float(r['mdf']):.1f} Hz")
        ax.set_xlabel(tr("Frequency (Hz)"), fontsize=8)
        ax.set_ylabel("PSD (mV²/Hz)", fontsize=8)
        ax.set_xlim(0, float(r.get("f_high", 450)) + 50)
        ax.legend(fontsize=7)
    elif idx == 5:
        ax.plot(r["t_seg"], r["rms_seg"], color="#2ca02c", lw=1.3, marker="o", ms=3,
                label=tr("RMS per 1 s window"))
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_ylabel("RMS (mV)", fontsize=8)
        ax.set_xlim(x0, x1)
        ax.legend(fontsize=7)
        _draw_report_markers(ax, markers, x0, x1)
    elif idx == 6:
        dos = r.get("mdf_seg_2") is not None
        n1 = r.get("channel_name") or tr("Muscle {n}").format(n=1)
        ax.scatter(r["t_seg"], r["mdf_seg"], s=18, alpha=0.7,
                   color="#4169E1" if dos else "#666666",
                   label=(tr("{muscle}: MDF per window").format(muscle=n1)
                          if dos else tr("MDF per window")))
        if len(r["t_seg"]) >= 2:
            ax.plot(r["t_seg"], r["fat_fitted"],
                    color="#4169E1" if dos else "#E74C3C", lw=2.2,
                    label=(tr("{muscle}: trend").format(muscle=n1)
                           if dos else tr("Trend (degree 2)")))
        if dos:
            n2 = r.get("channel_name_2") or tr("Muscle {n}").format(n=2)
            ax.scatter(r["t_seg_2"], r["mdf_seg_2"], s=18, alpha=0.7,
                       color="#D62728",
                       label=tr("{muscle}: MDF per window").format(muscle=n2))
            if len(r["t_seg_2"]) >= 2:
                ax.plot(r["t_seg_2"], r["fat_fitted_2"], color="#D62728", lw=2.2,
                        label=tr("{muscle}: trend").format(muscle=n2))
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_ylabel("MDF (Hz)", fontsize=8)
        ax.set_xlim(x0, x1)
        ax.legend(fontsize=7)
        _draw_report_markers(ax, markers, x0, x1)
    elif idx == 7:
        sc = ax.scatter(r["mdf_seg"], r["rms_seg"], c=r["t_seg"], cmap="viridis",
                        s=45, alpha=0.8, zorder=3)
        ax.plot(r["rms_mdf_range"], r["rms_mdf_fitted"], color="#E74C3C", lw=2.2,
                label=tr("Degree-2 fit"))
        cbar = fig.colorbar(sc, ax=ax, orientation="vertical", pad=0.02)
        cbar.set_label(tr("Time (s)"), fontsize=8)
        cbar.ax.tick_params(labelsize=7)
        ax.set_xlabel("MDF (Hz)", fontsize=8)
        ax.set_ylabel("RMS (mV)", fontsize=8)
        ax.legend(fontsize=7)
    elif idx == 8:
        # Each muscle against its own maximum — see the same panel in the
        # analysis tab for why two muscles must never share a millivolt axis.
        # Same rule as the screen, decided in one place: this is the figure
        # the student hands in, so it must not be able to disagree with the
        # panel it was read from.
        curve1, curve2 = overlay_curves(r)
        ax.plot(times, curve1.data, color="#4169E1", lw=1.6,
                label=str(r.get("channel_name") or tr("Muscle {n}").format(n=1)))
        if curve2 is not None:
            ax.plot(times, curve2.data, color="#D62728", lw=1.6,
                    label=str(r.get("channel_name_2")
                              or tr("Muscle {n}").format(n=2)))
        ax.set_ylabel(curve1.ylabel, fontsize=8)
        mark_excess_over_100(ax, curve1.ylabel)
        if curve1.warning:
            ax.set_title(ax.get_title(), pad=16)
            ax.text(0.5, 1.005, curve1.warning, transform=ax.transAxes,
                    ha="center", va="bottom", fontsize=6.5,
                    color="#B0243A")
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_xlim(x0, x1)
        ax.legend(loc="upper right", fontsize=7)
        _draw_report_markers(ax, markers, x0, x1)
    elif idx == 9:
        emg_lbl = r.get("channel_name") or "EMG"
        ax.plot(times, r["emg_envelope"], color="#4169E1", lw=1.5,
                label=tr("EMG — {ch} (electrical)").format(ch=emg_lbl))
        mmg = r.get("acc_mmg_envelope")
        if mmg is not None:
            ax2 = ax.twinx()
            ax2.plot(times, mmg, color="#2ca02c", lw=1.4,
                     label=tr("MMG envelope (mechanical)"))
            ax2.set_ylabel(tr("MMG (g)"), fontsize=8, color="#2ca02c")
            ax2.tick_params(axis="y", labelsize=7, colors="#2ca02c")
            ax2.set_xlim(x0, x1)
        ax.set_ylabel(tr("EMG (mV)"), fontsize=8, color="#4169E1")
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_xlim(x0, x1)
        ax.legend(loc="upper left", fontsize=7)
        _draw_report_markers(ax, markers, x0, x1)
    elif idx == 10:
        freqs = r.get("acc_tremor_freqs")
        psd = r.get("acc_tremor_psd")
        if freqs is not None and psd is not None:
            ax.plot(freqs, psd, color="#8c564b", lw=1.5)
            peak = float(r.get("acc_tremor_peak_hz", 0.0))
            if peak > 0:
                ax.axvline(peak, color="#E74C3C", ls="--", lw=1.6,
                           label=tr("Peak: {hz:.1f} Hz").format(hz=peak))
                ax.legend(fontsize=7)
            ax.set_xlim(0, 25)
        ax.set_xlabel(tr("Frequency (Hz)"), fontsize=8)
        ax.set_ylabel("PSD (g²/Hz)", fontsize=8)
    elif idx == 11:
        emg_lbl = r.get("channel_name") or "EMG"
        ax.plot(times, r["emg_envelope"], color="#4169E1", lw=1.5,
                label=tr("EMG — {ch} (electrical)").format(ch=emg_lbl))
        move = r.get("acc_movement_envelope")
        if move is not None:
            ax2 = ax.twinx()
            ax2.plot(times, move, color="#D35400", lw=1.4,
                     label=tr("Movement (limb kinematics)"))
            ax2.set_ylabel(tr("Movement (a.u.)"), fontsize=8, color="#D35400")
            ax2.tick_params(axis="y", labelsize=7, colors="#D35400")
            ax2.set_xlim(x0, x1)
            draw_emd_note(ax, r)
        ax.set_ylabel(tr("EMG (mV)"), fontsize=8, color="#4169E1")
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.set_xlim(x0, x1)
        ax.legend(loc="upper left", fontsize=7)
        _draw_report_markers(ax, markers, x0, x1)

    ax.set_title(tr(_PANEL_REPORT_TITLES.get(idx, "")), fontsize=9)
    ax.tick_params(labelsize=7)
    ax.grid(True, **grid)


def _render_one_panel_figure(
    result: Mapping[str, Any], idx: int,
    x_range: tuple[float, float] | None = None,
) -> BytesIO:
    """Render a single analysis panel into a PNG buffer."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7.2, 2.9), dpi=150)
    FigureCanvasAgg(fig)
    ax = fig.subplots(1, 1)
    _draw_analysis_panel(fig, ax, idx, result, x_range)
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf


def _styled_table(data: list[list[str]]) -> Table:
    table = Table(data, hAlign="LEFT", colWidths=[7 * cm, 8 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _seccion_contracciones(story: list, result: Mapping[str, Any], h2, normal) -> None:
    """One row per contraction, as on screen.

    This is the table a laboratory report is built from; without it the
    student copies numbers off a screenshot. Same rows, same columns, same
    rounding as the tab, so the two cannot be compared and found different.
    """
    filas = result.get("contractions") or []
    if not filas:
        return
    dos = bool(result.get("channel_name_2"))
    con_emd = any(f.emd_ms is not None for f in filas)
    story.append(Paragraph(tr("Contractions"), h2))
    cab = ["#", tr("Start (s)"), tr("Duration (s)")]
    if dos:
        cab.append(tr("Muscle"))
    cab += [tr("RMS (mV)"), tr("Peak (% MVC)"), tr("MDF (Hz)")]
    if con_emd:
        cab.append(tr("EMD (ms)"))
    rows = [cab]
    for f in filas:
        fila = [str(f.n), f"{f.start_s:.1f}", f"{f.duration_s:.2f}"]
        if dos:
            fila.append(str(f.muscle))
        fila += [
            f"{f.rms_mv:.3f}",
            "" if f.peak_pct is None else f"{f.peak_pct:.0f}",
            "" if f.mdf_hz is None else f"{f.mdf_hz:.0f}",
        ]
        if con_emd:
            fila.append("" if f.emd_ms is None else f"{f.emd_ms:.0f}")
        rows.append(fila)
    story.append(_styled_table(rows))
    emd = result.get("emd_ms_mean")
    if emd is not None:
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(
            tr("Electromechanical delay: {ms:.0f} ms (mean of {n})").format(
                ms=float(emd), n=sum(1 for f in filas if f.emd_ms is not None)),
            normal,
        ))
    story.append(Spacer(1, 0.4 * cm))


def _seccion_calibracion(story: list, result: Mapping[str, Any], h2, normal) -> None:
    """The reference, and everything the application knows about it.

    One row per muscle: the value, where it came from and how many
    repetitions counted; what the task reached against it, sustained over the
    same half second the reference is measured on; and, when that crosses the
    limit, the sentence that says the maximum was not one. Then the
    repetitions themselves, with what the other muscle did during each — the
    cross-talk that used to be shown for four seconds in the calibration
    panel and then vanished.
    """
    refs = [
        (result.get("channel_name"), result.get("mvc_ref"),
         result.get("mvc_ref_source", NO_CALIBRATION),
         len(result.get("cal_reps", {}).get(0, ()) or ())),
        (result.get("channel_name_2"), result.get("mvc_ref_2"),
         result.get("mvc_ref_source_2", NO_CALIBRATION),
         len(result.get("cal_reps", {}).get(1, ()) or ())),
    ]
    refs = [r for r in refs if r[0] and r[1]]
    if not refs:
        return
    story.append(Paragraph(tr("Calibration (maximal voluntary contraction)"), h2))
    picos = result.get("task_peak_pct", {}) or {}
    rows = [[tr("Muscle"), tr("Reference"), tr("Source"), tr("Task maximum")]]
    for name, ref, fuente, n_reps in refs:
        pico = picos.get(name)
        rows.append([
            str(name), f"{float(ref):.3f} mV",
            reference_source_text(str(fuente), int(n_reps)),
            "" if pico is None else tr("{pct:.0f} % MVC (sustained {w:.1f} s)").format(
                pct=pico, w=EMG_PROFILE.mvc_peak_window_s),
        ])
    story.append(_styled_table(rows))
    if result.get("mvc_implausible"):
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(tr(
            "The task exceeds the reference by a wide margin: the calibration "
            "did not capture a maximum, so every percentage in this report is "
            "too high in the same proportion. Calibrate again with a genuinely "
            "maximal contraction, against something that cannot move."
        ), normal))

    reps = result.get("cal_rep_values") or {}
    nombres = result.get("cal_channel_names") or {}
    if reps:
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(tr("Calibration repetitions"), normal))
        filas = [[tr("Muscle"), tr("Repetition"), tr("Value"),
                  tr("Other muscle during it")]]
        keep = result.get("cal_keep") or {}
        for idx, valores in sorted(reps.items()):
            nombre = str(nombres.get(idx, tr("Channel {n}").format(n=int(idx) + 1)))
            kept = keep.get(idx)
            for v in valores:
                descartada = kept is not None and v.rep not in kept
                etiqueta = f"{v.rep}" + (f" ({tr('discarded')})" if descartada else "")
                cross = "" if v.crosstalk_pct is None else f"{v.crosstalk_pct:.0f} %"
                filas.append([nombre, etiqueta, f"{v.value_mv:.3f} mV", cross])
        story.append(_styled_table(filas))
    story.append(Spacer(1, 0.4 * cm))


def build_session_report(
    pdf_path: str | Path,
    result: Mapping[str, Any],
    meta: Mapping[str, Any] | None = None,
    panels: list[int] | None = None,
    time_range: tuple[float, float] | None = None,
) -> str:
    """Write a one-page PDF report of an analysed EMG session.

    Parameters
    ----------
    pdf_path : str or pathlib.Path
        Output path for the PDF (parent directory must exist).
    result : mapping
        The analysis-result dictionary from
        :class:`emgteach.workers.AnalysisWorker` (arrays, metrics,
        ``markers`` and ``config``).
    meta : mapping, optional
        Extra fields: ``student`` (str), ``student_code`` (str),
        ``device`` (str), ``generated_at`` (datetime), ``version`` (str)
        and ``commit`` (str). Missing fields are filled in automatically
        (version from the package, commit from git, timestamp from now).
    panels : list of int, optional
        Indices (0-7) of the analysis panels to include as graphs, in the
        order given. When ``None`` (default), the legacy single combined
        signal figure (filtered EMG + envelope) is used instead.
    time_range : tuple of float, optional
        ``(start, end)`` seconds to show on the time-domain panels; ``None``
        (default) plots the whole recording.

    Returns
    -------
    str
        The path written.
    """
    meta = dict(meta or {})
    pdf_path = str(pdf_path)

    generated_at: datetime = meta.get("generated_at") or datetime.now()
    version: str = meta.get("version") or _app_version()
    commit = meta.get("commit", git_commit_hash())
    student_code = str(meta.get("student_code", "")).strip()
    protocol = str(meta.get("protocol", "")).strip()
    device = str(meta.get("device", "")).strip()

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=16, spaceAfter=6
    )
    normal = styles["Normal"]
    h2 = styles["Heading2"]

    story: list[Any] = []
    story.append(Paragraph(tr("EMG recording and analysis report"), title_style))

    # The code alone. The report is what gets handed in and marked, and a
    # name on it is a name in every copy of it.
    header_lines = [tr("Generated on: {dt:%Y-%m-%d %H:%M}").format(dt=generated_at)]
    if student_code:
        header_lines.append(
            tr("Test identifier: {code}").format(code=student_code))
    edf_name = Path(str(result.get("edf_path", ""))).name
    if edf_name:
        header_lines.append(tr("File: {name}").format(name=edf_name))
    if protocol:
        header_lines.append(tr("Protocol: {p}").format(p=protocol))
    for line in header_lines:
        story.append(Paragraph(line, normal))
    story.append(Spacer(1, 0.4 * cm))

    # Graphs: either the chosen analysis panels, or (default) the legacy
    # combined signal figure.
    if panels is None:
        story.append(
            Image(_render_signal_figure(result), width=16 * cm, height=9.33 * cm)
        )
        story.append(Spacer(1, 0.4 * cm))
    elif panels:
        story.append(Paragraph(tr("Graphs"), h2))
        for idx in panels:
            if idx not in _PANEL_REPORT_TITLES:
                continue
            story.append(
                Image(_render_one_panel_figure(result, idx, time_range),
                      width=16 * cm, height=6.44 * cm)
            )
            story.append(Spacer(1, 0.3 * cm))

    # Metrics.
    story.append(Paragraph(tr("Metrics"), h2))
    metrics = [
        [tr("Metric"), tr("Value")],
        [tr("Duration"), f"{float(result.get('duration', 0.0)):.1f} s"],
    ]
    # State the analysed window/fragments explicitly when not the whole file.
    full_dur = float(result.get("full_duration_s", 0.0))
    segments = result.get("roi_segments")
    roi_a = result.get("roi_start_s")
    roi_b = result.get("roi_end_s")
    if segments and len(segments) > 1:
        kept = sum(float(b) - float(a) for a, b in segments)
        frag_txt = "; ".join(f"{float(a):.2f}-{float(b):.2f}" for a, b in segments)
        metrics.append(
            [
                tr("Analysed fragments"),
                tr("{n} fragments ({d:.2f} s of {full:.1f} s): {list} s").format(
                    n=len(segments), d=kept, full=full_dur, list=frag_txt
                ),
            ]
        )
    elif roi_a is not None and roi_b is not None and (
        float(roi_a) > 0.0 or float(roi_b) < full_dur - 1e-6
    ):
        metrics.append(
            [
                tr("Analysed window"),
                tr("{a:.2f}-{b:.2f} s of {d:.1f} s").format(
                    a=float(roi_a), b=float(roi_b), d=full_dur
                ),
            ]
        )
    metrics += [
        [tr("Global RMS"), f"{float(result.get('rms_global', 0.0)):.4f} mV"],
        [tr("Mean frequency (MNF)"), f"{float(result.get('mnf', 0.0)):.1f} Hz"],
        [tr("Median frequency (MDF)"), f"{float(result.get('mdf', 0.0)):.1f} Hz"],
        ["iEMG", f"{float(result.get('iemg', 0.0)):.3f} mV·s"],
        [tr("Fatigue evidence"), _fatigue_text(result)],
    ]
    story.append(_styled_table(metrics))
    story.append(Spacer(1, 0.4 * cm))

    # The calibration, when the recording carries one. Everything the
    # application learned about the reference used to stay in the log, or in
    # a panel that closed itself: which repetitions counted, what the task
    # reached against the maximum, whether the maximum was one at all, and
    # what the other muscle did during each effort. The report is what the
    # student hands in, so this is where it has to be.
    _seccion_calibracion(story, result, h2, normal)
    _seccion_contracciones(story, result, h2, normal)

    # Co-activation, when the recording can support it: two muscles, and an
    # MVC reference for each. The two mean activations go beside every index,
    # never the index alone — see emgteach.coactivation.
    coact = result.get("coactivation")
    if coact:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(tr("Co-activation (Falconer-Winter)"), h2))
        if not result.get("coactivation_from_markers", True):
            story.append(Paragraph(
                f"<font color='#B0243A'>"
                f"{tr('Whole recording — mark the phases for a meaningful value')}"
                f"</font>", normal
            ))
        cab = tr("Mean activation (% MVC)")
        n1 = str(result.get("channel_name") or tr("Muscle {n}").format(n=1))
        n2 = str(result.get("channel_name_2") or tr("Muscle {n}").format(n=2))
        rows = [[tr("Window"), f"{n1} — {cab}", f"{n2} — {cab}",
                 tr("Co-activation index")]]
        for res in coact:
            rows.append([
                # With its seconds: the last window is closed at the
                # end of the effort rather than at the end of the
                # recording, and the report is what gets handed in.
                f"{res.label}  ({res.window_s[0]:.1f}–"  # noqa: RUF001
                f"{res.window_s[1]:.1f} s)".strip(),
                f"{res.mean_1:.0f}",
                f"{res.mean_2:.0f}",
                res.reason or f"{res.index:.0f} %",
            ])
        tabla = Table(rows, hAlign="LEFT",
                      colWidths=[4 * cm, 3.5 * cm, 3.5 * cm, 5 * cm])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tabla)
        story.append(Spacer(1, 0.4 * cm))
    elif result.get("coactivation_reason"):
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(tr("Co-activation (Falconer-Winter)"), h2))
        story.append(Paragraph(str(result["coactivation_reason"]), normal))
        story.append(Spacer(1, 0.4 * cm))

    # Configuration used.
    story.append(Paragraph(tr("Configuration used"), h2))
    cfg = result.get("config", {})
    config_rows = [
        [tr("Parameter"), tr("Value")],
        [tr("Sampling rate"), f"{float(result.get('fs', 0.0)):.0f} Hz"],
        [tr("Channel"), str(result.get("channel_name", ""))],
    ]
    if cfg:
        config_rows += [
            [tr("Band-pass"), f"{cfg.get('f_low')}-{cfg.get('f_high')} Hz"],
            [tr("Notch (mains)"), f"{cfg.get('f_notch')} Hz"],
            [tr("Envelope (low-pass)"), f"{cfg.get('f_env')} Hz"],
            [tr("RMS window"), f"{cfg.get('rms_window_ms')} ms"],
        ]
    config_rows.append(
        [tr("Device"), device or tr("not stored in the EDF")]
    )
    story.append(_styled_table(config_rows))

    def _footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        parts = [f"emgteach v{version}"]
        if commit:
            parts.append(f"commit {commit}")
        parts.append(tr("generated {dt:%Y-%m-%d %H:%M}").format(dt=generated_at))
        canvas.drawString(2 * cm, 1 * cm, "  ·  ".join(parts))
        canvas.drawRightString(
            A4[0] - 2 * cm, 1 * cm, tr("page {n}").format(n=doc.page)
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="Informe EMG",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return pdf_path


def _render_mvc_figure(
    result: Mapping[str, Any], x_range: tuple[float, float] | None = None,
) -> BytesIO:
    """Render the MVC panels (filtered+rectified / envelope / normalised) and
    the muscle-load APDF into a PNG buffer. ``x_range`` restricts the time axis
    of the three time-series panels; the APDF (a distribution) ignores it."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7.0, 10.5), dpi=150, constrained_layout=True)
    FigureCanvasAgg(fig)
    axes = fig.subplots(4, 1)

    ref = result.get("mvc_amplitude_ref")
    norm = result.get("emg_norm")
    n = int(result.get("n_plot", len(result["emg_envelope"])))
    t = result["t_plot"]
    dim = result.get("dimension", "")

    ax = axes[0]
    ax.plot(t, result["emg_filtered"][:n], color="#4169E1", lw=0.6,
            label=tr("Filtered EMG (20-450 Hz)"))
    ax.plot(t, result["emg_rectified"][:n], color="#d62728", lw=0.6, alpha=0.8,
            label=tr("Rectified EMG"))
    ax.set_title(tr("1. Filtered and rectified EMG signal"), fontsize=9)
    ax.set_ylabel(tr("Amplitude ({units})").format(units=dim), fontsize=8)
    ax.legend(loc="upper right", fontsize=6)
    ax.grid(True, color="#DDDDDD", alpha=0.5)
    ax.tick_params(labelsize=7)

    ax = axes[1]
    ax.plot(t, result["emg_envelope"][:n], color="purple", lw=1.5,
            label=tr("LP envelope (zero-phase)"))
    if ref:
        ax.axhline(float(ref), color="red", ls="--", lw=1.2)
    ax.set_title(
        tr("2. Envelope and MVC reference amplitude") if ref
        else tr("2. Envelope (no calibration in this recording)"),
        fontsize=9,
    )
    ax.set_ylabel(tr("Amplitude ({units})").format(units=dim), fontsize=8)
    ax.legend(loc="upper right", fontsize=6)
    ax.grid(True, color="#DDDDDD", alpha=0.5)
    ax.tick_params(labelsize=7)

    ax = axes[2]
    # The report is what the student hands in. A panel that quietly vanished
    # would leave them holding a document that does not say what is missing.
    if norm is None:
        ax.text(0.5, 0.5, tr(NO_LOAD_MSG), ha="center", va="center",
                fontsize=8, color="#666666", wrap=True, transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(tr("3. Signal as % MVC — not available"), fontsize=9)
    else:
        ax.fill_between(t, norm[:n], alpha=0.25, color="darkorange")
        ax.plot(t, norm[:n], color="darkorange", lw=1.5)
        ax.axhline(100.0, color="red", ls=":", lw=1.0)
        ax.set_title(
            tr("3. EMG signal normalised to MVC (% MVC)"), fontsize=9)
        ax.set_ylabel(tr("% MVC"), fontsize=8)
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.grid(True, color="#DDDDDD", alpha=0.5)
        ax.tick_params(labelsize=7)

    if x_range is not None:
        for tax in (axes[0], axes[1], axes[2]):
            tax.set_xlim(*x_range)

    ax = axes[3]
    apdf = result.get("apdf")
    if apdf is None:
        ax.text(0.5, 0.5, tr(NO_LOAD_MSG), ha="center", va="center",
                fontsize=8, color="#666666", wrap=True, transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(
            tr("Muscle-load distribution (APDF, Jonsson)"), fontsize=9)
        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        return buf

    ax.plot(apdf.load, apdf.cumulative, color="#0047AB", lw=1.5)
    for lvl, prob, name in (
        (apdf.static, 10, tr("Static")),
        (apdf.median, 50, tr("Median")),
        (apdf.peak, 90, tr("Peak")),
    ):
        base = _LEVEL_COLORS[lvl.name]
        ax.axhline(prob, color="#cccccc", ls=":", lw=0.6)
        ax.plot([lvl.value], [prob], "o", ms=7, zorder=5,
                markerfacecolor=base, markeredgecolor=base, markeredgewidth=0.6,
                label=f"{name}: {lvl.value:.0f} % (≤{lvl.limit:.0f} %)")
        if lvl.exceeds:
            ax.plot([lvl.value], [prob], "o", ms=16, zorder=6,
                    markerfacecolor="none", markeredgecolor=_OUT_COLOR,
                    markeredgewidth=2.0)
    ax.set_title(tr("Muscle-load distribution (APDF, Jonsson)"), fontsize=9)
    ax.set_xlabel(tr("Load (% MVC)"), fontsize=8)
    ax.set_ylabel(tr("Cumulative % of time"), fontsize=8)
    ax.set_ylim(0, 100)
    # Legend key for the out-of-range marker (the red ring drawn above).
    ax.plot([], [], "o", linestyle="none", markersize=9,
            markerfacecolor="none", markeredgecolor=_OUT_COLOR,
            markeredgewidth=1.8, label=tr("Out of normal range"))
    ax.legend(loc="lower right", fontsize=6)
    ax.grid(True, color="#DDDDDD", alpha=0.5)
    ax.tick_params(labelsize=7)

    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf


def build_mvc_report(
    pdf_path: str | Path,
    result: Mapping[str, Any],
    meta: Mapping[str, Any] | None = None,
    time_range: tuple[float, float] | None = None,
) -> str:
    """Write a one-page PDF report of an MVC normalisation + muscle-load run.

    Mirrors :func:`build_session_report` (header, figure, metrics table,
    reproducible footer) but for the MVC-tab result: the three normalisation
    panels, the Jonsson muscle-load APDF, and a metrics table with the
    static / median / peak load levels against their recommended limits.

    Returns the path written.
    """
    meta = dict(meta or {})
    pdf_path = str(pdf_path)

    generated_at: datetime = meta.get("generated_at") or datetime.now()
    version: str = meta.get("version") or _app_version()
    commit = meta.get("commit", git_commit_hash())
    student_code = str(meta.get("student_code", "")).strip()
    protocol = str(meta.get("protocol", "")).strip()

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=16, spaceAfter=6
    )
    normal = styles["Normal"]
    h2 = styles["Heading2"]

    story: list[Any] = []
    story.append(Paragraph(tr("MVC normalisation and muscle-load report"), title_style))

    header_lines = [tr("Generated on: {dt:%Y-%m-%d %H:%M}").format(dt=generated_at)]
    if student_code:
        header_lines.append(
            tr("Test identifier: {code}").format(code=student_code))
    edf_name = Path(str(result.get("edf_path", ""))).name
    if edf_name:
        header_lines.append(tr("File: {name}").format(name=edf_name))
    if protocol:
        header_lines.append(tr("Protocol: {p}").format(p=protocol))
    for line in header_lines:
        story.append(Paragraph(line, normal))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Image(_render_mvc_figure(result, time_range), width=14 * cm, height=21 * cm))

    dim = result.get("dimension", "")
    duration = float(result["tiempo"][-1]) if len(result.get("tiempo", [])) else 0.0
    apdf = result.get("apdf")
    ref = result.get("mvc_amplitude_ref")

    def _level_cell(lvl: Any) -> str:
        status = tr("exceeds limit") if lvl.exceeds else tr("within limit")
        return f"{lvl.value:.0f} % MVC  (≤ {lvl.limit:.0f} %) — {status}"

    story.append(PageBreak())
    story.append(Paragraph(tr("Metrics"), h2))
    metrics = [
        [tr("Metric"), tr("Value")],
        [tr("MVC reference:"), f"{ref:.4f} {dim}" if ref else tr("none")],
        [
            tr("Reference from:"),
            reference_source_text(
                str(result.get("mvc_ref_source", NO_CALIBRATION)),
                int(result.get("cal_reps_n", 0)),
            ),
        ],
        [tr("Mean activation:"),
         "—" if result.get("mean_norm") is None
         else f"{float(result['mean_norm']):.1f} % MVC"],
        [tr("Duration"), f"{duration:.1f} s"],
    ]
    # Without a reference the three load levels do not exist, so the report
    # says so instead of printing verdicts against limits computed from
    # nothing.
    if apdf is not None:
        metrics += [
            [f"{tr('Static')} (P10)", _level_cell(apdf.static)],
            [f"{tr('Median')} (P50)", _level_cell(apdf.median)],
            [f"{tr('Peak')} (P90)", _level_cell(apdf.peak)],
        ]
    story.append(_styled_table(metrics))
    if apdf is None:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            f"<font color='{AUTO_COLOR}'>{tr(NO_LOAD_MSG)}</font>", normal
        ))

    def _footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        parts = [f"emgteach v{version}"]
        if commit:
            parts.append(f"commit {commit}")
        parts.append(tr("generated {dt:%Y-%m-%d %H:%M}").format(dt=generated_at))
        canvas.drawString(2 * cm, 1 * cm, "  ·  ".join(parts))
        canvas.drawRightString(
            A4[0] - 2 * cm, 1 * cm, tr("page {n}").format(n=doc.page)
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="Informe CVM",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return pdf_path
