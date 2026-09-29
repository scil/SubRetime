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
before and after.

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

### Project layout

| File | Purpose |
|---|---|
| `align_srt.py` | the retiming pipeline (CLI) |
| `evaluate_timing.py` | quality check against the audio |
| `gui.py` | Tkinter front end for `align_srt.py` |
| `requirements.txt` | Python dependencies |
| `LESSONS.md` | what went wrong while building this, and why the design is what it is |
| `TROUBLESHOOTING.md` | installation and Windows problems |
| `README.zh.md` | the old Chinese README (outdated) |
