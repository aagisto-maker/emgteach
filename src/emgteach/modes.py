"""Recording modes — what kind of practical the app is set up for.

The interface is configured by choosing the practical, not by choosing how
much interface to show. The mode fixes what is being recorded (how many EMG
channels, whether the accelerometer is used), and everything downstream
follows from it: which controls make sense in the acquisition tab, and which
analysis panels are worth offering.

That matters for more than tidiness. Before this existed the channel count was
a separate control, so a two-muscle setup could survive into a screen that had
no way to show or change it — the labels and load bars said two muscles while
the rest of the tab behaved as if there were one. Deriving the channel count
from the mode makes that state unreachable.

Orthogonal to the mode is the *advanced* flag: filter cut-offs, region of
interest, warning thresholds, onset detection and classroom broadcast apply
equally to all three modes, and are hidden unless asked for. Mode answers
"which practical", advanced answers "how much fine control".
"""

from __future__ import annotations

from emgteach.i18n import tr

__all__ = [
    "DEFAULT_MODE",
    "MODES",
    "MODE_KINEMATICS",
    "MODE_PAIR",
    "MODE_SINGLE",
    "mode_channels",
    "mode_label",
    "mode_uses_acc",
    "normalise_mode",
]

MODE_SINGLE = "single"
MODE_PAIR = "pair"
MODE_KINEMATICS = "kinematics"

MODES: tuple[str, ...] = (MODE_SINGLE, MODE_PAIR, MODE_KINEMATICS)
DEFAULT_MODE = MODE_SINGLE

# EMG channels each mode records. The accelerometer, where used, is a further
# channel and is not counted here.
_CHANNELS = {MODE_SINGLE: 1, MODE_PAIR: 2, MODE_KINEMATICS: 1}

# Only the kinematics mode records the accelerometer. Whether it sits on the
# muscle (MMG) or on the moving segment (tremor, force-velocity) stays a
# choice inside that mode, since both are the same practical set-up.
_USES_ACC = {MODE_SINGLE: False, MODE_PAIR: False, MODE_KINEMATICS: True}


def normalise_mode(value: object) -> str:
    """Coerce a stored setting to a valid mode, falling back to the default."""
    return value if value in MODES else DEFAULT_MODE


def mode_channels(mode: str) -> int:
    return _CHANNELS.get(normalise_mode(mode), 1)


def mode_uses_acc(mode: str) -> bool:
    return _USES_ACC.get(normalise_mode(mode), False)


def mode_label(mode: str) -> str:
    """Human-readable name, translated. Names the practical, not the wiring."""
    return {
        MODE_SINGLE: tr("Single-muscle contraction"),
        MODE_PAIR: tr("Agonist / antagonist contraction"),
        # Kinematics, not kinetics: the accelerometer measures the movement of
        # the segment. The force-velocity curve derived from it is kinetic,
        # but what the sensor reads is kinematic.
        MODE_KINEMATICS: tr("Muscle kinematics"),
    }[normalise_mode(mode)]
