#!/usr/bin/env python3
"""A polished Match-3 game for the terminal, built with the Python stdlib."""

from __future__ import annotations

import argparse
import curses
import json
import locale
import os
import random
import sys
from pathlib import Path
from typing import Sequence

from match3_logic import Board, Coord, Snapshot, Step

CELL_W = 3
TITLE = "MATCH 3"

UNICODE_GEMS = ("●", "◆", "▲", "★", "■", "♥")
ASCII_GEMS = ("o", "D", "A", "*", "s", "H")
GEM_COLORS = (
    curses.COLOR_RED,
    curses.COLOR_GREEN,
    curses.COLOR_YELLOW,
    curses.COLOR_BLUE,
    curses.COLOR_MAGENTA,
    curses.COLOR_CYAN,
)

# Color pair numbers. Pairs 1..8 belong to gem kinds.
PAIR_TITLE = 11
PAIR_SCORE = 12
PAIR_MUTED = 13
PAIR_GOOD = 14
PAIR_BAD = 15
PAIR_TARGET = 16
PAIR_WHITE = 17

BEST_FILE = Path(
    os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
) / "match3-terminal" / "best.json"


def _supports_unicode() -> bool:
    encoding = (sys.stdout.encoding or locale.getpreferredencoding(False) or "").lower()
    return "utf" in encoding


