"""
Worked example of a status flowchart: generates lab/docs/diagrams/cue-flowchart.html
(align_srt.py, film dog-man-2025). Copy it and replace the data and geometry
sections; the helpers (down, chip, box, oval, count_label, check) carry over.

    python example_gen.py [OUT.html]
"""
import math
import sys
import unicodedata

OUT = sys.argv[1] if len(sys.argv) > 1 else "lab/docs/diagrams/cue-flowchart.html"

PAPER, INK, MUTED, SOFT = "#f5f5f5", "#2d3142", "#4f5d75", "#7a8399"
ACC, ACC_T = "#eb6c36", "rgba(235,108,54,0.08)"
FS = "'Geist', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
FM = "'Geist Mono', ui-monospace, monospace"

# status lanes (columns): order chosen so every step's inputs/outputs are contiguous
A, V, R, O, I, N = 104, 248, 392, 536, 680, 824
L, RGT = 40, 888            # full-width box span
W = RGT + 40
CHIP_W, CHIP_H = 112, 28

arrows, labels, nodes, leg = [], [], [], []


def tw(s, size, mono=True):
    adv = 0.62 if mono else 0.60
    return sum(size if unicodedata.east_asian_width(c) in "WF" else size * adv for c in s)


def r4(v):
    return int(math.ceil(v / 4.0) * 4)


def sw(n):
    return 3 if n >= 1000 else (2 if n >= 100 else 1.2)


def mk(n, accent=False):
    return "arrow-accent" if accent else ("arrow-lg" if n >= 1000 else "arrow")


