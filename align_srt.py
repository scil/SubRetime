"""
SubRetime: keep the text of an original SRT, take the timing from a
WhisperX transcript.

Algorithm (word-level global alignment):

1. Split every original cue into normalized words, remembering which cue
   each word came from.
2. Load WhisperX words with their own start/end times (from the WhisperX
   JSON; if only an SRT is given, word times are interpolated inside each
   segment).
3. Align the two word streams globally and monotonically:
   exact-word anchors via difflib, then fuzzy word pairing inside the gaps.
4. Time each original cue from its first and last matched words.
   Cues whose anchors disagree with their neighbours (outliers) or that have
   no matched words are placed by interpolating the local time offset
   between the original and WhisperX timelines.
5. Clean up: enforce order, minimum reading time and a small gap between
   cues.
"""

import argparse
import bisect
import csv
import difflib
import inspect
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import srt
from rapidfuzz import fuzz

try:
    # Development: pause in the debugger at chosen steps (see dev_stops.py).
    from dev_stops import stop_for_debug
except ImportError:
    def stop_for_debug(step, cue=None):
        pass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>|\{[^}]+\}")
_WORD_RE = re.compile(r"[\w']+", re.UNICODE)

_TYPO = str.maketrans({
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": " ", "—": " ", "-": " ",
})

_EQUIV = {
    "ok": "okay",
    "mr": "mister",
    "mrs": "missus",
    "dr": "doctor",
}


def normalize_word(word: str) -> str:
    word = word.lower().strip("'")
    return _EQUIV.get(word, word)


def tokenize(text: str) -> list[str]:
    """Split subtitle text into normalized words. Output text is untouched."""
    text = _TAG_RE.sub(" ", text).translate(_TYPO).lower()
    words = (normalize_word(w) for w in _WORD_RE.findall(text))
    return [w for w in words if w]


# ---------------------------------------------------------------------------
# WhisperX input
# ---------------------------------------------------------------------------

@dataclass
class Word:
    text: str
    start: float
    end: float


def _fill_missing_times(raw: list[dict]) -> list[Word]:
    """WhisperX leaves some words (often numbers) without timestamps."""
    words = []
    for i, w in enumerate(raw):
        start, end = w.get("start"), w.get("end")
        if start is None or end is None:
            prev_end = next((raw[k]["end"] for k in range(i - 1, -1, -1)
                             if raw[k].get("end") is not None), 0.0)
            next_start = next((raw[k]["start"] for k in range(i + 1, len(raw))
                               if raw[k].get("start") is not None), prev_end)
            start, end = prev_end, max(prev_end, next_start)
        for token in tokenize(w["word"]):
            words.append(Word(token, float(start), float(end)))
    return words


def load_whisper_words(path: Path) -> tuple[list[Word], str]:
    """
    Return WhisperX words with times, preferring the JSON next to an SRT.
    A directory must hold exactly one WhisperX .json (the DVC pipeline passes
    its output directory, whose file is named after the video).
    """
    if path.is_dir():
        found = sorted(path.glob("*.json"))
        if len(found) != 1:
            raise SystemExit(f"{path}: expected one WhisperX .json, found {len(found)}")
        path = found[0]
    json_path = path if path.suffix.lower() == ".json" else path.with_suffix(".json")

    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("word_segments") or [
            w for seg in data["segments"] for w in seg.get("words", [])
        ]
        return _fill_missing_times(raw), f"{json_path} (word timestamps)"

    # SRT only: spread each segment's duration over its words by length.
    with open(path, "r", encoding="utf-8-sig") as f:
        segments = list(srt.parse(f.read()))
    words = []
    for seg in segments:
        tokens = tokenize(seg.content)
        if not tokens:
            continue
        start = seg.start.total_seconds()
        span = seg.end.total_seconds() - start
        total = sum(len(t) for t in tokens)
        pos = 0
        for t in tokens:
            w_start = start + span * pos / total
            pos += len(t)
            words.append(Word(t, w_start, start + span * pos / total))
    return words, f"{path} (segment timestamps, interpolated)"


# ---------------------------------------------------------------------------
# Word alignment
# ---------------------------------------------------------------------------

# Moves of the gap alignment: (original words used, WhisperX words used).
# 2:1 and 1:2 cover split/joined words such as "dog man" vs "dogman".
_MOVES = ((1, 1), (2, 1), (1, 2))


