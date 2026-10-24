"""The audible phase cue must never be able to end a recording.

A cue that cannot sound is a small inconvenience. An exception raised out of a
timer callback in the middle of an acquisition is a lost session, and the
sound path is exactly where a lab PC differs from a development one: no audio
device, a muted output, a virtual machine.
"""

from __future__ import annotations

import io
import struct
import sys
import threading
import time

import pytest

from emgteach import cue


@pytest.fixture(autouse=True)
def _the_previous_tone_has_finished():
    """One tone sounds at a time and a tone meanwhile is dropped, so each
    test starts once the previous test's tone, a real one, has ended."""
    if cue._SOUNDING.acquire(timeout=5):
        cue._SOUNDING.release()
    yield


def test_the_tone_is_on_by_default() -> None:
    # Off since 2026-08-07, when a session had the box ticked, the device
    # working, and no tone sounded. On again since 0.4.0 (Ángel, after the
    # bench of 5 Oct 2026): with the eyes closed the tone is the only cue,
    # and a box that has to be remembered gets forgotten.
    assert cue.DEFAULT_ENABLED is True


def test_the_tone_is_short_and_mild() -> None:
    # A startle response ends in a blink, which would land in the last moments
    # of the phase being measured.
    assert 400 <= cue._FREQ_HZ <= 2000
    assert cue._DURATION_MS <= 250


def test_a_beep_on_a_working_system_does_not_raise() -> None:
    cue.beep()


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_a_failing_sound_device_is_swallowed(monkeypatch) -> None:
    import winsound

    def explode(*args, **kwargs) -> None:
        raise RuntimeError("no audio device")

    monkeypatch.setattr(winsound, "PlaySound", explode)
    # Must fall through to the Qt fallback and return quietly either way.
    cue.beep()


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_playsound_is_actually_called_with_a_playable_combination(monkeypatch) -> None:
    """The regression this module shipped with for months.

    ``winsound.PlaySound(data, SND_MEMORY | SND_ASYNC)`` raises
    ``RuntimeError: Cannot play asynchronously from memory`` on every real
    Windows machine — Python's binding refuses the combination outright. Every
    call through :func:`cue.beep` hit that exception and it was swallowed by
    the ``except Exception: pass`` a few lines below, so ``beep()`` "worked"
    (raised nothing, per the test above) while never making a sound. Silence
    reads as a passing test unless something asserts that ``PlaySound`` was
    actually reached and actually accepted its arguments.
    """
    import winsound

    real_playsound = winsound.PlaySound
    calls = []
    reached = threading.Event()

    def record(data, flags):
        calls.append((data, flags))
        reached.set()
        # Call the real function too: if this flag combination is invalid,
        # it raises here exactly as it does outside the test, and the
        # exception must not escape (see the next test).
        return real_playsound(data, flags)

    monkeypatch.setattr(winsound, "PlaySound", record)
    cue.beep()
    # The call happens on a background thread: wait for it, not for the clock.
    assert reached.wait(10), "winsound.PlaySound was never called"
    _data, flags = calls[0]
    assert not (flags & winsound.SND_ASYNC), (
        "SND_MEMORY | SND_ASYNC is rejected by winsound — this must never "
        "be the combination passed to PlaySound"
    )
    assert flags & winsound.SND_MEMORY


def test_play_wav_does_not_block_the_caller() -> None:
    """The whole reason for the background thread: a timer callback on the
    GUI thread must return immediately, not for the ~100 ms a tone lasts."""
    started = time.monotonic()
    cue.play_wav(cue._tone_wav())
    assert time.monotonic() - started < 0.05


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_a_playsound_failure_on_the_thread_does_not_crash(monkeypatch) -> None:
    """The exception now happens on a background thread; it must not take
    the process down, and the caller must not see it either."""
    import winsound

    reached = threading.Event()

    def explode(*args, **kwargs) -> None:
        reached.set()
        raise RuntimeError("no audio device")

    monkeypatch.setattr(winsound, "PlaySound", explode, raising=False)
    cue.play_wav(cue._tone_wav())
    # The thread got as far as the failure; nothing crashed on the way back.
    assert reached.wait(10), "the background thread never reached PlaySound"


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_a_playsound_failure_is_logged_not_just_swallowed(monkeypatch, caplog) -> None:
    """A tone that failed for an ordinary reason must still leave a trace.

    Before this, ``except Exception: pass`` meant a genuinely failing device
    was indistinguishable from a tone that was never attempted - which is
    exactly the question after a session where the box was ticked, the
    device was confirmed working moments earlier, and nothing sounded all
    the same. Swallowing silently and swallowing *loudly* both keep the
    "never raises" guarantee; only one of them leaves anything to debug from.
    """
    import winsound

    def explode(*args, **kwargs) -> None:
        raise RuntimeError("no audio device")

    monkeypatch.setattr(winsound, "PlaySound", explode)
    with caplog.at_level("WARNING", logger="emgteach.cue"):
        cue._play_sync_on_thread(cue._tone_wav())  # direct call: no thread hop to wait for
    assert "PlaySound failed" in caplog.text
    assert "no audio device" in caplog.text  # the original exception, not just that one happened


