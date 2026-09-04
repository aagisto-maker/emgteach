"""Session phases: one recording, with the calibration marked inside it.

A session used to be two files — a calibration recorded separately and chosen
by hand, and the recording to analyse. That model is what produced a tab
asking for a reference an already-calibrated file was carrying, and it left
the only way of separating calibration from work to the operator's eye, on the
one decision that must not be eyeballed: the application knows exactly where
the calibration was.

**A session is one file with two phases marked in it.** The acquisition writes
them as EDF+ annotations, in the idiom the file already uses for the MVC
reference (:func:`emgteach.mvc.mvc_ref_marker`) and the force-velocity loads
(:func:`emgteach.force_velocity.fv_load_marker`)::

    CAL start ch=1 rep=1
    CAL end   ch=1 rep=1
    ...
    PREP start
    REC start

Two rules the rest of the code depends on:

* **The `CAL` spans are the source; `MVC ref` is a cached result.** When the
  spans are there the reference is recomputed from them — so discarding a
  repetition in the analysis tab moves the reference, and every %MVC with it.
  The cached annotation is what a file recorded before this change has, and
  the only case where it is used.
* **The analysed span starts at `REC start`.** Calibration and preparation sit
  before it and are therefore excluded from every analysis by construction,
  with no separate notion of "excluded regions" to keep in step. The
  acquisition does not stop between the phases — the file is continuous and
  EDF+ never has to represent a gap — so a few seconds of preparation are
  recorded and simply not analysed.

One consequence worth stating before it is mistaken for a bug: **the
recomputed reference will not equal the cached one to the last digit, even
with every repetition kept.** The wizard computes its value from the online
envelope while recording; this recomputes it from
:func:`emgteach.dsp.process_offline`, which is zero-phase and uses whatever
envelope cut-off the tab is set to. The two agree to a few per cent. The
recomputed one is the better number — it is the one the offline analysis can
reproduce — and it is what the precedence rule selects.

Qt-free, like :mod:`emgteach.coactivation` and :mod:`emgteach.apda`, so the
workers and any offline use share it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from emgteach.i18n import tr
from emgteach.mvc import mvc_from_reps

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping, Sequence

    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]

__all__ = [
    "FROM_CACHE",
    "FROM_REPS",
    "NO_CALIBRATION",
    "CalRep",
    "RepValue",
    "SessionPhases",
    "cal_end_marker",
    "cal_start_marker",
    "is_phase_marker",
    "mvc_reference",
    "parse_phase_markers",
    "prep_start_marker",
    "rec_start_marker",
    "reference_source_text",
    "rep_values",
    "slice_reps",
    "strip_phase_markers",
    "warmup_start_marker",
]

_CAL_RE = re.compile(
    r"CAL\s+(start|end)\s+ch=\s*(\d+)\s+rep=\s*(\d+)", re.IGNORECASE
)
_WARMUP_RE = re.compile(r"WARMUP\s+start", re.IGNORECASE)
_PREP_RE = re.compile(r"PREP\s+start", re.IGNORECASE)
_REC_RE = re.compile(r"REC\s+start", re.IGNORECASE)

#: Where a usable MVC reference came from. Tokens, not sentences: the interface
#: has to branch on this and must not depend on the wording of a particular
#: language — the same lesson as ``mvc_is_auto`` in the MVC worker, which was
#: added as a flag precisely because ``mvc_source`` is translated. Render one
#: with :func:`reference_source_text`.
FROM_REPS = "reps"
FROM_CACHE = "cache"
NO_CALIBRATION = "none"


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def cal_start_marker(channel_index: int, rep: int) -> str:
    """Annotation opening one calibration repetition.

    ``channel_index`` is 0-based; the label carries it 1-based, as
    :func:`emgteach.mvc.mvc_ref_marker` does, because that is how the channels
    are numbered on screen. ``rep`` is 1-based in both.
    """
    return f"CAL start ch={channel_index + 1} rep={rep}"


def cal_end_marker(channel_index: int, rep: int) -> str:
    """Annotation closing one calibration repetition."""
    return f"CAL end ch={channel_index + 1} rep={rep}"


def warmup_start_marker() -> str:
    """Annotation opening the warm-up that precedes the calibration.

    The first maximal effort of a session is submaximal, so the wizard
    asks for a few easy contractions first. Recorded rather than waited
    out off the clock, for the same reason the pause is: the acquisition
    never stops, and the file stays continuous.
    """
    return "WARMUP start"


def prep_start_marker() -> str:
    """Annotation opening the preparation pause between the two phases."""
    return "PREP start"


def rec_start_marker() -> str:
    """Annotation opening the recording proper — the start of the analysed span."""
    return "REC start"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def is_phase_marker(description: str) -> bool:
    """Whether an annotation is one of this module's, rather than a student's mark."""
    text = str(description)
    return bool(
        _CAL_RE.search(text)
        or _WARMUP_RE.search(text)
        or _PREP_RE.search(text)
        or _REC_RE.search(text)
    )


def strip_phase_markers(
    markers: Iterable[tuple[float, str]],
) -> list[tuple[float, str]]:
    """Drop the phase annotations, keeping the marks that divide the work.

    Phases are facts about the session, not moments in it. Left in the list
    they would draw a line across every panel and open a window in the
    co-activation table, which reports one row per marked phase — the same
    reason the MVC references and the force-velocity loads are stripped in the
    analysis worker before the markers are used.
    """
    return [(float(t), str(d)) for t, d in markers if not is_phase_marker(d)]


@dataclass(frozen=True)
class CalRep:
    """One calibration repetition of one channel, delimited in the recording."""

    channel_index: int      #: 0-based, as everywhere else in the code
    rep: int                #: 1-based, as the wizard counts them
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


@dataclass(frozen=True)
class SessionPhases:
    """What the annotations say about the shape of a session."""

    cal_reps: tuple[CalRep, ...] = ()
    prep_start_s: float | None = None
    rec_start_s: float | None = None
    warmup_start_s: float | None = None

    @property
    def has_phases(self) -> bool:
        """Whether this file was recorded with the two-phase flow at all."""
        return bool(self.cal_reps) or self.rec_start_s is not None

    def channels(self) -> tuple[int, ...]:
        """Channel indices that have at least one calibration repetition."""
        return tuple(sorted({r.channel_index for r in self.cal_reps}))

    def reps_for(self, channel_index: int) -> tuple[CalRep, ...]:
        """This channel's repetitions, in the order they were performed."""
        return tuple(
            r for r in self.cal_reps if r.channel_index == int(channel_index)
        )

    def rec_span(self, duration_s: float) -> tuple[float, float] | None:
        """The analysed span ``(start, end)``, or ``None`` without a ``REC start``.

        Everything before the start — calibration and preparation alike — falls
        outside, which is how the preparation pause is kept out of every
        analysis without a separate list of regions to exclude.
        """
        if self.rec_start_s is None:
            return None
        start = max(0.0, min(float(self.rec_start_s), float(duration_s)))
        return (start, float(duration_s))


