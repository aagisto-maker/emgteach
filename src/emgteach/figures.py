"""Drawing helpers shared by the screen panels and the report figures.

Whatever is drawn on both has to come from one place, or the PDF the
student hands in stops matching the panel they were looking at. These take
a matplotlib axis and the analysis result and know nothing about Qt.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from scipy.integrate import trapezoid

# The two muscles' colours are those of charts.py and nowhere else: a colour
# convention copied by hand drifts, and this one carries the whole tab.
from emgteach.charts import COLOUR_1, COLOUR_2
from emgteach.i18n import cifra, tr

#: Below this share of the other muscle's total power a spectrum is drawn
#: faint and its legend says so. A muscle at rest while the other works is
#: some 20 µV against 200 µV of RMS, a hundredfold in power; a weaker but
#: working muscle stays well above this (one bench pair sat at 13 %).
PSD_FAINT_RATIO = 0.02


def spectrum_power(frequencies: Any, psd: Any) -> float:
    """The area under a spectrum: its total power, in mV² for a PSD in mV²/Hz."""
    f = np.asarray(frequencies, dtype=np.float64)
    p = np.asarray(psd, dtype=np.float64)
    n = min(f.size, p.size)
    if n < 2:
        return 0.0
    return float(trapezoid(p[:n], f[:n]))


def relative_spectrum(frequencies: Any, psd: Any) -> np.ndarray:
    """The spectrum scaled to unit area: a density, comparable by shape.

    The PSD goes with the square of the amplitude, so drawn in mV²/Hz the
    height of one muscle against the other compares skin and electrode
    placement — what the % MVC panels exist not to compare — and the
    muscle that contracts less was pinned to the axis. With unit area
    each curve is read by its shape, and the median frequency splits its
    area in two equal halves in both alike: the spectral counterpart of
    normalising the amplitude by the MVC. MDF and MNF are invariant to
    the scaling; nothing computed changes.
    """
    p = np.asarray(psd, dtype=np.float64)
    area = spectrum_power(frequencies, p)
    return p / area if area > 0.0 else p


def _potencia(mv2: float) -> str:
    """Two significant figures, in the language's decimal notation."""
    return cifra(float(f"{mv2:.2g}")) + " mV²"


def draw_spectrum_before_filter(ax: Any, result: Mapping[str, Any]) -> None:
    """The raw spectrum, faint, behind the filtered one.

    The student is told a band-pass and a notch were applied; here they see
    what was taken away — the mains line at 50 Hz, the movement below
    20 Hz. Both spectra are drawn scaled to unit area
    (:func:`relative_spectrum`), and the axis stays scaled to the filtered
    one on purpose: those two features can be tens of times taller, and
    letting them set the scale would flatten the spectrum the panel is
    about. They go off the top, which is the point.
    """
    f = result.get("frequencies_raw")
    p = result.get("psd_raw")
    if f is None or p is None:
        return
    ax.plot(f, relative_spectrum(f, p), color="#9AA5B1", lw=1.0, alpha=0.85,
            label=tr("Before the filter (raw)"))
    psd = np.asarray(result.get("psd", ()), dtype=np.float64)
    ff = result.get("frequencies")
    if ff is None or len(ff) != psd.size:
        ff = f if len(f) == psd.size else None
    top = float(np.max(relative_spectrum(ff, psd))) if psd.size and ff is not None else 0.0
    if top > 0.0:
        ax.set_ylim(0.0, top * 1.35)