def _fuzzy_gap(a: list[str], b: list[str], min_sim: float):
    """
    Needleman-Wunsch style pairing for a small gap, maximizing similarity.
    Returns (original index, first WhisperX index, last WhisperX index).
    """
    n, m = len(a), len(b)

    def sim(i, j, da, db):
        s = fuzz.ratio("".join(a[i - da:i]), "".join(b[j - db:j])) / 100
        return s * da if s >= min_sim else 0.0

    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best, move = -1.0, None
            if i > 0 and score[i - 1][j] > best:
                best, move = score[i - 1][j], (1, 0)
            if j > 0 and score[i][j - 1] > best:
                best, move = score[i][j - 1], (0, 1)
            for da, db in _MOVES:
                if i >= da and j >= db:
                    s = sim(i, j, da, db)
                    if s and score[i - da][j - db] + s > best:
                        best, move = score[i - da][j - db] + s, (da, db)
            score[i][j], back[i][j] = best, move

    triples = []
    i, j = n, m
    while i > 0 or j > 0:
        da, db = back[i][j]
        if da and db:
            for k in range(da):
                triples.append((i - da + k, j - db, j - 1))
        i, j = i - da, j - db
    return triples[::-1]


def align_words(orig: list[str], new: list[str], min_sim=0.75,
                max_gap_cells=4000, trace=None) -> dict[int, tuple[int, int]]:
    """
    Map original word index -> (first, last) WhisperX word index,
    monotonically. Exact runs come from difflib; the gaps between them are
    filled by fuzzy pairing (spelling variants, split/joined words).

    trace: a list to append one entry per gap between exact runs:
    {"orig": (start, stop), "new": (start, stop), "status": s}, where s is
    "tried" (fuzzy pairing ran), "skipped" (larger than max_gap_cells) or
    "one_sided" (words on one side only, nothing to pair); development only.
    """
    matcher = difflib.SequenceMatcher(None, orig, new, autojunk=False)
    mapping = {}
    prev_i = prev_j = 0

    for block in matcher.get_matching_blocks():
        gap_a = orig[prev_i:block.a]
        gap_b = new[prev_j:block.b]
        if not (gap_a and gap_b):
            status = "one_sided"
        elif len(gap_a) * len(gap_b) > max_gap_cells:
            status = "skipped"
        else:
            status = "tried"
            stop_for_debug("align_words")
            for gi, gj0, gj1 in _fuzzy_gap(gap_a, gap_b, min_sim):
                mapping[prev_i + gi] = (prev_j + gj0, prev_j + gj1)
        if trace is not None and (gap_a or gap_b):
            trace.append({"orig": (prev_i, block.a), "new": (prev_j, block.b),
                          "status": status})
        for k in range(block.size):
            mapping[block.a + k] = (block.b + k, block.b + k)
        prev_i, prev_j = block.a + block.size, block.b + block.size

    return mapping


# ---------------------------------------------------------------------------
# Cue timing
# ---------------------------------------------------------------------------

# Cues whose time comes from WhisperX words rather than interpolation.
PLACED = ("anchored", "verified", "rescued")


@dataclass
class CueResult:
    sub: srt.Subtitle
    words: int = 0
    matched: int = 0
    start: float | None = None
    end: float | None = None
    status: str = "none"          # anchored | rescued | outlier | interpolated | none
    offset: float | None = None   # new start - original start
    first_j: int | None = None    # first / last WhisperX word used
    last_j: int | None = None
    candidate: tuple | None = None  # rejected anchor, for audio verification
    matched_text: str = ""
    notes: list[str] = field(default_factory=list)


def _trim_edge_words(pairs, new_words, max_gap, orig_dur):
    """
    WhisperX sometimes pins the first or last word of a phrase seconds away
    from the rest ("petey's@823.8 first@830.5 attack@830.8"). Drop edge
    words separated from the rest of the cue by more than max_gap, but only
    while the cue is clearly longer than the original cue: a real pause
    inside a line is kept.
    """
    while len(pairs) > 1:
        span = new_words[pairs[-1][2]].end - new_words[pairs[0][1]].start
        if span <= orig_dur + max_gap:
            break
        head = new_words[pairs[1][1]].start - new_words[pairs[0][2]].end
        tail = new_words[pairs[-1][1]].start - new_words[pairs[-2][2]].end
        if max(head, tail) <= max_gap:
            break
        if head >= tail:
            pairs = pairs[1:]
        else:
            pairs = pairs[:-1]
    return pairs


