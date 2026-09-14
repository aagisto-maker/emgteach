"""The analysis panels: one row each, the one place a panel's number, name and
reading are written.

The article cites panels by number, so a number has to be the same whenever
its panel is drawn — whatever else is ticked, whatever the practical — and it
can only be that if it is written once. Every title, on screen and in the
report, is built here from the panel's row: its number, its name, the muscle
when the panel shows only one, and on a second line its reading, which says
what it means that the curve rises or falls. A panel that has to be explained
aloud is badly drawn; the reading is the explanation, on the figure.

Qt-free: the report draws from it too.
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
    is what the student, the report and the article see. ``name`` and the
    readings are English catalogue keys. ``two_key`` is the result entry
    present when the panel draws two muscles: then the muscles are named on
    its axes or in its legend, and otherwise, if ``per_muscle``, in its title.
    """

    pid: int
    number: int
    name: str
    reading: str
    reading_two: str = ""
    two_key: str = ""
    per_muscle: bool = True


PANELS: tuple[Panel, ...] = (
    Panel(0, 1, "Raw EMG signal",
          "the trace thickens while the muscle contracts and thins while it rests",
          "each muscle against its own axis: read when each one fires, not "
          "which is taller",
          two_key="emg_raw_2"),
    Panel(3, 2, "Envelope normalised to maximum",
          "1 is the highest point of this window, not the MVC: read the shape, "
          "not the height"),
    Panel(4, 3, "Power spectral density (PSD)",
          "where the signal's power lies; in grey, what the filter took away",
          "each curve has area 1, so the shapes compare; the dashed line is "
          "each muscle's MDF",
          two_key="psd_2"),
    Panel(1, 4, "Filtered + rectified EMG signal",
          "rectified, every oscillation counts upwards: the taller the trace, "
          "the stronger the activation"),
    Panel(2, 5, "EMG signal envelope",
          "the higher the curve, the stronger the activation; the two lines are "
          "two ways of measuring it"),
    Panel(5, 6, "RMS amplitude over time",
          "one point per window: rising at a steady effort means more motor "
          "units, often fatigue",
          "each muscle against its own axis: read how each one evolves, not "
          "which is higher",
          two_key="rms_seg_2"),
    Panel(6, 7, "Fatigue trend: median frequency vs. time",
          "a decrease indicates muscle fatigue",
          two_key="mdf_seg_2"),
    Panel(7, 8, "Amplitude vs median frequency",
          "the points follow time along the arrow; fatigue moves the path up "
          "and to the left: more amplitude, less frequency"),
    Panel(8, 9, "Overlaid envelopes (agonist/antagonist)",
          "each muscle against its own maximum: one rising as the other falls "
          "is alternation; both up at once, co-activation",
          per_muscle=False),
    Panel(9, 10, "EMG vs MMG (electrical vs mechanical)",
          "the muscle's vibration (MMG) follows its electrical activity (EMG)"),
    Panel(10, 11, "Tremor — accelerometer spectrum",
          "the peak is the tremor's frequency; physiological tremor sits at "
          "8-12 Hz",
          per_muscle=False),
    Panel(11, 12, "Movement vs EMG (limb kinematics)",
          "the EMG rises first and the movement follows: the gap is the "
          "electromechanical delay"),
)

#: Panel 9's reading when it stays in millivolts, for want of an MVC
#: reference for both muscles.
OVERLAY_READING_MV = "in millivolts: read when each one fires, not which is higher"

BY_PID: dict[int, Panel] = {p.pid: p for p in PANELS}


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
