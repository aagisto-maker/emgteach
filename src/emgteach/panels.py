"""The analysis panels: one row each, the one place anything about a panel is
written.

The article cites panels by number, so a number has to be the same whenever
its panel is drawn — whatever else is ticked, whatever the practical — and it
can only be that if it is written once. Everything that names a panel is
built from its row here: the title of the plot, on screen and in the report;
the checkbox that shows it; the line of the report dialog that adds it to
the PDF; its tooltip; and the «P#» beside its amplitude buttons.

A title carries the panel's number and name, the muscle when the panel shows
only one, and on a second line its reading, which says what it means that
the curve rises or falls. A panel that has to be explained aloud is badly
drawn; the reading is the explanation, on the figure.

Qt-free: the report and the tools that write the project's documents read
it too.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from emgteach.i18n import tr


@dataclass(frozen=True)
class Panel:
    """One analysis panel.

    ``pid`` is the identity the drawing code and the report use; ``number``
    is what the student, the report and the article see, and the row's place
    in :data:`PANELS` is its place on screen. Every text is an English
    catalogue key without the number, which is added here: ``label`` for the
    checkbox, ``long_name`` for the report dialog, ``name`` for the plot
    title, ``reading`` for the title's second line (``reading_two`` when the
    panel draws two muscles) and ``tooltip``. ``two_key`` is the result entry
    present when the panel draws two muscles: then they are named on its axes
    or in its legend, and otherwise, if ``per_muscle``, in its title.
    """

    pid: int
    number: int
    label: str
    long_name: str
    name: str
    reading: str
    tooltip: str
    reading_two: str = ""
    two_key: str = ""
    per_muscle: bool = True


PANELS: tuple[Panel, ...] = (
    Panel(
        pid=0, number=1, label="Raw", long_name="Raw signal",
        name="Raw EMG signal",
        reading="the trace thickens while the muscle contracts and thins while "
                "it rests",
        reading_two="each muscle against its own axis: read when each one "
                    "fires, not which is taller",
        tooltip="Raw EMG signal, unfiltered; with two muscles, each against "
                "its own axis, in its colour.",
        two_key="emg_raw_2",
    ),
    Panel(
        pid=3, number=2, label="Env. norm.", long_name="Normalised envelope",
        name="Envelope normalised to maximum",
        reading="1 is the highest point of this window, not the MVC: read the "
                "shape, not the height",
        tooltip="Envelope normalised to its maximum (0-1): the activation "
                "time course.",
    ),
    Panel(
        pid=4, number=3, label="PSD", long_name="PSD with MNF/MDF",
        name="Power spectral density (PSD)",
        reading="where the signal's power lies; in grey, what the filter took "
                "away",
        reading_two="each curve has area 1, so the shapes compare; the dashed "
                    "line is each muscle's MDF",
        tooltip="Power spectrum; MNF and MDF summarise its frequency content.",
        two_key="psd_2",
    ),
    Panel(
        pid=1, number=4, label="Filt.+rect.", long_name="Filtered + rectified",
        name="Filtered + rectified EMG signal",
        reading="rectified, every oscillation counts upwards: the taller the "
                "trace, the stronger the activation",
        tooltip="Band-pass filtered (20-450 Hz) and rectified signal.",
    ),
    Panel(
        pid=2, number=5, label="Env. vs RMS", long_name="Envelope vs RMS",
        name="EMG signal envelope",
        reading="the higher the curve, the stronger the activation; the two "
                "lines are two ways of measuring it",
        tooltip="Linear envelope vs the RMS envelope of the signal.",
    ),
    Panel(
        pid=5, number=6, label="RMS/window", long_name="RMS per window",
        name="RMS amplitude over time",
        reading="one point per window: rising at a steady effort means more "
                "motor units, often fatigue",
        reading_two="each muscle against its own axis: read how each one "
                    "evolves, not which is higher",
        tooltip="RMS amplitude per window: how the intensity evolves.",
        two_key="rms_seg_2",
    ),
    Panel(
        pid=6, number=7, label="MDF/time", long_name="MDF vs time (fatigue)",
        name="Fatigue trend: median frequency vs. time",
        reading="a decrease indicates muscle fatigue",
        tooltip="Median frequency over time; a fall indicates fatigue.",
        two_key="mdf_seg_2",
    ),
    Panel(
        pid=7, number=8, label="RMS vs MDF", long_name="RMS vs MDF",
        name="Amplitude vs median frequency",
        reading="the points follow time along the arrow; fatigue moves the "
                "path up and to the left: more amplitude, less frequency",
        tooltip="Amplitude against median frequency, window by window in time "
                "order: fatigue moves the path up and to the left.",
    ),
    Panel(
        pid=8, number=9, label="Env. overlay",
        long_name="Overlaid envelopes (agonist/antagonist)",
        name="Overlaid envelopes (agonist/antagonist)",
        reading="each muscle against its own maximum: one rising as the other "
                "falls is alternation; both up at once, co-activation",
        tooltip="Both channels' envelopes overlaid — agonist/antagonist "
                "coordination (needs a 2nd channel).",
        per_muscle=False,
    ),
    Panel(
        pid=9, number=10, label="EMG vs MMG",
        long_name="EMG vs MMG (electrical vs mechanical)",
        name="EMG vs MMG (electrical vs mechanical)",
        reading="the muscle's vibration (MMG) follows its electrical activity "
                "(EMG)",
        tooltip="Electrical (EMG) vs mechanical (MMG, from the accelerometer "
                "on the muscle) envelope — needs an accelerometer channel.",
    ),
    Panel(
        pid=10, number=11, label="Tremor",
        long_name="Tremor (accelerometer FFT)",
        name="Tremor — accelerometer spectrum",
        reading="the peak is the tremor's frequency; physiological tremor sits "
                "at 8-12 Hz",
        tooltip="Frequency spectrum of the accelerometer with the tremor peak "
                "(physiological ~8-12 Hz) — needs an accelerometer channel.",
        per_muscle=False,
    ),
    Panel(
        pid=11, number=12, label="Move vs EMG",
        long_name="Movement vs EMG (limb kinematics)",
        name="Movement vs EMG (limb kinematics)",
        reading="the EMG rises first and the movement follows: the gap is the "
                "electromechanical delay",
        tooltip="Movement (from the accelerometer on the moving segment) vs "
                "the EMG envelope — movement follows contraction; needs an "
                "accelerometer channel.",
    ),
)

#: Panel 9's reading when it stays in millivolts, for want of an MVC
#: reference for both muscles.
OVERLAY_READING_MV = "in millivolts: read when each one fires, not which is higher"

BY_PID: dict[int, Panel] = {p.pid: p for p in PANELS}


def texts(panel: Panel) -> tuple[str, ...]:
    """Every catalogue key a row holds, for the test that they are translated."""
    return tuple(s for s in (panel.label, panel.long_name, panel.name,
                             panel.reading, panel.reading_two, panel.tooltip) if s)


def panel_label(pid: int) -> str:
    """The checkbox: «3. PSD»."""
    p = BY_PID[pid]
    return f"{p.number}. {tr(p.label)}"


def panel_long_name(pid: int) -> str:
    """The report dialog's line: «3. PSD with MNF/MDF»."""
    p = BY_PID[pid]
    return f"{p.number}. {tr(p.long_name)}"


