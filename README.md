# PT-300B — print labels on a Brother PT-P300BT from a Mac

Small Python tool for printing text labels on a Brother **PT-P300BT** (P-touch Cube) over Bluetooth from macOS, without Brother's app. Text is rendered on the Mac with any installed font and sent to the printer as raster data.

## Requirements

- macOS with Bluetooth
- Python 3 (tested with 3.14)
- [`blueutil`](https://github.com/toy/blueutil): `brew install blueutil`
- Pillow, installed in a project virtualenv:

  ```
  python3 -m venv .venv
  .venv/bin/pip install pillow
  ```

## Usage

Turn the printer on (its light blinks slowly when it's ready), then:

```
.venv/bin/python print_label.py LINE [LINE ...] [options]
```

Each positional argument is one line of text.

| Option | Meaning |
|---|---|
| `--length-in N` / `--length-mm N` | Fixed label length. Text shrinks to fit. Without it, the label is as long as the text needs. |
| `--copies N` | Print N labels on one strip, with dotted cut marks between them. |
| `--font PATH` | Any `.ttf`, `.ttc` or `.otf` font file. Default: Helvetica Neue. |
| `--preview` | Only write `preview.png`; don't contact the printer. |
| `--tape-mm N` | Tape width to use for `--preview` (default 9). When printing, the width comes from the printer. |
| `--preview-path PATH` | Where to write the preview image. |

### Examples

```
# One label, as long as the text needs
.venv/bin/python print_label.py "Hello"

# Three 1.5" labels with two lines each
.venv/bin/python print_label.py "you@example.com" "555-123-4567" --length-in 1.5 --copies 3

# Bold font, preview only
.venv/bin/python print_label.py "Spices" --font "/System/Library/Fonts/Supplemental/Arial Bold.ttf" --preview
```

The script prints the font size it chose. On 9 mm tape, anything under about 14 px is hard to read. Use two lines or a longer label instead.

### Printer status

```
python3 status.py
```

Reports tape width, tape type and any errors (no tape, cover open, cutter jam, weak batteries, overheating). It doesn't need the virtualenv.

## Files

- `print_label.py`: renders the text, builds the raster print job and sends it.
- `status.py`: Bluetooth serial connection, re-pairing, and status query and decoding.
- `preview.png`: the most recent rendered label.

## How it works

The printer has a 128-dot print head at 180 dpi and uses Brother's raster command protocol over a Bluetooth serial port (`/dev/cu.PT-P300BT8261`). Each print job:

1. Re-pairs the printer (see below) and opens the serial port.
2. Asks for status to get the tape width and check for errors.
3. Renders the text as a 1-bit image and centres it in the tape's printable area. For example, 9 mm tape has 50 printable dots, starting 39 dots in from the edge of the head.
4. Sends: invalidate → initialize → raster mode → print information → mode settings → TIFF compression → one raster line per image column → print.
5. Reads the printer's replies until it reports "printing completed" or an error.

The printer has no fonts of its own, so all text is drawn on the Mac.

## Known issues

- **Must re-pair every time.** On this Mac, the printer answers only one serial session per pairing. After that the port opens but the printer never replies. So `status.py` unpairs and re-pairs it with `blueutil` before every run, which takes about 15 seconds. As a side effect, the printer may show up in Bluetooth settings under its address instead of its name.
- **Label length may be about 5% long.** A 1.5" (38 mm) label measured about 40 mm. This hasn't been calibrated yet. Print one `--length-mm 100` label and measure it to get the correction.
- **No auto-cutter.** Cut at the dotted marks. There is some blank tape before the first label.
- The printer address (`98-6e-e8-48-10-d6`) and port name are hard-coded in `status.py`.
