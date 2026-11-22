import tempfile
import unittest
from pathlib import Path

from machine import Puzzle, load_programs, replay, save_verified


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
