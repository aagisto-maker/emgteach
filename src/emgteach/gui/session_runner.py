"""The clock of a guided session: which phase it is, and when it changes.

A runner knows the script (:class:`emgteach.sessions.SessionScript`) and the
time, and nothing else: not the acquisition tab, not the panel over the plots,
not the phones. It says what happens — a mark to write, a phase that starts,
the seconds left, the end — and whoever runs it decides how that looks and
where it goes. The tab's other guided flows (the calibration, the pair's task,
the force-velocity loads) are state machines written inside the tab; this one
is kept out of it on purpose, so the tab only connects signals
(docs/PLAN-sesiones-contraccion-simple.md, §6).

**Time is measured, not counted.** Each tick reads a monotonic clock and moves
on to whatever phase that instant falls in, so a tick that comes late — a busy
interface thread — shortens nothing and skips no mark: every phase crossed
writes its marks in order. The marks themselves are stamped by the acquisition
worker with the sample count when they arrive, so they sit where the signal
was when the phase changed, within a tick.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from emgteach.sessions import SessionPhase, SessionScript, end_marker

__all__ = ["TICK_MS", "SessionRunner"]

#: How often the runner looks at the clock, in ms. The calibration's tick.
TICK_MS = 100


class SessionRunner(QObject):
    """Runs a :class:`SessionScript` against the clock.

    Signals
    -------
    marker(str)
        A mark to write into the recording: the session's header on
        :meth:`start`, each phase's ``opens`` and ``closes``, and the end.
    phase_started(object, int)
        A phase began: the :class:`SessionPhase` and its 0-based index.
    tick(object, float, float)
        The running phase, the seconds left in it, and how much of it has
        gone (0..1). Every tick, including the first.
    finished(bool)
        The session is over: ``True`` when it ran to its end, ``False`` when
        it was stopped.
    """

    marker = Signal(str)
    phase_started = Signal(object, int)
    tick = Signal(object, float, float)
    finished = Signal(bool)

    def __init__(
        self,
        script: SessionScript,
        parent: QObject | None = None,
        *,
        tick_ms: int = TICK_MS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self._script = script
        self._phases = script.timed()
        self._clock = clock
        self._t0 = 0.0
        self._index = -1
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(int(tick_ms))
        self._timer.timeout.connect(self._on_tick)

    @property
    def script(self) -> SessionScript:
        return self._script

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_phase(self) -> SessionPhase | None:
        if not self._running or not 0 <= self._index < len(self._phases):
            return None
        return self._phases[self._index]

    @property
    def index(self) -> int:
        return self._index

    def start(self) -> None:
        """Write the header and begin the first phase."""
        if self._running:
            return
        self._running = True
        self._t0 = self._clock()
        self._index = -1
        self.marker.emit(self._script.header)
        self._advance_to(0.0)
        if self._running:
            self._timer.start()

    def cancel(self) -> None:
        """Stop before the end: the session's end mark says «stopped».

        The stretch running at that moment is left open on purpose; the
        reader drops it, as it drops a calibration effort cut short.
        """
        if not self._running:
            return
        self._stop()
        self.marker.emit(end_marker(self._script.family, stopped=True))
        self.finished.emit(False)

    def _stop(self) -> None:
        self._running = False
        self._timer.stop()

    @Slot()
    def _on_tick(self) -> None:
        if not self._running:
            return
        self._advance_to(self._clock() - self._t0)

    def _advance_to(self, elapsed: float) -> None:
        """Cross every phase boundary up to *elapsed*, in order, then report."""
        while self._running:
            if self._index >= 0:
                actual = self._phases[self._index]
                if elapsed < actual.end:
                    break
                if actual.closes:
                    self.marker.emit(actual.closes)
            self._index += 1
            if self._index >= len(self._phases):
                self._stop()
                self.marker.emit(end_marker(self._script.family))
                self.finished.emit(True)
                return
            fase = self._phases[self._index]
            if fase.opens:
                self.marker.emit(fase.opens)
            self.phase_started.emit(fase, self._index)
        if not self._running:               # stopped by whoever heard a signal
            return
        fase = self._phases[self._index]
        hecho = min(1.0, max(0.0, (elapsed - fase.start) / fase.seconds))
        self.tick.emit(fase, max(0.0, fase.end - elapsed), hecho)
