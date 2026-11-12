"""Tests for the pure Match-3 engine (no terminal required)."""

from __future__ import annotations

import random
import unittest

from match3_logic import Board


DEAD_BOARD = [
    [1, 2, 1],
    [1, 0, 0],
    [2, 0, 1],
]

PLAYABLE_BOARD = [
    [0, 0, 1],
    [1, 2, 0],
    [1, 2, 0],
]


class NewBoardTests(unittest.TestCase):
    def test_generated_boards_are_match_free_and_playable(self) -> None:
        for seed in range(25):
            for rows, cols, kinds in ((4, 4, 3), (8, 8, 6), (12, 9, 5)):
                with self.subTest(seed=seed, rows=rows, cols=cols, kinds=kinds):
                    board = Board(rows, cols, kinds, rng=random.Random(seed))
                    self.assertFalse(board.find_groups())
                    self.assertTrue(board.has_valid_move())
                    self.assertEqual(len(board.grid), rows)
                    self.assertTrue(all(len(row) == cols for row in board.grid))
                    self.assertTrue(
                        all(
                            0 <= kind < kinds
                            for row in board.grid
                            for kind in row
                            if kind is not None
                        )
                    )

    def test_new_board_starts_at_zero_score(self) -> None:
        board = Board(rng=random.Random(1))
        self.assertEqual(board.score, 0)

    def test_invalid_dimensions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Board(rows=2, cols=2)
        with self.assertRaises(ValueError):
            Board(kinds=2)
        with self.assertRaises(ValueError):
            Board(rows=21, cols=8)


class MatchDetectionTests(unittest.TestCase):
    def test_horizontal_run(self) -> None:
        board = Board.from_rows(
            [
                [0, 0, 0],
                [1, 2, 3],
                [3, 1, 2],
            ],
            kinds=4,
        )
        groups = board.find_groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0]), {(0, 0), (0, 1), (0, 2)})

    def test_vertical_run(self) -> None:
        board = Board.from_rows(
            [
                [0, 1, 2],
                [0, 3, 1],
                [0, 2, 3],
            ],
            kinds=4,
        )
        groups = board.find_groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0]), {(0, 0), (1, 0), (2, 0)})

    def test_two_runs_can_intersect(self) -> None:
        board = Board.from_rows(
            [
                [0, 1, 2],
                [0, 0, 0],
                [0, 2, 2],
            ],
            kinds=3,
        )
        groups = board.find_groups()
        self.assertEqual(len(groups), 2)
        cleaned = {cell for group in groups for cell in group}
        self.assertEqual(len(cleaned), 5)

    def test_no_false_positives(self) -> None:
        board = Board.from_rows(
            [
                [0, 0, 1],
                [0, 1, 1],
                [1, 0, 0],
            ],
            kinds=3,
        )
        self.assertEqual(board.find_groups(), [])


class SwapTests(unittest.TestCase):
    def test_swap_cells_requires_adjacency(self) -> None:
        board = Board.from_rows(PLAYABLE_BOARD, kinds=4)
        before = board.snapshot()
        self.assertFalse(board.swap_cells((0, 0), (2, 2)))
        self.assertEqual(board.snapshot(), before)
        self.assertTrue(board.swap_cells((0, 1), (0, 2)))
        self.assertNotEqual(board.snapshot(), before)
        self.assertTrue(board.swap_cells((0, 1), (0, 2)))
        self.assertEqual(board.snapshot(), before)

    def test_invalid_swap_is_reverted_and_costs_nothing(self) -> None:
        board = Board.from_rows(
            [
                [0, 1, 2],
                [1, 2, 3],
                [2, 3, 0],
            ],
            kinds=4,
        )
        before = board.snapshot()
        result = board.try_swap((0, 0), (0, 1))
        self.assertFalse(result.swapped)
        self.assertEqual(board.snapshot(), before)
        self.assertEqual(board.score, 0)
        self.assertEqual(result.steps, ())

    def test_non_adjacent_swap_is_rejected(self) -> None:
        board = Board.from_rows(PLAYABLE_BOARD, kinds=4)
        before = board.snapshot()
        self.assertFalse(board.try_swap((0, 0), (2, 2)).swapped)
        self.assertEqual(board.snapshot(), before)

    def test_valid_swap_clears_and_refills(self) -> None:
        board = Board.from_rows(PLAYABLE_BOARD, kinds=4, rng=random.Random(2))
        result = board.try_swap((0, 2), (1, 2))
        self.assertTrue(result.swapped)
        self.assertGreaterEqual(result.points, 30)
        self.assertEqual(result.steps[0].kind, "clear")
        self.assertEqual(result.steps[-1].kind, "fall")
        self.assertIn(None, [cell for row in result.steps[0].grid for cell in row])
        self.assertFalse(board.find_groups())
        self.assertTrue(all(cell is not None for row in board.grid for cell in row))
        self.assertEqual(board.score, result.points)

    def test_hint_is_a_real_move(self) -> None:
        board = Board(7, 7, 5, rng=random.Random(9))
        hint = board.find_hint()
        self.assertIsNotNone(hint)
        assert hint is not None
        a, b = hint
        self.assertTrue(board.are_adjacent(a, b))
        self.assertTrue(board.would_match(a, b))

    def test_hint_is_none_on_dead_board(self) -> None:
        board = Board.from_rows(DEAD_BOARD, kinds=3)
        self.assertFalse(board.has_valid_move())
        self.assertIsNone(board.find_hint())


