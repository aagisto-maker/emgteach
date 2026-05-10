"""
AnalysisTab — pestaña 2: análisis offline completo de señal EMG.

Reproduce los 7 paneles de analisis_emg_completo.py con matplotlib embebido
en Qt (FigureCanvasQTAgg). El procesado corre en AnalysisWorker (QThread)
para que la UI no se bloquee durante el análisis.

Controles:
  - Selector de archivo EDF (ruta persistida en QSettings)
  - Nombre del canal EMG
  - Frecuencia de corte de la envolvente (editable, por defecto 5.0 Hz)
  - Botón Analizar / Guardar figura
  - Barra de progreso

Panel de resumen: MNF, MDF, indicador de fatiga.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_ZOOM_FACTORS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]

_PANEL_NOMBRES = [
    "1A. Señal bruta",
    "1B. Filtrada + rectificada",
    "2. Envolvente vs RMS",
    "3. Envolvente normalizada",
    "4. PSD con MNF/MDF",
    "5. RMS por ventana",
    "6. MDF vs tiempo (fatiga)",
    "7. RMS vs MDF",
]

_PANEL_SHORT_NAMES = ["1A", "1B", "2", "3", "4", "5", "6", "7"]

from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.gui.widgets.time_range import TimeRangeSelector
from emgteach.workers import AnalysisWorker


class AnalysisTab(QWidget):
    def __init__(self, logger: LoggerWidget, settings: QSettings, parent=None):
        super().__init__(parent)
        self._logger = logger
        self._settings = settings
        self._worker: AnalysisWorker | None = None
        self._last_result: dict | None = None
        self._last_edf_dir: str = self._settings.value("analisis/last_dir", ".")

        self._duracion_total: float = 60.0
        self._markers: list[tuple[float, str]] = []
        self._axes_list: list = []
        self._y_accum: dict[int, float] = {}
        self._y_initial_lims: dict[int, tuple[float, float]] = {}

        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(400)
        self._redraw_timer.timeout.connect(self._redibujar_con_ventana_actual)

        self._build_ui()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- Fila superior: Parámetros (stretch 3) + Log (stretch 2) ---
        grp_ctrl = QGroupBox("Parámetros de análisis")
        ctrl = QVBoxLayout(grp_ctrl)
        ctrl.setSpacing(4)
        ctrl.setContentsMargins(6, 4, 6, 4)

        # Línea 1: archivo EDF + Analizar + Guardar
        row_file = QHBoxLayout()
        row_file.addWidget(QLabel("Archivo EDF:"))
        self._edit_path = QLineEdit()
        self._edit_path.setPlaceholderText("Selecciona un archivo EDF…")
        self._edit_path.setReadOnly(True)
        row_file.addWidget(self._edit_path, stretch=1)
        self._btn_abrir = QPushButton("Explorar…")
        self._btn_abrir.setFixedWidth(84)
        self._btn_abrir.clicked.connect(self._seleccionar_archivo)
        row_file.addWidget(self._btn_abrir)
        self._btn_analizar = QPushButton("Analizar")
        self._btn_analizar.setEnabled(False)
        self._btn_analizar.clicked.connect(self._iniciar_analisis)
        row_file.addWidget(self._btn_analizar)
        self._btn_guardar = QPushButton("Guardar figura (PNG)")
        self._btn_guardar.setEnabled(False)
        self._btn_guardar.clicked.connect(self._guardar_figura)
        row_file.addWidget(self._btn_guardar)
        ctrl.addLayout(row_file)

        # Línea 2: canal + f_env
        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Canal EMG:"))
        self._edit_canal = QLineEdit("EMG")
        self._edit_canal.setFixedWidth(90)
        row_params.addWidget(self._edit_canal)
        row_params.addWidget(QLabel("Frec. corte envolvente (Hz):"))
        self._spin_fenv = QDoubleSpinBox()
        self._spin_fenv.setRange(1.0, 20.0)
        self._spin_fenv.setSingleStep(0.5)
        self._spin_fenv.setValue(5.0)
        self._spin_fenv.setFixedWidth(72)
        row_params.addWidget(self._spin_fenv)
        row_params.addStretch()
        ctrl.addLayout(row_params)

        # Log a la derecha de los parámetros
        grp_log_top = QGroupBox("Registro de eventos")
        log_top_layout = QVBoxLayout(grp_log_top)
        log_top_layout.setContentsMargins(4, 4, 4, 4)
        log_top_layout.addWidget(self._logger)

        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        top_row.addWidget(grp_ctrl, stretch=3)
        top_row.addWidget(grp_log_top, stretch=2)
        root.addLayout(top_row)

        # --- Selección de paneles — una línea compacta con scroll horizontal ---
        _PANEL_SHORT_LABELS = [
            "1A. Bruta", "1B. Filtr.+rect.", "2. Env. vs RMS",
            "3. Env. norm.", "4. PSD", "5. RMS/ventana",
            "6. MDF/tiempo", "7. RMS vs MDF",
        ]
        grp_paneles = QGroupBox("Paneles a mostrar")
        paneles_inner = QWidget()
        paneles_layout = QHBoxLayout(paneles_inner)
        paneles_layout.setContentsMargins(2, 0, 2, 0)
        paneles_layout.setSpacing(6)
        self._chk_paneles: list[QCheckBox] = []
        for label in _PANEL_SHORT_LABELS:
            chk = QCheckBox(label)
            chk.setChecked(True)
            paneles_layout.addWidget(chk)
            self._chk_paneles.append(chk)
        paneles_layout.addStretch()
        self._btn_redibujar = QPushButton("Redibujar")
        self._btn_redibujar.setEnabled(False)
        self._btn_redibujar.clicked.connect(self._redibujar)
        paneles_layout.addWidget(self._btn_redibujar)

        paneles_scroll = QScrollArea()
        paneles_scroll.setWidget(paneles_inner)
        paneles_scroll.setWidgetResizable(True)
        paneles_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        paneles_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        paneles_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        _fm = QFontMetrics(self.font())
        paneles_scroll.setFixedHeight(_fm.lineSpacing() * 2 + 10)

        paneles_outer = QVBoxLayout(grp_paneles)
        paneles_outer.setContentsMargins(4, 2, 4, 2)
        paneles_outer.addWidget(paneles_scroll)

        # --- Ventana de visualización (minimapa) ---
        grp_ventana = QGroupBox("Ventana de visualización")
        ventana_vbox = QVBoxLayout(grp_ventana)
        ventana_vbox.setContentsMargins(6, 4, 6, 4)
        ventana_vbox.setSpacing(2)

        self._time_range = TimeRangeSelector()
        self._time_range.setEnabled(False)
        self._time_range.range_changed.connect(self._on_range_changed)
        self._time_range.range_preview.connect(self._on_range_preview)
        ventana_vbox.addWidget(self._time_range)

        row_info = QHBoxLayout()
        self._lbl_inicio_info   = QLabel("Inicio: 0.0 s")
        self._lbl_duracion_info = QLabel("Duración: 10.0 s")
        _info_sep = QLabel("|")
        for lbl in (self._lbl_inicio_info, _info_sep, self._lbl_duracion_info):
            lbl.setStyleSheet("font-size: 9px; padding: 0 4px; color: #333333;")
        self._btn_reset_ventana = QPushButton("Reset ventana")
        self._btn_reset_ventana.setEnabled(False)
        self._btn_reset_ventana.setFixedHeight(22)
        self._btn_reset_ventana.setStyleSheet("font-size: 9px;")
        self._btn_reset_ventana.clicked.connect(self._reset_ventana)

        _btn_st = "font-size: 9px;"
        self._btn_tiempo_ampliar = QPushButton("◀▶")
        self._btn_tiempo_ampliar.setToolTip("Ampliar ventana temporal (×2)")
        self._btn_tiempo_ampliar.setFixedSize(30, 22)
        self._btn_tiempo_ampliar.setStyleSheet(_btn_st)
        self._btn_tiempo_ampliar.setEnabled(False)
        self._btn_tiempo_ampliar.clicked.connect(self._on_tiempo_ampliar)

        self._combo_zoom = QComboBox()
        self._combo_zoom.setFixedSize(62, 22)
        self._combo_zoom.setStyleSheet(_btn_st)
        self._combo_zoom.setEnabled(False)
        for f in _ZOOM_FACTORS:
            self._combo_zoom.addItem(f"×{f}")
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)

        self._btn_tiempo_reducir = QPushButton("▶◀")
        self._btn_tiempo_reducir.setToolTip("Reducir ventana temporal (÷2)")
        self._btn_tiempo_reducir.setFixedSize(30, 22)
        self._btn_tiempo_reducir.setStyleSheet(_btn_st)
        self._btn_tiempo_reducir.setEnabled(False)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)

        row_info.addWidget(self._lbl_inicio_info)
        row_info.addWidget(_info_sep)
        row_info.addWidget(self._lbl_duracion_info)
        row_info.addStretch()
        row_info.addWidget(self._btn_tiempo_ampliar)
        row_info.addWidget(self._combo_zoom)
        row_info.addWidget(self._btn_tiempo_reducir)
        row_info.addWidget(self._btn_reset_ventana)
        ventana_vbox.addLayout(row_info)

        # --- Barra de progreso ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("Listo")
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # --- Panel de resumen numérico (una fila) ---
        grp_resumen = QGroupBox("Resumen del análisis")
        grp_resumen.setContentsMargins(4, 2, 4, 2)
        resumen_inner = QWidget()
        resumen_row = QHBoxLayout(resumen_inner)
        resumen_row.setContentsMargins(4, 0, 4, 0)
        resumen_row.setSpacing(0)

        _st = "font-size: 9px; padding: 0 4px;"
        _sep_st = "font-size: 9px; color: #999999; padding: 0 2px;"

        def _sep():
            s = QLabel("|")
            s.setStyleSheet(_sep_st)
            return s

        self._lbl_mnf = QLabel("Frecuencia Media (MNF): —")
        self._lbl_mdf = QLabel("Frecuencia Mediana (MDF): —")
        self._lbl_fatiga = QLabel("Fatiga: —")
        self._lbl_pendiente = QLabel("Pendiente MDF: —")
        self._lbl_rms_global = QLabel("RMS global: —")
        self._lbl_iemg = QLabel("iEMG: —")
        self._lbl_duracion = QLabel("Duración: —")
        self._lbl_archivo = QLabel("")

        for lbl in (self._lbl_mnf, self._lbl_mdf, self._lbl_fatiga, self._lbl_pendiente,
                    self._lbl_rms_global, self._lbl_iemg, self._lbl_duracion, self._lbl_archivo):
            lbl.setStyleSheet(_st)

        for lbl in (self._lbl_mnf, _sep(), self._lbl_mdf, _sep(), self._lbl_fatiga, _sep(),
                    self._lbl_pendiente, _sep(), self._lbl_rms_global, _sep(),
                    self._lbl_iemg, _sep(), self._lbl_duracion, _sep(), self._lbl_archivo):
            resumen_row.addWidget(lbl)
        resumen_row.addStretch()

        resumen_scroll = QScrollArea()
        resumen_scroll.setWidget(resumen_inner)
        resumen_scroll.setWidgetResizable(True)
        resumen_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        resumen_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        resumen_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        resumen_scroll.setFixedHeight(28)

        resumen_vbox = QVBoxLayout(grp_resumen)
        resumen_vbox.setContentsMargins(0, 0, 0, 0)
        resumen_vbox.addWidget(resumen_scroll)

        root.addWidget(grp_resumen)

        # --- Canvas matplotlib con scroll (7 paneles son altos) ---
        self._fig = Figure(constrained_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Sidebar de escala vertical: una pareja ▲▼ por panel activo
        self._y_scale_sidebar = QWidget()
        self._y_scale_sidebar.setFixedWidth(38)
        self._y_scale_sidebar_layout = QVBoxLayout(self._y_scale_sidebar)
        self._y_scale_sidebar_layout.setContentsMargins(2, 4, 2, 4)
        self._y_scale_sidebar_layout.setSpacing(0)

        canvas_container = QWidget()
        canvas_hbox = QHBoxLayout(canvas_container)
        canvas_hbox.setContentsMargins(0, 0, 0, 0)
        canvas_hbox.setSpacing(2)
        canvas_hbox.addWidget(self._y_scale_sidebar)
        canvas_hbox.addWidget(self._canvas)

        scroll = QScrollArea()
        scroll.setWidget(canvas_container)
        scroll.setWidgetResizable(True)

        root.addWidget(scroll, stretch=1)

        # --- Ventana de visualización (ancho completo, bajo el canvas) ---
        root.addWidget(grp_ventana)

        # --- Fila inferior: Marcadores (stretch=2) + Paneles a mostrar (stretch=5) ---
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        # Grupo marcadores
        grp_markers_bar = QGroupBox("Marcadores")
        markers_inner = QHBoxLayout(grp_markers_bar)
        markers_inner.setContentsMargins(6, 2, 6, 2)
        markers_inner.setSpacing(6)
        self._lbl_markers_bar = QLabel("Marcadores (0):")
        self._lbl_markers_bar.setStyleSheet("font-size: 9px;")
        markers_inner.addWidget(self._lbl_markers_bar)
        self._combo_markers = QComboBox()
        self._combo_markers.setStyleSheet("font-size: 9px;")
        self._combo_markers.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._combo_markers.setEnabled(False)
        self._combo_markers.addItem("Sin marcadores")
        markers_inner.addWidget(self._combo_markers, stretch=1)
        self._btn_ir_marcador = QPushButton("Ir")
        self._btn_ir_marcador.setFixedWidth(36)
        self._btn_ir_marcador.setFixedHeight(22)
        self._btn_ir_marcador.setStyleSheet("font-size: 9px;")
        self._btn_ir_marcador.setEnabled(False)
        self._btn_ir_marcador.clicked.connect(self._on_ir_marcador)
        markers_inner.addWidget(self._btn_ir_marcador)
        bottom_row.addWidget(grp_markers_bar, stretch=2)

        bottom_row.addWidget(grp_paneles, stretch=5)
        root.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Slots de control
    # ------------------------------------------------------------------

    @Slot()
    def _seleccionar_archivo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo EDF",
            self._last_edf_dir,
            "Archivos EDF (*.edf *.EDF)",
        )
        if path:
            self._edit_path.setText(path)
            self._last_edf_dir = str(Path(path).parent)
            self._settings.setValue("analisis/last_dir", self._last_edf_dir)
            self._btn_analizar.setEnabled(True)
            self._btn_guardar.setEnabled(False)
            self._progress.setValue(0)
            self._progress.setFormat("Listo")

    @Slot()
    def _iniciar_analisis(self) -> None:
        path = self._edit_path.text().strip()
        canal = self._edit_canal.text().strip() or "EMG"
        f_env = self._spin_fenv.value()

        self._set_controles_habilitados(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._progress.setFormat("Analizando…  %p%")
        self._btn_guardar.setEnabled(False)
        self._lbl_mnf.setText("Frecuencia Media (MNF): —")
        self._lbl_mdf.setText("Frecuencia Mediana (MDF): —")
        self._lbl_fatiga.setText("Fatiga: —")

        self._worker = AnalysisWorker(
            edf_path=path,
            channel_name=canal,
            f_env=f_env,
            plot_duration_s=0,
        )
        self._worker.result_ready.connect(self._on_result)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._logger.append_log)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    # ------------------------------------------------------------------
    # Slots del worker
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_progress(self, value: int) -> None:
        self._progress.setValue(value)

    @Slot(dict)
    def _on_result(self, result: dict) -> None:
        self._last_result = result
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)
        self._btn_guardar.setEnabled(True)
        self._btn_redibujar.setEnabled(True)
        duracion_total = float(result["times"][-1])
        self._duracion_total = duracion_total
        self._time_range.set_total_duration(duracion_total)
        _dur_ini = duracion_total / 3.0
        self._time_range.set_range(0.0, _dur_ini)
        self._lbl_inicio_info.setText("Inicio: 0.0 s")
        self._lbl_duracion_info.setText(f"Duración: {_dur_ini:.1f} s")
        self._markers = result.get("markers", [])
        self._actualizar_lista_marcadores()
        self._update_combo_items()
        self._sync_combo_zoom()
        self._actualizar_resumen(result)
        self._dibujar_paneles(result)

    @Slot(float, float)
    def _on_range_changed(self, inicio: float, duracion: float) -> None:
        self._lbl_inicio_info.setText(f"Inicio: {inicio:.1f} s")
        self._lbl_duracion_info.setText(f"Duración: {duracion:.1f} s")
        self._sync_combo_zoom()
        self._redraw_timer.start()

    @Slot(float, float)
    def _on_range_preview(self, inicio: float, duracion: float) -> None:
        self._lbl_inicio_info.setText(f"Inicio: {inicio:.1f} s")
        self._lbl_duracion_info.setText(f"Duración: {duracion:.1f} s")

    @Slot()
    def _redibujar_con_ventana_actual(self) -> None:
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)

    @Slot()
    def _reset_ventana(self) -> None:
        dur = self._duracion_total / 3.0
        self._time_range.set_range(0.0, dur)
        self._lbl_inicio_info.setText("Inicio: 0.0 s")
        self._lbl_duracion_info.setText(f"Duración: {dur:.1f} s")
        self._sync_combo_zoom()
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)

    @Slot()
    def _redibujar(self) -> None:
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._logger.append_error(msg)
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)

    # ------------------------------------------------------------------
    # Resumen numérico
    # ------------------------------------------------------------------

    def _actualizar_resumen(self, r: dict) -> None:
        self._lbl_archivo.setText(f"Archivo: {Path(r['edf_path']).name}")
        self._lbl_mnf.setText(f"Frecuencia Media (MNF): {r['mnf']:.1f} Hz")
        self._lbl_mdf.setText(f"Frecuencia Mediana (MDF): {r['mdf']:.1f} Hz")
        pendiente = r.get("mdf_slope", 0.0)
        signo = "+" if pendiente >= 0 else ""
        self._lbl_pendiente.setText(f"Pendiente MDF: {signo}{pendiente:.2f} Hz/s")
        self._lbl_rms_global.setText(f"RMS global: {r.get('rms_global', 0.0):.2f} mV")
        self._lbl_iemg.setText(f"iEMG: {r.get('iemg', 0.0):.1f} mV·s")
        self._lbl_duracion.setText(f"Duración: {r.get('duration', 0.0):.1f} s")

        sign = r["fat_slope_sign"]
        if sign < 0:
            texto = "Fatiga: DETECTADA (MDF decrece)"
            color = "#cc0000"
        elif sign > 0:
            texto = "Fatiga: No detectada (MDF estable o crece)"
            color = "#007700"
        else:
            texto = "Fatiga: Indeterminada (Señal insuficiente)"
            color = "#885500"
        self._lbl_fatiga.setText(texto)
        self._lbl_fatiga.setStyleSheet(f"font-size: 9px; padding: 0 4px; color: {color};")

    # ------------------------------------------------------------------
    # Dibujo de los 7 paneles (replica analisis_emg_completo.py)
    # ------------------------------------------------------------------

    def _dibujar_paneles(self, r: dict) -> None:
        self._fig.clear()
        self._fig.set_constrained_layout_pads(hspace=0.12, h_pad=0.08)

        selected = [i for i, chk in enumerate(self._chk_paneles) if chk.isChecked()]
        if not selected:
            self._canvas.draw_idle()
            return

        times = r["times"]
        inicio_s, dur_s = self._time_range.get_range()
        fin_s = inicio_s + dur_s
        f_high = r["f_high"]

        n_panels = len(selected)
        raw_axes = self._fig.subplots(n_panels, 1, sharex=False)
        axes_list = [raw_axes] if n_panels == 1 else list(raw_axes)
        ax_map = {panel_idx: axes_list[pos] for pos, panel_idx in enumerate(selected)}

        _grid = dict(ls="--", color="#DDDDDD", alpha=0.8)

        # --- 1A: Señal bruta ---
        if 0 in ax_map:
            ax = ax_map[0]
            ax.plot(times, r["emg_raw"],
                    color="#333333", lw=0.8, alpha=0.7)
            ax.set_title("1A. Señal EMG bruta", fontsize=9)
            ax.set_ylabel("Amplitud (mV)", fontsize=8)
            ax.set_xlabel("Tiempo (s)", fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 1B: Filtrada + rectificada ---
        if 1 in ax_map:
            ax = ax_map[1]
            ax.plot(times, r["emg_filtered"],
                    color="#1f77b4", lw=1.2, label="EMG filtrado (20-450 Hz)")
            ax.plot(times, r["emg_rectified"],
                    color="#d62728", lw=1.2, alpha=0.9, label="EMG rectificado")
            ax.set_title("1B. Señal EMG filtrada + rectificada", fontsize=9)
            ax.set_ylabel("Amplitud (mV)", fontsize=8)
            ax.set_xlabel("Tiempo (s)", fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 2: Envolvente ---
        if 2 in ax_map:
            ax = ax_map[2]
            ax.plot(times, r["emg_rectified"],
                    color="#E74C3C", lw=1.2, alpha=0.6, label="EMG rectificado")
            ax.plot(times, r["emg_envelope"],
                    color="#9467bd", lw=2.0, label="Envolvente LP (fase cero)")
            ax.plot(times, r["rms_sliding"],
                    color="#2ca02c", lw=1.5, ls="--", label="Envolvente RMS")
            ax.set_title("2. Envolvente de la señal EMG", fontsize=9)
            ax.set_ylabel("Amplitud (mV)", fontsize=8)
            ax.set_xlabel("Tiempo (s)", fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 3: Envolvente normalizada ---
        if 3 in ax_map:
            ax = ax_map[3]
            ax.plot(times, r["emg_envelope_normalised"],
                    color="#9467bd", lw=1.8, label="Envolvente normalizada (max=1)")
            ax.axhline(1.0, color="#E74C3C", ls=":", lw=1.5, alpha=0.8)
            ax.set_title("3. Envolvente normalizada al máximo", fontsize=9)
            ax.set_ylabel("Amplitud normalizada (0–1)", fontsize=8)
            ax.set_xlabel("Tiempo (s)", fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.set_ylim(0, 1.15)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 4: PSD ---
        if 4 in ax_map:
            ax = ax_map[4]
            ax.plot(r["frequencies"], r["psd"], color="#0047AB", lw=1.8)
            ax.axvline(r["mnf"], color="#FF8C00", ls="--", lw=2.0,
                       label=f"MNF: {r['mnf']:.1f} Hz")
            ax.axvline(r["mdf"], color="#C71585", ls="--", lw=2.0,
                       label=f"MDF: {r['mdf']:.1f} Hz")
            ax.set_title("4. Densidad Espectral de Potencia (PSD)", fontsize=9)
            ax.set_xlabel("Frecuencia (Hz)", fontsize=8)
            ax.set_ylabel("PSD (mV²/Hz)", fontsize=8)
            ax.set_xlim(0, f_high + 50)
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7)
            ax.grid(True, **_grid)

        # --- 5: RMS por ventana ---
        if 5 in ax_map:
            ax = ax_map[5]
            ax.plot(r["t_seg"], r["rms_seg"],
                    color="#2ca02c", lw=1.5, marker="o", ms=4,
                    label="RMS por ventana de 1 s")
            ax.set_title("5. Evolución temporal de la Amplitud RMS", fontsize=9)
            ax.set_xlabel("Tiempo (s)", fontsize=8)
            ax.set_ylabel("RMS (mV)", fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 6: MDF vs tiempo ---
        if 6 in ax_map:
            ax = ax_map[6]
            ax.scatter(r["t_seg"], r["mdf_seg"],
                       s=20, alpha=0.7, color="#666666",
                       label="Frecuencia Mediana por ventana")
            if len(r["t_seg"]) >= 2:
                ax.plot(r["t_seg"], r["fat_fitted"],
                        color="#E74C3C", lw=2.5,
                        label="Tendencia (polinomio grado 2)")
            ax.set_title(
                "6. Tendencia de Fatiga: Frecuencia Mediana vs. Tiempo\n"
                "   (descenso = indicador de fatiga muscular)",
                fontsize=9, pad=8,
            )
            ax.set_xlabel("Tiempo (s)", fontsize=8)
            ax.set_ylabel("MDF (Hz)", fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 7: RMS vs MDF (scatter) ---
        if 7 in ax_map:
            ax = ax_map[7]
            t_seg = r["t_seg"]
            sc = ax.scatter(r["mdf_seg"], r["rms_seg"],
                            c=t_seg, cmap="viridis", s=60, alpha=0.8, zorder=3)
            ax.plot(r["rms_mdf_range"], r["rms_mdf_fitted"],
                    color="#E74C3C", lw=2.5, label="Ajuste polinómico grado 2")
            cbar = self._fig.colorbar(sc, ax=ax, orientation="vertical", pad=0.02)
            cbar.set_label("Tiempo (s)", fontsize=8)
            cbar.ax.tick_params(labelsize=7)
            ax.set_title("7. Relación Amplitud (Fuerza) vs. Frecuencia Mediana (Fatiga)", fontsize=9)
            ax.set_xlabel("MDF (Hz)", fontsize=8)
            ax.set_ylabel("RMS (mV)", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7)
            ax.grid(True, **_grid)

        self._axes_list = axes_list
        self._y_initial_lims = {pi: ax.get_ylim() for pi, ax in zip(selected, axes_list)}
        self._y_accum = {pi: 1.0 for pi in selected}
        self._canvas.setMinimumHeight(n_panels * 180)
        self._canvas.setMinimumWidth(0)
        self._canvas.draw_idle()
        self._rebuild_y_sidebar(selected)

    # ------------------------------------------------------------------
    # Guardar figura
    # ------------------------------------------------------------------

    @Slot()
    def _guardar_figura(self) -> None:
        if self._last_result is None:
            return
        carpeta = str(Path(self._last_result["edf_path"]).parent)
        nombre = Path(self._last_result["edf_path"]).stem + "_analisis_emg.png"
        ruta_default = str(Path(carpeta) / nombre)

        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar figura",
            ruta_default,
            "Imágenes PNG (*.png)",
        )
        if ruta:
            self._fig.savefig(ruta, dpi=150, bbox_inches="tight")
            self._logger.append_log(f"Figura guardada en: {ruta}")

    # ------------------------------------------------------------------
    # Marcadores
    # ------------------------------------------------------------------

    def _dibujar_marcadores(self, ax, inicio_s: float, fin_s: float) -> None:
        for t_mark, lbl_mark in self._markers:
            if inicio_s <= t_mark <= fin_s:
                ax.axvline(t_mark, color="#E67E22", linestyle="--",
                           linewidth=1.2, alpha=0.8)
                txt = (lbl_mark[:15] + "…") if len(lbl_mark) > 15 else lbl_mark
                ax.text(t_mark, ax.get_ylim()[1], txt,
                        fontsize=7, rotation=90, va="top", ha="right",
                        color="#E67E22")

    def _actualizar_lista_marcadores(self) -> None:
        sorted_m = sorted(self._markers, key=lambda x: x[0])
        n = len(sorted_m)
        self._lbl_markers_bar.setText(f"Marcadores ({n}):")
        self._combo_markers.blockSignals(True)
        self._combo_markers.clear()
        if sorted_m:
            for tiempo, etiqueta in sorted_m:
                self._combo_markers.addItem(f"t={tiempo:.1f} s — {etiqueta}")
            self._combo_markers.setEnabled(True)
            self._btn_ir_marcador.setEnabled(True)
        else:
            self._combo_markers.addItem("Sin marcadores")
            self._combo_markers.setEnabled(False)
            self._btn_ir_marcador.setEnabled(False)
        self._combo_markers.blockSignals(False)

    def _on_ir_marcador(self) -> None:
        sorted_m = sorted(self._markers, key=lambda x: x[0])
        idx = self._combo_markers.currentIndex()
        if idx < 0 or idx >= len(sorted_m):
            return
        tiempo, _ = sorted_m[idx]
        _, dur = self._time_range.get_range()
        nuevo_inicio = max(0.0, min(tiempo - dur / 2, self._duracion_total - dur))
        self._time_range.set_range(nuevo_inicio, dur)
        self._lbl_inicio_info.setText(f"Inicio: {nuevo_inicio:.1f} s")
        self._lbl_duracion_info.setText(f"Duración: {dur:.1f} s")
        self._sync_combo_zoom()
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)

    # ------------------------------------------------------------------
    # Escala vertical por panel
    # ------------------------------------------------------------------

    def _rebuild_y_sidebar(self, selected: list[int]) -> None:
        while self._y_scale_sidebar_layout.count():
            item = self._y_scale_sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for panel_idx, ax in zip(selected, self._axes_list):
            slot = QWidget()
            slot_vbox = QVBoxLayout(slot)
            slot_vbox.setContentsMargins(0, 0, 0, 0)
            slot_vbox.setSpacing(1)

            btn_up = QToolButton()
            btn_up.setText("▲")
            btn_up.setFixedSize(32, 18)
            btn_up.setStyleSheet("font-size: 9px;")
            btn_up.clicked.connect(
                lambda checked=False, a=ax, pi=panel_idx: self._y_zoom(pi, a, True)
            )

            lbl = QLabel(f"P{_PANEL_SHORT_NAMES[panel_idx]}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 7px; color: #666666;")

            btn_dn = QToolButton()
            btn_dn.setText("▼")
            btn_dn.setFixedSize(32, 18)
            btn_dn.setStyleSheet("font-size: 9px;")
            btn_dn.clicked.connect(
                lambda checked=False, a=ax, pi=panel_idx: self._y_zoom(pi, a, False)
            )

            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addStretch()

            self._y_scale_sidebar_layout.addWidget(slot, stretch=1)

    def _y_zoom(self, panel_idx: int, ax, zoom_in: bool) -> None:
        factor = 1.5
        accum = self._y_accum.get(panel_idx, 1.0)
        if zoom_in:
            new_accum = accum / factor
            if new_accum < 0.01:
                return
            ymin, ymax = ax.get_ylim()
            ax.set_ylim(ymin / factor, ymax / factor)
        else:
            new_accum = accum * factor
            if new_accum > 100.0:
                return
            ymin, ymax = ax.get_ylim()
            ax.set_ylim(ymin * factor, ymax * factor)
        self._y_accum[panel_idx] = new_accum
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Controles de escala temporal
    # ------------------------------------------------------------------

    @Slot()
    def _on_tiempo_ampliar(self) -> None:
        inicio, dur = self._time_range.get_range()
        nueva_dur = min(dur * 2.0, self._duracion_total)
        nueva_dur = max(nueva_dur, 0.5)
        nuevo_inicio = min(inicio, self._duracion_total - nueva_dur)
        self._time_range.set_range(nuevo_inicio, nueva_dur)
        self._lbl_inicio_info.setText(f"Inicio: {nuevo_inicio:.1f} s")
        self._lbl_duracion_info.setText(f"Duración: {nueva_dur:.1f} s")
        self._sync_combo_zoom()
        self._redraw_timer.start()

    @Slot()
    def _on_tiempo_reducir(self) -> None:
        inicio, dur = self._time_range.get_range()
        nueva_dur = max(dur / 2.0, 0.5)
        nuevo_inicio = min(inicio, self._duracion_total - nueva_dur)
        self._time_range.set_range(nuevo_inicio, nueva_dur)
        self._lbl_inicio_info.setText(f"Inicio: {nuevo_inicio:.1f} s")
        self._lbl_duracion_info.setText(f"Duración: {nueva_dur:.1f} s")
        self._sync_combo_zoom()
        self._redraw_timer.start()

    @Slot(int)
    def _on_combo_zoom_changed(self, index: int) -> None:
        factor = _ZOOM_FACTORS[index]
        nueva_dur = self._duracion_total / factor
        if nueva_dur < 0.5:
            return
        inicio, _ = self._time_range.get_range()
        nuevo_inicio = min(inicio, self._duracion_total - nueva_dur)
        self._time_range.set_range(nuevo_inicio, nueva_dur)
        self._lbl_inicio_info.setText(f"Inicio: {nuevo_inicio:.1f} s")
        self._lbl_duracion_info.setText(f"Duración: {nueva_dur:.1f} s")
        self._redraw_timer.start()

    def _sync_combo_zoom(self) -> None:
        if self._duracion_total <= 0:
            return
        _, dur = self._time_range.get_range()
        factor = self._duracion_total / dur
        best_idx, best_diff = 0, float("inf")
        for i, f in enumerate(_ZOOM_FACTORS):
            diff = abs(factor - f)
            if diff < best_diff:
                best_diff, best_idx = diff, i
        self._combo_zoom.blockSignals(True)
        self._combo_zoom.setCurrentIndex(best_idx)
        self._combo_zoom.blockSignals(False)

    def _update_combo_items(self) -> None:
        model = self._combo_zoom.model()
        for i, f in enumerate(_ZOOM_FACTORS):
            item = model.item(i)
            if item is None:
                continue
            enabled = (self._duracion_total / f) >= 0.5
            flags = item.flags()
            if enabled:
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            else:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_controles_habilitados(self, habilitado: bool) -> None:
        self._btn_abrir.setEnabled(habilitado)
        self._btn_analizar.setEnabled(habilitado and bool(self._edit_path.text()))
        self._edit_canal.setEnabled(habilitado)
        self._spin_fenv.setEnabled(habilitado)
        has_data = habilitado and self._last_result is not None
        self._time_range.setEnabled(has_data)
        self._btn_reset_ventana.setEnabled(has_data)
        self._btn_tiempo_ampliar.setEnabled(has_data)
        self._btn_tiempo_reducir.setEnabled(has_data)
        self._combo_zoom.setEnabled(has_data)

    def cleanup(self) -> None:
        """Llamado por MainWindow.closeEvent — cancela y espera al worker."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
