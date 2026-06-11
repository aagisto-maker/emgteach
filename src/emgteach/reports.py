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
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "build_session_report",
    "git_commit_hash",
]

_HEADER_BG = colors.HexColor("#1a2a3a")
_ROW_ALT = colors.HexColor("#eef3f8")


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
    if sign < 0:
        return f"Sí — la MDF desciende con el tiempo ({slope:+.2f} Hz/s)"
    if sign > 0:
        return f"No — la MDF se mantiene o aumenta ({slope:+.2f} Hz/s)"
    return "Indeterminada (señal corta o constante)"


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
    ax1.set_ylabel("Filtrada (mV)")
    ax1.set_title(f"Señal EMG — canal «{result.get('channel_name', '')}»")

    ax2.plot(times, result["emg_envelope"], color="#D6620C", linewidth=0.9)
    ax2.set_ylabel("Envolvente (mV)")
    ax2.set_xlabel("Tiempo (s)")

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
    story.append(Paragraph("Informe de registro y análisis de EMG", title_style))

    who = ""
    if student:
        who = f"Alumno/a: {student}"
        if student_code:
            who += f" ({student_code})"
    header_lines = [f"Fecha de generación: {generated_at:%Y-%m-%d %H:%M}"]
    if who:
        header_lines.append(who)
    edf_name = Path(str(result.get("edf_path", ""))).name
    if edf_name:
        header_lines.append(f"Archivo: {edf_name}")
    for line in header_lines:
        story.append(Paragraph(line, normal))
    story.append(Spacer(1, 0.4 * cm))

    # Main signal plot with annotations.
    story.append(Image(_render_signal_figure(result), width=16 * cm, height=9.33 * cm))
    story.append(Spacer(1, 0.4 * cm))

    # Metrics.
    story.append(Paragraph("Métricas", h2))
    metrics = [
        ["Métrica", "Valor"],
        ["Duración", f"{float(result.get('duration', 0.0)):.1f} s"],
        ["RMS global", f"{float(result.get('rms_global', 0.0)):.4f} mV"],
        ["Frecuencia media (MNF)", f"{float(result.get('mnf', 0.0)):.1f} Hz"],
        ["Frecuencia mediana (MDF)", f"{float(result.get('mdf', 0.0)):.1f} Hz"],
        ["iEMG", f"{float(result.get('iemg', 0.0)):.3f} mV·s"],
        ["Evidencia de fatiga", _fatigue_text(result)],
    ]
    story.append(_styled_table(metrics))
    story.append(Spacer(1, 0.4 * cm))

    # Configuration used.
    story.append(Paragraph("Configuración utilizada", h2))
    cfg = result.get("config", {})
    config_rows = [
        ["Parámetro", "Valor"],
        ["Frecuencia de muestreo", f"{float(result.get('fs', 0.0)):.0f} Hz"],
        ["Canal", str(result.get("channel_name", ""))],
    ]
    if cfg:
        config_rows += [
            ["Paso-banda", f"{cfg.get('f_low')}-{cfg.get('f_high')} Hz"],
            ["Notch (red)", f"{cfg.get('f_notch')} Hz"],
            ["Envolvente (paso-bajo)", f"{cfg.get('f_env')} Hz"],
            ["Ventana RMS", f"{cfg.get('rms_window_ms')} ms"],
        ]
    config_rows.append(
        ["Dispositivo", device or "no almacenado en el EDF"]
    )
    story.append(_styled_table(config_rows))

    def _footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        parts = [f"emgteach v{version}"]
        if commit:
            parts.append(f"commit {commit}")
        parts.append(f"generado {generated_at:%Y-%m-%d %H:%M}")
        canvas.drawString(2 * cm, 1 * cm, "  ·  ".join(parts))
        canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f"página {doc.page}")
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
