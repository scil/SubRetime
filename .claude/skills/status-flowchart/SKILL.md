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

Rendered example: [`lab/docs/diagrams/cue-flowchart.html`](../../../lab/docs/diagrams/cue-flowchart.html).
Its generator, [`example_gen.py`](example_gen.py), is the starting point for a
new one: copy it and replace the data and geometry sections.

Style, typography, markers, accessibility and the connector rules come from the
`diagram-design` skill (default skin, `references/type-flowchart.md`,
`primitives-core.md`); load it first. This skill replaces only its layout
grammar for this case, and relaxes its 9-node budget.

## Steps

1. **Collect the routing table.** For every step: the statuses it consumes, the
   statuses it produces, and the count on each edge. For align_srt.py, take
   the rules from `align_subtitles()` and the counts from
   `lab/out/<film>/changes.csv` (group by `step, status_before, status_after`)
   and the per-step snapshots `lab/out/<film>/steps/NN_<step>.csv` (count by
   `status`). Done when every step's inputs equal its outputs and the total
   after every step equals the record count.
2. **Order the columns** so each step's consumed and produced statuses are
   contiguous; then every box is one span and every pass-by is straight. Try
   orders until no box has to skip a column; if none exists, split the box
   into two spans, one per contiguous group, sharing the step tag. (align_srt.py order: anchored | verified | rescued |
   outlier | interpolated | none.)
3. **Lay out top to bottom:** start pill (total) → step 01 → chip row → step
   02 → chip row … → final pills. A step that consumes everything spans all
   columns. Give each step box a number tag, a short name and a mono rule line
   (the threshold that decides it). When a step changes records but keeps
   their status, give that chip a second line naming the change
   (`chip(..., note=...)`, e.g. 03's outlier: "time re-set only");
   otherwise it matches the chip above and the step reads as a pass-by.
4. **Draw the flows.** Every edge is vertical within its column. Stroke width
   encodes count in three tiers (≥1000 / 100–999 / <100: 3 / 2 / 1.2 px),
   stated in the legend. Label every pass-by line with its count; a short
   step→chip edge needs no label because the chip carries it. A record that
   jumps columns (e.g. 06's reverted +3) leaves the box's side edge and elbows
   down beside its target column, 16 px clear of it.
5. **Mark emphasis.** Dashed box and edges for an optional step (align_srt.py
   04, `--audio` only). Accent on the one path the diagram is about — at most
   two accent elements, e.g. where the demoted records appear and where they
   end.
6. **Check.** In the generator, assert conservation at every step. Then run,
   with `.venv\Scripts\python.exe`, the diagram-design `scripts/self_check.py`
   (in the installed skill directory) and `verify-geometry.py` (in the plugin's
   root `scripts/`), and open the page in the browser pane, top to bottom.
   Done when both scripts pass, the assertions hold, and nothing overlaps or
   clips on screen.

## Sankey variant

When the reader cares how *much* flows, not just where, draw the same routing
table as a Sankey: [`sankey_gen.py`](sankey_gen.py) generates
[`lab/docs/diagrams/cue-status-sankey.html`](../../../lab/docs/diagrams/cue-status-sankey.html).

- **One column per step**, each holding the status counts after that step.
  Merge a step into its neighbour only when it changes no status (align_srt.py
  07). Merging steps that do change statuses hides their order: 05 acts on the
  99 outliers left after 04, which a merged 04+05 column shows as a split of
  108.
- Unchanged pass-throughs are pale straight bands; status changes are darker;
  the accent stream is the one path the diagram is about.
- Keep columns close (`COL_STEP`, 140 px); the bands carry the eye, not the gaps.
- Tiny flows get a 4 px minimum band; the generator absorbs the extra height
  inside one stream and states the inflated nodes in a note.
- The plugin's `verify-sankey.py` only accepts bars inside its example's
  560 px band; `sankey_gen.py` runs it with the band widened. Its remaining
  findings are the minimum-band nodes, by design.

## Output

Single self-contained HTML under `lab/docs/diagrams/`, generated by a script
in this folder. English text throughout; step and status names as code.
