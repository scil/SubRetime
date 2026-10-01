# Stepping through the Dog Man sample

The sample `films/dog-man-2025-sample-1075-1161/` holds cues 1075-1161 of
Dog Man (2025): 87 lines, 282 WhisperX words, 64:17-69:23. Study cues
1092-1151; the rest is context for the steps that look at neighbours. Every
step's snapshot matches the full film's, except for line 1161 in
`finalize_timing` (see "Sample films for debugging" in the README).

## Setup

1. `cd lab`, `python pick_films.py dog-man-2025-sample-1075-1161`, then
   `dvc repro`. This fills `cache/dog-man-2025-sample-1075-1161/`, so the
   debugger answers every audio question from the cache.
2. In VS Code, Run and Debug → **align sample (dog-man 1075-1161)**.
   Outputs go to `lab/debug/dog-man-2025-sample-1075-1161/`.
3. Keep `lab/out/dog-man-2025-sample-1075-1161/steps/` open next to the
   code: each `NN_<step>.csv` is what `results` looks like after that step.

`results` is a list in cue order, so cue *N* is `results[N - 1075]`. In a
loop, a conditional breakpoint such as `r.sub.index == 1134` stops on one
line. The Debug Console evaluates expressions at the current frame, e.g.
`[(r.sub.index, r.status, r.offset) for r in results[17:30]]`.

## Steps

All are called in order from `align_subtitles()` in `align_srt.py`. Put a
breakpoint on each call there, step over it, and compare `results` with the
snapshot of that step.

### 00 `align_words`: original words ↔ WhisperX words

Inputs: `orig_tokens` (378 words of the subtitle) and `new_tokens` (the
WhisperX words). `difflib.SequenceMatcher` finds the exact runs; each gap
between two runs that has words on both sides goes to `_fuzzy_gap`, a small
Needleman-Wunsch pairing that accepts `fuzz.ratio` ≥ `min_sim` and 2:1 or
1:2 merges. Snapshot: `00_align_words.csv`.

| Cue | Watch |
|---|---|
| 1119 | "cave in" ↔ "caveman": a 2x1 gap; `_fuzzy_gap` takes the (2, 1) move, so original words 207 and 208 both map to WhisperX word 190 (`kind` = join) |
| 1137 | "gooders" ↔ "goodness": a 2x2 gap paired by similarity (`kind` = fuzzy) |
| 1134 | "gabba go go go go go": WhisperX heard only "gooba"; a one-sided gap (6x0) has nothing to pair |

Breakpoint: the `for gi, gj0, gj1 in _fuzzy_gap(...)` line in
`align_words`, condition `prev_i == 207` (1119) or `prev_i == 266` (1137);
`trace` lists every gap as it is reached.

### 01 `time_cues`: a time for every line with matched words

Per line: its matched word pairs, `_trim_edge_words` (drop an edge word
pinned far from the rest), then start/end from the first and last WhisperX
word, stretched by `word_dur` for unmatched words at the line's edges.
Status `anchored`; `offset` = new start − original start.

| Cue | Watch |
|---|---|
| 1096 | a clean match: 4/4 words, offset +0.56 s, like its neighbours |
| 1119, 1134, 1150 | matched, but 17-25 s *earlier* than the original time: the global alignment paired them with words far away |
| 1092, 1104 | no matched word: stay `none`, no time yet |

Breakpoint: `r.status = "anchored"` in `time_cues`, condition
`r.sub.index == 1119`. Look at `pairs`, `start`, `r.offset`.

### 02 `reject_outliers`: anchors that disagree with their neighbours

For each anchor, `local` = median offset of up to 8 anchors on each side
(`window`). An anchor further than `strong_dev` (4+ words) or `weak_dev`
from it becomes `outlier`; its time is kept in `r.candidate` for the audio
check. With `--audio` both tolerances are 1.0 s.

