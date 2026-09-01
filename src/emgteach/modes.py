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
belong to :data:`MODE_KINEMATICS`, the one practical advanced enough to need
them.

**There were two kinematics practicals and only one of them was a practical.**
A restricted one — a single muscle, the accelerometer, no fine controls — and a
"free analysis" that recorded the accelerometer too, with two muscles and every
control on screen. The second was a superset of the first, so all the first
contributed was *removal*; and "free analysis" named none of what it did. It
was not free analysis at all: it was a kinematics with options, which is what
the practical needs to be, since deriving a force-velocity curve from a
movement is an advanced exercise by its own nature and the reader is already
past the point where a hidden filter cut-off protects them.

So there are three practicals, and the third is named for what it measures.
Its stored setting is still ``"kinematics"``, and a session saved under the old
``"free"`` is read as the same thing — the two collapsed into one, and nobody
should be thrown back to the single-muscle default for having chosen either.
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
    "mode_complexity",
    "mode_complexity_colour",
    "mode_complexity_label",
    "mode_label",
    "mode_requires_calibration",
    "mode_shows_fine_controls",
    "mode_uses_acc",
    "normalise_mode",
]

MODE_SINGLE = "single"
MODE_PAIR = "pair"
#: Movement and the force-velocity relationship, with every control on screen.
#: See the note above on why there is one of these and not two.
MODE_KINEMATICS = "kinematics"

#: What the setting said while this practical was called "free analysis". Read
#: as :data:`MODE_KINEMATICS` so an installation that had it selected opens on
#: the same practical instead of falling back to the default.
_LEGACY_FREE = "free"

MODES: tuple[str, ...] = (MODE_SINGLE, MODE_PAIR, MODE_KINEMATICS)
DEFAULT_MODE = MODE_SINGLE

# EMG channels each mode records. The accelerometer, where used, is a further
# channel and is not counted here.
_CHANNELS = {MODE_SINGLE: 1, MODE_PAIR: 2, MODE_KINEMATICS: 2}

# Only the kinematics practical records the accelerometer. Whether it sits on
# the muscle (MMG) or on the moving segment (tremor, force-velocity) stays a
# choice inside the mode, since both are the same practical set-up.
_USES_ACC = {MODE_SINGLE: False, MODE_PAIR: False, MODE_KINEMATICS: True}

#: How much the practical asks of the reader, for the band across the top. The
#: point is not to rank the practicals but to warn: the further down this list,
#: the more of the reading is interpretation rather than measurement.
_COMPLEXITY = {
    MODE_SINGLE: "basic",
    MODE_PAIR: "intermediate",
    MODE_KINEMATICS: "advanced",
}

_COMPLEXITY_COLOURS = {
    "basic": "#2E7D32",         # green
    "intermediate": "#E67E22",  # amber
    "advanced": "#8E44AD",      # purple
}


def normalise_mode(value: object) -> str:
    """Coerce a stored setting to a valid mode, falling back to the default."""
    if value == _LEGACY_FREE:
        return MODE_KINEMATICS
    return value if value in MODES else DEFAULT_MODE


def mode_channels(mode: str) -> int:
    return _CHANNELS.get(normalise_mode(mode), 1)


def mode_uses_acc(mode: str) -> bool:
    return _USES_ACC.get(normalise_mode(mode), False)


def mode_requires_calibration(mode: str) -> bool:
    """Whether pressing record has to run the calibration first.

    Only the agonist/antagonist practical: comparing two muscles is comparing
    two percentages of two different maxima, so without both references there
    is nothing to compare and the co-activation index cannot be computed at
    all. The others *offer* calibration — the button is there and the wizard
    writes its phases the same way — but a recording without it still says
    something, so it is not imposed.
    """
    return normalise_mode(mode) == MODE_PAIR


def mode_shows_fine_controls(mode: str) -> bool:
    """Whether this mode puts the fine controls on screen.

    Only the kinematics practical does. The other two would be asking the
    student to decide a filter cut-off in the middle of a physiology exercise,
    which is a different lesson from the one they are teaching; a reader
    deriving a force-velocity curve is already past that point.
    """
    return normalise_mode(mode) == MODE_KINEMATICS


def mode_complexity(mode: str) -> str:
    """Identifier of the complexity level: basic, intermediate or advanced."""
    return _COMPLEXITY[normalise_mode(mode)]


def mode_complexity_colour(mode: str) -> str:
    """Colour for the band, as a hex string."""
    return _COMPLEXITY_COLOURS[mode_complexity(mode)]


def mode_complexity_label(mode: str) -> str:
    """What the band says: the level, and what it means for the reading."""
    return {
        "basic": tr("Basic analysis — direct measurements"),
        "intermediate": tr("Intermediate analysis — comparison between muscles"),
        "advanced": tr("Advanced analysis — muscle kinematics"),
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
    }[normalise_mode(mode)]
