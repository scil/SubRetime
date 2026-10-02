---
name: status-flowchart
description: Draw a status flowchart — records flowing through a fixed sequence of steps, where each step only processes some statuses and the rest pass by — as columns of statuses with step boxes spanning the columns they consume, no decision diamonds, or as a one-column-per-step Sankey. Use when showing how data splits and flows through a pipeline (e.g. align_srt.py's cue statuses), or when a flowchart's diamonds hide the flow.
---

# Status flowchart

A flowchart for **routing by status**: every record carries a status, steps run
in a fixed order, and each step consumes only certain statuses. The reader
should see where the data goes at a glance, so the routing is drawn as geometry,
not as decisions:

- **Columns are statuses.** Each status owns one vertical lane for the whole
  diagram.
- **Step boxes span the columns they consume.** The box width is the routing
  rule; no diamonds, no YES/NO edges.
- **Status chips are the data.** A chip (status + count) sits under a step for
  every status it produces.
- **Pass-by is a straight line.** A status the step does not consume runs
  straight down its column past the box, labelled with its count.

For align_srt.py this is already built: [`lab/flow_diagrams.py`](../../../lab/flow_diagrams.py)
reads one run's snapshots and writes the flowchart and the Sankey (HTML and
SVG); the DVC stages `diagrams_0@<film>` and `diagrams_A@<film>` run it after
every `align_0` / `align_A`. Change the
drawing there. Rendered example:
[`lab/docs/diagrams/dog-man-2025/`](../../../lab/docs/diagrams/dog-man-2025/).
For another pipeline, start from a copy of it.

Style, typography, markers, accessibility and the connector rules come from the
`diagram-design` skill (default skin, `references/type-flowchart.md`,
`primitives-core.md`); load it first. This skill replaces only its layout
grammar for this case, and relaxes its 9-node budget.

## Steps

1. **Read the routing table from the run, not by hand.** Counts come from
   per-step snapshots: a record's status before and after a step is its row
   in two consecutive snapshot files, so every count conserves by
   construction. Which statuses a step consumes is a rule of the code
   (`CONSUMES` in `flow_diagrams.py`), not data: a step can consume a status
   and change nothing. Done when the generator's conservation asserts hold.
2. **Order the columns** so each step's consumed and produced statuses are
   contiguous; then every box is one span and every pass-by is straight
   (`ORDER`; align_srt.py: anchored | verified | rescued | outlier |
   interpolated | none). The generator stops if a pass-by line would run
   behind a box; reorder until it does not.
3. **Lay out top to bottom:** start pill (total) → step 01 → chip row → step
   02 → chip row … → final pills. A step that consumes everything spans all
   columns. Give each step box a number tag, a short name and a mono rule line
   (the threshold that decides it). When a step changes records but keeps
   their status, the chip gets a second line ("108 re-timed"); otherwise it
   matches the chip above and the step reads as a pass-by.
4. **Draw the flows.** Every edge is vertical within its column. Stroke width
   encodes count in three tiers (≥1000 / 100–999 / <100: 3 / 2 / 1.2 px),
   stated in the legend. Label every pass-by line with its count; a short
   step→chip edge needs no label because the chip carries it. A record that
   jumps to a column the step does not span (e.g. 06's reverted +3) leaves the
   box's side edge and elbows down beside its target column, 16 px clear of it.
5. **Mark emphasis.** Dashed box and edges for an optional step (align_srt.py
   04, `--audio` only). Accent on the one path the diagram is about (`ACCENT`):
   where that status first appears and where it ends.
6. **Check.** Run, with `.venv\Scripts\python.exe`, the diagram-design
   `scripts/self_check.py` (in the installed skill directory) and
   `verify-geometry.py` (in the plugin's root `scripts/`) on the HTML, parse
   the SVG as XML (escape `&` and `<` in text), and open the page in the
   browser pane, top to bottom. Try every film's run: a run without a status
   (e.g. no `verified`) narrows the flowchart. Done when both scripts pass, the
   SVG parses, and nothing overlaps or clips on screen.

## Sankey variant

When the reader cares how *much* flows, not just where, draw the same routing
table as a Sankey.

- **One column per step**, each holding the status counts after that step.
  Merging steps hides their order: 05 acts on the 99 outliers left after 04,
  which a merged 04+05 column shows as a split of 108.
- Each status keeps one slot at the same height in every column, so unchanged
  bands run straight; status changes are darker; the accent stream is the one
  path the diagram is about.
- Keep columns close (140 px); the bands carry the eye, not the gaps.
- Bands keep their true width, so every column conserves exactly; a band
  under 2 px gets a 1 px outline so a flow of 3 records stays visible.

## Output

HTML (page with title and note) and a standalone SVG of the same drawing; the
SVG is what README.md embeds. English text throughout; step and status names
as code.
