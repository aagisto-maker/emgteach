"""The pair is agonist/antagonist, not «the forearm's flexor and extensor».

The engine never knew any anatomy — it works on channel 1 and channel 2, and
the teacher names the muscles — but the guided session's instructions had
converged on one pair: the wizard told the subject to clench the fist,
whichever two muscles the electrodes were on. The rule is the same for any
pair, the gesture is not, so each instruction states the rule first and names
the forearm behind it, as the example of the practical guide.

These two tests are the guard: one over the texts a subject reads while doing
the manoeuvre, one over the modules that compute.
"""

from __future__ import annotations

import ast
import pathlib
import re

from emgteach import i18n
from emgteach.profiles import EMG_PROFILE

#: Anything that names one pair of muscles, in either language.
ANATOMIA = re.compile(
    r"wrist|forearm|fist|\bFCR\b|\bECR\b|flexor|extensor|biceps|triceps"
    r"|muñeca|antebrazo|puño|bíceps|tríceps",
    re.IGNORECASE,
)
#: What every calibration instruction has to say before any of that.
PRINCIPIO = {
    "en": "brief, explosive jerk",
    "es": "Sacudida breve y explosiva",
}


def _la_regla() -> list[tuple[str, str]]:
    """The one calibration instruction, as ``(language, text)``.

    One, now: the rule. The gesture that illustrates it is the pair's and
    lives in :mod:`emgteach.pairs`, so it cannot be written before the rule
    even by accident — it is a separate sentence, said after.
    """
    claves = [k for k in i18n._ES
              if k.startswith("A brief, explosive jerk")]
    assert len(claves) == 1, claves
    return [("en", claves[0]), ("es", i18n._ES[claves[0]])]


def test_the_calibration_instruction_is_the_rule_and_names_no_pair() -> None:
    for lang, texto in _la_regla():
        assert PRINCIPIO[lang] in texto, (lang, texto)
        assert not ANATOMIA.search(texto), (lang, texto)


def test_the_example_comes_after_the_rule_for_every_pair() -> None:
    """What the wizard actually says, assembled as the tab assembles it."""
    from emgteach.pairs import PAIRS, pair_calibration_cue

    for lang in ("en", "es"):
        anterior = i18n.get_language()
        try:
            i18n.set_language(lang)
            regla = _la_regla()[0 if lang == "en" else 1][1]
            for par in PAIRS:
                for canal in (0, 1):
                    ejemplo = pair_calibration_cue(par, canal)
                    frase = f"{regla} {ejemplo}." if ejemplo else regla
                    assert PRINCIPIO[lang] in frase
                    anatomia = ANATOMIA.search(frase)
                    if anatomia is None:
                        continue           # «another pair»: the rule on its own
                    assert frase.index(PRINCIPIO[lang]) < anatomia.start(), (lang, par, frase)
        finally:
            i18n.set_language(anterior)

def test_the_montage_warning_and_the_paper_labels_name_no_muscle() -> None:
    # The montage warning asks for the limb to be supported, whichever it is.
    aviso = next(k for k in i18n._ES if k.startswith("{pairs}. Move the electrode pairs"))
    for texto in (aviso, i18n._ES[aviso]):
        assert not ANATOMIA.search(texto), texto

    # The labels of the pair practical are the roles, with the forearm as an example.
    from emgteach.gui.tabs.acquisition import _LABEL_FALLBACKS

    for etiqueta in (f() for f in _LABEL_FALLBACKS):
        assert not ANATOMIA.search(etiqueta), etiqueta


def test_nothing_that_computes_names_a_muscle() -> None:
    """The calculations stay neutral: any pair, named by the teacher.

    Docstrings and comments may name the forearm — they explain where the
    default limits were measured, which is the point of saying it — so only
    the code and the strings it builds are checked.
    """
    raiz = pathlib.Path(i18n.__file__).parent
    culpables: list[str] = []
    for nombre in ("dsp.py", "apda.py", "mvc.py", "coactivation.py", "fatigue.py",
                   "contractions.py", "selection.py", "phases.py", "profiles.py"):
        arbol = ast.parse((raiz / nombre).read_text(encoding="utf-8"))
        docs = {
            texto
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            if (texto := ast.get_docstring(nodo, clean=False)) is not None
        }
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                    and nodo.value not in docs and ANATOMIA.search(nodo.value)):
                culpables.append(f"{nombre}:{nodo.lineno} {nodo.value[:50]!r}")
            if isinstance(nodo, ast.Name | ast.Attribute):
                texto = getattr(nodo, "id", None) or getattr(nodo, "attr", "")
                if ANATOMIA.search(texto):
                    culpables.append(f"{nombre}:{nodo.lineno} {texto}")
    assert not culpables, "el motor nombra músculos: " + "; ".join(culpables)


def test_the_measured_limits_say_where_they_were_measured() -> None:
    """The numbers are not neutral, and the code and the interface say so.

    The co-activation floor, the cross-talk share and the calibration ranges
    were measured on the forearm pair of the practical guide. Another pair has
    its own resting level and its own cross-talk, so they are defaults to
    check — and a default nobody knows came from one pair is a default nobody
    checks.
    """
    from emgteach.profiles import __doc__ as profiles_doc

    assert profiles_doc is not None
    assert "FCR and ECR" in profiles_doc and "defaults to check" in profiles_doc

    ayuda = next(k for k in i18n._ES
                 if k.startswith("When either muscle's mean activation above rest"))
    for texto in (ayuda, i18n._ES[ayuda]):
        assert "FCR" in texto and "ECR" in texto, texto
    assert EMG_PROFILE.coact_floor_pct == 4.5      # the measured value the texts name
