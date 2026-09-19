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

There are three practicals, and each is named for what it measures. The third,
muscle kinematics, is the advanced one: deriving a force-velocity curve from a
movement is an advanced exercise by its own nature, and the reader is already
past the point where a hidden filter cut-off protects them — so that practical
carries the fine controls and the other two do not.
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
    "mode_detection_k",
    "mode_expected_contractions",
    "mode_fixed_labels",
    "mode_label",
    "mode_protocol",
    "mode_requires_calibration",
    "mode_shows_fine_controls",
    "mode_uses_acc",
    "normalise_mode",
    "protocol_label",
]

MODE_SINGLE = "single"
MODE_PAIR = "pair"
#: Movement and the force-velocity relationship, with every control on screen.
#: See the note above on why there is one of these and not two.
MODE_KINEMATICS = "kinematics"

#: A value older installations may still have saved for the advanced
#: practical. Read as :data:`MODE_KINEMATICS` so they open on it instead of
#: falling back to the default.
_LEGACY_FREE = "free"

MODES: tuple[str, ...] = (MODE_SINGLE, MODE_PAIR, MODE_KINEMATICS)
DEFAULT_MODE = MODE_SINGLE

# EMG channels each mode records. The accelerometer, where used, is a further
# channel and is not counted here.
_CHANNELS = {MODE_SINGLE: 1, MODE_PAIR: 2, MODE_KINEMATICS: 1}

# Only the kinematics practical records the accelerometer. Whether it sits on
# the muscle (MMG) or on the moving segment (tremor, force-velocity) stays a
# choice inside the mode, since both are the same practical set-up.
_USES_ACC = {MODE_SINGLE: False, MODE_PAIR: False, MODE_KINEMATICS: True}

#: The detector's sensitivity each practical opens on (the k of
#: :func:`emgteach.selection.activity_threshold`). One global value served the
#: single-muscle practicals and not the pair: there 4.4 is the value that gives
#: one row per manoeuvre of the protocol's series in the recordings it was
#: tried on. It is where the editor starts, not a limit: the slider still
#: moves, and whatever it is left on travels into the report and the CSV.
_DETECTION_K = {MODE_SINGLE: 3.0, MODE_PAIR: 4.4, MODE_KINEMATICS: 3.0}

#: How many contractions the practical's protocol asks for, in the order the
#: fragment editor counts them — led by the first muscle, by the second, by
#: both. The pair's series is six flexions, six extensions and one grip. Empty
#: where the protocol sets no number; the editor then counts without a target.
_EXPECTED = {MODE_PAIR: (6, 6, 1)}

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


#: What the EDF calls each channel, per practical. Fixed wherever the practical
#: leaves nothing to choose:
#:
#: * the single-muscle practical records **a** muscle — whichever one the
#:   exercise is about — so a text box for its name asks a question whose
#:   answer changes nothing the application does; the student writes it on
#:   their sheet;
#: * the kinematics one relates the EMG of a muscle to the movement of the
#:   segment it drives, so both roles are fixed and only "which muscle" is
#:   open, which is the same case.
#:
#: The agonist/antagonist practical is the exception, and the reason is the
#: point of it: there are two muscles, telling them apart *is* the reading, and
#: the names travel into the co-activation table as its column headings.
# No practical imposes a name any more. The two single-muscle practicals
# used to fix «Muscle», on the reasoning that there was nothing else to call
# it — and every recording came back headed «Músculo», which says nothing
# about which muscle it was. The box is offered in every practical; a name
# left empty falls back to the practical's generic one.
_FIXED_LABELS: dict[str, tuple[str, ...]] = {}


def mode_channels(mode: str) -> int:
    return _CHANNELS.get(normalise_mode(mode), 1)


def mode_fixed_labels(mode: str) -> tuple[str, ...]:
    """Channel names this practical imposes, or ``()`` when it names none.

    Offering a text box for a name that cannot sensibly be anything else is
    asking a question with one answer — and inviting a recording whose header
    disagrees with what the practical was.
    """
    return _FIXED_LABELS.get(normalise_mode(mode), ())


