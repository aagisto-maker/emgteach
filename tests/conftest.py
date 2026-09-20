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
