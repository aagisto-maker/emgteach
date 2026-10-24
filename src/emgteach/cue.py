"""Audible phase cue for the guided sessions.

A student squeezing as hard as they can for thirty seconds is watching their
hand, or the ceiling, not the screen; and a session built on phases that
change on a timer needs the change announced, or someone calling it out loud
at every bench. Ported unchanged from ecgteach, which took it from eegteach,
where the sessions were born (24 October 2026): the three copies are the same
module, a candidate for the shared core (docs/PLAN-teachcore.md).

**Why not the BITalino buzzer.** It is the obvious hardware answer and it is
the wrong one. The buzzer draws its current from the same battery that feeds
the EMG front-end, so switching it puts a supply transient straight into the
signal; and it vibrates, which moves electrodes and cables when the board is
worn rather than sitting on a table. A tone from the computer is a different
device altogether: no electrical path, no vibration near the electrodes, and
it is emitted by the same code that writes the marker, so it cannot drift out
of step with it.

What no cue can avoid is the startle. That is why the tone is short and quiet
rather than an alarm, and why it can be switched off.
"""

from __future__ import annotations

import io
import logging
import math
import struct
import sys
import threading
import time
import wave

__all__ = [
    "DEFAULT_ENABLED",
    "beep",
    "beep_abort",
    "beep_end",
    "play_wav",
    "render_tone",
]

#: A tone that fails is deliberately never allowed to raise or block - see
#: play_wav - but "never raises" had come to mean "never explains itself"
#: either. A session on 2026-08-07 had the tone enabled, the audio device
#: confirmed working moments earlier, and every phase change went by in
#: silence anyway - a failure this module cannot reproduce on demand, which
#: is exactly the kind that needs a trail the next time it happens rather
#: than another guess. Logging cannot raise, so it costs nothing against the
#: guarantee; with no handler configured elsewhere, Python's own last-resort
#: handler still puts it on stderr, which is where a console launch already
#: has eyes on it.
_LOG = logging.getLogger(__name__)

#: Off by default.
#:
#: This flipped to on for one day (2026-08-07) and back, on a session where
#: the box was ticked, the audio device was confirmed working, and every
#: phase change went by silent anyway. It is on again since 0.4.0, by Ángel's
#: decision after the bench of 5 October 2026: in the Berger session, with the
#: eyes closed, the tone is the only cue, and a box that has to be remembered
#: is a box that gets forgotten. The silent phase changes seen on that bench
#: (the first and last tones sounded, the ones in between did not) are the
#: reason for _WAKE_MS and for the stuck-tone rule in play_wav below.
DEFAULT_ENABLED = True

#: Deliberately mild: enough to be noticed with the eyes closed, not enough to
#: make anyone jump. A startle response ends with a blink, which lands in the
#: last moments of the phase being measured.
_FREQ_HZ = 880
_DURATION_MS = 120
_RATE_HZ = 44100
_VOLUME = 0.35

#: The end-of-session motif: two falling notes.
#:
#: It has to be unmistakably *not* a phase change, because the last phase of
#: the Berger session is recorded with the eyes closed - the subject is
#: waiting for a sound and has no other way to learn that the session is over.
#: Two notes read as an ending where one reads as "next", and falling reads as
#: closing where rising reads as "carry on".
_END_NOTES = ((988, 130), (0, 60), (659, 200))

#: The abort motif: one low, sustained tone. "Open your eyes, this is over."
#:
#: The three existing motifs all mean the session is proceeding — next phase,
#: here is your alpha, well done, finished. None of them can say *stop and
#: come and look*, and that is the one message the subject cannot receive any
#: other way: the app decides to abandon a session precisely when something
#: has gone wrong with the electrodes, which is exactly when the subject is
#: sitting with their eyes shut waiting for a cue that will now never come.
#: Before this they sat there until they gave up and looked.
#:
#: Low and long on purpose, against a vocabulary that is otherwise short and
#: high: 220 Hz is two octaves under the phase cue and the note lasts six
#: times as long, so it cannot be mistaken for a phase change even by someone
#: half-asleep in a dim room. It is also the one cue meant to be slightly
#: unwelcome — a startle costs nothing here, since the recording it would
#: spoil is being abandoned anyway.
_ABORT_NOTES = ((220, 750),)

#: Silence before every motif, in ms. Many sound cards power down after a few
#: seconds with nothing to play and lose the start of the next sound while
#: they wake. A 120 ms phase tone ten seconds after the last one can be lost
#: whole, while the half-second end motif survives in part - which is what
#: the Berger session of 5 Oct 2026 sounded like: first and last tones heard,
#: the ones in between not. Confirmed on the laboratory PC on 5 Oct 2026,
#: runs D/E/F/G: a 120 ms tone every 4 s was heard, every 12 s it was not,
#: and every 12 s with 250 ms or 1 s of silence before it, it was.
#: A quarter of a second of silence opens the stream before the note.
_WAKE_MS = 250

