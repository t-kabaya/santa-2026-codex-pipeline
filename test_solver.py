import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from machine import Puzzle, load_programs, replay, save_verified
from sync_santa_answers import download


class CalculatorTests(unittest.TestCase):
    def test_dataset_merges_best_program_per_puzzle_across_csvs(self):
        puzzles = [Puzzle(pid, (1,), (2,), 8, 3) for pid in ("p", "q")]
        short = [["+", 0, 0, 1]]
        longer = short * 2
        ref = {"dataset": "owner/dataset", "file": "submission.csv"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "dataset.zip"
            scratch = root / "candidate.csv"
            with ZipFile(archive_path, "w") as archive:
                save_verified(scratch, puzzles, {"p": short, "q": longer})
                archive.write(scratch, "submission.csv")
                save_verified(scratch, puzzles, {"p": longer, "q": short})
                archive.write(scratch, "bench/frontier.csv")
                archive.writestr("invalid.csv", b"id,program\np,[]\n")
            with patch("sync_santa_answers.download_archive", return_value=archive_path):
                for filename in ("submission.csv", "submission_old.csv"):
                    with self.subTest(filename=filename):
                        raw = download("source", {**ref, "file": filename}, puzzles, scratch, {})
                        self.assertEqual(raw, scratch.read_bytes())
                        self.assertEqual(load_programs(scratch), {"p": short, "q": short})
                with ZipFile(archive_path, "w") as archive:
                    archive.writestr("invalid.csv", b"id,program\np,[]\n")
                self.assertIsNone(download("source", ref, puzzles, scratch, {}))

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
