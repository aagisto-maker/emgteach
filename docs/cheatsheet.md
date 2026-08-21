# emgteach — Lab cheat sheet (1 page)

**The 3 tabs** · **Acquisition**: record live · **Analysis**: study a saved EDF ·
**MVC**: normalise to % MVC and assess muscular load.

**Signal chain:** Raw → *50 Hz notch + 20–450 Hz band‑pass* → **Filtered** →
rectified → **Envelope** (5 Hz low‑pass). *Only the raw is stored in the EDF; the
rest is recomputed.*

---

### Record (Acquisition)
1. **Connect** (choose device + MAC/port + folder + number of channels).
2. **Start recording**. Mark events with the **M** key (or the button).
3. **Stop** (the EDF is saved). You can enable **Auto‑onset** (marks contraction
   onsets automatically).
- **LED:** red = disconnected · yellow = no data · green = receiving.
- **Scales:** ▲▼ per plot; time zoom via dropdown / ◀▶ / mouse wheel.
- **2 channels:** raw and filtered are **stacked**; the envelope is **overlaid**
  (blue = channel 1, red = channel 2).

### Live muscle load
1. **Start recording** → **Calibrate MVC** (contract at **maximum** for a few
   seconds).
2. Watch the **bars**: 🟢 Normal · 🟠 *Warning* (tiredness) · 🔴 *Danger* (fatigue).

### Analyse (Analysis)
Open EDF → choose **channel** → review panels + summary → **Generate PDF report**
(choose graphs and time range).

### Normalise and load (MVC)
Load **test EDF** (+ optional **MVC EDF**) → see panels + **APDF chart** + data
panel → **PDF report**.

---

### Key metrics — what they mean
| Metric | Meaning |
|---|---|
| **RMS / envelope** | Amplitude → **activation level** (≈ force, non‑linear) |
| **iEMG** | Total accumulated activity (area under the envelope) |
| **MNF / MDF** | Mean / median frequency of the spectrum (PSD) |
| **MDF ↓ over time** | **FATIGUE** (the spectrum shifts to lower frequencies) |
| **% MVC** | Activation relative to the maximum (enables comparison) |

### Muscular load (Jonsson's method, in % MVC)
| Level | = | Meaning | Guideline limit |
|---|---|---|---|
| **Static** | P10 | Near‑continuous background load | ≤ ~5 % |
| **Median** | P50 | Typical working load | ≤ ~14 % |
| **Peak** | P90 | Recurrent high efforts | ≤ ~70 % |

🔴 **In red** = exceeds its limit (review load/ergonomics).

---

### Quick troubleshooting
- **No signal / flat line** → electrode contact, reference, correct channel.
- **50 Hz noise** → improve contact; move away from chargers/cables.
- **"Not calibrated"** → press **Calibrate MVC** *while recording*.
- **Unreadable report (long recording)** → shorten the **time range** in the dialog.
- **BITalino won't connect** → pair it in the OS Bluetooth settings first,
  then give its **MAC address** (or leave the field empty to autodetect).

> **Key idea:** *amplitude = how much the muscle activates; frequency = fatigue.*
