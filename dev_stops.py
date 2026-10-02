"""
Development: pause in the debugger inside align_srt.py's steps.

align_srt.py calls stop_for_debug(step, cue) at the point where each step
decides about a line. It does nothing unless the environment variable
SUBRETIME_STOPS names a YAML file such as lab/stops.yaml:

  steps: [reject_outliers, rescue_local]   # or [all]
  cues: [1134, 1140]                       # optional: only these lines

Then it calls breakpoint() there: under VS Code's debugger the run pauses
with the step's local variables in view; in a terminal, pdb starts. The
file is read once, when align_srt.py starts. align_words works on words,
not lines: it pauses at every gap that fuzzy pairing tries, whatever
`cues` says.
"""

import os

# The steps that call stop_for_debug, in pipeline order.
STEPS = ("force_align", "align_words", "time_cues", "reject_outliers", "interpolate_missing",
         "verify_with_audio", "rescue_local", "revert_out_of_order",
         "finalize_timing")


def _load():
    path = os.environ.get("SUBRETIME_STOPS")
    if not path:
        return None
    import yaml  # development dependency, only when stops are on

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    steps = set(config.get("steps") or [])
    unknown = steps - set(STEPS) - {"all"}
    if unknown:
        raise SystemExit(f"{path}: unknown step(s) {', '.join(sorted(unknown))} "
                         f"(known: all, {', '.join(STEPS)})")
    if "all" in steps:
        steps = set(STEPS)
    cues = config.get("cues") or []
    if not all(isinstance(c, int) for c in cues):
        raise SystemExit(f"{path}: cues must be cue numbers, got {cues}")
    return steps, set(cues)


_CONFIG = _load()


def stop_for_debug(step, cue=None):
    """Pause here if the stops file asks for this step (and this cue)."""
    if _CONFIG is None:
        return
    steps, cues = _CONFIG
    if step in steps and (cue is None or not cues or cue in cues):
        breakpoint()
