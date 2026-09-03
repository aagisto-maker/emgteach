# emgteach documentation

Welcome to the documentation for **emgteach**, an open-source teaching
platform for surface electromyography acquisition and analysis in the
physiology teaching laboratory, with a BITalino or an Arduino + MyoWare 2.0.

The application is configured by choosing one of **three practicals**; each
fixes what is recorded and what the analysis offers:

| Practical | Level | Channels | What it teaches |
|---|---|---|---|
| Single-muscle contraction | basic | 1 | amplitude, spectrum, fatigue, muscle load |
| Agonist / antagonist contraction | intermediate | 2 | two muscles compared in % MVC, co-activation |
| Muscle kinematics | advanced | 1 + accelerometer | force-velocity, electromechanical delay, tremor |

## Where to start

- **Installing and connecting** — the [README](https://github.com/aagisto-maker/emgteach#readme):
  Python 3.10–3.12, `pip install`, pairing the BITalino and identifying it by its
  MAC address.
- **Placing the electrodes** — [`colocacion_electrodos_antebrazo_es.md`](colocacion_electrodos_antebrazo_es.md)
  (Spanish): the forearm pair, measured from the bony landmarks, and how the
  maximum has to be made against the table.
- **Citing emgteach** — [`CITATION.cff`](https://github.com/aagisto-maker/emgteach/blob/main/CITATION.cff).

## User manual

A detailed manual — what the app does and the physiological meaning of every
metric — plus teaching materials, are available (English and Spanish):

- **User manual** — English: [`manual_emgteach.md`](manual_emgteach.md) ·
  Spanish: [`manual_emgteach_es.md`](manual_emgteach_es.md)
- **Lab practical guide** — English: [`lab_practicals.md`](lab_practicals.md) ·
  Spanish: [`guion_practicas_es.md`](guion_practicas_es.md)
- **Assessment rubric** — English: [`evaluation_rubric.md`](evaluation_rubric.md) ·
  Spanish: [`rubrica_evaluacion_es.md`](rubrica_evaluacion_es.md)
- **One‑page cheat sheet** — English: [`cheatsheet.md`](cheatsheet.md) ·
  Spanish: [`chuleta_es.md`](chuleta_es.md)

## Useful links

- Source code: <https://github.com/aagisto-maker/emgteach>
- Issue tracker: <https://github.com/aagisto-maker/emgteach/issues>
- Companion paper (reproducibility package): <https://doi.org/10.5281/zenodo.20042878>