def time_cues(original, orig_owner, mapping, new_words, word_dur=0.3,
              max_word_gap=1.5):
    results = [CueResult(sub) for sub in original]
    by_cue: dict[int, list[tuple[int, int, int]]] = {}
    for oi, cue in enumerate(orig_owner):
        results[cue].words += 1
        if oi in mapping:
            by_cue.setdefault(cue, []).append((oi, *mapping[oi]))

    first_word_of_cue = {}
    last_word_of_cue = {}
    for oi, cue in enumerate(orig_owner):
        first_word_of_cue.setdefault(cue, oi)
        last_word_of_cue[cue] = oi

    for cue, pairs in by_cue.items():
        r = results[cue]
        orig_dur = (r.sub.end - r.sub.start).total_seconds()
        trimmed = _trim_edge_words(pairs, new_words, max_word_gap, orig_dur)
        if len(trimmed) < len(pairs):
            r.notes.append(f"dropped {len(pairs) - len(trimmed)} mistimed edge word(s)")
        pairs = trimmed
        r.matched = len(pairs)
        (oi_first, nj_first, _), (oi_last, _, nj_last) = pairs[0], pairs[-1]

        start = new_words[nj_first].start
        end = new_words[nj_last].end

        # Original words before the first / after the last match were not
        # recognized by WhisperX; stretch the cue a little to cover them
        # without crossing into the neighbouring WhisperX words.
        lead = oi_first - first_word_of_cue[cue]
        if lead:
            floor = new_words[nj_first - 1].end if nj_first > 0 else 0.0
            start = max(floor, start - lead * word_dur)
        trail = last_word_of_cue[cue] - oi_last
        if trail:
            ceil = (new_words[nj_last + 1].start
                    if nj_last + 1 < len(new_words) else end + trail * word_dur)
            end = min(ceil, end + trail * word_dur)

        stop_for_debug("time_cues", r.sub.index)
        r.start, r.end = start, max(end, start)
        r.offset = start - r.sub.start.total_seconds()
        r.first_j, r.last_j = nj_first, nj_last
        r.matched_text = " ".join(w.text for w in new_words[nj_first:nj_last + 1])
        r.status = "anchored"

    return results


def _is_strong(r):
    """Four matched words, or three that cover most of the cue."""
    return r.matched >= 4 or (r.matched == 3 and r.matched / r.words >= 0.6)


def reject_outliers(results, strong_dev=1.5, weak_dev=1.0, window=8):
    """
    Reject anchors that disagree with the local offset between the original
    and WhisperX timelines (median over neighbouring anchors).

    Measured on Dog Man (2025) with an audio discrimination test: when an
    anchor is more than ~3 s away from the local offset, the original
    (ffsubsync) timing is right about 3x as often as WhisperX. Causes are
    WhisperX segments whose words are smeared over many seconds, and lone
    common words ("no", "okay") paired with the wrong copy. Anchors with
    several matched words get a wider tolerance than weak ones.
    """
    anchored = [i for i, r in enumerate(results) if r.status == "anchored"]
    offsets = [results[i].offset for i in anchored]

    for k, i in enumerate(anchored):
        lo, hi = max(0, k - window), min(len(anchored), k + window + 1)
        neighbours = offsets[lo:k] + offsets[k + 1:hi]
        if len(neighbours) < 3:
            continue
        local = statistics.median(neighbours)
        r = results[i]
        limit = strong_dev if _is_strong(r) else weak_dev
        stop_for_debug("reject_outliers", r.sub.index)
        if abs(r.offset - local) > limit:
            r.status = "outlier"
            r.candidate = (r.start, r.end, r.first_j, r.last_j, r.matched_text)
            r.notes.append(f"offset {r.offset:+.2f}s vs local {local:+.2f}s")


def interpolate_missing(results, side=3):
    """
    Place unanchored cues using the original timing plus the local offset:
    the median offset of up to `side` anchored cues on each side. Linear
    interpolation between just the two nearest anchors lets a single
    mistimed anchor drag a whole run of unrecognized cues with it.
    """
    anchored = [i for i, r in enumerate(results) if r.status == "anchored"]
    if not anchored:
        for r in results:
            r.start = r.sub.start.total_seconds()
            r.end = r.sub.end.total_seconds()
            r.status = "none"
        return

    for i, r in enumerate(results):
        if r.status in PLACED:
            continue
        k = bisect.bisect_left(anchored, i)
        near = anchored[max(0, k - side):k + side]
        offset = statistics.median(results[j].offset for j in near)

        stop_for_debug("interpolate_missing", r.sub.index)
        r.start = r.sub.start.total_seconds() + offset
        r.end = r.sub.end.total_seconds() + offset
        r.status = "interpolated" if r.status == "none" else r.status


def revert_out_of_order(results, tolerance=1.0):
    """
    A placed cue that starts after both following cues (or before both
    previous cues) contradicts the subtitle order; trusting it would make
    the overlap guard push its neighbours by seconds. Mark it an outlier
    and return how many were reverted; the caller re-interpolates them.
    """
    reverted = 0
    for i, r in enumerate(results):
        if r.status not in PLACED:
            continue
        after = results[i + 1:i + 3]
        before = results[max(0, i - 2):i]
        late = len(after) == 2 and all(n.start < r.start - tolerance for n in after)
        early = len(before) == 2 and all(p.start > r.start + tolerance for p in before)
        stop_for_debug("revert_out_of_order", r.sub.index)
        if late or early:
            r.notes.append(f"{r.status} but out of order, reverted")
            r.status = "outlier"
            reverted += 1
    return reverted


