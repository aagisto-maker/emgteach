"""The marks the operator makes by hand while recording, and how to tell them.

During a recording the operator can mark a moment with one of a short list of
labels, by a button or the M key. The mark goes the way every other mark
goes — :meth:`AcquisitionWorker.add_marker`: an EDF+ annotation, a line in
the ``.marcas.txt`` mirror and one in the event log — written in the language
of the interface at that moment, as ecgteach and eegteach write theirs.

Nothing in the application interprets these marks; they are for whoever reads
the recording afterwards. What the analysis needs is to tell them from the
marks the application writes by itself — the automatic onsets, the gaps in
the link, the phases of a guided session — and :func:`is_manual_mark` does
that in either language, so a recording made in Spanish is recognised by an
interface in English.

No Qt here: the analysis and the tests ask without a display.
"""

from __future__ import annotations

from emgteach.i18n import in_every_language

#: The labels offered, as catalogue keys (English), in the order shown.
MANUAL_MARK_LABELS: tuple[str, ...] = (
    "Contraction start",
    "Contraction end",
    "Fatigue",
    "Rest",
    "Other",
)

#: The key that marks with the selected label.
MARK_KEY = "M"

_ALL_LANGUAGES: frozenset[str] = frozenset(
    text for label in MANUAL_MARK_LABELS for text in in_every_language(label)
)


def is_manual_mark(label: str) -> bool:
    """Whether *label* is one of the manual marks, in either language."""
    return str(label).strip() in _ALL_LANGUAGES
