# emgteach — Lab cheat sheet (2 pages)

**Step 0: choose the practical.** Drop-down in the top-right corner. The band
beside it names the level. Everything else follows from that choice.

| Practical | Level | Channels | What it measures |
|---|---|---|---|
| **Single-muscle contraction** | basic | 1 | amplitude, spectrum, fatigue, load |
| **Agonist / antagonist contraction** | intermediate | 2 | two muscles in % MVC, co-activation |
| **Muscle kinematics** | advanced | 1 + accelerometer | force-velocity, electromechanical delay, tremor |

**«Guide»** replays the five-step walkthrough; every box has a **«?»** in its
corner saying what it does.

**The 3 tabs** · **Acquisition**: record · **Analysis**: read a recording (analysed
on its own when opened) · **MVC normalisation**: the task in % MVC and its load.

**Signal chain:** raw → *50 Hz notch + 20–450 Hz band-pass* → rectified →
**envelope** (5 Hz low-pass). *Only the raw signal goes into the EDF; the rest is
recomputed.* BITalino full scale ±1.635 mV.

---

### Record (Acquisition)
1. **Connect**. Only the single-muscle practical chooses the device; the other two
   are BITalino. Identify it by its **MAC**. Type the muscle **labels** (Muscle 1 =
   A1) and the **test identifier**.
2. **Start recording**. In the pair, the wizard calibrates both muscles before the
   task. In the other two, **«Calibrate MVC»** while recording.
3. **Stop**: the EDF is saved and the whole session appears with its phases.
- **Calibration**: 10 s warm-up; per muscle, **3 brief maximal efforts**
  (1.5 s). Reference = the best 0.2 s of the three.
- **The maximum is made against the table, never against a hand.** FCR: **fist
  closed**, palm up under the table edge. ECR: back of the hand against the top.
  Wrist about 20° towards the side opposite to the muscle's action.
- **Auto-onset** marks each contraction by itself (threshold = rest + k × noise,
  k = 3).
- **Load bars** after calibrating: 🟢 up to 40 % · 🟠 up to 70 % · 🔴 above.

### Following the session on a phone
Tick **«Broadcast to phones (in the laboratory)»** → **QR** or the link
`http://…:8070/?k=…`. Same Wi-Fi, with `http://`. Each activation changes the code.

### Analyse (Analysis)
The recording is analysed on its own when opened. Follow the boxes that appear, in
order:
1. **«Calibration repetitions…»**: drop the weak ones. First, because it fixes the
   reference of every percentage.
2. **«Select fragments…»**: one row per contraction; untick the bad ones (and, in
   the single-muscle practical, the calibration efforts) and **«Use these
   fragments»**. Two live sliders: **sensitivity** and, in the pair, the
   **co-activation threshold**; a click on a shaded stretch drops or restores
   it; the fine adjustment stays folded.

Then read: **panels** (mouse wheel to scroll; ▲▼ amplitude, ▶◀ time), the
**contraction chart** (one view at a time, on its title: **Relation**, amplitude
against MDF with one muscle or one muscle against the other with the
co-activation wedge in the pair; in the pair **Category** and **Who leads**;
**Series**; in kinematics **By load**; and **Table** with the numbers), the
**summary** cards, and in the pair the **co-activation chart** (one bar per
window with the index, with its own «Chart · Table»).
**«Generate PDF report»** = the deliverable.

Panels per practical: single **1A · 2 · 3**; pair **1A · 1B · 3 · 7 · 9**;
kinematics **1A · 2 · 3 · 10 · 11 · 12**. **«More panels…»** reveals the rest.

### Normalise and load (MVC normalisation)
Computed on its own when the recording arrives. **«Select fragments…»** to keep
only the task (without the calibration). Data panel: P10 / P50 / P90 and their
limits.

---

### What the numbers mean
| Measure | Meaning | Orientative |
|---|---|---|
| **RMS** | how much the muscle activates (non-linear with force) | rest ≈ 0.01 mV · effort 0.1–1 mV |
| **Peak (% MVC)** | the effort against its own maximum | task 20–80 % · > 150 % = the calibration was not maximal |
| **MNF / MDF** | mean / median frequency of the spectrum | 80–170 / 60–150 Hz |
| **MDF ↓ over time** | **fatigue** (a negative slope that fits, R² ≥ 0.30) | «not conclusive» = the recording does not answer |
| **Co-activation index** | activity shared by the two muscles | reciprocal: «not reported» · grip: high |
| **Channel separation** | what one channel reads of the other muscle at its maximum | ≤ 25 % fine · > 50 % «not separated» |
| **P10 · P50 · P90** | static · median · peak load (Jonsson) | ≤ 5 · 14 · 70 % MVC |
| **EMD** | from the electrical signal to the movement | 30–100 ms |
| **Tremor** | peak of the accelerometer's spectrum | 8–12 Hz |

### Quick troubleshooting
- **No signal / flat line** → electrode contact, reference, correct channel.
- **50 Hz noise** → improve contact; move away from chargers and mains cables.
- **«not a maximum»** (in red, Task maximum) → recalibrate against the table, fist
  closed, hold the 4 s.
- **The co-activation table says «not reported»** → in a clean flexion or
  extension that is correct; a **grip** is needed for a number.
- **The grip does not co-activate** → the wrist is resting on the table. It has to
  be **in the air, beyond the edge**: resting, the table stabilises and the
  extensor relaxes. And never ask for «extend the wrist»: the extensors come in on
  their own.
- **«Channels not separated»** → move the pairs apart towards the ulnar and dorsal
  edges; each pair over its belly; forearm rested.
- **«Fatigue: not conclusive»** → contraction too short or intermittent; select
  only the sustained stretch.
- **The guided box does not appear** → switch to the Analysis tab: it waits there.
- **BITalino won't connect** → pair it in the OS Bluetooth settings first and give
  its **MAC** (or leave the field empty to autodetect).

> **Key idea:** *amplitude = how much the muscle activates · frequency = whether
> it fatigues · % MVC = what to compare it with.*
