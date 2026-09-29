# Lessons learned: aligning Dog Man (2025)

Original subtitle: `*.synced-by-ffsubsync.srt`, 1391 cues.
WhisperX: `large-v3`, 1395 segments, 6362 timed words.

| Version | What changed | Result |
|---|---|---|
| greedy cue matcher | original `align_srt.py` | 273 matched, 1118 missed |
| word alignment | difflib + fuzzy gaps, WhisperX word times | 1145 anchored in 0.3 s |
| + trusted WhisperX | outlier rule relaxed after an invalid "referee" | audio disagreed: 34 wins, 89 losses |
| + median interpolation, order check | rules restored and measured | 6 wins, 12 losses on 33 disputed |
| + `--audio` verification | disputes settled by a validated audio test | 10 wins, 7 losses on 25 disputed |

"Wins/losses": on cues where the output and ffsubsync start more than 1 s
apart, how often the audio prefers the output. The other ~1360 cues agree
within 1 s.

## 1. Find the failure mode before tuning parameters

The README advised lowering `--threshold` or raising `--lookahead` when
there are many MISSes. The log showed the real cause in its first 50
lines: original #40 matched WhisperX #91, #41 matched #101, and by original
#384 the whole WhisperX file was used up. Everything after that could only
MISS. No threshold fixes a matcher that runs away.

**Habit:** before changing a parameter, read the matches and ask where the
cursor is compared to where it should be.

## 2. Know what your similarity score really measures

`fuzz.WRatio("whoa you crazy kid", <4 cues containing it>)` is 90, because
WRatio switches to partial matching when one string is much longer. So "4
merged cues" almost always beat "the right single cue", and every match
jumped ahead. A score that rewards containment is wrong for "is this the
same sentence?".

**Habit:** test the scoring function on 2-3 hand-made cases, including a
short needle in a long haystack, before building on it.

## 3. Use the finest-grained data you have

The WhisperX `.srt` drops what the `.json` has: a timestamp for every
word. Aligning word streams (monotonic sequence alignment) instead of cue
blocks removed the whole "how many cues to merge / how far to look ahead"
problem.

## 4. Every source of truth has characteristic failures

- WhisperX forced alignment sometimes pins an edge word seconds away
  (`petey's@823.8 first@830.5`), smears a line over 15 s during music, or
  places a whole segment 8-20 s early.
- The original subtitle, even after ffsubsync, is several seconds off for
  some single lines. ffsubsync fixes only a global shift or speed.
- Repeated words ("Papa?" "Papa." "Papa!", "no", "okay") get paired with
  the wrong copy by any global text alignment.

So neither timeline is "the truth". Use one as a prior (the original's
local offset) and accept the other only where they roughly agree or where
independent evidence decides.

## 5. Validate the measuring instrument before trusting it

The biggest mistake of the session: I force-aligned each cue over a wide
window covering both candidate times and called it a "referee". Spot checks
looked plausible, so I relaxed the outlier rule to trust WhisperX. Then the
full run showed the referee was off by a median of 1.78 s **even on cues
where ffsubsync and WhisperX agreed within 0.25 s**. CTC forced alignment
assumes the window holds only the given text; other people's speech in the
window makes it snap anywhere.

The replacement, a *discrimination test* (align in a tight window at A and
at B, compare confidence), was checked with a control first: the true
window beat a 3 s shifted window in 114/120 cues. Only then did its
verdicts count, and they reversed my earlier conclusion.

**Habit:** before trusting any metric, run it where you already know the
answer (agreement cases, deliberately shifted inputs). Plausible spot
checks are not validation.

**A validated tool is only validated where it was tested.** The control
used cues of 3+ words, yet the audio check was then allowed to move
one-word cues. A report line like `offset -7.30s ...; audio: whisper 0.62
vs prior 0.29` moved "Huh?" 7 s. Sliding the window showed "Huh?" scoring
0.6-0.9 almost anywhere, and an unrelated word ("Papa!") scoring 0.5-0.8
in the same spots. Measured separately, the control drops from 108/120
(3+ words) to 98/120 (1-2 words), and real disputes are harder than a 3 s
shift. Fix: short cues are no longer judged by audio (18 of 27 audio
"restores" had been 1-2 word cues).

## 6. Fix the cause of a symptom, not the symptom

- "Start pushed +10 s to avoid overlap" was not a finishing-pass problem.
  One cue was placed out of order, and the overlap guard dutifully pushed
  everything after it. Fix: detect cues that are out of order against
  their two neighbours on either side and fall back to interpolation.
- A run of unmatched cues all shifted by +1.02 s came from linear
  interpolation between the two nearest anchors, one of them wrong. Fix:
  median of several anchors on each side.
- The local rescue pass silently undid audio verdicts (it found the same
  WhisperX words the audio had rejected). Fix: in audio mode, rescue also
  needs the audio's approval.

## 7. Keep a regression yardstick and re-run it after every change

Each change was checked with the same summary plus the audio test. Without
it, v4 → v7 would have looked like progress (more anchored cues) while the
audio said it made the output worse.

**Habit:** "more matches" is not "better timing". Measure the thing you
care about.

## 8. A GUI must not wait on a long job, and must not be touched from a thread

Adding the **Audio check** option to `gui.py` turned a sub-second run into
a 1–2 minute one. The old GUI called `subprocess.run()` on the Tk thread,
so the window would have frozen for the whole run and looked crashed.

- **Run long work off the UI thread.** The subprocess now runs in a
  background thread; the button shows "Running…" and is disabled.
- **Tkinter is not thread-safe.** My first version called `root.after()`
  from the worker thread to report back. That is itself a Tk call from the
  wrong thread and only works by luck. Fix: the worker puts its result on
  a `queue.Queue`, and the Tk thread polls it with `root.after(200, check)`.
- **Test the GUI by driving it, not by looking at it.** A script loaded
  `gui.py` with `mainloop` stubbed out, filled the fields, called `run()`,
  pumped `root.update()` and captured the message boxes. It confirmed the
  validation error, identical results to the CLI, and that the window kept
  updating (1501 updates during a 76 s run).
- **Quote durations the user will experience.** I had told the user
  `--audio` "adds about 20 s": that counted only the checking. The GUI test
  measured the whole run, including loading the film's audio and the
  alignment model: about 76 s. Time the full path end to end before putting
  a number in help text or docs.

## 9. Remaining limits

Measured on the current output (`English.srt` input, `--audio`):

- 19 of 1391 lines start more than 1 s away from ffsubsync. On the 10 the
  audio test can judge (3+ words): 3 better, 3 worse, 4 ties. The other 9
  are 1–2 word lines the test cannot judge.
- 173 lines have no matched words: about 160 were never transcribed by
  Whisper (interjections, lyrics, overlapping speech); about 13 are
  matching failures. They keep the original timing plus the local offset.
- 86 lines had their WhisperX time rejected and use the same fallback.
- Errors below the rejection tolerance (1–1.5 s) are not detected.
- Very dense dialogue still produces about 10 lines shorter than 0.7 s.
