"""The force-velocity plan opens with what the practical guide says.

On the bench the plan read two lifts per load while the guide says
three lifts per load by default. The code said three as well: the two was a
plan saved on that computer, which is what the button shows. The guide now
says the plan is kept per computer; this holds the default itself to the
guide, in the dialog, in the tab and in both languages of the guide.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_the_tab_and_the_guide_agree_on_three() -> None:
    from emgteach.gui.tabs.acquisition import FV_REPS_DEF

    assert FV_REPS_DEF == 3
    assert "tres por defecto" in (DOCS / "guion_practicas_es.md").read_text(encoding="utf-8")
    assert "three by default" in (DOCS / "lab_practicals.md").read_text(encoding="utf-8")


@pytest.mark.gui
def test_the_dialog_opens_on_the_tabs_default(qapp) -> None:
    from emgteach.gui.tabs.acquisition import FV_LIFT_DEF_S, FV_PREP_DEF_S, FV_REPS_DEF
    from emgteach.gui.widgets.force_velocity_plan_dialog import ForceVelocityPlanDialog

    dlg = ForceVelocityPlanDialog()
    assert dlg.reps() == FV_REPS_DEF
    assert dlg.prep_seconds() == FV_PREP_DEF_S
    assert dlg.window_seconds() == FV_LIFT_DEF_S
    dlg.deleteLater()