def mode_protocol(mode: str) -> str:
    """What the EDF header records this recording as.

    Written from the practical instead of typed. It used to be a free-text
    field beside the student's name, which asked the operator to name what the
    application already knew, and let the header disagree with the mode it was
    recorded in.

    Deliberately **not** translated: the header outlives the session and is
    read by whoever opens the file later, so a Spanish recording and an English
    one describing the same practical have to say the same thing.

    **And it has to fit.** EDF+ leaves thirty-nine characters to be shared
    between this field and the ones naming the bench, and the protocol is the
    one that never gives way (:meth:`emgteach.io.RecordingMetadata.fit_to_edf_budget`),
    so every character spent here is taken from the device string. The pair
    practical adds which pair it was run on, and «agonist/antagonist
    contraction (forearm)» came to forty: one over the whole budget, so the
    header lost its closing bracket and warned on every single recording. The
    word «contraction» was what paid for it: a field called the protocol does
    not need to say that a muscle recording is of contractions, and the pair
    is worth more than the word — it cannot be recovered from anywhere else.
    """
    return {
        MODE_SINGLE: "single-muscle contraction",
        MODE_PAIR: "agonist/antagonist",
        MODE_KINEMATICS: "muscle kinematics",
    }[normalise_mode(mode)]


#: The header values this application has written, and the practical each
#: one names. The second spelling of the pair is what 3.6.0 and earlier
#: wrote, before the pair had to fit in the header beside it: recordings
#: made with those versions are read for years and still say it.
_PROTOCOL_MODES: dict[str, str] = {
    "single-muscle contraction": MODE_SINGLE,
    "agonist/antagonist": MODE_PAIR,
    "agonist/antagonist contraction": MODE_PAIR,
    "muscle kinematics": MODE_KINEMATICS,
}


def protocol_label(protocol: str) -> str | None:
    """What a header's protocol value is called in the reader's language.

    The stored value is deliberately untranslated (:func:`mode_protocol`):
    the header outlives the session and a Spanish recording and an English
    one of the same practical have to say the same thing. A report, on the
    other hand, is read now and by one person, so the translation happens
    on the way out.

    ``None`` for anything this application did not write — a file from
    another tool, or a spelling no version of this one used. The caller
    shows the raw value then, which is honest: an unknown protocol is
    better read in its own words than guessed at in ours.
    """
    from emgteach.pairs import PAIRS, pair_protocol_suffix, pair_short_label

    crudo = (protocol or "").strip()
    if not crudo:
        return None
    base, marca, resto = crudo.partition(" (")
    modo = _PROTOCOL_MODES.get(base)
    if modo is None:
        return None
    if not marca:
        return mode_label(modo)
    # Only the pair practical adds anything, and only its own pairs.
    if modo != MODE_PAIR or not resto.endswith(")"):
        return None
    sufijo = resto[:-1]
    for par in PAIRS:
        if pair_protocol_suffix(par) == sufijo:
            return f"{mode_label(modo)} ({pair_short_label(par)})"
    return None


def mode_uses_acc(mode: str) -> bool:
    return _USES_ACC.get(normalise_mode(mode), False)


def mode_detection_k(mode: str) -> float:
    """The detection sensitivity the fragment editor opens on in this practical."""
    return _DETECTION_K.get(normalise_mode(mode), 3.0)


def mode_expected_contractions(mode: str) -> tuple[int, ...]:
    """Contractions the protocol asks for (first muscle, second, both), or ``()``."""
    return _EXPECTED.get(normalise_mode(mode), ())


def mode_requires_calibration(mode: str) -> bool:
    """Whether pressing record has to run the calibration first.

    The agonist/antagonist practical: comparing two muscles is comparing two
    percentages of two different maxima, so without both references there is
    nothing to compare and the co-activation index cannot be computed at all.
    And the kinematics practical: its
    whole session is a sequence — the maximum, then the loads — and left as
    a button beside the record button the calibration was the step nobody
    knew whether or when to take. The single-muscle practical *offers* it:
    the button is there and the wizard writes its phases the same way, but a
    recording without it still says something, so it is not imposed.
    """
    return normalise_mode(mode) in (MODE_PAIR, MODE_KINEMATICS)


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
    """What the band says: the level, and nothing else.

    It used to carry a second half describing the kind of reading — "direct
    measurements", "comparison between muscles", "derived quantities". Two
    things went wrong with it. The practical is already named in the selector
    directly above the band, so any half naming it is read twice; and any half
    describing the reading instead is a second vocabulary for the same three
    things, which has to be kept in step with the practicals and was not: one
    of them had drifted to naming its practical while the others still
    described their reading.

    The level alone is what the band is for. Its colour carries the rest.
    """
    return {
        "basic": tr("Basic level"),
        "intermediate": tr("Intermediate level"),
        "advanced": tr("Advanced level"),
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
