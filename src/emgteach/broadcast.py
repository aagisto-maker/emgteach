"""Classroom broadcast server — stream the live monitor to student browsers.

The operator PC owns the single Bluetooth link to the BITalino (Bluetooth
Classic is point-to-point: one device per board). This server re-broadcasts
the already-computed data — envelope, %MVC load, the guided-calibration state
and markers — over the local network, so any number of students can *follow*,
read-only, from their phone/tablet browser: no install and no second
Bluetooth link.

Two Qt-native servers share the GUI event loop (no threads, no extra
dependencies beyond PySide6):

* a tiny HTTP server (:class:`QTcpServer`) that serves the single-page
  dashboard, and
* a WebSocket server (:class:`QWebSocketServer`) that pushes live JSON frames.

Frames are small JSON objects tagged by ``"t"``: ``config``, ``data``
(envelope), ``load``, ``calib`` and ``marker``. The dashboard (``web/
dashboard.html``) renders them. This module is import-safe without a running
event loop; nothing is opened until :meth:`BroadcastServer.start`.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QHostAddress, QNetworkInterface, QTcpServer
from PySide6.QtWebSockets import QWebSocketServer

# Default ports for the classroom broadcast (HTTP page + WebSocket data).
DEFAULT_HTTP_PORT = 8070
DEFAULT_WS_PORT = 8071

_DASHBOARD = Path(__file__).resolve().parent / "web" / "dashboard.html"


def _load_dashboard_html() -> bytes:
    """Read the follower dashboard page (bundled next to this module)."""
    try:
        return _DASHBOARD.read_bytes()
    except OSError:
        return b"<!doctype html><meta charset=utf-8><p>Dashboard not found.</p>"


def lan_ipv4() -> str:
    """Best-guess LAN IPv4 address of this machine (for the follower URL).

    Returns the first non-loopback, non-link-local IPv4 of an up, running
    interface, or ``127.0.0.1`` when none is found.
    """
    best = "127.0.0.1"
    for iface in QNetworkInterface.allInterfaces():
        flags = iface.flags()
        if not (flags & QNetworkInterface.InterfaceFlag.IsUp):
            continue
        if not (flags & QNetworkInterface.InterfaceFlag.IsRunning):
            continue
        if flags & QNetworkInterface.InterfaceFlag.IsLoopBack:
            continue
        for entry in iface.addressEntries():
            s = entry.ip().toString()
            if ":" in s:                       # skip IPv6
                continue
            if s.startswith("127.") or s.startswith("169.254."):
                continue
            return s
    return best


class _HttpServer(QTcpServer):
    """Minimal HTTP/1.1 server that returns the dashboard page for any GET."""

    def __init__(self, html: bytes, parent=None) -> None:
        super().__init__(parent)
        self._html = html
        self.newConnection.connect(self._on_new)

    def _on_new(self) -> None:
        while self.hasPendingConnections():
            sock = self.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._serve(s))
            sock.disconnected.connect(sock.deleteLater)

    def _serve(self, sock) -> None:
        data = bytes(sock.readAll().data())
        # A browser with "HTTPS-First" tries TLS first; a TLS ClientHello starts
        # with the 0x16 (handshake) record byte. We only speak plain HTTP, so
        # reset the connection: the browser then falls back to http:// instead
        # of failing with ERR_SSL_PROTOCOL_ERROR.
        if data[:1] == b"\x16":
            sock.abort()
            return
        body = self._html
        head = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"Cache-Control: no-store\r\n"
            b"Connection: close\r\n\r\n"
        )
        sock.write(head + body)
        sock.flush()
        sock.disconnectFromHost()


class BroadcastServer(QObject):
    """Serves the follower dashboard and pushes live JSON frames to browsers.

    Signals
    -------
    clients_changed : int
        Emitted with the new follower count whenever a browser connects or
        disconnects.
    """

    clients_changed = Signal(int)

    def __init__(
        self,
        http_port: int = DEFAULT_HTTP_PORT,
        ws_port: int = DEFAULT_WS_PORT,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._http_port = int(http_port)
        self._ws_port = int(ws_port)
        self._http: _HttpServer | None = None
        self._ws: QWebSocketServer | None = None
        self._clients: list = []
        self._last_config: dict | None = None

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> bool:
        """Start both servers. Returns ``True`` on success."""
        if self.is_running():
            return True
        html = _load_dashboard_html().replace(
            b"{{WS_PORT}}", str(self._ws_port).encode()
        )
        http = _HttpServer(html, self)
        if not http.listen(QHostAddress(QHostAddress.SpecialAddress.Any), self._http_port):
            http.deleteLater()
            return False
        ws = QWebSocketServer(
            "emgteach", QWebSocketServer.SslMode.NonSecureMode, self
        )
        if not ws.listen(QHostAddress(QHostAddress.SpecialAddress.Any), self._ws_port):
            http.close()
            http.deleteLater()
            ws.deleteLater()
            return False
        ws.newConnection.connect(self._on_ws_connection)
        self._http = http
        self._ws = ws
        return True

    def stop(self) -> None:
        """Close all connections and both servers."""
        for c in list(self._clients):
            try:
                c.disconnected.disconnect()   # avoid _drop firing during teardown
            except (RuntimeError, TypeError):
                pass
            try:
                c.close()
            except RuntimeError:
                pass
        self._clients.clear()
        if self._ws is not None:
            self._ws.close()
            self._ws.deleteLater()
            self._ws = None
        if self._http is not None:
            self._http.close()
            self._http.deleteLater()
            self._http = None
        self._last_config = None
        self.clients_changed.emit(0)

    def is_running(self) -> bool:
        return self._ws is not None

    def client_count(self) -> int:
        return len(self._clients)

    def follower_url(self) -> str:
        """URL students type in their browser to follow the session."""
        return f"http://{lan_ipv4()}:{self._http_port}"

    # -- WebSocket clients ---------------------------------------------------

    def _on_ws_connection(self) -> None:
        assert self._ws is not None
        while self._ws.hasPendingConnections():
            client = self._ws.nextPendingConnection()
            client.disconnected.connect(lambda c=client: self._drop(c))
            self._clients.append(client)
            # A late joiner needs the current session config to initialise.
            if self._last_config is not None:
                client.sendTextMessage(json.dumps(self._last_config))
            self.clients_changed.emit(len(self._clients))

    def _drop(self, client) -> None:
        try:
            self._clients.remove(client)
        except ValueError:
            pass
        try:
            client.deleteLater()
        except RuntimeError:      # C++ object already gone (teardown race)
            pass
        self.clients_changed.emit(len(self._clients))

    # -- broadcasting --------------------------------------------------------

    def broadcast(self, payload: dict) -> None:
        """Send one JSON frame to every connected follower."""
        if payload.get("t") == "config":
            self._last_config = payload  # remember for late joiners
        if not self._clients:
            return
        msg = json.dumps(payload, separators=(",", ":"))
        for client in list(self._clients):
            try:
                client.sendTextMessage(msg)
            except RuntimeError:
                self._drop(client)


def _demo_main() -> int:
    """Serve the follower dashboard with synthetic data, for a quick preview::

        python -m emgteach.broadcast

    Open the printed URL in a browser to see exactly what students would see,
    without any hardware. Ctrl-C to stop.
    """
    import math
    import sys

    from PySide6.QtCore import QCoreApplication, QTimer

    app = QCoreApplication(sys.argv)
    srv = BroadcastServer()
    if not srv.start():
        print("Could not start the broadcast server (port busy?).", file=sys.stderr)
        return 1
    print(f"emgteach dashboard preview (demo data) at {srv.follower_url()}")
    srv.broadcast({"t": "config", "n": 2,
                   "labels": ["Bíceps", "Tríceps"], "recording": True})
    state = {"k": 0}

    def _zone(p: float) -> str:
        return "danger" if p >= 70 else "warning" if p >= 40 else "normal"

    def tick() -> None:
        k = state["k"]
        state["k"] = k + 1
        ph = k * 0.1
        e0 = [max(0.0, 0.2 + 0.25 * math.sin(ph + i * 0.3) + 0.05 * math.sin(ph * 3))
              for i in range(8)]
        e1 = [max(0.0, 0.15 + 0.2 * math.sin(ph * 0.8 + i * 0.3 + 1)) for i in range(8)]
        srv.broadcast({"t": "data", "env": [e0, e1]})
        p0 = 30 + 40 * (0.5 + 0.5 * math.sin(ph * 0.5))
        p1 = 20 + 55 * (0.5 + 0.5 * math.sin(ph * 0.4 + 2))
        srv.broadcast({"t": "load", "warn": 40, "danger": 70, "ch": [
            {"active": True, "pct": p0, "static": 8, "median": 22,
             "peak": round(p0), "zone": _zone(p0)},
            {"active": True, "pct": p1, "static": 6, "median": 18,
             "peak": round(p1), "zone": _zone(p1)},
        ]})
        c = k % 120
        if c < 30:
            srv.broadcast({"t": "calib", "active": True, "phase": "ready",
                           "title": "Prepárate — Bíceps",
                           "sub": "Contracción máxima al llegar a 0", "count": 3 - c // 10})
        elif c < 70:
            cc = (c - 30) / 40.0
            srv.broadcast({"t": "calib", "active": True, "phase": "contract",
                           "title": "¡Contrae Bíceps al máximo!", "secs": 4 * (1 - cc),
                           "progress": cc, "effort": 0.4 + 0.5 * math.sin(cc * 6)})
        elif c < 80:
            srv.broadcast({"t": "calib", "active": True, "phase": "done",
                           "title": "CVM listo",
                           "sub": "Bíceps: 0.52 mV · Tríceps: 0.48 mV"})
        else:
            srv.broadcast({"t": "calib", "active": False})

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