def down(x, y1, y2, n, accent=False, dashed=False):
    col = ACC if accent else MUTED
    d = ' stroke-dasharray="5,4"' if dashed else ""
    arrows.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2 - 1}" stroke="{col}" stroke-width="{sw(n)}"{d} marker-end="url(#{mk(n, accent)})"/>')


def count_label(x_line, ymid, text, side="right"):
    w = max(20, r4(tw(text, 8) + 8))
    if side == "right":
        x = x_line + 8 + (2 if True else 0)
    else:
        x = x_line - 10 - w
    labels.append(f'<rect x="{x}" y="{ymid - 6}" width="{w}" height="12" rx="2" fill="{PAPER}"/>')
    labels.append(f'<text x="{x + w / 2:g}" y="{ymid + 3}" fill="{MUTED}" font-size="8" font-weight="500" font-family="{FM}" text-anchor="middle" letter-spacing="0.06em">{text}</text>')
    return x, w


def box(x0, x1, y, step, name, detail, optional=False):
    w = x1 - x0
    cx = (x0 + x1) / 2
    nodes.append(f'<rect x="{x0}" y="{y}" width="{w}" height="48" rx="6" fill="{PAPER}"/>')
    if optional:
        nodes.append(f'<rect x="{x0}" y="{y}" width="{w}" height="48" rx="6" fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.40)" stroke-width="1" stroke-dasharray="4,3"/>')
    else:
        nodes.append(f'<rect x="{x0}" y="{y}" width="{w}" height="48" rx="6" fill="#ffffff" stroke="{INK}" stroke-width="1"/>')
    nodes.append(f'<rect x="{x0 + 8}" y="{y + 6}" width="24" height="12" rx="2" fill="transparent" stroke="rgba(45,49,66,0.40)" stroke-width="0.8"/>')
    nodes.append(f'<text x="{x0 + 20}" y="{y + 15}" fill="{MUTED}" font-size="7" font-family="{FM}" text-anchor="middle" letter-spacing="0.08em">{step}</text>')
    nodes.append(f'<text x="{cx:g}" y="{y + 21}" fill="{INK}" font-size="12" font-weight="600" font-family="{FS}" text-anchor="middle">{name}</text>')
    nodes.append(f'<text x="{cx:g}" y="{y + 37}" fill="{SOFT}" font-size="9" font-family="{FM}" text-anchor="middle">{detail}</text>')


def chip(cx, y, status, n, accent=False, note=None):
    """Status + count; `note` adds a second line for a change the status hides."""
    x = cx - CHIP_W // 2
    h = chip_h(note)
    if accent:
        nodes.append(f'<rect x="{x}" y="{y}" width="{CHIP_W}" height="{h}" rx="8" fill="{PAPER}"/>')
        nodes.append(f'<rect x="{x}" y="{y}" width="{CHIP_W}" height="{h}" rx="8" fill="{ACC_T}" stroke="{ACC}" stroke-width="1"/>')
    else:
        nodes.append(f'<rect x="{x}" y="{y}" width="{CHIP_W}" height="{h}" rx="8" fill="rgba(79,93,117,0.10)" stroke="{SOFT}" stroke-width="0.8"/>')
    ncol = ACC if accent else INK
    nodes.append(f'<text x="{cx}" y="{y + 17}" fill="{INK}" font-size="9" font-family="{FM}" text-anchor="middle">{status} '
                 f'<tspan font-weight="600" fill="{ncol}">{n}</tspan></text>')
    if note:
        nodes.append(f'<text x="{cx}" y="{y + 31}" fill="{MUTED}" font-size="8" font-family="{FS}" text-anchor="middle">{note}</text>')


def chip_h(note=None):
    return CHIP_H + 12 if note else CHIP_H


def oval(cx, y, status, n, accent=False):
    x = cx - 56
    nodes.append(f'<rect x="{x}" y="{y}" width="112" height="44" rx="22" fill="{PAPER}"/>')
    if accent:
        nodes.append(f'<rect x="{x}" y="{y}" width="112" height="44" rx="22" fill="{ACC_T}" stroke="{ACC}" stroke-width="1"/>')
    else:
        nodes.append(f'<rect x="{x}" y="{y}" width="112" height="44" rx="22" fill="rgba(45,49,66,0.03)" stroke="rgba(45,49,66,0.30)" stroke-width="1"/>')
    nodes.append(f'<text x="{cx}" y="{y + 20}" fill="{ACC if accent else INK}" font-size="12" font-weight="600" font-family="{FS}" text-anchor="middle">{n}</text>')
    nodes.append(f'<text x="{cx}" y="{y + 34}" fill="{MUTED}" font-size="9" font-family="{FM}" text-anchor="middle">{status}</text>')


# ---------- conservation bookkeeping: pools alive after each step ----------
pools = {}


def check(step, alive):
    assert sum(alive.values()) == 1391, (step, alive)
    pools[step] = alive


# ---------- geometry ----------
B = [None] + [112 + 132 * k for k in range(7)]   # box top per step (index = step no.)
CH = lambda k: B[k] + 72                          # chip row after step k

# start
SX = (L + RGT) // 2
nodes.append(f'<rect x="{SX - 120}" y="40" width="240" height="48" rx="24" fill="rgba(45,49,66,0.03)" stroke="rgba(45,49,66,0.30)" stroke-width="1"/>')
nodes.append(f'<text x="{SX}" y="61" fill="{INK}" font-size="12" font-weight="600" font-family="{FS}" text-anchor="middle">原始字幕 1391 条 cue</text>')
nodes.append(f'<text x="{SX}" y="76" fill="{SOFT}" font-size="9" font-family="{FM}" text-anchor="middle">words aligned (align_words)</text>')
down(SX, 88, B[1], 1391)
count_label(SX, 100, "1391")

# 01
box(L, RGT, B[1], "01", "逐条定时", "time_cues · matched words → anchored, else none")
for x, st, n in [(A, "anchored", 1213), (N, "none", 178)]:
    down(x, B[1] + 48, CH(1), n)
    chip(x, CH(1), st, n)
check("01", {"anchored": 1213, "none": 178})

# 02  (anchored only)
box(L, O + 64, B[2], "02", "剔除离群", "reject_outliers · |Δ − median(±8)| > 1.5 / 1.0 s")
down(A, CH(1) + CHIP_H, B[2], 1213)
down(A, B[2] + 48, CH(2), 1105); chip(A, CH(2), "anchored", 1105)
down(O, B[2] + 48, CH(2), 108, accent=True); chip(O, CH(2), "outlier", 108, accent=True)
down(N, CH(1) + CHIP_H, B[3], 178)                       # none passes 02
count_label(N, B[2] + 24, "178")
assert 1105 + 108 == 1213
check("02", {"anchored": 1105, "outlier": 108, "none": 178})

# 03  (none, outlier)
box(O - 64, RGT, B[3], "03", "插值补时", "interpolate_missing · orig + median Δ · outlier keeps label")
down(O, CH(2) + CHIP_H, B[3], 108)
OUTLIER_NOTE = "状态不变 · 时间改为插值"
down(O, B[3] + 48, CH(3), 108); chip(O, CH(3), "outlier", 108, note=OUTLIER_NOTE)
down(I, B[3] + 48, CH(3), 178); chip(I, CH(3), "interpolated", 178)
down(A, CH(2) + CHIP_H, B[6], 1105)                      # anchored passes 03 04 05
count_label(A, B[4] + 24, "1105")
check("03", {"anchored": 1105, "outlier": 108, "interpolated": 178})

# 04  (outlier, optional)
box(V - 64, O + 64, B[4], "04", "音频复核（仅 --audio）", "verify_with_audio · outlier ≥3 words · wins by ≥0.05", optional=True)
down(O, CH(3) + chip_h(OUTLIER_NOTE), B[4], 108, dashed=True)
down(V, B[4] + 48, CH(4), 9, dashed=True); chip(V, CH(4), "verified", 9)
down(O, B[4] + 48, CH(4), 99, dashed=True); chip(O, CH(4), "outlier", 99)
down(I, CH(3) + CHIP_H, B[5], 178)                       # interpolated passes 04
count_label(I, B[4] + 24, "178")
assert 9 + 99 == 108
check("04", {"anchored": 1105, "verified": 9, "outlier": 99, "interpolated": 178})

# 05  (outlier, interpolated)
box(R - 64, I + 64, B[5], "05", "局部搜救", "rescue_local · fuzzy ±1.5 s ≥85 · 16 outlier + 5 interp.")
down(O, CH(4) + CHIP_H, B[5], 99)
down(R, B[5] + 48, CH(5), 21); chip(R, CH(5), "rescued", 21)
down(O, B[5] + 48, CH(5), 83); chip(O, CH(5), "outlier", 83)
down(I, B[5] + 48, CH(5), 173); chip(I, CH(5), "interpolated", 173)
down(V, CH(4) + CHIP_H, B[6], 9)                         # verified passes 05
count_label(V, B[5] + 24, "9")
assert 21 + 83 + 173 == 99 + 178
check("05", {"anchored": 1105, "verified": 9, "rescued": 21, "outlier": 83, "interpolated": 173})

# 06  (PLACED: anchored, verified, rescued)
box(L, R + 64, B[6], "06", "乱序回退", "revert_out_of_order · > 1 s out of order → outlier")
down(R, CH(5) + CHIP_H, B[6], 21)
for x, st, n in [(A, "anchored", 1105), (V, "verified", 6), (R, "rescued", 21)]:
    down(x, B[6] + 48, CH(6), n)
    chip(x, CH(6), st, n)
# +3 reverted: leave 06's right edge, elbow down into 07 beside the outlier lane
PX = O - 16
arrows.append(f'<path d="M {R + 64},{B[6] + 24} H {PX - 8} A 8,8 0 0 1 {PX},{B[6] + 32} V {B[7] - 1}" fill="none" '
              f'stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
count_label(PX, CH(6) + CHIP_H + 12, "outlier +3", side="left")
down(O, CH(5) + CHIP_H, B[7], 83)                        # outlier passes 06
count_label(O, B[6] + 24, "83")
down(I, CH(5) + CHIP_H, B[7], 173)                       # interpolated passes 06
count_label(I, B[6] + 24, "173")
assert 1105 + 6 + 21 + 3 == 1105 + 9 + 21
check("06", {"anchored": 1105, "verified": 6, "rescued": 21, "outlier": 86, "interpolated": 173})

# 07  (all)
box(L, RGT, B[7], "07", "收尾定时（状态不变）", "finalize_timing · gap 0.084 s · 17 chars/s · 0.8–7 s · ≤0.5 s earlier")
for x in (A, V, R):
    pass
down(A, CH(6) + CHIP_H, B[7], 1105)
down(V, CH(6) + CHIP_H, B[7], 6)
down(R, CH(6) + CHIP_H, B[7], 21)
FY = B[7] + 48 + 24
finals = [(A, "anchored", 1105), (V, "verified", 6), (R, "rescued", 21), (O, "outlier", 86), (I, "interpolated", 173)]
for x, st, n in finals:
    acc = st == "outlier"
    down(x, B[7] + 48, FY, n, accent=acc)
    oval(x, FY, st, n, accent=acc)
assert sum(n for *_, n in finals) == 1391
check("07", {st: n for _, st, n in finals})

# ---------- legend ----------
LY = FY + 44 + 28
H = LY + 72
leg.append(f'<line x1="40" y1="{LY}" x2="{RGT}" y2="{LY}" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>')
leg.append(f'<text x="40" y="{LY + 20}" fill="{MUTED}" font-size="8" font-family="{FM}" letter-spacing="0.18em">LEGEND</text>')
iy = LY + 44


def ltext(x, t, mono=False):
    fam, size = (FM, 9) if mono else (FS, 12)
    wgt = '' if mono else ' font-weight="500"'
    leg.append(f'<text x="{x}" y="{iy + 4}" fill="{MUTED}" font-size="{size}"{wgt} font-family="{fam}">{t}</text>')
    return x + tw(t, size, mono=mono)


x = 40
leg.append(f'<rect x="{x}" y="{iy - 7}" width="28" height="14" rx="6" fill="rgba(79,93,117,0.10)" stroke="{SOFT}" stroke-width="0.8"/>')
x = ltext(x + 36, "状态 + 条数") + 20
leg.append(f'<rect x="{x}" y="{iy - 6}" width="24" height="12" rx="2" fill="#ffffff" stroke="{INK}" stroke-width="1"/>')
x = ltext(x + 32, "步骤") + 20
leg.append(f'<rect x="{x}" y="{iy - 6}" width="24" height="12" rx="2" fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.40)" stroke-width="1" stroke-dasharray="4,3"/>')
x = ltext(x + 32, "可选 --audio") + 20
x = ltext(x, "线宽") + 8
for wv, t in [(3, "≥1000"), (2, "100–999"), (1.2, "<100")]:
    leg.append(f'<line x1="{x}" y1="{iy}" x2="{x + 20}" y2="{iy}" stroke="{MUTED}" stroke-width="{wv}"/>')
    x = ltext(x + 26, t, mono=True) + 12
x += 8
leg.append(f'<line x1="{x}" y1="{iy}" x2="{x + 20}" y2="{iy}" stroke="{ACC}" stroke-width="2" marker-end="url(#arrow-accent)"/>')
x = ltext(x + 30, "outlier 去向")
assert x < RGT, x

TITLE = "数据流向：1391 条字幕如何流过七步"
DESC = ("流程图：dog-man-2025 的 1391 条 cue 按状态分列，每个状态直接连到处理它的步骤，"
        "步骤不处理的状态直线绕过；每一步前后合计 1391 条，最终为 anchored 1105、verified 6、"
        "rescued 21、outlier 86、interpolated 173。")

body = "\n        ".join(["<!-- ===== Arrows (drawn first) ===== -->"] + arrows +
                        ["<!-- ===== Count labels ===== -->"] + labels +
                        ["<!-- ===== Nodes ===== -->"] + nodes +
                        ["<!-- ===== Legend ===== -->"] + leg)

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{TITLE}</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&family=Noto+Serif:ital@0;1&family=Noto+Sans+SC:wght@400;500;600&family=Noto+Serif+SC:wght@400&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --color-paper:   #f5f5f5;
      --color-ink:     #2d3142;
      --color-muted:   #4f5d75;
      --color-soft:    #7a8399;
      --color-accent:  #eb6c36;
      --font-sans:     'Geist', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
      --font-serif:    'Instrument Serif', 'Noto Serif', 'Noto Serif SC', 'Songti SC', serif;
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

    .frame {{ max-width: {W}px; width: 100%; min-width: 0; }}
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
      margin-top: 1rem;
      font-size: 0.8rem;
      line-height: 1.6;
      color: var(--color-muted);
    }}
    .note code {{ font-family: var(--font-mono); font-size: 0.75rem; }}
    .note strong {{ color: var(--color-ink); font-weight: 600; }}

    svg {{ width: 100%; min-width: {W}px; display: block; }}
    @media print {{
      .diagram-container {{ overflow-x: visible; }}
      svg {{ min-width: 0; }}
    }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">Flowchart · align_srt.py · dog-man-2025</p>
    <h1>{TITLE}</h1>

    <div class="diagram-container">
      <svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="cue-flowchart-title cue-flowchart-desc">
        <title id="cue-flowchart-title">{TITLE}</title>
        <desc id="cue-flowchart-desc">{DESC}</desc>
        <defs>
          <marker id="arrow" markerUnits="userSpaceOnUse" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#4f5d75"/></marker>
          <marker id="arrow-lg" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><polygon points="0 0, 10 4, 0 8" fill="#4f5d75"/></marker>
          <marker id="arrow-accent" markerUnits="userSpaceOnUse" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#eb6c36"/></marker>
          <marker id="arrow-link" markerUnits="userSpaceOnUse" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#2e5aa8"/></marker>
        </defs>

        <rect width="100%" height="100%" fill="#f5f5f5"/>

        {body}
      </svg>
    </div>

    <p class="note">数字取自 dog-man-2025（1391 条 cue，带 <code>--audio</code> 运行）。每一列是一种状态：箭头进入的步骤处理该状态，步骤没有覆盖的列直线绕过，所以每一步前后合计都是 1391 条。<strong>被 02 降级的 108 条 outlier</strong>：16 条被 05 局部搜救找回，6 条经 04 音频复核保住，其余 86 条以 outlier 收尾（含 06 退回的 3 条 verified）。PLACED = <code>anchored</code>、<code>verified</code>、<code>rescued</code>。04 只在给出 <code>--audio</code> 时运行，且只复核至少 3 个词的 outlier；06 把越界的 PLACED cue 改回 <code>outlier</code> 并立即重新插值。07 只调时间、不改状态。</p>
  </div>
</body>
</html>
"""

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)
print("ok", W, H, {k: sum(v.values()) for k, v in pools.items()})
