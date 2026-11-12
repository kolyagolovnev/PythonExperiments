# Match 3 — terminal edition

A colourful Match-3 puzzle game that runs entirely in your terminal. Pure Python
standard library: no packages, no build step, no network access.

```
                       MATCH 3 ◆ terminal edition   SCORE                235
                                                    BEST                 235
                       ┌────────────────────────┐   MOVES                 29
                       │ ■  ▲  ♥  ●  ■  ▲  ★  ● │   TARGET             1,800
                       │ ★  ◆  ♥  ▲  ♥  ♥  ★  ★ │   ██░░░░░░░░░░░░░░░░░░░░░░
                       │ ◆  ★  ■  ●  ◆  ★  ◆  ♥ │
                       │ ◆  ★  ▲  ●  ■  ●  ■  ◆ │   ────────────────────────
                       │ ♥  ♥  ★  ▲  ■  ▲  ▲  ◆ │   ↑↓←→ / WASD         move
                       │ ◆  ◆  ▲  ▲  ★  ●  ■  ▲ │   SPACE               swap
                       │ ◆  ♥  ◆  ★  ▲  ●  ▲  ★ │   H                   hint
                       │ ▲  ◆  ▲  ●  ▲  ▲  ♥  ■ │   U                   undo
                       └────────────────────────┘   R / Q     restart / quit
                       Excellent! Cascade x2! +235 points
```

## Run it

Requires Python 3.10+ and a terminal with `curses` (Linux and macOS ship with it;
Windows needs the `windows-curses` package).

```sh
python3 match3.py
# or
./match3.py
```

No installation or virtual environment is needed.

## How to play

Swap two neighbouring gems so that three or more of the same kind line up
horizontally or vertically. Matched gems disappear, new gems fall in, and any
new matches cascade for bonus points.

You have **30 moves** to reach the score target (default: 1,800 points).
Invalid swaps do not cost a move.

| Key | Action |
| --- | --- |
| Arrow keys / `WASD` | Move the cursor |
| `Space` / `Enter` | Select a gem, then swap with a neighbour |
| `H` | Highlight a legal move |
| `U` | Undo the last successful move |
| `R` | Start a new board |
| `Esc` | Clear the selection |
| `Q` | Quit |
| Mouse | Click a gem to select/swap |

Press `H` and then `Space` if you are stuck — the hint sets up the swap for you.

## Scoring

- Every cleared gem is worth **10 points**.
- A run longer than three gems adds **25 points per extra gem**.
- Every cascade doubles the value of the next clear: cascade 1 is ×1, cascade 2 is
  ×2, cascade 3 is ×3, and so on.
- The best score for each board/mode combination is saved automatically to
  `$XDG_DATA_HOME/match3-terminal/best.json` (usually
  `~/.local/share/match3-terminal/best.json`).

The board reshuffles itself automatically if no legal moves remain.

## Options

```text
python3 match3.py --moves 20 --target 1500
python3 match3.py --zen                 # endless play, no move limit
python3 match3.py --rows 10 --cols 10 --kinds 5
python3 match3.py --ascii               # terminal-safe ASCII glyphs
python3 match3.py --seed 42             # reproducible board
python3 match3.py --no-mouse --no-save
```

Run `python3 match3.py --help` for the full list.

## Tests

The game engine is independent of `curses` and is covered by the standard
library test suite:

```sh
python3 -m unittest discover -v
# or
make test
```

## Layout

| File | Purpose |
| --- | --- |
| `match3.py` | Curses front end, layout, input, colours, persistence, CLI |
| `match3_logic.py` | Pure board engine: matches, cascades, scoring, hints, shuffling |
| `tests/test_match3_logic.py` | Engine unit tests |
| `Makefile` | `make run` / `make test` shortcuts |

### Terminal notes

- The default Unicode gem glyphs look best in a UTF-8 terminal. If wide or
  ambiguous-width characters break the grid, launch with `--ascii`.
- The game adapts to narrow windows by hiding the side panel. If the window is
  too small it asks you to resize.
- Mouse support may conflict with terminal text selection; hold `Shift` while
  selecting text, or pass `--no-mouse`.