class AudioJudge:
    """
    Decide which of two start times really holds a cue's speech: force-align
    the cue text (wav2vec2 via WhisperX) in a tight window at each time and
    compare alignment confidence. Validated on Dog Man: the true window beat
    a window shifted by 3 s in 114 of 120 control cues.

    Only cues with MIN_WORDS or more words are judged. A one-word cue
    ("Huh?") scores 0.6-0.9 almost anywhere, and so does a word nobody says
    there; the 3 s control drops from 108/120 (3+ words) to 98/120 (1-2
    words), and real disputes are closer calls than a 3 s shift. Too weak
    to overrule the fallback time.

    Do not force-align over a wide window instead: CTC alignment assumes the
    window holds only the given text and snaps to other people's speech.

    cache_path: an SQLite file remembering every answer, keyed by the media
    file (path, size, mtime), WhisperX version, device, text, start,
    duration and pad. The audio and the model load only on the first
    question the cache cannot answer, so a rerun that asks the same
    questions skips them. Bump CACHE_VERSION when confidence() changes.
    """

    MIN_WORDS = 3
    CACHE_VERSION = 1

    def can_judge(self, text):
        return len(tokenize(text)) >= self.MIN_WORDS

    def __init__(self, media_path, device="cuda", cache_path=None):
        self.media_path = Path(media_path)
        self.device = device
        self.whisperx = None
        self.cache = None
        if cache_path:
            import sqlite3
            from importlib.metadata import version

            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            self.cache = sqlite3.connect(cache_path)
            self.cache.execute("CREATE TABLE IF NOT EXISTS confidence "
                               "(key TEXT PRIMARY KEY, value REAL)")
            st = self.media_path.stat()
            self.cache_prefix = [self.CACHE_VERSION, str(self.media_path.resolve()),
                                 st.st_size, st.st_mtime_ns, version("whisperx"),
                                 device]
            self.hits = self.misses = 0

    def _load(self):
        import whisperx  # optional dependency, only for --audio

        self.whisperx = whisperx
        self.audio = whisperx.load_audio(str(self.media_path))
        self.model, self.meta = whisperx.load_align_model(
            language_code="en", device=self.device)

    def confidence(self, text, start, duration, pad=0.3):
        if self.cache is None:
            return self._confidence(text, start, duration, pad)
        key = json.dumps(self.cache_prefix + [text, round(start, 6),
                                              round(duration, 6), pad])
        row = self.cache.execute("SELECT value FROM confidence WHERE key = ?",
                                 (key,)).fetchone()
        if row:
            self.hits += 1
            return row[0]
        self.misses += 1
        value = self._confidence(text, start, duration, pad)
        self.cache.execute("INSERT OR REPLACE INTO confidence VALUES (?, ?)",
                           (key, value))
        self.cache.commit()
        return value

    def _confidence(self, text, start, duration, pad):
        if self.whisperx is None:
            self._load()
        seg = [{"start": max(0.0, start - pad), "end": start + duration + pad,
                "text": text}]
        try:
            out = self.whisperx.align(seg, self.model, self.meta, self.audio,
                                      self.device)
        except Exception:
            return 0.0
        scores = [w.get("score", 0.0) for w in out["word_segments"]]
        # float(): a numpy float would not survive the SQLite round trip.
        return float(statistics.mean(scores)) if scores else 0.0

    def cache_summary(self):
        if self.cache is None:
            return "audio cache: off"
        return (f"audio cache: {self.hits} hits, {self.misses} computed"
                + ("" if self.whisperx else "; audio not loaded"))


def verify_with_audio(results, judge, min_margin=0.05):
    """Restore a rejected anchor when the audio clearly prefers it."""
    restored = 0
    for r in results:
        if r.status != "outlier" or r.candidate is None:
            continue
        text = r.sub.content.replace("\n", " ")
        if not judge.can_judge(text):
            r.notes.append("too short for audio check")
            continue
        duration = (r.sub.end - r.sub.start).total_seconds()
        c_start, c_end, c_first, c_last, c_text = r.candidate
        whisper_conf = judge.confidence(text, c_start, duration)
        prior_conf = judge.confidence(text, r.start, duration)
        r.notes.append(f"audio: whisper {whisper_conf:.2f} vs prior {prior_conf:.2f}")
        stop_for_debug("verify_with_audio", r.sub.index)
        if whisper_conf >= prior_conf + min_margin:
            r.status = "verified"
            r.start, r.end = c_start, c_end
            r.first_j, r.last_j, r.matched_text = c_first, c_last, c_text
            r.offset = c_start - r.sub.start.total_seconds()
            restored += 1
    return restored


