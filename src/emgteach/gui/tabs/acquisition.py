"""
AcquisitionTab — pestaña 1: adquisición EMG en tiempo real con BITalino.

Controles:
  - Dirección MAC del BITalino (persistida con QSettings)
  - Carpeta de destino para el EDF (persistida con QSettings)
  - Botón Conectar / Desconectar
  - Botón Iniciar / Detener grabación

Canales:
  - 1 o 2 canales simultáneos (p. ej. agonista/antagonista), con etiqueta
    editable por canal. Cada canal se dibuja superpuesto en su propio color.

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
from PySide6.QtCore import QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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

from emgteach.devices import (
    BACKEND_ARDUINO,
    BACKEND_BITALINO,
    ArduinoDevice,
    create_device,
)
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.profiles import EMG_PROFILE
from emgteach.workers import AcquisitionWorker

# Número de muestras en el buffer circular (= 30 s a 1000 Hz)
# La ventana visible puede ser menor gracias al control de zoom temporal.
MAX_POINTS = 30_000
FS = EMG_PROFILE.sample_frequency  # Hz nominal (tomado del perfil de señal)

# Número máximo de canales simultáneos que ofrece la interfaz. La capa de
# datos admite N, pero la UI se limita por ahora a 2 (agonista/antagonista).
MAX_CHANNELS = 2

# Número máximo de marcas de evento dibujadas simultáneamente en vivo
# (pool reutilizable de líneas por gráfica; sobran para una ventana de 30 s).
MAX_MARKER_LINES = 40

# Color por canal, consistente en las tres gráficas: así un color identifica
# siempre al mismo sensor (azul = canal 1, rojo = canal 2).
_CHANNEL_COLORS = [(65, 105, 225), (214, 39, 40)]
_CHANNEL_COLOR_HEX = ["#4169E1", "#D62728"]
_CHANNEL_DEFAULT_LABELS = ["EMG", "EMG 2"]
# Defaults usados brevemente en una versión anterior; se migran a los de
# arriba si siguen guardados en QSettings (no pisa nombres elegidos por el
# usuario, solo los antiguos por defecto).
_OLD_DEFAULT_LABELS = ["Canal 1", "Canal 2"]

# Con 2 canales las gráficas de bruto y filtrada se apilan (un carril por
# canal) en lugar de superponerse. El eje en mV deja de ser absoluto, así que
# cada carril muestra ticks de referencia 0/±_CALIB_MV·ganancia (calibración
# honesta que no tapa la señal). mV de señal real por gráfica (0=bruto,
# 1=filtrada); la envolvente (2) nunca se apila.
_CALIB_MV = {0: 1.0, 1: 0.2}

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
# Variante de mayor tipografía para los controles de ventana temporal (1-2 pt
# más que _BTN_ST, que se reserva para los pequeños botones ▲▼ del sidebar).
_TBTN_ST = (
    "QToolButton { font-size: 11px; padding: 0px 2px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
_COMBO_ST = (
    "QComboBox { font-size: 11px; padding: 1px 3px; min-width: 60px; max-width: 76px; }"
)


class AcquisitionTab(QWidget):
    def __init__(self, logger: LoggerWidget, settings: QSettings, parent=None):
        super().__init__(parent)
        self._logger = logger
        self._settings = settings
        self._worker: AcquisitionWorker | None = None
        self._profile = EMG_PROFILE

        # Número de canales activos (1 o 2), persistido en QSettings.
        saved_n = int(self._settings.value("adquisicion/n_channels", 1))
        self._n_channels = min(max(saved_n, 1), MAX_CHANNELS)

        # Buffers circulares por canal para las tres señales (30 s a 1000 Hz).
        # Se reservan siempre MAX_CHANNELS; solo se rellenan los canales activos.
        self._buf_raw = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(MAX_CHANNELS)
        ]
        self._buf_filt = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(MAX_CHANNELS)
        ]
        self._buf_env = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(MAX_CHANNELS)
        ]
        self._new_data = False  # flag: hay datos nuevos que pintar

        # Eventos para dibujar líneas en vivo: (tiempo_s, etiqueta). El total
        # de muestras adquiridas sitúa cada marca en la ventana deslizante.
        self._marker_events: list[tuple[float, str]] = []
        self._total_samples = 0

        # ---- Estado de escala vertical (por gráfica: 0=raw, 1=filt, 2=env) ----
        # Rangos Y iniciales tomados del perfil de señal (se restauran en
        # _reset_y_scales). Cambiar de modalidad = cambiar de perfil.
        self._y_ranges_init: list[tuple[float, float]] = [
            self._profile.ylim_raw,       # raw
            self._profile.ylim_filtered,  # filtrada
            self._profile.ylim_envelope,  # envolvente
        ]
        self._y_accum: list[float] = [1.0, 1.0, 1.0]  # factor acumulado por gráfica
        # Ganancia de datos por gráfica, usada SOLO en modo apilado (2 canales)
        # en bruto/filtrada: el zoom ▲▼ multiplica la señal dejando los carriles
        # fijos, en lugar de escalar el ViewBox. En modo 1 canal no se usa.
        self._y_gain: list[float] = [1.0, 1.0, 1.0]

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
        # La estética (fondo gris, cajas azul acero, márgenes del título) está
        # centralizada en gui/app.py y se aplica a todas las pestañas. Aquí solo
        # se marca el marco de gráficas con objectName "plotsBox" para que quede
        # en blanco (más abajo).
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ══ Fila superior: Configuración (izq.) | Registro de eventos (der.) ══
        row_top = QHBoxLayout()
        row_top.setSpacing(4)

        # — Configuración del dispositivo (media anchura) —
        grp_config = QGroupBox("Configuración del dispositivo")
        cfg_outer = QVBoxLayout(grp_config)
        cfg_outer.setContentsMargins(6, 3, 6, 3)
        cfg_outer.setSpacing(3)

        # Fila 1: tipo de dispositivo + conexión (MAC o COM)
        cfg_row1 = QHBoxLayout()
        cfg_row1.setSpacing(6)

        # Combo tipo de dispositivo
        self._combo_device_type = QComboBox()
        self._combo_device_type.addItem("BITalino (Bluetooth)")
        self._combo_device_type.addItem("Arduino + MyoWare 2.0 (USB)")
        saved_type = int(self._settings.value("adquisicion/device_type", 0))
        self._combo_device_type.setCurrentIndex(saved_type)
        self._combo_device_type.currentIndexChanged.connect(self._on_device_type_changed)
        cfg_row1.addWidget(self._combo_device_type, stretch=1)

        # Zona central condicional: MAC (BITalino) o COM (Arduino)
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
        cfg_row1.addWidget(self._stack_conn, stretch=2)
        cfg_outer.addLayout(cfg_row1)

        # Fila 2: carpeta de destino + Explorar
        cfg_row2 = QHBoxLayout()
        cfg_row2.setSpacing(6)
        self._edit_dir = QLineEdit()
        self._edit_dir.setPlaceholderText("Carpeta de destino EDF")
        self._edit_dir.setText(self._settings.value("adquisicion/save_dir", "."))
        cfg_row2.addWidget(self._edit_dir, stretch=1)
        btn_dir = QPushButton("Explorar…")
        btn_dir.setFixedWidth(84)
        btn_dir.clicked.connect(self._seleccionar_directorio)
        cfg_row2.addWidget(btn_dir)
        cfg_outer.addLayout(cfg_row2)

        # Visibilidad inicial de la zona de conexión
        self._widget_mac.setVisible(saved_type == 0)
        self._widget_arduino.setVisible(saved_type == 1)
        self._refresh_ports()

        # Fila 3: número de canales y etiquetas por canal
        ch_row = QHBoxLayout()
        ch_row.setSpacing(6)
        ch_row.addWidget(QLabel("Canales:"))
        self._combo_n_channels = QComboBox()
        self._combo_n_channels.addItem("1 (un sensor)")
        self._combo_n_channels.addItem("2 (agonista / antagonista)")
        self._combo_n_channels.setCurrentIndex(self._n_channels - 1)
        self._combo_n_channels.currentIndexChanged.connect(self._on_n_channels_changed)
        ch_row.addWidget(self._combo_n_channels)

        ch_row.addWidget(QLabel("Etiquetas:"))
        self._edit_labels: list[QLineEdit] = []
        for i in range(MAX_CHANNELS):
            edit = QLineEdit()
            edit.setMaxLength(16)  # límite de etiqueta de canal EDF
            edit.setToolTip(
                "Nombre del músculo/sensor de este canal (máx. 16 caracteres; "
                "se usa como etiqueta del canal en el archivo EDF)."
            )
            stored = self._settings.value(
                f"adquisicion/label_{i}", _CHANNEL_DEFAULT_LABELS[i]
            )
            if stored == _OLD_DEFAULT_LABELS[i]:
                stored = _CHANNEL_DEFAULT_LABELS[i]  # migrate old default
            edit.setText(stored)
            edit.textChanged.connect(self._on_label_changed)
            self._edit_labels.append(edit)
            ch_row.addWidget(edit, stretch=1)
        cfg_outer.addLayout(ch_row)

        row_top.addWidget(grp_config, stretch=1)

        # — Registro de eventos (comparte la fila con la configuración) —
        grp_log = QGroupBox("Registro de eventos")
        log_layout = QVBoxLayout(grp_log)
        log_layout.setContentsMargins(4, 4, 4, 4)
        # La fila superior (Configuración + Registro) ocupa ~3 filas de alto;
        # el log llena esa caja y el espacio restante de la ventana va a las
        # gráficas en tiempo real.
        self._local_log.setMaximumHeight(90)
        log_layout.addWidget(self._local_log)
        row_top.addWidget(grp_log, stretch=1)

        root.addLayout(row_top)

        # ══ Fila de acciones: Control | Marcadores (una línea cada una) ══
        row_actions = QHBoxLayout()
        row_actions.setSpacing(4)

        # — Control de adquisición (una sola línea) —
        grp_control = QGroupBox("Control de adquisición")
        ctrl_layout = QHBoxLayout(grp_control)
        ctrl_layout.setContentsMargins(6, 3, 6, 3)
        ctrl_layout.setSpacing(6)

        self._btn_conectar = QPushButton("Conectar")
        self._btn_conectar.setCheckable(True)
        self._btn_conectar.clicked.connect(self._toggle_conexion)
        ctrl_layout.addWidget(self._btn_conectar)

        self._btn_grabar = QPushButton("Iniciar grabación")
        self._btn_grabar.setCheckable(True)
        self._btn_grabar.setEnabled(False)
        self._btn_grabar.clicked.connect(self._toggle_grabacion)
        ctrl_layout.addWidget(self._btn_grabar)

        self._led = QLabel()
        self._led.setFixedSize(16, 16)
        self._led.setToolTip("Estado de comunicación con el dispositivo")
        ctrl_layout.addWidget(self._led)
        self._lbl_estado = QLabel("Estado: desconectado")
        ctrl_layout.addWidget(self._lbl_estado)
        ctrl_layout.addStretch()

        row_actions.addWidget(grp_control, stretch=1)

        # Timer LED idle
        self._led_idle_timer = QTimer(self)
        self._led_idle_timer.setSingleShot(True)
        self._led_idle_timer.setInterval(LED_IDLE_MS)
        self._led_idle_timer.timeout.connect(lambda: self._set_led("idle"))
        self._set_led("off")

        # — Marcadores de eventos (una sola línea) —
        grp_markers = QGroupBox("Marcadores de eventos")
        markers_layout = QHBoxLayout(grp_markers)
        markers_layout.setContentsMargins(6, 3, 6, 3)
        markers_layout.setSpacing(6)

        self._combo_etiqueta = QComboBox()
        for etiq in self._profile.marker_presets:
            self._combo_etiqueta.addItem(etiq)
        self._combo_etiqueta.setEnabled(False)
        markers_layout.addWidget(self._combo_etiqueta, stretch=1)

        self._btn_marcar = QPushButton("MARCAR")
        self._btn_marcar.setMinimumHeight(30)
        self._btn_marcar.setStyleSheet("font-size: 12px; font-weight: bold;")
        self._btn_marcar.setEnabled(False)
        self._btn_marcar.clicked.connect(self._on_marcar)
        markers_layout.addWidget(self._btn_marcar)

        # Detección automática de inicio de contracción (compacta, en línea).
        # Las marcas añadidas quedan reflejadas en el "Registro de eventos".
        self._chk_auto = QCheckBox("Auto-inicio")
        self._chk_auto.setToolTip(
            "Marca automáticamente el inicio de contracción cuando la "
            "envolvente supera el umbral (línea base + k·DE del reposo)."
        )
        self._chk_auto.setChecked(
            self._settings.value("adquisicion/auto_detect", False, type=bool)
        )
        self._chk_auto.toggled.connect(self._on_auto_toggled)
        markers_layout.addWidget(self._chk_auto)
        markers_layout.addWidget(QLabel("k:"))
        self._spin_k = QDoubleSpinBox()
        self._spin_k.setRange(1.0, 10.0)
        self._spin_k.setSingleStep(0.5)
        self._spin_k.setValue(
            self._settings.value(
                "adquisicion/onset_k", self._profile.onset_k, type=float
            )
        )
        self._spin_k.setFixedWidth(60)
        self._spin_k.setToolTip(
            "Umbral en desviaciones típicas sobre el reposo (menor = más sensible)."
        )
        self._spin_k.valueChanged.connect(
            lambda v: self._settings.setValue("adquisicion/onset_k", v)
        )
        self._spin_k.setEnabled(self._chk_auto.isChecked())
        markers_layout.addWidget(self._spin_k)

        row_actions.addWidget(grp_markers, stretch=1)

        root.addLayout(row_actions)

        # Atajo de teclado M
        self._shortcut_m = QShortcut(QKeySequence("M"), self)
        self._shortcut_m.setEnabled(False)
        self._shortcut_m.activated.connect(self._on_marcar_rapido)

        # ── Gráficas + controles de escala ──────────────────────────────
        grp_plots = QGroupBox("Señal EMG en tiempo real")
        grp_plots.setObjectName("plotsBox")  # se mantiene en blanco (ver setStyleSheet)
        plots_root = QVBoxLayout(grp_plots)
        plots_root.setContentsMargins(6, 8, 6, 3)
        plots_root.setSpacing(3)

        # -- Barra de escala temporal (arriba de las gráficas) -----------
        row_tiempo = QHBoxLayout()
        row_tiempo.addWidget(QLabel("Ventana temporal:"))

        self._btn_tiempo_ampliar = QToolButton()
        self._btn_tiempo_ampliar.setText("◀▶")
        self._btn_tiempo_ampliar.setToolTip("Ampliar ventana (ver más tiempo)")
        self._btn_tiempo_ampliar.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_ampliar.setFixedSize(32, 26)
        self._btn_tiempo_ampliar.clicked.connect(self._on_tiempo_ampliar)
        row_tiempo.addWidget(self._btn_tiempo_ampliar)

        self._combo_zoom = QComboBox()
        self._combo_zoom.setStyleSheet(_COMBO_ST)
        self._combo_zoom.setFixedSize(76, 26)
        for f in _ZOOM_FACTORS:
            self._combo_zoom.addItem(f"×{f}")
        self._combo_zoom.setCurrentIndex(0)   # ×1 = todo el buffer
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)
        row_tiempo.addWidget(self._combo_zoom)

        self._btn_tiempo_reducir = QToolButton()
        self._btn_tiempo_reducir.setText("▶◀")
        self._btn_tiempo_reducir.setToolTip("Reducir ventana (ver menos tiempo, más detalle)")
        self._btn_tiempo_reducir.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_reducir.setFixedSize(32, 26)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)
        row_tiempo.addWidget(self._btn_tiempo_reducir)

        self._lbl_ventana_info = QLabel(f"{MAX_POINTS // FS} s visibles")
        self._lbl_ventana_info.setStyleSheet("font-size: 8px; color: #444;")
        row_tiempo.addWidget(self._lbl_ventana_info)

        row_tiempo.addSpacing(12)
        self._lbl_legend = QLabel()
        self._lbl_legend.setStyleSheet("font-size: 9px; font-weight: bold;")
        self._lbl_legend.setToolTip("Color de cada canal en las gráficas")
        row_tiempo.addWidget(self._lbl_legend)

        row_tiempo.addStretch()

        btn_reset_escala = QPushButton("Reset escalas")
        btn_reset_escala.setFixedHeight(26)
        btn_reset_escala.setStyleSheet("font-size: 10px;")
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

        # Una curva por canal en cada gráfica (color = canal). Se reservan
        # MAX_CHANNELS curvas; las de canales inactivos quedan ocultas.
        self._curves_raw: list = []
        self._curves_filt: list = []
        self._curves_env: list = []

        # Señal bruta
        self._plot_raw = pg.PlotWidget(title="Señal EMG en bruto (mV)")
        self._plot_raw.setYRange(*self._y_ranges_init[0])
        self._plot_raw.setLabel("left", "mV")
        self._plot_raw.showGrid(x=True, y=True, alpha=0.3)
        for c in range(MAX_CHANNELS):
            self._curves_raw.append(
                self._plot_raw.plot(pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=1))
            )
        plots_col_vbox.addWidget(self._plot_raw)

        # Señal filtrada
        self._plot_filt = pg.PlotWidget(
            title="EMG filtrado (notch 50 Hz + paso-banda 20-450 Hz)"
        )
        self._plot_filt.setYRange(*self._y_ranges_init[1])
        self._plot_filt.setLabel("left", "mV")
        self._plot_filt.showGrid(x=True, y=True, alpha=0.3)
        for c in range(MAX_CHANNELS):
            self._curves_filt.append(
                self._plot_filt.plot(pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=1))
            )
        plots_col_vbox.addWidget(self._plot_filt)

        # Envolvente
        self._plot_env = pg.PlotWidget(
            title="Envolvente (filtro paso-bajo 5 Hz, causal con estado continuo)"
        )
        self._plot_env.setYRange(*self._y_ranges_init[2])
        self._plot_env.setLabel("left", "mV")
        self._plot_env.showGrid(x=True, y=True, alpha=0.3)
        for c in range(MAX_CHANNELS):
            self._curves_env.append(
                self._plot_env.plot(pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=2))
            )
        plots_col_vbox.addWidget(self._plot_env)

        # Pool reutilizable de líneas verticales para las marcas de evento,
        # una colección por gráfica (se reposicionan en cada refresco según la
        # ventana deslizante; color naranja, igual que en la pestaña Análisis).
        marker_pen = pg.mkPen(color=(230, 126, 34), width=1, style=Qt.PenStyle.DashLine)
        self._marker_lines: list[list] = []
        for pw in (self._plot_raw, self._plot_filt, self._plot_env):
            pool = []
            for _ in range(MAX_MARKER_LINES):
                line = pg.InfiniteLine(angle=90, movable=False, pen=marker_pen)
                line.hide()
                pw.addItem(line, ignoreBounds=True)
                pool.append(line)
            self._marker_lines.append(pool)

        # Anotaciones del modo apilado (2 canales), solo en bruto y filtrada:
        # una línea base horizontal por canal (su "cero") y la etiqueta del
        # músculo junto a cada carril. La calibración se presenta como ticks de
        # referencia en el eje (ver _set_calib_ticks). Ocultas en modo 1 canal.
        self._baselines: dict[int, list] = {}
        self._lane_labels: dict[int, list] = {}
        for idx, pw in ((0, self._plot_raw), (1, self._plot_filt)):
            base_lines = []
            lane_labels = []
            for c in range(MAX_CHANNELS):
                bl = pg.InfiniteLine(
                    angle=0,
                    movable=False,
                    pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=1,
                                 style=Qt.PenStyle.DotLine),
                )
                bl.hide()
                pw.addItem(bl, ignoreBounds=True)
                base_lines.append(bl)

                txt = pg.TextItem(anchor=(0, 0.5), fill=(255, 255, 255, 200))
                txt.setColor(_CHANNEL_COLORS[c])
                txt.hide()
                pw.addItem(txt, ignoreBounds=True)
                lane_labels.append(txt)
            self._baselines[idx] = base_lines
            self._lane_labels[idx] = lane_labels

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
            btn_up.setToolTip(f"Ampliar (vertical) — {lbl_txt}")
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
            btn_dn.setToolTip(f"Reducir (vertical) — {lbl_txt}")
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

        # Mostrar solo los canales activos y pintar la leyenda
        self._apply_channel_visibility()
        self._update_legend()
        # Configurar el modo de las gráficas (superpuesto o apilado) según el
        # número de canales persistido.
        self._apply_stacking_mode()

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

    # ------------------------------------------------------------------
    # Canales (1 o 2: agonista/antagonista)
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_n_channels_changed(self, index: int) -> None:
        self._n_channels = index + 1
        self._settings.setValue("adquisicion/n_channels", self._n_channels)
        self._apply_channel_visibility()
        self._update_legend()
        # Cambiar de 1↔2 canales reconfigura las gráficas (apilado vs
        # superpuesto) y reinicia la ganancia del apilado.
        self._y_gain = [1.0, 1.0, 1.0]
        self._apply_stacking_mode()

    @Slot()
    def _on_label_changed(self) -> None:
        for i, edit in enumerate(self._edit_labels):
            self._settings.setValue(f"adquisicion/label_{i}", edit.text())
        self._update_legend()

    def _active_labels(self) -> list[str]:
        """Labels of the active channels, falling back to the defaults."""
        labels = []
        for i in range(self._n_channels):
            text = self._edit_labels[i].text().strip()
            labels.append(text or _CHANNEL_DEFAULT_LABELS[i])
        return labels

    def _apply_channel_visibility(self) -> None:
        """Show only the widgets and curves of the active channels."""
        for i, edit in enumerate(self._edit_labels):
            edit.setVisible(i < self._n_channels)
        for c in range(MAX_CHANNELS):
            visible = c < self._n_channels
            self._curves_raw[c].setVisible(visible)
            self._curves_filt[c].setVisible(visible)
            self._curves_env[c].setVisible(visible)

    def _update_legend(self) -> None:
        parts = [
            f'<span style="color:{_CHANNEL_COLOR_HEX[i]}">&#9679; {lbl}</span>'
            for i, lbl in enumerate(self._active_labels())
        ]
        self._lbl_legend.setText("&nbsp;&nbsp;&nbsp;".join(parts))
        # Mantener sincronizadas las etiquetas de carril del modo apilado.
        if hasattr(self, "_lane_labels"):
            self._refresh_lane_label_texts()

    # ------------------------------------------------------------------
    # Modo apilado (2 canales) en bruto / filtrada
    # ------------------------------------------------------------------

    def _is_stacked(self, idx: int) -> bool:
        """True si la gráfica idx (0=bruto, 1=filtrada) apila 2 canales."""
        return self._n_channels == 2 and idx in (0, 1)

    def _lane_half(self, idx: int) -> float:
        """Semialtura del rango inicial de la gráfica idx (= altura de un carril)."""
        lo, hi = self._y_ranges_init[idx]
        return (hi - lo) / 2.0

    def _lane_baseline(self, idx: int, channel: int) -> float:
        """Línea base (offset) del canal en la gráfica idx: canal 0 arriba (+A),
        canal 1 abajo (-A)."""
        a = self._lane_half(idx)
        return a if channel == 0 else -a

    def _set_calib_ticks(self, idx: int) -> None:
        """Ticks de referencia 0 y ±_CALIB_MV·ganancia en cada carril. Sustituyen
        al eje mV absoluto (engañoso al apilar) por una calibración honesta que
        no tapa la señal."""
        axis = self._plots_widgets[idx].getAxis("left")
        calib = _CALIB_MV[idx]
        g = self._y_gain[idx]
        major = []
        for c in range(self._n_channels):
            base = self._lane_baseline(idx, c)
            major.append((base, "0"))
            major.append((base + g * calib, f"+{calib:g}"))
            major.append((base - g * calib, f"−{calib:g}"))
        axis.setTicks([major])

    def _refresh_lane_label_texts(self) -> None:
        """Actualiza texto, color, posición y visibilidad de las etiquetas de
        carril según las etiquetas activas y el modo apilado."""
        labels = self._active_labels()
        for idx in (0, 1):
            a = self._lane_half(idx)
            for c in range(MAX_CHANNELS):
                txt = self._lane_labels[idx][c]
                if self._is_stacked(idx) and c < self._n_channels:
                    txt.setText(f" {labels[c]}")
                    txt.setColor(_CHANNEL_COLORS[c])
                    txt.setPos(0.0, self._lane_baseline(idx, c) + a * 0.78)
                    txt.show()
                else:
                    txt.hide()

    def _apply_stacking_mode(self) -> None:
        """Configura rango Y, ticks de calibración y líneas base de bruto y
        filtrada según el número de canales (1 = superpuesto sobre cero,
        2 = dos carriles apilados). La envolvente nunca se apila."""
        for idx in (0, 1):
            pw = self._plots_widgets[idx]
            axis = pw.getAxis("left")
            a = self._lane_half(idx)
            if self._is_stacked(idx):
                pw.setYRange(-2 * a, 2 * a, padding=0)
                self._set_calib_ticks(idx)
                for c in range(MAX_CHANNELS):
                    bl = self._baselines[idx][c]
                    if c < self._n_channels:
                        bl.setPos(self._lane_baseline(idx, c))
                        bl.show()
                    else:
                        bl.hide()
            else:
                pw.setYRange(*self._y_ranges_init[idx], padding=0)
                axis.setTicks(None)  # restaura ticks automáticos (mV absolutos)
                for c in range(MAX_CHANNELS):
                    self._baselines[idx][c].hide()
        self._refresh_lane_label_texts()

    def _set_channel_controls_enabled(self, enabled: bool) -> None:
        self._combo_n_channels.setEnabled(enabled)
        for edit in self._edit_labels:
            edit.setEnabled(enabled)

    def _reset_buffers(self) -> None:
        """Clear every per-channel ring buffer back to silence."""
        for bufs in (self._buf_raw, self._buf_filt, self._buf_env):
            for buf in bufs:
                buf.clear()
                buf.extend([0.0] * MAX_POINTS)

    @Slot(bool)
    def _on_auto_toggled(self, checked: bool) -> None:
        self._spin_k.setEnabled(checked)
        self._settings.setValue("adquisicion/auto_detect", checked)

    def _set_auto_controls_enabled(self, enabled: bool) -> None:
        self._chk_auto.setEnabled(enabled)
        self._spin_k.setEnabled(enabled and self._chk_auto.isChecked())

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
        self._set_channel_controls_enabled(False)
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
        self._set_channel_controls_enabled(True)
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

        self._reset_buffers()
        self._marker_events.clear()
        self._total_samples = 0
        for pool in self._marker_lines:
            for line in pool:
                line.hide()
        self._reset_y_scales()

        n = self._n_channels
        labels = self._active_labels()
        for i, lbl in enumerate(labels):
            self._settings.setValue(f"adquisicion/label_{i}", lbl)

        if self._combo_device_type.currentIndex() == 0:
            device = create_device(
                BACKEND_BITALINO,
                mac=self._edit_mac.text().strip(),
                fs=FS,
                channels=list(range(n)),
            )
        else:
            device = create_device(
                BACKEND_ARDUINO,
                port=self._combo_port.currentText().strip(),
                fs=FS,
                n_channels=n,
            )
        self._settings.setValue("adquisicion/auto_detect", self._chk_auto.isChecked())
        self._settings.setValue("adquisicion/onset_k", self._spin_k.value())
        self._worker = AcquisitionWorker(
            device=device,
            save_dir=save_dir,
            sensor_labels=labels,
            auto_detect=self._chk_auto.isChecked(),
            onset_k=self._spin_k.value(),
        )
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
        self._set_auto_controls_enabled(False)
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
        self._set_auto_controls_enabled(True)

    # ------------------------------------------------------------------
    # Slots del worker
    # ------------------------------------------------------------------

    @Slot(dict)
    def _on_data_ready(self, data: dict) -> None:
        # Arranca el watchdog en la primera muestra recibida (no antes, para no
        # disparar durante device.open() que puede tardar hasta 3 s en Arduino).
        if not self._watchdog_timer.isActive():
            self._watchdog_timer.start()
        # data_ready carries one array per channel; append each to its buffer.
        raw = data["raw_mv"]
        filt = data["filtered"]
        env = data["envelope"]
        for c in range(min(len(raw), MAX_CHANNELS)):
            self._buf_raw[c].extend(raw[c].tolist())
            self._buf_filt[c].extend(filt[c].tolist())
            self._buf_env[c].extend(env[c].tolist())
        if raw:
            self._total_samples += len(raw[0])
        self._new_data = True
        # LED verde: hay tráfico. El timer lo devolverá a amarillo si no llega
        # ningún bloque nuevo en LED_IDLE_MS ms.
        self._set_led("ok")
        self._led_idle_timer.start()

    def _refresh_plots(self, force: bool = False) -> None:
        """Llamado cada 33 ms por _render_timer. Pinta solo si hay datos nuevos
        (o si `force`, p. ej. al cambiar la ganancia del apilado)."""
        if not self._new_data and not force:
            return
        self._new_data = False

        n = min(self._n_visible, MAX_POINTS)
        # Eje X en segundos relativo al inicio de la ventana visible (todos los
        # buffers tienen la misma longitud, así que se calcula una sola vez).
        t = np.arange(n) / FS

        # En modo apilado (2 canales) bruto/filtrada se dibujan desplazados a su
        # carril y escalados por la ganancia: mostrado = base + ganancia·señal.
        stacked_raw = self._is_stacked(0)
        stacked_filt = self._is_stacked(1)

        for c in range(self._n_channels):
            arr_raw = np.array(list(self._buf_raw[c]))[-n:]
            arr_filt = np.array(list(self._buf_filt[c]))[-n:]
            arr_env = np.array(list(self._buf_env[c]))[-n:]
            if stacked_raw:
                arr_raw = self._lane_baseline(0, c) + self._y_gain[0] * arr_raw
            if stacked_filt:
                arr_filt = self._lane_baseline(1, c) + self._y_gain[1] * arr_filt
            self._curves_raw[c].setData(t, arr_raw)
            self._curves_filt[c].setData(t, arr_filt)
            self._curves_env[c].setData(t, arr_env)

        # Reposicionar las líneas de marca: cada evento se sitúa según cuántas
        # muestras hace que ocurrió, dentro de la ventana visible.
        win_s = n / FS
        visible = [
            win_s - (self._total_samples - tiempo * FS) / FS
            for tiempo, _label in self._marker_events
            if 0 <= self._total_samples - tiempo * FS <= n
        ]
        visible = visible[-MAX_MARKER_LINES:]
        for pool in self._marker_lines:
            for i, line in enumerate(pool):
                if i < len(visible):
                    line.setPos(visible[i])
                    line.show()
                elif line.isVisible():
                    line.hide()

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
        # La marca queda reflejada en el "Registro de eventos" (log).
        self._log(f"Marca añadida: t={tiempo:.1f} s — {etiqueta}")
        # Registrar el evento para dibujarlo en vivo sobre las gráficas.
        self._marker_events.append((tiempo, etiqueta))

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
        self._set_auto_controls_enabled(True)

    # ------------------------------------------------------------------
    # Escala vertical (▲▼ por gráfica)
    # ------------------------------------------------------------------

    def _y_zoom(self, idx: int, zoom_in: bool) -> None:
        """Ajusta la escala vertical de la gráfica `idx` por factor 1.5.

        En modo apilado (bruto/filtrada con 2 canales) escala la ganancia de
        datos dejando los carriles fijos; en el resto escala el ViewBox.
        """
        factor = 1.5

        if self._is_stacked(idx):
            gain = self._y_gain[idx]
            new_gain = gain / factor if zoom_in else gain * factor
            if new_gain < 0.01 or new_gain > 100.0:
                return
            self._y_gain[idx] = new_gain
            self._set_calib_ticks(idx)
            self._refresh_plots(force=True)
            return

        pw = self._plots_widgets[idx]
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
        """Restaura la escala vertical de las tres gráficas a su estado inicial."""
        self._y_accum = [1.0, 1.0, 1.0]
        self._y_gain = [1.0, 1.0, 1.0]
        # Envolvente: nunca apilada, rango inicial directo.
        self._plot_env.setYRange(*self._y_ranges_init[2], padding=0)
        # Bruto/filtrada: el modo (apilado o superpuesto) fija rango y anotaciones.
        self._apply_stacking_mode()

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
