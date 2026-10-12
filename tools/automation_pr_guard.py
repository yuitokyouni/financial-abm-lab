"""Leave pending generated PRs unchanged until their review is resolved.

Uses only read-only GitHub REST requests and the Python standard library.
The workflow's concurrency group serializes runs before this check.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def pending_pr_numbers(fetch_page, repository: str, prefix: str, base: str) -> list[int]:
    """Inspect every page, including legacy branches named with run IDs."""
    pending = []
    page = 1
    while True:
        prs = fetch_page(page)
        if not isinstance(prs, list):
            raise ValueError("GitHub did not return a pull-request list")
        for pr in prs:
            head = pr["head"]
            head_repository = (head.get("repo") or {}).get("full_name")
            if (
                pr["state"] == "open"
                and head_repository == repository
                and head["ref"].startswith(prefix)
                and pr["base"]["ref"] == base
            ):
                pending.append(pr["number"])
        if len(prs) < 100:
            return sorted(set(pending))
        page += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--base", default="main")
    args = parser.parse_args()
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    output = os.environ.get("GITHUB_OUTPUT", "")
    if not repository or not token or not output:
        print("::error::GITHUB_REPOSITORY, GITHUB_TOKEN and GITHUB_OUTPUT are required", file=sys.stderr)
        return 1
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")

    def fetch_page(page):
        query = urlencode({"state": "open", "base": args.base, "per_page": 100, "page": page})
        request = Request(
            f"{api_url}/repos/{repository}/pulls?{query}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    try:
        pending = pending_pr_numbers(fetch_page, repository, args.prefix, args.base)
    except HTTPError as exc:
        print(f"::error::Cannot inspect pending PRs (HTTP {exc.code}); generation blocked", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, ValueError, KeyError, TypeError):
        print("::error::Cannot inspect pending PRs; generation blocked", file=sys.stderr)
        return 1

    can_run = not pending
    with Path(output).open("a", encoding="utf-8") as handle:
        handle.write(f"can_run={str(can_run).lower()}\n")
    if pending:
        numbers = ", ".join(f"#{number}" for number in pending)
        print(f"::notice::Generation skipped while {numbers} await review; their branches remain unchanged")
    else:
        print("No pending PR for this workflow; generation may proceed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