def rescue_local(results, new_words, judge=None, time_window=1.5, min_score=85):
    """
    Second chance for outliers and interpolated cues: look for the cue's
    words only near its expected time and only between the WhisperX words
    already used by its anchored neighbours. Global alignment often pairs a
    repeated line ("Papa!", a chorus) with the wrong copy; a local search
    with a time prior picks the right one.
    """
    starts = [w.start for w in new_words]
    fixed = [i for i, r in enumerate(results) if r.status in ("anchored", "verified")]
    prev_last_j = -1

    for i, r in enumerate(results):
        if r.status in PLACED:
            prev_last_j = r.last_j
            continue

        tokens = tokenize(r.sub.content)
        if not tokens:
            continue
        target = " ".join(tokens)

        k = bisect.bisect_right(fixed, i)
        next_first_j = results[fixed[k]].first_j if k < len(fixed) else len(new_words)

        lo = max(prev_last_j + 1, bisect.bisect_left(starts, r.start - time_window))
        hi = min(next_first_j, bisect.bisect_right(starts, r.start + time_window))

        best = None
        n = len(tokens)
        for j in range(lo, hi):
            for length in range(max(1, n - 1), n + 2):
                if j + length > next_first_j:
                    break
                cand = " ".join(w.text for w in new_words[j:j + length])
                score = fuzz.ratio(target, cand)
                key = (score, -abs(new_words[j].start - r.start))
                if best is None or key > best[0]:
                    best = (key, j, j + length - 1)

        stop_for_debug("rescue_local", r.sub.index)
        if best and best[0][0] >= min_score:
            _, j0, j1 = best
            text = r.sub.content.replace("\n", " ")
            if (judge and judge.can_judge(text)
                    and abs(new_words[j0].start - r.start) > 0.5):
                # Otherwise rescue would undo a verdict of the audio check.
                duration = (r.sub.end - r.sub.start).total_seconds()
                if (judge.confidence(text, new_words[j0].start, duration)
                        < judge.confidence(text, r.start, duration) + 0.05):
                    continue
            r.notes.append(f"rescued from {r.status}, score {best[0][0]:.0f}")
            r.status = "rescued"
            r.start, r.end = new_words[j0].start, new_words[j1].end
            r.offset = r.start - r.sub.start.total_seconds()
            r.first_j, r.last_j = j0, j1
            r.matched = n
            r.matched_text = " ".join(w.text for w in new_words[j0:j1 + 1])
            prev_last_j = j1


def finalize_timing(results, min_gap=0.084, chars_per_sec=17.0, min_dur=0.8,
                    min_show=0.5, end_pad=0.3, max_dur=7.0, max_lead=0.5):
    """
    WhisperX word times are tight around the speech. Subtitles need reading
    time, must stay in order and must not overlap. One forward pass:
    1. start no earlier than the previous cue's end + min_gap;
    2. extend the end for reading time, up to the next cue's start;
    3. if still too short, start up to max_lead earlier, into free time.
    """
    prev_end = None
    for i, r in enumerate(results):
        if prev_end is not None and r.start < prev_end + min_gap:
            shift = prev_end + min_gap - r.start
            r.notes.append(f"start pushed {shift:+.2f}s to avoid overlap")
            r.start += shift
            r.end = max(r.end, r.start)

        chars = len(re.sub(r"\s+", "", r.sub.content))
        wanted = max(min_dur, chars / chars_per_sec)
        end = max(r.end + end_pad, r.start + wanted)
        end = min(end, r.start + max(max_dur, r.end - r.start))
        if i + 1 < len(results):
            limit = results[i + 1].start - min_gap
            if end > limit:
                # The next cue gets pushed if min_show does not fit.
                end = max(limit, r.start + min_show)

        if end - r.start < wanted:
            floor = prev_end + min_gap if prev_end is not None else 0.0
            r.start = min(r.start, max(floor, end - wanted, r.start - max_lead))

        stop_for_debug("finalize_timing", r.sub.index)
        r.end = end
        prev_end = end


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def write_snapshot(results, path):
    """One row per cue after a pipeline step, for diffing steps and runs."""
    def fmt(t):
        return "" if t is None else f"{t:.3f}"

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "status", "matched_words", "words",
                         "orig_start", "start", "end", "shift_s", "text",
                         "whisper_text", "notes"])
        for r in results:
            orig_start = r.sub.start.total_seconds()
            writer.writerow([
                r.sub.index, r.status, r.matched, r.words, f"{orig_start:.3f}",
                fmt(r.start), fmt(r.end),
                "" if r.start is None else f"{r.start - orig_start:+.3f}",
                r.sub.content.replace("\n", " / "), r.matched_text,
                "; ".join(r.notes),
            ])