class Game:
    """Curses front end and game-run state."""

    def __init__(
        self,
        *,
        rows: int = 8,
        cols: int = 8,
        kinds: int = 6,
        moves: int | None = 30,
        target: int | None = None,
        seed: int | None = None,
        unicode: bool = True,
        mouse: bool = True,
        save_best: bool = True,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.kinds = kinds
        self.starting_moves = moves
        self.target = target
        self.seed = seed
        self.unicode = unicode
        self.mouse_enabled = mouse
        self.save_best = save_best

        self.gems = UNICODE_GEMS if unicode else ASCII_GEMS
        if kinds > len(self.gems):
            raise ValueError(f"the UI supports at most {len(self.gems)} gem kinds")

        self.rng = random.Random(seed)
        self.best_key = f"{rows}x{cols}x{kinds}:{'zen' if moves is None else moves}"
        self.best = self._load_best() if save_best else 0

        self.board: Board
        self.moves_left: int | None
        self.cursor: Coord
        self.selected: Coord | None
        self.undo_state: tuple[Snapshot, int, int | None] | None
        self.game_over = False
        self.reached_target = False
        self.message = ""
        self.message_kind = "info"
        self._anim: Step | None = None
        self._geo: dict[str, int | bool] | None = None
        self._new_game(reset_rng=True)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_best(self) -> int:
        try:
            raw = json.loads(BEST_FILE.read_text(encoding="utf-8"))
            scores = raw.get("scores", raw)
            value = scores.get(self.best_key, 0)
            return int(value) if isinstance(value, (int, float)) else 0
        except (OSError, ValueError, TypeError, AttributeError):
            return 0

    def _save_best(self) -> None:
        if not self.save_best:
            return
        try:
            try:
                raw = json.loads(BEST_FILE.read_text(encoding="utf-8"))
                scores = raw.get("scores", raw) if isinstance(raw, dict) else {}
                if not isinstance(scores, dict):
                    scores = {}
            except (OSError, ValueError):
                scores = {}
            scores[self.best_key] = self.best
            BEST_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = BEST_FILE.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"scores": scores}, indent=2), encoding="utf-8"
            )
            temporary.replace(BEST_FILE)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------
    def _new_game(self, *, reset_rng: bool = False) -> None:
        if reset_rng and self.seed is not None:
            self.rng = random.Random(self.seed)
        self.board = Board(self.rows, self.cols, self.kinds, rng=self.rng)
        self.moves_left = self.starting_moves
        self.cursor = (self.rows // 2, self.cols // 2)
        self.selected = None
        self.undo_state = None
        self.game_over = False
        self.reached_target = bool(
            self.target is not None and self.board.score >= self.target
        )
        self._anim = None
        self.message = (
            "Arrows move · space swaps · h hint · u undo"
            if self.starting_moves is not None
            else "Zen mode — no move limit. Space swaps."
        )
        self.message_kind = "info"

    # ------------------------------------------------------------------
    # Curses setup and main loop
    # ------------------------------------------------------------------
    def run(self, screen: "curses.window") -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        screen.keypad(True)
        screen.timeout(-1)
        self._init_colors()
        if self.mouse_enabled:
            try:
                curses.mousemask(
                    curses.BUTTON1_CLICKED
                    | curses.BUTTON1_PRESSED
                    | curses.BUTTON1_RELEASED
                )
                curses.mouseinterval(120)
            except (curses.error, AttributeError):
                self.mouse_enabled = False

        try:
            while True:
                self.draw(screen)
                try:
                    key = screen.getch()
                except KeyboardInterrupt:
                    return
                if key in (ord("q"), ord("Q")):
                    return
                if key == curses.KEY_RESIZE:
                    continue
                if self.game_over:
                    self._handle_game_over_key(screen, key)
                else:
                    self._handle_key(screen, key)
        finally:
            self._save_best()
            try:
                curses.curs_set(1)
            except curses.error:
                pass

    def _init_colors(self) -> None:
        if not curses.has_colors():
            return
        try:
            curses.start_color()
        except curses.error:
            return
        default_bg = -1
        try:
            curses.use_default_colors()
        except curses.error:
            default_bg = curses.COLOR_BLACK

        pairs: list[tuple[int, int]] = []
        for index, color in enumerate(GEM_COLORS, start=1):
            pairs.append((index, color))
        neutral = -1 if default_bg == -1 else curses.COLOR_WHITE
        pairs.extend(
            [
                (PAIR_TITLE, curses.COLOR_CYAN),
                (PAIR_SCORE, curses.COLOR_YELLOW),
                (PAIR_MUTED, neutral),
                (PAIR_GOOD, curses.COLOR_GREEN),
                (PAIR_BAD, curses.COLOR_RED),
                (PAIR_TARGET, curses.COLOR_MAGENTA),
                (PAIR_WHITE, neutral),
            ]
        )
        for pair, foreground in pairs:
            try:
                curses.init_pair(pair, foreground, default_bg)
            except curses.error:
                pass

    def _cp(self, pair: int) -> int:
        return curses.color_pair(pair) if curses.has_colors() else 0

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------
    def _handle_key(self, screen: "curses.window", key: int) -> None:
        movements = {
            curses.KEY_UP: (-1, 0),
            curses.KEY_DOWN: (1, 0),
            curses.KEY_LEFT: (0, -1),
            curses.KEY_RIGHT: (0, 1),
            ord("w"): (-1, 0),
            ord("s"): (1, 0),
            ord("a"): (0, -1),
            ord("d"): (0, 1),
            ord("W"): (-1, 0),
            ord("S"): (1, 0),
            ord("A"): (0, -1),
            ord("D"): (0, 1),
        }
        if key in movements:
            dr, dc = movements[key]
            row = min(max(self.cursor[0] + dr, 0), self.rows - 1)
            col = min(max(self.cursor[1] + dc, 0), self.cols - 1)
            if (row, col) != self.cursor:
                self.cursor = (row, col)
                self.message = ""
            return

        if key in (ord(" "), ord("\n"), ord("\r"), curses.KEY_ENTER):
            self._select(screen, self.cursor)
            return

        if key == 27:  # Escape
            self.selected = None
            self.message = ""
            return

        if key in (ord("h"), ord("H")):
            hint = self.board.find_hint()
            if hint is None:
                self.message = "No moves available — press r for a new board."
                self.message_kind = "bad"
            else:
                first, second = hint
                self.selected = first
                self.cursor = second
                self.message = "Hint ready — press space to swap."
                self.message_kind = "info"
            return

        if key in (ord("u"), ord("U")):
            self._undo()
            return

        if key in (ord("r"), ord("R")):
            self._new_game(reset_rng=True)
            self.message = "New board!"
            self.message_kind = "info"
            return

        if key == curses.KEY_MOUSE and self.mouse_enabled and self._geo:
            try:
                _, mx, my, _, state = curses.getmouse()
            except curses.error:
                return
            if state & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                coord = self._cell_at(mx, my)
                if coord is not None:
                    self._select(screen, coord)

    def _handle_game_over_key(self, screen: "curses.window", key: int) -> None:
        if key in (ord("r"), ord("R")):
            self._new_game(reset_rng=True)
            self.message = "New board!"
            self.message_kind = "info"
        elif key in (ord("u"), ord("U")):
            self._undo()

    def _select(self, screen: "curses.window", coord: Coord) -> None:
        if not self.board.inside(coord):
            return
        self.cursor = coord
        if self.selected is None:
            self.selected = coord
            self.message = (
                f"Selected row {coord[0] + 1}, col {coord[1] + 1} — "
                "pick a neighbour."
            )
            self.message_kind = "info"
            return
        if self.selected == coord:
            self.selected = None
            self.message = ""
            return
        if not self.board.are_adjacent(self.selected, coord):
            self.selected = coord
            self.message = "Selection moved — pick a neighbour."
            self.message_kind = "info"
            return

        self._perform_swap(screen, self.selected, coord)

    def _perform_swap(self, screen: "curses.window", a: Coord, b: Coord) -> None:
        self.selected = None
        if not self.board.would_match(a, b):
            self._play_bad_swap(screen, a, b)
            return

        snapshot = self.board.snapshot()
        score_before = self.board.score
        moves_before = self.moves_left
        result = self.board.try_swap(a, b)
        if not result.swapped:  # Defensive: should be impossible after would_match.
            return

        self.undo_state = (snapshot, score_before, moves_before)
        if self.moves_left is not None:
            self.moves_left -= 1

        self._play_animation(screen, result.steps)

        if self.board.score > self.best:
            self.best = self.board.score
            self._save_best()

        if result.cascades > 1:
            message = f"Cascade x{result.cascades}! +{result.points} points"
        else:
            message = f"+{result.points} points"
        if result.points >= 200:
            message = "Excellent! " + message
        self.message = message
        self.message_kind = "good"

        if self.target is not None and not self.reached_target:
            if self.board.score >= self.target:
                self.reached_target = True
                self.message += "  Target reached!"

        if not self.board.has_valid_move():
            self.board.shuffle()
            self.message += "  No moves left — board shuffled."
            self.message_kind = "info"

        if self.moves_left is not None and self.moves_left <= 0:
            self.game_over = True
            if self.target is not None and self.board.score < self.target:
                short = self.target - self.board.score
                self.message = f"Out of moves — {short} points short of the target."
                self.message_kind = "bad"
            else:
                self.message = "Out of moves — great score!"
                self.message_kind = "good"
            self._save_best()

    def _play_bad_swap(self, screen: "curses.window", a: Coord, b: Coord) -> None:
        """Nudge the two gems together and back so the rejection is visible."""

        self.selected = None
        self.board.swap_cells(a, b)
        self.draw(screen)
        curses.napms(85)
        self.board.swap_cells(a, b)
        self.draw(screen)
        self.message = "That swap makes no match."
        self.message_kind = "bad"

    def _play_animation(self, screen: "curses.window", steps: Sequence[Step]) -> None:
        for step in steps:
            self._anim = step
            self.draw(screen)
            curses.napms(105 if step.kind == "clear" else 65)
        self._anim = None

    def _undo(self) -> None:
        if self.undo_state is None:
            self.message = "Nothing to undo."
            self.message_kind = "info"
            return
        snapshot, score, moves = self.undo_state
        self.board.restore(snapshot, score)
        self.moves_left = moves
        self.undo_state = None
        self.selected = None
        self.game_over = False
        self.reached_target = bool(
            self.target is not None and self.board.score >= self.target
        )
        self.message = "Last move undone."
        self.message_kind = "info"

    # ------------------------------------------------------------------
    # Layout and drawing
    # ------------------------------------------------------------------
    def _layout(self, height: int, width: int) -> dict[str, int | bool]:
        board_w = self.cols * CELL_W + 2
        board_h = self.rows + 2
        panel_wanted = 24
        gap = 3
        total_w = board_w + gap + panel_wanted
        has_panel = width >= total_w + 2
        if has_panel:
            left = max(2, (width - total_w) // 2)
            panel_left = left + board_w + gap
            panel_w = panel_wanted
        else:
            left = max(1, (width - board_w) // 2)
            panel_left = 0
            panel_w = 0
        return {
            "height": height,
            "width": width,
            "board_left": left,
            "board_top": 3,
            "board_w": board_w,
            "board_h": board_h,
            "panel_left": panel_left,
            "panel_w": panel_w,
            "has_panel": has_panel,
        }

    def draw(self, screen: "curses.window") -> None:
        height, width = screen.getmaxyx()
        try:
            screen.erase()
        except curses.error:
            return

        min_width = max(34, self.cols * CELL_W + 4)
        min_height = max(14, self.rows + 8)
        if width < min_width or height < min_height:
            self._geo = None
            self._draw_too_small(screen, height, width)
            self._refresh(screen)
            return

        layout = self._layout(height, width)
        self._geo = layout
        self._draw_title(screen, layout)
        self._draw_board(screen, layout)
        # In compact mode the game-over modal can extend below the board, so the
        # status/help lines would show through around it. Hide them instead.
        if not self.game_over or layout["has_panel"]:
            self._draw_status(screen, layout)
        if layout["has_panel"]:
            self._draw_panel(screen, layout)
        else:
            self._draw_compact_stats(screen, layout)
        if self.game_over:
            self._draw_game_over(screen, layout)
        self._refresh(screen)

    def _refresh(self, screen: "curses.window") -> None:
        try:
            screen.refresh()
        except curses.error:
            pass

    def _add(
        self,
        screen: "curses.window",
        y: int,
        x: int,
        text: str,
        attr: int = 0,
    ) -> None:
        if y < 0 or x < 0:
            return
        height, width = screen.getmaxyx()
        if y >= height or x >= width or not text:
            return
        if not self.unicode:
            for unicode_text, ascii_text in (
                ("↑↓←→", "ARROWS"),
                ("∞", "inf"),
                ("·", "-"),
                ("—", "-"),
                ("✓", "OK"),
                ("◆", "*"),
                ("█", "#"),
                ("░", "-"),
            ):
                text = text.replace(unicode_text, ascii_text)
            text = text.encode("ascii", "replace").decode("ascii")
        try:
            screen.addnstr(y, x, text, max(0, width - x), attr)
        except curses.error:
            pass

    def _draw_too_small(
        self, screen: "curses.window", height: int, width: int
    ) -> None:
        need_w = max(34, self.cols * CELL_W + 4)
        need_h = max(14, self.rows + 8)
        lines = [
            ("Terminal is too small", self._cp(PAIR_BAD) | curses.A_BOLD),
            (f"Need at least {need_w} x {need_h}, have {width} x {height}", self._cp(PAIR_MUTED)),
            ("Resize the window or press q to quit.", self._cp(PAIR_MUTED)),
        ]
        top = max(0, (height - len(lines)) // 2)
        for index, (text, attr) in enumerate(lines):
            x = max(0, (width - len(text)) // 2)
            self._add(screen, top + index, x, text, attr)

    def _draw_title(self, screen: "curses.window", layout: dict[str, int | bool]) -> None:
        left = int(layout["board_left"])
        self._add(
            screen,
            1,
            left,
            TITLE,
            self._cp(PAIR_TITLE) | curses.A_BOLD,
        )
        tagline = "◆ terminal edition"
        tag_x = left + len(TITLE) + 1
        limit = (
            int(layout["panel_left"]) - 1
            if layout["has_panel"]
            else int(layout["width"]) - 1
        )
        if self.unicode and tag_x + len(tagline) <= limit:
            self._add(
                screen,
                1,
                tag_x,
                tagline,
                self._cp(PAIR_MUTED) | curses.A_DIM,
            )

    def _frame_chars(self) -> tuple[str, str, str, str, str, str]:
        if self.unicode:
            return "┌", "┐", "└", "┘", "─", "│"
        return "+", "+", "+", "+", "-", "|"

    def _draw_board(self, screen: "curses.window", layout: dict[str, int | bool]) -> None:
        left = int(layout["board_left"])
        top = int(layout["board_top"])
        cols = self.cols
        rows = self.rows
        tl, tr, bl, br, horiz, vert = self._frame_chars()
        inner_w = cols * CELL_W
        frame_attr = self._cp(PAIR_MUTED) | curses.A_DIM

        self._add(screen, top, left, tl + horiz * inner_w + tr, frame_attr)
        for r in range(rows):
            self._add(screen, top + 1 + r, left, vert, frame_attr)
            self._add(screen, top + 1 + r, left + inner_w + 1, vert, frame_attr)

        bottom_y = top + rows + 1
        self._add(screen, bottom_y, left, bl + horiz * inner_w + br, frame_attr)

        grid = self._anim.grid if self._anim is not None else self.board.snapshot()
        anim_cleared = (
            self._anim.cleared if self._anim is not None and self._anim.kind == "clear" else frozenset()
        )
        for r in range(rows):
            for c in range(cols):
                kind = grid[r][c]
                x = left + 1 + c * CELL_W
                y = top + 1 + r
                if kind is None:
                    if (r, c) in anim_cleared:
                        self._add(
                            screen,
                            y,
                            x,
                            " · ",
                            self._cp(PAIR_MUTED) | curses.A_DIM,
                        )
                    continue
                text = f" {self.gems[kind]} "
                attr = self._gem_attr(kind)
                if (r, c) == self.cursor:
                    attr |= curses.A_REVERSE
                if (r, c) == self.selected:
                    attr |= curses.A_UNDERLINE | curses.A_BOLD
                self._add(screen, y, x, text, attr)

        if self._anim is not None and self._anim.kind == "clear":
            label = f" match x{self._anim.cascade} "
            color = PAIR_TARGET
            if self._anim.points:
                label = f" match x{self._anim.cascade}  +{self._anim.points} "
            self._add(
                screen,
                bottom_y,
                left + max(1, (inner_w - len(label)) // 2),
                label,
                self._cp(color) | curses.A_BOLD,
            )

    def _gem_attr(self, kind: int) -> int:
        pair = kind + 1 if kind < len(GEM_COLORS) else PAIR_WHITE
        return self._cp(pair) | curses.A_BOLD

    def _draw_status(self, screen: "curses.window", layout: dict[str, int | bool]) -> None:
        left = int(layout["board_left"])
        width = int(layout["width"])
        board_bottom = int(layout["board_top"]) + self.rows + 1
        # The side panel's last line is row 12; keep the message below it.
        y = max(board_bottom + 1, 13) if layout["has_panel"] else board_bottom + 1
        if not self.message:
            if self.selected is not None:
                text = "Space swaps with a neighbour · Esc / space again deselects"
            else:
                text = "Space selects · h hint · u undo · r restart · q quit"
            attr = self._cp(PAIR_MUTED) | curses.A_DIM
        else:
            text = self.message
            colors = {"good": PAIR_GOOD, "bad": PAIR_BAD, "info": PAIR_MUTED}
            attr = self._cp(colors.get(self.message_kind, PAIR_MUTED))
            if self.message_kind == "good":
                attr |= curses.A_BOLD
        x = left if layout["has_panel"] else 1
        self._add(screen, y, x, text[: max(0, width - x - 1)], attr)

        if not layout["has_panel"]:
            help_lines = ["arrows/WASD move · space swap"]
            if width >= 40:
                help_lines.append("h hint · u undo · r restart · q quit")
            else:
                help_lines.append("h hint · u undo · q quit")
            for offset, help_text in enumerate(help_lines, start=1):
                help_x = max(0, (width - len(help_text)) // 2)
                self._add(
                    screen,
                    y + offset,
                    help_x,
                    help_text,
                    self._cp(PAIR_MUTED) | curses.A_DIM,
                )

    def _panel_stat(
        self,
        screen: "curses.window",
        y: int,
        left: int,
        width: int,
        label: str,
        value: str,
        value_attr: int,
    ) -> None:
        self._add(screen, y, left, label, self._cp(PAIR_MUTED) | curses.A_DIM)
        x = left + max(0, width - len(value))
        self._add(screen, y, x, value, value_attr)

    def _draw_panel(self, screen: "curses.window", layout: dict[str, int | bool]) -> None:
        left = int(layout["panel_left"])
        width = int(layout["panel_w"])
        y = 1

        self._panel_stat(
            screen,
            y,
            left,
            width,
            "SCORE",
            f"{self.board.score:,}",
            self._cp(PAIR_SCORE) | curses.A_BOLD,
        )
        self._panel_stat(
            screen,
            y + 1,
            left,
            width,
            "BEST",
            f"{self.best:,}",
            self._cp(PAIR_WHITE),
        )
        if self.moves_left is None:
            moves = "∞" if self.unicode else "inf"
        else:
            moves = str(self.moves_left)
        self._panel_stat(
            screen,
            y + 2,
            left,
            width,
            "MOVES",
            moves,
            self._cp(PAIR_WHITE) | curses.A_BOLD,
        )
        y += 3
        if self.target is not None:
            reached = " ✓" if self.reached_target and self.unicode else (
                " OK" if self.reached_target else ""
            )
            self._panel_stat(
                screen,
                y,
                left,
                width,
                "TARGET",
                f"{self.target:,}{reached}",
                self._cp(PAIR_TARGET),
            )
            bar_y = y + 1
            bar_width = max(1, width)
            filled = min(
                bar_width,
                int(round(bar_width * self.board.score / max(1, self.target))),
            )
            if self.unicode:
                bar = "█" * filled + "░" * (bar_width - filled)
            else:
                bar = "#" * filled + "-" * (bar_width - filled)
            self._add(
                screen, bar_y, left, bar, self._cp(PAIR_TARGET) | curses.A_BOLD
            )
            y = bar_y + 1

        rule_y = y + 1
        self._add(
            screen,
            rule_y,
            left,
            "─" * width if self.unicode else "-" * width,
            self._cp(PAIR_MUTED) | curses.A_DIM,
        )

        controls = [
            ("↑↓←→ / WASD" if self.unicode else "ARROWS / WASD", "move"),
            ("SPACE", "swap"),
            ("H", "hint"),
            ("U", "undo"),
            ("R / Q", "restart / quit"),
        ]
        for index, (key, description) in enumerate(controls):
            row = rule_y + 1 + index
            self._add(
                screen, row, left, key, self._cp(PAIR_WHITE) | curses.A_BOLD
            )
            self._add(
                screen,
                row,
                left + max(0, width - len(description)),
                description,
                self._cp(PAIR_MUTED) | curses.A_DIM,
            )

        if self.moves_left is None:
            self._add(
                screen,
                rule_y + len(controls) + 1,
                left,
                "ZEN MODE",
                self._cp(PAIR_TITLE) | curses.A_BOLD,
            )

    def _draw_compact_stats(
        self, screen: "curses.window", layout: dict[str, int | bool]
    ) -> None:
        if self.moves_left is None:
            moves = "∞" if self.unicode else "inf"
        else:
            moves = str(self.moves_left)
        text = f"Score {self.board.score:,}   Best {self.best:,}   Moves {moves}"
        width = int(layout["width"])
        x = max(1, (width - len(text)) // 2)
        self._add(
            screen,
            2,
            x,
            text,
            self._cp(PAIR_MUTED) | curses.A_DIM,
        )

    def _draw_game_over(
        self, screen: "curses.window", layout: dict[str, int | bool]
    ) -> None:
        board_left = int(layout["board_left"])
        board_top = int(layout["board_top"])
        board_w = int(layout["board_w"])
        inner_w = board_w - 2
        board_h = int(layout["board_h"])

        score_attr = self._cp(PAIR_SCORE) | curses.A_BOLD
        if self.target is not None:
            if self.reached_target:
                target_line = f"Target {self.target:,} reached!"
                short_target = "Target hit"
                target_attr = self._cp(PAIR_GOOD) | curses.A_BOLD
            else:
                target_line = f"Target {self.target:,} missed"
                short_target = "Target miss"
                target_attr = self._cp(PAIR_MUTED)
        else:
            target_line = ""
            short_target = ""
            target_attr = 0

        full_lines: list[tuple[str, int]] = [
            ("GAME OVER", self._cp(PAIR_BAD) | curses.A_BOLD),
            ("", 0),
            (f"Score  {self.board.score:,}", score_attr),
            (f"Best   {self.best:,}", self._cp(PAIR_WHITE)),
            (target_line, target_attr),
            ("r restart   q quit", self._cp(PAIR_WHITE)),
        ]
        if max(len(text) for text, _ in full_lines) <= inner_w:
            lines = full_lines
        else:
            # Narrow boards get a tighter modal so nothing spills outside.
            lines = [
                ("GAME OVER", self._cp(PAIR_BAD) | curses.A_BOLD),
                (f"Score {self.board.score:,}", score_attr),
                (f"Best {self.best:,}", self._cp(PAIR_WHITE)),
                (short_target, target_attr),
                ("", 0),
                ("r restart", self._cp(PAIR_WHITE)),
                ("q quit", self._cp(PAIR_WHITE)),
            ]

        height = max(8, len(lines) + 2)
        if board_h >= height:
            height = min(board_h, 10)
        top = board_top + max(0, (board_h - height) // 2)
        left = board_left

        if self.unicode:
            tl, tr, bl, br, horiz, vert = "╔", "╗", "╚", "╝", "═", "║"
        else:
            tl, tr, bl, br, horiz, vert = "+", "+", "+", "+", "=", "|"

        border_attr = self._cp(PAIR_BAD) | curses.A_BOLD
        self._add(
            screen,
            top,
            left,
            tl + horiz * inner_w + tr,
            border_attr,
        )
        for row in range(top + 1, top + height - 1):
            # Blank the interior so board gems do not show through the modal.
            self._add(screen, row, left + 1, " " * inner_w)
            self._add(screen, row, left, vert, border_attr)
            self._add(screen, row, left + inner_w + 1, vert, border_attr)
        self._add(
            screen,
            top + height - 1,
            left,
            bl + horiz * inner_w + br,
            border_attr,
        )

        content_start = top + 1 + max(0, (height - 2 - len(lines)) // 2)
        for index, (text, attr) in enumerate(lines):
            text = text[:inner_w]
            y = content_start + index
            x = left + 1 + max(0, (inner_w - len(text)) // 2)
            self._add(screen, y, x, text, attr)

    # ------------------------------------------------------------------
    # Mouse helpers
    # ------------------------------------------------------------------
    def _cell_at(self, x: int, y: int) -> Coord | None:
        geo = self._geo
        if not geo:
            return None
        left = int(geo["board_left"])
        top = int(geo["board_top"])
        inner_left = left + 1
        inner_top = top + 1
        if not (
            inner_left <= x < inner_left + self.cols * CELL_W
            and inner_top <= y < inner_top + self.rows
        ):
            return None
        return (y - inner_top, (x - inner_left) // CELL_W)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="match3",
        description="Play Match 3 in your terminal. No dependencies required.",
    )
    parser.add_argument("--rows", type=int, default=8, help="board rows, 4-12")
    parser.add_argument("--cols", type=int, default=8, help="board columns, 4-12")
    parser.add_argument(
        "--kinds", type=int, default=6, help="number of gem types, 3-6"
    )
    parser.add_argument(
        "--moves",
        type=int,
        default=30,
        help="moves per game (default: 30, ignored with --zen)",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="target score (default: 60 per move; 0 disables)",
    )
    parser.add_argument(
        "--zen", action="store_true", help="endless mode with no move limit"
    )
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="force ASCII characters instead of Unicode glyphs",
    )
    parser.add_argument(
        "--no-mouse", action="store_true", help="disable mouse input"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="do not persist best scores"
    )
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not 4 <= args.rows <= 12:
        parser.error("--rows must be between 4 and 12")
    if not 4 <= args.cols <= 12:
        parser.error("--cols must be between 4 and 12")
    if not 3 <= args.kinds <= 6:
        parser.error("--kinds must be between 3 and 6")
    if args.moves < 1:
        parser.error("--moves must be at least 1")
    if args.target is not None and args.target < 0:
        parser.error("--target cannot be negative")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(
            "match3 needs an interactive terminal (stdin and stdout must be a TTY).",
            file=sys.stderr,
        )
        return 1

    os.environ.setdefault("ESCDELAY", "25")
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass

    moves = None if args.zen else args.moves
    if args.target is not None:
        target = args.target or None
    elif args.zen:
        target = None
    else:
        target = args.moves * 60

    game = Game(
        rows=args.rows,
        cols=args.cols,
        kinds=args.kinds,
        moves=moves,
        target=target,
        seed=args.seed,
        unicode=not args.ascii and _supports_unicode(),
        mouse=not args.no_mouse,
        save_best=not args.no_save,
    )

    try:
        curses.wrapper(game.run)
    except KeyboardInterrupt:
        return 130
    except curses.error as error:
        print(f"Terminal could not be initialized: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
