"""
Measure subtitle timing quality against the audio.

Structure check (no audio needed): overlaps, order, too-short cues and
reading speed.

Audio check (--audio, needs whisperx): for every cue where a candidate
timeline and the baseline start more than 1 s apart, force-align the cue
text in a tight window at each start and count which one the audio prefers.
Before trusting the verdicts, a control compares the baseline window with
the same window shifted by 3 s on cues where the timelines agree; the test
is only meaningful if the true window wins the control almost always.

Usage:
  python evaluate_timing.py baseline.srt candidate.srt [more.srt ...]
  python evaluate_timing.py baseline.srt candidate.srt --audio movie.mp4
"""

import argparse
import difflib
import json
import random
import re
from pathlib import Path

import srt

from align_srt import AudioJudge, tokenize


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(srt.parse(f.read()))


def pair_cues(baseline, subs):
    """
    Pair cues of two timelines by normalized text, in order. ffsubsync drops
    cues it shifts before 0:00 and strips <i> and music notes, so position
    alone is not enough. Returns (baseline cues, matching cues).
    """
    matcher = difflib.SequenceMatcher(
        None, [" ".join(tokenize(s.content)) for s in baseline],
        [" ".join(tokenize(s.content)) for s in subs], autojunk=False)
    pairs = [(baseline[b.a + k], subs[b.b + k])
             for b in matcher.get_matching_blocks() for k in range(b.size)]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def structure(name, subs):
    durs = [(s.end - s.start).total_seconds() for s in subs]
    overlaps = sum(a.end > b.start for a, b in zip(subs, subs[1:]))
    disorder = sum(b.start < a.start for a, b in zip(subs, subs[1:]))
    cps = [len(re.sub(r"\s", "", s.content)) / max(d, 0.01)
           for s, d in zip(subs, durs)]
    counts = {"overlaps": overlaps, "out_of_order": disorder,
              "under_0.7s": sum(d < 0.7 for d in durs),
              "over_7s": sum(d > 7 for d in durs),
              "over_25cps": sum(c > 25 for c in cps)}
    print(f"{name:<32} " + " ".join(f"{k}={v}" for k, v in counts.items()))
    return counts


def audio_check(candidates, judge, margin=0.05, control_size=120):
    """candidates: (name, baseline cues, candidate cues), paired by pair_cues."""
    def conf(sub, start):
        return judge.confidence(sub.content.replace("\n", " "), start,
                                (sub.end - sub.start).total_seconds())

    def judgeable(sub):
        return judge.can_judge(sub.content.replace("\n", " "))

    _, baseline, first = candidates[0]
    agree = [i for i, s in enumerate(baseline)
             if abs((first[i].start - s.start).total_seconds()) < 0.25]
    # A private generator: loading the WhisperX model consumes the global
    # one, so the samples would depend on when the model happens to load.
    rng = random.Random(1)
    out = {"control": {}, "disputes": {}}
    print()
    for label, pool in (
            (f"{judge.MIN_WORDS}+ words", [i for i in agree if judgeable(baseline[i])]),
            ("shorter", [i for i in agree if not judgeable(baseline[i])])):
        control = rng.sample(pool, min(control_size, len(pool)))
        wins = sum(conf(baseline[i], baseline[i].start.total_seconds())
                   > conf(baseline[i], baseline[i].start.total_seconds() + 3)
                   for i in control)
        print(f"control ({label}): true window beats a 3 s shift in {wins}/{len(control)}")
        # int(): the confidences are numpy floats, so wins is a numpy int.
        out["control"][label] = {"wins": int(wins), "size": len(control)}

    print(f"{'timeline':<32}{'disputed':>9}{'wins':>6}{'losses':>7}{'ties':>6}"
          f"{'unjudged':>10}   (vs baseline, starts > 1 s apart;"
          f" unjudged = under {judge.MIN_WORDS} words)")
    for name, base, subs in candidates:
        w = l = t = u = 0
        for b, c in zip(base, subs):
            tb, tc = b.start.total_seconds(), c.start.total_seconds()
            if abs(tb - tc) <= 1.0:
                continue
            if not judgeable(b):
                u += 1
                continue
            cb, cc = conf(b, tb), conf(b, tc)
            if abs(cc - cb) < margin:
                t += 1
            elif cc > cb:
                w += 1
            else:
                l += 1
        print(f"{name:<32}{w + l + t + u:>9}{w:>6}{l:>7}{t:>6}{u:>10}")
        out["disputes"][name] = {"disputed": w + l + t + u, "wins": w,
                                 "losses": l, "ties": t, "unjudged": u}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("baseline", help="Reference timeline, e.g. the ffsubsync SRT")
    parser.add_argument("candidates", nargs="+",
                        help="Timelines to judge (cues are paired by text)")
    parser.add_argument("--audio", help="Video/audio file for the audio check")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--audio-cache",
                        help="SQLite file caching confidence scores across runs "
                             "(shared with align_srt.py --audio-cache)")
    parser.add_argument("--json", help="Also write the numbers to this JSON file")
    args = parser.parse_args()

    baseline = load(args.baseline)
    candidates = [(Path(p).name, load(p)) for p in args.candidates]
    # The baseline's file name varies per film; keep the JSON keys stable.
    result = {"structure": {"baseline": structure(Path(args.baseline).name, baseline)},
              "unpaired": {}}
    paired = []
    for name, subs in candidates:
        result["structure"][name] = structure(name, subs)
        base, cand = pair_cues(baseline, subs)
        unpaired = len(subs) - len(cand)
        if unpaired:
            print(f"{name}: {unpaired} of {len(subs)} cues have no baseline "
                  f"cue with the same text; they are left out of the audio check")
        result["unpaired"][name] = unpaired
        paired.append((name, base, cand))

    if args.audio:
        judge = AudioJudge(args.audio, args.device, cache_path=args.audio_cache)
        result.update(audio_check(paired, judge))
        print(judge.cache_summary())

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