def parse_phase_markers(
    markers: Iterable[tuple[float, str]],
) -> SessionPhases:
    """Read the phases back from a recording's annotations.

    A repetition is only reported once it is **closed**: a ``CAL start`` with
    no matching ``CAL end`` is dropped, which is what a recording stopped in
    the middle of a calibration leaves behind. A second ``start`` for the same
    channel and repetition before its ``end`` replaces the first — the wizard
    restarted that repetition — and an ``end`` with nothing open is ignored.

    ``PREP start`` and ``REC start`` take the **last** occurrence, on the same
    reasoning as the MVC references: if a session wrote one twice, the one it
    finished with is the one that describes the file.
    """
    reps: list[CalRep] = []
    abiertas: dict[tuple[int, int], float] = {}
    warmup: float | None = None
    prep: float | None = None
    rec: float | None = None

    for onset, desc in sorted(markers, key=lambda m: float(m[0])):
        t = float(onset)
        text = str(desc)

        cal = _CAL_RE.search(text)
        if cal:
            channel = int(cal.group(2)) - 1
            numero = int(cal.group(3))
            if channel < 0 or numero < 1:
                continue
            clave = (channel, numero)
            if cal.group(1).lower() == "start":
                abiertas[clave] = t
            else:
                inicio = abiertas.pop(clave, None)
                if inicio is not None and t > inicio:
                    reps.append(CalRep(channel, numero, inicio, t))
            continue

        if _WARMUP_RE.search(text):
            warmup = t
        elif _PREP_RE.search(text):
            prep = t
        elif _REC_RE.search(text):
            rec = t

    reps.sort(key=lambda r: (r.channel_index, r.rep, r.start_s))
    return SessionPhases(tuple(reps), prep, rec, warmup)


# ---------------------------------------------------------------------------
# The reference
# ---------------------------------------------------------------------------


