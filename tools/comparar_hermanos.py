#!/usr/bin/env python
"""Compara los módulos compartidos de esta app con los de sus hermanas.

emgteach, ecgteach y eegteach mantienen copias a mano de los mismos módulos
(dispositivos, difusión, recuperación, informe de fallos...). Este script
dice, módulo a módulo, en qué se ha separado la copia de esta app de la de
cada hermana, para que un arreglo hecho en una no se quede sin portar a las
otras. Se ejecuta a mano antes de cada versión; no es una prueba de pytest.

Uso, desde la raíz del repositorio (aquí, desde emgteach; desde ecgteach o
eegteach se dan las rutas de las otras dos):

    python tools/comparar_hermanos.py ../ecgteach ../eegteach
    python tools/comparar_hermanos.py ../ecgteach ../eegteach --modulo bitalino.py
    python tools/comparar_hermanos.py ../ecgteach --modulo crash.py --completo

Cada ruta es la raíz de un repositorio hermano, con su código en
``src/<app>/``. Se comparan los ficheros tal como están en disco (la rama que
tenga cada repositorio en ese momento, con sus cambios sin commit); el
encabezado de la salida dice qué commit y qué rama se leyeron. El script solo
lee: no escribe nada en ningún repositorio.

Antes de comparar se normalizan los nombres de paquete (emgteach, ecgteach,
eegteach -> XXteach) y de señal (EMG, ECG, EEG -> XX), para que no cuente como
diferencia lo que solo es el nombre de la app. Ojo: así se esconde también una
diferencia que sí sea de señal, como cuál es la ganancia por defecto del
sensor. ``--sin-normalizar-senal`` deja los nombres de señal como están.

Lista de módulos: la del §1 del plan de teachcore (emgteach,
docs/PLAN-teachcore.md). Si se añade o se retira un módulo compartido, se
cambia aquí, en las tres copias de este script.
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

APPS = ("emgteach", "ecgteach", "eegteach")

MODULOS = (
    "difusion.py",
    "devices/factory.py",
    "devices/arduino.py",
    "devices/base.py",
    "devices/bitalino.py",
    "devices/bitalino_sim.py",
    "broadcast.py",
    "crash.py",
    "recovery.py",
    "gui/widgets/logger.py",
    "gui/widgets/help_button.py",
)

RE_PAQUETE = re.compile(r"\b(emg|ecg|eeg)teach\b", re.IGNORECASE)
RE_SENAL = re.compile(r"\b(EMG|ECG|EEG)\b")
RE_SENAL_TITULO = re.compile(r"\b(Emg|Ecg|Eeg)")


@dataclass(frozen=True)
class Repo:
    raiz: Path
    app: str

    @property
    def paquete(self) -> Path:
        return self.raiz / "src" / self.app

    def leer(self, modulo: str) -> list[str] | None:
        ruta = self.paquete / modulo
        if not ruta.is_file():
            return None
        return ruta.read_text(encoding="utf-8").splitlines()

    def version_git(self) -> str:
        """Rama y commit que hay en disco, o un aviso si git no responde."""
        def git(*args: str) -> str:
            r = subprocess.run(["git", "-C", str(self.raiz), *args],
                               capture_output=True, text=True, check=False)
            return r.stdout.strip() if r.returncode == 0 else ""

        commit = git("rev-parse", "--short", "HEAD")
        if not commit:
            return "(no es un repositorio git)"
        rama = git("rev-parse", "--abbrev-ref", "HEAD")
        sucio = " con cambios sin commit" if git("status", "--porcelain", "--", "src") else ""
        return f"{rama} {commit}{sucio}"


def detectar(raiz: Path) -> Repo:
    """La app cuya raíz es ``raiz``: la única carpeta src/<app> que hay."""
    encontradas = [a for a in APPS if (raiz / "src" / a / "__init__.py").is_file()]
    if len(encontradas) != 1:
        raise SystemExit(
            f"{raiz}: no parece la raíz de emgteach, ecgteach ni eegteach "
            f"(se busca src/<app>/__init__.py)."
        )
    return Repo(raiz.resolve(), encontradas[0])


def normalizar(lineas: list[str], senal: bool) -> list[str]:
    salida = []
    for linea in lineas:
        linea = RE_PAQUETE.sub("XXteach", linea)
        if senal:
            linea = RE_SENAL.sub("XX", linea)
            linea = RE_SENAL_TITULO.sub("Xx", linea)
        salida.append(linea)
    return salida


@dataclass
class Comparacion:
    quitadas: int          # líneas de esta app que la hermana no tiene
    anadidas: int          # líneas de la hermana que esta app no tiene
    diff: list[str]

    @property
    def distintas(self) -> int:
        return self.quitadas + self.anadidas


def comparar(propia: list[str], ajena: list[str], nombre_propio: str,
             nombre_ajeno: str, contexto: int) -> Comparacion:
    diff = list(difflib.unified_diff(propia, ajena, nombre_propio, nombre_ajeno,
                                     lineterm="", n=contexto))
    cuerpo = [d for d in diff if not d.startswith(("---", "+++"))]
    quitadas = sum(1 for d in cuerpo if d.startswith("-"))
    anadidas = sum(1 for d in cuerpo if d.startswith("+"))
    return Comparacion(quitadas, anadidas, diff)


def celda(c: Comparacion | None, falta: str) -> str:
    if c is None:
        return falta
    return "idéntico" if c.distintas == 0 else f"{c.distintas} (-{c.quitadas} +{c.anadidas})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compara los módulos compartidos con los de las apps hermanas.")
    parser.add_argument("hermanos", nargs="+", type=Path,
                        help="raíz de cada repositorio hermano (por ejemplo ../ecgteach)")
    parser.add_argument("--modulo", action="append", default=[],
                        help="solo este módulo (por ejemplo bitalino.py); se puede repetir")
    parser.add_argument("--contexto", type=int, default=1,
                        help="líneas de contexto en el diff (por defecto 1)")
    parser.add_argument("--max-lineas", type=int, default=40,
                        help="líneas del diff que se muestran por módulo (por defecto 40)")
    parser.add_argument("--completo", action="store_true",
                        help="muestra el diff entero, sin recortar")
    parser.add_argument("--sin-normalizar-senal", action="store_true",
                        help="no cambia EMG, ECG y EEG por XX antes de comparar")
    args = parser.parse_args(argv)

    propio = detectar(Path(__file__).resolve().parents[1])
    hermanos = [detectar(r) for r in args.hermanos]
    for h in hermanos:
        if h.app == propio.app:
            raise SystemExit(f"{h.raiz} es {h.app}, la misma app que este repositorio.")

    modulos = list(MODULOS)
    if args.modulo:
        modulos = [m for m in MODULOS
                   if any(m == p or m.endswith("/" + p) for p in args.modulo)]
        if not modulos:
            raise SystemExit(f"Ningún módulo compartido se llama {', '.join(args.modulo)}. "
                             f"Los compartidos son: {', '.join(MODULOS)}.")
    senal = not args.sin_normalizar_senal

    print(f"Esta app: {propio.app}, {propio.version_git()} ({propio.raiz})")
    for h in hermanos:
        print(f"Hermana:  {h.app}, {h.version_git()} ({h.raiz})")
    print("Normalizado: nombres de paquete" + (" y de señal" if senal else "")
          + ". Líneas distintas: -N solo en esta app, +N solo en la hermana.")

    resumen: list[tuple[str, list[Comparacion | None], str]] = []
    for modulo in modulos:
        print()
        print("=" * 78)
        print(modulo)
        print("=" * 78)
        texto_propio = propio.leer(modulo)
        fila: list[Comparacion | None] = []
        if texto_propio is None:
            print(f"  {propio.app} no tiene este módulo.")
            resumen.append((modulo, [None] * len(hermanos), f"falta en {propio.app}"))
            continue
        for h in hermanos:
            texto_ajeno = h.leer(modulo)
            if texto_ajeno is None:
                print(f"  {h.app}: no tiene este módulo.")
                fila.append(None)
                continue
            c = comparar(normalizar(texto_propio, senal), normalizar(texto_ajeno, senal),
                         f"{propio.app}/{modulo}", f"{h.app}/{modulo}", args.contexto)
            fila.append(c)
            if c.distintas == 0:
                print(f"  {h.app}: idéntico.")
                continue
            print(f"  {h.app}: {c.distintas} líneas distintas "
                  f"(-{c.quitadas} solo en {propio.app}, +{c.anadidas} solo en {h.app}).")
            mostrar = c.diff if args.completo else c.diff[:args.max_lineas]
            for linea in mostrar:
                print("    " + linea)
            if len(mostrar) < len(c.diff):
                print(f"    ... {len(c.diff) - len(mostrar)} líneas más del diff; "
                      f"para verlo entero: --modulo {Path(modulo).name} --completo")
        resumen.append((modulo, fila, "falta"))

    print()
    print("=" * 78)
    print("Resumen: líneas distintas tras normalizar")
    print("=" * 78)
    ancho = max(len(m) for m in modulos)
    cabecera = f"{'módulo':<{ancho}}" + "".join(f"  {h.app:>20}" for h in hermanos)
    print(cabecera)
    print("-" * len(cabecera))
    iguales = 0
    for modulo, fila, falta in resumen:
        print(f"{modulo:<{ancho}}" + "".join(f"  {celda(c, falta):>20}" for c in fila))
        if fila and all(c is not None and c.distintas == 0 for c in fila):
            iguales += 1
    print("-" * len(cabecera))
    print(f"{iguales} de {len(resumen)} módulos son idénticos en "
          f"{' y '.join([propio.app, *(h.app for h in hermanos)])}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