def write_word_snapshot(original, orig_tokens, orig_owner, new_words,
                        mapping, trace, path):
    """
    The input and output of align_words in one table: both word streams
    merged in order, one row per original word, with each WhisperX word that
    no original word took in a row of its own where it falls.
    """
    def fmt(t):
        return "" if t is None else f"{t:.3f}"

    # Original words sharing one WhisperX word: a 2:1 join ("dog man").
    shared = {}
    for j_range in mapping.values():
        shared[j_range] = shared.get(j_range, 0) + 1

    # Which gap between exact runs each word fell in (absent: inside a run).
    orig_gap, new_gap = {}, {}
    for g in trace:
        (i0, i1), (j0, j1) = g["orig"], g["new"]
        size = f"{i1 - i0}x{j1 - j0}"
        for i in range(i0, i1):
            orig_gap[i] = (g["status"], size)
        for j in range(j0, j1):
            new_gap[j] = (g["status"], size)

    def whisper_only(j):
        w = new_words[j]
        gap, size = new_gap.get(j, ("", ""))
        return ["", "", "", j, w.text, fmt(w.start), fmt(w.end), "", "",
                "whisper_only", gap, size]

    rows = []
    next_j = 0  # first WhisperX word not written yet
    for i, token in enumerate(orig_tokens):
        sub = original[orig_owner[i]]
        orig_start = sub.start.total_seconds()
        gap, size = orig_gap.get(i, ("", ""))
        if i not in mapping:
            rows.append([sub.index, i, token, "", "", "", "", fmt(orig_start),
                         "", "orig_only", gap, size])
            continue
        j0, j1 = mapping[i]
        rows.extend(whisper_only(j) for j in range(next_j, j0))
        next_j = max(next_j, j1 + 1)
        if j1 > j0:
            kind = "split"
        elif shared[(j0, j1)] > 1:
            kind = "join"
        elif token == new_words[j0].text:
            kind = "exact"
        else:
            kind = "fuzzy"
        start = new_words[j0].start
        rows.append([sub.index, i, token,
                     str(j0) if j0 == j1 else f"{j0}-{j1}",
                     " ".join(w.text for w in new_words[j0:j1 + 1]),
                     fmt(start), fmt(new_words[j1].end), fmt(orig_start),
                     f"{start - orig_start:+.3f}", kind, gap, size])
    rows.extend(whisper_only(j) for j in range(next_j, len(new_words)))

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "index",          # line (cue) number the original word is in;
                              # empty for a WhisperX-only row
            "orig_i",         # position of the word among all original words
            "orig_word",      # the original word, normalized (input)
            "new_j",          # WhisperX word position(s) it maps to: "j", or
                              # "j0-j1" for a split (output)
            "whisper_word",   # the WhisperX word(s) at new_j (input)
            "whisper_start",  # s: start of the first WhisperX word
            "whisper_end",    # s: end of the last WhisperX word
            "orig_start",     # s: original start of the word's line
            "shift_s",        # whisper_start - orig_start: the line's shift
                              # plus the word's place inside the line
            "kind",           # exact | fuzzy (similar spelling) | split (one
                              # original word, several WhisperX words) | join
                              # (several original words, one WhisperX word) |
                              # orig_only | whisper_only (not matched)
            "gap",            # empty: inside an exact run; else the gap
                              # between exact runs it fell in: tried |
                              # skipped (over max_gap_cells) | one_sided
            "gap_size",       # that gap: original words x WhisperX words
        ])
        writer.writerows(rows)


CHANGES_HEADER = ["step", "index", "status_before", "status_after",
                  "start_before", "start_after", "moved_s", "end_before",
                  "end_after", "text", "notes"]


def _changed(a, b):
    if a is None or b is None:
        return a is not b
    return abs(a - b) >= 0.0005


def cue_changes(step_name, results, before):
    """
    Rows for the cues a step changed (status, start or end), measured
    against `before`: {cue position: (status, start, end, notes count)}.
    Updates `before` to the current state.
    """
    def fmt(t):
        return "" if t is None else f"{t:.3f}"

    rows = []
    for i, r in enumerate(results):
        if r.start is None:
            continue  # no time yet: compare once a step gives it one
        status, start, end, n_notes = before[i]
        if (r.status != status or _changed(r.start, start)
                or _changed(r.end, end)):
            moved = ("" if r.start is None or start is None
                     else f"{r.start - start:+.3f}")
            rows.append([step_name, r.sub.index, status, r.status, fmt(start),
                         fmt(r.start), moved, fmt(end), fmt(r.end),
                         r.sub.content.replace("\n", " / "),
                         "; ".join(r.notes[n_notes:])])
        before[i] = (r.status, r.start, r.end, len(r.notes))
    return rows


