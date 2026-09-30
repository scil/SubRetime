"""Generate lab/docs/diagrams/cue-status-sankey.html: one column per step.

    python sankey_gen.py [OUT.html]

Data: dog-man-2025, 1391 cues, run with --audio (counts from
lab/out/<film>/changes.csv and steps/*.csv).
Every column is the status count AFTER that step; 07 changes no status, so it
is folded into the final column.

Asserts conservation (node in == out == height, equal column totals), constant
ribbon width, and midline control points; then runs the plugin's
verify-sankey.py logic with the plot-band window widened (its constants are
tuned to the 560px-tall shipped example) as an extra audit.
"""
from __future__ import annotations

import importlib.util
import itertools
import os
import sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "lab/docs/diagrams/cue-status-sankey.html")
# diagram-design plugin root, for the optional verify-sankey.py audit at the end
PLUGIN = Path(os.environ.get("DIAGRAM_DESIGN_PLUGIN", Path.home() / ".claude/plugins/cache/diagram-design/diagram-design/2.6.46"))

TOTAL = 1391
K = 0.5          # px per cue, one scale for the whole figure
MIN_BAND = 4.0   # px, minimum rendered ribbon

# ---------------------------------------------------------------- data
COLS = [
    ("01 time_cues", "Match & time", None),
    ("02 reject_outliers", "Reject outliers", None),
    ("03 interpolate_missing", "Interpolate", None),
    ("04 verify_with_audio", "Audio check", "OPTIONAL · --AUDIO"),
    ("05 rescue_local", "Local rescue", None),
    ("06 revert_out_of_order", "Revert order", None),
    ("07 finalize_timing", "Final", None),
]
# status counts after each step (exactly as in the brief)
COUNTS = [
    {"anchored": 1213, "none": 178},
    {"anchored": 1105, "outlier": 108, "none": 178},
    {"anchored": 1105, "outlier": 108, "interpolated": 178},
    {"anchored": 1105, "verified": 9, "outlier": 99, "interpolated": 178},
    {"anchored": 1105, "verified": 9, "outlier": 83, "rescued": 21, "interpolated": 173},
    {"anchored": 1105, "verified": 6, "outlier": 86, "rescued": 21, "interpolated": 173},
    {"anchored": 1105, "verified": 6, "outlier": 86, "rescued": 21, "interpolated": 173},
]
# transitions into column i+1: (from, to, cues)
FLOWS = [
    [("anchored", "anchored", 1105), ("anchored", "outlier", 108), ("none", "none", 178)],
    [("anchored", "anchored", 1105), ("outlier", "outlier", 108), ("none", "interpolated", 178)],
    [("anchored", "anchored", 1105), ("outlier", "verified", 9), ("outlier", "outlier", 99),
     ("interpolated", "interpolated", 178)],
    [("anchored", "anchored", 1105), ("verified", "verified", 9), ("outlier", "outlier", 83),
     ("outlier", "rescued", 16), ("interpolated", "rescued", 5), ("interpolated", "interpolated", 173)],
    [("anchored", "anchored", 1105), ("verified", "verified", 6), ("verified", "outlier", 3),
     ("outlier", "outlier", 83), ("rescued", "rescued", 21), ("interpolated", "interpolated", 173)],
    [("anchored", "anchored", 1105), ("verified", "verified", 6), ("outlier", "outlier", 86),
     ("rescued", "rescued", 21), ("interpolated", "interpolated", 173)],
]

# data-level conservation
for i, counts in enumerate(COUNTS):
    assert sum(counts.values()) == TOTAL, (i, counts)
for i, flows in enumerate(FLOWS):
    for s, n in COUNTS[i].items():
        assert sum(c for a, _, c in flows if a == s) == n, ("out", i, s)
    for s, n in COUNTS[i + 1].items():
        assert sum(c for _, b, c in flows if b == s) == n, ("in", i + 1, s)

