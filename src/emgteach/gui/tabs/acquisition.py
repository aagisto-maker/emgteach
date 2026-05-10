"""
AcquisitionTab — pestaña 1: adquisición EMG en tiempo real con BITalino.

Controles:
  - Dirección MAC del BITalino (persistida con QSettings)
  - Carpeta de destino para el EDF (persistida con QSettings)
  - Botón Conectar / Desconectar
  - Botón Iniciar / Detener grabación

Visualización (pyqtgraph):
  - Señal EMG en bruto
  - Señal filtrada (notch + paso-banda)
  - Envolvente

Controles de escala:
  - Escala vertical: botones ▲▼ por gráfica (factor ×1.5, límites 0.01×–100× inicial)
  - Escala temporal: desplegable de factores + botones ◀▶ (ventana deslizante sobre
    el buffer circular; permite ver desde 0.5 s hasta los MAX_POINTS/fs segundos)

La pestaña nunca bloquea la UI: toda la adquisición corre en AcquisitionWorker (QThread).
"""

from __future__ import annotations

from collections import deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSettings, QTimer, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from emgteach.devices import ArduinoDevice, BitalinoDevice
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.workers import AcquisitionWorker

# Número de muestras en el buffer circular (= 30 s a 1000 Hz)
# La ventana visible puede ser menor gracias al control de zoom temporal.
MAX_POINTS = 30_000
FS = 1000  # Hz nominal del BITalino

# MAC por defecto del BITalino del laboratorio UCM (editable en el campo).
DEFAULT_MAC = "98:D3:91:FE:44:E4"

# Intervalo (ms) tras el último dato recibido después del cual se considera
# que no hay tráfico (el LED pasa de verde a amarillo).
LED_IDLE_MS = 500

# Factores de zoom temporal disponibles (denominador: cuántas veces cabe la ventana
# visible en el buffer total). Factor ×1 → ver todo el buffer.
_ZOOM_FACTORS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]

