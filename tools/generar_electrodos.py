"""Render the forearm electrode-placement figure, in both languages.

    python tools/generar_electrodos.py

Writes ``docs/electrodos_antebrazo_<lang>.svg``. Hand-authored SVG rather than
matplotlib: this is anatomy, and the shapes matter more than the plotting.

The figure exists because "put the electrodes on the muscle belly" is not an
instruction anyone can follow precisely. What makes placement repeatable is a
**bony landmark to measure from** — the epicondyles and the styloid processes
are palpable through the skin on everyone — plus a palpation test to confirm
the muscle underneath is the intended one. Both are drawn.

The radial and ulnar sides are labelled in every panel on purpose. Turning a
forearm from the volar to the dorsal view swaps left and right, and a reader
who works it out from the silhouette alone has a fair chance of putting the
extensor pair on the ulnar side, over the wrong muscle entirely.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs"

W, H = 1000, 830

#: The forearm silhouette, elbow at the top, hand at the bottom. Reused from
#: the figure drafted for the manuscript, which had the anatomy right and the
#: labelling generic.
BRAZO = (
    "M {x0} 132 C {a} 214, {b} 276, {c} 356 C {d} 376, {e} 388, {f} 401 "
    "C {g} 426, {h} 456, {i} 478 L {j} 478 C {j} 456, {k} 431, {m} 414 "
    "L {n} 414 L {n} 478 L {o} 478 L {o} 414 L {p} 414 L {p} 478 L {q} 478 "
    "L {q} 414 L {r} 414 C {s} 431, {t} 456, {t} 478 L {u} 478 "
    "C {v} 456, {w} 426, {x} 401 C {y} 388, {z} 376, {A} 356 "
    "C {B} 276, {C} 214, {D} 132 C {E} 118, {F} 118, {x0} 132 Z"
)

TEXTOS = {
    "es": {
        "titulo": "Colocación de electrodos · par agonista/antagonista de la muñeca",
        "sub": "Antebrazo derecho. Sujeto sentado, codo a 90°, antebrazo apoyado y en pronación.",
        "volar": "Cara anterior (volar) · Canal 1",
        "dorsal": "Cara posterior (dorsal) · Canal 2",
        "m1": "Flexor radial del carpo",
        "m1b": "(flexor carpi radialis)",
        "m2": "Extensores radiales del carpo",
        "m2b": "(ext. carpi radialis longus + brevis)",
        "epi_med": "Epicóndilo medial",
        "epi_lat": "Epicóndilo lateral",
        "est_rad": "Estiloides radial",
        "muneca_dorso": "Centro del dorso\nde la muñeca",
        "radial": "radial\n(pulgar)",
        "cubital": "cubital\n(meñique)",
        "tercio": "⅓ de la línea",
        "dos_cm": "2 cm",
        "ref": "Referencia",
        "prueba1": "Comprobar: flexión de muñeca contra resistencia.\nEl vientre se endurece bajo los electrodos.",
        "prueba2": "Comprobar: extensión de muñeca con el puño cerrado.\nEl relieve aparece justo distal al epicóndilo.",
        "leyenda_reg": "Electrodos de registro",
        "leyenda_reg_txt": "dos por músculo, separados 2 cm de centro a centro y alineados con las fibras (a lo largo del músculo).",
        "leyenda_ref": "Electrodo de referencia",
        "leyenda_ref_txt": "sobre hueso, donde no hay músculo: olécranon o estiloides cubital. Uno por sensor.",
        "pie": "Piel limpia, seca y sin crema. Si la señal sale pequeña, desplace el par 1–2 cm en sentido distal y repita la comprobación.",
    },
    "en": {
        "titulo": "Electrode placement · the wrist agonist/antagonist pair",
        "sub": "Right forearm. Seated, elbow at 90°, forearm supported and pronated.",
        "volar": "Anterior (volar) aspect · Channel 1",
        "dorsal": "Posterior (dorsal) aspect · Channel 2",
        "m1": "Flexor carpi radialis",
        "m1b": "(wrist flexor)",
        "m2": "Extensor carpi radialis",
        "m2b": "(longus + brevis, wrist extensors)",
        "epi_med": "Medial epicondyle",
        "epi_lat": "Lateral epicondyle",
        "est_rad": "Radial styloid",
        "muneca_dorso": "Middle of the\ndorsal wrist",
        "radial": "radial\n(thumb)",
        "cubital": "ulnar\n(little finger)",
        "tercio": "⅓ of the line",
        "dos_cm": "2 cm",
        "ref": "Reference",
        "prueba1": "Check: resisted wrist flexion.\nThe belly hardens under the electrodes.",
        "prueba2": "Check: wrist extension with a closed fist.\nThe bulge appears just distal to the epicondyle.",
        "leyenda_reg": "Recording electrodes",
        "leyenda_reg_txt": "two per muscle, 2 cm apart centre to centre, aligned with the fibres (along the muscle).",
        "leyenda_ref": "Reference electrode",
        "leyenda_ref_txt": "on bone, clear of muscle: olecranon or ulnar styloid. One per sensor.",
        "pie": "Skin clean, dry and free of cream. If the signal is small, move the pair 1–2 cm distally and check again.",
    },
}


def _brazo(x: float) -> str:
    """The silhouette translated so its centre line sits at ``x``."""
    off = x - 250.0
    puntos = {
        "x0": 190, "a": 180, "b": 184, "c": 220, "d": 210, "e": 206, "f": 208,
        "g": 204, "h": 206, "i": 212, "j": 220, "k": 222, "m": 226, "n": 242,
        "o": 248, "p": 258, "q": 264, "r": 274, "s": 278, "t": 280, "u": 288,
        "v": 294, "w": 296, "x": 292, "y": 294, "z": 290, "A": 280, "B": 316,
        "C": 320, "D": 310, "E": 280, "F": 220,
    }
    return BRAZO.format(**{k: v + off for k, v in puntos.items()})


def _electrodo(x: float, y: float, r: float = 10.0) -> str:
    return (
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#33383F" stroke="#C9CDD2" '
        f'stroke-width="2.5"/>'
        f'<circle cx="{x}" cy="{y}" r="{r * 0.34}" fill="#C9CDD2"/>'
    )


def _hueso(x: float, y: float, etiqueta: str, anchor: str, dx: float) -> str:
    """A palpable bony landmark: the thing placement is measured from."""
    return (
        f'<circle cx="{x}" cy="{y}" r="6.5" fill="#FFFFFF" stroke="#1F3A5F" '
        f'stroke-width="2.4"/>'
        f'<circle cx="{x}" cy="{y}" r="2.2" fill="#1F3A5F"/>'
        f'<line x1="{x + dx * 0.18}" y1="{y}" x2="{x + dx * 0.82}" y2="{y}" '
        f'stroke="#1F3A5F" stroke-width="1.1" stroke-dasharray="3 2"/>'
        f'<text x="{x + dx}" y="{y + 4}" font-size="12.5" '
        f'text-anchor="{anchor}" fill="#1F3A5F" font-weight="600">'
        f'{etiqueta}</text>'
    )


def _multilinea(x: float, y: float, texto: str, size: float, anchor: str,
                fill: str, weight: str = "400", lh: float = 15.0) -> str:
    out = []
    for i, linea in enumerate(texto.split("\n")):
        out.append(
            f'<text x="{x}" y="{y + i * lh}" font-size="{size}" '
            f'text-anchor="{anchor}" fill="{fill}" font-weight="{weight}">'
            f'{linea}</text>'
        )
    return "".join(out)


def _panel(cx: float, t: dict, volar: bool) -> str:
    """One view. ``volar`` also decides which side of the panel is radial."""
    p: list[str] = []
    p.append(f'<path d="{_brazo(cx)}" fill="url(#piel)" stroke="#A9744C" '
             f'stroke-width="2.2" stroke-linejoin="round"/>')
    # Thumb on the radial side; nails only on the dorsal view.
    if volar:
        p.append(f'<path d="M {cx - 40} 376 C {cx - 64} 376, {cx - 72} 396, '
                 f'{cx - 60} 412 C {cx - 52} 422, {cx - 44} 414, {cx - 40} 406 Z" '
                 f'fill="url(#piel)" stroke="#A9744C" stroke-width="2"/>')
    else:
        p.append(f'<path d="M {cx + 40} 376 C {cx + 64} 376, {cx + 72} 396, '
                 f'{cx + 60} 412 C {cx + 52} 422, {cx + 44} 414, {cx + 40} 406 Z" '
                 f'fill="url(#piel)" stroke="#A9744C" stroke-width="2"/>')
        for i in range(4):
            p.append(f'<rect x="{cx - 79 + i * 11}" y="422" width="7" '
                     f'height="6" rx="2" fill="#E9C39F" stroke="#A9744C" '
                     f'stroke-width="0.8"/>')

    # Radial / ulnar, said outright: the two views mirror each other, and
    # working it out from the drawing is how the pair ends up on the wrong
    # muscle.
    lado_radial = cx - 108 if volar else cx + 108
    lado_cubital = cx + 108 if volar else cx - 108
    p.append(_multilinea(lado_radial, 330, t["radial"], 11.5, "middle",
                         "#7A6A55", lh=13))
    p.append(_multilinea(lado_cubital, 330, t["cubital"], 11.5, "middle",
                         "#7A6A55", lh=13))

    # The construction line, from the epicondyle to the distal landmark.
    if volar:
        epi = (cx + 58, 146)          # medial epicondyle: ulnar side
        dist = (cx - 26, 358)         # radial styloid
        etiqueta_epi, etiqueta_dist = t["epi_med"], t["est_rad"]
        anchor_epi, dx_epi = "start", 76
        anchor_dist, dx_dist = "end", -70
    else:
        epi = (cx + 58, 146)          # lateral epicondyle: radial side
        dist = (cx + 4, 358)          # middle of the dorsal wrist
        etiqueta_epi, etiqueta_dist = t["epi_lat"], t["muneca_dorso"]
        anchor_epi, dx_epi = "start", 76
        anchor_dist, dx_dist = "start", 74

    p.append(f'<line x1="{epi[0]}" y1="{epi[1]}" x2="{dist[0]}" y2="{dist[1]}" '
             f'stroke="#1F3A5F" stroke-width="1.4" stroke-dasharray="6 4" '
             f'opacity="0.65"/>')
    mx = epi[0] + (dist[0] - epi[0]) / 3.0
    my = epi[1] + (dist[1] - epi[1]) / 3.0

    # The muscle belly, centred on the third-point.
    p.append(f'<ellipse cx="{mx}" cy="{my + 10}" rx="31" ry="56" '
             f'fill="#C0392B" fill-opacity="0.16" stroke="#C0392B" '
             f'stroke-opacity="0.35" stroke-width="1.2"/>')

    # The pair, along the muscle, 2 cm apart.
    p.append(_electrodo(mx, my - 12))
    p.append(_electrodo(mx, my + 32))
    p.append(f'<line x1="{mx - 24}" y1="{my - 12}" x2="{mx - 24}" '
             f'y2="{my + 32}" stroke="#33383F" stroke-width="1"/>')
    for yy in (my - 12, my + 32):
        p.append(f'<line x1="{mx - 28}" y1="{yy}" x2="{mx - 20}" y2="{yy}" '
                 f'stroke="#33383F" stroke-width="1"/>')
    p.append(f'<text x="{mx - 32}" y="{my + 14}" font-size="11.5" '
             f'text-anchor="end" fill="#33383F">{t["dos_cm"]}</text>')

    # The tick that says where along the line the pair goes.
    p.append(f'<line x1="{mx - 7}" y1="{my}" x2="{mx + 7}" y2="{my}" '
             f'stroke="#1F3A5F" stroke-width="2"/>')
    p.append(f'<text x="{mx + 46}" y="{my - 30}" font-size="12" '
             f'fill="#1F3A5F" font-weight="600">{t["tercio"]}</text>')

    p.append(_hueso(*epi, etiqueta_epi, anchor_epi, dx_epi))
    p.append(_hueso(*dist, etiqueta_dist.replace("\n", " "),
                    anchor_dist, dx_dist))

    # Reference, on bone at the wrist, ulnar side.
    rx = cx + 44 if volar else cx - 44
    p.append(f'<circle cx="{rx}" cy="378" r="8.5" fill="#2E8B57" '
             f'stroke="#DFF0E6" stroke-width="2.4"/>'
             f'<circle cx="{rx}" cy="378" r="3" fill="#DFF0E6"/>')
    return "".join(p)


def construir(lang: str) -> str:
    t = TEXTOS[lang]
    # Panels pulled inwards: at 738 the dorsal wrist label ran
    # into the right edge.
    izq, der = 252.0, 702.0
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'font-family="Liberation Sans, Arial, Helvetica, sans-serif">',
        '<defs><linearGradient id="piel" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#F6DCC2"/>'
        '<stop offset="0.5" stop-color="#F0CBA8"/>'
        '<stop offset="1" stop-color="#E3B58C"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
        f'<text x="{W / 2}" y="38" font-size="20" font-weight="bold" '
        f'text-anchor="middle" fill="#16202A">{t["titulo"]}</text>',
        f'<text x="{W / 2}" y="62" font-size="13" text-anchor="middle" '
        f'fill="#55636F">{t["sub"]}</text>',
    ]
    for cx, cab, m, mb, volar, prueba in (
        (izq, t["volar"], t["m1"], t["m1b"], True, t["prueba1"]),
        (der, t["dorsal"], t["m2"], t["m2b"], False, t["prueba2"]),
    ):
        out.append(f'<text x="{cx}" y="96" font-size="14.5" '
                   f'font-weight="bold" text-anchor="middle" '
                   f'fill="#0D7D7D">{cab}</text>')
        out.append(f'<text x="{cx}" y="116" font-size="13.5" '
                   f'text-anchor="middle" fill="#16202A" '
                   f'font-weight="600">{m}</text>')
        out.append(f'<text x="{cx}" y="132" font-size="11.5" '
                   f'text-anchor="middle" fill="#55636F">{mb}</text>')
        # The drawing sits below the two heading lines rather than starting
        # at the top of the panel: the muscle's latin name fell inside the
        # forearm otherwise.
        out.append(f'<g transform="translate(0,34)">{_panel(cx, t, volar)}</g>')
        out.append(_multilinea(cx, 556, prueba, 11.5, "middle", "#55636F",
                               lh=14))

    y0 = 614
    out.append(f'<rect x="56" y="{y0}" width="{W - 112}" height="112" rx="9" '
               f'fill="#F7F4EF" stroke="#D9CBB8"/>')
    out.append(_electrodo(88, y0 + 28, 9))
    out.append(f'<text x="108" y="{y0 + 32}" font-size="13" fill="#16202A">'
               f'<tspan font-weight="bold">{t["leyenda_reg"]}</tspan>: '
               f'{t["leyenda_reg_txt"]}</text>')
    out.append(f'<circle cx="88" cy="{y0 + 60}" r="9" fill="#2E8B57" '
               f'stroke="#DFF0E6" stroke-width="2.3"/>'
               f'<circle cx="88" cy="{y0 + 60}" r="3" fill="#DFF0E6"/>')
    out.append(f'<text x="108" y="{y0 + 64}" font-size="13" fill="#16202A">'
               f'<tspan font-weight="bold">{t["leyenda_ref"]}</tspan>: '
               f'{t["leyenda_ref_txt"]}</text>')
    out.append(f'<circle cx="88" cy="{y0 + 90}" r="6.5" fill="#FFFFFF" '
               f'stroke="#1F3A5F" stroke-width="2.4"/>'
               f'<circle cx="88" cy="{y0 + 90}" r="2.2" fill="#1F3A5F"/>')
    out.append(f'<text x="108" y="{y0 + 94}" font-size="13" fill="#1F3A5F">'
               f'{t["pie"]}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for lang in ("es", "en"):
        ruta = DESTINO / f"electrodos_antebrazo_{lang}.svg"
        ruta.write_text(construir(lang), encoding="utf-8")
        print(f"  {ruta.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
