# Surface‑EMG lab practical guide with emgteach

> **Course:** Physiology (teaching laboratory).
> **Software:** emgteach. **Hardware:** BITalino or Arduino + MyoWare 2.0 with
> surface electrodes.
>
> This guide proposes **five progressive practicals**. Each is self‑contained:
> objectives, brief background, materials, step‑by‑step procedure in the
> application, data to record and questions for the students. The instructor may
> select those that fit the available time.

---

## General objectives

By the end of the practicals, students should be able to:

1. Correctly record a surface‑EMG signal (electrode placement, connection,
   recording).
2. Distinguish the **raw**, **filtered** and **envelope** signals, and explain the
   purpose of each processing step.
3. Relate the EMG **amplitude** to the muscle **activation level**.
4. Observe agonist/antagonist **co‑activation**.
5. Identify **muscle fatigue** from the spectral shift (drop in MNF/MDF).
6. **Normalise** to % MVC and assess **muscular load** (Jonsson's method),
   including real‑time monitoring.

---

## Safety and hygiene

- **Very low‑voltage** equipment, battery/USB powered; no electrical risk to the
  subject.
- Use **single‑use** disposable electrodes; clean the skin with a wipe. Do not
  reuse electrodes between subjects.
- Subjects with skin lesions in the area should abstain.

---

## Common setup (before each practical)

1. **Electrode placement.** Clean the skin over the muscle belly; place two active
   electrodes aligned with the fibres and one **reference** electrode on a neutral
   area (a nearby bony prominence).
2. **Connection.** Open emgteach → **Acquisition** tab. Choose the device
   (BITalino/Arduino), enter the **MAC**/**port**, the **destination folder** and
   the **number of channels**. Press **Connect** (the **LED** should turn yellow).
3. **Test.** Press **Start recording**; ask for a brief contraction and check that
   the three plots (raw, filtered, envelope) respond. **Stop** and discard if there
   is a lot of artefact (reposition the electrodes).

[Suggested figure: photo of the electrode placement and a screenshot of the
Acquisition tab with the LED green during a contraction.]

---

## Practical 1 — Familiarisation and first recording

**Objective.** Obtain a clean recording and recognise the three representations of
the signal.

**Background.** Surface EMG picks up the sum of the active motor units' potentials.
The raw signal is **filtered** (50 Hz notch + 20–450 Hz band‑pass), **rectified**
and its **envelope** is computed, which follows the activation level.

**Procedure.**
1. With one channel over, e.g., the **biceps brachii**, start recording.
2. Perform the sequence: **5 s rest → light contraction 5 s → rest 5 s → strong
   contraction 5 s → rest 5 s**. Mark each onset with the **M** key (label
   *Contraction onset*).
3. Stop and open the file in the **Analysis** tab.

**Data to record.** Observe, in panel **2 (Envelope vs RMS)**, the amplitude
difference between the light and the strong contraction.

**Questions.**
- Why is the raw signal positive and negative, and the envelope only positive?
- What does the 50 Hz filter do? And the band‑pass?
- Does the envelope onset match your manual markers?

---

## Practical 2 — EMG–activation relationship (graded effort)

**Objective.** Verify that the EMG **amplitude** increases with the muscle
**activation level**.

**Background.** The greater the activation, the more motor units are recruited and
the faster they fire → **greater amplitude** (envelope / RMS). The relationship
with force is **monotonic but non‑linear**.

**Procedure.**
1. One channel over the muscle of interest. Start recording.
2. Perform **graded isometric contractions** of ~5 s each at increasing subjective
   levels (e.g. 25 %, 50 %, 75 %, 100 % of the perceived maximum effort), separated
   by rest. Mark each step.
3. In **Analysis**, use panel **5 (RMS per window)** and the summary (**global
   RMS**).

**Data to record.** Fill in the table:

| Effort level (subjective) | Approximate RMS |
|---|---|
| 25 % | |
| 50 % | |
| 75 % | |
| 100 % (MVC) | |

**Questions.**
- Is the RMS increase linear with the effort level? Comment.
- What sources of variability can affect the absolute amplitude (mV)?
- Why is it convenient to **normalise** to % MVC to compare across subjects?

[Suggested figure: plot of the RMS‑per‑window panel with the steps, and the data
table.]

---

## Practical 3 — Agonist/antagonist co‑activation (two channels)

**Objective.** Observe the coordinated activation of an agonist/antagonist pair.

**Background.** In many movements, the **antagonist** muscle co‑activates to
stabilise the joint. Two channels let you visualise this coordination.

**Procedure.**
1. Configure **2 channels** (e.g. **biceps** = channel 1, **triceps** = channel 2),
   with their labels. Start recording.
2. Perform controlled elbow **flexions and extensions** (alternating isometrics or
   slow movements). Mark the phases.
3. Watch the **stacked** plots (raw/filtered) and the **overlaid envelope**
   (blue/red) live. Stop and review each channel in **Analysis**.

**Data to record.** For one flexion and one extension, note which channel dominates
and whether the other co‑activates.

**Questions.**
- During flexion, does the triceps activate at all? What would that co‑activation
  be for?
- How does the **stacked view** help, compared with the overlaid one, to compare?

[Suggested figure: live screenshot of 2 channels with the overlaid envelope during
flexion and extension.]

---

## Practical 4 — Muscle fatigue (sustained contraction)

**Objective.** Detect **muscle fatigue** from the shift of the spectrum toward
lower frequencies.

**Background.** During a sustained contraction, the fibres' **conduction velocity**
falls and the spectrum **shifts to the left**: **MNF and MDF decrease** over time.
Often, the **amplitude (RMS) rises** to keep the force.

**Procedure.**
1. One channel over the muscle. Start recording.
2. Hold a **sustained submaximal isometric contraction** (e.g. ~50 % of maximum)
   **as long as possible** (30–60 s or until it cannot be held). Mark the start and
   end.
3. In **Analysis**, review panel **6 (MDF vs time)** and panel **4 (PSD)**; read the
   **MDF slope** and the **fatigue** indicator in the summary.

**Data to record.**

| Quantity | Start | End |
|---|---|---|
| MDF (Hz) | | |
| RMS | | |

MDF slope: ____ Hz/s. Fatigue detected? Yes / No.

**Questions.**
- Did the MDF decrease during the contraction? What explains it physiologically?
- Did the RMS increase at the end? Why would the nervous system do that?
- How would the shift look in the PSD panel (start vs end)?

[Suggested figure: MDF‑vs‑time panel with a descending trend and two PSDs
(start/end) showing the spectral shift.]

---

## Practical 5 — MVC normalisation and muscular load (Jonsson's method)

**Objective.** Express activation as **% MVC** and assess the **muscular load** of a
task, both **offline** and in **real time**.

**Background.** The **MVC** is the maximum‑effort reference. Normalising to % MVC
allows comparison. **Jonsson's method (APDF)** summarises the load into three
levels: **static (P10)**, **median (P50)** and **peak (P90)**, with recommended
limits; sustainedly exceeding them is associated with fatigue and musculoskeletal
risk.

**Part A — Offline (MVC tab).**
1. Record an **MVC reference**: a maximum contraction of ~3–5 s (save the EDF).
2. Record a representative **task** (e.g. holding a weight, a working posture) for a
   while (save the EDF).
3. In the **MVC** tab, load the **task EDF** and the **reference MVC EDF**. Review
   the **3 panels** and the **APDF chart** + **data panel**.

**Part B — Live (Acquisition tab).**
1. Start recording. Press **Calibrate MVC** and contract maximally for a few
   seconds.
2. Perform the task watching the **load bars**: note when they enter **orange**
   (tiredness) or **red** (fatigue).

**Data to record.**

| Level | Value (% MVC) | Within the normal range? |
|---|---|---|
| Static (P10) | | |
| Median (P50) | | |
| Peak (P90) | | |
| Mean activation | | |

**Questions.**
- Which level(s) exceed their recommended limit? What ergonomic implication does it
  have?
- Does the **live monitor** impression (colour zones) match the offline APDF
  analysis?
- What intervention would you propose if the static load is sustainedly high?

[Suggested figure: APDF chart with the three levels and the data panel; screenshot
of the live monitor with a bar in the orange/red zone.]

---

## Appendix — Student report template

For each practical, submit:

1. **Identification**: name/group, muscle(s) studied, device.
2. **Screenshots/figures** of the relevant panels (or the **PDF report** generated
   by the app).
3. Completed **data tables**.
4. **Reasoned answers** to the questions.
5. A brief **conclusion** relating the observations to the physiological background.

> **Note for instructors.** The app generates reproducible **PDF reports** (with the
> student's name and code) from the Analysis and MVC tabs; they can be used as a
> deliverable or as an appendix to the lab report. The **parameters** (filters, load
> limits, onset‑detection sensitivity, etc.) are adjustable to tune the difficulty.