#: Every motif, by key. A dict rather than a chain of conditionals so adding
#: one is a line here and nothing else.
_MOTIFS: dict[str, tuple[tuple[int, int], ...]] = {
    "phase": ((_FREQ_HZ, _DURATION_MS),),
    "end": _END_NOTES,
    "abort": _ABORT_NOTES,
}

#: The rendered tones, built once and kept alive for the life of the process.
#:
#: ``PlaySound`` with ``SND_MEMORY`` reads the buffer *while it plays*, and it
#: plays asynchronously, so the bytes have to outlive the call.
_WAV: dict[str, bytes] = {}


def render_tone(
    notes: tuple[tuple[int, int], ...], *, volume: float = _VOLUME
) -> bytes:
    """A mono 16-bit WAV of ``(frequency_hz, duration_ms)`` notes.

    A frequency of zero is a silence. Every note is faded in and out over 5 ms
    because a hard edge clicks, and a click startles more than the tone does.

    Public so every tone the app makes goes through the same synthesiser.
    """
    edge = max(1, int(0.005 * _RATE_HZ))
    frames = bytearray()
    for freq, ms in notes:
        n = int(_RATE_HZ * ms / 1000)
        for i in range(n):
            if freq <= 0:
                frames += struct.pack("<h", 0)
                continue
            fade = min(1.0, i / edge, (n - i) / edge)
            value = volume * fade * math.sin(2.0 * math.pi * freq * i / _RATE_HZ)
            frames += struct.pack("<h", int(value * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(_RATE_HZ)
        handle.writeframes(bytes(frames))
    return buf.getvalue()


def _tone_wav(key: str = "phase") -> bytes:
    """The cached waveform for any key in :data:`_MOTIFS`.

    An unknown key renders the phase cue rather than raising: a wrong sound
    is a smaller failure than an exception out of a timer callback in the
    middle of a recording, which is the rule this whole module is built on.
    """
    if key not in _WAV:
        notes = _MOTIFS.get(key, _MOTIFS["phase"])
        _WAV[key] = render_tone(((0, _WAKE_MS), *notes))
    return _WAV[key]


def beep_abort() -> None:
    """Emit the abort motif. Never raises, and never blocks.

    The rule for sounding it: the app has something the subject must open
    their eyes for — a session it has abandoned, or one it judges is not
    working and wants them to interrupt. Never as an acknowledgement of
    something the operator has already done: whoever just pressed Stop has
    their eyes open and knows, and a tone there would only teach them to
    ignore this one.
    """
    _play("abort")


def beep_end() -> None:
    """Emit the end-of-session motif. Never raises, and never blocks.

    Distinct from :func:`beep` on purpose: the Berger session ends on a phase
    recorded with the eyes closed, so without a sound that says *finished*
    rather than *next* the subject is left sitting there waiting for a cue
    that never comes.
    """
    _play("end")


def beep() -> None:
    """Emit the phase-change tone. Never raises, and never blocks.

    A cue that cannot sound is a small inconvenience; an exception raised from
    a timer callback in the middle of a recording is a lost session. Every
    failure path here therefore ends in silence.

    **Why a synthesised WAV and not winsound.Beep.** Beep() goes through the
    kernel's beep path, which is emulated on modern Windows and turned out to
    be silent on the lab machine even though the call blocked for its full
    duration - it reported success and made no sound. PlaySound with a buffer
    of our own goes to the default audio device like any other application.
    It is also asynchronous: Beep() held the GUI thread for 130 ms at every
    phase change, which is a visible stall in the live traces during a
    recording.
    """
    _play("phase")


#: Who hears what became of each cue: called as ``report(kind, seconds)``
#: with kind «sounded», «dropped», «stuck» or «failed». The executable has no
#: console and no logging handler, so the warnings below went nowhere; the
#: acquisition tab sets this and writes a line in its event log (annex of
#: 6 Oct 2026). It is called from the tone's thread: whoever sets it must
#: pass the line on to its own thread.
_report = None


def set_tone_report(report) -> None:
    """Set (or clear, with ``None``) who is told about each cue."""
    global _report
    _report = report


def _tell(kind: str, seconds: float) -> None:
    report = _report
    if report is None:
        return
    try:
        report(kind, float(seconds))
    except Exception:  # pragma: no cover - a report must never cost a tone
        _LOG.warning("The tone report failed.", exc_info=True)


def _play(key: str) -> None:
    """Sound one of the cached waveforms, swallowing every failure.

    These are the cues - phase, end, abort - and each one is reported
    (set_tone_report); a tone played straight through play_wav, such as a
    neurofeedback tone a second, is not.
    """
    play_wav(_tone_wav(key), report=True)


#: Held while a tone sounds. A tone that arrives meanwhile is dropped, not
#: queued: with one thread per tone, an audio device that stopped answering
#: left every later tone's thread blocked in PlaySound for good - fifty tones,
#: fifty threads (measured on 30 Sep 2026; eegteach's suite hung with more
#: than a hundred). One tone at a time keeps it to one thread, and in normal
#: use changes nothing: the tones are seconds apart and last a fraction of one.
_SOUNDING = threading.Lock()

#: When the tone holding the lock started, and how long one may hold it before
#: it is taken as stuck. A stuck tone must not silence the ones after it: the
#: next one gets a lock of its own and the stuck thread keeps the old one.
#: At most _MAX_STUCK times per process, so a device that never answers again
#: cannot pile up threads as it did before the lock.
_sounding_since = 0.0
_STUCK_S = 2.0
_MAX_STUCK = 4
_stuck = 0


def _play_and_release(data: bytes, lock: threading.Lock | None = None,
                      report: bool = False) -> None:
    """Sound *data* on this helper thread, then let the next tone through."""
    started = time.monotonic()
    try:
        ok = _play_sync_on_thread(data)
    finally:
        (lock if lock is not None else _SOUNDING).release()
    if report:
        _tell("sounded" if ok else "failed", time.monotonic() - started)


def _play_sync_on_thread(data: bytes) -> bool:
    """The ``winsound.PlaySound`` call itself, run off the GUI thread.

    Never lets an exception escape to the thread boundary - one raised there
    does not propagate to whoever started the thread, but Python's default
    unraisable-hook still prints a full traceback, which is noise for a tone
    that failed for an ordinary reason (muted output, no device). It is
    logged instead, at a level a console launch will still show: silence
    that leaves no trace is indistinguishable from a tone that was never
    attempted, and telling those two apart is the point.
    """
    import winsound

    try:
        # winsound's names exist only on Windows, where this runs.
        flags = winsound.SND_MEMORY | winsound.SND_NODEFAULT  # type: ignore[attr-defined,unused-ignore]
        winsound.PlaySound(data, flags)  # type: ignore[attr-defined,unused-ignore]
    except Exception:
        _LOG.warning("PlaySound failed; the tone did not sound.", exc_info=True)
        return False
    return True


def play_wav(data: bytes, report: bool = False) -> None:
    """Sound an in-memory WAV. Never raises, and never blocks.

    The caller must keep *data* alive for at least as long as it takes to
    start the thread below: both callers hold theirs in a module-level cache
    for the life of the process, so that is never in question.

    **Why not ``SND_ASYNC``.** It looks like the obvious way to avoid
    blocking the caller, and it is what this used to do — silently, because
    Python's ``winsound`` binding refuses the combination outright:
    ``PlaySound(data, SND_MEMORY | SND_ASYNC)`` raises ``RuntimeError:
    Cannot play asynchronously from memory`` on every call, on every version
    of Windows, and always did. The restriction exists because the Win32 API
    reads the buffer on its own schedule while playing it asynchronously, and
    Python cannot promise the buffer will still exist when it gets around to
    it; play from a file instead and the OS owns the read, which is why
    ``SND_ASYNC`` is fine there. The exception was reaching the ``except``
    below every single time, so no tone from this module had ever actually
    played — not the phase cue, not the alpha feedback tone, on any machine.

    The fix is not to fight the restriction but to sidestep the reason for
    it: play synchronously, on a short-lived helper thread, so the calling
    thread — normally the GUI thread, inside a timer callback — never blocks.
    The buffer's lifetime is no longer in question either, since it is a
    plain function argument for as long as the synchronous call needs it.
    """
    global _SOUNDING, _sounding_since, _stuck
    if sys.platform == "win32":
        lock = _SOUNDING
        if not lock.acquire(blocking=False):
            held = time.monotonic() - _sounding_since
            if held < _STUCK_S or _stuck >= _MAX_STUCK:
                # A tone is still sounding: this one is dropped, and said, so
                # a console launch shows which cues never reached the card.
                _LOG.warning("Tone dropped: the previous one has been sounding "
                             "for %.2f s.", held)
                if report:
                    _tell("dropped", held)
                return
            # The previous tone is stuck in PlaySound: it keeps its lock and
            # its thread, and this one gets a lock of its own.
            _stuck += 1
            _LOG.warning("A tone has been stuck for %.1f s; the next one sounds "
                         "on its own (%d of %d).", held, _stuck, _MAX_STUCK)
            lock = threading.Lock()
            lock.acquire()
            _SOUNDING = lock
            if report:
                _tell("stuck", held)
        _sounding_since = time.monotonic()
        try:
            threading.Thread(
                target=_play_and_release, args=(data, lock, report), daemon=True
            ).start()
            return
        except Exception:  # pragma: no cover - defensive
            lock.release()
            _LOG.warning("Could not start the tone thread.", exc_info=True)
    # Anywhere else, and as the fallback when the tone cannot be synthesised:
    # the platform's own alert sound. QtMultimedia would give a nicer one but
    # it is excluded from the frozen build on purpose, for about fifty
    # megabytes.
    try:  # pragma: no cover - needs a QApplication and an audio device
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.beep()
    except Exception:  # pragma: no cover - defensive
        _LOG.warning("The Qt fallback beep failed too.", exc_info=True)