def slice_reps(
    envelope,
    fs: float,
    reps: Sequence[CalRep],
    *,
    keep: Collection[int] | None = None,
) -> list[FloatArray]:
    """The envelope of each repetition, ready for :func:`mvc_from_reps`.

    ``keep`` selects repetitions by their 1-based number; ``None`` keeps them
    all. Spans are clamped to the signal, and a span that lands outside it or
    is empty is skipped rather than contributing a zero-length repetition.
    """
    env = np.asarray(envelope, dtype=np.float64)
    out: list[FloatArray] = []
    for r in reps:
        if keep is not None and r.rep not in keep:
            continue
        i0 = max(0, min(round(r.start_s * fs), env.size))
        i1 = max(i0, min(round(r.end_s * fs), env.size))
        if i1 > i0:
            out.append(env[i0:i1])
    return out


@dataclass(frozen=True)
class RepValue:
    """One calibration repetition, as the analysis tab offers it for keeping.

    ``value_mv`` is measured exactly as the reference is — strongest sustained
    window — so the largest of them *is* the reference when every repetition is
    kept, and the arithmetic the student sees adds up.

    ``crosstalk_pct`` is what the *other* channel reached during this effort, as
    a share of its own reference. It belongs beside the value because the two
    answer different halves of "was this repetition any good": a weak one and a
    contaminated one both deserve discarding, and only one of them is visible
    in the number.
    """

    rep: int
    value_mv: float
    crosstalk_pct: float | None = None


def rep_values(
    channel_index: int,
    *,
    phases: SessionPhases,
    envelope,
    fs: float,
    percentile: float = 95.0,
    window_s: float = 0.5,
    other_envelope=None,
    other_reference: float | None = None,
) -> tuple[RepValue, ...]:
    """What each of this channel's calibration repetitions was worth.

    Returns them in the order they were performed, which is the order that
    makes a rising profile — a subject still warming up at the third attempt —
    visible at a glance.
    """
    reps = phases.reps_for(channel_index)
    if not reps or envelope is None or fs <= 0:
        return ()
    ventana = max(1, round(float(window_s) * float(fs)))
    trozos = slice_reps(envelope, fs, reps)
    cruzados = (
        slice_reps(other_envelope, fs, reps)
        if other_envelope is not None and other_reference
        else [None] * len(trozos)
    )
    salida: list[RepValue] = []
    for r, propio, ajeno in zip(reps, trozos, cruzados, strict=False):
        valor = mvc_from_reps([propio], percentile, window_samples=ventana)
        cruce = None
        if ajeno is not None and ajeno.size:
            nivel = mvc_from_reps([ajeno], percentile, window_samples=ventana)
            cruce = 100.0 * nivel / float(other_reference)
        salida.append(RepValue(r.rep, float(valor), cruce))
    return tuple(salida)


def mvc_reference(
    channel_index: int,
    *,
    phases: SessionPhases | None = None,
    envelope=None,
    fs: float = 0.0,
    cached: Mapping[int, float] | None = None,
    keep: Collection[int] | None = None,
    percentile: float = 95.0,
    window_s: float = 0.5,
) -> tuple[float | None, str]:
    """This channel's usable MVC reference and where it came from.

    The one place that decides, so the three tabs, the PDF and the CSV cannot
    disagree about the same recording. Precedence:

    1. **recomputed from the ``CAL`` spans**, with the repetitions currently
       kept → :data:`FROM_REPS`;
    2. the **cached ``MVC ref`` annotation** — what a file recorded before the
       two-phase flow carries → :data:`FROM_CACHE`;
    3. nothing → ``(None, NO_CALIBRATION)``.

    Returns ``(value_mV, source_token)``. Render the token for display with
    :func:`reference_source_text`; do not branch on translated text.

    Parameters
    ----------
    channel_index : int
        0-based channel.
    phases, envelope, fs
        What the first rule needs: the parsed spans, the **envelope** of the
        whole recording (untrimmed, so the spans' times still line up) and its
        sampling rate. Any of them missing and the rule is skipped.
    cached : mapping, optional
        ``{channel_index: reference_mV}`` from
        :func:`emgteach.mvc.parse_mvc_ref_markers`.
    keep : collection of int, optional
        1-based repetition numbers to keep. ``None`` keeps them all.
    percentile, window_s
        Measured the same way the wizard measured it: the strongest window of
        ``window_s`` seconds, best of the repetitions.

    Raises
    ------
    ValueError
        If ``keep`` excludes every repetition of a channel that has some.
        Leaving a channel with no repetition is not a calibration with a
        smaller reference, it is no calibration at all — done by not
        calibrating, not by emptying the list — and silently falling back to
        the cached value would answer a question nobody asked.
    """
    reps = phases.reps_for(channel_index) if phases is not None else ()
    if reps and envelope is not None and fs > 0:
        if keep is not None and not any(r.rep in keep for r in reps):
            raise ValueError(
                "keep excludes every calibration repetition of channel "
                f"{channel_index + 1}; at least one has to be kept."
            )
        trozos = slice_reps(envelope, fs, reps, keep=keep)
        ventana = max(1, round(float(window_s) * float(fs)))
        valor = mvc_from_reps(trozos, percentile, window_samples=ventana)
        if valor > 0:
            return float(valor), FROM_REPS

    if cached:
        guardada = cached.get(int(channel_index))
        if guardada and float(guardada) > 0:
            return float(guardada), FROM_CACHE

    return None, NO_CALIBRATION


