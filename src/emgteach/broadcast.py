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

Access control: every :meth:`BroadcastServer.start` mints a fresh random
session code, embedded as ``?k=...`` in :meth:`BroadcastServer.follower_url`.
Both servers reject requests without the current code, so a follower link
only works for the session it was shared for — stopping and restarting the
broadcast invalidates every previously shared link (students from a past
practical cannot reconnect), and knowing the host's IP alone is not enough
to watch.
"""

from __future__ import annotations

import json
import secrets
import socket
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs

from PySide6.QtCore import QObject, QUrlQuery, Signal
from PySide6.QtNetwork import QHostAddress, QNetworkInterface, QTcpServer
from PySide6.QtWebSockets import QWebSocketProtocol, QWebSocketServer

from emgteach.difusion import (
    DEFAULT_DATA_PORT,
    DEFAULT_PAGE_PORT,
    PORTS_FILE,
    read_broadcast_address,
)
from emgteach.i18n import tr

# Default ports for the classroom broadcast (HTTP page + WebSocket data); a
# laboratory changes them in difusion.txt next to the application.
DEFAULT_HTTP_PORT = DEFAULT_PAGE_PORT
DEFAULT_WS_PORT = DEFAULT_DATA_PORT

_DASHBOARD = Path(__file__).resolve().parent / "web" / "dashboard.html"


def _load_dashboard_html() -> bytes:
    """Read the follower dashboard page (bundled next to this module)."""
    try:
        return _DASHBOARD.read_bytes()
    except OSError:
        return b"<!doctype html><meta charset=utf-8><p>Dashboard not found.</p>"


#: Words in an interface's name that make it a virtual adapter: Hyper-V,
#: WSL and Docker («vEthernet (…)»), VirtualBox, VMware, the VPN clients and
#: overlay networks, Npcap and Bluetooth. Such an adapter is up and running
#: whether or not anything is behind it, and its address is on a network the
#: phones are not on: on a computer with WSL installed, the link carried a
#: 172.x address and no phone could load the page (November 2026).
_VIRTUAL_WORDS = (
    "vethernet", "hyper-v", "wsl", "virtualbox", "vmware", "vmnet", "docker",
    "tap", "tun", "wintun", "wireguard", "vpn", "forti", "anyconnect",
    "globalprotect", "pangp", "tailscale", "zerotier", "npcap", "bluetooth",
    "loopback",
)

#: The network Windows' mobile hotspot gives the phones it shares this
#: computer's connection with: what the application itself advises when
#: there is no network the phones and the computer share.
HOTSPOT_PREFIX = "192.168.137."


@dataclass(frozen=True)
class Candidate:
    """An IPv4 address of this computer the phones might reach it by."""

    ip: str
    interface: str
    virtual: bool = False


@dataclass
class AddressChoice:
    """Which address the follower link carries, and why.

    ``reason`` is one of ``"fixed_ip"``, ``"fixed_interface"``, ``"hotspot"``,
    ``"route"``, ``"first_real"``, ``"virtual"`` or ``"none"``. ``route`` is
    the address the default route leaves by, when there is one; ``notes``
    are what the event log must also say (a fixed address or interface that
    is not on this computer now).
    """

    ip: str
    reason: str
    candidates: list[Candidate]
    route: str | None = None
    notes: list[str] = field(default_factory=list)


def _looks_virtual(name: str) -> bool:
    nombre = name.lower()
    return any(w in nombre for w in _VIRTUAL_WORDS)


def ipv4_candidates() -> list[Candidate]:
    """Every IPv4 of an up, running, non-loopback interface, in the system's order.

    Loopback (127.x) and link-local (169.254.x) addresses are left out: the
    first is the phone itself when typed on a phone, the second is what an
    interface gives itself when no network answered.
    """
    out: list[Candidate] = []
    for iface in QNetworkInterface.allInterfaces():
        flags = iface.flags()
        if not (flags & QNetworkInterface.InterfaceFlag.IsUp):
            continue
        if not (flags & QNetworkInterface.InterfaceFlag.IsRunning):
            continue
        if flags & QNetworkInterface.InterfaceFlag.IsLoopBack:
            continue
        nombre = iface.humanReadableName() or iface.name()
        virtual = (iface.type() == QNetworkInterface.InterfaceType.Virtual
                   or _looks_virtual(nombre))
        for entry in iface.addressEntries():
            s = entry.ip().toString()
            if ":" in s:                       # skip IPv6
                continue
            if s.startswith("127.") or s.startswith("169.254."):
                continue
            out.append(Candidate(s, nombre, virtual))
    return out


def default_route_ipv4() -> str | None:
    """The address this computer's default route leaves by, or ``None``.

    A UDP socket «connected» to an outside address makes the system pick the
    route and the local address for it, and nothing is sent: connecting a
    datagram socket only records where it would send. Without a default
    route the connect fails, and there is no answer.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 53))
            ip = s.getsockname()[0]
    except OSError:
        return None
    return ip if ip and not ip.startswith(("0.", "127.")) else None


