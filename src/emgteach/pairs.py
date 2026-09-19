"""Which pair of muscles the agonist/antagonist practical is run on.

The engine never knew any anatomy: it works on channel 1 and channel 2, the
teacher names the muscles, and the definition of the index, the flow of the
session, the normalisation and every calculation are the same for any pair.
What is *not* the same is what a student is told and shown — the gesture that
serves as the reference, the pictures of where the electrodes go, the examples
in the boxes where the muscles are named — and all of that had converged on one
pair, the forearm's, the one the practical guide is written around.

This is that content, one column per pair, and nothing else: **no threshold
changes with the pair**. The co-activation floor, the channel-separation
criterion and the ranges of the calibration checks were measured on the forearm
pair (see :mod:`emgteach.profiles`), and they stay where they are for every
pair — which is why each pair other than the forearm carries the line that says
to check them on a test recording.

Three pairs, because three is what the teaching needs:

* the **forearm** (flexor and extensor carpi radialis), the practical guide's
  own, with its pictures and its gestures — the default, and the one every
  recording made so far was made on;
* the **arm** (biceps and triceps), written up in the guide as a variant, whose
  reference gesture is an elbow flexion and an elbow extension and whose third
  manoeuvre is a co-contraction, because there is no grip at the elbow;
* **another pair**, which is any pair at all: the rule without the example. No
  pictures, no gesture named, and the warning that the defaults were measured
  elsewhere.

The strings are English keys translated at the moment of showing, as everywhere
else, so a language switch does not need the table rebuilt.

What is **not** here is the name of each manoeuvre. The application does not
name them and does not want to: the windows of the co-activation table are
named after the muscle that led each one, because the program is told which
muscles these are only as the text the operator typed, and a label reading
«extension» over a flexion is worse than no label (see
:func:`emgteach.coactivation.propose_labels`). The practical guide names the
manoeuvres, per pair, which is where a name can be checked against a gesture.
"""

from __future__ import annotations

from emgteach.i18n import tr

__all__ = [
    "DEFAULT_PAIR",
    "PAIRS",
    "PAIR_ARM",
    "PAIR_FOREARM",
    "PAIR_OTHER",
    "normalise_pair",
    "pair_calibration_example",
    "pair_has_pictures",
    "pair_hint",
    "pair_image",
    "pair_label",
    "pair_protocol_suffix",
    "pair_short_label",
    "pair_warning",
]

PAIR_FOREARM = "forearm"
PAIR_ARM = "arm"
PAIR_OTHER = "other"

#: In the order the selector offers them: the guide's pair first.
PAIRS: tuple[str, ...] = (PAIR_FOREARM, PAIR_ARM, PAIR_OTHER)
DEFAULT_PAIR = PAIR_FOREARM

#: Suffix of the pictures in ``gui/assets/recorrido``. The forearm's are the
#: files that have always been there, with no suffix; a pair with no pictures
#: drawn for it carries ``None`` and the interface shows none rather than
#: somebody else's arm.
_IMAGE_SUFFIX: dict[str, str | None] = {
    PAIR_FOREARM: "",
    PAIR_ARM: "_biceps",
    PAIR_OTHER: None,
}


def normalise_pair(value: object) -> str:
    """Coerce a stored setting to a valid pair, falling back to the default."""
    return value if value in PAIRS else DEFAULT_PAIR


def pair_label(pair: str) -> str:
    """Human-readable name, translated: what the selector shows."""
    return {
        PAIR_FOREARM: tr("Forearm (FCR / ECR)"),
        PAIR_ARM: tr("Arm (biceps / triceps)"),
        PAIR_OTHER: tr("Another pair"),
    }[normalise_pair(pair)]


def pair_hint(pair: str, channel: int) -> str:
    """The placeholder of each label box: the role, and an example if there is one."""
    par = normalise_pair(pair)
    if par == PAIR_FOREARM:
        return (tr("Agonist — e.g. FCR"), tr("Antagonist — e.g. ECR"))[channel]
    if par == PAIR_ARM:
        return (tr("Agonist — e.g. biceps"), tr("Antagonist — e.g. triceps"))[channel]
    return (tr("Agonist"), tr("Antagonist"))[channel]


def pair_has_pictures(pair: str) -> bool:
    """Whether this pair is meant to have pictures at all.

    Whether they have been *drawn* is a question for the files, and the
    interface asks it of :func:`emgteach.gui.imagenes.imagen`: a pair whose
    pictures are still to be drawn shows none and says so, and the day they
    are drawn it stops saying it without anybody editing this table.
    """
    return _IMAGE_SUFFIX[normalise_pair(pair)] is not None


def pair_image(pair: str, nombre: str) -> str | None:
    """The name of the picture *nombre* for this pair, or ``None`` if it has none.

    The name only: who turns it into a file is
    :func:`emgteach.gui.imagenes.imagen`, which resolves the language.
    """
    sufijo = _IMAGE_SUFFIX[normalise_pair(pair)]
    return None if sufijo is None else f"{nombre}{sufijo}"


def pair_calibration_example(pair: str, channel: int) -> str:
    """The sentence that follows the rule of the calibration, or ``""``.

    The rule — one brief, explosive maximal jerk of the movement this muscle
    makes — is the same for every pair and is not here: it is in the
    instruction. This is the gesture that illustrates it, which is the pair's.
    With a pair the application knows nothing about there is no example, and
    the rule stands on its own.
    """
    par = normalise_pair(pair)
    if par == PAIR_FOREARM:
        return (
            tr("On the forearm: wrist flexion, clenching the fist with all "
               "your strength."),
            tr("On the forearm: wrist extension, with the hand open and the "
               "fingers stretched out as far as they go."),
        )[channel]
    if par == PAIR_ARM:
        return (
            tr("On the arm: elbow flexion against something that does not give."),
            tr("On the arm: elbow extension against something that does not give."),
        )[channel]
    return ""


def pair_warning(pair: str) -> str:
    """The line the teacher has to read before using this pair, or ``""``.

    The forearm is the pair the defaults were measured on, so it has nothing
    to warn about; every other pair does. That a pair has no pictures yet is
    said where the picture would have been, by whoever went looking for it.
    """
    par = normalise_pair(pair)
    if par == PAIR_FOREARM:
        return ""
    return tr(
        "The default limits were measured on the forearm pair: check them on a "
        "test recording before using this one with a group."
    )


def pair_protocol_suffix(pair: str) -> str:
    """What the EDF header adds about the pair, so the file says which it was.

    Untranslated, like the protocol it is appended to: the header outlives
    the session. :func:`pair_short_label` is the same thing for reading.
    """
    par = normalise_pair(pair)
    return {
        PAIR_FOREARM: "forearm",
        PAIR_ARM: "arm",
        PAIR_OTHER: "other",
    }[par]


def pair_short_label(pair: str) -> str:
    """The pair in one word, translated: for a report, beside the practical.

    Shorter than :func:`pair_label`, which names the muscles because it is
    what the selector shows. Inside a bracket after the practical, those
    brackets would nest.
    """
    return {
        PAIR_FOREARM: tr("forearm"),
        PAIR_ARM: tr("arm"),
        PAIR_OTHER: tr("another pair"),
    }[normalise_pair(pair)]