# ---------------------------------------------------------------- widths
# Tiny flows get the 4px minimum. Their inflation must be carried by some
# stream to keep every node balanced. Free parameters: a (anchored pass-through),
# b (anchored->outlier at 02), x (none/interpolated stream), r (outlier->rescued).
v_out = [max(MIN_BAND, 6 * K), max(MIN_BAND, 3 * K)]          # 06: verified -> verified / outlier
V = sum(v_out)                                                # verified node 04..05 height
IR = max(MIN_BAND, 5 * K)                                     # 05: interpolated -> rescued


def widths(a, b, x, r):
    w = {}
    w[(0, "anchored", "anchored")] = a
    w[(0, "anchored", "outlier")] = b
    w[(0, "none", "none")] = x
    w[(1, "anchored", "anchored")] = a
    w[(1, "outlier", "outlier")] = b
    w[(1, "none", "interpolated")] = x
    w[(2, "anchored", "anchored")] = a
    w[(2, "outlier", "verified")] = V
    w[(2, "outlier", "outlier")] = b - V
    w[(2, "interpolated", "interpolated")] = x
    w[(3, "anchored", "anchored")] = a
    w[(3, "verified", "verified")] = V
    w[(3, "outlier", "outlier")] = b - V - r
    w[(3, "outlier", "rescued")] = r
    w[(3, "interpolated", "rescued")] = IR
    w[(3, "interpolated", "interpolated")] = x - IR
    w[(4, "anchored", "anchored")] = a
    w[(4, "verified", "verified")] = v_out[0]
    w[(4, "verified", "outlier")] = v_out[1]
    w[(4, "outlier", "outlier")] = b - V - r
    w[(4, "rescued", "rescued")] = r + IR
    w[(4, "interpolated", "interpolated")] = x - IR
    w[(5, "anchored", "anchored")] = a
    w[(5, "verified", "verified")] = v_out[0]
    w[(5, "outlier", "outlier")] = b - V - r + v_out[1]
    w[(5, "rescued", "rescued")] = r + IR
    w[(5, "interpolated", "interpolated")] = x - IR
    return w


def node_heights(w):
    h = []
    for i, counts in enumerate(COUNTS):
        col = {}
        for s in counts:
            if i < len(FLOWS):
                col[s] = sum(v for (j, a, _), v in w.items() if j == i and a == s)
            else:
                col[s] = sum(v for (j, _, b), v in w.items() if j == i - 1 and b == s)
        h.append(col)
    return h


MIN_BAND_NODES = {"verified", "rescued"}  # nodes that carry a min-band ribbon


