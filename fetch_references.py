"""Fetch the six versioned public program files and verify their exact bytes."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile


def fetch(folder):
    folder.mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path(__file__).with_name("references.json").read_text())
    for name, ref in spec.items():
        dest = folder / (name + ".csv")
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError(f"{dest} already exists with different contents")
            continue
        url = f"https://www.kaggle.com/api/v1/datasets/download/{ref['dataset']}?datasetVersionNumber={ref['version']}"
        with (
            urlopen(url, timeout=90) as response,
            ZipFile(io.BytesIO(response.read())) as archive,
        ):
            content = archive.read(ref["file"])
        if hashlib.sha256(content).hexdigest() != ref["sha256"]:
            raise ValueError(f"Unexpected checksum for {name}")
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as out:
            out.write(content)
            tmp = Path(out.name)
        try:
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
        print(f"{name}: verified", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path, nargs="?", default=Path("data"))
    fetch(ap.parse_args().directory)
