---
name: label-maker
description: Print labels on a Brother PT-P300BT (P-touch Cube) Bluetooth label maker. Use when the user says "label maker", asks to print/make a label or labels, or asks about the label printer's tape or status.
---

# Label maker (Brother PT-P300BT)

Code lives in `/path/to/PT-300B`. Always run with the project venv:

```
cd /path/to/PT-300B && .venv/bin/python print_label.py LINE [LINE ...] [options]
```

- Each positional argument is **one line of text** (9 mm tape fits 2 lines comfortably, 3 at most).
- `--length-in 1.5` / `--length-mm 40` — fixed label length; text auto-shrinks to fit. Omit for "as long as the text needs".
- `--copies N` — N labels on one strip, separated by dotted cut marks (one print job).
- `--font PATH` — any font on the Mac (default Helvetica Neue). Bold option: `/System/Library/Fonts/Supplemental/Arial Bold.ttf`.
- `--preview` — render `preview.png` only, no printer needed (`--tape-mm` sets width, default 9).

## Workflow

1. **Collect details from the request.** Text, number of labels, length, font. Ask the user (one AskUserQuestion, only for what is missing or ambiguous) — don't ask about things with sensible defaults (1 copy, length fits text, default font).
   - A `//`, `|` or `/` between items usually means a line break — ask if unsure, or preview both.
   - Different texts per label → run one print per distinct text (each re-pairs, ~15 s).
2. **Preview first.** Run with `--preview`, then Read `/path/to/PT-300B/preview.png` to check it. Report the font size it chose; under ~14px on 9 mm tape is hard to read — suggest two lines or a longer label.
3. **Confirm, then print.** Show the preview summary and get a yes before printing (tape is consumable). Skip the confirmation if the user said to just print.
4. **Print** with the same arguments minus `--preview`. Success = `printer: printing completed | errors: ['none']`.

## Things to know

- The printer must be **on** (button on top; the light blinks slowly when ready). It auto-powers off after a while.
- Each run **unpairs and re-pairs** it via `blueutil` (~15 s): on this Mac the printer answers only one serial session per pairing. This is expected; don't "fix" it.
- If it fails with "did not appear after re-pairing" → printer is off or asleep; ask the user to turn it on.
- No auto-cutter: the user cuts at the dotted marks. There is some blank leader tape before the first label.
- `python3 status.py` (no venv needed) reports tape width, type and errors.
- The printer has no fonts of its own; all text is rendered on the Mac and sent as raster.
