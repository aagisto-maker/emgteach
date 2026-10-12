"""A new recording forgets the last one's report, on the server and on the page.

Bench of 12 October 2026, M10: with the broadcast on, a second recording
was made, and two phones showed the report and the metrics with it. The
server already forgot them when a recording started (broadcast.py, the
«status» frame); what a follower gets during the second recording and after
it is checked here from the acquisition tab, as the bench drove it, with the
analysis tab wired as the window wires it. After the recording the analysis
runs by itself (``AnalysisTab.adopt_recording``), and what reaches the phones
is the new recording's report, never the last one's.

The page that stayed open kept the last report on screen, under the new
recording: it now clears it on a new recording or a new session. Its script
runs under Node with a small stand-in for the browser; without Node that
test is skipped.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from tests.test_broadcast import _follow
from tests.test_eventos_y_capturas import _pump, _record, _until

PAGE = Path(__file__).resolve().parents[1] / "src" / "emgteach" / "web" / "dashboard.html"


def _kinds(frames: list[str]) -> list[dict]:
    return [m for m in map(json.loads, frames) if m["t"] in ("results", "download")]


@pytest.mark.gui
def test_a_follower_never_gets_the_last_recordings_report(qapp, tmp_path, monkeypatch) -> None:
    from emgteach.broadcast import BroadcastServer
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "grabacion-nueva-olvida-el-informe")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/port", "simulada")
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    srv = BroadcastServer(http_port=8130, ws_port=8131)
    log = LoggerWidget()
    tab = AcquisitionTab(log, settings, broadcast=srv)
    ana = AnalysisTab(log, settings, broadcast=srv)
    tab.recording_saved.connect(ana.adopt_recording)
    tab.apply_mode("single", False)
    tab._edit_mac.setText("simulada")
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tab.next_path), "")))
    try:
        tab._on_toggle_broadcast(True)
        assert srv.is_running()
        tab._btn_conectar.setChecked(True)
        tab._toggle_conexion()

        # First recording, its analysis and its report (M8).
        _record(qapp, tab, tmp_path / "a.edf", 3.0)
        _until(qapp, lambda: "report" in srv._offers, 60.0, "the first report")
        first = _kinds(_follow(srv, 8131, wait_ms=2000))
        assert [m["t"] for m in first] == ["results", "download"]
        assert first[0]["file"] == "a.edf"

        # Second recording, started from the tab: a phone that joins while
        # it runs gets the session, and nothing of the first recording.
        tab.next_path = tmp_path / "b.edf"
        tab._btn_grabar.setChecked(True)
        tab._toggle_grabacion()
        _until(qapp, lambda: tab._worker is not None and tab._total_samples > 300,
               8.0, "the second recording")
        during = list(map(json.loads, _follow(srv, 8131, wait_ms=2000)))
        assert during[0]["t"] == "config"
        assert not [m for m in during if m["t"] in ("results", "download")]

        # And after it, only the second recording's own analysis.
        tab._btn_grabar.setChecked(False)
        tab._toggle_grabacion()
        _until(qapp, lambda: not tab.is_recording(), 5.0, "the recording to end")
        _until(qapp, lambda: "report" in srv._offers, 60.0, "the second report")
        after = _kinds(_follow(srv, 8131, wait_ms=2000))
        assert [m["t"] for m in after] == ["results", "download"]
        assert after[0]["file"] == "b.edf"
        assert after[1]["name"].startswith("b")
    finally:
        tab.cleanup()
        srv.stop()
        settings.clear()
        _pump(qapp, 100)


_BROWSER = r"""
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const script = html.split("<script>")[1].split("</script>")[0];
const any = new Proxy(function () {}, { get: (t, p) => p === Symbol.toPrimitive ? () => 0 : any, apply: () => any, construct: () => any, set: () => true });
const els = {};
function el(id) {
  const e = { id, style: {}, children: [], innerHTML: "", textContent: "",
    classList: { toggle() {}, add() {}, remove() {} },
    appendChild(c) { this.children.push(c); if (c.id) els[c.id] = c; return c; },
    remove() { if (els[this.id] === p) delete els[this.id]; },
    setAttribute() {} };
  const p = new Proxy(e, { get: (t, k) => (k in t ? t[k] : any) });
  return p;
}
for (const m of html.matchAll(/id="([^"]+)"/g)) els[m[1]] = el(m[1]);
global.document = { getElementById: (id) => els[id] || null, createElement: () => el(""), title: "" };
global.window = { devicePixelRatio: 1 };
global.location = { hostname: "h", search: "?k=1" };
global.requestAnimationFrame = () => {};
let sock;
global.WebSocket = class { constructor() { sock = this; } close() {} };
new Function(script.replace("{{WS_PORT}}", "1"))();
const frames = JSON.parse(fs.readFileSync(0, "utf8"));
const out = [];
for (const f of frames) {
  sock.onmessage({ data: JSON.stringify(f) });
  out.push({ shown: els.results.style.display, metrics: els.resMetrics.innerHTML !== "", button: !!els.dl_report });
}
console.log(JSON.stringify(out));
"""


def _page(tmp_path: Path, frames: list[dict]) -> list[dict]:
    """What the page shows after each of *frames*."""
    harness = tmp_path / "pagina.js"
    harness.write_text(_BROWSER, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(PAGE)], input=json.dumps(frames),
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True,
    )
    return json.loads(out.stdout)


_RESULTS = {"t": "results", "file": "a.edf", "mnf": 80.0, "mdf": 70.0, "mdf_slope": -0.1,
            "rms": 0.2, "iemg": 1.0, "duration": 30.0, "fatigue": 0}
_REPORT = {"t": "download", "kind": "report", "url": "/dl/informe.pdf", "name": "a_informe.pdf"}
_CONFIG = {"t": "config", "n": 1, "labels": ["Bíceps"], "recording": False}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to run the page")
def test_the_open_page_clears_the_report_when_a_recording_starts(tmp_path) -> None:
    shown = _page(tmp_path, [_CONFIG, _RESULTS, _REPORT,
                             {"t": "status", "recording": False},
                             {"t": "status", "recording": True}])
    # The report is shown, and stays when a recording stops…
    assert shown[2] == shown[3] == {"shown": "block", "metrics": True, "button": True}
    # …and goes when the next one starts.
    assert shown[4] == {"shown": "none", "metrics": False, "button": False}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to run the page")
def test_a_new_session_clears_the_report_and_a_late_joiner_still_gets_it(tmp_path) -> None:
    # A late joiner gets config, results and report in that order: the
    # config clears first, so what follows stays.
    shown = _page(tmp_path, [_CONFIG, _RESULTS, _REPORT, _CONFIG])
    assert shown[2] == {"shown": "block", "metrics": True, "button": True}
    assert shown[3] == {"shown": "none", "metrics": False, "button": False}
