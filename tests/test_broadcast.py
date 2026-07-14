"""Tests for the classroom broadcast server (:mod:`emgteach.broadcast`).

Marked ``gui`` because the Qt-native servers need a QApplication / event loop
(offscreen, set in ``conftest.py``).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_dashboard_asset_and_lan_ip() -> None:
    from emgteach.broadcast import _load_dashboard_html, lan_ipv4

    html = _load_dashboard_html()
    assert b"emgteach" in html
    assert b"{{WS_PORT}}" in html          # placeholder substituted at serve time
    ip = lan_ipv4()
    assert isinstance(ip, str) and ip.count(".") == 3


def test_start_stop_and_config_cache(qapp) -> None:
    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8110, ws_port=8111)
    assert srv.start()
    assert srv.is_running()
    url = srv.follower_url()
    assert url.startswith("http://") and f":8110/?k={srv._token}" in url
    assert srv.client_count() == 0
    # Broadcasting with no followers is a safe no-op, and config is remembered.
    srv.broadcast({"t": "config", "n": 1, "labels": ["EMG"], "recording": False})
    assert srv._last_config is not None
    srv.stop()
    assert not srv.is_running()


def test_session_code_rotates_between_starts(qapp) -> None:
    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8116, ws_port=8117)
    assert srv.start()
    first = srv._token
    assert len(first) == 6
    srv.stop()
    assert srv.start()
    # A new session mints a new code, so links shared for the previous
    # practical no longer work.
    assert srv._token != first
    srv.stop()


def test_broadcast_reaches_a_follower(qapp) -> None:
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtWebSockets import QWebSocket

    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8112, ws_port=8113)
    assert srv.start()

    received: list[str] = []
    ws = QWebSocket()
    ws.textMessageReceived.connect(received.append)

    def on_open() -> None:
        # config is auto-sent on connect (cached); push one live frame too.
        srv.broadcast({"t": "config", "n": 2, "labels": ["A", "B"], "recording": True})
        srv.broadcast({"t": "data", "env": [[0.1], [0.2]]})

    ws.connected.connect(on_open)
    ws.open(QUrl(f"ws://127.0.0.1:8113/?k={srv._token}"))

    loop = QEventLoop()
    QTimer.singleShot(3000, loop.quit)
    QTimer.singleShot(600, loop.quit)   # enough for localhost round-trip
    loop.exec()

    assert srv.client_count() == 1
    assert any('"t":"config"' in m for m in received)
    assert any('"t":"data"' in m for m in received)

    ws.close()
    srv.stop()


def test_follower_without_session_code_is_rejected(qapp) -> None:
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtWebSockets import QWebSocket

    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8118, ws_port=8119)
    assert srv.start()

    ws = QWebSocket()
    ws.open(QUrl("ws://127.0.0.1:8119"))          # no ?k=... code
    ws_bad = QWebSocket()
    ws_bad.open(QUrl("ws://127.0.0.1:8119/?k=nope"))

    loop = QEventLoop()
    QTimer.singleShot(600, loop.quit)
    loop.exec()

    assert srv.client_count() == 0
    ws.close()
    ws_bad.close()
    srv.stop()


def test_registered_download_is_served(qapp) -> None:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtNetwork import QTcpSocket

    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8114, ws_port=8115)
    assert srv.start()
    srv.register_download("/dl/x.csv", b"a,b\n1,2\n", "text/csv", "datos.csv")

    def http_get(target: str) -> bytes:
        raw = bytearray()
        sock = QTcpSocket()
        sock.readyRead.connect(lambda: raw.extend(bytes(sock.readAll().data())))
        sock.connected.connect(
            lambda: sock.write(
                b"GET " + target.encode() + b" HTTP/1.1\r\nHost: x\r\n\r\n"
            )
        )
        sock.connectToHost("127.0.0.1", 8114)
        loop = QEventLoop()
        QTimer.singleShot(600, loop.quit)
        loop.exec()
        return bytes(raw)

    resp = http_get(f"/dl/x.csv?k={srv._token}")
    assert b"200 OK" in resp
    assert b'Content-Disposition: attachment; filename="datos.csv"' in resp
    assert b"a,b\n1,2\n" in resp

    # The dashboard is served (not a 404) for any unregistered path with a
    # valid code…
    resp = http_get(f"/whatever?k={srv._token}")
    assert b"200 OK" in resp and b"text/html" in resp

    # …while a missing or stale session code gets the 403 page instead of
    # the dashboard or the file.
    for target in ("/", "/dl/x.csv", "/dl/x.csv?k=stale1"):
        resp = http_get(target)
        assert b"403 Forbidden" in resp
        assert b"a,b" not in resp

    srv.stop()
