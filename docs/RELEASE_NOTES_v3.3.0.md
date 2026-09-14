# emgteach 3.3.0 — the task maximum is a maximum of the recording phase

A minor version, not a patch, because one figure the program shows can
change: the task maximum is now read on the whole recording phase, whatever
fragments are chosen. Nothing else that is computed changes. The MVC
reference, the co-activation index and its floor, the contraction table and
the fatigue analysis are those of 3.2.0.

## Changed

- **The task maximum is read on the whole recording phase.** From the start
  of the recording to the end of the file, or the whole file when the
  recording has no phases, whatever fragments or window are chosen: a
  maximum of the phase, not of the selection. It was read on the analysed
  span, which with chosen fragments is their concatenation. There, two
  fragments cut inside their contractions and glued together lifted the
  envelope above either real peak (five points on the example recording),
  and a burst outside the fragments was not seen at all. On the bench
  recordings, with the fragments the editor proposes — which start and end
  at rest — the two readings agree within 0.05 points on 18 of 28 recordings
  and within 0.35 points on another 7 (the filter run on a concatenation
  rather than on the phase); on the remaining 3 the phase maximum lies in
  activity the editor's proposal had left out, and is 2 to 11 points higher.
  The card's help and the summary's say where it is read; `task_peak_span_s`
  in the result says which seconds of the file.
- **Panel 3 draws each spectrum scaled to unit area.** The PSD goes with the
  square of the amplitude, so in mV²/Hz the height of one muscle against the
  other compared skin and electrode placement — what the % MVC panels exist
  not to compare — and the muscle that contracts less was pinned to the axis
  and could not be read. Each curve is now a density, with its area shaded
  and its MDF line splitting the shade in two equal halves, in both muscles
  alike; the axis says «relative spectral density (area 1)»; the legend
  carries each muscle's MDF and its total power in mV², so the power is not
  lost; and a muscle whose power is under 2 % of the other's is drawn faint
  and its legend asks whether it is noise. MDF and MNF are invariant to the
  scaling: nothing computed changes. The screen and the report draw the panel
  from one function, `emgteach.figures.draw_psd_panel`.

## What the example recordings give

Nothing cited changes. On the three-manoeuvre recording the task maximum is
68.4 % (flexor) and 41.2 % (extensor) read either way; on the pair
recording, 100.5 % and 81.5 %. The co-activation table, the contraction
table and the fatigue analysis are untouched.

## Unchanged, on purpose

The MVC reference (the envelope's peak, best of the repetitions kept), the
150 % limit, the 5× rest-to-reference ratio, the 4.5 % co-activation floor,
the envelope chain, the calibration protocol and the file format.

## Meta

- Bumped to 3.3.0 (`pyproject.toml`, `__init__`, `.zenodo.json`,
  `CITATION.cff`).
- New `tests/test_maximo_de_la_fase.py` and `tests/test_espectro_relativo.py`.
  **1093 automated tests.**
- The version-specific Zenodo DOI is to be minted at release.
