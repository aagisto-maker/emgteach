"""The classroom broadcast, as a piece of the acquisition tab (step 1 of
docs/PLAN-partir-AcquisitionTab.md).

Students follow the session on their phone browser: the operator's
computer serves a read-only page over the local network and this box turns
the broadcast on and off, offers the follower link (to copy, or as a QR
code), says how many are following, and warns when nobody has joined a
while after it started. What the followers see — the live envelope, the
load, the calibration's phases, the markers — the tab sends through the
methods below; the box knows nothing of the tab.

Communication, the rule of the plan: the tab calls :meth:`config`,
:meth:`status`, :meth:`live`, :meth:`calib` and :meth:`marker`, and
listens to :attr:`logged` and :attr:`warned`, which carry the lines the
event log and the warning box get. The :class:`BroadcastServer` itself is
the application's — the Analysis tab pushes its report through the same
one — so it is given to the box, not made by it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from emgteach.broadcast import BroadcastServer, hay_red_utilizable
from emgteach.difusion import PORTS_FILE
from emgteach.i18n import tr

__all__ = [
    "ESPERA_SEGUIDORES_MS",
    "ClassroomBox",
    "aviso_puerto_ocupado",
    "aviso_sin_red",
    "aviso_sin_seguidores",
]

#: How long the classroom broadcast waits for its first follower before saying
#: that the phones may not be reaching this computer. Long enough to scan a
#: QR code and open a page; short enough to still be useful in the session.
ESPERA_SEGUIDORES_MS = 90_000


def aviso_sin_red() -> str:
    """Said when the broadcast starts on a computer with no network at all."""
    return tr(
        "This computer is not connected to any network, so the phones cannot "
        "reach it. Connect it to the network the phones use, or share this "
        "computer's own connection (Windows: Settings › Network & internet › "
        "Mobile hotspot) and connect the phones to that."
    )


def aviso_sin_seguidores() -> str:
    """Said once when nobody has joined a while after the broadcast started.

    The two usual causes in a university cannot be seen or fixed from here:
    the wired computers and the Wi-Fi on separate networks that do not route
    to each other, or a Wi-Fi that keeps its clients from seeing one another.
    A third can be fixed at the laboratory: a network that blocks the
    broadcast's ports, which are changed in difusion.txt. What can be said
    besides is the one arrangement that always works.
    """
    return tr(
        "Nobody has joined the broadcast yet. If the phones do not load the "
        "page, this computer and the Wi-Fi may be on separate networks, or the "
        "Wi-Fi may keep devices from seeing each other — both are common in "
        "universities, and neither can be fixed from here. What always works: "
        "share this computer's own connection (Windows: Settings › Network & "
        "internet › Mobile hotspot) and connect the phones to that."
    ) + " " + tr(
        "The network may also block the broadcast's ports; they are changed "
        "in {file}, next to the application."
    ).format(file=PORTS_FILE)


def aviso_puerto_ocupado(puerto: int) -> str:
    """Said when the broadcast cannot open one of its ports."""
    return tr(
        "Could not start classroom mode: port {port} is in use by another "
        "program. Other ports can be written in {file}, next to the application."
    ).format(port=puerto, file=PORTS_FILE)


class ClassroomBox(QWidget):
    """The broadcast's controls on one line: the box that turns it on, «Copy
    link», «QR» and the label with the follower link and the count.

    Signals
    -------
    started()
        The broadcast has just started and the followers need to be told
        what is being recorded — channels, names, recording state —, which
        only the tab knows: it answers with :meth:`config`.
    logged(str)
        A line for the event log: the broadcast turned on or off, the link
        copied.
    warned(str)
        A warning for the operator: no network, nobody following, a port
        in use, no QR library.
    """

    started = Signal()
    logged = Signal(str)
    warned = Signal(str)

    def __init__(self, broadcast: BroadcastServer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._broadcast = broadcast
        self._timer_sin_seguidores: QTimer | None = None
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._chk = QCheckBox(tr("Broadcast to phones (in the laboratory)"))
        self._chk.setToolTip(
            tr(
                "Serve a read-only live view over the local network so students "
                "can follow on their phone/tablet browser (no install). One "
                "device drives the BITalino; the others just watch."
            )
        )
        self._chk.toggled.connect(self._on_toggle)
        row.addWidget(self._chk)
        self._btn_copy = QPushButton(tr("Copy link"))
        self._btn_copy.setToolTip(
            tr(
                "Copy the follower link to the clipboard, e.g. to email it to "
                "the students. The link only works for this session: stopping "
                "the broadcast invalidates it."
            )
        )
        self._btn_copy.setVisible(False)
        self._btn_copy.clicked.connect(self._copy_url)
        row.addWidget(self._btn_copy)
        self._btn_qr = QPushButton(tr("QR"))
        self._btn_qr.setToolTip(
            tr("Show a QR code students can scan to open the follower page.")
        )
        self._btn_qr.clicked.connect(self._show_qr)
        self._btn_qr.setEnabled(False)
        row.addWidget(self._btn_qr)
        self._lbl = QLabel("")
        self._lbl.setStyleSheet("font-size: 11px; color: #1F4E79; font-weight: bold;")
        self._lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self._lbl, stretch=1)
        self._broadcast.clients_changed.connect(self._on_clients)

    # -- what the tab asks -----------------------------------------------------

    def is_running(self) -> bool:
        """Whether followers can be watching right now."""
        return self._broadcast.is_running()

    def config(self, n_channels: int, labels: list[str], recording: bool) -> None:
        """Tell the followers what is being recorded: how many channels,
        their names, and whether a recording is on."""
        self._broadcast.broadcast({
            "t": "config", "n": n_channels, "labels": labels, "recording": recording,
        })

    def status(self, recording: bool) -> None:
        self._broadcast.broadcast({"t": "status", "recording": recording})

    def live(self, env: list, n_channels: int, load: dict | None) -> None:
        """Push a downsampled envelope of each channel, and the live % MVC
        load the tab measured (``{"warn", "danger", "ch": [...]}``), to the
        followers. Nothing is sent while the broadcast is off."""
        if not self._broadcast.is_running():
            return
        env_out: list[list[float]] = []
        for c in range(n_channels):
            a = env[c] if c < len(env) else None
            if a is None or not len(a):
                env_out.append([])
                continue
            step = max(1, len(a) // 8)
            env_out.append([round(float(x), 4) for x in a[::step][:8]])
        self._broadcast.broadcast({"t": "data", "env": env_out})
        if load is not None:
            self._broadcast.broadcast({"t": "load", **load})

    def calib(self, active: bool, phase: str = "", title: str = "",
              sub: str = "", count=None, secs=None,
              progress=None, effort=None) -> None:
        """What a guided flow is asking for right now, for the followers'
        panel; ``active=False`` takes the panel down."""
        if not self._broadcast.is_running():
            return
        self._broadcast.broadcast({
            "t": "calib", "active": active, "phase": phase, "title": title,
            "sub": sub, "count": count, "secs": secs,
            "progress": progress, "effort": effort,
        })

    def marker(self, time_s: float, label: str) -> None:
        """A marker just written into the file, for the followers' plots."""
        if self._broadcast.is_running():
            self._broadcast.broadcast(
                {"t": "marker", "time": round(time_s, 1), "label": label}
            )

    # -- the controls -----------------------------------------------------------

    @Slot(bool)
    def _on_toggle(self, checked: bool) -> None:
        if checked:
            if self._broadcast.start():
                url = self._broadcast.follower_url()
                self._lbl.setText(tr("Students open:  {url}").format(url=url))
                self._btn_copy.setVisible(True)
                self.logged.emit(
                    tr("Classroom mode on — students can follow at {url}").format(url=url)
                )
                self._btn_qr.setEnabled(True)
                self.started.emit()
                # A panel that stays empty on twenty phones with nothing to say
                # why is the worst thing this can do in front of a class.
                if not hay_red_utilizable():
                    self.warned.emit(aviso_sin_red())
                    self._lbl.setText(
                        tr("No network: the phones cannot reach this computer.")
                    )
                else:
                    self._vigilar_seguidores(True)
            else:
                self._chk.setChecked(False)
                puerto = self._broadcast.failed_port
                self.warned.emit(
                    aviso_puerto_ocupado(puerto) if puerto is not None
                    else tr("Could not start classroom mode (port busy?).")
                )
        else:
            self._vigilar_seguidores(False)
            self._broadcast.stop()
            self._lbl.setText("")
            self._btn_copy.setVisible(False)
            self._btn_qr.setEnabled(False)
            self.logged.emit(
                tr("Classroom mode off — previous follower links are now invalid."))

    def _vigilar_seguidores(self, activo: bool) -> None:
        """Arm or disarm the «nobody has joined yet» warning."""
        reloj = self._timer_sin_seguidores
        if reloj is None:
            reloj = QTimer(self)
            reloj.setSingleShot(True)
            reloj.setInterval(ESPERA_SEGUIDORES_MS)
            reloj.timeout.connect(self._avisar_sin_seguidores)
            self._timer_sin_seguidores = reloj
        if activo:
            reloj.start()
        else:
            reloj.stop()

    @Slot()
    def _avisar_sin_seguidores(self) -> None:
        if self._broadcast.is_running() and self._broadcast.client_count() == 0:
            self.warned.emit(aviso_sin_seguidores())

    @Slot()
    def _copy_url(self) -> None:
        if not self._broadcast.is_running():
            return
        QGuiApplication.clipboard().setText(self._broadcast.follower_url())
        self.logged.emit(tr("Follower link copied to the clipboard."))
        self._btn_copy.setText(tr("Copied ✓"))
        QTimer.singleShot(1500, lambda: self._btn_copy.setText(tr("Copy link")))

    @Slot()
    def _show_qr(self) -> None:
        """Show a scannable QR code of the follower URL in a small dialog."""
        if not self._broadcast.is_running():
            return
        url = self._broadcast.follower_url()
        pix = self._make_qr_pixmap(url)
        if pix is None:
            self.warned.emit(tr("QR code unavailable (the 'segno' library is missing)."))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Scan to follow the session"))
        lay = QVBoxLayout(dlg)
        img = QLabel()
        img.setPixmap(pix)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(img)
        cap = QLabel(url)
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cap.setStyleSheet("font-weight: bold; color: #1F4E79;")
        lay.addWidget(cap)
        hint = QLabel(tr("Point the phone camera at the code (same Wi-Fi network)."))
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        dlg.exec()

    @staticmethod
    def _make_qr_pixmap(url: str, scale: int = 8) -> QPixmap | None:
        """Render *url* as a QR-code QPixmap, or None if segno is unavailable."""
        try:
            import io

            import segno
        except ImportError:
            return None
        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="png", scale=scale, border=2)
        pix = QPixmap()
        pix.loadFromData(buf.getvalue())  # the format is read from the data
        return pix

    @Slot(int)
    def _on_clients(self, n: int) -> None:
        if n > 0:
            self._vigilar_seguidores(False)
        if self._broadcast.is_running():
            url = self._broadcast.follower_url()
            self._lbl.setText(
                tr("Students open:  {url}   ·   {n} following").format(url=url, n=n)
            )
