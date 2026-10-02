"""
Cut a short test film out of a long one, for stepping through align_srt.py
in a debugger.

You name the cues to study, FIRST..LAST; the sample also holds context
around them, so that every step treats them as it did in the full film:
reject_outliers compares a cue with the 8 anchored cues on each side
(`window`), and interpolate_missing times unmatched cues from their
anchored neighbours, however far away. The cut is widened on each side
until it holds --anchors cues still anchored after reject_outliers in the
full film (by default the larger of reject_outliers' `window` and
interpolate_missing's `side` in params.yaml).

The cut follows Approach 0's run of the film (stage align_0): its WhisperX
words and statuses. The sample keeps the source's absolute times and cue
numbers, so its step snapshots line up with the full film's
(out/<film>/0/steps/) and the audio judge asks the same questions of the
same video. Inputs:

  films/<film>/original.srt, films/<film>/ffsubsync.srt  (the cut's cues)
  work/<film>/whisper/*.json  (the words the full film aligned to them)
  out/<film>/0/steps/  (that alignment and the statuses: run align_0 first)

Output: films/<film>-sample-<first>-<last>/ with original.srt,
ffsubsync.srt and whisper/<same name>.json. Then the sample is aligned
here, with the full film's audio cache, and its step snapshots are compared
with the film's: a difference on a studied cue is an error. Add the printed
entry to films.yaml; its `whisper` key makes the pipeline skip
transcription.

Usage:
  python make_sample.py dog-man-2025 1092 1151
"""

import argparse
import contextlib
import csv
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

import srt
import yaml

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parent))
import align_srt  # noqa: E402
from align_srt import tokenize  # noqa: E402  (counts tokens as the aligner does)


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def default_anchors():
    with open(LAB / "params.yaml", encoding="utf-8") as f:
        align = (yaml.safe_load(f) or {}).get("align") or {}
    return max(align.get("reject_outliers", {}).get("window", 8),
               align.get("interpolate_missing", {}).get("side", 3))


def context_range(steps, first, last, anchors):
    """
    Widen FIRST..LAST until each side holds ANCHORS cues outside the range
    that the full film still had anchored after reject_outliers (or the
    film's first / last cue).
    """
    cues = [(int(r["index"]), r["status"]) for r in
            read_csv(steps / "02_reject_outliers.csv")]
    numbers = [c for c, _ in cues]
    if first not in numbers or last not in numbers:
        raise SystemExit(f"cues {first}..{last} not in the film")
    before = [c for c, s in cues if c < first and s == "anchored"]
    after = [c for c, s in cues if c > last and s == "anchored"]
    lo = before[-anchors] if len(before) >= anchors else numbers[0]
    hi = after[anchors - 1] if len(after) >= anchors else numbers[-1]
    return lo, hi


def cut_cues(path, first, last):
    with open(path, encoding="utf-8-sig") as f:
        cues = [c for c in srt.parse(f.read()) if first <= c.index <= last]
    if not cues or cues[0].index != first or cues[-1].index != last:
        raise SystemExit(f"{path}: cues {first}..{last} not found")
    return cues


def write_cues(cues, path):
    # reindex=False keeps the source's cue numbers.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(srt.compose(cues, reindex=False))


def word_range(steps, first, last):
    """
    The WhisperX words (token positions, as align_srt.py numbers them) that
    the full film's alignment left between the cues before FIRST and the
    cues after LAST: those cues' own words and the unmatched ones among
    them. Cutting by time instead would hand the sample's edge cues words
    that the full film gave to their neighbours.
    """
    before, after = -1, None
    for row in read_csv(steps / "00_align_words.csv"):
        if not (row["index"] and row["new_j"]):
            continue
        # new_j is "a-b" when one original word took two WhisperX words.
        cue, js = int(row["index"]), [int(j) for j in row["new_j"].split("-")]
        if cue < first:
            before = max(before, js[-1])
        elif cue > last:
            after = js[0] if after is None else min(after, js[0])
    return before + 1, after


def cut_whisper(data, j0, j1):
    """
    Keep the raw words holding tokens j0..j1-1 (j1 None: to the end), and the
    segments they belong to, trimmed to them. Assumes word_segments is the
    segments' words in order, as WhisperX writes it.
    """
    segments, j = [], 0
    for s in data["segments"]:
        words = []
        for w in s.get("words", []):
            n = len(tokenize(w["word"]))
            if n and j + n > j0 and (j1 is None or j < j1):
                words.append(w)
            j += n
        if not words:
            continue
        timed = [w for w in words if "start" in w]
        segments.append({**s, "start": timed[0]["start"] if timed else s["start"],
                         "end": timed[-1]["end"] if timed else s["end"],
                         "text": "".join(" " + w["word"] for w in words),
                         "words": words})
    return {**data, "segments": segments,
            "word_segments": [w for s in segments for w in s["words"]]}


