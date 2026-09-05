"""What the program does when something breaks.

Until now it did nothing. An unhandled exception in a Qt slot is printed to a
console that a windowed build does not have, and the application either carries
on in a half-broken state or disappears — so a crash on the bench left the
operator with nothing to report but the fact that it had happened, and left
nobody able to find out why.

So: every unhandled exception is written to a file whose path is fixed and
easy to say out loud, and the operator is told, in a dialogue, that it happened
and where the file is. The file accumulates; a crash that only shows up once
every few sessions is exactly the one worth keeping.

This cannot catch everything. A fault in the C++ half — a QThread destroyed
while still running, a segmentation fault — kills the process before Python
gets a turn. Those are prevented rather than reported, which is why the two
places that start a background worker now refuse to start a second one.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType

__all__ = ["install_crash_log", "log_path", "record_exception"]

#: Message boxes currently on screen. Held only so Python does not collect a
#: modeless dialogue the moment the function that built it returns.
_abiertas: list = []


def log_path() -> Path:
    """Where the log lives: the user's own folder, top level.

    Deliberately not a hidden directory nor an application-data path. It has to
    be somewhere the operator can be told to look over the phone.
    """
    return Path.home() / "emgteach-errores.log"


def record_exception(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> Path | None:
    """Append one traceback to the log. Returns the path, or None if it could
    not be written — in which case the caller still reports the crash."""
    try:
        from emgteach import __version__
    except Exception:  # pragma: no cover — version is not essential
        __version__ = "?"
    try:
        destino = log_path()
        with destino.open("a", encoding="utf-8") as f:
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  emgteach {__version__}"
                    f"  python {sys.version.split()[0]}\n")
            f.write("=" * 70 + "\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
        return destino
    except Exception:  # pragma: no cover — a read-only home, a full disk
        return None


def install_crash_log() -> None:
    """Route unhandled exceptions to the log and to a dialogue.

    Chains to the previous hook so nothing that was already being reported
    stops being reported.
    """
    anterior = sys.excepthook

    def gancho(exc_type, exc, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            anterior(exc_type, exc, tb)
            return
        destino = record_exception(exc_type, exc, tb)
        _avisar(exc, destino)
        anterior(exc_type, exc, tb)

    sys.excepthook = gancho


def _hay_alguien_delante() -> bool:
    """Whether there is a window on screen to put the warning next to.

    The second line of defence. The box is modeless, so it can no longer hang
    anything, but putting one up in a run with no interface at all is noise:
    the log is the report there.
    """
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return False
        return any(w.isVisible() for w in app.topLevelWidgets())
    except Exception:  # pragma: no cover — no Qt at all
        return False


def _avisar(exc: BaseException, destino: Path | None) -> None:
    """Tell the operator, if there is one."""
    if not _hay_alguien_delante():
        return
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMessageBox

        from emgteach.i18n import tr

        texto = tr(
            "The application hit an error it did not expect. What you were "
            "doing may not have been saved.\n\nThe details have been written "
            "to:\n{path}\n\nSend that file on, with a note of what you were "
            "doing at the time."
        ).format(path=destino) if destino else tr(
            "The application hit an error it did not expect, and could not "
            "write the details to a file."
        )
        caja = QMessageBox()
        caja.setIcon(QMessageBox.Icon.Warning)
        caja.setWindowTitle(tr("Unexpected error"))
        caja.setText(texto)
        caja.setDetailedText(f"{type(exc).__name__}: {exc}")
        caja.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        # show(), never exec(). A modal box waits for a click, and the one
        # thing you cannot count on while reporting a crash is that there is
        # somebody to click it: a script driving the application, a test, a
        # build server. Blocking there does not warn anyone, it hangs the
        # program — which is a worse failure than the one being reported.
        _abiertas.append(caja)
        caja.finished.connect(lambda _r, c=caja: _abiertas.remove(c))
        caja.show()
        caja.raise_()
    except Exception:  # pragma: no cover — never crash inside the crash handler
        pass