def choose_ipv4(candidates: list[Candidate], route: str | None,
                fixed_ip: str | None = None,
                fixed_interface: str | None = None) -> AddressChoice:
    """Which of *candidates* the follower link should carry.

    In order: the address fixed in difusion.txt, if it is on this computer
    now; the address of the interface fixed there; the mobile hotspot's,
    because that is the network the application sends the phones to when
    there is no other; the one the default route leaves by, unless it is a
    virtual adapter's (a VPN that takes all the traffic); the first that is
    not virtual; a virtual one as the last resort; and with none at all,
    ``127.0.0.1``, which :func:`hay_red_utilizable` reads as no network.
    """
    notes: list[str] = []
    por_ip = {c.ip: c for c in candidates}

    def elige(c: Candidate, reason: str) -> AddressChoice:
        return AddressChoice(c.ip, reason, list(candidates), route, notes)

    if fixed_ip:
        if fixed_ip in por_ip:
            return elige(por_ip[fixed_ip], "fixed_ip")
        notes.append(tr(
            "The address {ip} fixed in {file} is not on this computer now; "
            "another one is chosen.").format(ip=fixed_ip, file=PORTS_FILE))
    if fixed_interface:
        de_esa = [c for c in candidates
                  if c.interface.casefold() == fixed_interface.casefold()]
        if de_esa:
            return elige(de_esa[0], "fixed_interface")
        notes.append(tr(
            "The interface «{iface}» fixed in {file} has no IPv4 address on "
            "this computer now; another one is chosen.").format(
                iface=fixed_interface, file=PORTS_FILE))
    hotspot = [c for c in candidates if c.ip.startswith(HOTSPOT_PREFIX)]
    if hotspot:
        return elige(hotspot[0], "hotspot")
    if route in por_ip and not por_ip[route].virtual:
        return elige(por_ip[route], "route")
    reales = [c for c in candidates if not c.virtual]
    if reales:
        return elige(reales[0], "first_real")
    if candidates:
        return elige(candidates[0], "virtual")
    return AddressChoice("127.0.0.1", "none", [], route, notes)


def current_address_choice(folder: Path | None = None) -> AddressChoice:
    """The choice for this computer as it is now, with difusion.txt's say."""
    fixed_ip, fixed_interface = read_broadcast_address(folder)
    return choose_ipv4(ipv4_candidates(), default_route_ipv4(),
                       fixed_ip, fixed_interface)


def address_report(choice: AddressChoice) -> list[str]:
    """The event log's lines: every candidate, and which one and why.

    Written when the broadcast starts, so that a computer whose phones
    cannot load the page says, where the operator reads, which addresses it
    had and which one it gave them.
    """
    def nombre(c: Candidate) -> str:
        return (tr("{iface}, virtual").format(iface=c.interface) if c.virtual
                else c.interface)

    if not choice.candidates:
        return [*choice.notes, tr("Broadcast: this computer has no IPv4 address "
                                  "the phones could reach.")]
    lista = "; ".join(f"{c.ip} ({nombre(c)})" for c in choice.candidates)
    lineas = [tr("Broadcast addresses of this computer: {list}.").format(list=lista)]
    lineas += choice.notes
    elegida = next(c for c in choice.candidates if c.ip == choice.ip)
    por_ruta = next((c for c in choice.candidates if c.ip == choice.route), None)
    if choice.reason == "fixed_ip":
        lineas.append(tr("Chosen: {ip}, fixed in {file}.").format(
            ip=choice.ip, file=PORTS_FILE))
    elif choice.reason == "fixed_interface":
        lineas.append(tr("Chosen: {ip}, of the interface «{iface}» fixed in {file}.")
                      .format(ip=choice.ip, iface=elegida.interface, file=PORTS_FILE))
    elif choice.reason == "hotspot":
        if por_ruta is not None and por_ruta.ip != choice.ip:
            ruta = tr("the default route goes through {iface} ({ip})").format(
                iface=por_ruta.interface, ip=por_ruta.ip)
        elif choice.route:
            ruta = tr("the default route goes through {ip}").format(ip=choice.route)
        else:
            ruta = tr("there is no default route")
        lineas.append(tr(
            "Chosen: the mobile hotspot, {ip}; {route}. If the phones are "
            "not on the hotspot, fix the address in {file}.").format(
                ip=choice.ip, route=ruta, file=PORTS_FILE))
    elif choice.reason == "route":
        lineas.append(tr("Chosen: {ip} ({iface}), the one the default route "
                         "goes through.").format(ip=choice.ip, iface=elegida.interface))
    elif choice.reason == "first_real":
        lineas.append(tr("Chosen: {ip} ({iface}), the first that is not a "
                         "virtual adapter.").format(ip=choice.ip, iface=elegida.interface))
    else:
        lineas.append(tr("Chosen: {ip} ({iface}); every address is a virtual "
                         "adapter's, and the phones may not reach it.").format(
                             ip=choice.ip, iface=elegida.interface))
    return lineas


