"""Analogue-channel diagnostic for the BITalino.

Reads all six analogue inputs (A1-A6) at once and shows, per channel, the live
raw ADC value and the range (max - min) seen since the scan started. Tilt the
accelerometer slowly: the channel whose range grows the most is the one the
accelerometer is actually wired to. This finds the ACC's real channel
independently of any per-channel scaling, which is why it is the ground truth
when the expected channel (A4) reads only noise.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from emgteach.i18n import tr

_CH_NAMES = ["A1", "A2", "A3", "A4", "A5", "A6"]


class _ChannelScanWorker(QThread):
    """Streams all six channels and emits per-channel (last, min, max) raw ADC."""

    stats = Signal(list)   # list of (last, vmin, vmax) per decoded channel
    failed = Signal(str)

    def __init__(self, device) -> None:
        super().__init__()
        self._device = device
        self._running = True
        self._reset = False

    def request_reset(self) -> None:
        self._reset = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        try:
            self._device.open()
        except Exception as exc:  # pragma: no cover - hardware/serial errors
            self.failed.emit(str(exc))
            return
        n_ch = None
        vmin = vmax = None
        try:
            while self._running:
                block = np.asarray(self._device.read_raw(100), dtype=np.float64)
                if block.size == 0:
                    continue
                if n_ch is None or self._reset:
                    n_ch = block.shape[1]
                    vmin = block.min(axis=0)
                    vmax = block.max(axis=0)
                    self._reset = False
                else:
                    vmin = np.minimum(vmin, block.min(axis=0))
                    vmax = np.maximum(vmax, block.max(axis=0))
                last = block[-1]
                self.stats.emit([
                    (float(last[c]), float(vmin[c]), float(vmax[c]))
                    for c in range(n_ch)
                ])
        except Exception as exc:  # pragma: no cover - hardware/serial errors
            if self._running:
                self.failed.emit(str(exc))
        finally:
            try:
                self._device.close()
            except Exception:
                pass


class ChannelDiagnosticDialog(QDialog):
    """Live per-channel raw readout to locate the accelerometer's real channel."""

    def __init__(self, device_factory, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Find the accelerometer channel"))
        self.setMinimumWidth(460)
        self._max_range = 1.0
        # Set to the responding channel index once one clearly stands out; the
        # caller reads it to point the ACC at the right analogue input.
        self.found_channel: int | None = None

        root = QVBoxLayout(self)
        intro = QLabel(tr(
            "Reading all six analogue inputs. Tilt the accelerometer slowly "
            "through 90° in each direction: the channel whose range grows the "
            "most is where the accelerometer is wired. A4 is the one emgteach "
            "uses for the ACC."
        ))
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#555; font-size:11px;")
        root.addWidget(intro)

        self._table = QTableWidget(6, 4)
        self._table.setHorizontalHeaderLabels([
            tr("Channel"), tr("Value (raw)"), tr("Range"), tr("Movement"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._bars: list[QProgressBar] = []
        for r in range(6):
            name = QTableWidgetItem(_CH_NAMES[r])
            self._table.setItem(r, 0, name)
            self._table.setItem(r, 1, QTableWidgetItem("—"))
            self._table.setItem(r, 2, QTableWidgetItem("—"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            self._bars.append(bar)
            self._table.setCellWidget(r, 3, bar)
        root.addWidget(self._table)

        self._verdict = QLabel("")
        self._verdict.setWordWrap(True)
        self._verdict.setStyleSheet("font-size:12px; font-weight:500;")
        root.addWidget(self._verdict)

        row = QHBoxLayout()
        self._btn_reset = QPushButton(tr("Reset ranges"))
        self._btn_reset.clicked.connect(self._on_reset)
        row.addWidget(self._btn_reset)
        self._btn_use = QPushButton(tr("Use this channel for the ACC"))
        self._btn_use.setEnabled(False)
        self._btn_use.clicked.connect(self.accept)
        row.addWidget(self._btn_use)
        row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        root.addLayout(row)

        self._worker = _ChannelScanWorker(device_factory())
        self._worker.stats.connect(self._on_stats)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_reset(self) -> None:
        self._max_range = 1.0
        self._worker.request_reset()

    @staticmethod
    def _pick_channel(ranges: list) -> int | None:
        """Index of the channel that clearly stands out (a real ACC swing), or
        ``None`` when nothing exceeds the noise floor.

        A winner needs an absolute range of at least 30 ADC counts and at least
        3× the next-largest range, so tremor/noise on the other inputs does not
        produce a false positive."""
        if not ranges:
            return None
        best = int(np.argmax(ranges))
        second = sorted(ranges)[-2] if len(ranges) > 1 else 0.0
        if ranges[best] >= 30 and ranges[best] >= 3 * second:
            return best
        return None

    def _on_stats(self, stats: list) -> None:
        ranges = [vmax - vmin for _last, vmin, vmax in stats]
        self._max_range = max(self._max_range, max(ranges) if ranges else 1.0)
        for r, (last, vmin, vmax) in enumerate(stats):
            rng = vmax - vmin
            self._table.item(r, 1).setText(f"{last:.0f}")
            self._table.item(r, 2).setText(f"{rng:.0f}")
            self._bars[r].setValue(int(100 * rng / self._max_range))
        best = self._pick_channel(ranges)
        self.found_channel = best
        self._btn_use.setEnabled(best is not None)
        if best is not None:
            ch = _CH_NAMES[best] if best < len(_CH_NAMES) else f"#{best}"
            if ch == "A4":
                self._verdict.setText(
                    tr("✓ The accelerometer responds on A4 — as expected.")
                )
                self._verdict.setStyleSheet(
                    "font-size:12px; font-weight:500; color:#1a7f37;"
                )
            else:
                self._verdict.setText(tr(
                    "→ The accelerometer is on {ch}, not A4. Move its plug to "
                    "the A4 port (or tell me and I make the ACC channel "
                    "selectable)."
                ).format(ch=ch))
                self._verdict.setStyleSheet(
                    "font-size:12px; font-weight:500; color:#b00020;"
                )
        else:
            self._verdict.setText(tr(
                "Tilt the sensor 90°… no channel clearly responds yet."
            ))
            self._verdict.setStyleSheet(
                "font-size:12px; font-weight:500; color:#555;"
            )

    def _on_failed(self, msg: str) -> None:
        self._verdict.setText(tr("Could not read the BITalino: {err}").format(err=msg))
        self._verdict.setStyleSheet(
            "font-size:12px; font-weight:500; color:#b00020;"
        )

    def _shutdown(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(3000)

    def reject(self) -> None:
        self._shutdown()
        super().reject()

    def accept(self) -> None:
        self._shutdown()
        super().accept()
