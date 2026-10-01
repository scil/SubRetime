"""
Cut a short test film out of a long one, for stepping through align_srt.py
in a debugger.

The sample keeps the source's absolute times and cue numbers, so its step
snapshots line up with the full film's (out/<film>/steps/) and the audio
judge asks the same questions of the same video. Inputs:

  films/<film>/original.srt, films/<film>/ffsubsync.srt  (cues FIRST..LAST)
  work/<film>/whisper/*.json  (the words the full film aligned to them)
  out/<film>/steps/00_align_words.csv  (that alignment: run align first)

Output: films/<film>-sample-<first>-<last>/ with original.srt,
ffsubsync.srt and whisper/<same name>.json. Add the printed entry to
films.yaml; its `whisper` key makes the pipeline skip transcription.

Keep margin around the cues you study: reject_outliers compares a cue with
the 8 anchored cues on each side (`window`), and interpolate_missing times
unmatched cues from their anchored neighbours, however far away. With at
least 8 anchored cues on each side, the sample's step snapshots matched the
full film's on every cue but the last (Dog Man 1075-1161, studying
1092-1151); compare them after cutting a new sample.

Usage:
  python make_sample.py dog-man-2025 1075 1161
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import srt
import yaml

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parent))
from align_srt import tokenize  # noqa: E402  (counts tokens as the aligner does)


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


def word_range(film, first, last):
    """
    The WhisperX words (token positions, as align_srt.py numbers them) that
    the full film's alignment left between the cues before FIRST and the
    cues after LAST: those cues' own words and the unmatched ones among
    them. Cutting by time instead would hand the sample's edge cues words
    that the full film gave to their neighbours.
    """
    path = LAB / "out" / film / "steps" / "00_align_words.csv"
    if not path.exists():
        raise SystemExit(f"{path.relative_to(LAB)} missing: run the align "
                         f"stage on {film} first")
    before, after = -1, None
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("film", help="film id in films.yaml")
    parser.add_argument("first", type=int, help="first cue number")
    parser.add_argument("last", type=int, help="last cue number")
    args = parser.parse_args()

    with open(LAB / "films.yaml", encoding="utf-8") as f:
        info = yaml.safe_load(f)[args.film]
    sample = f"{args.film}-sample-{args.first}-{args.last}"
    out = LAB / "films" / sample

    original = cut_cues(LAB / info["original"], args.first, args.last)
    baseline = cut_cues(LAB / info["baseline"], args.first, args.last)

    found = sorted((LAB / "work" / args.film / "whisper").glob("*.json"))
    if len(found) != 1:
        raise SystemExit(f"work/{args.film}/whisper: expected one .json, "
                         f"found {len(found)} (run the transcribe stage first)")
    j0, j1 = word_range(args.film, args.first, args.last)
    with open(found[0], encoding="utf-8") as f:
        whisper = cut_whisper(json.load(f), j0, j1)
    t0, t1 = whisper["segments"][0]["start"], whisper["segments"][-1]["end"]

    (out / "whisper").mkdir(parents=True, exist_ok=True)
    write_cues(original, out / "original.srt")
    write_cues(baseline, out / "ffsubsync.srt")
    with open(out / "whisper" / found[0].name, "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(whisper, f, ensure_ascii=False, indent=1)

    print(f"{out.relative_to(LAB)}: {len(original)} cues, "
          f"{len(whisper['word_segments'])} WhisperX words, "
          f"{t0:.1f}-{t1:.1f} s")
    print("\nAdd to films.yaml:\n")
    print(yaml.safe_dump({sample: {
        "video": info["video"],
        "original": f"films/{sample}/original.srt",
        "baseline": f"films/{sample}/ffsubsync.srt",
        "whisper": f"films/{sample}/whisper",
    }}, sort_keys=False, allow_unicode=True, width=1000))


if __name__ == "__main__":
    main()