def align_subtitles(original, new_words, judge=None, verbose=True,
                    snapshot_dir=None, settings=None, changes_path=None):
    """
    snapshot_dir: write the per-cue state after every step as
    NN_<step>.csv there (see write_snapshot), and align_words' input and
    output as 00_align_words.csv (see write_word_snapshot).
    settings: {step name: {keyword: value}} overriding the steps' defaults
    (see TUNABLE and load_settings); development only.
    changes_path: write one row per cue a step changed, starting from the
    original subtitle's times (see cue_changes).
    """
    settings = settings or {}

    def kw(name):
        return settings.get(name, {})

    step = 0
    before = {i: ("original", s.start.total_seconds(), s.end.total_seconds(), 0)
              for i, s in enumerate(original)}
    changes = []

    def snapshot(name):
        nonlocal step
        step += 1
        if snapshot_dir:
            write_snapshot(results, Path(snapshot_dir) / f"{step:02d}_{name}.csv")
        if changes_path:
            changes.extend(cue_changes(f"{step:02d}_{name}", results, before))

    if snapshot_dir:
        Path(snapshot_dir).mkdir(parents=True, exist_ok=True)
        for old in Path(snapshot_dir).glob("*.csv"):
            old.unlink()

    orig_tokens, orig_owner = [], []
    for ci, sub in enumerate(original):
        for token in tokenize(sub.content):
            orig_tokens.append(token)
            orig_owner.append(ci)

    new_tokens = [w.text for w in new_words]
    trace = [] if snapshot_dir else None
    mapping = align_words(orig_tokens, new_tokens, trace=trace,
                          **kw("align_words"))
    if snapshot_dir:
        # Word-level, before any line has a time; numbered 00 so the line
        # snapshots keep their numbers (snapshot() is not called).
        write_word_snapshot(original, orig_tokens, orig_owner, new_words,
                            mapping, trace,
                            Path(snapshot_dir) / "00_align_words.csv")

    results = time_cues(original, orig_owner, mapping, new_words,
                        **kw("time_cues"))
    snapshot("time_cues")
    # With audio to settle disputes, reject more eagerly and let it decide.
    if judge:
        reject_outliers(results, **{"strong_dev": 1.0, "weak_dev": 1.0,
                                    **kw("reject_outliers_audio")})
    else:
        reject_outliers(results, **kw("reject_outliers"))
    snapshot("reject_outliers")
    interpolate_missing(results, **kw("interpolate_missing"))
    snapshot("interpolate_missing")
    if judge:
        verify_with_audio(results, judge, **kw("verify_with_audio"))
        snapshot("verify_with_audio")
    rescue_local(results, new_words, judge, **kw("rescue_local"))
    snapshot("rescue_local")
    if revert_out_of_order(results, **kw("revert_out_of_order")):
        interpolate_missing(results, **kw("interpolate_missing"))
    snapshot("revert_out_of_order")
    finalize_timing(results, **kw("finalize_timing"))
    snapshot("finalize_timing")

    if changes_path:
        Path(changes_path).parent.mkdir(parents=True, exist_ok=True)
        with open(changes_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CHANGES_HEADER)
            writer.writerows(changes)

    if verbose:
        for r in results:
            tag = {"anchored": "MATCH", "verified": "AUDIO", "rescued": "RESCU",
                   "outlier": "OUTLR", "interpolated": "INTRP",
                   "none": "KEEP "}[r.status]
            print(f"[{tag}] {r.sub.index:4d} "
                  f"words={r.matched}/{r.words} "
                  f"{srt.timedelta_to_srt_timestamp(timedelta(seconds=r.start))} "
                  f"text={r.sub.content[:50]!r}")

    counts = {s: sum(r.status == s for r in results)
              for s in ("anchored", "verified", "rescued", "outlier",
                        "interpolated", "none")}
    total_words = len(orig_tokens)
    print()
    print("Alignment finished")
    print("------------------")
    print(f"Words matched: {len(mapping)}/{total_words} "
          f"({100 * len(mapping) / max(total_words, 1):.1f}%)")
    print(f"Anchored:      {counts['anchored']}  (timed from WhisperX words)")
    if judge:
        print(f"Verified:      {counts['verified']}  (rejected anchor restored by audio check)")
    print(f"Rescued:       {counts['rescued']}  (found by local search near expected time)")
    print(f"Outliers:      {counts['outlier']}  (anchor rejected, interpolated)")
    print(f"Interpolated:  {counts['interpolated']}  (no words recognized)")
    print(f"Total cues:    {len(results)}")

    return results


