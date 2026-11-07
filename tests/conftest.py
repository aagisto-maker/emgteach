"""Shared pytest fixtures and Qt setup.

The Qt offscreen platform plugin is selected at import time so the
GUI-touching tests (workers and, eventually, tabs) can run on a
headless CI runner without a display server.
"""

from __future__ import annotations

import faulthandler
import gc
import os
import sys
import threading
import time

import pytest

# Must be set before any PySide6 import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The offscreen platform ships no fonts of its own. On Windows it then draws
# every glyph as a box, and a box is wider than a letter: a window measured
# under it had a minimum width of 1911 px against 858 px with real fonts, so
# any test that asks how wide something is was measuring the missing fonts.
# Pointed at the system's, the suite sees what the student sees. Linux and
# macOS find theirs through fontconfig and need nothing.
if os.name == "nt" and os.path.isdir(r"C:\Windows\Fonts"):
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")


def pytest_configure(config: pytest.Config) -> None:
    """Make Qt's fatal messages visible, because otherwise nothing is.

    Twice on 19 September the ``windows-latest / Python 3.10`` job ended with
    ``exit code 1`` and **no** ``FAILED`` line: every test walked, the log
    stopping in the middle of the last file and not one word about why. Two
    things conspired to make that silence.

    The first is Qt. When something goes fatally wrong -- a ``QThread``
    destroyed while it is still running is the one we are chasing -- Qt calls
    the installed message handler and then aborts through ``__fastfail``.
    That is not a signal, so ``faulthandler`` never sees it; the
    ``faulthandler_timeout`` in ``ci.yml`` catches a *hang* and can say
    nothing about an abort. And the exit status, ``0xC0000409``, comes out of
    the PowerShell the runner wraps the step in as plain ``1``, which is
    indistinguishable from a test having failed.

    The second is pytest's own capture. It redirects file descriptors 1 and 2
    into temporary files and only shows what it caught when a test fails; a
    process that aborts never gets that far, so Qt's message died in the
    capture. Hence the suspend below: the handler writes to the terminal the
    runner is actually reading, and flushes before Qt pulls the floor away.

    What comes out is the sentence that was missing -- which thread, by name,
    and a stack for every thread alive at that instant, so the next time this
    happens the log says who was still running instead of nothing at all.
    """
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:  # pragma: no cover -- Qt-free environment, nothing to guard
        return

    capman = config.pluginmanager.getplugin("capturemanager")
    etiquetas = {QtMsgType.QtFatalMsg: "FATAL", QtMsgType.QtCriticalMsg: "CRITICAL"}

    def handler(mode, _context, message: str) -> None:
        etiqueta = etiquetas.get(mode)
        if etiqueta is None:          # debug, info, warning: Qt's own business
            return
        mortal = mode == QtMsgType.QtFatalMsg

        # Nothing below may raise. This runs inside a Qt callback, and an
        # instrument able to break the run it is watching is worse than none;
        # the suspension is tried separately so that losing it still leaves
        # the message, which is the part worth having.
        suspendida = False
        try:
            if capman is not None and capman.is_globally_capturing():
                capman.suspend_global_capture(in_=False)
                suspendida = True
        except Exception:  # pragma: no cover -- older pytest, or no capture
            pass

        try:
            sys.stdout.flush()
            sys.stderr.write(f"\n[Qt {etiqueta}] {message}\n")
            if mortal:
                # Qt aborts the moment this returns, so the stacks have to be
                # taken here: afterwards there is no process left to ask.
                faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
            sys.stderr.flush()
        except Exception:  # pragma: no cover -- never break the run
            pass
        finally:
            if suspendida and not mortal:
                try:
                    capman.resume_global_capture()
                except Exception:  # pragma: no cover
                    pass

    qInstallMessageHandler(handler)


@pytest.fixture(autouse=True)
def qsettings_of_its_own(tmp_path_factory):
    """Give each test its own settings file, in a directory nothing else uses.

    This is what made one random GUI test fail per full run — a different one
    each time, every one of them passing alone.

    The tests address their settings as ``QSettings("emgteach-test", <app>)``,
    which on Windows is the *registry*, and they share that one store between
    them: a fixture clears it on the way in and again on the way out, so a
    test's setup is racing the previous test's teardown over the same key.
    ``clear()`` on the native backend deletes the registry key, and Windows
    defers deleting a key while a handle to it is open — which, with a window
    and its three tabs holding the same settings, it always is. The delete
    lands late and takes the writes that followed it, and the store reads back
    **completely empty**: measured, 19 of 25 window-build cycles lost the value
    written a line earlier, against 0 of 25 through a file.

    A window then asks ``_mode()`` which practical it is, gets nothing, and
    falls back to ``single``; a tour built for ``single`` points at controls a
    window laid out for ``pair`` is not showing. Nothing is wrong with the
    window — its combo still holds the right index. What is wrong is the
    answer it is given about itself.

    Two changes, because the file backend alone only makes the sharing
    *reliable*, not harmless: an INI file instead of the registry, and a fresh
    directory per test instead of one store for the suite. With a path of its
    own, no test can see what another wrote, the ``clear()`` calls scattered
    through the fixtures become the no-ops they always meant to be, and a
    window outliving its test writes to a file nobody will read again. It also
    stops the suite writing into the developer's real registry, which it had
    no business doing.
    """
    try:
        from PySide6.QtCore import QSettings
    except Exception:  # pragma: no cover — Qt-free environment, nothing to do
        return
    ini = QSettings.Format.IniFormat
    QSettings.setDefaultFormat(ini)
    QSettings.setPath(
        ini,
        QSettings.Scope.UserScope,
        str(tmp_path_factory.mktemp("qsettings")),
    )


