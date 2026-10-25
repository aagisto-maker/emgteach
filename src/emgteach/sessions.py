"""Guided sessions of the one-muscle practical: timed scripts, marked in the file.

The pair practical and the kinematics practical already guide their task; the
one-muscle practical, the one students do most, left it to the student and a
stopwatch. A guided session is a fixed sequence of phases — announced, timed,
with an optional tone at every change — whose measured stretches are written
into the recording as EDF+ annotations, so the file analyses itself afterwards.
It is the idea of ecgteach's and eegteach's guided sessions with emgteach's
own vocabulary: the prompts go to the panel over the plots and to the phones,
and the marks are ASCII codes in the idiom of the phase marks
(:mod:`emgteach.phases`), not translated text::

    GRAD start steps=5 v=1          the session begins (its family and version)
    GRAD step start k=1 pct=20      a measured stretch opens…
    GRAD step end k=1               …and closes
    ...
    GRAD end                        the session ran to its end
    GRAD end stopped                or was stopped before it

Three rules the analysis depends on:

* **Only closed stretches count.** A ``start`` with no ``end`` is dropped, which
  is what a recording stopped in the middle of an effort leaves behind — as
  :func:`emgteach.phases.parse_phase_markers` does with a calibration
  repetition.
* **The family is the first word**, in capitals, and is one of
  :data:`FAMILIES`. Nothing a student can type with the manual marker starts
  that way, so a session mark is never read as a student's and the reverse.
* **``v=`` versions the script.** A script whose phases change keeps reading
  the files recorded with the old one.

Qt-free, like :mod:`emgteach.phases`: the acquisition tab runs the script, the
analysis worker reads the marks, and the tests do both without a display.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

__all__ = [
    "EFFORT",
    "FAMILIES",
    "GRADATION_STEPS_PCT",
    "HOLD_MAX_S",
    "READY",
    "REST",
    "GuidedSession",
    "MeasuredSpan",
    "SessionPhase",
    "SessionScript",
    "end_marker",
    "gradation_script",
    "header_marker",
    "hold_script",
    "intermittent_script",
    "is_session_marker",
    "parse_session_markers",
    "span_end_marker",
    "span_start_marker",
]

#: What a phase asks of the subject, which is also how the panel shows it.
#: A countdown before an effort.
READY = "ready"
#: An effort, timed; the panel shows the seconds left and the load.
EFFORT = "effort"
#: Rest, timed.
REST = "rest"
_KINDS = (READY, EFFORT, REST)

#: The families of session marks. One per guided session; a new session adds
#: its family here so the analysis and the review recognise its marks.
FAMILIES: tuple[str, ...] = ("GRAD", "HOLD")

_FAMILY = "|".join(FAMILIES)
#: ``GRAD start …`` / ``GRAD end …`` — the session itself.
_SESSION_RE = re.compile(rf"^\s*({_FAMILY})\s+(start|end)\b(.*)$")
#: ``GRAD step start …`` / ``GRAD step end …`` — a measured stretch.
_SPAN_RE = re.compile(rf"^\s*({_FAMILY})\s+([a-z]+)\s+(start|end)\b(.*)$")
_PARAM_RE = re.compile(r"([a-z]+)(?:=(\S+))?")


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _params(params: dict[str, object]) -> str:
    """``k=1 pct=20``, in the order given; a ``True`` value is a bare flag."""
    partes = []
    for clave, valor in params.items():
        if valor is True:
            partes.append(clave)
        elif valor is not None and valor is not False:
            texto = f"{valor:g}" if isinstance(valor, float) else str(valor)
            partes.append(f"{clave}={texto}")
    return (" " + " ".join(partes)) if partes else ""


def header_marker(family: str, version: int = 1, **params: object) -> str:
    """The mark that opens a session: its family, its parameters, its version."""
    return f"{family} start{_params({**params, 'v': int(version)})}"


def end_marker(family: str, *, stopped: bool = False) -> str:
    """The mark that closes a session, completed or stopped."""
    return f"{family} end{_params({'stopped': stopped})}"


def span_start_marker(family: str, name: str, **params: object) -> str:
    """The mark that opens a measured stretch."""
    return f"{family} {name} start{_params(params)}"


def span_end_marker(family: str, name: str, **params: object) -> str:
    """The mark that closes a measured stretch."""
    return f"{family} {name} end{_params(params)}"


# ---------------------------------------------------------------------------
# The script
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionPhase:
    """One phase of a guided session, as the subject lives it.

    ``title`` and ``text`` are English canonical strings, translated when
    shown. ``level`` is what the simulated board's subject is asked for during
    the phase (0..1 of its maximum; ``None`` for rest), so a session can be
    rehearsed and tested without hardware. ``target_pct`` is the band of the
    load bar the phase aims at, in % MVC, for the panel to draw.

    ``opens`` and ``closes`` are the marks written at the phase's start and
    end; empty for a phase that is not measured — the rests between efforts
    are the gaps between marks, as the rest between calibration efforts is.
    ``cue`` says whether its start is announced (with the tone); a phase that
    only continues the one before it is not. ``fmt`` fills the ``{…}`` of the
    title and the text once translated (``(("pct", 40),)``), so the catalogue
    holds one entry for every step.
    """

    key: str
    kind: str
    seconds: float
    title: str
    text: str = ""
    level: float | None = None
    target_pct: tuple[float, float] | None = None
    opens: str = ""
    closes: str = ""
    cue: bool = True
    fmt: tuple[tuple[str, object], ...] = ()
    #: Start of this phase within the session, filled in by
    #: :meth:`SessionScript.timed`.
    start: float = 0.0

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise ValueError(f"Phase {self.key!r} has an unknown kind {self.kind!r}.")
        if self.seconds <= 0:
            raise ValueError(
                f"Phase {self.key!r} has a non-positive duration ({self.seconds})."
            )

    @property
    def end(self) -> float:
        return self.start + self.seconds


@dataclass(frozen=True)
class SessionScript:
    """A whole guided session: its phases in order and the words around them.

    ``key`` names it in the interface and in settings; ``slug`` goes into the
    proposed file name. ``needs_mvc`` makes recording calibrate first, as the
    pair practical does. ``header`` is written when the session begins and
    ``family`` decides its end mark.
    """

    key: str
    family: str
    title: str
    slug: str
    header: str
    phases: tuple[SessionPhase, ...]
    needs_mvc: bool = False
    #: One line for the tooltip of the session chooser, and what fills its ``{…}``.
    summary: str = ""
    fmt: tuple[tuple[str, object], ...] = ()
    #: The gesture the session's efforts are made with, said to the student
    #: by the calibration too: the reference is measured with the movement
    #: the experiment then asks for, and the two say it in the same words.
    gesture: str = ""

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"Unknown session family {self.family!r}.")
        if not self.phases:
            raise ValueError(f"Session {self.key!r} has no phases.")

    def timed(self) -> tuple[SessionPhase, ...]:
        """The phases with their start times filled in, tiling the session."""
        t = 0.0
        out = []
        for fase in self.phases:
            out.append(replace(fase, start=t))
            t += fase.seconds
        return tuple(out)

    @property
    def total_seconds(self) -> float:
        return float(sum(f.seconds for f in self.phases))

    def with_seconds(self, seconds: float) -> SessionScript:
        """The same script with every phase lasting *seconds*: for tests."""
        return replace(self, phases=tuple(
            replace(f, seconds=float(seconds)) for f in self.phases))


# ---------------------------------------------------------------------------
# The sessions
# ---------------------------------------------------------------------------

#: Every session of the one-muscle practical is made with the fist, and the
#: calibration that precedes it asks for the same gesture (Ángel, 25 Oct 2026:
#: the calibration said «a brief, explosive jerk» and the session «squeeze
#: your fist», and the student did not know they were the same movement).
_FIST = "Clench your fist: a brief, explosive jerk."

#: The gradation's targets, % MVC. Five and not four: with four (25, 50, 75,
#: 100) the curve has three intervals; with five its bend can be seen.
GRADATION_STEPS_PCT: tuple[int, ...] = (20, 40, 60, 80, 100)
#: Seconds of each step, of the rest between steps, and of the rests that
#: open and close the session (plan, §4.1).
GRADATION_STEP_S = 4.0
GRADATION_REST_S = 6.0
GRADATION_EDGE_S = 5.0
#: Half the width of the band each step aims at, % MVC.
_GRADATION_BAND = 5.0


def gradation_script() -> SessionScript:
    """Contractions of growing strength, each held a few seconds.

    The envelope grows with the force — monotonically, and not in proportion,
    which is the lesson. The steps are asked for as a share of the bar, so the
    session calibrates first (Ángel's decision of 24 October 2026: without
    the bar the student cannot grade).
    """
    n = len(GRADATION_STEPS_PCT)
    fases: list[SessionPhase] = [SessionPhase(
        "rest_0", REST, GRADATION_EDGE_S, "Rest",
        "Leave your hand loose on the table.")]
    for k, pct in enumerate(GRADATION_STEPS_PCT, start=1):
        maximo = pct >= 100
        fases.append(SessionPhase(
            f"step_{k}", EFFORT, GRADATION_STEP_S,
            "Step {k} of {n}: maximum" if maximo else "Step {k} of {n}: {pct} %",
            ("Squeeze your fist as hard as you can and hold it."
             if maximo else "Squeeze your fist up to {pct} % of the bar and hold it there."),
            level=pct / 100.0,
            target_pct=(100.0 - 2 * _GRADATION_BAND, 100.0) if maximo
            else (pct - _GRADATION_BAND, pct + _GRADATION_BAND),
            opens=span_start_marker("GRAD", "step", k=k, pct=pct),
            closes=span_end_marker("GRAD", "step", k=k),
            fmt=(("k", k), ("n", n), ("pct", pct)),
        ))
        if k < n:
            fases.append(SessionPhase(
                f"rest_{k}", REST, GRADATION_REST_S, "Rest", "Let go and rest."))
    fases.append(SessionPhase(
        "rest_end", REST, GRADATION_EDGE_S, "Rest",
        "Let go. That was the last one: the recording stops on its own."))
    return SessionScript(
        key="gradacion", family="GRAD", title="Graded contractions", slug="graduales",
        header=header_marker("GRAD", steps=n), phases=tuple(fases), needs_mvc=True,
        summary="Five contractions of growing strength, 20 to 100 % of the bar, "
                "four seconds each with rest between them. Calibrates first.",
        gesture=_FIST,
    )


#: The sustained maximum: 10 s by default and never more than 45. Ángel's
#: decision of 24 October 2026 was 30 s; on the 25th, after trying it, 10 s:
#: with a maximal effort the fall is seen in ten, and thirty are long.
HOLD_DEFAULT_S = 10.0
HOLD_MAX_S = 45.0
_HOLD_BEFORE_S = 5.0
_HOLD_COUNT_S = 3.0
_HOLD_AFTER_S = 10.0


def hold_script(seconds: float = HOLD_DEFAULT_S) -> SessionScript:
    """One maximal contraction, held: the amplitude and the MDF fall.

    Isometric, the forearm resting and the fist against the table, with no
    weight in the hand. The text tells the student to breathe — a maximal
    effort held with the breath held is a Valsalva — and to let go if it
    hurts. The calibration is optional: without it the panel's bar is the
    effort against the peak of this same contraction.
    """
    secs = float(seconds)
    if not 0 < secs <= HOLD_MAX_S:
        raise ValueError(f"A sustained maximum lasts at most {HOLD_MAX_S:g} s, not {secs:g}.")
    fases = (
        SessionPhase("rest_0", REST, _HOLD_BEFORE_S, "Rest",
                     "Forearm on the table, fist closed without squeezing."),
        SessionPhase("ready", READY, _HOLD_COUNT_S, "Squeeze as hard as you can at 0",
                     "And keep it up for {secs:g} seconds.", fmt=(("secs", secs),)),
        SessionPhase("effort", EFFORT, secs, "Maximum: keep it up",
                     "Squeeze as hard as you can and keep it up. Breathe: do not "
                     "hold your breath. If it hurts, let go.", level=1.0,
                     opens=span_start_marker("HOLD", "effort", secs=secs),
                     closes=span_end_marker("HOLD", "effort")),
        SessionPhase("rest_end", REST, _HOLD_AFTER_S, "Rest",
                     "Let go and let the hand drop. The recording stops on its own."),
    )
    return SessionScript(
        key="fatiga", family="HOLD", title="Fatigue: sustained contraction",
        slug="fatiga_mantenida",
        header=header_marker("HOLD", mode="sustained", secs=secs), phases=fases,
        summary="One maximal contraction held for {secs:g} s, with rest before "
                "and after. The amplitude and the MDF fall as it is held.",
        fmt=(("secs", secs),), gesture=_FIST,
    )


#: The intermittent maximum: six contractions of 5 s with 1 s between them.
#: Ten at first; six after Ángel tried it (25 Oct 2026): enough to see the fall.
#: Ángel's pilots of 24 October 2026: with 5/1 s the RMS fell 21 % almost
#: steadily over ten; with 5/2 s and 5/5 s the fall was irregular.
INTERMITTENT_REPS = 6
INTERMITTENT_ON_S = 5.0
INTERMITTENT_OFF_S = 1.0


def intermittent_script(reps: int = INTERMITTENT_REPS, on_s: float = INTERMITTENT_ON_S,
                        off_s: float = INTERMITTENT_OFF_S) -> SessionScript:
    """Maximal contractions with a short rest between them, timed by the app.

    The measure is each contraction's RMS, not its peak: the peak is the
    start of each contraction, and it does not fall. Tone at the start and
    at the end of every contraction, and the seconds always on screen: timing
    it by hand was what made the pilots hard.
    """
    n = int(reps)
    fases: list[SessionPhase] = [
        SessionPhase("rest_0", REST, _HOLD_BEFORE_S, "Rest",
                     "Forearm on the table, fist closed without squeezing."),
        SessionPhase("ready", READY, _HOLD_COUNT_S, "Squeeze as hard as you can at 0",
                     "{n} contractions of {on:g} s, {off:g} s apart.",
                     fmt=(("n", n), ("on", on_s), ("off", off_s))),
    ]
    for k in range(1, n + 1):
        fases.append(SessionPhase(
            f"rep_{k}", EFFORT, float(on_s), "Contraction {k} of {n}: maximum",
            "Squeeze as hard as you can. Breathe.", level=1.0,
            opens=span_start_marker("HOLD", "rep", n=k),
            closes=span_end_marker("HOLD", "rep", n=k),
            fmt=(("k", k), ("n", n)),
        ))
        if k < n:
            fases.append(SessionPhase(
                f"off_{k}", READY, float(off_s), "Let go: {k} of {n} done",
                "The next one comes at 0.", fmt=(("k", k), ("n", n))))
    fases.append(SessionPhase(
        "rest_end", REST, _HOLD_AFTER_S, "Rest",
        "Let go and let the hand drop. The recording stops on its own."))
    return SessionScript(
        key="fatiga_intermitente", family="HOLD",
        title="Fatigue: intermittent contractions",
        slug="fatiga_intermitente",
        header=header_marker("HOLD", mode="intermittent", reps=n, on=float(on_s),
                             off=float(off_s)),
        phases=tuple(fases),
        summary="{n} maximal contractions of {on:g} s with {off:g} s between them; "
                "the RMS of each one falls as the muscle tires.",
        fmt=(("n", n), ("on", on_s), ("off", off_s)), gesture=_FIST,
    )


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _parse_params(text: str) -> dict[str, str]:
    """``k=1 pct=20 stopped`` → ``{"k": "1", "pct": "20", "stopped": ""}``."""
    return {m.group(1): (m.group(2) or "") for m in _PARAM_RE.finditer(text)}


def is_session_marker(description: str) -> bool:
    """Whether an annotation is a guided session's, rather than a student's mark."""
    text = str(description)
    return bool(_SESSION_RE.match(text) or _SPAN_RE.match(text))


@dataclass(frozen=True)
class MeasuredSpan:
    """One measured stretch of a session, delimited in the recording."""

    name: str
    start_s: float
    end_s: float
    #: The parameters of its ``start`` mark, as written (``{"k": "1", …}``).
    params: dict[str, str] = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)

    def number(self, key: str, default: float | None = None) -> float | None:
        """A parameter as a number, or *default* when missing or not a number."""
        try:
            return float(self.params[key])
        except (KeyError, ValueError):
            return default


@dataclass(frozen=True)
class GuidedSession:
    """What a recording's annotations say about the guided session in it."""

    family: str
    start_s: float
    #: The ``end`` mark, or ``None`` when the recording stopped first.
    end_s: float | None
    params: dict[str, str]
    spans: tuple[MeasuredSpan, ...]
    #: Ran to its end: the ``end`` mark is there and does not say «stopped».
    completed: bool

    @property
    def version(self) -> int:
        try:
            return int(self.params.get("v", "1"))
        except ValueError:
            return 1

    def spans_named(self, name: str) -> tuple[MeasuredSpan, ...]:
        return tuple(s for s in self.spans if s.name == name)


