"""Review public restoration instructions with the local Codex CLI."""

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from collect_restore_docs import OUTPUT as DOCUMENTS, main as collect

ROOT = Path(__file__).resolve().parent
SCHEMA = ROOT / ".github" / "restore-review.schema.json"
PROMPT = ROOT / ".github" / "restore-review.prompt.txt"
OUTPUT = ROOT / "out" / "restore-review.json"


def main():
    collect()
    documents = json.loads(DOCUMENTS.read_text(encoding="utf-8"))
    with TemporaryDirectory(dir=OUTPUT.parent) as directory:
        report = Path(directory) / "review.json"
        if documents:
            prompt = PROMPT.read_text(encoding="utf-8") + "\n" + json.dumps(documents, ensure_ascii=False)
            try:
                subprocess.run(
                    ["codex", "-a", "never", "--disable", "shell_tool", "--disable", "unified_exec",
                     "-c", 'web_search="disabled"', "exec", "--ignore-user-config",
                     "--sandbox", "read-only",
                     "--model", os.environ.get("CODEX_REVIEW_MODEL", "gpt-5.5"),
                     "--output-schema", str(SCHEMA), "--output-last-message", str(report), "-"],
                    cwd=ROOT, input=prompt, text=True, check=True,
                )
            except FileNotFoundError:
                sys.exit("Codex CLI is required for make review-restore.")
            except subprocess.CalledProcessError as error:
                sys.exit(f"Codex restoration review failed (exit {error.returncode}).")
            json.loads(report.read_text(encoding="utf-8"))
        else:
            print("No GitHub documents to review.")
            report.write_text('{"candidates": []}\n', encoding="utf-8")
        report.replace(OUTPUT)
    print(f"Codex restoration review: {OUTPUT}")


if __name__ == "__main__":
    main()