def score(w):
    h = node_heights(w)
    # same reference verify-sankey.py uses: the median px-per-cue over all bars
    ratios = sorted(h[i][s] / n for i, counts in enumerate(COUNTS) for s, n in counts.items())
    ref = ratios[len(ratios) // 2]
    errs = []
    for i, counts in enumerate(COUNTS):
        for s, n in counts.items():
            if s in MIN_BAND_NODES:
                continue
            # honest against the stated K, and passing verify-sankey's median check
            errs.append(max(abs(h[i][s] / n - ref) / ref, abs(h[i][s] / n - K) / K))
    rib = []
    for i, flows in enumerate(FLOWS):
        for a, b_, c in flows:
            if c * K >= MIN_BAND:
                rib.append(abs(w[(i, a, b_)] - c * K) / (c * K))
    return (round(max(errs), 4), round(sum(e * e for e in rib), 6))


def frange(lo, hi, step=0.25):
    n = int(round((hi - lo) / step))
    return [lo + step * i for i in range(n + 1)]


best = None
for a, b, x, r in itertools.product(frange(552, 553), frange(53, 60), frange(89, 91), frange(5, 9)):
    if b - V - r <= 0 or x - IR <= 0:
        continue
    s = score(widths(a, b, x, r))
    if best is None or s < best[0]:
        best = (s, (a, b, x, r))
(A_W, B_W, X_W, R_W) = best[1]
W = widths(A_W, B_W, X_W, R_W)
H = node_heights(W)
MAX_NODE_ERR = best[0][0]

# ---------------------------------------------------------------- layout
COL_STEP = 140   # px between status columns
COL_X = [120 + COL_STEP * i for i in range(7)]
VIEW_W, VIEW_H = COL_X[-1] + 160, 1120
BAR_W = 12
TOP = 136
SLOT = {  # node tops per column
    "anchored": [TOP] * 7,
    "verified": [None, None, None, 728, 728, 728, 728],
    "outlier": [None, 728, 728, 776, 776, 772, 772],
    "rescued": [None, None, None, None, 856, 856, 856],
    "none": [908, 908, None, None, None, None, None],
    "interpolated": [None, None, 908, 908, 908, 908, 908],
}
NODE = []  # per column: status -> (top, height)
for i, counts in enumerate(COUNTS):
    col = {}
    for s in counts:
        col[s] = (SLOT[s][i], H[i][s])
    NODE.append(col)
# gutters and ordering sanity
for i, col in enumerate(NODE):
    spans = sorted((t, t + h, s) for s, (t, h) in col.items())
    for (t0, b0, s0), (t1, b1, s1) in zip(spans, spans[1:]):
        assert t1 - b0 >= 36, ("gutter too small", i, s0, s1, t1 - b0)

# ribbons: stack outflows by target top, inflows by source top
RIBBONS = []
for i, flows in enumerate(FLOWS):
    out_cursor = {s: NODE[i][s][0] for s in NODE[i]}
    in_cursor = {s: NODE[i + 1][s][0] for s in NODE[i + 1]}
    by_target = sorted(flows, key=lambda f: (NODE[i][f[0]][0], NODE[i + 1][f[1]][0]))
    placed = {}
    for a, b_, c in sorted(flows, key=lambda f: (NODE[i][f[0]][0], NODE[i + 1][f[1]][0])):
        wv = W[(i, a, b_)]
        placed[(a, b_)] = [out_cursor[a], None, wv, c]
        out_cursor[a] += wv
    for a, b_, c in sorted(flows, key=lambda f: (NODE[i + 1][f[1]][0], NODE[i][f[0]][0])):
        placed[(a, b_)][1] = in_cursor[b_]
        in_cursor[b_] += placed[(a, b_)][2]
    for (a, b_), (y0, y1, wv, c) in placed.items():
        RIBBONS.append(dict(col=i, src=a, dst=b_, y0=y0, y1=y1, w=wv, cues=c))
    # conservation at pixel level
    for s, (t, h) in NODE[i].items():
        assert abs(out_cursor[s] - (t + h)) < 1e-9, ("out", i, s)
    for s, (t, h) in NODE[i + 1].items():
        assert abs(in_cursor[s] - (t + h)) < 1e-9, ("in", i + 1, s)

col_totals = [sum(h for _, h in col.values()) for col in NODE]
assert all(abs(t - col_totals[0]) < 1e-9 for t in col_totals), col_totals
assert abs(col_totals[0] - TOTAL * K) / (TOTAL * K) < 0.01, col_totals  # min-band inflation only


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------- styles
GREY = "79,93,117"
CORAL = "235,108,54"
OUTLIER_STREAM = {(0, "anchored", "outlier"), (4, "verified", "outlier")} | {
    (i, "outlier", "outlier") for i in range(1, 6)}
OPTIONAL = {(2, "outlier", "verified")}


def ribbon_style(rb):
    key = (rb["col"], rb["src"], rb["dst"])
    change = rb["src"] != rb["dst"]
    if key in OUTLIER_STREAM:
        return "coral", f"rgba({CORAL},{0.42 if change else 0.24})"
    return ("change" if change else "pass"), f"rgba({GREY},{0.32 if change else 0.12})"


SANS = "'Geist', sans-serif"
MONO = "'Geist Mono', monospace"
SERIF = "'Instrument Serif', serif"
INK, MUTED, SOFT, PAPER = "#2d3142", "#4f5d75", "#7a8399", "#f5f5f5"

svg = []
add = svg.append
add(f'<rect width="100%" height="100%" fill="{PAPER}"/>')

# column headers
add("<!-- Column headers: every column is the status count AFTER that step -->")
for i, (code, zh, tag) in enumerate(COLS):
    cx = COL_X[i] + BAR_W / 2
    add(f'<text x="{fmt(cx)}" y="52" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{code}</text>')
    add(f'<text x="{fmt(cx)}" y="72" fill="{INK}" font-size="12" font-weight="500" font-family="{SANS}" text-anchor="middle">{zh}</text>')
    if tag:
        add(f'<text x="{fmt(cx)}" y="90" fill="{MUTED}" font-size="8" font-family="{MONO}" text-anchor="middle" letter-spacing="0.14em">{tag}</text>')
    if i == 6:
        add(f'<text x="{fmt(cx)}" y="90" fill="{MUTED}" font-size="8" font-family="{MONO}" text-anchor="middle" letter-spacing="0.14em">STATUS UNCHANGED</text>')


def ribbon_path(rb):
    x0 = COL_X[rb["col"]] + BAR_W
    x1 = COL_X[rb["col"] + 1]
    mid = (x0 + x1) / 2
    y0t, y1t = rb["y0"], rb["y1"]
    y0b, y1b = y0t + rb["w"], y1t + rb["w"]
    f = fmt
    return (f"M{x0},{f(y0t)} C{f(mid)},{f(y0t)} {f(mid)},{f(y1t)} {x1},{f(y1t)} "
            f"L{x1},{f(y1b)} C{f(mid)},{f(y1b)} {f(mid)},{f(y0b)} {x0},{f(y0b)} Z")


order = {"pass": 0, "change": 1, "coral": 2}
add("<!-- Ribbons: calm pass-throughs first, status changes next, the outlier stream last -->")
for rb in sorted(RIBBONS, key=lambda r: order[ribbon_style(r)[0]]):
    kind, fill = ribbon_style(rb)
    extra = ""
    if (rb["col"], rb["src"], rb["dst"]) in OPTIONAL:
        extra = f' stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3"'
    add(f'<!-- {COLS[rb["col"] + 1][0][:2]}: {rb["src"]} -> {rb["dst"]} {rb["cues"]} cues, {fmt(rb["w"])}px -->')
    add(f'<path d="{ribbon_path(rb)}" fill="{fill}"{extra}/>')

add("<!-- Node bars -->")
for i, col in enumerate(NODE):
    for s, (t, h) in col.items():
        add(f'<rect x="{COL_X[i]}" y="{fmt(t)}" width="{BAR_W}" height="{fmt(h)}" fill="{INK}"/>')

# labels
SUBLABEL = {(4, "rescued"): "21 = 16 + 5", (5, "outlier"): "86 = 83 + 3", (6, "outlier"): "86 = 83 + 3 reverted"}


def show_name(i, s):
    if i in (0, 6):
        return True
    prev = COUNTS[i - 1].get(s)
    return prev != COUNTS[i][s]


add("<!-- Labels: names only where a status appears or its count changes; otherwise the count alone -->")
for i, col in enumerate(NODE):
    for s, (t, h) in col.items():
        value = SUBLABEL.get((i, s), str(COUNTS[i][s]))
        name = show_name(i, s)
        if i == 0:
            cy = t + h / 2
            add(f'<text x="{COL_X[0] - 16}" y="{fmt(cy - 2)}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="end">{s}</text>')
            add(f'<text x="{COL_X[0] - 16}" y="{fmt(cy + 12)}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="end">{value}</text>')
        elif i == 6:
            cy = t + h / 2
            x = COL_X[6] + BAR_W + 16
            add(f'<text x="{x}" y="{fmt(cy - 2)}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="start">{s}</text>')
            add(f'<text x="{x}" y="{fmt(cy + 12)}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="start">{value}</text>')
        else:
            cx = COL_X[i] + BAR_W / 2
            if name:
                add(f'<text x="{fmt(cx)}" y="{fmt(t - 20)}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{s}</text>')
            add(f'<text x="{fmt(cx)}" y="{fmt(t - 6)}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{value}</text>')

# chip under 03's outlier node: status unchanged, time re-set
t, h = NODE[2]["outlier"]
CHIP_TEXT = "status kept · time re-set"
chip_w, chip_top, chip_h = 168, 800, 24
assert chip_top - (t + h) >= 12
# right edge just past 03's bar: the 03->04 ribbons are still flat there
x1 = COL_X[2] + BAR_W + 32
x0 = x1 - chip_w
chip_cx = (x0 + x1) // 2
y0, y1 = chip_top, chip_top + chip_h
add("<!-- Chip: 03 keeps the outlier label and only re-times these cues -->")
for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
    add(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="{SOFT}" stroke-width="0.8"/>')
add(f'<text x="{chip_cx}" y="{y0 + 16}" fill="{MUTED}" font-size="12" font-weight="500" font-family="{SANS}" text-anchor="middle">{CHIP_TEXT}</text>')

# legend
LY = 1028
add("<!-- Legend -->")
add(f'<line x1="40" y1="{LY}" x2="{VIEW_W - 40}" y2="{LY}" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>')
add(f'<text x="40" y="{LY + 20}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.18em">LEGEND</text>')
sy = LY + 36
items = [
    (f'fill="rgba({GREY},0.12)" stroke="{MUTED}" stroke-width="1"', "status unchanged"),
    (f'fill="rgba({GREY},0.32)" stroke="{MUTED}" stroke-width="1"', "status changed"),
    (f'fill="rgba({CORAL},0.32)" stroke="#eb6c36" stroke-width="1"', "outlier stream: 02 demotion → final 86"),
    (f'fill="rgba({GREY},0.32)" stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3"', "optional 04 (--audio only)"),
    (f'fill="{INK}"', "node: status count after the step"),
]
x = 40
for attrs, label in items:
    add(f'<rect x="{x}" y="{sy}" width="16" height="8" {attrs}/>')
    add(f'<text x="{x + 24}" y="{sy + 8}" fill="{MUTED}" font-size="12" font-weight="500" font-family="{SANS}">{label}</text>')
    x += 24 + round(len(label) * 6.4) + 24
assert x - 24 <= VIEW_W - 40, ("legend too wide", x)
add(f'<text x="40" y="{sy + 36}" fill="{MUTED}" font-size="14" font-style="italic" font-family="{SERIF}">'
    f'Of the 108 outliers, 22 end up back on WhisperX timing; 86 stay interpolated.</text>')

svg_body = "\n        ".join(svg)

notes = [
    "One column per step: each column is the status count after that step. Only 07 finalize_timing "
    "is folded into the final column; it adjusts timing (no overlap, reading speed, min/max duration) "
    "and changes no status.",
    f"Scale: k = {K} px per cue throughout; every column is {fmt(col_totals[0])}px = 1391 cues "
    "(the generator asserts conservation per node and per column). Node heights follow the true counts.",
    f"Minimum band 4px: the 3-, 5- and 6-cue bands are drawn at 4px (true size {fmt(3 * K)}–{fmt(6 * K)}px), "
    f"so the verified node at 04–05 (9 cues) is {fmt(V)}px to hold 06's 6 + 3 split, and rescued (21 cues, "
    f"including a 4px 5-cue band) is {fmt(R_W + IR)}px. The extra height is absorbed inside the outlier "
    f"stream; every other node is within {MAX_NODE_ERR * 100:.1f}% of its count. All printed numbers are true counts.",
    "05 acts on the 99 outliers left after 04 and the 178 interpolated cues: it rescues 16 outliers and "
    "5 interpolated, 21 in all. 06 sends 3 verified cues back to outlier and re-interpolates them; "
    "no anchored or rescued cue was reverted in this run.",
]
notes_html = "\n    ".join(f'<p class="note">{i + 1}. {n}</p>' for i, n in enumerate(notes))

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dog Man: how 1391 cues flow through seven steps</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --color-paper:   #f5f5f5;
      --color-ink:     #2d3142;
      --color-muted:   #4f5d75;
      --color-accent:  #eb6c36;
      --font-sans:     'Geist', system-ui, sans-serif;
      --font-serif:    'Instrument Serif', serif;
      --font-mono:     'Geist Mono', ui-monospace, monospace;
    }}

    body {{
      font-family: var(--font-sans);
      background: var(--color-paper);
      color: var(--color-ink);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 3rem 2rem;
    }}

    .frame {{ max-width: {VIEW_W}px; width: 100%; min-width: 0; }}
    .diagram-container {{ width: 100%; overflow-x: auto; }}

    .eyebrow {{
      font-family: var(--font-mono);
      font-size: 0.66rem;
      font-weight: 500;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--color-muted);
      margin-bottom: 0.5rem;
    }}

    h1 {{
      font-family: var(--font-serif);
      font-size: clamp(1.5rem, 2.4vw + 0.75rem, 2rem);
      font-weight: 400;
      letter-spacing: -0.02em;
      line-height: 1.15;
      color: var(--color-ink);
      margin-bottom: 1.5rem;
    }}

    .note {{
      margin-top: 0.4rem;
      font-size: 0.8rem;
      line-height: 1.6;
      color: var(--color-muted);
      max-width: 1040px;
    }}
    .note:first-of-type {{ margin-top: 1rem; }}

    svg {{ width: 100%; min-width: {VIEW_W}px; display: block; }}
    @media print {{
      .diagram-container {{ overflow-x: visible; }}
      svg {{ min-width: 0; }}
    }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">Sankey · dog-man-2025 · align_srt.py --audio</p>
    <h1>Dog Man: how 1391 cues flow through seven steps</h1>

    <div class="diagram-container">
      <svg viewBox="0 0 {VIEW_W} {VIEW_H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="cue-status-sankey-title cue-status-sankey-desc">
        <title id="cue-status-sankey-title">Dog Man: how 1391 cues flow through seven steps</title>
        <desc id="cue-status-sankey-desc">Sankey, one column per step: dog-man-2025's 1391 cues are 1213 anchored and 178 none after 01; 02 demotes 108 to outlier, 03 only re-times them, 04 verifies 9, 05 rescues 16 of the remaining 99, 06 reverts 3, and 86 end as outlier; the outlier stream is highlighted in coral.</desc>

        {svg_body}
      </svg>
    </div>

    {notes_html}
  </div>
</body>
</html>
"""
OUT.write_text(html, encoding="utf-8")

# ---------------------------------------------------------------- report
print(f"widths: a={A_W} b={B_W} x={X_W} r={R_W}  V={V}  IR={IR}")
print(f"column total px = {col_totals[0]} (1391 * K = {TOTAL * K})")
for i, col in enumerate(NODE):
    row = []
    for s, (t, h) in col.items():
        n = COUNTS[i][s]
        row.append(f"{s}:{n}->{fmt(h)}px({(h / (n * K) - 1) * 100:+.1f}%)")
    print(f"col{i + 1}: " + "  ".join(row))
print("max node error (excl. verified):", MAX_NODE_ERR)

# audit with verify-sankey.py, band window widened to this canvas
spec = importlib.util.spec_from_file_location("verify_sankey", PLUGIN / "scripts" / "verify-sankey.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)
vs.BAND_BOTTOM = LY - 8
findings = vs.check(OUT)
print(f"verify-sankey (band 30..{vs.BAND_BOTTOM}): {len(findings)} finding(s)")
for f in findings:
    print("  ", f)
