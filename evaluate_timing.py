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
import random
import re
from pathlib import Path

import srt

from align_srt import AudioJudge


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(srt.parse(f.read()))


def structure(name, subs):
    durs = [(s.end - s.start).total_seconds() for s in subs]
    overlaps = sum(a.end > b.start for a, b in zip(subs, subs[1:]))
    disorder = sum(b.start < a.start for a, b in zip(subs, subs[1:]))
    cps = [len(re.sub(r"\s", "", s.content)) / max(d, 0.01)
           for s, d in zip(subs, durs)]
    print(f"{name:<32} overlaps={overlaps} out_of_order={disorder} "
          f"under_0.7s={sum(d < 0.7 for d in durs)} over_7s={sum(d > 7 for d in durs)} "
          f"over_25cps={sum(c > 25 for c in cps)}")


def audio_check(baseline, candidates, judge, margin=0.05, control_size=120):
    def conf(sub, start):
        return judge.confidence(sub.content.replace("\n", " "), start,
                                (sub.end - sub.start).total_seconds())

    def judgeable(sub):
        return judge.can_judge(sub.content.replace("\n", " "))

    first = candidates[0][1]
    agree = [i for i, s in enumerate(baseline)
             if abs((first[i].start - s.start).total_seconds()) < 0.25]
    random.seed(1)
    print()
    for label, pool in (
            (f"{judge.MIN_WORDS}+ words", [i for i in agree if judgeable(baseline[i])]),
            ("shorter", [i for i in agree if not judgeable(baseline[i])])):
        control = random.sample(pool, min(control_size, len(pool)))
        wins = sum(conf(baseline[i], baseline[i].start.total_seconds())
                   > conf(baseline[i], baseline[i].start.total_seconds() + 3)
                   for i in control)
        print(f"control ({label}): true window beats a 3 s shift in {wins}/{len(control)}")

    print(f"{'timeline':<32}{'disputed':>9}{'wins':>6}{'losses':>7}{'ties':>6}"
          f"{'unjudged':>10}   (vs baseline, starts > 1 s apart;"
          f" unjudged = under {judge.MIN_WORDS} words)")
    for name, subs in candidates:
        w = l = t = u = 0
        for b, c in zip(baseline, subs):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("baseline", help="Reference timeline, e.g. the ffsubsync SRT")
    parser.add_argument("candidates", nargs="+", help="Timelines to judge (same cues)")
    parser.add_argument("--audio", help="Video/audio file for the audio check")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    baseline = load(args.baseline)
    candidates = [(Path(p).name, load(p)) for p in args.candidates]
    for name, subs in [(Path(args.baseline).name, baseline)] + candidates:
        if len(subs) != len(baseline):
            raise SystemExit(f"{name}: {len(subs)} cues, baseline has {len(baseline)}")
        structure(name, subs)

    if args.audio:
        audio_check(baseline, candidates, AudioJudge(args.audio, args.device))


if __name__ == "__main__":
    main()