# Estilo compartido para botones de escala pequeños
_BTN_ST = (
    "QToolButton { font-size: 9px; padding: 0px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
_COMBO_ST = (
    "QComboBox { font-size: 9px; padding: 1px 2px; min-width: 54px; max-width: 66px; }"
)


class AcquisitionTab(QWidget):
    def __init__(self, logger: LoggerWidget, settings: QSettings, parent=None):
        super().__init__(parent)
        self._logger = logger
        self._settings = settings
        self._worker: AcquisitionWorker | None = None

        # Buffers circulares para las tres señales (30 s a 1000 Hz)
        self._buf_raw  = deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
        self._buf_filt = deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
        self._buf_env  = deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
        self._new_data = False  # flag: hay datos nuevos que pintar

        self._marcas_recientes: list[str] = []

        # ---- Estado de escala vertical (por gráfica: 0=raw, 1=filt, 2=env) ----
        # Rangos Y iniciales fijos (se restauran en _reset_y_scales)
        self._y_ranges_init: list[tuple[float, float]] = [
            (-3.3, 3.3),   # raw
            (-0.8, 0.8),   # filtrada
            (0.0,  0.5),   # envolvente
        ]
        self._y_accum: list[float] = [1.0, 1.0, 1.0]  # factor acumulado por gráfica

        # ---- Estado de escala temporal ----
        # Número de muestras visibles en cada gráfica. Empieza mostrando 5 s.
        self._n_visible: int = 5 * FS   # muestras visibles (ajustable con zoom)

        # Timer de render independiente — desacopla recepción de datos y redibujado.
        # 33 ms ≈ 30 FPS máximo, independientemente de la velocidad del worker.
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(33)
        self._render_timer.timeout.connect(self._refresh_plots)

        # Watchdog: dispara cada 1 s durante la grabación y verifica que el
        # worker siga recibiendo muestras. Si no llegan datos en 3 s, fuerza
        # la desconexión para desbloquear un read() colgado por pérdida de BT.
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.setInterval(1000)
        self._watchdog_timer.timeout.connect(self._check_watchdog)
        self._watchdog_umbral_s = 3.0

        # Logger local: instancia propia para mostrar en esta pestaña.
        # Los mensajes se duplican al logger compartido (self._logger) para
        # que tab_analisis también los reciba si los necesita.
        self._local_log = LoggerWidget()

        self._build_ui()

    # ------------------------------------------------------------------
    # Helpers de log — escriben en el logger local Y en el compartido
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        self._local_log.append_log(msg)
        self._logger.append_log(msg)

    def _err(self, msg: str) -> None:
        self._local_log.append_error(msg)
        self._logger.append_error(msg)

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ── Panel de configuración — una sola fila ──────────────────────
        grp_config = QGroupBox("Configuración del dispositivo")
        cfg_row = QHBoxLayout(grp_config)
        cfg_row.setContentsMargins(6, 4, 6, 4)
        cfg_row.setSpacing(6)

        # Combo tipo de dispositivo (stretch 25)
        self._combo_device_type = QComboBox()
        self._combo_device_type.addItem("BITalino (Bluetooth)")
        self._combo_device_type.addItem("Arduino + MyoWare 2.0 (USB)")
        saved_type = int(self._settings.value("adquisicion/device_type", 0))
        self._combo_device_type.setCurrentIndex(saved_type)
        self._combo_device_type.currentIndexChanged.connect(self._on_device_type_changed)
        cfg_row.addWidget(self._combo_device_type, stretch=25)

        # Zona central condicional: MAC (BITalino) o COM (Arduino) — stretch 30
        # Envuelta en un QWidget para poder cambiar contenido sin rehacer el layout
        self._widget_mac = QWidget()
        mac_inner = QHBoxLayout(self._widget_mac)
        mac_inner.setContentsMargins(0, 0, 0, 0)
        mac_inner.setSpacing(4)
        self._edit_mac = QLineEdit()
        self._edit_mac.setPlaceholderText("98:D3:91:FE:44:E4")
        self._edit_mac.setText(self._settings.value("adquisicion/mac", DEFAULT_MAC))
        mac_inner.addWidget(self._edit_mac)
        btn_reset_mac = QPushButton("Por defecto")
        btn_reset_mac.setFixedWidth(84)
        btn_reset_mac.setToolTip(f"Restaurar MAC por defecto ({DEFAULT_MAC})")
        btn_reset_mac.clicked.connect(self._reset_mac)
        mac_inner.addWidget(btn_reset_mac)

        self._widget_arduino = QWidget()
        ard_inner = QHBoxLayout(self._widget_arduino)
        ard_inner.setContentsMargins(0, 0, 0, 0)
        ard_inner.setSpacing(4)
        self._combo_port = QComboBox()
        ard_inner.addWidget(self._combo_port)
        btn_refresh_ports = QPushButton("Refrescar")
        btn_refresh_ports.setFixedWidth(84)
        btn_refresh_ports.setToolTip("Refrescar lista de puertos serie disponibles")
        btn_refresh_ports.clicked.connect(self._refresh_ports)
        ard_inner.addWidget(btn_refresh_ports)

        # Contenedor que alterna entre _widget_mac y _widget_arduino
        self._stack_conn = QWidget()
        stack_layout = QHBoxLayout(self._stack_conn)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.addWidget(self._widget_mac)
        stack_layout.addWidget(self._widget_arduino)
        cfg_row.addWidget(self._stack_conn, stretch=30)

        # Campo carpeta destino (stretch 40)
        self._edit_dir = QLineEdit()
        self._edit_dir.setPlaceholderText("Carpeta de destino EDF")
        self._edit_dir.setText(self._settings.value("adquisicion/save_dir", "."))
        cfg_row.addWidget(self._edit_dir, stretch=40)

        # Botón Explorar (ancho fijo)
        btn_dir = QPushButton("Explorar…")
        btn_dir.setFixedWidth(84)
        btn_dir.clicked.connect(self._seleccionar_directorio)
        cfg_row.addWidget(btn_dir)

        # Visibilidad inicial
        self._widget_mac.setVisible(saved_type == 0)
        self._widget_arduino.setVisible(saved_type == 1)
        self._refresh_ports()

        root.addWidget(grp_config)

        # ── Fila tripartita: Control | Marcadores | Log ─────────────────
        row_triptych = QHBoxLayout()
        row_triptych.setSpacing(4)

        # — Control de adquisición (stretch 2) —
        grp_control = QGroupBox("Control de adquisición")
        ctrl_layout = QVBoxLayout(grp_control)
        ctrl_layout.setSpacing(4)

        row_btns = QHBoxLayout()
        self._btn_conectar = QPushButton("Conectar")
        self._btn_conectar.setCheckable(True)
        self._btn_conectar.clicked.connect(self._toggle_conexion)
        row_btns.addWidget(self._btn_conectar)

        self._btn_grabar = QPushButton("Iniciar grabación")
        self._btn_grabar.setCheckable(True)
        self._btn_grabar.setEnabled(False)
        self._btn_grabar.clicked.connect(self._toggle_grabacion)
        row_btns.addWidget(self._btn_grabar)
        ctrl_layout.addLayout(row_btns)

        row_led = QHBoxLayout()
        self._led = QLabel()
        self._led.setFixedSize(16, 16)
        self._led.setToolTip("Estado de comunicación con el dispositivo")
        row_led.addWidget(self._led)
        self._lbl_estado = QLabel("Estado: desconectado")
        row_led.addWidget(self._lbl_estado)
        row_led.addStretch()
        ctrl_layout.addLayout(row_led)

        row_triptych.addWidget(grp_control, stretch=2)

        # Timer LED idle
        self._led_idle_timer = QTimer(self)
        self._led_idle_timer.setSingleShot(True)
        self._led_idle_timer.setInterval(LED_IDLE_MS)
        self._led_idle_timer.timeout.connect(lambda: self._set_led("idle"))
        self._set_led("off")

        # — Marcadores de eventos (stretch 3) —
        grp_markers = QGroupBox("Marcadores de eventos")
        markers_layout = QVBoxLayout(grp_markers)
        markers_layout.setSpacing(4)

        row_m = QHBoxLayout()
        self._combo_etiqueta = QComboBox()
        for etiq in ["Inicio contracción", "Fin contracción", "Fatiga", "Reposo", "Otro…"]:
            self._combo_etiqueta.addItem(etiq)
        self._combo_etiqueta.setEnabled(False)
        row_m.addWidget(self._combo_etiqueta)

        self._btn_marcar = QPushButton("MARCAR")
        self._btn_marcar.setMinimumHeight(34)
        self._btn_marcar.setStyleSheet("font-size: 12px; font-weight: bold;")
        self._btn_marcar.setEnabled(False)
        self._btn_marcar.clicked.connect(self._on_marcar)
        row_m.addWidget(self._btn_marcar)
        markers_layout.addLayout(row_m)

        self._lbl_marcas_recientes = QLabel("(sin marcas en esta sesión)")
        self._lbl_marcas_recientes.setStyleSheet("font-size: 8px; color: #555555;")
        self._lbl_marcas_recientes.setWordWrap(True)
        markers_layout.addWidget(self._lbl_marcas_recientes)

        row_triptych.addWidget(grp_markers, stretch=3)

        # — Registro de eventos (stretch 5) —
        grp_log = QGroupBox("Registro de eventos")
        log_layout = QVBoxLayout(grp_log)
        log_layout.setContentsMargins(4, 4, 4, 4)
        log_layout.addWidget(self._local_log)
        row_triptych.addWidget(grp_log, stretch=5)

        root.addLayout(row_triptych)

        # Atajo de teclado M
        self._shortcut_m = QShortcut(QKeySequence("M"), self)
        self._shortcut_m.setEnabled(False)
        self._shortcut_m.activated.connect(self._on_marcar_rapido)

        # ── Gráficas + controles de escala ──────────────────────────────
        grp_plots = QGroupBox("Señal EMG en tiempo real")
        plots_root = QVBoxLayout(grp_plots)

        # -- Barra de escala temporal (arriba de las gráficas) -----------
        row_tiempo = QHBoxLayout()
        row_tiempo.addWidget(QLabel("Ventana temporal:"))

        self._btn_tiempo_ampliar = QToolButton()
        self._btn_tiempo_ampliar.setText("◀▶")
        self._btn_tiempo_ampliar.setToolTip("Ampliar ventana (ver más tiempo)")
        self._btn_tiempo_ampliar.setStyleSheet(_BTN_ST)
        self._btn_tiempo_ampliar.setFixedSize(28, 22)
        self._btn_tiempo_ampliar.clicked.connect(self._on_tiempo_ampliar)
        row_tiempo.addWidget(self._btn_tiempo_ampliar)

        self._combo_zoom = QComboBox()
        self._combo_zoom.setStyleSheet(_COMBO_ST)
        self._combo_zoom.setFixedSize(66, 22)
        for f in _ZOOM_FACTORS:
            self._combo_zoom.addItem(f"×{f}")
        self._combo_zoom.setCurrentIndex(0)   # ×1 = todo el buffer
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)
        row_tiempo.addWidget(self._combo_zoom)

        self._btn_tiempo_reducir = QToolButton()
        self._btn_tiempo_reducir.setText("▶◀")
        self._btn_tiempo_reducir.setToolTip("Reducir ventana (ver menos tiempo, más detalle)")
        self._btn_tiempo_reducir.setStyleSheet(_BTN_ST)
        self._btn_tiempo_reducir.setFixedSize(28, 22)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)
        row_tiempo.addWidget(self._btn_tiempo_reducir)

        self._lbl_ventana_info = QLabel(f"{MAX_POINTS // FS} s visibles")
        self._lbl_ventana_info.setStyleSheet("font-size: 8px; color: #444;")
        row_tiempo.addWidget(self._lbl_ventana_info)

        row_tiempo.addStretch()

        btn_reset_escala = QPushButton("Reset escalas")
        btn_reset_escala.setFixedHeight(22)
        btn_reset_escala.setStyleSheet("font-size: 9px;")
        btn_reset_escala.setToolTip("Restaurar rangos Y y ventana temporal a valores iniciales")
        btn_reset_escala.clicked.connect(self._reset_all_scales)
        row_tiempo.addWidget(btn_reset_escala)

        plots_root.addLayout(row_tiempo)

        # -- Área de gráficas con sidebar de escala vertical -------------
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")

        # Sidebar vertical (▲▼ por gráfica)
        self._sidebar = QWidget()
        self._sidebar.setFixedWidth(38)
        sidebar_vbox = QVBoxLayout(self._sidebar)
        sidebar_vbox.setContentsMargins(2, 4, 2, 4)
        sidebar_vbox.setSpacing(0)

        # Contenedor gráficas
        plots_col = QWidget()
        plots_col_vbox = QVBoxLayout(plots_col)
        plots_col_vbox.setContentsMargins(0, 0, 0, 0)
        plots_col_vbox.setSpacing(4)

        canvas_hbox = QHBoxLayout()
        canvas_hbox.setContentsMargins(0, 0, 0, 0)
        canvas_hbox.setSpacing(2)
        canvas_hbox.addWidget(self._sidebar)
        canvas_hbox.addWidget(plots_col)
        plots_root.addLayout(canvas_hbox)

        # Señal bruta
        self._plot_raw = pg.PlotWidget(title="Señal EMG en bruto (mV)")
        self._plot_raw.setYRange(*self._y_ranges_init[0])
        self._plot_raw.setLabel("left", "mV")
        self._plot_raw.showGrid(x=True, y=True, alpha=0.3)
        self._curve_raw = self._plot_raw.plot(
            pen=pg.mkPen(color=(120, 120, 120), width=1),
        )
        plots_col_vbox.addWidget(self._plot_raw)

        # Señal filtrada
        self._plot_filt = pg.PlotWidget(
            title="EMG filtrado (notch 50 Hz + paso-banda 20-450 Hz)"
        )
        self._plot_filt.setYRange(*self._y_ranges_init[1])
        self._plot_filt.setLabel("left", "mV")
        self._plot_filt.showGrid(x=True, y=True, alpha=0.3)
        self._curve_filt = self._plot_filt.plot(
            pen=pg.mkPen(color=(65, 105, 225), width=1),
        )
        plots_col_vbox.addWidget(self._plot_filt)

        # Envolvente
        self._plot_env = pg.PlotWidget(
            title="Envolvente (filtro paso-bajo 5 Hz, causal con estado continuo)"
        )
        self._plot_env.setYRange(*self._y_ranges_init[2])
        self._plot_env.setLabel("left", "mV")
        self._plot_env.showGrid(x=True, y=True, alpha=0.3)
        self._curve_env = self._plot_env.plot(
            pen=pg.mkPen(color=(220, 120, 0), width=2),
        )
        plots_col_vbox.addWidget(self._plot_env)

        # Construir botones ▲▼ en el sidebar (uno por gráfica)
        self._plots_widgets = [self._plot_raw, self._plot_filt, self._plot_env]
        labels = ["B", "F", "E"]   # Bruta / Filtrada / Envolvente
        for i, (pw, lbl_txt) in enumerate(zip(self._plots_widgets, labels)):
            slot = QWidget()
            slot_vbox = QVBoxLayout(slot)
            slot_vbox.setContentsMargins(0, 0, 0, 0)
            slot_vbox.setSpacing(1)

            btn_up = QToolButton()
            btn_up.setText("▲")
            btn_up.setFixedSize(32, 18)
            btn_up.setStyleSheet(_BTN_ST)
            btn_up.setToolTip(f"Zoom-in vertical — {lbl_txt}")
            btn_up.clicked.connect(
                lambda checked=False, idx=i: self._y_zoom(idx, zoom_in=True)
            )

            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet("font-size: 7px; color: #666;")
            from PySide6.QtCore import Qt as _Qt
            lbl.setAlignment(_Qt.AlignmentFlag.AlignCenter)

            btn_dn = QToolButton()
            btn_dn.setText("▼")
            btn_dn.setFixedSize(32, 18)
            btn_dn.setStyleSheet(_BTN_ST)
            btn_dn.setToolTip(f"Zoom-out vertical — {lbl_txt}")
            btn_dn.clicked.connect(
                lambda checked=False, idx=i: self._y_zoom(idx, zoom_in=False)
            )

            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up,  alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl,     alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn,  alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addStretch()

            sidebar_vbox.addWidget(slot, stretch=1)

        root.addWidget(grp_plots, stretch=1)

        # Actualizar combo para que refleje n_visible inicial
        self._sync_combo_zoom()

    # ------------------------------------------------------------------
    # Slots de control de dispositivo
    # ------------------------------------------------------------------

    @Slot()
    def _seleccionar_directorio(self) -> None:
        directorio = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de destino",
            self._edit_dir.text() or ".",
        )
        if directorio:
            self._edit_dir.setText(directorio)
            self._settings.setValue("adquisicion/save_dir", directorio)

    @Slot()
    def _reset_mac(self) -> None:
        """Restaura la MAC por defecto del laboratorio."""
        self._edit_mac.setText(DEFAULT_MAC)
        self._settings.setValue("adquisicion/mac", DEFAULT_MAC)

    @Slot(int)
    def _on_device_type_changed(self, index: int) -> None:
        """Muestra el campo MAC (BITalino) o el selector de puerto COM (Arduino)."""
        self._widget_mac.setVisible(index == 0)
        self._widget_arduino.setVisible(index == 1)

    @Slot()
    def _refresh_ports(self) -> None:
        """Repopula el combo de puertos COM con los disponibles en el sistema."""
        ports = ArduinoDevice.list_ports()
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

    @Slot()
    def _toggle_conexion(self) -> None:
        if self._btn_conectar.isChecked():
            self._conectar()
        else:
            self._desconectar()

    def _conectar(self) -> None:
        device_idx = self._combo_device_type.currentIndex()
        if device_idx == 0:  # BITalino
            desc = self._edit_mac.text().strip()
            if not desc:
                self._err(
                    "Introduce la dirección MAC del BITalino antes de conectar."
                )
                self._btn_conectar.setChecked(False)
                return
            self._settings.setValue("adquisicion/mac", desc)
        else:  # Arduino
            desc = self._combo_port.currentText().strip()
            if not desc:
                self._err(
                    "Selecciona un puerto COM para el Arduino antes de conectar."
                )
                self._btn_conectar.setChecked(False)
                return
            self._settings.setValue("adquisicion/port", desc)
        self._settings.setValue("adquisicion/device_type", device_idx)

        self._btn_conectar.setText("Desconectar")
        self._btn_grabar.setEnabled(True)
        self._combo_device_type.setEnabled(False)
        self._widget_mac.setEnabled(False)
        self._widget_arduino.setEnabled(False)
        self._edit_dir.setEnabled(False)
        self._lbl_estado.setText("Estado: conectado (listo para grabar)")
        self._set_led("idle")
        self._log(f"Dispositivo configurado: {desc}. Pulsa 'Iniciar grabación'.")

    def _desconectar(self) -> None:
        self._watchdog_timer.stop()
        if self._worker and self._worker.isRunning():
            self._detener_grabacion()
        self._btn_conectar.setText("Conectar")
        self._btn_conectar.setChecked(False)
        self._btn_grabar.setEnabled(False)
        self._btn_grabar.setChecked(False)
        self._btn_grabar.setText("Iniciar grabación")
        self._combo_device_type.setEnabled(True)
        self._widget_mac.setEnabled(True)
        self._widget_arduino.setEnabled(True)
        self._edit_dir.setEnabled(True)
        self._lbl_estado.setText("Estado: desconectado")
        self._set_led("off")
        self._led_idle_timer.stop()
        self._log("Dispositivo desconectado.")

    @Slot()
    def _toggle_grabacion(self) -> None:
        if self._btn_grabar.isChecked():
            self._iniciar_grabacion()
        else:
            self._detener_grabacion()

    def _iniciar_grabacion(self) -> None:
        save_dir = self._edit_dir.text().strip() or "."

        for buf in (self._buf_raw, self._buf_filt, self._buf_env):
            buf.clear()
            buf.extend([0.0] * MAX_POINTS)

        self._marcas_recientes.clear()
        self._lbl_marcas_recientes.setText("(sin marcas en esta sesión)")
        self._reset_y_scales()

        if self._combo_device_type.currentIndex() == 0:
            device = BitalinoDevice(mac=self._edit_mac.text().strip(), fs=FS)
        else:
            device = ArduinoDevice(
                port=self._combo_port.currentText().strip(), fs=FS
            )
        self._worker = AcquisitionWorker(device=device, save_dir=save_dir)
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.log.connect(self._log)
        self._worker.error.connect(self._on_error)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.marker_added.connect(self._on_marker_added)
        self._worker.start()
        self._render_timer.start()
        # El watchdog arranca en _on_data_ready tras la primera muestra leída;
        # no aquí, para no disparar durante device.open() (puede tardar ~3 s).

        self._btn_grabar.setText("Detener grabación")
        self._btn_conectar.setEnabled(False)
        self._lbl_estado.setText("Estado: grabando…")
        self._combo_etiqueta.setEnabled(True)
        self._btn_marcar.setEnabled(True)
        self._shortcut_m.setEnabled(True)
        self._log("Pulsa M para marcar rápidamente con la etiqueta seleccionada.")

    def _detener_grabacion(self) -> None:
        self._watchdog_timer.stop()
        self._render_timer.stop()
        if self._worker:
            self._worker.stop()
        self._btn_grabar.setText("Iniciar grabación")
        self._btn_grabar.setChecked(False)
        self._btn_conectar.setEnabled(True)
        self._lbl_estado.setText("Estado: conectado (listo para grabar)")
        self._combo_etiqueta.setEnabled(False)
        self._btn_marcar.setEnabled(False)
        self._shortcut_m.setEnabled(False)

    # ------------------------------------------------------------------
    # Slots del worker
    # ------------------------------------------------------------------

    @Slot(dict)
    def _on_data_ready(self, data: dict) -> None:
        # Arranca el watchdog en la primera muestra recibida (no antes, para no
        # disparar durante device.open() que puede tardar hasta 3 s en Arduino).
        if not self._watchdog_timer.isActive():
            self._watchdog_timer.start()
        self._buf_raw.extend(data["raw_mv"].tolist())
        self._buf_filt.extend(data["filtered"].tolist())
        self._buf_env.extend(data["envelope"].tolist())
        self._new_data = True
        # LED verde: hay tráfico. El timer lo devolverá a amarillo si no llega
        # ningún bloque nuevo en LED_IDLE_MS ms.
        self._set_led("ok")
        self._led_idle_timer.start()

    def _refresh_plots(self) -> None:
        """Llamado cada 33 ms por _render_timer. Pinta solo si hay datos nuevos."""
        if not self._new_data:
            return
        self._new_data = False

        n = min(self._n_visible, MAX_POINTS)
        # Extraer las últimas n muestras del buffer circular
        arr_raw  = np.array(list(self._buf_raw))[-n:]
        arr_filt = np.array(list(self._buf_filt))[-n:]
        arr_env  = np.array(list(self._buf_env))[-n:]

        # Eje X en segundos relativos al inicio de la ventana visible
        t = np.arange(len(arr_raw)) / FS

        self._curve_raw.setData(t, arr_raw)
        self._curve_filt.setData(t, arr_filt)
        self._curve_env.setData(t, arr_env)

    # ------------------------------------------------------------------
    # Marcadores
    # ------------------------------------------------------------------

    @Slot()
    def _on_marcar(self) -> None:
        etiqueta = self._combo_etiqueta.currentText()
        if etiqueta == "Otro…":
            text, ok = QInputDialog.getText(
                self, "Marcador personalizado",
                "Descripción (máx. 60 caracteres):",
            )
            if not ok or not text.strip():
                return
            etiqueta = text.strip()[:60].replace("\n", " ")
        if self._worker and self._worker.isRunning():
            self._worker.add_marker(etiqueta)

    @Slot()
    def _on_marcar_rapido(self) -> None:
        if not self._worker or not self._worker.isRunning():
            return
        etiqueta = self._combo_etiqueta.currentText()
        if etiqueta == "Otro…":
            etiqueta = "Otro"
        self._worker.add_marker(etiqueta)

    @Slot(float, str)
    def _on_marker_added(self, tiempo: float, etiqueta: str) -> None:
        self._log(f"Marca añadida: t={tiempo:.1f} s — {etiqueta}")
        self._marcas_recientes.append(f"t={tiempo:.1f} s: {etiqueta}")
        self._lbl_marcas_recientes.setText("\n".join(self._marcas_recientes[-5:]))

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._err(msg)
        self._restaurar_controles()

    @Slot(str)
    def _on_finished(self, edf_path: str) -> None:
        self._restaurar_controles()
        if edf_path:
            self._log(f"Grabación finalizada. Archivo: {edf_path}")

    def _restaurar_controles(self) -> None:
        self._btn_grabar.setChecked(False)
        self._btn_grabar.setText("Iniciar grabación")
        self._btn_conectar.setEnabled(True)
        self._lbl_estado.setText("Estado: conectado (listo para grabar)")
        self._combo_etiqueta.setEnabled(False)
        self._btn_marcar.setEnabled(False)
        self._shortcut_m.setEnabled(False)

    # ------------------------------------------------------------------
    # Escala vertical (▲▼ por gráfica)
    # ------------------------------------------------------------------

    def _y_zoom(self, idx: int, zoom_in: bool) -> None:
        """Ajusta el rango Y de la gráfica `idx` por factor 1.5."""
        pw = self._plots_widgets[idx]
        factor = 1.5
        accum = self._y_accum[idx]

        if zoom_in:
            new_accum = accum / factor
            if new_accum < 0.01:
                return
            vb = pw.getViewBox()
            ymin, ymax = vb.viewRange()[1]
            centro = (ymin + ymax) / 2
            half = (ymax - ymin) / 2 / factor
            pw.setYRange(centro - half, centro + half, padding=0)
        else:
            new_accum = accum * factor
            if new_accum > 100.0:
                return
            vb = pw.getViewBox()
            ymin, ymax = vb.viewRange()[1]
            centro = (ymin + ymax) / 2
            half = (ymax - ymin) / 2 * factor
            pw.setYRange(centro - half, centro + half, padding=0)

        self._y_accum[idx] = new_accum

    def _reset_y_scales(self) -> None:
        """Restaura los rangos Y de las tres gráficas a sus valores iniciales."""
        for i, pw in enumerate(self._plots_widgets):
            pw.setYRange(*self._y_ranges_init[i], padding=0)
        self._y_accum = [1.0, 1.0, 1.0]

    # ------------------------------------------------------------------
    # Escala temporal (ventana deslizante)
    # ------------------------------------------------------------------

    @Slot()
    def _on_tiempo_ampliar(self) -> None:
        """◀▶ — duplica la ventana visible (menos detalle, más contexto)."""
        nueva = min(self._n_visible * 2, MAX_POINTS)
        nueva = max(nueva, int(0.5 * FS))
        self._n_visible = nueva
        self._sync_combo_zoom()
        self._update_ventana_label()

    @Slot()
    def _on_tiempo_reducir(self) -> None:
        """▶◀ — divide la ventana visible a la mitad (más detalle)."""
        nueva = max(self._n_visible // 2, int(0.5 * FS))
        self._n_visible = nueva
        self._sync_combo_zoom()
        self._update_ventana_label()

    @Slot(int)
    def _on_combo_zoom_changed(self, index: int) -> None:
        factor = _ZOOM_FACTORS[index]
        nueva = MAX_POINTS // factor
        nueva = max(nueva, int(0.5 * FS))
        self._n_visible = nueva
        self._update_ventana_label()

    def _sync_combo_zoom(self) -> None:
        """Actualiza el combo para que refleje el n_visible actual."""
        if MAX_POINTS <= 0:
            return
        factor_actual = MAX_POINTS / self._n_visible
        best_idx, best_diff = 0, float("inf")
        for i, f in enumerate(_ZOOM_FACTORS):
            d = abs(factor_actual - f)
            if d < best_diff:
                best_diff, best_idx = d, i
        self._combo_zoom.blockSignals(True)
        self._combo_zoom.setCurrentIndex(best_idx)
        self._combo_zoom.blockSignals(False)

        # Deshabilitar factores cuya ventana resultante sería < 0.5 s
        model = self._combo_zoom.model()
        for i, f in enumerate(_ZOOM_FACTORS):
            n = MAX_POINTS // f
            item = model.item(i)
            if item:
                enabled = n >= int(0.5 * FS)
                item.setEnabled(enabled)

    def _update_ventana_label(self) -> None:
        segundos = self._n_visible / FS
        if segundos >= 1.0:
            self._lbl_ventana_info.setText(f"{segundos:.1f} s visibles")
        else:
            self._lbl_ventana_info.setText(f"{segundos * 1000:.0f} ms visibles")

    def _reset_all_scales(self) -> None:
        """Reset completo: rangos Y + ventana temporal al estado inicial."""
        self._reset_y_scales()
        self._n_visible = 5 * FS
        self._sync_combo_zoom()
        self._update_ventana_label()

    # ------------------------------------------------------------------
    # LED indicador de comunicación
    # ------------------------------------------------------------------

    def _set_led(self, state: str) -> None:
        """
        Ajusta el LED de comunicación.
        state: 'off'  → rojo    (desconectado)
               'idle' → amarillo (conectado, sin tráfico)
               'ok'   → verde    (recibiendo datos)
        """
        colors = {
            "off":  ("#C0392B", "#7B241C"),   # rojo
            "idle": ("#F1C40F", "#B7950B"),   # amarillo
            "ok":   ("#27AE60", "#196F3D"),   # verde
        }
        fill, border = colors.get(state, colors["off"])
        self._led.setStyleSheet(
            f"background-color: {fill};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
        )

    # ------------------------------------------------------------------
    # Watchdog de conexión BITalino
    # ------------------------------------------------------------------

    @Slot()
    def _check_watchdog(self) -> None:
        """Comprueba cada 1 s que el worker siga recibiendo muestras."""
        if self._worker is None or not self._worker.isRunning():
            return
        # Solo supervisar una vez que el worker esté en fase de lectura
        if not self._worker.is_streaming():
            return
        silencio = self._worker.time_since_last_sample()
        if silencio > self._watchdog_umbral_s:
            if silencio == float("inf") or silencio > 999:
                msg = "Sin datos del dispositivo — conexion no establecida."
            else:
                msg = (f"Sin datos del dispositivo durante {silencio:.1f} s — "
                       "forzando desconexion.")
            self._err(msg)
            self._watchdog_timer.stop()
            self._worker.stop_forced()
            self._worker.wait(2000)
            self._desconectar()

    # ------------------------------------------------------------------
    # Limpieza al cerrar la ventana
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """
        Llamado por MainWindow.closeEvent antes de destruir la ventana.
        Detiene timers, para el worker (forzado si es necesario) y espera
        a que termine para garantizar que el EDF queda cerrado correctamente.
        """
        self._watchdog_timer.stop()
        self._render_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.stop_forced()
            self._worker.wait(5000)
