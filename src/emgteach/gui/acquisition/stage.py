"""What every guided flow of the acquisition tab asks of the world around it,
as a piece of the tab (step 4 of docs/PLAN-partir-AcquisitionTab.md).

The calibration, the countdown, the pair's task, the force-velocity loads
and the guided sessions all do the same few things at each of their phases:
tell the simulated subject what is being asked of each muscle (or let it be),
write the phase's annotation into the recording, sound the phase tone if the
box is ticked, and put a line under the panel. Those live here, once, so the
flows can be moved out of the tab one by one without each calling into
another for them.

Communication, the rule of the plan: the piece keeps no reference to the
tab. It is given ways to ask, each time, for the current worker, the number
of channels and whether the tone box is ticked, and the label it writes
under the panel; the flows call its methods.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QLabel

from emgteach import cue

if TYPE_CHECKING:
    from emgteach.workers.acquisition import AcquisitionWorker

__all__ = ["FlowStage"]


class FlowStage(QObject):
    """The subject, the file, the tone and the panel's line, for every flow."""

    def __init__(
        self,
        *,
        worker: Callable[[], AcquisitionWorker | None],
        n_channels: Callable[[], int],
        tone_on: Callable[[], bool],
        info_label: QLabel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        #: The recording's worker, asked for each time: the one running now.
        self._worker = worker
        #: How many muscles there are to tell, asked for each time.
        self._n_channels_of = n_channels
        #: Whether the «Tone» box is ticked, asked for at each tone.
        self._tone_on = tone_on
        #: The line under the load bars the flows write to.
        self._info_label = info_label

    @property
    def _n_channels(self) -> int:
        return self._n_channels_of()

    def instruct_device(self, channel_index: int, level: float | None,
                         *, repeat_s: float | None = None) -> None:
        """Say what is being asked of a muscle, if there is a device to tell.

        Only the simulated board acts on it; the call is harmless with any
        other, and with none at all.
        """
        worker = self._worker()
        if worker is not None and worker.isRunning():
            worker.instruct(channel_index, level, repeat_s=repeat_s)

    def ask_subject(self, pedido: dict[int, float], *,
                         repeat_s: float | None = None) -> None:
        """Say what every muscle is being asked for, and not only one.

        *pedido* is ``{channel: level}``; the channels left out are asked
        for rest, and an empty one asks every muscle to stay still. ``None``
        — give the subject back to itself — is :meth:`_soltar_al_sujeto`.

        One call per muscle, because the instruction is per muscle: the
        manoeuvre that works both at once could not be asked for at all
        while asking one meant «and the other rests».
        """
        for c in range(self._n_channels):
            nivel = pedido.get(c, 0.0)
            self.instruct_device(
                c, nivel, repeat_s=repeat_s if nivel > 0.0 else None)

    def release_subject(self) -> None:
        """Nothing is being asked any more: the device does what it does."""
        for c in range(self._n_channels):
            self.instruct_device(c, None)

    def write_phase_marker(self, label: str) -> None:
        """Write a phase annotation, if there is an open recording to write to.

        Calibrating without recording is still allowed — the reference lands
        in the next file as a cached ``MVC ref`` — and then there is no span
        to mark. Silently doing nothing is the right answer: the phases
        describe a file, and in that case there is no file yet.
        """
        worker = self._worker()
        if worker is not None and worker.isRunning():
            worker.add_marker(label)

    def tone(self, *, final: bool = False) -> None:
        """A phase change of any guided flow, said with a tone if the box is ticked.

        The calibration, the countdown to the recording, the pair's task,
        the force-velocity loads and the guided sessions alike (Ángel, 25 Oct
        2026: the tone in every experiment of the application). *final* is
        the end of a whole guided task: two falling notes, so that «finished»
        is not heard as «next».
        """
        if not self._tone_on():
            return
        if final:
            cue.beep_end()
        else:
            cue.beep()

    def info(self, text: str) -> None:
        """Show the wizard's current instruction (small info label)."""
        self._info_label.setText(text)