def draw_psd_panel(ax: Any, result: Mapping[str, Any], *, lw: float = 1.8,
                   fontsize: int = 8) -> None:
    """Panel 3, on screen and in the report: each spectrum scaled to unit area.

    With two muscles, each curve is a density (:func:`relative_spectrum`)
    with its area shaded and its median frequency as a dashed line that
    splits the shade in two equal halves; the legend carries the MDF and
    the total power in mV², so the power is not lost with the scaling. A
    muscle whose power is under :data:`PSD_FAINT_RATIO` of the other's is
    drawn faint and its legend asks whether it is noise, so a spectrum of
    noise does not pass for a muscle's because it is as tall. With one
    muscle, the raw spectrum goes faintly behind the filtered one, and the
    MNF and the MDF are marked.
    """
    f1 = np.asarray(result["frequencies"], dtype=np.float64)
    p1 = np.asarray(result["psd"], dtype=np.float64)
    a1 = spectrum_power(f1, p1)
    r1 = relative_spectrum(f1, p1)
    if result.get("psd_2") is not None:
        f2 = np.asarray(result["frequencies_2"], dtype=np.float64)
        p2 = np.asarray(result["psd_2"], dtype=np.float64)
        a2 = spectrum_power(f2, p2)
        r2 = relative_spectrum(f2, p2)
        n1 = result.get("channel_name") or tr("Muscle {n}").format(n=1)
        n2 = result.get("channel_name_2") or tr("Muscle {n}").format(n=2)
        faint_1 = a2 > 0.0 and a1 < PSD_FAINT_RATIO * a2
        faint_2 = a1 > 0.0 and a2 < PSD_FAINT_RATIO * a1
        for f, r, a, name, mdf, colour, faint, other, a_other in (
            (f1, r1, a1, n1, result["mdf"], COLOUR_1, faint_1, n2, a2),
            (f2, r2, a2, n2, result["mdf_2"], COLOUR_2, faint_2, n1, a1),
        ):
            label = f"{name} — MDF {float(mdf):.0f} Hz · {_potencia(a)}"
            if faint:
                label += " · " + tr("{pct:.0f} % of {other}'s power: noise?").format(
                    pct=100.0 * a / a_other, other=other)
            alpha = 0.35 if faint else 1.0
            ax.fill_between(f, r, color=colour, alpha=0.05 if faint else 0.12, lw=0)
            ax.plot(f, r, color=colour, lw=lw, alpha=alpha, label=label)
            ax.axvline(float(mdf), color=colour, ls="--", lw=lw * 0.75,
                       alpha=0.8 * alpha)
    else:
        draw_spectrum_before_filter(ax, result)
        ax.fill_between(f1, r1, color="#0047AB", alpha=0.10, lw=0)
        ax.plot(f1, r1, color="#0047AB", lw=lw,
                label=tr("After the filter") + f" · {_potencia(a1)}")
        ax.axvline(float(result["mnf"]), color="#FF8C00", ls="--", lw=lw * 1.1,
                   label=f"MNF: {float(result['mnf']):.1f} Hz")
        ax.axvline(float(result["mdf"]), color="#C71585", ls="--", lw=lw * 1.1,
                   label=f"MDF: {float(result['mdf']):.1f} Hz")
    ax.set_xlabel(tr("Frequency (Hz)"), fontsize=fontsize)
    ax.set_ylabel(tr("Relative spectral density (area 1)"), fontsize=fontsize)
    f_high = result.get("f_high") or (result.get("config") or {}).get("f_high") or 450.0
    ax.set_xlim(0, float(f_high) + 50)
    ax.legend(fontsize=max(6, fontsize - 1))


