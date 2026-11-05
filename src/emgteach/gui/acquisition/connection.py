"""The device and its link, as a piece of the acquisition tab (step 2 of
docs/PLAN-partir-AcquisitionTab.md).

Which board, and where it is: the BITalino by its address (the lab's MAC,
a COM port, «simulada», or what bitalino.txt next to the application says)
or the Arduino by its serial port. The Connect button and the
communication LED are this piece's too, though the tab lays them out in its
control row, beside the record button. And so is the watch on the link
while a recording runs: the deadline for the board's first block, with the
box that says it did not answer and offers to try again, and the watchdog
that disconnects when samples stop arriving.

Communication, the rule of the plan: the tab calls the methods below and
listens to the signals. :attr:`logged` and :attr:`warned` carry the lines
the event log and the warning box get; :attr:`device_type_changed` asks for
the raw plot's scale to follow the device; :attr:`link_lost`,
:attr:`no_answer` and :attr:`retry_requested` hand the recording back to
the tab, which owns it. The worker is the tab's: the piece is given a way
to ask for the current one, and keeps no reference to it or to the tab.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QSettings, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from emgteach.devices import BACKEND_ARDUINO, device_class
from emgteach.devices.bitalino_sim import is_simulated_address
from emgteach.i18n import tr
from emgteach.station import ADDRESS_FILE, read_station_address

if TYPE_CHECKING:
    from emgteach.workers.acquisition import AcquisitionWorker

__all__ = [
    "CONEXION_MAX_S",
    "DEFAULT_BITALINO_ADDR",
    "LED_IDLE_MS",
    "ConnectionBox",
]

#: Seconds a recording waits for the board's first block before it stops
#: and says so. Reaching the board takes two or three seconds on the bench;
#: finding it among the Bluetooth ports, a few more. Past this the status
#: line was saying «recording…» over empty plots, and nothing was recorded.
CONEXION_MAX_S = 20.0

# Default BITalino address (editable in the field). The lab's MAC is stable
# across PCs; BitalinoDevice resolves it to the local virtual COM port. The
# field also accepts an explicit COMx, or empty for autodetection.
DEFAULT_BITALINO_ADDR = "98:D3:91:FE:44:E4"

# Interval (ms) after the last received data beyond which there is considered
# to be no traffic (the LED goes from green to yellow).
LED_IDLE_MS = 500


class ConnectionBox(QWidget):
    """The device row of the configuration, the Connect button and the LED,
    and the watch on the link while a recording runs."""

    #: A line for the event log.
    logged = Signal(str)
    #: A line for the event log, as an error.
    warned = Signal(str)
    #: The device type was changed (0 BITalino, 1 Arduino).
    device_type_changed = Signal(int)
    #: The watchdog found the samples stopped: the tab disconnects.
    link_lost = Signal()
    #: No block within CONEXION_MAX_S: the tab stops the recording.
    no_answer = Signal()
    #: «Retry» on the box that said the board did not answer.
    retry_requested = Signal()

    def __init__(
        self,
        settings: QSettings,
        worker: Callable[[], AcquisitionWorker | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._worker = worker

        # The box is the row, a named container so the basic UI level can hide
        # it at once — hiding the individual widgets would leave their labels.
        cfg_row1 = QHBoxLayout(self)
        cfg_row1.setContentsMargins(0, 0, 0, 0)
        cfg_row1.setSpacing(6)

        # Device-type combo. Both interchangeable backends are offered — the
        # BITalino (Bluetooth) and the Arduino + MyoWare 2.0 (USB) — matching
        # the documented, published feature set. BITalino is the default.
        self._combo_device_type = QComboBox()
        self._combo_device_type.addItem("BITalino (Bluetooth)")
        self._combo_device_type.addItem("Arduino + MyoWare 2.0 (USB)")
        saved_type = int(cast("int | str", self._settings.value("adquisicion/device_type", 0)))
        self._combo_device_type.setCurrentIndex(saved_type)
        self._combo_device_type.currentIndexChanged.connect(self._on_device_type_changed)
        # In the practicals that can only be done with the BITalino the
        # selector is hidden and this caption stands in for it, so the
        # address field beside it does not sit there unnamed.
        self._lbl_device_fixed = QLabel(tr("Device: BITalino"))
        self._lbl_device_fixed.setVisible(False)
        cfg_row1.addWidget(self._lbl_device_fixed)
        cfg_row1.addWidget(self._combo_device_type, stretch=1)

        # Conditional central area: COM port (BITalino) or COM selector (Arduino)
        # Wrapped in a QWidget so the content can change without rebuilding the layout
        self._widget_mac = QWidget()
        mac_inner = QHBoxLayout(self._widget_mac)
        mac_inner.setContentsMargins(0, 0, 0, 0)
        mac_inner.setSpacing(4)
        self._edit_mac = QLineEdit()
        self._edit_mac.setPlaceholderText("98:D3:91:FE:44:E4   ·   COM5   ·   (auto)")
        self._edit_mac.setToolTip(
            tr(
                "BITalino MAC address (recommended — stable on every PC), or an "
                "explicit COM port (e.g. COM5), or leave empty to autodetect. Pair "
                "the BITalino in Windows Bluetooth settings first. No PyBluez is used. "
                "Write «simulada» to try the application without the board. It starts "
                "from the address written in bitalino.txt next to the application, "
                "when there is one."
            )
        )
        # The station's address, when it is written in bitalino.txt next to
        # the application, is the one the tab starts with: typed once there,
        # never again at that station, whatever account or copy of the
        # application is used (see emgteach.station).
        self._station_address = read_station_address()
        self._edit_mac.setText(
            self._station_address if self._station_address is not None
            else cast(str, self._settings.value("adquisicion/port", DEFAULT_BITALINO_ADDR))
        )
        if self._station_address is not None:
            # Said once the tab is up, where the operator reads.
            QTimer.singleShot(0, self._log_station_address)
        mac_inner.addWidget(self._edit_mac)
        btn_reset_mac = QPushButton(tr("Default"))
        btn_reset_mac.setFixedWidth(84)
        btn_reset_mac.setToolTip(
            tr("Restore default address ({addr})").format(
                addr=self._default_address() or tr("autodetect")
            )
        )
        btn_reset_mac.clicked.connect(self._reset_mac)
        mac_inner.addWidget(btn_reset_mac)

        self._widget_arduino = QWidget()
        ard_inner = QHBoxLayout(self._widget_arduino)
        ard_inner.setContentsMargins(0, 0, 0, 0)
        ard_inner.setSpacing(4)
        self._combo_port = QComboBox()
        ard_inner.addWidget(self._combo_port)
        btn_refresh_ports = QPushButton(tr("Refresh"))
        btn_refresh_ports.setFixedWidth(84)
        btn_refresh_ports.setToolTip(tr("Refresh the list of available serial ports"))
        btn_refresh_ports.clicked.connect(self._refresh_ports)
        ard_inner.addWidget(btn_refresh_ports)

        # Container that switches between _widget_mac and _widget_arduino
        self._stack_conn = QWidget()
        stack_layout = QHBoxLayout(self._stack_conn)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.addWidget(self._widget_mac)
        stack_layout.addWidget(self._widget_arduino)
        cfg_row1.addWidget(self._stack_conn, stretch=2)
        # Shown only when the basic level reveals this row because no port has
        # been saved yet, so a first-time user knows it is a one-off step.
        self._lbl_first_setup = QLabel(tr("One-off setup"))
        self._lbl_first_setup.setStyleSheet("font-size: 9px; color: #1F4E79;")
        self._lbl_first_setup.setVisible(False)
        cfg_row1.addWidget(self._lbl_first_setup)

        # Initial visibility of the connection area
        self._widget_mac.setVisible(saved_type == 0)
        self._widget_arduino.setVisible(saved_type == 1)
        self._refresh_ports()

        # The Connect button and the LED are laid out by the tab, in its
        # control row; the tab connects the button to its own toggle, since
        # connecting and disconnecting reach the recording too.
        self.connect_button = QPushButton(tr("Connect"))
        self.connect_button.setCheckable(True)

        self.led = QLabel()
        self.led.setFixedSize(16, 16)
        self.led.setToolTip(tr("Device communication status"))

        # LED idle timer
        self._led_idle_timer = QTimer(self)
        self._led_idle_timer.setSingleShot(True)
        self._led_idle_timer.setInterval(LED_IDLE_MS)
        self._led_idle_timer.timeout.connect(lambda: self._set_led("idle"))
        self._set_led("off")

        # Watchdog: fires every 1 s during recording and checks that the
        # worker keeps receiving samples. If no data arrives within 3 s, it
        # forces a disconnection to unblock a read() hung by a lost BT link.
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.setInterval(1000)
        self._watchdog_timer.timeout.connect(self._check_watchdog)
        self._watchdog_umbral_s = 3.0

        # The watchdog only watches once samples flow. Before the first one
        # the board is being reached, and that can hang with nothing to say
        # so: this one waits for the first block and gives up after
        # CONEXION_MAX_S (see _conexion_sin_datos).
        self._conexion_timer = QTimer(self)
        self._conexion_timer.setSingleShot(True)
        self._conexion_timer.setInterval(int(CONEXION_MAX_S * 1000))
        self._conexion_timer.timeout.connect(self._conexion_sin_datos)
        self._aviso_conexion: QMessageBox | None = None
        #: The last recording ended before the board sent anything.
        self._sin_respuesta = False
        #: The real BITalino sent data in the last recording: the next one
        #: needs it switched off and on (see idle_status).
        self._placa_reiniciar = False

    # ------------------------------------------------------------------
    # What the tab reads
    # ------------------------------------------------------------------

    def device_index(self) -> int:
        """0 for the BITalino, 1 for the Arduino."""
        return self._combo_device_type.currentIndex()

    def address(self) -> str:
        """The BITalino's address as written in the field."""
        return self._edit_mac.text().strip()

    def serial_port(self) -> str:
        """The Arduino's serial port as chosen."""
        return self._combo_port.currentText().strip()

    def is_connected(self) -> bool:
        """The Connect button is down."""
        return self.connect_button.isChecked()

    def idle_status(self) -> tuple[str, str]:
        """What the status line says when nothing is being recorded, and its
        tooltip.

        Derived from the Connect button, not written by whoever stopped the
        recording: a disconnection in the middle of one used to end, a second
        later, with «connected (ready to record)» under an unticked button.
        """
        if self.connect_button.isChecked():
            if self._sin_respuesta:
                return tr("Status: the board did not answer"), ""
            if self._placa_reiniciar:
                # 3.8.0, from ecgteach 0.4.0 (bench of 5 Oct 2026): after a
                # recording with the real BITalino, the next one did not
                # connect (Windows errors 1168 and 121) until the board was
                # switched off and on. Not investigated, by Ángel's decision:
                # said, where the operator looks — short on screen, whole in
                # the tooltip.
                return (
                    tr("Status: switch the board off and on, wait about 20 s and press Start"),
                    tr(
                        "Status: for the next recording, switch the BITalino board off and on, "
                        "wait about 20 s and press «Start recording»"),
                )
            return tr("Status: connected (ready to record)"), ""
        return tr("Status: disconnected"), ""

    # ------------------------------------------------------------------
    # The device
    # ------------------------------------------------------------------

    def _default_address(self) -> str:
        """The station's address from bitalino.txt; the lab's MAC without it."""
        if self._station_address is not None:
            return self._station_address
        return DEFAULT_BITALINO_ADDR

    def _log_station_address(self) -> None:
        self.logged.emit(
            tr("BITalino address taken from {file}: {addr}").format(
                file=ADDRESS_FILE, addr=self._station_address or tr("autodetect")
            )
        )

    @Slot()
    def _reset_mac(self) -> None:
        """Restore the default BITalino address: the station's, or the lab's MAC."""
        addr = self._default_address()
        self._edit_mac.setText(addr)
        self._settings.setValue("adquisicion/port", addr)

    @Slot(int)
    def _on_device_type_changed(self, index: int) -> None:
        """Show the COM-port field (BITalino) or the COM-port selector (Arduino)."""
        self._widget_mac.setVisible(index == 0)
        self._widget_arduino.setVisible(index == 1)
        self.device_type_changed.emit(index)

    @Slot()
    def _refresh_ports(self) -> None:
        """Repopulate the COM-port combo with those available on the system."""
        ports = device_class(BACKEND_ARDUINO).list_ports()
        saved_port = self._settings.value("adquisicion/port", "")
        self._combo_port.blockSignals(True)
        self._combo_port.clear()
        for p in ports:
            self._combo_port.addItem(p)
        if saved_port in ports:
            self._combo_port.setCurrentText(saved_port)
        elif ports:
            self._combo_port.setCurrentIndex(0)
        self._combo_port.blockSignals(False)

    def select_bitalino(self, address: str) -> None:
        """The BITalino, at ``address``, as if chosen and typed."""
        self._combo_device_type.setCurrentIndex(0)
        self._edit_mac.setText(address)

    def set_practical(self, single_muscle: bool) -> None:
        """Offer the device choice only where the practical allows both."""
        # Which device, and where it is plugged in, is offered in every
        # practical. It used to be a fine control, on the reasoning that a
        # laboratory is set up once — but the practicals are where the app is
        # actually used, and sending someone to a different mode to change a
        # COM port is sending them away from the exercise to fix the tool.
        port = str(self._settings.value("adquisicion/port", "") or "").strip()
        # A station with bitalino.txt is set up, whatever the settings say.
        first_setup = not port and self._station_address is None
        self.setVisible(True)
        self._lbl_first_setup.setVisible(first_setup)
        # Only the single-muscle practical can be done with the Arduino +
        # MyoWare board; the other two need the BITalino (two channels, the
        # accelerometer). So the device choice is offered there and nowhere
        # else, and a practical that needs the BITalino gets it — the port
        # or address stays editable, since that differs from board to board.
        self._combo_device_type.setVisible(single_muscle)
        self._lbl_device_fixed.setVisible(not single_muscle)
        if not single_muscle and self._combo_device_type.currentIndex() != 0:
            self._combo_device_type.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Connecting and disconnecting
    # ------------------------------------------------------------------

    def connect_device(self) -> str | None:
        """Take the device as configured, and lock its controls.

        Returns what was connected to, for the log; ``None`` if there was
        nothing to connect to (an Arduino with no port chosen), with the
        button let up again.
        """
        device_idx = self._combo_device_type.currentIndex()
        if device_idx == 0:  # BITalino
            # Empty is allowed: BitalinoDevice autodetects the device. A MAC or
            # an explicit COM port are also accepted and resolved on open().
            desc = self._edit_mac.text().strip()
            self._settings.setValue("adquisicion/port", desc)
        else:  # Arduino
            desc = self._combo_port.currentText().strip()
            if not desc:
                self.warned.emit(
                    tr("Select a COM port for the Arduino before connecting.")
                )
                self.connect_button.setChecked(False)
                return None
            self._settings.setValue("adquisicion/port", desc)
        self._settings.setValue("adquisicion/device_type", device_idx)

        self.connect_button.setText(tr("Disconnect"))
        self._combo_device_type.setEnabled(False)
        self._widget_mac.setEnabled(False)
        self._widget_arduino.setEnabled(False)
        self._placa_reiniciar = False
        self._set_led("idle")
        return desc

    def disconnect_device(self) -> None:
        """Let the button up and the controls free, and forget the last link."""
        self.connect_button.setText(tr("Connect"))
        self.connect_button.setChecked(False)
        self._combo_device_type.setEnabled(True)
        self._widget_mac.setEnabled(True)
        self._widget_arduino.setEnabled(True)
        self._sin_respuesta = False
        self._placa_reiniciar = False
        self._set_led("off")
        self._led_idle_timer.stop()

    # ------------------------------------------------------------------
    # The link while a recording runs
    # ------------------------------------------------------------------

    def recording_requested(self) -> None:
        """A new recording was asked for: the advice to switch the board off
        and on was for this one, and has been heard."""
        self._placa_reiniciar = False

    def recording_started(self) -> None:
        """The recording's thread is running: wait for the board's first block."""
        self.connect_button.setEnabled(False)
        self._sin_respuesta = False
        self._conexion_timer.start()

    def block_arrived(self) -> bool:
        """A block of samples arrived; ``True`` if it is the recording's first.

        The first block says the board answered. From it the watchdog
        watches — not before, so it does not fire during device.open(),
        which can take up to 3 s on Arduino.
        """
        primero = self._conexion_timer.isActive()
        if primero:
            self._conexion_timer.stop()
            # The real BITalino answered: the next recording needs it switched
            # off and on. Not the simulated board, and not the Arduino (USB
            # cable, no Bluetooth link; the bench saw it only on the BITalino).
            self._placa_reiniciar = (
                self._combo_device_type.currentIndex() == 0
                and not is_simulated_address(self._edit_mac.text().strip())
            )
        if not self._watchdog_timer.isActive():
            self._watchdog_timer.start()
        return primero

    def traffic(self) -> None:
        """Green LED: there is traffic. The timer will set it back to yellow if
        no new block arrives within LED_IDLE_MS ms."""
        self._set_led("ok")
        self._led_idle_timer.start()

    def stop_watchdog(self) -> None:
        self._watchdog_timer.stop()

    def mark_if_no_answer(self) -> None:
        """A recording that ends before its first block: the board never
        answered, and the status must not come back saying «connected»."""
        if self._conexion_timer.isActive():
            self._conexion_timer.stop()
            # A file that could not be created is not a board that did not
            # answer: the board answered, and the next recording can start
            # (3.8.0, from ecgteach 9a33ef3).
            worker = self._worker()
            if worker is None or not worker.placa_respondio():
                self._sin_respuesta = True
                self._set_led("off")

    def recording_finished(self) -> None:
        """The recording is over: the device can be disconnected again."""
        self.connect_button.setEnabled(True)

    def stop(self) -> None:
        """Stop the watch on the link, for the window that is closing."""
        self._watchdog_timer.stop()
        self._conexion_timer.stop()

    # ------------------------------------------------------------------
    # Communication-status LED
    # ------------------------------------------------------------------

    def _set_led(self, state: str) -> None:
        """
        Set the communication LED.
        state: 'off'  → red    (disconnected)
               'idle' → yellow (connected, no traffic)
               'ok'   → green  (receiving data)
        """
        colors = {
            "off":  ("#C0392B", "#7B241C"),   # red
            "idle": ("#F1C40F", "#B7950B"),   # yellow
            "ok":   ("#27AE60", "#196F3D"),   # green
        }
        fill, border = colors.get(state, colors["off"])
        self.led.setStyleSheet(
            f"background-color: {fill};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
        )

    # ------------------------------------------------------------------
    # BITalino connection watchdog
    # ------------------------------------------------------------------

    @Slot()
    def _conexion_sin_datos(self) -> None:
        """No block from the board within CONEXION_MAX_S: stop, and say so.

        On the bench the connection hung without a word — the log stopped at
        «Connecting to BITalino…», the status said «recording…» and then,
        once stopped, «connected (ready to record)», and no file was
        written. A student believes the status line. So the recording stops
        here, the status says the board did not answer, and a box says what
        to do and offers to try again. The thread is asked to stop and to
        release the port; if it is stuck where nothing can reach it, it
        closes the board and records nothing once it comes back.
        """
        worker = self._worker()
        if worker is None or not worker.isRunning() or worker.is_streaming():
            return
        worker.stop_forced()
        self._sin_respuesta = True
        self._set_led("off")
        self.no_answer.emit()      # the tab stops it; the status says the board did not answer
        texto = tr(
            "No data arrived from the board in {s:.0f} s, so nothing is being "
            "recorded. Check that the BITalino is switched on, switch it off "
            "and on again, and try again. If it happens again, close emgteach "
            "and open it again."
        ).format(s=CONEXION_MAX_S)
        self.warned.emit(texto)
        caja = QMessageBox(
            QMessageBox.Icon.Warning, tr("The board did not answer"), texto,
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Close,
            self)
        caja.setDefaultButton(QMessageBox.StandardButton.Retry)
        caja.finished.connect(self._tras_aviso_conexion)
        self._aviso_conexion = caja
        caja.open()

    def _tras_aviso_conexion(self, respuesta: int) -> None:
        """«Retry» asks the tab to start the recording again, as the button would."""
        self._aviso_conexion = None
        if respuesta == QMessageBox.StandardButton.Retry:
            self.retry_requested.emit()

    @Slot()
    def _check_watchdog(self) -> None:
        """Check every 1 s that the worker keeps receiving samples."""
        worker = self._worker()
        if worker is None or not worker.isRunning():
            return
        # Only monitor once the worker is in its reading phase
        if not worker.is_streaming():
            return
        silencio = worker.time_since_last_sample()
        if silencio > self._watchdog_umbral_s:
            if silencio == float("inf") or silencio > 999:
                msg = tr("No data from the device — connection not established.")
            else:
                msg = tr(
                    "No data from the device for {s:.1f} s — forcing disconnection."
                ).format(s=silencio)
            self.warned.emit(msg)
            self._watchdog_timer.stop()
            worker.stop_forced()
            worker.wait(2000)
            self.link_lost.emit()
