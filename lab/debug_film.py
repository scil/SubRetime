"""
Run align_srt.py on one film with the align_0 stage's arguments (Approach
0) or the align_A stage's (Approach A, --force-align), for VS Code's
debugger (.vscode/launch.json).

The films offered are the ones selected in pick_films.py (selection.yaml),
which also holds each film's inputs: subtitle, video and transcript.
Asked in the terminal which one to debug, answer with its number, or `p`
to open the pick_films window and select others (run them there with
"Save and run dvc repro" if they have not run yet); then which approach.
Outputs go to debug/<film>/0/ or debug/<film>/A/ (git-ignored),
so DVC's outputs stay as DVC wrote them. The audio cache is the
pipeline's, cache/<film>/: after one `dvc repro` of the film, the audio
and the GPU model are not loaded.

Usage:
  python debug_film.py              # ask which selected film and approach
  python debug_film.py <film>       # that film (must be selected), Approach 0
  python debug_film.py <film> A     # that film, Approach A
"""

import os
import sys
from pathlib import Path

import yaml

import pick_films

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent


def selected_films():
    """{film: info} from selection.yaml, `whisper` filled in by pick_films."""
    if not pick_films.SELECTION.exists():
        return {}
    with open(pick_films.SELECTION, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("films") or {}


APPROACHES = ("0", "A")


def problem(film, info, approach="0"):
    """Why the film cannot be debugged yet, or None."""
    if approach == "0" and not (LAB / info["whisper"]).is_dir():
        return "no transcript yet for Approach 0: run dvc repro on it"
    return None


def ask_approach():
    while True:
        answer = input("Approach: 0 = WhisperX transcript, "
                       "A = force-align the subtitle [0]: ").strip().upper() or "0"
        if answer in APPROACHES:
            return answer
        print("answer 0 or A")


def ask():
    """
    Ask in the terminal which selected film and approach to debug; `p`
    reselects films.
    """
    while True:
        films = selected_films()
        print("\nFilms selected in pick_films.py:")
        for n, (film, info) in enumerate(films.items(), start=1):
            why = problem(film, info)
            print(f"  {n}) {film}" + (f"  ({why})" if why else ""))
        print("  p) select other films (opens the pick_films window)")
        answer = input("Film to debug [1]: ").strip().lower() or "1"
        if answer == "p":
            pick_films.gui(from_debugger=True)
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(films):
            film = list(films)[int(answer) - 1]
            approach = ask_approach()
            why = problem(film, films[film], approach)
            if why:
                print(f"{film}: {why} (p, then Save and run dvc repro)")
                continue
            return film, films[film], approach
        print(f"answer a number from 1 to {len(films)}, or p")


def align_args(film, info, approach="0"):
    cache = f"cache/{film}/confidence.sqlite"
    if not (LAB / cache).exists():
        print(f"note: {cache} not filled yet: the audio check loads the "
              f"video and the GPU model (run dvc repro on {film} to avoid it)")
    out = f"debug/{film}/{approach}"
    if approach == "A":
        # As in the align_A stage: the original's own text and times.
        words = [info["original"]]
        extra = ["--force-align"]
    else:
        words = [info["whisper"]]
        extra = []
    return [info["original"], *words, f"{out}/fixed.srt", *extra,
            "--audio", info["video"],
            "--report", f"{out}/fixed.report.csv",
            "--snapshots", f"{out}/steps",
            "--changes", f"{out}/changes.csv",
            "--params", "params.yaml",
            "--audio-cache", cache]


def main():
    if len(sys.argv) > 3 or (len(sys.argv) == 3
                             and sys.argv[2].upper() not in APPROACHES):
        raise SystemExit(__doc__.strip().split("Usage:")[1])
    if len(sys.argv) >= 2:
        film = sys.argv[1]
        approach = sys.argv[2].upper() if len(sys.argv) == 3 else "0"
        films = selected_films()
        if film not in films:
            raise SystemExit(f"{film} is not selected: python pick_films.py {film}")
        info = films[film]
        why = problem(film, info, approach)
        if why:
            raise SystemExit(f"{film}: {why}")
    else:
        film, info, approach = ask()
    print(f"\nDebugging {film}, Approach {approach}\n")

    # align_srt.py's paths are relative to lab/, as in dvc.yaml.
    os.chdir(LAB)
    sys.path.insert(0, str(ROOT))
    import align_srt

    sys.argv = [str(ROOT / "align_srt.py")] + align_args(film, info, approach)
    align_srt.main()


if __name__ == "__main__":
    main()
