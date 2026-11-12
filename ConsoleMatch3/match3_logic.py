"""Pure, UI-independent game logic for the terminal Match-3 game.

The module has no third-party dependencies and no knowledge of curses, which
keeps it easy to test and to reuse from another front end.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

Coord = tuple[int, int]
Snapshot = tuple[tuple[int | None, ...], ...]


@dataclass(frozen=True)
class Step:
    """One animation frame produced while resolving matches.

    ``kind`` is either ``"clear"`` (matched gems are holes in ``grid``) or
    ``"fall"`` (the board after gravity and refill).
    """

    kind: str
    grid: Snapshot
    cleared: frozenset[Coord] = frozenset()
    cascade: int = 0
    points: int = 0
    groups: tuple[tuple[Coord, ...], ...] = ()


@dataclass(frozen=True)
class MoveResult:
    """Outcome of an attempted swap."""

    swapped: bool
    points: int = 0
    cascades: int = 0
    cleared: int = 0
    groups_cleared: int = 0
    steps: tuple[Step, ...] = ()


class Board:
    """A rectangular grid of gem kinds.

    Coordinates are ``(row, column)`` with ``(0, 0)`` in the top-left corner.
    A kind is an integer in ``range(kinds)``.
    """

    MIN_SIZE = 3
    MAX_SIZE = 20
    POINTS_PER_GEM = 10
    LONG_GROUP_BONUS = 25

    def __init__(
        self,
        rows: int = 8,
        cols: int = 8,
        kinds: int = 6,
        *,
        rng: random.Random | None = None,
    ) -> None:
        if not (self.MIN_SIZE <= rows <= self.MAX_SIZE):
            raise ValueError(f"rows must be between {self.MIN_SIZE} and {self.MAX_SIZE}")
        if not (self.MIN_SIZE <= cols <= self.MAX_SIZE):
            raise ValueError(f"cols must be between {self.MIN_SIZE} and {self.MAX_SIZE}")
        if not 3 <= kinds <= 8:
            raise ValueError("kinds must be between 3 and 8")
        if rows * cols < 9:
            raise ValueError("board must have at least 9 cells")

        self.rows = rows
        self.cols = cols
        self.kinds = kinds
        self.rng = rng or random.Random()
        self.score = 0
        self.grid: list[list[int | None]] = []
        self._generate_playable()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_rows(
        cls,
        rows: Sequence[Sequence[int]],
        *,
        kinds: int | None = None,
        rng: random.Random | None = None,
    ) -> "Board":
        """Create a board from literal rows (handy for tests and demos)."""

        grid = [list(row) for row in rows]
        if not grid or not grid[0]:
            raise ValueError("board cannot be empty")
        width = len(grid[0])
        if any(len(row) != width for row in grid):
            raise ValueError("all rows must have the same length")
        if len(grid) < cls.MIN_SIZE or width < cls.MIN_SIZE:
            raise ValueError("board is too small")
        if any(not isinstance(kind, int) or kind < 0 for row in grid for kind in row):
            raise ValueError("kinds must be non-negative integers")

        obj = cls.__new__(cls)
        obj.rows = len(grid)
        obj.cols = width
        obj.kinds = max(kinds or 0, max(max(row) for row in grid) + 1)
        if obj.kinds < 3:
            obj.kinds = 3
        obj.rng = rng or random.Random()
        obj.score = 0
        obj.grid = grid
        return obj

    def _generate_playable(self) -> None:
        """Fill the board without matches and retry until a move exists."""

        for _ in range(10_000):
            self.grid = self._make_grid()
            if self.has_valid_move():
                return
        # Practically unreachable, even for tiny boards. Fall back to a
        # deliberately playable pattern while keeping the requested size.
        self.grid = self._make_grid()
        self._force_move()
        self._clear_matches()

    def _make_grid(self) -> list[list[int]]:
        grid: list[list[int]] = [[0] * self.cols for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                banned: set[int] = set()
                if c >= 2 and grid[r][c - 1] == grid[r][c - 2]:
                    banned.add(int(grid[r][c - 1]))
                if r >= 2 and grid[r - 1][c] == grid[r - 2][c]:
                    banned.add(int(grid[r - 1][c]))
                choices = [kind for kind in range(self.kinds) if kind not in banned]
                grid[r][c] = self.rng.choice(choices)
        return grid

    def _force_move(self) -> None:
        """Create a guaranteed horizontal match opportunity in the corner."""

        self.grid[0][0] = 0
        self.grid[0][1] = 0
        self.grid[1][2] = 0
        self.grid[0][2] = 1

    def _clear_matches(self) -> None:
        """Remove any matches caused by manual grid manipulation."""

        while True:
            groups = self.find_groups()
            if not groups:
                return
            for r, c in {cell for group in groups for cell in group}:
                self.grid[r][c] = None
            self._collapse()

    # ------------------------------------------------------------------
    # Basic queries
    # ------------------------------------------------------------------
    def are_adjacent(self, a: Coord, b: Coord) -> bool:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1

    def inside(self, coord: Coord) -> bool:
        r, c = coord
        return 0 <= r < self.rows and 0 <= c < self.cols

    def find_groups(self) -> list[list[Coord]]:
        """Return every horizontal/vertical run of three or more equal gems."""

        groups: list[list[Coord]] = []
        grid = self.grid

        for r in range(self.rows):
            c = 0
            while c < self.cols:
                kind = grid[r][c]
                if kind is None:
                    c += 1
                    continue
                start = c
                c += 1
                while c < self.cols and grid[r][c] == kind:
                    c += 1
                if c - start >= 3:
                    groups.append([(r, cc) for cc in range(start, c)])

        for c in range(self.cols):
            r = 0
            while r < self.rows:
                kind = grid[r][c]
                if kind is None:
                    r += 1
                    continue
                start = r
                r += 1
                while r < self.rows and grid[r][c] == kind:
                    r += 1
                if r - start >= 3:
                    groups.append([(rr, c) for rr in range(start, r)])

        return groups

    def would_match(self, a: Coord, b: Coord) -> bool:
        if not (self.inside(a) and self.inside(b) and self.are_adjacent(a, b)):
            return False
        self._swap(a, b)
        try:
            return bool(self.find_groups())
        finally:
            self._swap(a, b)

    def has_valid_move(self) -> bool:
        for r in range(self.rows):
            for c in range(self.cols):
                for nr, nc in ((r, c + 1), (r + 1, c)):
                    if nr < self.rows and nc < self.cols:
                        if self.would_match((r, c), (nr, nc)):
                            return True
        return False

    def find_hint(self) -> tuple[Coord, Coord] | None:
        """Return the swap that clears the most gems, or ``None`` if stuck."""

        best: tuple[Coord, Coord] | None = None
        best_size = 0
        for r in range(self.rows):
            for c in range(self.cols):
                for nr, nc in ((r, c + 1), (r + 1, c)):
                    if nr >= self.rows or nc >= self.cols:
                        continue
                    a, b = (r, c), (nr, nc)
                    self._swap(a, b)
                    groups = self.find_groups()
                    size = len({cell for group in groups for cell in group})
                    self._swap(a, b)
                    if size > best_size:
                        best_size = size
                        best = (a, b)
        return best

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def _swap(self, a: Coord, b: Coord) -> None:
        ar, ac = a
        br, bc = b
        self.grid[ar][ac], self.grid[br][bc] = self.grid[br][bc], self.grid[ar][ac]

    def swap_cells(self, a: Coord, b: Coord) -> bool:
        """Swap two adjacent cells, without any match validation."""

        if not (self.inside(a) and self.inside(b) and self.are_adjacent(a, b)):
            return False
        self._swap(a, b)
        return True

    def try_swap(self, a: Coord, b: Coord) -> MoveResult:
        """Swap two neighbours if it makes a match, then resolve the board."""

        if not (self.inside(a) and self.inside(b) and self.are_adjacent(a, b)):
            return MoveResult(False)

        self._swap(a, b)
        if not self.find_groups():
            self._swap(a, b)
            return MoveResult(False)

        steps, points, cascades, cleared, groups = self.resolve()
        return MoveResult(True, points, cascades, cleared, groups, tuple(steps))

    def resolve(self) -> tuple[list[Step], int, int, int, int]:
        """Clear all matches, apply gravity/refill, and repeat for cascades.

        Returns ``(steps, points, cascades, gems_cleared, groups_cleared)``.
        """

        steps: list[Step] = []
        total_points = 0
        total_cleared = 0
        total_groups = 0
        cascade = 0

        while True:
            groups = self.find_groups()
            if not groups:
                break

            cascade += 1
            total_groups += len(groups)
            cleared = sorted({cell for group in groups for cell in group})
            bonus = sum(
                max(0, len(group) - 3) * self.LONG_GROUP_BONUS for group in groups
            )
            points = (len(cleared) * self.POINTS_PER_GEM + bonus) * cascade
            total_points += points
            total_cleared += len(cleared)

            holes = [row[:] for row in self.grid]
            for r, c in cleared:
                holes[r][c] = None
            steps.append(
                Step(
                    kind="clear",
                    grid=tuple(tuple(row) for row in holes),
                    cleared=frozenset(cleared),
                    cascade=cascade,
                    points=points,
                    groups=tuple(tuple(group) for group in groups),
                )
            )

            self.grid = holes
            self._collapse()
            steps.append(
                Step(
                    kind="fall",
                    grid=tuple(tuple(row) for row in self.grid),
                    cascade=cascade,
                )
            )

        self.score += total_points
        return steps, total_points, cascade, total_cleared, total_groups

    def _collapse(self) -> None:
        """Let gems fall down each column, then refill from the top."""

        for c in range(self.cols):
            write = self.rows - 1
            for r in range(self.rows - 1, -1, -1):
                kind = self.grid[r][c]
                if kind is not None:
                    self.grid[write][c] = kind
                    write -= 1
            while write >= 0:
                self.grid[write][c] = self.rng.randrange(self.kinds)
                write -= 1

    def shuffle(self) -> None:
        """Reshuffle the existing gems into a match-free, playable layout."""

        flat = [kind for row in self.grid for kind in row if kind is not None]
        for _ in range(500):
            self.rng.shuffle(flat)
            self.grid = [
                flat[r * self.cols : (r + 1) * self.cols] for r in range(self.rows)
            ]
            if not self.find_groups() and self.has_valid_move():
                return

        # Extremely unlikely fallback: build a brand new playable board.
        self._generate_playable()

    def snapshot(self) -> Snapshot:
        return tuple(tuple(row) for row in self.grid)

    def restore(self, snapshot: Snapshot, score: int) -> None:
        self.grid = [list(row) for row in snapshot]
        self.score = score

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------
    def render(self) -> str:
        """Small text rendering used by tests and debugging."""

        return "\n".join(
            "".join("." if kind is None else str(kind) for kind in row)
            for row in self.grid
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience
        return f"Board({self.rows}x{self.cols}, kinds={self.kinds}, score={self.score})"