def lan_ipv4() -> str:
    """The IPv4 address the follower link carries (see :func:`choose_ipv4`).

    It used to be the first address of the first interface the system
    listed, and on a PC with a virtual adapter — WSL, VirtualBox, a VPN — that
    was the adapter's, on a network no phone was on.
    """
    return current_address_choice().ip


def hay_red_utilizable() -> bool:
    """Whether the phones have any way at all to reach this computer.

    :func:`lan_ipv4` falls back to ``127.0.0.1`` when no interface is up — an
    address that, typed on a phone, means the phone itself. A follower link
    built on it can never load.
    """
    return lan_ipv4() != "127.0.0.1"


# Served (with 403) when a request carries a wrong/expired session code.
_DENIED_HTML = (
    b"<!doctype html><meta charset=utf-8>"
    b"<meta name=viewport content='width=device-width,initial-scale=1'>"
    b"<title>emgteach</title>"
    b"<body style='font-family:system-ui;background:#10141a;color:#dde;"
    b"display:flex;align-items:center;justify-content:center;height:95vh;"
    b"text-align:center'><div><h2>&#128274; Enlace no v&aacute;lido o "
    b"sesi&oacute;n finalizada</h2><p>Pide al profesor el enlace de la "
    b"sesi&oacute;n de hoy.<br><small>Invalid or expired session link "
    b"&mdash; ask your instructor for today's link.</small></p></div>"
)