# Steps whose keyword arguments --params may override. With --audio,
# reject_outliers is called with its own settings (reject_outliers_audio).
TUNABLE = {
    "align_words": align_words,
    "time_cues": time_cues,
    "reject_outliers": reject_outliers,
    "reject_outliers_audio": reject_outliers,
    "interpolate_missing": interpolate_missing,
    "verify_with_audio": verify_with_audio,
    "rescue_local": rescue_local,
    "revert_out_of_order": revert_out_of_order,
    "finalize_timing": finalize_timing,
}


def load_settings(path):
    """
    Read the `align` section of a YAML file: {step: {keyword: value}}.
    Checked against the step signatures here, before any slow work starts.
    """
    import yaml  # development dependency, only for --params

    with open(path, "r", encoding="utf-8") as f:
        settings = (yaml.safe_load(f) or {}).get("align") or {}
    for name, values in settings.items():
        if name not in TUNABLE:
            raise SystemExit(f"{path}: unknown step '{name}' "
                             f"(known: {', '.join(TUNABLE)})")
        try:
            inspect.signature(TUNABLE[name]).bind_partial(**values)
        except TypeError as e:
            raise SystemExit(f"{path}: align.{name}: {e}")
    return settings


def write_report(results, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "status", "matched_words", "words",
                         "orig_start", "new_start", "new_end", "shift_s",
                         "text", "whisper_text", "notes"])
        for r in results:
            orig_start = r.sub.start.total_seconds()
            writer.writerow([
                r.sub.index, r.status, r.matched, r.words,
                f"{orig_start:.3f}", f"{r.start:.3f}", f"{r.end:.3f}",
                f"{r.start - orig_start:+.3f}",
                r.sub.content.replace("\n", " / "), r.matched_text,
                "; ".join(r.notes),
            ])


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Keep text from the original SRT, "
            "but take timestamps from a WhisperX transcript."
        )
    )
    parser.add_argument("original",
                        help="Original subtitle whose text should be preserved")
    parser.add_argument("new",
                        help="WhisperX .json or .srt (a .json next to the .srt "
                             "is used automatically for word timestamps)")
    parser.add_argument("output", help="Output SRT filename")
    parser.add_argument("--report",
                        help="CSV report path (default: <output>.report.csv)")
    parser.add_argument("--audio",
                        help="Video/audio file: settle disputed cues by "
                             "force-aligning their text (needs whisperx, GPU)")
    parser.add_argument("--device", default="cuda",
                        help="Device for --audio (default: cuda)")
    parser.add_argument("--quiet", action="store_true",
                        help="Only print the summary")
    parser.add_argument("--snapshots",
                        help="Directory for per-step CSV snapshots (development)")
    parser.add_argument("--metrics",
                        help="JSON file for status counts (development)")
    parser.add_argument("--params",
                        help="YAML file whose `align` section overrides the "
                             "steps' tuning constants (development)")
    parser.add_argument("--changes",
                        help="CSV of every line each step changed, starting "
                             "from the original times (development)")
    parser.add_argument("--audio-cache",
                        help="SQLite file caching --audio confidence scores "
                             "across runs (development)")
    args = parser.parse_args()
    settings = load_settings(args.params) if args.params else None

    with open(args.original, "r", encoding="utf-8-sig") as f:
        original = list(srt.parse(f.read()))

    new_words, source = load_whisper_words(Path(args.new))

    print(f"Original subtitles: {len(original)}")
    print(f"WhisperX words:     {len(new_words)} from {source}")
    print()

    judge = None
    if args.audio:
        print(f"Audio check with: {args.audio}")
        judge = AudioJudge(args.audio, device=args.device,
                           cache_path=args.audio_cache)

    results = align_subtitles(original, new_words, judge=judge,
                              verbose=not args.quiet,
                              snapshot_dir=args.snapshots, settings=settings,
                              changes_path=args.changes)
    if judge:
        print(judge.cache_summary())

    output = [
        srt.Subtitle(
            index=r.sub.index,
            start=timedelta(seconds=max(r.start, 0.0)),
            end=timedelta(seconds=max(r.end, 0.0)),
            content=r.sub.content,
            proprietary=r.sub.proprietary,
        )
        for r in results
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(srt.compose(output, reindex=False))

    report = args.report or str(Path(args.output).with_suffix(".report.csv"))
    write_report(results, report)

    if args.metrics:
        metrics = {s: sum(r.status == s for r in results)
                   for s in ("anchored", "verified", "rescued", "outlier",
                             "interpolated", "none")}
        metrics["cues"] = len(results)
        metrics["cue_words_matched_pct"] = round(
            100 * sum(r.matched for r in results)
            / max(sum(r.words for r in results), 1), 2)
        Path(args.metrics).parent.mkdir(parents=True, exist_ok=True)
        with open(args.metrics, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

    print()
    print(f"Saved:  {args.output}")
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