def reference_source_text(source: str, n_reps: int = 0, *, short: bool = False) -> str:
    """The provenance in words, for the panel that used to say ``MVC source:``.

    Always shown beside the value: a reference the student cannot trace is the
    same trap as an auto-normalised one, only quieter. ``short`` is the
    summary card's version — «calibration» over «(6 repetitions)», two short
    lines — where the full sentence is the report's.
    """
    if source == FROM_REPS:
        if short:
            if n_reps == 1:
                return tr("calibration") + "\n" + tr("(1 repetition)")
            if n_reps > 1:
                return tr("calibration") + "\n" + tr("({n} repetitions)").format(n=n_reps)
            return tr("calibration")
        if n_reps == 1:
            return tr("calibration in this recording (1 repetition)")
        if n_reps > 1:
            return tr(
                "calibration in this recording ({n} repetitions)"
            ).format(n=n_reps)
        return tr("calibration in this recording")
    if source == FROM_CACHE:
        if short:
            return tr("calibration") + "\n" + tr("(as recorded)")
        return tr("calibration as recorded (repetitions not stored)")
    return tr("no calibration")


#: The kinds of stretch a two-phase session is made of. Tokens, not sentences:
#: the interface picks a colour and a wording for each, and neither belongs
#: here — the same lesson as the reference-provenance tokens above.
WARMUP = "warmup"
CALIBRATION = "calibration"
PREPARATION = "preparation"
RECORDING = "recording"


@dataclass(frozen=True)
class PhaseSpan:
    """One named stretch of the session, in file time."""

    start_s: float
    end_s: float
    kind: str
    #: The muscle and repetition for a calibration effort; empty otherwise.
    label: str = ""

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


def phase_spans(
    phases: SessionPhases,
    total_duration_s: float,
    *,
    channel_names: dict[int, str] | None = None,
) -> tuple[PhaseSpan, ...]:
    """The session divided into the stretches it was actually made of.

    What this is for: after a recording, seeing your own session laid out —
    where the warm-up ended, which second each maximal effort occupied, where
    the pause was, where the analysed part begins. The file knows all of it
    and until now only the analysis could read it back.

    The rest between calibration efforts is deliberately left out. Shading it
    would fill the picture edge to edge and the efforts would stop standing
    out, which is the one thing the drawing is for; an unshaded gap between
    two marked efforts reads as rest without having to say so.

    Spans come back sorted by start time and clipped to the recording.
    """
    nombres = channel_names or {}
    fin = max(0.0, float(total_duration_s))
    spans: list[PhaseSpan] = []

    primera_cal = min(
        (r.start_s for r in phases.cal_reps), default=None)
    if phases.warmup_start_s is not None:
        # It runs until there is something else to do: the first maximal
        # effort, or the pause when the practical needs no calibration.
        acaba = primera_cal
        if acaba is None:
            acaba = phases.prep_start_s
        if acaba is None:
            acaba = phases.rec_start_s
        if acaba is not None and acaba > phases.warmup_start_s:
            spans.append(PhaseSpan(
                phases.warmup_start_s, acaba, WARMUP))

    for r in phases.cal_reps:
        if r.end_s > r.start_s:
            nombre = nombres.get(r.channel_index, str(r.channel_index + 1))
            spans.append(PhaseSpan(
                r.start_s, r.end_s, CALIBRATION, f"{nombre} {r.rep}"))

    if phases.prep_start_s is not None:
        acaba = phases.rec_start_s if phases.rec_start_s is not None else fin
        if acaba > phases.prep_start_s:
            spans.append(PhaseSpan(
                phases.prep_start_s, acaba, PREPARATION))

    if phases.rec_start_s is not None and fin > phases.rec_start_s:
        spans.append(PhaseSpan(phases.rec_start_s, fin, RECORDING))

    recortados = [
        PhaseSpan(max(0.0, sp.start_s), min(fin, sp.end_s), sp.kind, sp.label)
        for sp in spans
    ]
    return tuple(sorted(
        (sp for sp in recortados if sp.end_s > sp.start_s),
        key=lambda sp: sp.start_s,
    ))