class _HttpServer(QTcpServer):
    """Minimal HTTP/1.1 server: the dashboard page for any path, plus any
    registered downloadable files (the recording CSV, the analysis report).

    Every request must carry the current session code (``?k=...``); anything
    else gets the 403 page so stale links from a past session are dead ends.
    """

    def __init__(self, html: bytes, downloads: dict, token: str, parent=None) -> None:
        super().__init__(parent)
        self._html = html
        self._downloads = downloads          # path -> (bytes, content_type, filename)
        self._token = token
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
        try:
            target = data.split(b"\r\n", 1)[0].decode("latin-1").split(" ")[1]
        except (IndexError, UnicodeDecodeError):
            target = "/"
        path, _, query = target.partition("?")
        key = (parse_qs(query).get("k") or [""])[0]
        # Compare as bytes: compare_digest() rejects non-ASCII str input.
        if not secrets.compare_digest(
            key.encode("utf-8", "ignore"), self._token.encode()
        ):
            body = _DENIED_HTML
            head = (
                b"HTTP/1.1 403 Forbidden\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Cache-Control: no-store\r\n"
                b"Connection: close\r\n\r\n"
            )
            sock.write(head + body)
            sock.flush()
            sock.disconnectFromHost()
            return
        entry = self._downloads.get(path)
        if entry is not None:
            payload, ctype, fname = entry
            fn = fname.encode("ascii", "ignore")
            head = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: " + ctype.encode() + b"\r\n"
                b'Content-Disposition: attachment; filename="' + fn + b'"\r\n'
                b"Content-Length: " + str(len(payload)).encode() + b"\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"Cache-Control: no-store\r\n"
                b"Connection: close\r\n\r\n"
            )
            sock.write(head + payload)
        else:
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
        self._downloads: dict = {}   # path -> (bytes, content_type, filename)
        # The last «download» frame of each kind: sent again to every follower
        # who connects, as the config is (see _on_ws_connection).
        self._offers: dict[str, dict] = {}
        # The last «results» frame (the metrics of the analysis), sent again
        # to every follower who connects and forgotten with the offers: a
        # phone that joined late got the report's button over an empty panel.
        self._last_results: dict | None = None
        self._token: str = ""        # per-session access code; minted on start()
        #: The port :meth:`start` could not open, or ``None``.
        self.failed_port: int | None = None

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> bool:
        """Start both servers. Returns ``True`` on success.

        Mints a fresh session code, so links shared for a previous
        broadcast stop working. On failure, :attr:`failed_port` says which
        port could not be opened.
        """
        if self.is_running():
            return True
        self.failed_port = None
        # 6 lowercase hex chars: easy to (re)type on a phone, and with the
        # link only valid while this session runs, ample against guessing.
        self._token = secrets.token_hex(3)
        from emgteach.i18n import get_language

        html = _load_dashboard_html().replace(
            b"{{WS_PORT}}", str(self._ws_port).encode()
        ).replace(
            b"{{LANG}}", get_language().encode()
        )
        http = _HttpServer(html, self._downloads, self._token, self)
        if not http.listen(QHostAddress(QHostAddress.SpecialAddress.Any), self._http_port):
            http.deleteLater()
            self.failed_port = self._http_port
            return False
        ws = QWebSocketServer(
            "emgteach", QWebSocketServer.SslMode.NonSecureMode, self
        )
        if not ws.listen(QHostAddress(QHostAddress.SpecialAddress.Any), self._ws_port):
            http.close()
            http.deleteLater()
            ws.deleteLater()
            self.failed_port = self._ws_port
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
        self._downloads.clear()
        self._offers.clear()
        self._last_results = None
        self.clients_changed.emit(0)

    def is_running(self) -> bool:
        return self._ws is not None

    def ports(self) -> tuple[int, int]:
        """The page port and the data port this server uses."""
        return self._http_port, self._ws_port

    def client_count(self) -> int:
        return len(self._clients)

    def address_choice(self) -> AddressChoice:
        """Which address of this computer the follower link carries, and why."""
        return current_address_choice()

    def follower_url(self) -> str:
        """URL students open in their browser to follow *this* session.

        Includes the per-session access code; the link dies when the
        broadcast is stopped.
        """
        return f"http://{lan_ipv4()}:{self._http_port}/?k={self._token}"

    # -- WebSocket clients ---------------------------------------------------

    def _on_ws_connection(self) -> None:
        assert self._ws is not None
        while self._ws.hasPendingConnections():
            client = self._ws.nextPendingConnection()
            key = QUrlQuery(client.requestUrl()).queryItemValue("k")
            if not secrets.compare_digest(
                key.encode("utf-8", "ignore"), self._token.encode()
            ):
                client.close(QWebSocketProtocol.CloseCode.CloseCodePolicyViolated)
                client.deleteLater()
                continue
            client.disconnected.connect(lambda c=client: self._drop(c))
            self._clients.append(client)
            # A late joiner needs the current session config to initialise,
            # and the files already on offer. The «download» frame used to go
            # once, to whoever was connected at that instant: a phone that
            # opens the page later, or reconnects after its screen goes off,
            # never saw it (ecgteach bench of 5 Oct 2026, E11; the 3.7.2 too).
            for frame in self.frames_for_a_new_follower():
                client.sendTextMessage(frame)
            self.clients_changed.emit(len(self._clients))

    def frames_for_a_new_follower(self) -> list[str]:
        """What a follower that connects now is sent, in order: the session's
        configuration, the last metrics and the files on offer."""
        frames = []
        if self._last_config is not None:
            frames.append(json.dumps(self._last_config))
        if self._last_results is not None:
            frames.append(json.dumps(self._last_results, separators=(",", ":")))
        for offer in self._offers.values():
            frames.append(json.dumps(offer, separators=(",", ":")))
        return frames

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
            # A new session: the files of the last one are not offered in it.
            self._offers.clear()
            self._last_results = None
        elif payload.get("t") == "status" and payload.get("recording"):
            # A new recording, too: its start sends a status, not a config,
            # and a phone joining during the second recording would get the
            # first one's report.
            self._offers.clear()
            self._last_results = None
        elif payload.get("t") == "results":
            self._last_results = payload
        elif payload.get("t") == "download":
            self._offers[str(payload.get("kind", ""))] = payload
        if not self._clients:
            return
        msg = json.dumps(payload, separators=(",", ":"))
        for client in list(self._clients):
            try:
                client.sendTextMessage(msg)
            except RuntimeError:
                self._drop(client)

    def register_download(self, path: str, data: bytes,
                          content_type: str, filename: str) -> None:
        """Make a file downloadable at ``http://host:port<path>`` for followers.

        Overwrites any file previously registered at the same path; all
        registered files are cleared on :meth:`stop`.
        """
        self._downloads[path] = (bytes(data), content_type, filename)


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
        print(f"Could not start the broadcast server: port {srv.failed_port} busy.",
              file=sys.stderr)
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