| Cue | Watch |
|---|---|
| 1102 | "Dog Man?": −0.59 s vs local +0.44 s; off by 1.03 s, just over the limit |
| 1105 | 2 of 4 words matched ("not my mouth"): +1.66 s vs +0.54 s |
| 1119 | −17.55 s vs +0.37 s |
| 1134 | 1 of 7 words matched: −24.74 s vs +0.50 s |
| 1096 | stays: its offset is the local offset |

Breakpoint: `if abs(r.offset - local) > limit:`, condition
`r.sub.index in (1102, 1134)`. Look at `neighbours`, `local`, `limit`.

### 03 `interpolate_missing`: a time for everything not placed

Lines without a word time (`none`, `outlier`) get original time + the
median offset of up to 3 anchors on each side (`side`). `none` becomes
`interpolated`; `outlier` keeps its status but moves.

| Cue | Watch |
|---|---|
| 1092 | `none` → `interpolated`, +0.41 s |
| 1140-1151 | 12 lines between anchors 1139 and 1154 (10 unrecognized, 2 outliers): all get +0.985 s, the median of anchors 1137-1139 and 1154-1156. This is why the sample reaches to 1161 |
| 1134 | outlier moves from its −24.74 s candidate to +0.60 s |

Breakpoint: `r.start = r.sub.start.total_seconds() + offset`, condition
`r.sub.index == 1140`. Look at `near` (indexes of the anchors used).

### 04 `verify_with_audio`: let the audio overrule a rejection

For each outlier with a candidate: force-align the line's text at the
candidate time and at the interpolated time (`AudioJudge.confidence`, from
the cache here). If the candidate scores at least `min_margin` (0.05)
higher, restore it as `verified`. Lines under 3 words are not judged.

| Cue | Watch |
|---|---|
| 1134 | whisper 0.48 vs prior 0.34: restored, `verified` at −24.74 s |
| 1150 | whisper 0.49 vs prior 0.92: stays outlier |
| 1119 | 0.50 vs 0.57: stays outlier |
| 1102 | "Dog Man?" has 2 words: "too short for audio check" |

Breakpoint: `if whisper_conf >= prior_conf + min_margin:`, condition
`r.sub.index == 1134`.

### 05 `rescue_local`: search near the expected time

For each line still not placed: search WhisperX words within
`time_window` (1.5 s) of its current time, but only between the words used
by the placed lines before and after it, for the best `fuzz.ratio` with the
line's text. Accept ≥ `min_score` (85); with audio, a far match must also
win the audio check.

| Cue | Watch |
|---|---|
| 1102 | outlier → `rescued`, score 100: back to −0.59 s, the time step 02 rejected; near its expected time it is the only "dog man" |
| 1140 | "Papa." `interpolated` → `rescued` at WhisperX word 237: the "papa" that step 01 gave to 1150, which is now an outlier and no longer holds it |

Breakpoint: `if best and best[0][0] >= min_score:`, condition
`r.sub.index == 1140`. Look at `lo`, `hi` (the search range) and `best`.

### 06 `revert_out_of_order`: placed lines that break the order

A placed line that starts more than `tolerance` after both following lines,
or before both previous ones, becomes `outlier` again, and
`interpolate_missing` runs once more.

| Cue | Watch |
|---|---|
| 1134 | `verified` at 4069.2 s, but the two lines before it start later (1132 at 4077.5 s, 1133 at 4085.2 s): "verified but out of order, reverted"; back to its interpolated time, 4094.6 s |

Breakpoint: `if late or early:`, condition `r.sub.index == 1134`. Look at
`before`, `after`.

### 07 `finalize_timing`: readable, ordered, no overlaps

One forward pass: start no earlier than the previous end + `min_gap`;
extend the end for reading time (`chars_per_sec`), up to the next line;
start up to `max_lead` earlier if still too short.

| Cue | Watch |
|---|---|
| 1140 | rescued "Papa." is a 0.26 s word: end extended, start moved 0.30 s earlier (`max_lead`) |
| 1096 | end + `end_pad` (0.3 s) |

Breakpoint: `r.end = end` in `finalize_timing`, condition
`r.sub.index == 1140`. Look at `wanted`, `limit`.
