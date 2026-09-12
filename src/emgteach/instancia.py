"""One copy of the application at a time.

On a slow classroom computer the application takes several seconds to show
anything, and the normal response to a program that gives no sign of life is
to click it again. Every click started another copy; they fought over the
machine, only one of them ended up working, and the others had to be found
and closed by hand — with the first minutes of the practical gone.

So the first copy listens on a local channel named after the user, and any
later one checks that channel before doing anything else. If somebody
answers, the later copy asks the first to come to the front and exits,
without building a window or loading the analysis stack. The check runs
before the heavy imports on purpose: a copy that is going to leave should not
first spend the machine the first copy is trying to start on.

The sign of life itself — something on screen from the first second — cannot
come from here. In the one-file Windows build the executable spends its first
seconds unpacking itself, before Python runs at all; that is covered by the
bootloader's splash screen (``packaging/emgteach.spec``), which this module
closes once the application's own splash is up.
"""

from __future__ import annotations

import getpass
import re
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

#: How long a later copy waits for the first one to answer. The first copy is
#: already inside its event loop and answers in milliseconds; the wait is only
#: paid in full when nobody is there, which is the normal start.
ESPERA_MS = 400


def nombre_del_servidor() -> str:
    """The channel's name: one per user, so two logged-in users get two apps."""
    try:
        usuario = getpass.getuser()
    except Exception:  # pragma: no cover — no user name in the environment
        usuario = ""
    limpio = re.sub(r"[^0-9A-Za-z_.-]+", "_", usuario).strip("_") or "usuario"
    return f"emgteach-{limpio}"


def avisar_a_la_otra(nombre: str | None = None, espera_ms: int = ESPERA_MS) -> bool:
    """Ask a running copy to come to the front. ``True`` if one answered."""
    sock = QLocalSocket()
    sock.connectToServer(nombre or nombre_del_servidor())
    if not sock.waitForConnected(espera_ms):
        return False
    # Connecting is the request; the byte only makes it visible on the wire.
    sock.write(b"1")
    sock.flush()
    sock.waitForBytesWritten(espera_ms)
    sock.disconnectFromServer()
    return True


class GuardiaDeInstancia(QObject):
    """Held by the running copy: listens, and says when another one knocked.

    Signals
    -------
    activar
        Another copy was started and has left; the window should come to the
        front so whoever clicked sees that it worked.
    """

    activar = Signal()

    def __init__(self, nombre: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._nombre = nombre or nombre_del_servidor()
        self._servidor = QLocalServer(self)
        self._servidor.newConnection.connect(self._al_llamar)

    @property
    def nombre(self) -> str:
        return self._nombre

    def escuchar(self) -> bool:
        """Start listening. ``False`` only if the channel cannot be opened."""
        if self._servidor.listen(self._nombre):
            return True
        # A channel left behind by a copy that crashed: on Unix the socket file
        # outlives its process (Windows pipes do not). Nobody answered the
        # knock before we got here, so it is stale — remove it, try once more.
        QLocalServer.removeServer(self._nombre)
        return self._servidor.listen(self._nombre)

    def cerrar(self) -> None:
        self._servidor.close()

    def _al_llamar(self) -> None:
        while self._servidor.hasPendingConnections():
            sock = self._servidor.nextPendingConnection()
            sock.disconnected.connect(sock.deleteLater)
        self.activar.emit()


def cerrar_splash_de_arranque() -> None:
    """Close the bootloader's splash, if this is the frozen build that has one."""
    try:
        import pyi_splash  # type: ignore[import-not-found]  # frozen build only
    except ImportError:
        return
    try:
        pyi_splash.close()
    except Exception:  # pragma: no cover — already closed, or no display
        pass


def lanzar(nombre: str | None = None) -> int | None:
    """Start the application, unless a copy is already running.

    Returns ``0`` when another copy answered and this one left without a
    window; otherwise runs the application and returns what it returns.
    """
    from emgteach.crash import install_crash_log

    install_crash_log()
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    if avisar_a_la_otra(nombre):
        cerrar_splash_de_arranque()
        return 0
    guardia = GuardiaDeInstancia(nombre)
    guardia.escuchar()
    from emgteach.gui.app import main

    return main(app=app, guardia=guardia)
