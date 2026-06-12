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

try:
    matplotlib.use("QtAgg")
except Exception:
    # Headless environment (e.g. CI without a display): the GUI is never
    # rendered there, and the tabs create FigureCanvasQTAgg explicitly.
    pass
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
from emgteach.i18n import tr
from emgteach.io import list_edf_channels
from emgteach.workers import MvcWorker

# Factores de zoom temporal disponibles (mismos que tab_analisis)
_ZOOM_FACTORS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]

_BTN_ST = (
    "QToolButton { font-size: 9px; padding: 0px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
# Variante de mayor tipografía para los controles de ventana temporal, igual
# que en la pestaña de adquisición (_BTN_ST se reserva para los botones ▲▼).
_TBTN_ST = (
    "QToolButton { font-size: 11px; padding: 0px 2px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
_COMBO_ST = (
    "QComboBox { font-size: 11px; padding: 1px 3px; min-width: 60px; max-width: 76px; }"
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
        grp_ctrl = QGroupBox(tr("MVC normalisation parameters"))
        ctrl = QVBoxLayout(grp_ctrl)

        row_test = QHBoxLayout()
        row_test.addWidget(QLabel(tr("Test EDF:")))
        self._edit_path = QLineEdit()
        self._edit_path.setPlaceholderText(tr("Select the EDF file to normalise…"))
        self._edit_path.setReadOnly(True)
        row_test.addWidget(self._edit_path)
        self._btn_abrir = QPushButton(tr("Browse…"))
        self._btn_abrir.clicked.connect(self._seleccionar_edf_prueba)
        row_test.addWidget(self._btn_abrir)
        ctrl.addLayout(row_test)

        row_cvm = QHBoxLayout()
        row_cvm.addWidget(QLabel(tr("MVC reference EDF (optional):")))
        self._edit_cvm_path = QLineEdit()
        self._edit_cvm_path.setPlaceholderText(tr("Leave empty for auto-normalisation…"))
        self._edit_cvm_path.setReadOnly(True)
        row_cvm.addWidget(self._edit_cvm_path)
        self._btn_abrir_cvm = QPushButton(tr("Browse…"))
        self._btn_abrir_cvm.clicked.connect(self._seleccionar_edf_cvm)
        row_cvm.addWidget(self._btn_abrir_cvm)
        self._btn_limpiar_cvm = QPushButton(tr("Remove"))
        self._btn_limpiar_cvm.clicked.connect(self._limpiar_cvm)
        row_cvm.addWidget(self._btn_limpiar_cvm)
        ctrl.addLayout(row_cvm)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel(tr("EMG channel:")))
        self._combo_canal = QComboBox()
        self._combo_canal.setEditable(False)
        self._combo_canal.addItem("EMG")
        self._combo_canal.setFixedWidth(150)
        self._combo_canal.setToolTip(
            tr(
                "EMG channel of the EDF to normalise. Filled with the channels "
                "of the test file when you select it."
            )
        )
        row_params.addWidget(self._combo_canal)

        row_params.addWidget(QLabel(tr("Envelope cutoff frequency (Hz):")))
        self._spin_fenv = QDoubleSpinBox()
        self._spin_fenv.setRange(1.0, 20.0)
        self._spin_fenv.setSingleStep(0.5)
        self._spin_fenv.setValue(5.0)
        self._spin_fenv.setFixedWidth(80)
        row_params.addWidget(self._spin_fenv)

        row_params.addStretch()
        self._btn_calcular = QPushButton(tr("Compute MVC"))
        self._btn_calcular.setEnabled(False)
        self._btn_calcular.clicked.connect(self._iniciar_calculo)
        row_params.addWidget(self._btn_calcular)

        self._btn_guardar = QPushButton(tr("Save figure (PNG)"))
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
        grp_resumen = QGroupBox(tr("Normalisation summary"))
        grp_resumen.setContentsMargins(6, 4, 6, 4)
        resumen_layout = QHBoxLayout(grp_resumen)
        resumen_layout.setContentsMargins(6, 4, 6, 4)

        self._lbl_cvm_ref = QLabel(f"{tr('MVC reference:')} —")
        self._lbl_mean_norm = QLabel(f"{tr('Mean activation:')} —")
        for lbl in (self._lbl_cvm_ref, self._lbl_mean_norm):
            # Sin negrita y a 11 px para mantener la uniformidad tipográfica con
            # el resto de etiquetas del resumen.
            lbl.setStyleSheet("font-size: 11px; padding: 2px 8px;")
            resumen_layout.addWidget(lbl)

        self._lbl_fuente = QLabel(f"{tr('MVC source:')} —")
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
        grp_ventana = QGroupBox(tr("Display window"))
        ventana_layout = QHBoxLayout(grp_ventana)
        ventana_layout.setContentsMargins(6, 4, 6, 4)

        self._btn_tiempo_ampliar = QToolButton()
        self._btn_tiempo_ampliar.setText("◀▶")
        self._btn_tiempo_ampliar.setToolTip(tr("Widen the window (see more time)"))
        self._btn_tiempo_ampliar.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_ampliar.setFixedSize(32, 26)
        self._btn_tiempo_ampliar.setEnabled(False)
        self._btn_tiempo_ampliar.clicked.connect(self._on_tiempo_ampliar)
        ventana_layout.addWidget(self._btn_tiempo_ampliar)

        self._combo_zoom = QComboBox()
        self._combo_zoom.setStyleSheet(_COMBO_ST)
        self._combo_zoom.setFixedSize(76, 26)
        self._combo_zoom.setEnabled(False)
        for f in _ZOOM_FACTORS:
            self._combo_zoom.addItem(f"×{f}")
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)
        ventana_layout.addWidget(self._combo_zoom)

        self._btn_tiempo_reducir = QToolButton()
        self._btn_tiempo_reducir.setText("▶◀")
        self._btn_tiempo_reducir.setToolTip(tr("Narrow the window (more detail)"))
        self._btn_tiempo_reducir.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_reducir.setFixedSize(32, 26)
        self._btn_tiempo_reducir.setEnabled(False)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)
        ventana_layout.addWidget(self._btn_tiempo_reducir)

        ventana_layout.addSpacing(12)
        self._lbl_inicio_info = QLabel(f"{tr('Start:')} — s")
        self._lbl_inicio_info.setStyleSheet("font-size: 10px;")
        ventana_layout.addWidget(self._lbl_inicio_info)

        self._lbl_duracion_info = QLabel(f"{tr('Duration:')} — s")
        self._lbl_duracion_info.setStyleSheet("font-size: 10px;")
        ventana_layout.addWidget(self._lbl_duracion_info)

        ventana_layout.addStretch()

        self._btn_reset_ventana = QPushButton(tr("Reset window"))
        self._btn_reset_ventana.setFixedHeight(26)
        self._btn_reset_ventana.setStyleSheet("font-size: 10px;")
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
        # Zoom con la rueda del ratón sobre el panel bajo el cursor.
        self._canvas.mpl_connect("scroll_event", self._on_scroll_zoom)

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
            self, tr("Select test EDF"),
            self._last_edf_dir, tr("EDF files (*.edf *.EDF)"),
        )
        if path:
            self._edit_path.setText(path)
            self._last_edf_dir = str(Path(path).parent)
            self._settings.setValue("cvm/last_edf_dir", self._last_edf_dir)
            self._populate_channels(path)
            self._btn_calcular.setEnabled(True)
            self._btn_guardar.setEnabled(False)

    def _populate_channels(self, path: str) -> None:
        """Fill the channel picker from the test EDF header."""
        labels = list_edf_channels(path)
        if not labels:
            return
        current = self._combo_canal.currentText().strip()
        self._combo_canal.blockSignals(True)
        self._combo_canal.clear()
        self._combo_canal.addItems(labels)
        idx = self._combo_canal.findText(current)
        self._combo_canal.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo_canal.blockSignals(False)

    @Slot()
    def _seleccionar_edf_cvm(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Select MVC reference EDF"),
            self._last_cvm_dir, tr("EDF files (*.edf *.EDF)"),
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
        self._lbl_cvm_ref.setText(f"{tr('MVC reference:')} —")
        self._lbl_mean_norm.setText(f"{tr('Mean activation:')} —")
        self._lbl_fuente.setText(f"{tr('MVC source:')} —")

        self._worker = MvcWorker(
            edf_path=path,
            mvc_path=cvm_path,
            f_env=f_env,
            channel_index=self._combo_canal.currentIndex(),
        )
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
        self._lbl_cvm_ref.setText(f"{tr('MVC reference:')} {r['mvc_amplitude_ref']:.4f} {dim}")
        mean_norm = float(np.mean(r["emg_norm"][:r["n_plot"]]))
        self._lbl_mean_norm.setText(f"{tr('Mean activation:')} {mean_norm:.1f} % MVC")
        self._lbl_fuente.setText(f"{tr('MVC source:')} {r['mvc_source']}")

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
                color="royalblue", lw=0.8, label=tr("Filtered EMG (20-450 Hz)"))
        ax.plot(t_full, r["emg_rectified"][:n],
                color="tomato", lw=0.8, alpha=0.8, label=tr("Rectified EMG"))
        ax.set_xlim(inicio, fin)
        ax.set_title(tr("1. Filtered and rectified EMG signal"), fontsize=9)
        ax.set_ylabel(tr("Amplitude ({units})").format(units=r.get('dimension', '')), fontsize=8)
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.tick_params(labelsize=7)
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(True, color="#DDDDDD", alpha=0.5)

        # Panel 2: envolvente + línea CVM
        ax = axes[1]
        ax.plot(t_full, r["emg_envelope"][:n],
                color="purple", lw=2.0, label=tr("LP envelope (zero-phase)"))
        ax.axhline(r["mvc_amplitude_ref"], color="red", ls="--", lw=1.5,
                   label=tr("MVC ref: {value:.4f} {units}").format(
                       value=r["mvc_amplitude_ref"], units=r.get("dimension", "")))
        ax.set_xlim(inicio, fin)
        ax.set_title(tr("2. Envelope and MVC reference amplitude"), fontsize=9)
        ax.set_ylabel(tr("Amplitude ({units})").format(units=r.get('dimension', '')), fontsize=8)
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
        ax.tick_params(labelsize=7)
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(True, color="#DDDDDD", alpha=0.5)

        # Panel 3: señal normalizada % CVM
        ax = axes[2]
        ax.fill_between(t_full, r["emg_norm"][:n], alpha=0.25, color="darkorange")
        ax.plot(t_full, r["emg_norm"][:n],
                color="darkorange", lw=1.8, label=tr("Activation (% MVC)"))
        ax.axhline(100.0, color="red", ls=":", lw=1.2, alpha=0.7, label=tr("100 % MVC"))
        ax.set_xlim(inicio, fin)
        ax.set_title(tr("3. EMG signal normalised to MVC (% MVC)"), fontsize=9)
        ax.set_ylabel(tr("% MVC"), fontsize=8)
        ax.set_xlabel(tr("Time (s)"), fontsize=8)
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

    def _on_scroll_zoom(self, event) -> None:
        """Mouse-wheel zoom on the panel under the cursor (X and Y), centred
        on the cursor position."""
        ax = event.inaxes
        if ax is None or event.xdata is None or event.ydata is None:
            return
        scale = 1.0 / 1.2 if event.button == "up" else 1.2
        x, y = event.xdata, event.ydata
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ax.set_xlim(x - (x - x0) * scale, x + (x1 - x) * scale)
        ax.set_ylim(y - (y - y0) * scale, y + (y1 - y) * scale)
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
        self._lbl_inicio_info.setText(f"{tr('Start:')} {self._inicio_s:.1f} s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')} {self._duracion_s:.1f} s")

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
            self, tr("Save figure"), ruta_default, tr("PNG images (*.png)"),
        )
        if ruta:
            self._fig.savefig(ruta, dpi=150, bbox_inches="tight")
            self._logger.append_log(tr("Figure saved to: {path}").format(path=ruta))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_controles_habilitados(self, habilitado: bool) -> None:
        self._btn_abrir.setEnabled(habilitado)
        self._btn_abrir_cvm.setEnabled(habilitado)
        self._btn_limpiar_cvm.setEnabled(habilitado)
        self._btn_calcular.setEnabled(habilitado and bool(self._edit_path.text()))
        self._combo_canal.setEnabled(habilitado)
        self._spin_fenv.setEnabled(habilitado)

    def cleanup(self) -> None:
        """Llamado por MainWindow.closeEvent — cancela y espera al worker."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
