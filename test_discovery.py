import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import discover_santa_answers as discovery
import sync_santa_answers as sync


class DiscoveryTests(unittest.TestCase):
    def test_missing_notebook_does_not_stop_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (patch.object(discovery, "OUTPUT", root),
                  patch.object(discovery, "DISCOVERED", root / "references.json"),
                  patch.object(discovery, "load_references", return_value={}),
                  patch.object(discovery, "discussion_references", return_value=([], [])),
                  patch.object(discovery, "search_datasets", return_value=[]),
                  patch.object(discovery, "search_notebooks", return_value={"missing/notebook": None}),
                  patch.object(discovery, "load_puzzles", return_value={}),
                  patch.object(discovery, "inspect_notebook", side_effect=sync.KaggleSourceNotFound("not found"))):
                self.assertFalse(discovery.discover(1))

    def test_download_distinguishes_missing_from_other_errors(self):
        with patch.object(sync.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, "", "404 Client Error: Not Found")
            with self.assertRaises(sync.KaggleSourceNotFound):
                sync.kaggle_download("kernels", "output", "missing/notebook")
            run.return_value = subprocess.CompletedProcess([], 1, "", "500 Client Error")
            with self.assertRaises(subprocess.CalledProcessError):
                sync.kaggle_download("kernels", "output", "broken/notebook")


if __name__ == "__main__":
    unittest.main()
