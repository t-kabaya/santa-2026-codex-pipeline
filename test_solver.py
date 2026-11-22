import tempfile
import unittest
from pathlib import Path

from construct import compile_dag, InstructionBudgetExceeded
from machine import Puzzle, load_programs, replay, save_verified
from schedule import allocate
from tiny import shortest


class CalculatorTests(unittest.TestCase):
    def test_covered_target_survives_register_overwrite(self):
        p = Puzzle("overwrite", (2, 3), (5, 15), 20, 2)
        self.assertEqual(2, replay(p, [["+", 0, 1, 0], ["*", 0, 1, 0]]))

    def test_invalid_programs(self):
        p = Puzzle("limits", (2, 3), (2,), 9, 3)
        for ins in [
            ["/", 1, 0, 2],
            ["-", 0, 1, 2],
            ["-", 0, 0, 2],
            ["+", 2, 0, 0],
            ["+", 0, 1, 3],
            ["+", True, 0, 2],
            ["^", 0, 0, 2],
        ]:
            with self.subTest(ins=ins), self.assertRaises(ValueError):
                replay(p, [ins])
        with self.assertRaises(ValueError):
            replay(p, [["*", 1, 1, 2], ["+", 2, 0, 2]])

    def test_tiny_exhaustion_proves_optimum(self):
        p = Puzzle("tiny", (1,), (15,), 16, 20)
        code = shortest(p)
        self.assertEqual(replay(p, code), 4)
        self.assertEqual(shortest(Puzzle("initial", (3,), (3,), 5, 5)), [])

    def test_last_use_releases_seed_registers(self):
        p = Puzzle("slots", (2, 3), (5, 15), 15, 2)
        expr = {5: (2, "+", 3), 15: (5, "*", 3)}
        self.assertEqual(2, replay(p, allocate(p, expr, [5, 15])))

    def test_spill_budget_preserves_incumbent(self):
        p = Puzzle("budget", (1,), (8,), 10, 4)
        expr = {2: (1, "+", 1), 4: (2, "+", 2), 8: (4, "+", 4)}
        with self.assertRaises(InstructionBudgetExceeded):
            compile_dag(p, expr, list(expr), max_steps=2)

    def test_failed_output_does_not_replace_valid_checkpoint(self):
        p = Puzzle("atomic", (1,), (2,), 8, 3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "submission.csv"
            good = {"atomic": [["+", 0, 0, 1]]}
            save_verified(path, [p], good)
            with self.assertRaises(ValueError):
                save_verified(path, [p], {"atomic": []})
            self.assertEqual(load_programs(path), good)


if __name__ == "__main__":
    unittest.main()
