# SubRetime

Retime a subtitle line by line: keep its text, take precise times from the
speech.

SubRetime takes a subtitle whose words are right but whose timing is a bit
off, and a WhisperX transcript of the same video, which has a timestamp for
every spoken word. It matches the two word by word and gives each subtitle
line the time its words are actually spoken. The text, line breaks and
formatting (`<i>`, `♪`) are kept exactly.

Real example from *Dog Man* (2025): the downloaded subtitle showed a line
a full second before it was said.

```text
downloaded   00:03:11,674 --> 00:03:13,710   You know I got you, buddy.
SubRetime    00:03:12,664 --> 00:03:14,265   You know I got you, buddy.
```

What it is **not**:

- not transcription: it never changes the subtitle's words;
- not a global shift like ffsubsync: every line gets its own time;
- not translation-aware: the subtitle must be in the spoken language.

The previous Chinese README is kept as [README.zh.md](README.zh.md)
(outdated, for reference).

## Features

- **Word-level timing** from the WhisperX `.json` (every word has a start
  and end time).
- **Keeps the original text and formatting**, including italics and music
  notes.
- **Safe fallbacks**: lines WhisperX did not hear, or timed implausibly,
  keep the original time corrected by the local offset instead of being
  forced onto a wrong time.
- **Optional audio check** (`--audio`): disputed lines are settled by
  checking which candidate time actually fits the sound.
- **Per-line report** (`.report.csv`) saying how each line was timed and
  which ones deserve a manual look.