class ResolutionTests(unittest.TestCase):
    def test_long_group_gets_a_bonus(self) -> None:
        board = Board.from_rows(
            [
                [0, 0, 0, 0],
                [1, 2, 3, 1],
                [2, 3, 1, 2],
                [3, 1, 2, 3],
            ],
            kinds=4,
            rng=random.Random(3),
        )
        steps, points, cascades, cleared, groups = board.resolve()
        self.assertGreaterEqual(cascades, 1)
        self.assertGreaterEqual(cleared, 4)
        self.assertGreaterEqual(groups, 1)
        self.assertEqual(steps[0].points, 65)  # 4 gems + two extra-for-three bonus
        self.assertEqual(board.score, points)
        self.assertFalse(board.find_groups())
        self.assertTrue(all(cell is not None for row in board.grid for cell in row))

    def test_cascade_steps_are_consistent(self) -> None:
        board = Board.from_rows(
            [
                [0, 0, 0, 1],
                [1, 2, 3, 0],
                [3, 1, 2, 3],
                [2, 3, 1, 2],
            ],
            kinds=4,
            rng=random.Random(5),
        )
        result = board.try_swap((0, 3), (1, 3))
        self.assertTrue(result.swapped)
        self.assertEqual(len(result.steps) % 2, 0)
        for step in result.steps:
            self.assertEqual(len(step.grid), board.rows)
            self.assertTrue(all(len(row) == board.cols for row in step.grid))
            if step.kind == "clear":
                self.assertTrue(step.cleared)
                for r, c in step.cleared:
                    self.assertIsNone(step.grid[r][c])
            else:
                self.assertEqual(step.kind, "fall")
                self.assertTrue(
                    all(cell is not None for row in step.grid for cell in row)
                )

    def test_restore_snapshot(self) -> None:
        board = Board(rng=random.Random(11))
        snapshot = board.snapshot()
        hint = board.find_hint()
        assert hint is not None
        board.try_swap(*hint)
        self.assertGreater(board.score, 0)
        board.restore(snapshot, 0)
        self.assertEqual(board.snapshot(), snapshot)
        self.assertEqual(board.score, 0)


class PlayabilityTests(unittest.TestCase):
    def test_dead_board_detection(self) -> None:
        self.assertFalse(Board.from_rows(DEAD_BOARD, kinds=3).has_valid_move())

    def test_playable_board_detection(self) -> None:
        self.assertTrue(Board.from_rows(PLAYABLE_BOARD, kinds=4).has_valid_move())

    def test_shuffle_produces_playable_match_free_board(self) -> None:
        board = Board.from_rows(DEAD_BOARD, kinds=3, rng=random.Random(4))
        board.shuffle()
        self.assertFalse(board.find_groups())
        self.assertTrue(board.has_valid_move())

    def test_many_turns_keep_board_healthy(self) -> None:
        board = Board(8, 8, 6, rng=random.Random(1234))
        for turn in range(40):
            hint = board.find_hint()
            if hint is None:
                board.shuffle()
                hint = board.find_hint()
            self.assertIsNotNone(hint, msg=f"no move after shuffle on turn {turn}")
            assert hint is not None
            result = board.try_swap(*hint)
            self.assertTrue(result.swapped)
            self.assertFalse(board.find_groups())
            self.assertTrue(
                all(cell is not None for row in board.grid for cell in row)
            )
            self.assertGreaterEqual(board.score, 0)
        self.assertGreater(board.score, 0)


if __name__ == "__main__":
    unittest.main()