#: Set to ``1`` to make a test that leaves a window open fail (CI does).
STRICT_WINDOWS_ENV = "EMGTEACH_STRICT_WINDOWS"

#: (test, windows) for every test that left one open, said at the end.
_WINDOWS_LEFT: list[tuple[str, list[str]]] = []


def _shown_windows(app) -> dict[int, object]:
    """The visible windows on screen and the modal one, by address.

    Asked of the platform windows (``QWindow``), not of the widgets. A widget
    gets a ``QWindow`` only once shown, so this touches what is on screen and
    nothing else; ``QApplication.topLevelWidgets()`` hands Python every
    top-level widget Qt still holds, the hidden ones, the popups and tooltips
    included, and asked twice per test across the suite it crashed once in
    CI with a segmentation fault inside that call (Python 3.11 on Ubuntu,
    5 November 2026). The widget behind a window is looked up only for what
    is left over (:func:`_widget_of`).

    A window whose Python wrapper says its C++ object is already deleted is
    passed over: Qt can hand back an address it has reused while shiboken
    still holds the wrapper of what used to live there, and in CI one such
    window, met while a test was being set up, failed it (Python 3.10 on
    Ubuntu, 5 November 2026). What cannot be read is not on screen for this
    purpose; the next look sees it as what it now is.
    """
    import shiboken6
    from PySide6.QtGui import QGuiApplication

    shown = {}
    modal = QGuiApplication.modalWindow()
    for window in [*QGuiApplication.topLevelWindows(), *([modal] if modal else [])]:
        try:
            if window is modal or window.isVisible():
                shown[shiboken6.getCppPointer(window)[0]] = window
        except RuntimeError:        # a wrapper left over from a deleted object
            continue
    return shown


def _widget_of(window):
    """The widget a platform window belongs to; ``None`` for one of its own."""
    from PySide6.QtWidgets import QWidget

    try:
        return QWidget.find(window.winId())
    except RuntimeError:            # deleted since it was listed
        return None


def _describe(widget) -> str:
    title = widget.windowTitle()
    return f"{type(widget).__name__} «{title}»" if title else type(widget).__name__


def _close_for_good(widget) -> None:
    """Close a window as the application would, and destroy it.

    ``widget`` is a widget, or a bare ``QWindow`` that belongs to none.

    A tab is stopped the way MainWindow.closeEvent stops it — its timers, its
    worker, its broadcast server — before it is closed: hidden, it would go on
    ticking and recording into the tests that follow. A dialog is closed with
    its signals blocked, so no «Retry» or «Close» answer runs the
    application's code on its way out.
    """
    from PySide6.QtWidgets import QDialog, QWidget

    try:
        if isinstance(widget, QDialog):
            widget.blockSignals(True)
        cleanup = getattr(widget, "cleanup", None)
        if callable(cleanup):
            cleanup()
        widget.close()
        if isinstance(widget, QWidget):
            widget.deleteLater()
    except RuntimeError:            # already deleted on the C++ side
        pass