- **No tuning parameters.** Thresholds are measured defaults (see
  [Key constants](#key-constants)).

## Requirements

- Windows or Linux, Python 3.11 or newer (tested on 3.13)
- FFmpeg on `PATH`
- For WhisperX: an NVIDIA GPU with a CUDA build of PyTorch is strongly
  recommended; CPU works but is much slower
- `--audio` also uses the GPU (it loads the WhisperX alignment model)

## Installation

```powershell
cd E:\me\subtitle-alignment-with-Whisper
uv venv                                  # or: python -m venv .venv
.\.venv\Scripts\Activate.ps1
winget install Gyan.FFmpeg               # skip if ffmpeg -version already works
uv pip install -r requirements.txt       # whisperx, srt, rapidfuzz
```

Verify that PyTorch sees the GPU:

```powershell
python -c "import torch, whisperx; print(torch.__version__, torch.cuda.is_available())"
```

If it prints `False`, WhisperX installed a CPU-only PyTorch. Reinstall the
**same version** from the CUDA index, e.g.:

```powershell
uv pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
```

Version pitfalls (RTX 50-series, TorchCodec, FFmpeg DLLs, encodings) are in
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Usage

### 1. Transcribe the video with WhisperX

```powershell
whisperx "F:\Videos\movie.mp4" --language en --model large-v3 --device cuda --compute_type float16 --output_dir "F:\Videos\whisper-output"
```

This writes `.json`, `.srt`, `.vtt`, `.tsv` and `.txt`. Keep the `.json`:
it is the only one with per-word times.

### 2. Retime the subtitle

```powershell
python align_srt.py original.srt "F:\Videos\whisper-output\movie.srt" fixed.srt --audio "F:\Videos\movie.mp4"
```

- The second argument may be the WhisperX `.json` or `.srt`. With an
  `.srt`, the `.json` of the same name next to it is used automatically.
- `--audio` is optional but recommended when a GPU is available. A feature
  film takes about 1–2 minutes with it (mostly loading the audio and the
  alignment model), versus under a second without.
- `--quiet` prints only the summary; `--report path.csv` changes where the
  report goes (default: next to the output).

Use the subtitle **as downloaded**. Running ffsubsync first is only needed
when the original is off by more than about 10–20 s or runs at a different
speed (e.g. 25 vs 23.976 fps); it also strips `<i>` and `♪`.

### 3. Check the result

```powershell
python evaluate_timing.py original.srt fixed.srt --audio "F:\Videos\movie.mp4"
```

Then open the video and `fixed.srt` in Subtitle Edit and review the lines
the report flags (see [Output](#output)).

### GUI

```powershell
python gui.py
```

Pick the original subtitle, the WhisperX file and the output path. Tick
**Audio check** and pick the video to run with `--audio`. The alignment
runs in the background, so the window stays responsive; a dialog shows the
summary when it finishes.

## Output

- `fixed.srt`: the retimed subtitle, UTF-8.
- `fixed.report.csv`: one row per line.

| Column | Meaning |
|---|---|
| `index` | line number in the original subtitle |
| `status` | how the line was timed (below) |
| `matched_words` / `words` | subtitle words paired with WhisperX words / total |
| `orig_start` | original start time (s) |
| `new_start`, `new_end` | output times (s) |
| `shift_s` | `new_start − orig_start` |
| `text` | subtitle text |
| `whisper_text` | the WhisperX words used |
| `notes` | why: rejected offsets, audio scores, rescues, pushes |

| Status | Meaning | Review? |
|---|---|---|
| `anchored` | timed from matched WhisperX words | no |
| `verified` | WhisperX time was rejected, then restored by the audio check | rarely |
| `rescued` | found again by a local search near the expected time | spot-check |
| `outlier` | WhisperX time rejected; original time + local offset | **yes** |
| `interpolated` | no words matched (interjections, songs); original time + local offset | long runs |
| `none` | nothing matched anywhere; original time kept | **yes** |

On *Dog Man* (1391 lines): 1105 anchored, 6 verified, 21 rescued,
86 outliers, 173 interpolated.

## Development

### Tech stack

| Component | Library | Role |
|---|---|---|
| Transcription + word times | WhisperX (Whisper + wav2vec2 forced alignment) | spoken words with start/end times |
| Subtitle I/O | `srt` | parse and write SRT |
| Exact word alignment | `difflib.SequenceMatcher` (standard library) | global, in-order word pairing |
| Fuzzy word similarity | `rapidfuzz` (`fuzz.ratio`) | spelling variants inside gaps |
| Audio check | WhisperX `align()` (wav2vec2, CTC) | which of two times fits the sound |
| GUI | `tkinter` | file pickers around the CLI |

### Core idea

Align **words, not lines**. Both the subtitle and the WhisperX transcript
become word sequences, and one global, in-order alignment pairs them for
the whole film at once, so no single mistake can drag later lines along.
Each line then starts at its first matched word and ends at its last.

Neither source is trusted blindly. WhisperX word times occasionally fail
(words smeared over many seconds during music, a whole segment placed
early), and the original subtitle is typically 0.2–0.5 s off per line. The
original's local offset is the prior; WhisperX times are accepted only
where they roughly agree with it, and disagreements are settled by audio
when available.

The steps fall into four kinds: **structure** limits how badly anything
can go wrong, **checks** detect errors, **evidence** decides between
candidates, and **repair / fill** supplies a time when WhisperX's is missing
or rejected.

### Pipeline

`align_subtitles()` in `align_srt.py` runs these steps in order:

| # | Step | Function | Kind |
|---|---|---|---|
| 1 | Normalize and split both texts into words; exact word matching, global and in order | `tokenize`, `align_words` (difflib) | structure |
| 2 | Fuzzy matching inside the gaps between exact matches (similar words, 2:1 joins such as "dog man" / "dogman") | `_fuzzy_gap` | repair |
| 3 | Time each line from its first and last matched word; drop a first/last word pinned seconds away from the rest | `time_cues`, `_trim_edge_words` | check |
| 4 | Reject WhisperX times far from the neighbours' median offset; stricter for weakly matched lines | `reject_outliers`, `_is_strong` | check |
| 5 | Fallback time for rejected and unmatched lines: original time + median local offset | `interpolate_missing` | fill |
| 6 | `--audio` only: restore a rejected time if the audio clearly prefers it (lines with 3+ words) | `verify_with_audio`, `AudioJudge` | evidence |
| 7 | Search again for unplaced lines within ±1.5 s of the fallback time | `rescue_local` | repair |
| 8 | Revert lines that break the subtitle order, then re-interpolate | `revert_out_of_order` | check |
| 9 | No overlaps, minimum reading time, small start adjustments | `finalize_timing` | finishing |

Step 8 exists because steps 4–7 edit times line by line and can undo the
ordering that step 1 guarantees.

### Key constants

These are the real knobs. Each value was chosen by measurement on
*Dog Man* (see LESSONS.md); change one only with `evaluate_timing.py`
before and after. For development, most of them can be overridden without
editing code: `align_srt.py --params FILE` reads the `align` section of a
YAML file, and the DVC pipeline passes `lab/params.yaml` (see
[Tuning constants](#tuning-constants)).

| Constant | Value | Where | Why |
|---|---|---|---|
| strong-line tolerance | 1.5 s (1.0 s with `--audio`) | `reject_outliers(strong_dev)` | gaps above ~3 s were WhisperX errors about 3× as often as original errors |
| weak-line tolerance | 1.0 s | `reject_outliers(weak_dev)` | a lone "no" / "okay" is easily paired with the wrong copy |
| strong line | 4+ matched words, or 3 covering ≥ 60% | `_is_strong` | enough words to trust the pairing |
| neighbour window | 8 anchored lines each side | `reject_outliers(window)` | median of enough lines to ignore a few bad ones |
| fallback median | 3 anchored lines each side | `interpolate_missing(side)` | one bad neighbour must not shift a whole run |
| edge-word gap | 1.5 s beyond the original duration | `time_cues(max_word_gap)` | real pauses inside a line are kept |
| fuzzy word similarity | 0.75 | `align_words(min_sim)` | `grampa`/`grandpa` yes, unrelated words no |
| fuzzy gap size limit | 4000 word pairs | `align_words(max_gap_cells)` | speed; larger gaps get exact matches only |
| rescue window / score | ±1.5 s / 85 | `rescue_local` | local search only, near-exact text |
| audio: minimum words | 3 | `AudioJudge.MIN_WORDS` | the audio test was validated only on 3+ word lines |
| audio: margin / window pad | 0.05 / 0.3 s | `verify_with_audio`, `AudioJudge.confidence` | smaller differences count as a tie |
| order tolerance | 1.0 s | `revert_out_of_order` | beyond both neighbours on one side = misplaced |
| reading time | 17 chars/s, min 0.8 s, gap 84 ms, max lead 0.5 s | `finalize_timing` | common subtitle guidelines |

### Evaluation

`evaluate_timing.py baseline.srt candidate.srt [...] --audio movie.mp4`
prints:

- **structure**: overlaps, order, lines under 0.7 s or over 7 s, reading
  speed above 25 characters/s;
- **a control test** of the audio judge: on lines where two timelines
  agree, does the true window beat the same window shifted by 3 s? Reported
  separately for 3+ word and shorter lines. Trust the next table only if
  the control passes;
- **disputes**: for lines whose starts differ by more than 1 s from the
  baseline, how often the audio prefers the candidate (wins / losses /
  ties / unjudged).

### Development workflow (DVC)

[DVC](https://dvc.org) runs the whole chain (transcribe → align → evaluate)
on a set of test films. It reruns only the stages whose code, inputs or
params changed, and it keeps every run's outputs and metrics so runs can be
compared. The DVC extension for VS Code shows the runs as a table, with
charts next to it.

Everything DVC-related lives in **`lab/`**, a self-contained DVC project
(created with `dvc init --subdir`): its `.dvc/` folder, the pipeline files,
the test subtitles and all outputs. The rest of the repository does not
depend on it. **Run every `dvc` command from inside `lab/`.**

#### Install

These steps assume the normal [Installation](#installation) above is done
(`.venv` exists and WhisperX works).

1. Install DVC into the project environment:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   uv pip install -r requirements-dev.txt    # or: python -m pip install -r requirements-dev.txt
   dvc --version
   ```

2. Optionally, turn off DVC's anonymous usage statistics for this project
   (the setting lives in `lab\.dvc\config.local`, which is not committed):

   ```powershell
   cd lab
   dvc config --local core.analytics false
   ```

3. Install the VS Code extension, then open the repository folder in VS Code:

   ```powershell
   code --install-extension iterative.dvc
   code .
   ```

   In VS Code, run **Python: Select Interpreter** and pick
   `.venv\Scripts\python.exe`: the DVC extension finds the `dvc` command
   through the interpreter the Python extension uses. The DVC icon then
   appears in the activity bar. If it reports that DVC was not found, open
   **DVC: Setup the Workspace** and pick the same interpreter. The extension
   finds the project in `lab/` by itself; if it does not, run **DVC: Select
   Project(s) to Focus** and pick `lab`.

4. Pick a **film id** for each test video: lowercase words joined by `-`
   that name exactly one video, with the year for a film and the episode for
   a series (`dog-man-2025`, `ann-droid-s01e01`), so `ann-droid-s01e02` can
   be added later without a clash.

5. Put each film's subtitles in `lab\films\<film id>\`. They are ordinary
   files, not ignored by git; once committed, a clone brings them along and
   git keeps their history. (The current test subtitles are not committed
   yet, so a fresh clone has to add its own.)

   ```powershell
   New-Item -ItemType Directory -Force lab\films\dog-man-2025
   Copy-Item -LiteralPath "F:\Videos\Subs\English.srt" lab\films\dog-man-2025\original.srt
   Copy-Item -LiteralPath "F:\Videos\Subs\movie.synced-by-ffsubsync.srt" lab\films\dog-man-2025\ffsubsync.srt
   ```

   Videos stay where they are: they are too large for the repository, and
   DVC still records their hash as a stage input.

6. List every test film in `lab\films.yaml` (paths there are relative to
   `lab/`); WhisperX settings shared by all films are in `lab\params.yaml`.

   | Key | Meaning |
   |---|---|
   | `<id>.video` | the video (audio source for WhisperX and `--audio`); an absolute path is fine |
   | `<id>.original` | the subtitle to retime, as downloaded, e.g. `films/dog-man-2025/original.srt` |
   | `<id>.baseline` | reference timeline for `evaluate_timing.py`, e.g. `films/dog-man-2025/ffsubsync.srt` |
   | `whisper.*` (params.yaml) | WhisperX model, language, device, compute type |

   Then choose which of them run (see [Choosing films](#choosing-films)):

   ```powershell
   cd lab
   python pick_films.py dog-man-2025
   ```

   Each selected film gets its own stages: `transcribe@<film id>`,
   `align@<film id>` and `evaluate@<film id>`.

7. Optional: reuse an existing WhisperX transcript instead of spending
   about 10 minutes per film on the transcribe stage. Copy its `.json` into
   `lab\work\<film id>\whisper\` and record it as that stage's output:

   ```powershell
   cd lab
   New-Item -ItemType Directory -Force work\dog-man-2025\whisper
   Copy-Item -LiteralPath "F:\Videos\whisper-output\movie.json" -Destination work\dog-man-2025\whisper\
   dvc commit -f transcribe@dog-man-2025
   ```

8. Run the pipeline:

   ```powershell
   cd lab
   dvc repro
   ```

   The first run of the align and evaluate stages takes a few minutes per
   film: both load the audio and the alignment model.

`lab/` has already been initialized and committed (`lab/.dvc/`,
`lab/.dvcignore`), so a fresh clone needs only the steps above. No DVC
remote is configured: transcripts and outputs exist only in this machine's
cache (`lab\.dvc\cache`) and are rebuilt by `dvc repro` elsewhere.

#### Files in `lab/`

| File | Purpose |
|---|---|
| `dvc.yaml` | stages `transcribe`, `align`, `evaluate`, repeated per film (`foreach`): commands, inputs, outputs, metrics, plots |
| `films.yaml` | every test film: video, subtitle, baseline (edited by hand) |
| `selection.yaml` | the films that run, copied from `films.yaml` by `pick_films.py` (generated; committed) |
| `pick_films.py` | choose the films to run, in a window or on the command line |
| `params.yaml` | WhisperX settings and `align_srt.py` tuning constants used by `dvc.yaml` |
| `dvc.lock` | hashes of each stage's inputs and outputs from the last run (committed; DVC maintains it) |
| `films/<film>/original.srt`, `ffsubsync.srt` | the test subtitles (not ignored by git; not committed yet) |
| `work/<film>/whisper/` | WhisperX `.json` (git-ignored, stored in DVC's cache) |
| `out/<film>/fixed.srt`, `fixed.report.csv` | the retimed subtitle and its report |
| `out/<film>/steps/NN_<step>.csv` | **snapshot**: the per-line state after each step of `align_subtitles()` |
| `out/<film>/align.json` | metrics: lines per status, share of subtitle words matched (committed) |
| `out/<film>/eval.json` | metrics: `evaluate_timing.py` results (committed) |
| `.dvc/`, `.dvcignore` | DVC's own configuration; `.dvc/cache` holds every run's outputs (git-ignored) |

Outputs other than the metrics files are git-ignored. DVC keeps them in its
cache, one copy per run.

The snapshots come from development options of `align_srt.py`, which also
work outside DVC: `--snapshots DIR` writes one CSV per step,
`--metrics FILE` writes the status counts, and `--params FILE` overrides
tuning constants (next section).

#### Tuning constants

The `align` section of `lab/params.yaml` holds the main tuning constants of
`align_srt.py`, as `{step: {keyword: value}}`. Each step is a function in
`align_srt.py`, and each keyword is one of its arguments:

```yaml
align:
  rescue_local:
    time_window: 1.5
    min_score: 85
```

The values equal the defaults in the code, so without `--params` (and for
every end user) nothing changes. `reject_outliers_audio` holds the
tolerances used when `--audio` is on, which the pipeline always uses. Any
other keyword argument of the steps listed in `TUNABLE` (in `align_srt.py`)
can be added the same way; a misspelled step or keyword stops the run
before any audio is loaded.

Because the `align` stages list `align` under `params`, DVC reruns them when
a value changes, and each value is a column in `dvc exp show` and the VS
Code Experiments table. Try a value without editing the file:

```powershell
dvc exp run -S align.rescue_local.time_window=2 -n rescue-2s
```

#### Daily loop

All commands run inside `lab/`.

| Goal | Command |
|---|---|
| Run what changed | `dvc repro` |
| Choose the films that run | `python pick_films.py` (window) or `python pick_films.py <film id> ...` |
| Run one selected film only, once | `dvc repro evaluate@ann-droid-s01e01` (also runs the stages it depends on) |
| Current metrics | `dvc metrics show` |
| Metrics vs the last commit | `dvc metrics diff` |
| Record a code change as a named experiment | `dvc exp run -n reject-1.2s` |
| Try a different tuning constant | `dvc exp run -S align.reject_outliers_audio.strong_dev=1.2 -n reject-1.2s` |
| Compare all experiments | `dvc exp show`, or the **Experiments** table in VS Code |
| Keep an experiment's code and results | `dvc exp apply <name>`, then commit |
| Charts: shift of every line after each step | `dvc plots show` (writes `dvc_plots/index.html`), or **Plots** in VS Code |
| What one step changed | `git diff --no-index out/dog-man-2025/steps/04_verify_with_audio.csv out/dog-man-2025/steps/05_rescue_local.csv` |

After a `dvc repro` that failed partway, DVC may not have written the
`.gitignore` entries for the stages that did finish, and `git status` then
lists outputs such as `out/<film>/fixed.srt`. Run `dvc commit -f` to write
them before committing; otherwise run outputs end up in git.

`dvc exp run` takes a copy of the uncommitted code with each run, so trying a
change does not need a commit first. In the VS Code **Experiments** table,
tick the runs to compare; the **Plots** view then draws their per-step
charts side by side.

#### Choosing films

DVC runs every film in `lab/selection.yaml`. That file is generated from
`films.yaml` by `pick_films.py`, because DVC's templates cannot pick entries
by a parameter (`films[<param>]` is not supported). `dvc.yaml` loads it
through `vars` and repeats its stages for each film with `foreach`.

```powershell
cd lab
python pick_films.py                     # window: a checkbox per film
python pick_films.py ann-droid-s01e01    # no window: write the selection
```

The window has two buttons. **Save selection** writes `selection.yaml`;
**Save and run dvc repro** also runs the pipeline and shows its output.
The window puts its own interpreter's folder first on `PATH`, so the stages'
`python` and `whisperx` are the ones in `.venv`, even when the window was
started without activating `.venv`.

A film you leave out keeps its entries in `dvc.lock` and its outputs in
DVC's cache. Selecting it again costs nothing if its inputs and the code are
unchanged since its last run; otherwise it reruns on the next `dvc repro`.

To choose what you *look at* in VS Code, among the films that ran:

- **Plots**: run **DVC: Select Plots to Display** from the Command Palette
  (Ctrl+Shift+P). It lists one entry per `out/<film>/steps/<step>.csv`;
  tick the films and steps to show.
- **Experiments** table: the metric columns are grouped by file,
  `out/<film>/align.json` and `out/<film>/eval.json`. Run **DVC: Select
  Columns to Display in the Experiments Table** and untick the other films.

To add a step, write the function, call it in `align_subtitles()`, and add
a `snapshot("<name>")` call after it. Later snapshot numbers shift by one,
so compare snapshots by step name rather than by number across runs.

### Project layout

| File | Purpose |
|---|---|
| `align_srt.py` | the retiming pipeline (CLI) |
| `evaluate_timing.py` | quality check against the audio |
| `gui.py` | Tkinter front end for `align_srt.py` |
| `requirements.txt` | Python dependencies |
| `requirements-dev.txt` | development tools (DVC) |
| `lab/` | DVC development pipeline, test subtitles and run outputs (see [Development workflow](#development-workflow-dvc)) |
| `LESSONS.md` | what went wrong while building this, and why the design is what it is |
| `TROUBLESHOOTING.md` | installation and Windows problems |
| `README.zh.md` | the old Chinese README (outdated) |