def compare(film, info, cues, sample_dir, first, last):
    """
    Align the sample as the pipeline does (audio, params.yaml) and compare
    each step snapshot with the film's. Returns {step: [differing cues]}.
    The film's audio cache answers the questions the film already asked.
    """
    steps = LAB / "out" / film / "0" / "steps"
    words, _ = align_srt.load_whisper_words(sample_dir / "whisper")
    judge = align_srt.AudioJudge(
        info["video"], cache_path=LAB / "cache" / film / "confidence.sqlite")
    tmp = Path(tempfile.mkdtemp())
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            align_srt.align_subtitles(
                cues, words, judge=judge, verbose=False, snapshot_dir=tmp,
                settings=align_srt.load_settings(LAB / "params.yaml"))
        diffs = {}
        for path in sorted(tmp.glob("0[1-9]_*.csv")):
            full = {r["index"]: r for r in read_csv(steps / path.name)}
            diffs[path.stem] = [int(r["index"]) for r in read_csv(path)
                                if r != full[r["index"]]]
        # Word snapshot: the studied cues' rows, in order, without the word
        # positions (orig_i, new_j), which count from the sample's start.
        def word_rows(rows):
            return [{k: v for k, v in r.items() if k not in ("orig_i", "new_j")}
                    for r in rows
                    if r["index"] and first <= int(r["index"]) <= last]
        if word_rows(read_csv(tmp / "00_align_words.csv")) != \
                word_rows(read_csv(steps / "00_align_words.csv")):
            diffs["00_align_words"] = ["rows differ"]
        return diffs, judge.cache_summary()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("film", help="film id in films.yaml")
    parser.add_argument("first", type=int, help="first cue to study")
    parser.add_argument("last", type=int, help="last cue to study")
    parser.add_argument("--anchors", type=int, default=default_anchors(),
                        help="anchored cues of context on each side "
                             "(default: %(default)s, from params.yaml)")
    parser.add_argument("--no-check", action="store_true",
                        help="do not align the sample to compare it with the film")
    args = parser.parse_args()

    with open(LAB / "films.yaml", encoding="utf-8") as f:
        info = yaml.safe_load(f)[args.film]
    steps = LAB / "out" / args.film / "0" / "steps"
    if not (steps / "00_align_words.csv").exists():
        raise SystemExit(f"out/{args.film}/0/steps missing: run the align_0 "
                         f"stage on {args.film} first")
    found = sorted((LAB / "work" / args.film / "whisper").glob("*.json"))
    if len(found) != 1:
        raise SystemExit(f"work/{args.film}/whisper: expected one .json, "
                         f"found {len(found)} (run the transcribe_0 stage first)")

    sample = f"{args.film}-sample-{args.first}-{args.last}"
    out = LAB / "films" / sample
    lo, hi = context_range(steps, args.first, args.last, args.anchors)
    original = cut_cues(LAB / info["original"], lo, hi)
    baseline = cut_cues(LAB / info["baseline"], lo, hi)
    j0, j1 = word_range(steps, lo, hi)
    with open(found[0], encoding="utf-8") as f:
        whisper = cut_whisper(json.load(f), j0, j1)
    t0, t1 = whisper["segments"][0]["start"], whisper["segments"][-1]["end"]

    (out / "whisper").mkdir(parents=True, exist_ok=True)
    write_cues(original, out / "original.srt")
    write_cues(baseline, out / "ffsubsync.srt")
    with open(out / "whisper" / found[0].name, "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(whisper, f, ensure_ascii=False, indent=1)

    print(f"{out.relative_to(LAB)}: cues {lo}-{hi} ({len(original)}), "
          f"{len(whisper['word_segments'])} WhisperX words, "
          f"{t0:.1f}-{t1:.1f} s")

    failed = False
    if not args.no_check:
        diffs, cache = compare(args.film, info, original, out,
                               args.first, args.last)
        print(f"\nCompared with {args.film}'s step snapshots ({cache}):")
        for step, cues in diffs.items():
            studied = [c for c in cues if not isinstance(c, int)
                       or args.first <= c <= args.last]
            failed |= bool(studied)
            context = [c for c in cues if c not in studied]
            print(f"  {step:24} "
                  + ("same" if not cues else
                     f"studied cues differ: {studied}" if studied else
                     f"same on studied cues; context differs: {context}"))

    print("\nAdd to films.yaml:\n")
    print(f"# Cues {args.first}-{args.last} of {args.film} to study, cut by "
          f"make_sample.py with\n# context: the files hold cues {lo}-{hi}.")
    print(yaml.safe_dump({sample: {
        "video": info["video"],
        "original": f"films/{sample}/original.srt",
        "baseline": f"films/{sample}/ffsubsync.srt",
        "whisper": f"films/{sample}/whisper",
    }}, sort_keys=False, allow_unicode=True, width=1000))
    if failed:
        raise SystemExit("studied cues differ from the full film: "
                         "widen the context with --anchors")


if __name__ == "__main__":
    main()
