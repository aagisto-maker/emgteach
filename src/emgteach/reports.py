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

from emgteach.i18n import tr

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
    sign = int(result.get("fat_slope_sign", 0))
    slope = float(result.get("mdf_slope", 0.0))
    r2 = float(result.get("fat_r_squared", 0.0))
    decline = float(result.get("fat_pct_decline", 0.0))
    if sign < 0:
        return tr(
            "Yes — MDF falls {slope:+.2f} Hz/s "
            "({decline:.1f}% decline, R²={r2:.2f})"
        ).format(slope=slope, decline=decline, r2=r2)
    if sign > 0:
        return tr(
            "No — MDF stable or rising ({slope:+.2f} Hz/s, R²={r2:.2f})"
        ).format(slope=slope, r2=r2)
    return tr("Undetermined (short or constant signal)")


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


_PANEL_REPORT_TITLES = {
    0: "1A. Raw EMG signal",
    1: "1B. Filtered + rectified EMG signal",
    2: "2. EMG signal envelope",
    3: "3. Envelope normalised to maximum",
    4: "4. Power spectral density (PSD)",
    5: "5. RMS amplitude over time",
    6: "6. Fatigue: median frequency (MDF) vs time",
    7: "7. Amplitude (RMS) vs median frequency (MDF)",
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
        ax.plot(r["frequencies"], r["psd"], color="#0047AB", lw=1.6)
        ax.axvline(r["mnf"], color="#FF8C00", ls="--", lw=1.8,
                   label=f"MNF: {float(r['mnf']):.1f} Hz")
        ax.axvline(r["mdf"], color="#C71585", ls="--", lw=1.8,
                   label=f"MDF: {float(r['mdf']):.1f} Hz")
        ax.set_xlabel("Frecuencia (Hz)", fontsize=8)
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
        ax.scatter(r["t_seg"], r["mdf_seg"], s=18, alpha=0.7, color="#666666",
                   label=tr("MDF per window"))
        if len(r["t_seg"]) >= 2:
            ax.plot(r["t_seg"], r["fat_fitted"], color="#E74C3C", lw=2.2,
                    label=tr("Trend (degree 2)"))
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
    student = str(meta.get("student", "")).strip()
    student_code = str(meta.get("student_code", "")).strip()
    device = str(meta.get("device", "")).strip()

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=16, spaceAfter=6
    )
    normal = styles["Normal"]
    h2 = styles["Heading2"]

    story: list[Any] = []
    story.append(Paragraph(tr("EMG recording and analysis report"), title_style))

    who = ""
    if student:
        who = tr("Student: {name}").format(name=student)
        if student_code:
            who += f" ({student_code})"
    header_lines = [tr("Generated on: {dt:%Y-%m-%d %H:%M}").format(dt=generated_at)]
    if who:
        header_lines.append(who)
    edf_name = Path(str(result.get("edf_path", ""))).name
    if edf_name:
        header_lines.append(tr("File: {name}").format(name=edf_name))
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
        [tr("Global RMS"), f"{float(result.get('rms_global', 0.0)):.4f} mV"],
        [tr("Mean frequency (MNF)"), f"{float(result.get('mnf', 0.0)):.1f} Hz"],
        [tr("Median frequency (MDF)"), f"{float(result.get('mdf', 0.0)):.1f} Hz"],
        ["iEMG", f"{float(result.get('iemg', 0.0)):.3f} mV·s"],
        [tr("Fatigue evidence"), _fatigue_text(result)],
    ]
    story.append(_styled_table(metrics))
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

    n = int(result.get("n_plot", len(result["emg_norm"])))
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
    ax.axhline(float(result["mvc_amplitude_ref"]), color="red", ls="--", lw=1.2)
    ax.set_title(tr("2. Envelope and MVC reference amplitude"), fontsize=9)
    ax.set_ylabel(tr("Amplitude ({units})").format(units=dim), fontsize=8)
    ax.legend(loc="upper right", fontsize=6)
    ax.grid(True, color="#DDDDDD", alpha=0.5)
    ax.tick_params(labelsize=7)

    ax = axes[2]
    ax.fill_between(t, result["emg_norm"][:n], alpha=0.25, color="darkorange")
    ax.plot(t, result["emg_norm"][:n], color="darkorange", lw=1.5)
    ax.axhline(100.0, color="red", ls=":", lw=1.0)
    ax.set_title(tr("3. EMG signal normalised to MVC (% MVC)"), fontsize=9)
    ax.set_ylabel(tr("% MVC"), fontsize=8)
    ax.set_xlabel(tr("Time (s)"), fontsize=8)
    ax.grid(True, color="#DDDDDD", alpha=0.5)
    ax.tick_params(labelsize=7)

    if x_range is not None:
        for tax in (axes[0], axes[1], axes[2]):
            tax.set_xlim(*x_range)

    ax = axes[3]
    apdf = result["apdf"]
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
    student = str(meta.get("student", "")).strip()
    student_code = str(meta.get("student_code", "")).strip()

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=16, spaceAfter=6
    )
    normal = styles["Normal"]
    h2 = styles["Heading2"]

    story: list[Any] = []
    story.append(Paragraph(tr("MVC normalisation and muscle-load report"), title_style))

    header_lines = [tr("Generated on: {dt:%Y-%m-%d %H:%M}").format(dt=generated_at)]
    if student:
        who = tr("Student: {name}").format(name=student)
        if student_code:
            who += f" ({student_code})"
        header_lines.append(who)
    edf_name = Path(str(result.get("edf_path", ""))).name
    if edf_name:
        header_lines.append(tr("File: {name}").format(name=edf_name))
    for line in header_lines:
        story.append(Paragraph(line, normal))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Image(_render_mvc_figure(result, time_range), width=14 * cm, height=21 * cm))

    dim = result.get("dimension", "")
    duration = float(result["tiempo"][-1]) if len(result.get("tiempo", [])) else 0.0
    apdf = result["apdf"]

    def _level_cell(lvl: Any) -> str:
        status = tr("exceeds limit") if lvl.exceeds else tr("within limit")
        return f"{lvl.value:.0f} % MVC  (≤ {lvl.limit:.0f} %) — {status}"

    story.append(PageBreak())
    story.append(Paragraph(tr("Metrics"), h2))
    metrics = [
        [tr("Metric"), tr("Value")],
        [tr("MVC reference:"), f"{float(result.get('mvc_amplitude_ref', 0.0)):.4f} {dim}"],
        [tr("MVC source:"), str(result.get("mvc_source", ""))],
        [tr("Mean activation:"), f"{float(result.get('mean_norm', 0.0)):.1f} % MVC"],
        [tr("Duration"), f"{duration:.1f} s"],
        [f"{tr('Static')} (P10)", _level_cell(apdf.static)],
        [f"{tr('Median')} (P50)", _level_cell(apdf.median)],
        [f"{tr('Peak')} (P90)", _level_cell(apdf.peak)],
    ]
    story.append(_styled_table(metrics))

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