def test_the_tone_is_a_playable_wav() -> None:
    import wave

    data = cue._tone_wav()
    assert data[:4] == b"RIFF"
    with wave.open(io.BytesIO(data), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == cue._RATE_HZ
        frames = handle.getnframes()
    # The note, after the silence that wakes a sleeping sound card.
    assert abs(frames / cue._RATE_HZ * 1000 - (cue._WAKE_MS + cue._DURATION_MS)) < 5


def test_the_tone_is_built_once_and_kept_alive() -> None:
    # PlaySound reads the buffer while it plays, asynchronously, so the bytes
    # have to outlive the call.
    first = cue._tone_wav()
    assert cue._tone_wav() is first
    assert cue._WAV["phase"] is first


class TestEndMotif:
    """The end of a session has to sound different from a phase change.

    The Berger session finishes on a phase recorded with the eyes closed, so
    the subject has no way to learn it is over except by hearing it — and
    hearing the phase tone would say "next", not "finished".
    """

    def test_it_is_a_different_sound(self) -> None:
        assert cue._tone_wav("end") != cue._tone_wav("phase")

    def test_it_is_longer_than_a_phase_tone(self) -> None:
        # Two notes read as an ending where one reads as "next".
        assert len(cue._tone_wav("end")) > len(cue._tone_wav("phase"))

    def test_it_falls_rather_than_rises(self) -> None:
        # Rising reads as "carry on"; falling reads as closing.
        pitched = [f for f, _ in cue._END_NOTES if f > 0]
        assert len(pitched) >= 2
        assert pitched[-1] < pitched[0]

    def test_it_is_a_playable_wav(self) -> None:
        import wave

        with wave.open(io.BytesIO(cue._tone_wav("end")), "rb") as handle:
            assert handle.getframerate() == cue._RATE_HZ
            assert handle.getnframes() > 0

    def test_it_is_cached_too(self) -> None:
        first = cue._tone_wav("end")
        assert cue._tone_wav("end") is first

    def test_beep_end_does_not_raise(self) -> None:
        cue.beep_end()


class TestAbortMotif:
    """"Open your eyes, this is over" — the one thing the other cues cannot say.

    Phase, level and end all mean the session is proceeding. When the app
    abandons a session it does so precisely because something went wrong with
    the electrodes, which is exactly when the subject is sitting with their
    eyes shut waiting for a cue that will now never arrive.
    """

    def test_it_is_lower_than_every_other_cue(self) -> None:
        abort = [f for f, _ in cue._ABORT_NOTES if f > 0]
        others = [f for f, _ in cue._END_NOTES if f > 0] + [cue._FREQ_HZ]
        assert max(abort) < min(others)

    def test_it_is_sustained_not_a_blip(self) -> None:
        # It must not be mistakable for a phase change by someone half-asleep
        # in a dim room.
        assert sum(ms for _, ms in cue._ABORT_NOTES) > 4 * cue._DURATION_MS

    def test_it_is_a_distinct_sound(self) -> None:
        assert cue._tone_wav("abort") != cue._tone_wav("phase")
        assert cue._tone_wav("abort") != cue._tone_wav("end")

    def test_it_is_a_playable_wav(self) -> None:
        import wave

        with wave.open(io.BytesIO(cue._tone_wav("abort")), "rb") as handle:
            assert handle.getframerate() == cue._RATE_HZ
            assert handle.getnframes() > 0

    def test_beep_abort_does_not_raise(self) -> None:
        cue.beep_abort()

    def test_it_is_cached_like_the_others(self) -> None:
        assert cue._tone_wav("abort") is cue._tone_wav("abort")

    def test_an_unknown_motif_falls_back_rather_than_raising(self) -> None:
        """A wrong sound is a smaller failure than an exception out of a timer
        callback in the middle of a recording."""
        assert cue._tone_wav("no-such-motif") == cue._tone_wav("phase")


def test_the_tone_starts_and_ends_at_silence() -> None:
    # A hard edge clicks, and a click is a worse startle than the tone.
    import wave

    with wave.open(io.BytesIO(cue._tone_wav()), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
    assert struct.unpack("<h", raw[:2])[0] == 0
    assert abs(struct.unpack("<h", raw[-2:])[0]) < 2000


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_a_missing_winsound_is_swallowed(monkeypatch) -> None:
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else None

    def no_winsound(name, *args, **kwargs):
        if name == "winsound":
            raise ImportError("no winsound here")
        return (real_import or __import__)(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", no_winsound)
    cue.beep()


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_tones_do_not_pile_up_threads_when_the_audio_is_stuck(monkeypatch) -> None:
    """The measurement asked for on 30 September 2026 (encargo 3.1).

    In eegteach the whole suite hung with more than a hundred cue threads
    blocked in PlaySound. Fifty tones in a row, with PlaySound replaced by a
    call that blocks for a second as a stuck audio device does, and the
    threads alive counted half a second later: one thread per tone, all of
    them waiting, is what the application would pile up in a lab whose audio
    stops answering.
    """
    import winsound

    release = threading.Event()

    def stuck(*_args, **_kwargs) -> None:
        release.wait(1.0)

    monkeypatch.setattr(winsound, "PlaySound", stuck)
    before = threading.active_count()
    try:
        for _ in range(50):
            cue.play_wav(cue._tone_wav())
        time.sleep(0.5)
        piled = threading.active_count() - before
    finally:
        release.set()
    assert piled <= 1, f"{piled} cue threads alive after 50 tones"


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_the_next_tone_sounds_once_the_last_has_ended(monkeypatch) -> None:
    """Dropping a tone while another sounds must not silence the ones after."""
    import winsound

    played: list[bytes] = []
    done = threading.Event()

    def quick(data, _flags) -> None:
        played.append(data)
        done.set()

    monkeypatch.setattr(winsound, "PlaySound", quick)
    for _ in range(3):
        done.clear()
        cue.play_wav(cue._tone_wav())
        assert done.wait(5)
        assert cue._SOUNDING.acquire(timeout=5)
        cue._SOUNDING.release()
    assert len(played) == 3


@pytest.fixture
def _fresh_lock():
    """The stuck-tone rule changes module state: start and end clean."""
    saved = (cue._SOUNDING, getattr(cue, "_sounding_since", 0.0), getattr(cue, "_stuck", 0))
    cue._SOUNDING = threading.Lock()
    cue._sounding_since, cue._stuck = 0.0, 0
    yield
    cue._SOUNDING, cue._sounding_since, cue._stuck = saved


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_a_stuck_tone_does_not_silence_the_next(monkeypatch, _fresh_lock) -> None:
    """Bench of 5 Oct 2026: in the Berger session the first and last tones
    sounded and the ones in between did not. A tone stuck in PlaySound held
    the lock, and the lock dropped every tone after it."""
    import winsound

    release = threading.Event()
    calls: list[float] = []

    def first_sticks(*_a, **_k) -> None:
        calls.append(time.monotonic())
        if len(calls) == 1:
            release.wait(6.0)

    monkeypatch.setattr(winsound, "PlaySound", first_sticks)
    try:
        cue.play_wav(cue._tone_wav())
        time.sleep(2.3)
        cue.play_wav(cue._tone_wav())
        deadline = time.monotonic() + 3.0
        while len(calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(calls) == 2, "the tone after a stuck one never sounded"
    finally:
        release.set()


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_a_dropped_tone_is_logged(monkeypatch, caplog, _fresh_lock) -> None:
    import winsound

    release = threading.Event()
    monkeypatch.setattr(winsound, "PlaySound", lambda *_a, **_k: release.wait(2.0))
    try:
        with caplog.at_level("WARNING", logger="emgteach.cue"):
            cue.play_wav(cue._tone_wav())
            cue.play_wav(cue._tone_wav())
        assert "Tone dropped" in caplog.text
    finally:
        release.set()


@pytest.mark.parametrize("key", ["phase", "end", "abort"])
def test_every_motif_opens_with_silence_for_a_sleeping_card(key: str) -> None:
    import wave

    with wave.open(io.BytesIO(cue._tone_wav(key)), "rb") as handle:
        rate = handle.getframerate()
        lead = handle.readframes(int(rate * 0.24))
    assert not any(lead), "the motif starts with sound, not silence"


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_each_tone_leaves_a_line_for_the_event_log(monkeypatch, _fresh_lock) -> None:
    """Annex of 6 Oct 2026, point 30: the executable has no console and no
    logging handler, so «Tone dropped» and «PlaySound failed» went nowhere.
    Each phase tone now reports what became of it, for the event log."""
    import winsound

    reports: list[tuple[str, float]] = []
    release = threading.Event()
    monkeypatch.setattr(winsound, "PlaySound", lambda *_a, **_k: release.wait(1.0))
    cue.set_tone_report(lambda kind, seconds: reports.append((kind, seconds)))
    try:
        cue.beep()
        cue.beep()                                   # while the first sounds
        release.set()
        deadline = time.monotonic() + 3.0
        while len(reports) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        kinds = sorted(k for k, _s in reports)
        assert kinds == ["dropped", "sounded"], reports
    finally:
        cue.set_tone_report(None)


@pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
def test_a_failed_tone_is_reported_too(monkeypatch, _fresh_lock) -> None:
    import winsound

    reports: list[tuple[str, float]] = []

    def explode(*_a, **_k) -> None:
        raise RuntimeError("no audio device")

    monkeypatch.setattr(winsound, "PlaySound", explode)
    cue.set_tone_report(lambda kind, seconds: reports.append((kind, seconds)))
    try:
        cue.beep()
        deadline = time.monotonic() + 3.0
        while not reports and time.monotonic() < deadline:
            time.sleep(0.01)
        assert [k for k, _s in reports] == ["failed"]
    finally:
        cue.set_tone_report(None)
