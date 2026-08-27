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

**The level of detail belongs to the practical.** There used to be a separate
"advanced options" tick, orthogonal to the mode, and two independent axes meant
the user had to hold both in mind to know why a control was or was not on
screen. Each practical now carries its own level, and the fine controls —
filter cut-offs, region of interest, fatigue thresholds, onset detection —
live in a fourth mode of their own, :data:`MODE_FREE`, which exists so that
nothing is lost and nothing is on by default.
"""

from __future__ import annotations

from emgteach.i18n import tr

__all__ = [
    "DEFAULT_MODE",
    "MODES",
    "MODE_FREE",
    "MODE_KINEMATICS",
    "MODE_PAIR",
    "MODE_SINGLE",
    "mode_channels",
    "mode_complexity",
    "mode_complexity_colour",
    "mode_complexity_label",
    "mode_forces_setup",
    "mode_label",
    "mode_shows_fine_controls",
    "mode_uses_acc",
    "normalise_mode",
]

MODE_SINGLE = "single"
MODE_PAIR = "pair"
MODE_KINEMATICS = "kinematics"
#: Everything on offer, for someone who knows what they are looking for. Not a
#: practical: it makes no teaching claim about what to record or read.
MODE_FREE = "free"

MODES: tuple[str, ...] = (MODE_SINGLE, MODE_PAIR, MODE_KINEMATICS, MODE_FREE)
DEFAULT_MODE = MODE_SINGLE

# EMG channels each mode records. The accelerometer, where used, is a further
# channel and is not counted here.
_CHANNELS = {MODE_SINGLE: 1, MODE_PAIR: 2, MODE_KINEMATICS: 1, MODE_FREE: 2}

# Only kinematics and the free mode record the accelerometer. Whether it sits
# on the muscle (MMG) or on the moving segment (tremor, force-velocity) stays a
# choice inside the mode, since both are the same practical set-up.
_USES_ACC = {
    MODE_SINGLE: False, MODE_PAIR: False, MODE_KINEMATICS: True, MODE_FREE: True,
}

#: How much the practical asks of the reader, for the band across the top. The
#: point is not to rank the practicals but to warn: the further down this list,
#: the more of the reading is interpretation rather than measurement.
_COMPLEXITY = {
    MODE_SINGLE: "basic",
    MODE_PAIR: "intermediate",
    MODE_KINEMATICS: "advanced",
    MODE_FREE: "free",
}

_COMPLEXITY_COLOURS = {
    "basic": "#2E7D32",         # green
    "intermediate": "#E67E22",  # amber
    "advanced": "#8E44AD",      # purple
    "free": "#5D6D7E",          # slate — deliberately not on the same scale
}


def normalise_mode(value: object) -> str:
    """Coerce a stored setting to a valid mode, falling back to the default."""
    return value if value in MODES else DEFAULT_MODE


def mode_channels(mode: str) -> int:
    return _CHANNELS.get(normalise_mode(mode), 1)


def mode_uses_acc(mode: str) -> bool:
    return _USES_ACC.get(normalise_mode(mode), False)


def mode_forces_setup(mode: str) -> bool:
    """Whether the mode imposes its channel count and accelerometer.

    A practical does: choosing it *is* choosing what to record, and letting the
    two disagree is the bug this module exists to prevent. The free mode does
    not — imposing a set-up on the mode whose whole point is that nothing is
    imposed would be a contradiction. It shows every control and leaves them
    where the user put them.
    """
    return normalise_mode(mode) != MODE_FREE


def mode_shows_fine_controls(mode: str) -> bool:
    """Whether this mode puts the fine controls on screen.

    Only the free mode does. A practical that offered them would be asking the
    student to decide a filter cut-off in the middle of a physiology exercise,
    which is a different lesson from the one it is teaching.
    """
    return normalise_mode(mode) == MODE_FREE


def mode_complexity(mode: str) -> str:
    """Identifier of the complexity level: basic, intermediate, advanced, free."""
    return _COMPLEXITY[normalise_mode(mode)]


def mode_complexity_colour(mode: str) -> str:
    """Colour for the band, as a hex string."""
    return _COMPLEXITY_COLOURS[mode_complexity(mode)]


def mode_complexity_label(mode: str) -> str:
    """What the band says: the level, and what it means for the reading."""
    return {
        "basic": tr("Basic analysis — direct measurements"),
        "intermediate": tr("Intermediate analysis — comparison between muscles"),
        "advanced": tr("Advanced analysis — derived quantities"),
        "free": tr("Free analysis — every control, no guidance"),
    }[mode_complexity(mode)]


def mode_label(mode: str) -> str:
    """Human-readable name, translated. Names the practical, not the wiring."""
    return {
        MODE_SINGLE: tr("Single-muscle contraction"),
        MODE_PAIR: tr("Agonist / antagonist contraction"),
        # Kinematics, not kinetics: the accelerometer measures the movement of
        # the segment. The force-velocity curve derived from it is kinetic,
        # but what the sensor reads is kinematic.
        MODE_KINEMATICS: tr("Muscle kinematics"),
        MODE_FREE: tr("Free analysis"),
    }[normalise_mode(mode)]
