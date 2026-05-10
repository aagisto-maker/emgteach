"""
MvcTab — pestaña 3: normalización CVM (Contracción Voluntaria Máxima).

Carga un EDF de prueba y, opcionalmente, un EDF de referencia CVM.
Normaliza la envolvente EMG como % del CVM de referencia (percentil 95).
Si no se proporciona archivo CVM, usa auto-normalización sobre la propia
señal de prueba.

Controles:
  - Selector de archivo EDF de prueba (ruta persistida en QSettings)
  - Selector de archivo EDF de referencia CVM (opcional, persistido)
  - Nombre del canal EMG
  - Frecuencia de corte de la envolvente (editable, por defecto 5.0 Hz)
  - Botón Calcular / Guardar figura
  - Indicador de progreso (indeterminado mientras el worker corre)

Controles de escala (misma lógica que tab_analisis.py):
  - Escala vertical: sidebar ▲▼ por panel (×1.5, límites 0.01×–100×)
  - Escala temporal: botones ◀▶ + desplegable de factores

Panel de resumen: amplitud CVM de referencia, activación media, fuente.
Gráfica: 3 paneles matplotlib (señal filtrada / envolvente / normalizada % CVM).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
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

from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.workers import MvcWorker

# Factores de zoom temporal disponibles (mismos que tab_analisis)
_ZOOM_FACTORS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]

_BTN_ST = (
    "QToolButton { font-size: 9px; padding: 0px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
_COMBO_ST = (
    "QComboBox { font-size: 9px; padding: 1px 2px; min-width: 54px; max-width: 66px; }"
)


class MvcTab(QWidget):
    def __init__(self, logger: LoggerWidget, settings: QSettings, parent=None):
        super().__init__(parent)
        self._logger = logger
        self._settings = settings
        self._worker: MvcWorker | None = None
        self._last_result: dict | None = None
        self._last_edf_dir: str = self._settings.value("cvm/last_edf_dir", ".")
        self._last_cvm_dir: str = self._settings.value("cvm/last_cvm_dir", ".")

        # ── Estado escala vertical (3 paneles: 0=filtrada, 1=envolvente, 2=norm) ──
        self._y_accum: dict[int, float] = {0: 1.0, 1: 1.0, 2: 1.0}
        self._y_initial_lims: dict[int, tuple[float, float]] = {}
        self._axes_list: list = []   # ejes matplotlib activos

        # ── Estado escala temporal ──
        self._duracion_total: float = 60.0   # s; actualizada al cargar EDF
        self._inicio_s: float = 0.0
        self._duracion_s: float = 60.0

        # Debounce para el redibujado (400 ms, igual que tab_analisis)
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

        # ── Panel de controles ──────────────────────────────────────────
        grp_ctrl = QGroupBox("Parámetros de normalización CVM")
        ctrl = QVBoxLayout(grp_ctrl)

        row_test = QHBoxLayout()
        row_test.addWidget(QLabel("EDF de prueba:"))
        self._edit_path = QLineEdit()
        self._edit_path.setPlaceholderText("Selecciona el archivo EDF a normalizar…")
        self._edit_path.setReadOnly(True)
        row_test.addWidget(self._edit_path)
        self._btn_abrir = QPushButton("Explorar…")
        self._btn_abrir.clicked.connect(self._seleccionar_edf_prueba)
        row_test.addWidget(self._btn_abrir)
        ctrl.addLayout(row_test)

        row_cvm = QHBoxLayout()
        row_cvm.addWidget(QLabel("EDF de referencia CVM (opcional):"))
        self._edit_cvm_path = QLineEdit()
        self._edit_cvm_path.setPlaceholderText("Dejar vacío para auto-normalización…")
        self._edit_cvm_path.setReadOnly(True)
        row_cvm.addWidget(self._edit_cvm_path)
        self._btn_abrir_cvm = QPushButton("Explorar…")
        self._btn_abrir_cvm.clicked.connect(self._seleccionar_edf_cvm)
        row_cvm.addWidget(self._btn_abrir_cvm)
        self._btn_limpiar_cvm = QPushButton("Quitar")
        self._btn_limpiar_cvm.clicked.connect(self._limpiar_cvm)
        row_cvm.addWidget(self._btn_limpiar_cvm)
        ctrl.addLayout(row_cvm)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Canal EMG:"))
        self._edit_canal = QLineEdit("EMG")
        self._edit_canal.setFixedWidth(100)
        row_params.addWidget(self._edit_canal)

        row_params.addWidget(QLabel("Frec. corte envolvente (Hz):"))
        self._spin_fenv = QDoubleSpinBox()
        self._spin_fenv.setRange(1.0, 20.0)
        self._spin_fenv.setSingleStep(0.5)
        self._spin_fenv.setValue(5.0)
        self._spin_fenv.setFixedWidth(80)
        row_params.addWidget(self._spin_fenv)

        row_params.addStretch()
        self._btn_calcular = QPushButton("Calcular CVM")
        self._btn_calcular.setEnabled(False)
        self._btn_calcular.clicked.connect(self._iniciar_calculo)
        row_params.addWidget(self._btn_calcular)

        self._btn_guardar = QPushButton("Guardar figura (PNG)")
        self._btn_guardar.setEnabled(False)
        self._btn_guardar.clicked.connect(self._guardar_figura)
        row_params.addWidget(self._btn_guardar)

        ctrl.addLayout(row_params)
        root.addWidget(grp_ctrl)

        # ── Barra de progreso ───────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # ── Panel de resumen numérico ───────────────────────────────────
        grp_resumen = QGroupBox("Resumen de normalización")
        grp_resumen.setContentsMargins(6, 4, 6, 4)
        resumen_layout = QHBoxLayout(grp_resumen)
        resumen_layout.setContentsMargins(6, 4, 6, 4)

        self._lbl_cvm_ref = QLabel("CVM referencia: —")
        self._lbl_mean_norm = QLabel("Activación media: —")
        for lbl in (self._lbl_cvm_ref, self._lbl_mean_norm):
            lbl.setStyleSheet("font-size: 13px; font-weight: bold; padding: 2px 8px;")
            resumen_layout.addWidget(lbl)

        self._lbl_fuente = QLabel("Fuente CVM: —")
        self._lbl_fuente.setStyleSheet("font-size: 11px; color: #555555; padding: 2px 6px;")
        resumen_layout.addWidget(self._lbl_fuente)

        resumen_layout.addStretch()

        self._lbl_archivo = QLabel("")
        self._lbl_archivo.setStyleSheet("font-size: 11px; color: #444444; padding: 2px 4px;")
        self._lbl_archivo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        resumen_layout.addWidget(self._lbl_archivo)

        fm = QFontMetrics(grp_resumen.font())
        grp_resumen.setMaximumHeight(fm.lineSpacing() * 3 + 8)
        root.addWidget(grp_resumen)

        # ── Controles de escala temporal ────────────────────────────────
        grp_ventana = QGroupBox("Ventana de visualización")
        ventana_layout = QHBoxLayout(grp_ventana)
        ventana_layout.setContentsMargins(6, 4, 6, 4)

        self._btn_tiempo_ampliar = QToolButton()
        self._btn_tiempo_ampliar.setText("◀▶")
        self._btn_tiempo_ampliar.setToolTip("Ampliar ventana (ver más tiempo)")
        self._btn_tiempo_ampliar.setStyleSheet(_BTN_ST)
        self._btn_tiempo_ampliar.setFixedSize(28, 22)
        self._btn_tiempo_ampliar.setEnabled(False)
        self._btn_tiempo_ampliar.clicked.connect(self._on_tiempo_ampliar)
        ventana_layout.addWidget(self._btn_tiempo_ampliar)

        self._combo_zoom = QComboBox()
        self._combo_zoom.setStyleSheet(_COMBO_ST)
        self._combo_zoom.setFixedSize(66, 22)
        self._combo_zoom.setEnabled(False)
        for f in _ZOOM_FACTORS:
            self._combo_zoom.addItem(f"×{f}")
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)
        ventana_layout.addWidget(self._combo_zoom)

        self._btn_tiempo_reducir = QToolButton()
        self._btn_tiempo_reducir.setText("▶◀")
        self._btn_tiempo_reducir.setToolTip("Reducir ventana (más detalle)")
        self._btn_tiempo_reducir.setStyleSheet(_BTN_ST)
        self._btn_tiempo_reducir.setFixedSize(28, 22)
        self._btn_tiempo_reducir.setEnabled(False)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)
        ventana_layout.addWidget(self._btn_tiempo_reducir)

        ventana_layout.addSpacing(12)
        self._lbl_inicio_info = QLabel("Inicio: — s")
        self._lbl_inicio_info.setStyleSheet("font-size: 9px;")
        ventana_layout.addWidget(self._lbl_inicio_info)

        self._lbl_duracion_info = QLabel("Duración: — s")
        self._lbl_duracion_info.setStyleSheet("font-size: 9px;")
        ventana_layout.addWidget(self._lbl_duracion_info)

        ventana_layout.addStretch()

        self._btn_reset_ventana = QPushButton("Reset ventana")
        self._btn_reset_ventana.setFixedHeight(22)
        self._btn_reset_ventana.setStyleSheet("font-size: 9px;")
        self._btn_reset_ventana.setEnabled(False)
        self._btn_reset_ventana.clicked.connect(self._reset_ventana)
        ventana_layout.addWidget(self._btn_reset_ventana)

        root.addWidget(grp_ventana)

        # ── Canvas matplotlib + sidebar de escala vertical ──────────────
        self._fig = Figure(constrained_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Sidebar ▲▼ (se reconstruye tras cada dibujo, igual que en tab_analisis)
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

    # ------------------------------------------------------------------
    # Slots de selección de archivos
    # ------------------------------------------------------------------

    @Slot()
    def _seleccionar_edf_prueba(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar EDF de prueba",
            self._last_edf_dir, "Archivos EDF (*.edf *.EDF)",
        )
        if path:
            self._edit_path.setText(path)
            self._last_edf_dir = str(Path(path).parent)
            self._settings.setValue("cvm/last_edf_dir", self._last_edf_dir)
            self._btn_calcular.setEnabled(True)
            self._btn_guardar.setEnabled(False)

    @Slot()
    def _seleccionar_edf_cvm(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar EDF de referencia CVM",
            self._last_cvm_dir, "Archivos EDF (*.edf *.EDF)",
        )
        if path:
            self._edit_cvm_path.setText(path)
            self._last_cvm_dir = str(Path(path).parent)
            self._settings.setValue("cvm/last_cvm_dir", self._last_cvm_dir)

    @Slot()
    def _limpiar_cvm(self) -> None:
        self._edit_cvm_path.clear()

    # ------------------------------------------------------------------
    # Lanzar cálculo
    # ------------------------------------------------------------------

    @Slot()
    def _iniciar_calculo(self) -> None:
        path = self._edit_path.text().strip()
        cvm_path = self._edit_cvm_path.text().strip()
        f_env = self._spin_fenv.value()

        self._set_controles_habilitados(False)
        self._progress.setVisible(True)
        self._btn_guardar.setEnabled(False)
        self._lbl_cvm_ref.setText("CVM referencia: —")
        self._lbl_mean_norm.setText("Activación media: —")
        self._lbl_fuente.setText("Fuente CVM: —")

        self._worker = MvcWorker(edf_path=path, mvc_path=cvm_path, f_env=f_env)
        self._worker.result_ready.connect(self._on_result)
        self._worker.log.connect(self._logger.append_log)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    # ------------------------------------------------------------------
    # Slots del worker
    # ------------------------------------------------------------------

    @Slot(dict)
    def _on_result(self, result: dict) -> None:
        self._last_result = result
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)
        self._btn_guardar.setEnabled(True)
        self._actualizar_resumen(result)

        # Inicializar ventana temporal: 1/3 de la duración total
        t_total = float(result["t_plot"][-1]) if len(result["t_plot"]) > 0 else 60.0
        self._duracion_total = t_total
        dur_ini = t_total / 3.0
        self._inicio_s = 0.0
        self._duracion_s = dur_ini

        # Habilitar controles de escala temporal
        for w in (self._btn_tiempo_ampliar, self._btn_tiempo_reducir,
                  self._combo_zoom, self._btn_reset_ventana):
            w.setEnabled(True)
        self._sync_combo_zoom()
        self._update_info_labels()

        # Reset escalas Y y dibujar
        self._y_accum = {0: 1.0, 1: 1.0, 2: 1.0}
        self._dibujar_paneles(result)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._logger.append_error(msg)
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)

    # ------------------------------------------------------------------
    # Resumen numérico
    # ------------------------------------------------------------------

    def _actualizar_resumen(self, r: dict) -> None:
        self._lbl_archivo.setText(Path(r["edf_path"]).name)
        dim = r.get("dimension", "")
        self._lbl_cvm_ref.setText(f"CVM referencia: {r['mvc_amplitude_ref']:.4f} {dim}")
        mean_norm = float(np.mean(r["emg_norm"][:r["n_plot"]]))
        self._lbl_mean_norm.setText(f"Activación media: {mean_norm:.1f} % CVM")
        self._lbl_fuente.setText(f"Fuente CVM: {r['mvc_source']}")

    # ------------------------------------------------------------------
    # Dibujo de los 3 paneles
    # ------------------------------------------------------------------

    def _dibujar_paneles(self, r: dict) -> None:
        self._fig.clear()

        n = r["n_plot"]
        t_full = r["t_plot"]

        # Ventana temporal: selección por xlim (datos completos, ajuste de eje)
        inicio = self._inicio_s
        fin = inicio + self._duracion_s

        axes = self._fig.subplots(3, 1, sharex=False)
        self._axes_list = list(axes)

        # Panel 1: señal filtrada + rectificada
        ax = axes[0]
        ax.plot(t_full, r["emg_filtered"][:n],
                color="royalblue", lw=0.8, label="EMG filtrada (20-450 Hz)")
        ax.plot(t_full, r["emg_rectified"][:n],
                color="tomato", lw=0.8, alpha=0.8, label="EMG rectificada")
        ax.set_xlim(inicio, fin)
        ax.set_title("1. Señal EMG filtrada y rectificada", fontsize=9)
        ax.set_ylabel(f"Amplitud ({r.get('dimension', '')})", fontsize=8)
        ax.set_xlabel("Tiempo (s)", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(True, color="#DDDDDD", alpha=0.5)

        # Panel 2: envolvente + línea CVM
        ax = axes[1]
        ax.plot(t_full, r["emg_envelope"][:n],
                color="purple", lw=2.0, label="Envolvente LP (fase cero)")
        ax.axhline(r["mvc_amplitude_ref"], color="red", ls="--", lw=1.5,
                   label=f"CVM ref: {r['mvc_amplitude_ref']:.4f} {r.get('dimension', '')}")
        ax.set_xlim(inicio, fin)
        ax.set_title("2. Envolvente y amplitud de referencia CVM", fontsize=9)
        ax.set_ylabel(f"Amplitud ({r.get('dimension', '')})", fontsize=8)
        ax.set_xlabel("Tiempo (s)", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(True, color="#DDDDDD", alpha=0.5)

        # Panel 3: señal normalizada % CVM
        ax = axes[2]
        ax.fill_between(t_full, r["emg_norm"][:n], alpha=0.25, color="darkorange")
        ax.plot(t_full, r["emg_norm"][:n],
                color="darkorange", lw=1.8, label="Activación (% CVM)")
        ax.axhline(100.0, color="red", ls=":", lw=1.2, alpha=0.7, label="100 % CVM")
        ax.set_xlim(inicio, fin)
        ax.set_title("3. Señal EMG normalizada al CVM (% CVM)", fontsize=9)
        ax.set_ylabel("% CVM", fontsize=8)
        ax.set_xlabel("Tiempo (s)", fontsize=8)
        ax.set_ylim(0, r["ylim_max"])
        ax.tick_params(labelsize=7)
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(True, color="#DDDDDD", alpha=0.5)

        # Guardar ylims iniciales y resetear acumuladores
        self._y_initial_lims = {i: ax.get_ylim() for i, ax in enumerate(self._axes_list)}
        self._y_accum = {i: 1.0 for i in range(3)}

        w, h = self._fig.get_size_inches()
        dpi = self._fig.dpi
        self._canvas.setMinimumSize(int(w * dpi), int(h * dpi))
        self._canvas.updateGeometry()
        self._canvas.draw_idle()

        # Reconstruir sidebar ▲▼
        self._rebuild_y_sidebar()

    def _redibujar_con_ventana_actual(self) -> None:
        """Redibuja aplicando la ventana temporal actual sin reanalizar."""
        if self._last_result is None:
            return
        self._dibujar_paneles(self._last_result)

    # ------------------------------------------------------------------
    # Sidebar de escala vertical (▲▼ por panel)
    # ------------------------------------------------------------------

    def _rebuild_y_sidebar(self) -> None:
        # Limpiar widgets anteriores
        while self._y_scale_sidebar_layout.count():
            item = self._y_scale_sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        labels_panel = ["P1", "P2", "P3"]
        for panel_idx, ax in enumerate(self._axes_list):
            slot = QWidget()
            slot_vbox = QVBoxLayout(slot)
            slot_vbox.setContentsMargins(0, 0, 0, 0)
            slot_vbox.setSpacing(1)

            btn_up = QToolButton()
            btn_up.setText("▲")
            btn_up.setFixedSize(32, 18)
            btn_up.setStyleSheet(_BTN_ST)
            btn_up.clicked.connect(
                lambda checked=False, a=ax, pi=panel_idx: self._y_zoom(pi, a, True)
            )

            lbl = QLabel(labels_panel[panel_idx])
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 7px; color: #666666;")

            btn_dn = QToolButton()
            btn_dn.setText("▼")
            btn_dn.setFixedSize(32, 18)
            btn_dn.setStyleSheet(_BTN_ST)
            btn_dn.clicked.connect(
                lambda checked=False, a=ax, pi=panel_idx: self._y_zoom(pi, a, False)
            )

            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl,    alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addStretch()

            self._y_scale_sidebar_layout.addWidget(slot, stretch=1)

    def _y_zoom(self, panel_idx: int, ax, zoom_in: bool) -> None:
        """Ajusta el rango Y del panel `panel_idx` por factor ×1.5."""
        factor = 1.5
        accum = self._y_accum.get(panel_idx, 1.0)
        if zoom_in:
            new_accum = accum / factor
            if new_accum < 0.01:
                return
            ymin, ymax = ax.get_ylim()
            centro = (ymin + ymax) / 2
            half = (ymax - ymin) / 2 / factor
            ax.set_ylim(centro - half, centro + half)
        else:
            new_accum = accum * factor
            if new_accum > 100.0:
                return
            ymin, ymax = ax.get_ylim()
            centro = (ymin + ymax) / 2
            half = (ymax - ymin) / 2 * factor
            ax.set_ylim(centro - half, centro + half)
        self._y_accum[panel_idx] = new_accum
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Controles de escala temporal
    # ------------------------------------------------------------------

    @Slot()
    def _on_tiempo_ampliar(self) -> None:
        """◀▶ — dobla la duración visible."""
        nueva_dur = min(self._duracion_s * 2.0, self._duracion_total)
        nueva_dur = max(nueva_dur, 0.5)
        nuevo_inicio = min(self._inicio_s, self._duracion_total - nueva_dur)
        self._inicio_s = nuevo_inicio
        self._duracion_s = nueva_dur
        self._sync_combo_zoom()
        self._update_info_labels()
        self._redraw_timer.start()

    @Slot()
    def _on_tiempo_reducir(self) -> None:
        """▶◀ — divide la duración visible a la mitad."""
        nueva_dur = max(self._duracion_s / 2.0, 0.5)
        nuevo_inicio = min(self._inicio_s, self._duracion_total - nueva_dur)
        self._inicio_s = nuevo_inicio
        self._duracion_s = nueva_dur
        self._sync_combo_zoom()
        self._update_info_labels()
        self._redraw_timer.start()

    @Slot(int)
    def _on_combo_zoom_changed(self, index: int) -> None:
        factor = _ZOOM_FACTORS[index]
        nueva_dur = self._duracion_total / factor
        nueva_dur = max(nueva_dur, 0.5)
        nuevo_inicio = min(self._inicio_s, self._duracion_total - nueva_dur)
        self._inicio_s = nuevo_inicio
        self._duracion_s = nueva_dur
        self._update_info_labels()
        self._redraw_timer.start()

    def _sync_combo_zoom(self) -> None:
        if self._duracion_total <= 0:
            return
        factor_actual = self._duracion_total / self._duracion_s
        best_idx, best_diff = 0, float("inf")
        for i, f in enumerate(_ZOOM_FACTORS):
            d = abs(factor_actual - f)
            if d < best_diff:
                best_diff, best_idx = d, i
        self._combo_zoom.blockSignals(True)
        self._combo_zoom.setCurrentIndex(best_idx)
        self._combo_zoom.blockSignals(False)

        model = self._combo_zoom.model()
        for i, f in enumerate(_ZOOM_FACTORS):
            item = model.item(i)
            if item:
                item.setEnabled((self._duracion_total / f) >= 0.5)

    def _update_info_labels(self) -> None:
        self._lbl_inicio_info.setText(f"Inicio: {self._inicio_s:.1f} s")
        self._lbl_duracion_info.setText(f"Duración: {self._duracion_s:.1f} s")

    @Slot()
    def _reset_ventana(self) -> None:
        """Vuelve a inicio=0, duración=1/3 del total."""
        self._inicio_s = 0.0
        self._duracion_s = self._duracion_total / 3.0
        self._sync_combo_zoom()
        self._update_info_labels()
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)  # sin debounce (acción explícita)

    # ------------------------------------------------------------------
    # Guardar figura
    # ------------------------------------------------------------------

    @Slot()
    def _guardar_figura(self) -> None:
        if self._last_result is None:
            return
        carpeta = str(Path(self._last_result["edf_path"]).parent)
        nombre = Path(self._last_result["edf_path"]).stem + "_cvm_norm.png"
        ruta_default = str(Path(carpeta) / nombre)
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar figura", ruta_default, "Imágenes PNG (*.png)",
        )
        if ruta:
            self._fig.savefig(ruta, dpi=150, bbox_inches="tight")
            self._logger.append_log(f"Figura guardada en: {ruta}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_controles_habilitados(self, habilitado: bool) -> None:
        self._btn_abrir.setEnabled(habilitado)
        self._btn_abrir_cvm.setEnabled(habilitado)
        self._btn_limpiar_cvm.setEnabled(habilitado)
        self._btn_calcular.setEnabled(habilitado and bool(self._edit_path.text()))
        self._edit_canal.setEnabled(habilitado)
        self._spin_fenv.setEnabled(habilitado)

    def cleanup(self) -> None:
        """Llamado por MainWindow.closeEvent — cancela y espera al worker."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