def panel_tooltip(pid: int) -> str:
    return tr(BY_PID[pid].tooltip)


def muscle_name(result: Mapping[str, Any], n: int = 1) -> str:
    """The channel's label, or «Muscle n» when the recording has none."""
    name = result.get("channel_name" if n == 1 else "channel_name_2")
    return str(name) if name else tr("Muscle {n}").format(n=n)


def shows_two(pid: int, result: Mapping[str, Any]) -> bool:
    """Whether this panel draws two muscles for this result."""
    key = BY_PID[pid].two_key
    return bool(key) and result.get(key) is not None


def panel_title(pid: int, result: Mapping[str, Any], *, unit: str = "",
                reading: str | None = None) -> str:
    """Number, name, the muscle when there is one, and the reading below.

    ``unit`` is appended to the name (panel 9 says «% MVC» when it is in it);
    ``reading`` replaces the row's (panel 9's in millivolts).
    """
    p = BY_PID[pid]
    two = shows_two(pid, result)
    head = f"{p.number}. {tr(p.name)}"
    if unit:
        head += f", {unit}"
    if p.per_muscle and not two:
        head += f" — {muscle_name(result)}"
    if reading is None:
        reading = p.reading_two if two and p.reading_two else p.reading
    return f"{head}\n({tr(reading)})"