def parse_session_markers(
    markers: Iterable[tuple[float, str]],
) -> GuidedSession | None:
    """The guided session a recording carries, or ``None`` if it has none.

    A file holds one session: the flow starts it once and the recording stops
    when it ends. Should a file carry more than one, the **last** is read, on
    the reasoning :func:`emgteach.phases.parse_phase_markers` applies to
    ``REC start``: the one the session finished with describes the file.

    A stretch is reported only once **closed**; a second ``start`` of the same
    stretch before its ``end`` replaces the first, and an ``end`` with nothing
    open is ignored. A stretch is matched to its end by its name and, when the
    end carries them, by the parameters both share (``k=``, ``n=``).
    """
    actual: dict | None = None
    sesiones: list[dict] = []

    for onset, desc in sorted(markers, key=lambda m: float(m[0])):
        t = float(onset)
        texto = str(desc)
        cab = _SESSION_RE.match(texto)
        if cab:
            familia, que, resto = cab.group(1), cab.group(2), cab.group(3)
            if que == "start":
                actual = {"family": familia, "start": t, "end": None,
                          "params": _parse_params(resto), "open": {},
                          "spans": [], "stopped": False}
                sesiones.append(actual)
            elif actual is not None and actual["family"] == familia:
                actual["end"] = t
                actual["stopped"] = "stopped" in _parse_params(resto)
                actual = None
            continue
        tramo = _SPAN_RE.match(texto)
        if not tramo or actual is None or tramo.group(1) != actual["family"]:
            continue
        nombre, que, params = tramo.group(2), tramo.group(3), _parse_params(tramo.group(4))
        if que == "start":
            actual["open"][nombre] = (t, params)
            continue
        abierto = actual["open"].get(nombre)
        if abierto is None:
            continue
        inicio, p_inicio = abierto
        if any(p_inicio.get(k) != v for k, v in params.items() if k in p_inicio):
            continue                       # the end of another one
        del actual["open"][nombre]
        if t > inicio:
            actual["spans"].append(MeasuredSpan(nombre, inicio, t, p_inicio))

    if not sesiones:
        return None
    s = sesiones[-1]
    return GuidedSession(
        family=s["family"], start_s=s["start"], end_s=s["end"],
        params=s["params"], spans=tuple(s["spans"]),
        completed=s["end"] is not None and not s["stopped"],
    )
