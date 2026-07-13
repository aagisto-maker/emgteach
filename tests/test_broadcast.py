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
    assert srv.follower_url().startswith("http://") and srv.follower_url().endswith(":8110")
    assert srv.client_count() == 0
    # Broadcasting with no followers is a safe no-op, and config is remembered.
    srv.broadcast({"t": "config", "n": 1, "labels": ["EMG"], "recording": False})
    assert srv._last_config is not None
    srv.stop()
    assert not srv.is_running()


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
    ws.open(QUrl("ws://127.0.0.1:8113"))

    loop = QEventLoop()
    QTimer.singleShot(3000, loop.quit)
    QTimer.singleShot(600, loop.quit)   # enough for localhost round-trip
    loop.exec()

    assert srv.client_count() == 1
    assert any('"t":"config"' in m for m in received)
    assert any('"t":"data"' in m for m in received)

    ws.close()
    srv.stop()


def test_registered_download_is_served(qapp) -> None:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtNetwork import QTcpSocket

    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8114, ws_port=8115)
    assert srv.start()
    srv.register_download("/dl/x.csv", b"a,b\n1,2\n", "text/csv", "datos.csv")

    raw = bytearray()
    sock = QTcpSocket()
    sock.readyRead.connect(lambda: raw.extend(bytes(sock.readAll().data())))
    sock.connected.connect(
        lambda: sock.write(b"GET /dl/x.csv HTTP/1.1\r\nHost: x\r\n\r\n")
    )
    sock.connectToHost("127.0.0.1", 8114)

    loop = QEventLoop()
    QTimer.singleShot(600, loop.quit)
    loop.exec()

    resp = bytes(raw)
    assert b"200 OK" in resp
    assert b'Content-Disposition: attachment; filename="datos.csv"' in resp
    assert b"a,b\n1,2\n" in resp
    # An unregistered path still serves the dashboard, not a 404.
    srv.stop()
