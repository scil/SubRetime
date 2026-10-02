"""
Draw how one run's cues flow between statuses, step by step, from the
snapshots align_srt.py writes with --snapshots (out/<film>/steps/NN_<step>.csv).

    python flow_diagrams.py out/<film> [--out DIR] [--title TEXT]

Writes four files to DIR (default: out/<film>/diagrams):
  flowchart.html / .svg   one column per status; a step box spans the statuses
                          it processes, the others pass straight by
  sankey.html / .svg      one column per step; band width = number of cues

Every number comes from the snapshots: a cue's status before and after a step
is read from consecutive snapshot files (row order is the subtitle order), so
the counts conserve by construction. Which statuses a step processes is a rule
of align_srt.py, not data, and lives in CONSUMES below.
"""
import argparse
import csv
import html
import re
from collections import Counter
from pathlib import Path

# Which statuses each step looks at (align_subtitles() in align_srt.py).
# A step missing here is assumed to look at every status.
CONSUMES = {
    "time_cues": {"original"},
    "reject_outliers": {"anchored"},
    "interpolate_missing": {"none", "outlier"},
    "verify_with_audio": {"outlier"},
    "rescue_local": {"outlier", "interpolated"},
    "revert_out_of_order": {"anchored", "verified", "rescued"},
}
NICE = {
    "time_cues": "Match &amp; time",
    "reject_outliers": "Reject outliers",
    "interpolate_missing": "Interpolate",
    "verify_with_audio": "Audio check",
    "rescue_local": "Local rescue",
    "revert_out_of_order": "Revert order",
    "finalize_timing": "Finalize timing",
}
RULE = {
    "time_cues": "matched words → anchored, else none",
    "reject_outliers": "|Δ − median of neighbours| too large → outlier",
    "interpolate_missing": "orig + median Δ · outlier keeps its label",
    "verify_with_audio": "outlier ≥3 words · audio prefers WhisperX → verified",
    "rescue_local": "fuzzy search near the expected time → rescued",
    "revert_out_of_order": "out of order by > 1 s → outlier",
    "finalize_timing": "no overlap · reading time · status unchanged",
}
OPTIONAL = {"verify_with_audio"}   # runs only with --audio
ACCENT = "outlier"                 # the stream both diagrams highlight
# Column order: every step's statuses sit next to each other, so step boxes
# are single spans and pass-by lines are straight.
ORDER = ["anchored", "verified", "rescued", "outlier", "interpolated", "none"]

PAPER, INK, MUTED, SOFT = "#f5f5f5", "#2d3142", "#4f5d75", "#7a8399"
ACC, ACC_T = "#eb6c36", "rgba(235,108,54,0.08)"
SANS, MONO, SERIF = "'Geist', sans-serif", "'Geist Mono', monospace", "'Instrument Serif', serif"
FONTS = ("https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1"
         "&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap")


# ---------------------------------------------------------------- data

class Run:
    def __init__(self, steps_dir):
        files, rows = [], []
        for f in sorted(Path(steps_dir).glob("[0-9][0-9]_*.csv")):
            with open(f, encoding="utf-8", newline="") as fh:
                snap = list(csv.DictReader(fh))
            # cue snapshots only; 00_align_words.csv has one row per word
            if snap and "status" in snap[0]:
                files.append(f)
                rows.append(snap)
        if not files:
            raise SystemExit(f"no cue snapshots in {steps_dir}")
        self.steps = [re.sub(r"^\d+_", "", f.stem) for f in files]
        self.nums = [f.stem[:2] for f in files]
        self.total = len(rows[0])
        assert all(len(r) == self.total for r in rows), "snapshots differ in length"
        prev_status = ["original"] * self.total
        prev_start = [None] * self.total
        self.before, self.after, self.flows, self.retimed = [], [], [], []
        for snap in rows:
            status = [r["status"] for r in snap]
            start = [float(r["start"]) if r["start"] else None for r in snap]
            self.before.append(Counter(prev_status))
            self.after.append(Counter(status))
            self.flows.append(Counter(zip(prev_status, status)))
            self.retimed.append(Counter(
                s for s, p, a, b in zip(status, prev_status, prev_start, start)
                if s == p and a is not None and b is not None and abs(a - b) >= 0.0005))
            prev_status, prev_start = status, start
        seen = {s for c in self.after for s in c}
        self.statuses = [s for s in ORDER if s in seen] + sorted(seen - set(ORDER))

    def consumed(self, k):
        rule = CONSUMES.get(self.steps[k])
        present = {s for s, n in self.before[k].items() if n}
        return present if rule is None else present & rule