@pytest.fixture(autouse=True)
def no_window_outlives_its_test(request):
    """Close what a test leaves on screen, and say which test left it.

    In the full suite fourteen tests left windows behind — nine acquisition
    tabs and five «The recording cannot be saved» boxes — none closed until
    the process ended. A test after them ran with up to fourteen windows on
    screen; one of them, a widget shown on its own in tests/test_conexion.py,
    took the keyboard focus from the manual-marks tests and failed seven of
    them in the full run only, every one passing alone.

    Only what appeared during this test is touched: a window that was already
    up belongs to someone else. This fixture is autouse, so it is set up
    before the test's own fixtures and torn down after them; what a fixture
    closes itself never reaches it.

    By default a window left open is closed and destroyed, and named at the
    end of the run; the test passes. A window a test forgot is a fault of
    that test, not of the one after it, and failing it would put a red mark
    on whatever runs next in a developer's run for a reason that has nothing
    to do with the code being worked on. With ``EMGTEACH_STRICT_WINDOWS=1``,
    as CI runs, the test that left it fails, so no new one gets in.
    """
    try:
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
    except Exception:  # pragma: no cover — Qt-free environment, nothing to do
        yield
        return
    app = QApplication.instance()
    before = set(_shown_windows(app)) if app is not None else set()
    yield
    app = QApplication.instance()
    if app is None:
        return
    app.processEvents()
    left = [w for address, w in _shown_windows(app).items() if address not in before]
    if not left:
        return
    left = [_widget_of(window) or window for window in left]
    names = [_describe(w) for w in left]
    for widget in left:
        _close_for_good(widget)
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    _WINDOWS_LEFT.append((request.node.nodeid, names))
    if os.environ.get(STRICT_WINDOWS_ENV) == "1":
        pytest.fail(
            f"the test left {len(names)} window(s) open: {', '.join(names)}",
            pytrace=False,
        )


@pytest.fixture
def message_boxes_not_shown(monkeypatch):
    """The acquisition tab's message boxes, built for real but never put on screen.

    A box like «The recording cannot be saved» is shown non-modal and left for
    the operator to close; in a test nobody closes it, and it stayed on screen
    to the end of the suite. Here the tab builds the same box — its title,
    text, buttons and modality are the real ones a test can check — and
    showing or opening it only records that it was shown. Returns the boxes
    shown, in order.
    """
    from PySide6.QtWidgets import QMessageBox

    from emgteach.gui.tabs import acquisition as acq_mod

    shown: list[QMessageBox] = []

    class _BoxNotShown(QMessageBox):
        def show(self) -> None:
            shown.append(self)

        def open(self) -> None:
            shown.append(self)

    monkeypatch.setattr(acq_mod, "QMessageBox", _BoxNotShown)
    return shown


@pytest.fixture
def marks_as_written(monkeypatch):
    """Every annotation the acquisition worker is asked to write, as it is asked.

    Each entry is ``(label, clock_s, file_s)``: the monotonic clock at the
    moment the application wrote it, and where it lands in the file (the
    samples the worker has received). A guided session decides its phases by
    the clock and the countdown by its ticks, so a phase's length is the
    application's in ``clock_s``; in ``file_s`` it also carries the worker's
    delay, which on a loaded runner is what moved the marks of a sound
    session past a tight margin.
    """
    import time

    from emgteach.workers import acquisition as wmod

    written: list[tuple[str, float, float]] = []
    original = wmod.AcquisitionWorker.add_marker

    def add_marker(self, label: str) -> None:
        written.append((label, time.monotonic(), self._n_samples_total / self._device.fs))
        original(self, label)

    monkeypatch.setattr(wmod.AcquisitionWorker, "add_marker", add_marker)
    return written


@pytest.fixture
def session_ticks(monkeypatch):
    """Every tick of every guided session's runner, as ``(clock_s, phase_key)``.

    The runner reads the clock at each tick and reports the phase it is in;
    a phase never reports a tick past its own end — that tick crosses into
    the next one instead. So a phase that ran longer than its script says
    leaves ticks after its planned end, while a machine that froze the
    interface for a while only leaves fewer ticks: the first after the
    freeze already crosses. A margin on when the next mark was written
    cannot tell the two apart; the ticks can.
    """
    import time

    from emgteach.gui.session_runner import SessionRunner

    ticks: list[tuple[float, str]] = []
    original = SessionRunner.__init__

    def __init__(self, *args, **kwargs) -> None:
        original(self, *args, **kwargs)
        self.tick.connect(lambda fase, _restante, _hecho: ticks.append(
            (time.monotonic(), fase.key)))

    monkeypatch.setattr(SessionRunner, "__init__", __init__)
    return ticks


# ── What the interface thread waits for, measured (Ángel, 7 November 2026) ──
#
# On CI on Windows two guided sessions failed by time: a rest of 0.4 s that
# ended 2.31 s after the early end (5 November) and two gradation steps whose
# level came late (7 November). The event log is written with fsync on the
# interface thread, and a stalled interface thread delays every cue. Nothing
# here changes the application: every fsync made on the main thread is timed,
# and so is every call a test makes to processEvents — one that takes longer
# than _PARON_S is the interface thread busy, in the application's slots,
# for that long, with the fsyncs it did in the meantime. The summary at the
# end of the run lists them by test.

#: A processEvents that takes longer than this is a stall of the interface.
_PARON_S = 0.2
#: (test, seconds) of each fsync made on the main thread.
_FSYNC: list[tuple[str, float]] = []
#: (test, seconds, fsyncs inside, their seconds) of each stall.
_PARONES: list[tuple[str, float, int, float]] = []


