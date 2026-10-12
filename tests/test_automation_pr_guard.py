"""Regression checks for leaving pending automated PRs untouched."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError


SPEC = importlib.util.spec_from_file_location(
    "automation_pr_guard", Path(__file__).resolve().parents[1] / "tools" / "automation_pr_guard.py"
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def pull(number, ref, *, repo="owner/repo", base="main", state="open"):
    return {"number": number, "state": state, "head": {"ref": ref, "repo": {"full_name": repo}}, "base": {"ref": base}}


class AutomationPRGuardTests(unittest.TestCase):
    def test_finds_legacy_and_stable_heads_without_blocking_other_families(self):
        data = [pull(1, "annotate/123"), pull(2, "annotate/pending"), pull(3, "propose/456"),
                pull(4, "annotate/789", repo="fork/repo"), pull(5, "annotate/012", base="develop"),
                pull(6, "annotate/345", state="closed")]
        self.assertEqual(guard.pending_pr_numbers(lambda page: data, "owner/repo", "annotate/", "main"), [1, 2])

    def test_pending_pr_on_second_page_is_not_missed(self):
        pages = {1: [pull(n, f"propose/{n}") for n in range(100)], 2: [pull(143, "annotate/old-run")]}
        called = []
        def fetch(page):
            called.append(page)
            return pages[page]
        self.assertEqual(guard.pending_pr_numbers(fetch, "owner/repo", "annotate/", "main"), [143])
        self.assertEqual(called, [1, 2])

    def test_malformed_or_failed_read_cannot_be_treated_as_empty_queue(self):
        with self.assertRaises(ValueError):
            guard.pending_pr_numbers(lambda page: {"message": "rate limited"}, "owner/repo", "annotate/", "main")
        with self.assertRaises(KeyError):
            guard.pending_pr_numbers(lambda page: [{"number": 143}], "owner/repo", "annotate/", "main")

    def run_main(self, response=None, error=None):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            env = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "test-token-must-not-appear", "GITHUB_OUTPUT": str(output)}
            stream = io.StringIO()
            with patch.dict(guard.os.environ, env, clear=True), patch("sys.argv", ["guard", "--prefix", "annotate/"]), \
                 patch.object(guard, "urlopen", side_effect=error, return_value=io.BytesIO(json.dumps(response).encode())), \
                 redirect_stdout(stream), redirect_stderr(stream):
                result = guard.main()
            return result, output.read_text() if output.exists() else "", stream.getvalue()

    def test_pending_read_writes_false(self):
        result, output, message = self.run_main([pull(143, "annotate/123")])
        self.assertEqual((result, output), (0, "can_run=false\n"))
        self.assertIn("#143", message)

    def test_empty_read_allows_generation(self):
        result, output, _ = self.run_main([])
        self.assertEqual((result, output), (0, "can_run=true\n"))

    def test_network_failure_fails_closed_and_does_not_print_token(self):
        result, output, message = self.run_main(error=URLError("test-token-must-not-appear"))
        self.assertEqual((result, output), (1, ""))
        self.assertNotIn("test-token-must-not-appear", message)


if __name__ == "__main__":
    unittest.main()