def draw_raw_panel(ax: Any, result: Mapping[str, Any], *, lw: float = 0.8,
                   fontsize: int = 8) -> Any | None:
    """Panel 1, on screen and in the report: the raw trace of each muscle.

    One muscle is drawn in grey against its amplitude axis. Two get a
    vertical axis each, painted in the muscle's colour and carrying its
    name, as the EMG and the accelerometer do in panels 10 and 12: two
    muscles in millivolts on one axis invite a comparison of heights that
    surface EMG cannot support — the amplitude depends on the skin and fat
    between muscle and electrode — and with an axis each, no two heights
    are ever claimed to share a yardstick. What the panel shows is when
    each muscle fires. Each axis takes its colour from the same variable
    as its trace, so the two cannot drift apart, and both are symmetric
    about zero so that the two zero lines are one.

    Returns the second muscle's axis, or ``None`` with one muscle, so that
    whoever rescales the panel can rescale both.
    """
    times = result["times"]
    raw_2 = result.get("emg_raw_2")
    if raw_2 is None:
        ax.plot(times, result["emg_raw"], color="#333333", lw=lw, alpha=0.7)
        ax.set_ylabel(tr("Amplitude (mV)"), fontsize=fontsize)
        ax.set_xlabel(tr("Time (s)"), fontsize=fontsize)
        return None
    ax_2 = ax.twinx()
    for axis, trace, name, n, colour in (
        (ax, result["emg_raw"], result.get("channel_name"), 1, COLOUR_1),
        (ax_2, raw_2, result.get("channel_name_2"), 2, COLOUR_2),
    ):
        name = name or tr("Muscle {n}").format(n=n)
        data = np.asarray(trace, dtype=np.float64)
        axis.plot(times, data, color=colour, lw=lw, alpha=0.7)
        axis.set_ylabel(tr("{muscle} (mV)").format(muscle=name),
                        fontsize=fontsize, color=colour)
        axis.tick_params(axis="y", labelsize=fontsize - 1, colors=colour)
        finite = data[np.isfinite(data)]
        top = float(np.max(np.abs(finite))) if finite.size else 0.0
        if top > 0.0:
            axis.set_ylim(-1.05 * top, 1.05 * top)
    ax.set_xlabel(tr("Time (s)"), fontsize=fontsize)
    return ax_2


def draw_rms_panel(ax: Any, result: Mapping[str, Any], *, lw: float = 1.5,
                   ms: float = 4, fontsize: int = 8) -> Any | None:
    """Panel 6, on screen and in the report: the RMS of each window.

    One muscle is one green line against its axis. Two get an axis each, in
    the muscle's colour and carrying its name, as in panel 1: RMS is in
    millivolts, and two muscles' millivolts do not share a yardstick. Both
    axes start at zero, so the two floors are one.

    Returns the second muscle's axis, or ``None`` with one muscle, so that
    whoever rescales the panel can rescale both.
    """
    rms_2 = result.get("rms_seg_2")
    if rms_2 is None:
        ax.plot(result["t_seg"], result["rms_seg"], color="#2ca02c", lw=lw,
                marker="o", ms=ms, label=tr("RMS per 1 s window"))
        ax.set_ylabel("RMS (mV)", fontsize=fontsize)
        ax.set_xlabel(tr("Time (s)"), fontsize=fontsize)
        ax.legend(fontsize=fontsize - 1)
        return None
    ax_2 = ax.twinx()
    for axis, t, rms, name, n, colour in (
        (ax, result["t_seg"], result["rms_seg"], result.get("channel_name"), 1,
         COLOUR_1),
        (ax_2, result["t_seg_2"], rms_2, result.get("channel_name_2"), 2,
         COLOUR_2),
    ):
        name = name or tr("Muscle {n}").format(n=n)
        data = np.asarray(rms, dtype=np.float64)
        axis.plot(t, data, color=colour, lw=lw, marker="o", ms=ms)
        axis.set_ylabel(tr("{muscle}: RMS (mV)").format(muscle=name),
                        fontsize=fontsize, color=colour)
        axis.tick_params(axis="y", labelsize=fontsize - 1, colors=colour)
        finite = data[np.isfinite(data)]
        top = float(np.max(finite)) if finite.size else 0.0
        axis.set_ylim(0.0, 1.1 * top if top > 0.0 else 1.0)
    ax.set_xlabel(tr("Time (s)"), fontsize=fontsize)
    return ax_2


def draw_emd_note(ax: Any, result: Mapping[str, Any]) -> None:
    """The mean electromechanical delay, in the corner of the movement panel.

    The number itself lives in the contraction table; this is the reminder
    on the figure that the gap between the two curves has a name and a
    value.
    """
    emd = result.get("emd_ms_mean")
    if emd is None:
        return
    filas = [c for c in (result.get("contractions") or []) if c.emd_ms is not None]
    ax.text(
        0.99, 0.03,
        tr("Electromechanical delay: {ms:.0f} ms (mean of {n})").format(
            ms=float(emd), n=len(filas)),
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=7, color="#D35400",
    )
