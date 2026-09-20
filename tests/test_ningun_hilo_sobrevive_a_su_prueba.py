"""No test may leave one of the QThread workers running behind it.

A worker started and not waited for is not a slow test: it is a thread the
session has lost track of. Whatever destroys it next -- a collection, the
``QApplication`` going down at the end -- finds it still inside ``run()``, and
Qt answers that with ``qFatal``, which aborts through ``__fastfail``. That is
not a signal, so nothing catches it; on Windows the runner's PowerShell
reports the ``0xC0000409`` as a plain ``1``, and what reaches the log is a job
that walked every test, printed no ``FAILED`` line and died in the middle of a
sentence. It happened twice on 19 September and cost two re-runs to guess at.

The one that caused it was ``mvc`` in ``test_auto_normalisation_emits_result``:
the only ``start()`` in ``test_workers.py`` without its ``wait()``, and the last
test of the last file, so nothing came after it to notice. The race is real and
narrow -- measured on a fast desktop, the thread was still inside ``run()`` at
the moment the test returned in 2 of 20 attempts -- which is why it showed up on
a loaded two-core runner and nowhere else.

This reads the sources rather than running anything, so it costs nothing and
catches the omission in the diff that introduces it instead of in a job that
aborts a fortnight later. It is deliberately narrow: only objects built from a
class whose name ends in ``Worker``, which are the QThread subclasses. A
``QTimer`` also has ``start()`` and has nothing to wait for.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).parent

# Ways of making sure the thread is not running any more. ``wait`` is the one
# this suite uses; the others are here so a legitimate alternative does not
# have to argue with the guard.
DESPEDIDAS = {"wait", "quit", "terminate"}


def _workers_started_without_waiting(tree: ast.Module) -> list[tuple[str, str, int]]:
    """``(function, variable, line)`` for every worker started and left running."""
    sueltos: list[tuple[str, str, int]] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        workers: set[str] = set()
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
                continue
            llamado = node.value.func
            clase = llamado.id if isinstance(llamado, ast.Name) else getattr(llamado, "attr", "")
            destinos = node.targets
            if clase.endswith("Worker") and len(destinos) == 1 and isinstance(destinos[0], ast.Name):
                workers.add(destinos[0].id)

        arrancados: dict[str, int] = {}
        despedidos: set[str] = set()
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if not isinstance(node.func.value, ast.Name):
                continue
            objeto = node.func.value.id
            if node.func.attr == "start":
                arrancados.setdefault(objeto, node.lineno)
            elif node.func.attr in DESPEDIDAS:
                despedidos.add(objeto)

        for objeto, linea in arrancados.items():
            if objeto in workers and objeto not in despedidos:
                sueltos.append((fn.name, objeto, linea))
    return sueltos


def test_every_worker_a_test_starts_is_waited_for() -> None:
    sueltos: list[str] = []
    for archivo in sorted(TESTS.glob("test_*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for funcion, objeto, linea in _workers_started_without_waiting(arbol):
            sueltos.append(
                f"{archivo.name}:{linea} — {funcion}() starts {objeto} and never "
                f"waits for it"
            )

    assert not sueltos, (
        "a worker thread left running outlives the test that started it, and "
        "whatever destroys it next aborts the whole session without saying why:\n  "
        + "\n  ".join(sueltos)
    )


def test_the_guard_can_tell_the_two_apart() -> None:
    """The guard has to catch the real thing and leave a QTimer alone."""
    suelto = ast.parse(
        "def t():\n"
        "    mvc = MvcWorker(edf_path='x')\n"
        "    mvc.start()\n"
    )
    assert _workers_started_without_waiting(suelto) == [("t", "mvc", 3)]

    esperado = ast.parse(
        "def t():\n"
        "    mvc = MvcWorker(edf_path='x')\n"
        "    mvc.start()\n"
        "    mvc.wait(15000)\n"
    )
    assert _workers_started_without_waiting(esperado) == []

    reloj = ast.parse(
        "def t():\n"
        "    timer = QTimer()\n"
        "    timer.start(50)\n"
    )
    assert _workers_started_without_waiting(reloj) == []
