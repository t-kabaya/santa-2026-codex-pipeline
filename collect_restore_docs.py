"""Collect public GitHub documentation for the Santa restoration review."""

import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
from urllib.error import URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

from discover_santa_discussion import OUTPUT as DISCUSSION

OUTPUT = DISCUSSION.with_name("repository-docs.json")
API = "https://api.github.com/repos"
NAME = re.compile(r"[A-Za-z0-9_.-]+")
LINK = re.compile(r"\]\(([^\s)]+)\)")


def request(url):
    with urlopen(Request(url, headers={"User-Agent": "santa-restore-review"}), timeout=20) as response:
        return response.read(256 * 1024 + 1)


def repository(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        return None
    parts = parsed.path.strip("/").split("/")[:2]
    if len(parts) == 2 and all(NAME.fullmatch(part) and part not in {".", ".."} for part in parts):
        return "/".join(parts).removesuffix(".git")


def collect(repo):
    revision = json.loads(request(f"{API}/{repo}/commits/HEAD"))["sha"]
    readme = json.loads(request(f"{API}/{repo}/readme?ref={revision}"))
    body = base64.b64decode(readme["content"]).decode("utf-8", errors="replace")
    documents = {readme["path"]: body[:32000]}
    for target in LINK.findall(body):
        path = PurePosixPath(unquote(urlsplit(target).path))
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() not in {".md", ".json", ".txt"}:
            continue
        if not re.search(r"restore|reproduc|release|source|portfolio|checkpoint|artifact", str(path), re.I):
            continue
        path = PurePosixPath(readme["path"]).parent / path
        if str(path) in documents:
            continue
        try:
            raw = request(f"https://raw.githubusercontent.com/{repo}/{revision}/{quote(str(path))}")
        except (URLError, TimeoutError):
            continue
        documents[str(path)] = raw.decode("utf-8", errors="replace")[:24000]
        if len(documents) == 5:
            break
    return {"repository": f"https://github.com/{repo}", "commit": revision, "documents": documents}


def main():
    topics = json.loads(DISCUSSION.read_text(encoding="utf-8"))
    repositories = dict.fromkeys(
        repo for topic in topics for link in topic["links"]
        if link["kind"] in {"github", "csv"} and (repo := repository(link["url"]))
    )
    results = []
    seen = set()
    for repo in list(repositories)[:10]:
        if repo.lower() in seen:
            continue
        seen.add(repo.lower())
        try:
            results.append(collect(repo))
        except (URLError, TimeoutError, KeyError, ValueError) as error:
            print(f"{repo}: {error}")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} repositories collected")
    if github_output := os.environ.get("GITHUB_OUTPUT"):
        with open(github_output, "a", encoding="utf-8") as output:
            print(f"found={'true' if results else 'false'}", file=output)


if __name__ == "__main__":
    main()