def tier(n):
    return 3 if n >= 1000 else (2 if n >= 100 else 1.2)


def text_w(s, size, mono=True):
    return len(html.unescape(s)) * size * (0.62 if mono else 0.6)


# ---------------------------------------------------------------- page

def page(title, desc, slug, eyebrow, width, height, body, notes):
    svg = svg_doc(title, desc, slug, width, height, body, standalone=False)
    notes_html = "\n    ".join(f'<p class="note">{n}</p>' for n in notes)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link href="{html.escape(FONTS)}" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Geist', system-ui, sans-serif; background: {PAPER}; color: {INK};
           min-height: 100vh; display: flex; justify-content: center; padding: 3rem 2rem; }}
    .frame {{ max-width: {width}px; width: 100%; min-width: 0; }}
    .diagram-container {{ width: 100%; overflow-x: auto; }}
    .eyebrow {{ font-family: 'Geist Mono', monospace; font-size: .66rem; font-weight: 500;
               letter-spacing: .18em; text-transform: uppercase; color: {MUTED}; margin-bottom: .5rem; }}
    h1 {{ font-family: 'Instrument Serif', serif; font-size: clamp(1.5rem, 2.4vw + .75rem, 2rem);
         font-weight: 400; letter-spacing: -.02em; line-height: 1.15; margin-bottom: 1.5rem; }}
    .note {{ margin-top: .5rem; font-size: .8rem; line-height: 1.6; color: {MUTED}; max-width: 960px; }}
    .note code {{ font-family: 'Geist Mono', monospace; font-size: .75rem; }}
    svg {{ width: 100%; min-width: {width}px; display: block; }}
    @media print {{ .diagram-container {{ overflow-x: visible; }} svg {{ min-width: 0; }} }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{title}</h1>
    <div class="diagram-container">
      {svg}
    </div>
    {notes_html}
  </div>
</body>
</html>
"""


def svg_doc(title, desc, slug, width, height, body, standalone=True):
    style = ""
    if standalone:
        style = f"<style>@import url('{html.escape(FONTS)}');</style>"
    markers = "".join(
        f'<marker id="{slug}-{name}" markerUnits="userSpaceOnUse" markerWidth="{w}" markerHeight="{h}" '
        f'refX="{w - 1}" refY="{h / 2:g}" orient="auto"><polygon points="0 0, {w} {h / 2:g}, 0 {h}" fill="{col}"/></marker>'
        for name, w, h, col in [("arrow", 8, 6, MUTED), ("arrow-lg", 10, 8, MUTED), ("arrow-accent", 8, 6, ACC)])
    doc = (f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-labelledby="{slug}-title {slug}-desc">\n'
           f'<title id="{slug}-title">{title}</title>\n<desc id="{slug}-desc">{desc}</desc>\n'
           f'<defs>{style}{markers}</defs>\n'
           f'<rect width="100%" height="100%" fill="{PAPER}"/>\n' + "\n".join(body) + "\n</svg>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + doc) if standalone else doc


def legend(y, width, items):
    """items: (swatch drawn at x,y, label), left to right, wrapping into rows.
    Returns the elements and the total height of the legend strip."""
    out = [f'<line x1="40" y1="{y}" x2="{width - 40}" y2="{y}" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>',
           f'<text x="40" y="{y + 20}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.18em">LEGEND</text>']
    x, iy = 40, y + 44
    for swatch, label in items:
        item_w = 30 + text_w(label, 12, mono=False)
        if x > 40 and x + item_w > width - 40:
            x, iy = 40, iy + 24
        out.append(swatch(x, iy))
        out.append(f'<text x="{x + 30}" y="{iy + 4}" fill="{MUTED}" font-size="12" font-weight="500" font-family="{SANS}">{label}</text>')
        x += item_w + 24
    return out, iy + 28 - y


def sw_line(width, color=MUTED, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return lambda x, y: f'<line x1="{x}" y1="{y}" x2="{x + 22}" y2="{y}" stroke="{color}" stroke-width="{width}"{d}/>'


def sw_rect(attrs, w=22, h=12, rx=3):
    return lambda x, y: f'<rect x="{x}" y="{y - h / 2:g}" width="{w}" height="{h}" rx="{rx}" {attrs}/>'


# ---------------------------------------------------------------- flowchart

def flowchart(run, title, slug):
    cols = {s: 104 + 144 * i for i, s in enumerate(run.statuses)}
    width = max(cols.values()) + 104
    left, right = 40, width - 40
    mid = (left + right) // 2
    chip_w, chip_h, note_h, box_h, row = 112, 28, 12, 48, 140
    arrows, labels, nodes = [], [], []
    acc_seen = set()

    def arrow(x, y1, y2, n, accent=False, dashed=False):
        col = ACC if accent else MUTED
        mk = "arrow-accent" if accent else ("arrow-lg" if n >= 1000 else "arrow")
        d = ' stroke-dasharray="5,4"' if dashed else ""
        arrows.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2 - 1}" stroke="{col}" '
                      f'stroke-width="{tier(n)}"{d} marker-end="url(#{slug}-{mk})"/>')

    def count_label(x, y, text, side=1):
        """Masked label 10 px beside a vertical line at x (side 1: right, -1: left)."""
        w = round(max(20, text_w(text, 8) + 10))
        lx = x + 10 if side > 0 else x - 10 - w
        labels.append(f'<rect x="{lx}" y="{y - 6:g}" width="{w}" height="12" rx="2" fill="{PAPER}"/>')
        labels.append(f'<text x="{lx + w / 2:g}" y="{y + 3:g}" fill="{MUTED}" font-size="8" font-weight="500" '
                      f'font-family="{MONO}" text-anchor="middle">{text}</text>')

    def box(x0, x1, y, num, step, optional):
        cx = (x0 + x1) / 2
        style = (f'fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.40)" stroke-dasharray="4,3"'
                 if optional else f'fill="#ffffff" stroke="{INK}"')
        name = NICE.get(step, step) + (" (--audio only)" if optional else "")
        nodes.extend([f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="{box_h}" rx="6" fill="{PAPER}"/>',
                  f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="{box_h}" rx="6" {style} stroke-width="1"/>',
                  f'<rect x="{x0 + 8}" y="{y + 6}" width="24" height="12" rx="2" fill="none" stroke="rgba(45,49,66,0.40)" stroke-width="0.8"/>',
                  f'<text x="{x0 + 20}" y="{y + 15}" fill="{MUTED}" font-size="7" font-family="{MONO}" text-anchor="middle">{num}</text>',
                  f'<text x="{cx:g}" y="{y + 21}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{name}</text>',
                  f'<text x="{cx:g}" y="{y + 37}" fill="{SOFT}" font-size="9" font-family="{MONO}" text-anchor="middle">{step} · {RULE.get(step, "")}</text>'])

    def chip(s, y, n, note, accent, final):
        x = cols[s] - chip_w // 2
        h = 44 if final else chip_h + (note_h if note else 0)
        fill = (f'fill="{ACC_T}" stroke="{ACC}"' if accent else
                ('fill="rgba(45,49,66,0.03)" stroke="rgba(45,49,66,0.30)"' if final else
                 f'fill="rgba(79,93,117,0.10)" stroke="{SOFT}"'))
        nodes.append(f'<rect x="{x}" y="{y}" width="{chip_w}" height="{h}" rx="{22 if final else 8}" fill="{PAPER}"/>')
        nodes.append(f'<rect x="{x}" y="{y}" width="{chip_w}" height="{h}" rx="{22 if final else 8}" {fill} stroke-width="1"/>')
        if final:
            nodes.append(f'<text x="{cols[s]}" y="{y + 20}" fill="{ACC if accent else INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{n}</text>')
            nodes.append(f'<text x="{cols[s]}" y="{y + 34}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{s}</text>')
        else:
            nodes.append(f'<text x="{cols[s]}" y="{y + 17}" fill="{INK}" font-size="9" font-family="{MONO}" text-anchor="middle">{s} '
                         f'<tspan font-weight="600" fill="{ACC if accent else INK}">{n}</tspan></text>')
            if note:
                nodes.append(f'<text x="{cols[s]}" y="{y + 31}" fill="{MUTED}" font-size="8" font-family="{SANS}" text-anchor="middle">{note}</text>')
        return y + h

    # start pill
    nodes += [f'<rect x="{mid - 120}" y="40" width="240" height="48" rx="24" fill="rgba(45,49,66,0.03)" stroke="rgba(45,49,66,0.30)" stroke-width="1"/>',
              f'<text x="{mid}" y="61" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">Original subtitle · {run.total} cues</text>',
              f'<text x="{mid}" y="76" fill="{SOFT}" font-size="9" font-family="{MONO}" text-anchor="middle">words aligned (align_words)</text>']
    line_at = {"original": (mid, 88)}   # status -> (x, y where its line continues)
    jumps = {}                          # status -> [(x, y, n)] cues jumping in from a side
    y = 112
    last = len(run.steps) - 1
    for k, step in enumerate(run.steps):
        consumed = run.consumed(k)
        assert consumed, f"step {step} has nothing to process"
        flows = {(b, a): n for (b, a), n in run.flows[k].items() if n}
        produced = {a for (b, a) in flows if b in consumed}
        passing = {s for s, n in run.before[k].items() if n} - consumed
        jumping = produced & passing
        optional = step in OPTIONAL
        if "original" in consumed or k == last or CONSUMES.get(step) is None:
            x0, x1 = left, right
        else:
            span = [cols[s] for s in (consumed | produced) - jumping]
            x0, x1 = min(span) - 64, max(span) + 64
        inside = [s for s in passing if x0 < cols[s] < x1]
        assert not inside, f"{step}: {inside} would pass behind the box; reorder ORDER"
        # lines into the box
        for s in consumed:
            if s in line_at:
                x, y0 = line_at[s]
                arrow(x, y0, y, run.before[k][s] - sum(n for *_, n in jumps.get(s, [])),
                      dashed=optional and s != "original")
                if s == "original":
                    count_label(x, (y0 + y) / 2, str(run.total))
            for (edge, tx, side), jy, n in jumps.pop(s, []):
                arrows.append(f'<path d="M {edge},{jy:g} H {tx - 8 * side} A 8,8 0 0 {1 if side > 0 else 0} {tx},{jy + 8:g} V {y - 1}" '
                              f'fill="none" stroke="{MUTED}" stroke-width="{tier(n)}" marker-end="url(#{slug}-arrow)"/>')
                count_label(tx, y - 16, f"{s} +{n}", side=-side)
        # pass-by labels: once per segment, beside the first box it passes
        for s in passing:
            if line_at[s][1] < y and (s, "labelled") not in line_at:
                count_label(cols[s], y + box_h / 2, str(run.before[k][s]))
                line_at[(s, "labelled")] = True
        box(x0, x1, y, run.nums[k], step, optional)
        # outputs
        cy = y + box_h + 24
        bottom = cy
        for a in [s for s in run.statuses if s in produced - jumping]:
            n = run.after[k][a]
            accent = a == ACCENT and (a not in acc_seen or k == last)
            acc_seen.add(a)
            note = f"{run.retimed[k][a]} re-timed" if run.retimed[k][a] and k != last and a in consumed else None
            arrow(cols[a], y + box_h, cy, n, accent=accent, dashed=optional)
            end = chip(a, cy, n, note, accent, final=k == last)
            line_at[a] = (cols[a], end)
            line_at.pop((a, "labelled"), None)
            bottom = max(bottom, end)
        for a in jumping:
            n = sum(v for (b, t), v in flows.items() if t == a and b in consumed)
            side = 1 if cols[a] > x1 else -1
            edge = x1 if side > 0 else x0
            jumps.setdefault(a, []).append(((edge, cols[a] - 16 * side, side), y + box_h / 2, n))
        y = max(y + row, bottom + 24)

    fy = y - 24
    leg, leg_h = legend(fy + 28, width, [
        (sw_rect(f'fill="rgba(79,93,117,0.10)" stroke="{SOFT}" stroke-width="0.8"', rx=6), "status + count"),
        (sw_rect(f'fill="#ffffff" stroke="{INK}" stroke-width="1"', rx=2), "step"),
        (sw_rect('fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.40)" stroke-width="1" stroke-dasharray="4,3"', rx=2), "optional (--audio)"),
        (sw_line(3), "≥1000"), (sw_line(2), "100–999"), (sw_line(1.2), "&lt;100"),
        (sw_line(2, ACC), f"{ACCENT} path"),
    ])
    height = fy + 28 + leg_h
    final = run.after[-1]
    desc = (f"Flowchart: {run.total} cues in one column per status; each status connects straight to the step "
            f"that processes it and passes by the others; final counts "
            + ", ".join(f"{s} {final[s]}" for s in run.statuses if final[s]) + ".")
    return width, height, arrows + labels + nodes + leg, desc


# ---------------------------------------------------------------- sankey

def sankey(run, title, slug):
    n_cols = len(run.steps)
    col_x = [120 + 140 * i for i in range(n_cols)]
    bar_w, gutter, top = 12, 52, 136
    k_px = 640 / run.total
    width = col_x[-1] + 180
    # one slot per status, the same in every column, so unchanged bands run straight
    slot, y = {}, top
    for s in run.statuses:
        h = max(c[s] for c in run.after) * k_px
        if h:
            slot[s] = y
            y += h + gutter
    bottom = y - gutter
    order = {s: i for i, s in enumerate(run.statuses)}
    body = []

    for i, step in enumerate(run.steps):
        cx = col_x[i] + bar_w / 2
        body.append(f'<text x="{cx:g}" y="52" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{run.nums[i]} {step}</text>')
        body.append(f'<text x="{cx:g}" y="72" fill="{INK}" font-size="12" font-weight="500" font-family="{SANS}" text-anchor="middle">{NICE.get(step, step)}</text>')
        if step in OPTIONAL:
            body.append(f'<text x="{cx:g}" y="90" fill="{MUTED}" font-size="8" font-family="{MONO}" text-anchor="middle" letter-spacing="0.14em">OPTIONAL · --AUDIO</text>')

    ribbons = []
    for i in range(1, n_cols):
        flows = [(b, a, n) for (b, a), n in run.flows[i].items() if n]
        out_y = {s: slot[s] for s in slot}
        in_y = {s: slot[s] for s in slot}
        placed = {}
        for b, a, n in sorted(flows, key=lambda f: (order[f[0]], order[f[1]])):
            placed[(b, a)] = [out_y[b], None, n * k_px, n]
            out_y[b] += n * k_px
        for b, a, n in sorted(flows, key=lambda f: (order[f[1]], order[f[0]])):
            placed[(b, a)][1] = in_y[a]
            in_y[a] += n * k_px
        for (b, a), (y0, y1, w, n) in placed.items():
            ribbons.append((i, b, a, y0, y1, w, n))

    def style(b, a):
        if a == ACCENT:
            return 2, f"rgba(235,108,54,{0.24 if a == b else 0.42})"
        return (0, "rgba(79,93,117,0.12)") if a == b else (1, "rgba(79,93,117,0.32)")

    for i, b, a, y0, y1, w, n in sorted(ribbons, key=lambda r: style(r[1], r[2])[0]):
        _, fill = style(b, a)
        x0, x1 = col_x[i - 1] + bar_w, col_x[i]
        m = (x0 + x1) / 2
        extra = ""
        if run.steps[i] in OPTIONAL and a != b:
            extra = f' stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3"'
        elif w < 2:   # true width kept; an outline keeps a hairline flow visible
            extra = f' stroke="{fill}" stroke-width="1"'
        body.append(f'<!-- {run.nums[i]}: {b} -> {a} {n} cues -->')
        body.append(f'<path d="M{x0},{y0:.2f} C{m},{y0:.2f} {m},{y1:.2f} {x1},{y1:.2f} L{x1},{y1 + w:.2f} '
                    f'C{m},{y1 + w:.2f} {m},{y0 + w:.2f} {x0},{y0 + w:.2f} Z" fill="{fill}"{extra}/>')

    for i in range(n_cols):
        for s in run.statuses:
            n = run.after[i][s]
            if not n:
                continue
            t, h = slot[s], n * k_px
            body.append(f'<rect x="{col_x[i]}" y="{t:.2f}" width="{bar_w}" height="{max(h, 1):.2f}" fill="{INK}"/>')
            prev = run.after[i - 1][s] if i else None
            if i == 0 or i == n_cols - 1:
                anchor, x = ("end", col_x[0] - 16) if i == 0 else ("start", col_x[i] + bar_w + 16)
                body.append(f'<text x="{x}" y="{t + h / 2 - 2:.1f}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="{anchor}">{s}</text>')
                body.append(f'<text x="{x}" y="{t + h / 2 + 12:.1f}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="{anchor}">{n}</text>')
            else:
                cx = col_x[i] + bar_w / 2
                if prev != n:
                    body.append(f'<text x="{cx:g}" y="{t - 20:.1f}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{s}</text>')
                body.append(f'<text x="{cx:g}" y="{t - 6:.1f}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{n}</text>')
            re_t = run.retimed[i][s]
            if re_t and i != n_cols - 1 and s in run.consumed(i):
                body.append(f'<text x="{col_x[i] + bar_w + 6}" y="{t + h + 12:.1f}" fill="{MUTED}" font-size="8" font-family="{MONO}">{re_t} re-timed</text>')

    ly = round(bottom + 40)
    acc_in = run.after[1][ACCENT] if n_cols > 1 else 0
    leg, leg_h = legend(ly, width, [
        (sw_rect('fill="rgba(79,93,117,0.12)" stroke="#4f5d75" stroke-width="1"', 16, 8, 0), "status unchanged"),
        (sw_rect('fill="rgba(79,93,117,0.32)" stroke="#4f5d75" stroke-width="1"', 16, 8, 0), "status changed"),
        (sw_rect(f'fill="rgba(235,108,54,0.32)" stroke="{ACC}" stroke-width="1"', 16, 8, 0), f"into {ACCENT}"),
        (sw_rect(f'fill="{INK}"', 6, 12, 0), "node: count after the step"),
    ])
    body += leg
    height = ly + leg_h
    final = run.after[-1]
    desc = (f"Sankey, one column per step: {run.total} cues; band width is the number of cues moving between "
            f"statuses; {acc_in} become {ACCENT} at step {run.nums[1] if n_cols > 1 else ''}, {final[ACCENT]} end as {ACCENT}.")
    return width, height, body, desc


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", help="out/<film>, holding steps/NN_<step>.csv")
    ap.add_argument("--out", help="output directory (default: <run_dir>/diagrams)")
    ap.add_argument("--title", help="film name for the titles (default: the folder name)")
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    run = Run(run_dir / "steps")
    out = Path(args.out) if args.out else run_dir / "diagrams"
    out.mkdir(parents=True, exist_ok=True)
    film = args.title or run_dir.name
    for (b, a), n in [(k, v) for c in run.flows for k, v in c.items()]:
        assert a in run.statuses or a == "original"
    for k in range(len(run.steps)):
        assert sum(run.after[k].values()) == run.total

    note = (f"Counts from <code>{run_dir.as_posix()}/steps</code> ({run.total} cues). "
            f"A cue's status before and after each step is read from consecutive snapshots, "
            f"so every column adds up to {run.total}. \"re-timed\": cues the step moved without changing their status.")
    for name, draw, ttl, eyebrow in [
        ("flowchart", flowchart, f"{film}: how {run.total} cues move through the steps", "Flowchart · align_srt.py"),
        ("sankey", sankey, f"{film}: status flow, one column per step", "Sankey · align_srt.py"),
    ]:
        slug = f"{name}"
        width, height, body, desc = draw(run, ttl, slug)
        (out / f"{name}.html").write_text(page(ttl, desc, slug, eyebrow, width, height, body, [note]), encoding="utf-8")
        (out / f"{name}.svg").write_text(svg_doc(ttl, desc, slug, width, height, body), encoding="utf-8")
    print(f"wrote {out}/flowchart.* and sankey.* ({run.total} cues, {len(run.steps)} steps)")


if __name__ == "__main__":
    main()