@pytest.fixture(autouse=True)
def mide_la_interfaz(request, monkeypatch):
    """Time the fsyncs of the main thread and the stalls inside processEvents."""
    nombre = request.node.nodeid
    principal = threading.main_thread()
    original = os.fsync
    dentro: list[float] = []               # the fsyncs of the current processEvents

    def fsync(fd):
        t0 = time.perf_counter()
        try:
            return original(fd)
        finally:
            if threading.current_thread() is principal:
                dt = time.perf_counter() - t0
                _FSYNC.append((nombre, dt))
                dentro.append(dt)

    monkeypatch.setattr(os, "fsync", fsync)
    if "PySide6.QtCore" in sys.modules or "qapp" in request.fixturenames:
        from PySide6.QtCore import QCoreApplication

        procesar = QCoreApplication.processEvents

        def processEvents(*args, **kwargs):
            dentro.clear()
            t0 = time.perf_counter()
            try:
                return procesar(*args, **kwargs)
            finally:
                dt = time.perf_counter() - t0
                if dt > _PARON_S:
                    _PARONES.append((nombre, dt, len(dentro), sum(dentro)))

        monkeypatch.setattr(QCoreApplication, "processEvents", staticmethod(processEvents))
    yield


def _percentil(valores: list[float], p: float) -> float:
    orden = sorted(valores)
    return orden[min(len(orden) - 1, int(p * len(orden)))] if orden else 0.0


def pytest_terminal_summary(terminalreporter) -> None:
    """Name the tests that left windows open, closed for them by the fixture;
    and what the interface thread waited for (mide_la_interfaz)."""
    if _FSYNC or _PARONES:
        terminalreporter.section("interface thread: fsync and stalls")
        tiempos = [dt for _t, dt in _FSYNC]
        terminalreporter.write_line(
            f"fsync on the main thread: {len(tiempos)} calls, "
            f"total {sum(tiempos):.3f} s, median {_percentil(tiempos, 0.5) * 1000:.1f} ms, "
            f"p95 {_percentil(tiempos, 0.95) * 1000:.1f} ms, "
            f"max {max(tiempos, default=0.0) * 1000:.1f} ms")
        for test, dt in sorted(_FSYNC, key=lambda x: -x[1])[:10]:
            terminalreporter.write_line(f"  fsync {dt * 1000:8.1f} ms  {test}")
        terminalreporter.write_line(
            f"stalls over {_PARON_S * 1000:.0f} ms inside processEvents: {len(_PARONES)}")
        for test, dt, n, en_fsync in sorted(_PARONES, key=lambda x: -x[1])[:25]:
            terminalreporter.write_line(
                f"  stall {dt * 1000:8.1f} ms, {n} fsync ({en_fsync * 1000:.1f} ms)  {test}")
    if not _WINDOWS_LEFT:
        return
    terminalreporter.section("windows left open (closed by no_window_outlives_its_test)")
    for test, names in _WINDOWS_LEFT:
        terminalreporter.write_line(f"{test}: {', '.join(names)}")


@pytest.fixture(scope="session")
def qapp():
    """Session-wide QApplication shared by the GUI and worker tests.

    A full ``QApplication`` (not just ``QCoreApplication``) so widget tests
    can create real widgets; it doubles as the event loop for the QThread
    worker tests. PySide6 is imported lazily so the Qt-free smoke tests still
    run on machines without the Qt platform libraries.
    """
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # pragma: no cover — headless without Qt
        pytest.skip(f"PySide6/Qt unavailable: {exc}")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(qapp):
    """A shown MainWindow on throwaway settings, closed afterwards.

    Shown rather than merely constructed because the mode and tour tests ask
    what is visible, and Qt only gives real geometry to a window on screen
    (offscreen still counts). The saved port stands in for a machine that has
    been set up already, so the first-run exception does not fire.
    """
    from PySide6.QtCore import QSettings

    from emgteach.gui.app import MainWindow

    settings = QSettings("emgteach-test", "gui-window")
    settings.clear()
    settings.setValue("adquisicion/port", "COM5")
    win = MainWindow(settings)
    win.resize(1400, 900)
    win.show()
    qapp.processEvents()
    try:
        yield win
    finally:
        settings.clear()
        qapp.processEvents()   # flush deferred canvas draws before teardown
        win.close()
        # Destroy this window deterministically before the next test builds
        # one. Left to the garbage collector, the C++ side of a discarded
        # window gets freed at an arbitrary moment — including part-way
        # through the construction of its successor, which crashes inside
        # pyqtgraph with an access violation on Windows.
        win.deleteLater()
        qapp.processEvents()
        qapp.processEvents()
        gc.collect()
