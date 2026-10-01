"""
Run align_srt.py on one film of films.yaml with the align stage's
arguments, for VS Code's debugger (.vscode/launch.json).

The film's inputs come from films.yaml: its subtitle, its video, and its
transcript (`whisper`, or work/<film>/whisper, which the transcribe stage
writes). Outputs go to debug/<film>/ (git-ignored), so DVC's outputs stay
as DVC wrote them. The audio cache is the pipeline's, cache/<film>/: after
one `dvc repro` of the film, the audio and the GPU model are not loaded.

VS Code's film list (the `film` input in launch.json) cannot be read from
a file, so this script rewrites it from films.yaml: on every run, and with
--sync alone. A film added to films.yaml appears in the list after the
next run or `python debug_film.py --sync`.

Usage:
  python debug_film.py dog-man-2025-sample-1092-1151
  python debug_film.py --sync
"""

import json
import os
import re
import sys
from pathlib import Path

import yaml

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
LAUNCH = ROOT / ".vscode" / "launch.json"


def load_catalog():
    with open(LAB / "films.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def sync_launch(films):
    """
    Make the options of the `film` input in launch.json the films.yaml ids.
    Rewrites only that array, as text, so the file's comments stay.
    Returns True when the file changed.
    """
    text = LAUNCH.read_text(encoding="utf-8")
    pattern = re.compile(r'("id": "film",.*?"options": )\[.*?\]', re.S)
    if not pattern.search(text):
        raise SystemExit(f"{LAUNCH}: no `film` input with options")
    options = "[" + ", ".join(json.dumps(f) for f in films) + "]"
    new = pattern.sub(lambda m: m.group(1) + options, text, count=1)
    if new == text:
        return False
    LAUNCH.write_text(new, encoding="utf-8", newline="\n")
    return True


def align_args(film, info):
    whisper = info.get("whisper", f"work/{film}/whisper")
    if not (LAB / whisper).is_dir():
        raise SystemExit(f"{whisper} missing: run the transcribe stage for "
                         f"{film} first (pick_films.py {film}, dvc repro)")
    out = f"debug/{film}"
    cache = f"cache/{film}/confidence.sqlite"
    if not (LAB / cache).exists():
        print(f"note: {cache} not filled yet: the audio check loads the "
              f"video and the GPU model (run dvc repro on {film} to avoid it)")
    return [info["original"], whisper, f"{out}/fixed.srt",
            "--audio", info["video"],
            "--report", f"{out}/fixed.report.csv",
            "--snapshots", f"{out}/steps",
            "--changes", f"{out}/changes.csv",
            "--params", "params.yaml",
            "--audio-cache", cache]


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__.strip().split("Usage:")[1])
    catalog = load_catalog()
    if sync_launch(list(catalog)):
        print("launch.json: film list updated from films.yaml")
    if sys.argv[1] == "--sync":
        return
    film = sys.argv[1]
    if film not in catalog:
        raise SystemExit(f"not in films.yaml: {film}")

    # align_srt.py's paths are relative to lab/, as in dvc.yaml.
    os.chdir(LAB)
    sys.path.insert(0, str(ROOT))
    import align_srt

    sys.argv = [str(ROOT / "align_srt.py")] + align_args(film, catalog[film])
    align_srt.main()


if __name__ == "__main__":
    main()
