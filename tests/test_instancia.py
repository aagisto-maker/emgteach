"""Una sola copia de la aplicación a la vez.

En un ordenador de aula lento la aplicación tarda en dar señales de vida, y la
respuesta normal ante eso es volver a hacer clic. Cada clic arrancaba otra
copia; solo una acababa funcionando y las demás había que cerrarlas a mano.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid

import pytest

pytestmark = pytest.mark.gui


def _nombre() -> str:
    """Un canal propio por prueba: nunca el de una aplicación de verdad."""
    return f"emgteach-prueba-{uuid.uuid4().hex[:12]}"


def _esperar(qapp, condicion, segundos: float) -> bool:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        qapp.processEvents()
        if condicion():
            return True
        time.sleep(0.02)
    qapp.processEvents()
    return condicion()


class TestTheFirstCopyAnswers:
    def test_with_nobody_there_the_copy_starts(self, qapp) -> None:
        from emgteach.instancia import avisar_a_la_otra

        assert avisar_a_la_otra(_nombre(), espera_ms=200) is False

    def test_a_later_copy_knocks_and_the_first_hears_it(self, qapp) -> None:
        from emgteach.instancia import GuardiaDeInstancia, avisar_a_la_otra

        nombre = _nombre()
        guardia = GuardiaDeInstancia(nombre)
        assert guardia.escuchar()
        oidas: list[int] = []
        guardia.activar.connect(lambda: oidas.append(1))
        try:
            assert avisar_a_la_otra(nombre) is True
            assert _esperar(qapp, lambda: bool(oidas), 5.0)
        finally:
            guardia.cerrar()

    def test_the_channel_is_named_after_the_user(self) -> None:
        """Dos personas en la misma máquina son dos aplicaciones, y el nombre
        de usuario puede traer espacios o acentos que un canal no admite."""
        from emgteach.instancia import nombre_del_servidor

        nombre = nombre_del_servidor()
        assert nombre.startswith("emgteach-")
        assert all(c.isalnum() or c in "-_." for c in nombre)


class TestASecondLaunchOpensNoWindow:
    """La segunda ejecución termina sin ventana nueva.

    La segunda copia corre en su propio proceso, como la de un segundo clic.
    Si llegara a construir la ventana se quedaría dentro del bucle de eventos
    y la prueba acabaría por tiempo; además comprueba que ni siquiera carga la
    interfaz, que es lo que la hace salir deprisa en un equipo lento.
    """

    def test_it_leaves_without_building_the_interface(self, qapp) -> None:
        from emgteach.instancia import GuardiaDeInstancia

        nombre = _nombre()
        guardia = GuardiaDeInstancia(nombre)
        assert guardia.escuchar()
        oidas: list[int] = []
        guardia.activar.connect(lambda: oidas.append(1))
        codigo = (
            "import sys\n"
            "from emgteach.instancia import lanzar\n"
            f"rc = lanzar({nombre!r})\n"
            "print('CON-INTERFAZ' if 'emgteach.gui.app' in sys.modules "
            "else 'SIN-INTERFAZ')\n"
            "sys.exit(rc)\n"
        )
        entorno = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        proc = subprocess.Popen(
            [sys.executable, "-c", codigo], env=entorno,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            # El bucle de eventos de esta copia tiene que girar para atender
            # la llamada, igual que el de la aplicación que ya está abierta.
            assert _esperar(qapp, lambda: proc.poll() is not None, 120.0), (
                "la segunda copia no terminó: se ha quedado abierta"
            )
            salida, errores = proc.communicate(timeout=10)
            assert proc.returncode == 0, errores
            assert "SIN-INTERFAZ" in salida
            assert _esperar(qapp, lambda: bool(oidas), 5.0), (
                "la copia abierta no se enteró de que la llamaban"
            )
        finally:
            if proc.poll() is None:
                proc.kill()
            guardia.cerrar()

    def test_the_command_line_entry_goes_through_the_check(self) -> None:
        """El ejecutable y el comando ``emgteach`` entran por el mismo sitio."""
        import inspect

        import emgteach.__main__ as entrada

        assert "lanzar" in inspect.getsource(entrada.main)
