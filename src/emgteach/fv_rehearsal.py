"""A dry run of the guided force-velocity acquisition, with no hardware.

The guided wizard is the most involved procedure in the application: a maximum
with no load, then a cued lift at each load, with prompts that appear and
vanish on a timer while the subject is holding a weight. That is a bad moment
to be reading the manual, and a worse one to discover that the accelerometer
is on the wrong segment. So the procedure can be rehearsed first — the same
prompts, in the same order, over a synthetic recording — before anyone is
strapped to anything.

Two things live here, both free of Qt so they can be tested directly:

* :func:`cue_script` — the sequence of prompts the wizard will show, derived
  from the same load plan the real one takes. The wording lives in the
  acquisition tab, which owns the state machine; what this reproduces is the
  **order and the timing**, and ``tests/test_fv_rehearsal.py`` drives the real
  state machine to check the two have not drifted apart.
* :func:`synthetic_trial` — an EMG and accelerometer recording of a subject
  who behaves. It is generated to obey the two relationships the study exists
  to show, so the rehearsal ends on curves with the right shape rather than on
  noise: heavier loads move slower (Hill) and need more activation (Henneman).

The synthetic recording is deliberately fed through the *real* analysis
pipeline rather than having its curves drawn directly. A rehearsal that drew
an idealised picture of its own would be a drawing of what the study is
supposed to produce; this way it is the study's own output.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "Cue",
    "PHASE_MVC_CONTRACT",
    "PHASE_MVC_READY",
    "PHASE_MVC_REST",
    "PHASE_DONE",
    "PHASE_LIFT",
    "PHASE_PREPARE",
    "PHASE_REST",
    "REHEARSAL_EMG_CHANNEL",
    "REHEARSAL_ACC_CHANNEL",
    "cue_script",
    "synthetic_trial",
    "total_seconds",
    "write_rehearsal_edf",
]

#: Channel labels of the rehearsal's EDF. The accelerometer is labelled as if
#: it were on the moving segment, because that is where the force-velocity
#: study needs it — a rehearsal that wrote "(muscle)" would demonstrate the
#: mistake the plan dialog warns about.
REHEARSAL_EMG_CHANNEL = "EMG"
REHEARSAL_ACC_CHANNEL = "ACC (limb)"

# The phase names are the acquisition tab's own, so a reader comparing the two
# is not also translating vocabulary.
PHASE_MVC_READY = "mvc_ready"
PHASE_MVC_CONTRACT = "mvc_contract"
PHASE_MVC_REST = "mvc_rest"
PHASE_PREPARE = "ready"
PHASE_LIFT = "contract"
PHASE_REST = "rest"
PHASE_DONE = "done"


@dataclass(frozen=True)
class Cue:
    """One prompt in the wizard's run: what is shown, and for how long.

    ``load`` is 0 for the three opening phases, which carry no weight. ``index``
    and ``rep`` are 1-based to match the "(load 2/4, rep 1/1)" the wizard puts
    on screen.
    """

    phase: str
    seconds: float
    load: float = 0.0
    index: int = 0
    rep: int = 0
    #: Start of this cue within the run, filled in by :func:`cue_script`.
    start: float = 0.0

    @property
    def end(self) -> float:
        return self.start + self.seconds

    @property
    def is_lift(self) -> bool:
        """True for a window that gets marked in the EDF with its load."""
        return self.phase == PHASE_LIFT


def cue_script(
    loads: list[float],
    reps: int = 1,
    prep_s: float = 5.0,
    lift_s: float = 1.5,
    *,
    mvc_ready_s: float = 3.0,
    mvc_hold_s: float = 3.0,
    mvc_rest_s: float = 5.0,
    rest_s: float = 2.0,
) -> list[Cue]:
    """The prompts the guided wizard will show, in order, with their timing.

    The defaults are the acquisition tab's constants (``MVC_READY_S``,
    ``FV_MVC_HOLD_S``, ``FV_MVC_TO_LOADS_REST_S``, ``MVC_REST_S``); they are
    parameters so a test can drive both this and the real state machine with
    the same numbers.

    The trailing rest after the very last lift is dropped: the real wizard
    finishes on that lift and goes straight to its "loads recorded" panel.
    """
    reps = max(1, int(reps))
    cues: list[Cue] = []
    t = 0.0

    def add(phase, seconds, load=0.0, index=0, rep=0):
        nonlocal t
        cues.append(Cue(phase, seconds, load, index, rep, start=t))
        t += seconds

    add(PHASE_MVC_READY, mvc_ready_s)
    add(PHASE_MVC_CONTRACT, mvc_hold_s)
    add(PHASE_MVC_REST, mvc_rest_s)

    n = len(loads)
    for i, kg in enumerate(loads, start=1):
        for r in range(1, reps + 1):
            add(PHASE_PREPARE, prep_s, kg, i, r)
            add(PHASE_LIFT, lift_s, kg, i, r)
            if not (i == n and r == reps):
                add(PHASE_REST, rest_s, kg, i, r)

    add(PHASE_DONE, 5.0)
    return cues


def total_seconds(cues: list[Cue]) -> float:
    return cues[-1].end if cues else 0.0


# -- the synthetic subject ---------------------------------------------------

#: Hill's hyperbola put in the form the rehearsal needs — the velocity a muscle
#: reaches against a load, as a fraction of its unloaded maximum. ``F0`` is the
#: load at which it would stall; it is set above the heaviest load in the plan
#: so every load in the rehearsal still moves.
def _hill_velocity(load: float, f0: float) -> float:
    a = 0.30 * f0            # Hill's a/F0 ≈ 0.25-0.30 for most muscles
    return 0.30 * (f0 - load) / (load + a)


def _activation(load: float, f0: float) -> float:
    """Envelope amplitude against load — Henneman's size principle.

    Roughly linear in load with a non-zero intercept: even the lightest lift
    recruits something, and the relation does not pass through the origin.
    """
    return 0.35 + 0.55 * (load / f0)


def synthetic_trial(
    loads: list[float],
    reps: int = 1,
    fs: float = 1000.0,
    prep_s: float = 5.0,
    lift_s: float = 1.5,
    *,
    cues: list[Cue] | None = None,
    mvc_mv: float = 1.4,
    seed: int = 20260827,
) -> dict:
    """An EMG + accelerometer recording of a well-behaved subject.

    Returns ``emg_raw`` (mV), ``acc_raw`` (g), ``fs``, ``markers`` as the EDF
    ``(onset_s, label)`` pairs the guided wizard writes, and the ``cues`` the
    timeline was built from.

    The subject is well behaved on purpose. A rehearsal is for learning the
    sequence of steps, so the signal should not also be a puzzle; the failures
    worth teaching (a flat accelerometer, a missed lift) are what the real
    dialog's own warnings are for.
    """
    from emgteach.force_velocity import fv_load_marker

    cues = cues or cue_script(loads, reps, prep_s, lift_s)
    rng = np.random.default_rng(seed)
    n = int(np.ceil(total_seconds(cues) * fs)) + 1
    t = np.arange(n) / fs

    # Baseline: a little instrumentation noise on the EMG, gravity plus tremor
    # on the accelerometer. Gravity is what the study's high-pass removes.
    emg = rng.normal(0.0, 0.006, n)
    acc = np.full(n, 0.98) + rng.normal(0.0, 0.004, n)

    f0 = 1.30 * max(loads) if loads else 1.0
    markers: list[tuple[float, str]] = []

    for cue in cues:
        i0, i1 = int(cue.start * fs), min(n, int(cue.end * fs))
        if i1 <= i0:
            continue
        span = t[i0:i1] - cue.start

        if cue.phase == PHASE_MVC_CONTRACT:
            # A sustained maximum: a plateau with the slight decline of a real
            # maximal effort, and no movement — it is isometric, so the
            # accelerometer must stay flat here or the study would read a
            # velocity for a contraction that never moved.
            shape = np.tanh(span / 0.35) * (1.0 - 0.08 * span / cue.seconds)
            emg[i0:i1] += rng.normal(0.0, mvc_mv, i1 - i0) * shape

        elif cue.phase == PHASE_LIFT:
            markers.append((cue.start, fv_load_marker(cue.load)))
            # EMG: one burst, taller for a heavier load.
            amp = mvc_mv * _activation(cue.load, f0)
            burst = np.sin(np.pi * np.clip(span / cue.seconds, 0, 1)) ** 2
            emg[i0:i1] += rng.normal(0.0, amp, i1 - i0) * burst
            # Movement: a half-sine velocity bump, faster for a lighter load.
            # The accelerometer records its derivative, which is what the
            # study integrates back — so the peak velocity it recovers is the
            # one Hill's equation asked for.
            dur = min(0.65, 0.85 * cue.seconds)
            vp = _hill_velocity(cue.load, f0)
            m = span <= dur
            acc[i0:i1][m] += vp * np.pi / dur * np.cos(np.pi * span[m] / dur)

    return {
        "emg_raw": emg,
        "acc_raw": acc,
        "fs": fs,
        "markers": markers,
        "cues": cues,
    }


def write_rehearsal_edf(trial: dict, path) -> str:
    """Write a rehearsal's synthetic recording to a real EDF+ file.

    So that the rehearsal can finish in the *actual* force-velocity study
    dialog rather than a mock-up of it: the study opens an EDF, so the
    rehearsal hands it one, load markers and all. What the student sees at the
    end is the real analysis, run on a subject who did the protocol properly.
    """
    from emgteach.io import BufferedEdfWriter, ChannelInfo

    fs = int(round(float(trial["fs"])))
    emg = np.asarray(trial["emg_raw"], dtype=np.float64)
    acc = np.asarray(trial["acc_raw"], dtype=np.float64)
    channels = [
        ChannelInfo(REHEARSAL_EMG_CHANNEL, sample_frequency=fs),
        # Wide enough for the synthetic movement; "g" is what the reader keys
        # off to find the accelerometer.
        ChannelInfo(REHEARSAL_ACC_CHANNEL, dimension="g", physical_min=-8.0,
                    physical_max=8.0, sample_frequency=fs),
    ]
    with BufferedEdfWriter(str(path), channels=channels) as w:
        for i in range(0, emg.size, fs):
            w.add_samples(emg[i:i + fs], acc[i:i + fs])
        for onset, label in trial["markers"]:
            w.add_annotation(float(onset), str(label))
    return str(path)
