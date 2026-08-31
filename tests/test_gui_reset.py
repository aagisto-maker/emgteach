"""GUI tests for the per-tab new-session reset (Analysis / MVC tabs).

Marked ``gui`` (needs a QApplication). They check that ``reset()`` returns a
tab to its just-opened state. The acquisition tab's reset is covered in
``test_gui_acquisition.py``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_analysis_reset(qapp) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "ana-reset")
    settings.clear()
    tab = AnalysisTab(LoggerWidget(), settings)

    tab._edit_path.setText("foo.edf")
    tab._edit_student.setText("Ada Lovelace")
    tab._edit_student_code.setText("A1")
    tab._last_result = {"sentinel": 1}
    tab._btn_informe.setEnabled(True)
    tab._btn_guardar.setEnabled(True)

    tab.reset()

    assert tab._last_result is None
    assert tab._edit_path.text() == ""
    assert tab._edit_student.text() == ""
    assert tab._edit_student_code.text() == ""
    assert not tab._btn_informe.isEnabled()
    assert not tab._btn_guardar.isEnabled()
    # The persisted student fields are cleared too.
    assert settings.value("analisis/student", "") == ""
    settings.clear()
    qapp.processEvents()   # flush deferred canvas draws before teardown
    tab.cleanup()


def test_mvc_reset(qapp) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.mvc import MvcTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "mvc-reset")
    settings.clear()
    tab = MvcTab(LoggerWidget(), settings)

    tab._edit_path.setText("foo.edf")
    tab._last_result = {"sentinel": 1}
    tab._btn_informe.setEnabled(True)
    tab._btn_guardar.setEnabled(True)

    tab.reset()

    assert tab._last_result is None
    assert tab._edit_path.text() == ""
    assert not tab._btn_informe.isEnabled()
    assert not tab._btn_guardar.isEnabled()
    assert tab._d_file.text() == "—"
    settings.clear()
    qapp.processEvents()   # flush deferred canvas draws before teardown
    tab.cleanup()
