"""Repository acquisition: pinning, verification, isolation, cleanup."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from support import make_repository

from runner.acquisition import (
    AcquisitionError,
    acquire,
    diff_manifests,
    remove_tree,
    validate_spec,
    verify,
)
from runner.provenance import file_manifest


class GitInvocationTests(unittest.TestCase):
    """The benchmark's git environment must not inherit a host setting that breaks pinning."""

    def test_pinned_checkout_does_not_depend_on_the_host_long_path_setting(self) -> None:
        from unittest import mock

        from runner import acquisition

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            completed = mock.Mock(returncode=0, stdout="ok\n", stderr="")
            with mock.patch.object(acquisition.subprocess, "run", return_value=completed) as run:
                acquisition._git(["rev-parse", "HEAD"], workspace, workspace, "git")
        argv = run.call_args.args[0]
        self.assertIn("core.longpaths=true", argv)
        self.assertIn("core.fsmonitor=false", argv)
        self.assertIn("submodule.recurse=false", argv)


@unittest.skipUnless(shutil.which("git"), "git is required")
class AcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository, self.commit = make_repository(self.root / "origin")
        self.url = self.repository.as_uri()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_acquires_the_pinned_commit_and_preserves_the_snapshot(self) -> None:
        workspace = self.root / "workspace"
        acquired = acquire(self.url, self.commit, workspace)
        self.assertEqual(acquired.verified_commit, self.commit)
        self.assertEqual(acquired.identity()["commit"], self.commit)
        self.assertGreater(acquired.file_count, 0)
        self.assertTrue((acquired.working / "src" / "orders" / "api.py").is_file())
        self.assertTrue(verify(acquired))

        (acquired.working / "src" / "orders" / "api.py").write_text("changed\n", encoding="utf-8")
        (acquired.working / "new-file.py").write_text("added\n", encoding="utf-8")
        self.assertTrue(verify(acquired), "the source snapshot must not change with the working copy")
        self.assertEqual(
            file_manifest(acquired.source)["src/orders/api.py"],
            acquired.manifest["src/orders/api.py"],
        )

    def test_acquisition_is_reproducible(self) -> None:
        first = acquire(self.url, self.commit, self.root / "first")
        second = acquire(self.url, self.commit, self.root / "second")
        self.assertEqual(first.identity(), second.identity())
        self.assertEqual(first.manifest, second.manifest)

    def test_incorrect_commit_is_rejected(self) -> None:
        with self.assertRaises(AcquisitionError) as raised:
            acquire(self.url, "0" * 40, self.root / "wrong")
        self.assertEqual(raised.exception.code, "commit_not_found")

    def test_invalid_url_and_commit_are_configuration_errors(self) -> None:
        for url, commit in (("ftp://example.invalid/repo", self.commit),
                            (self.url, "not-a-sha")):
            with self.assertRaises(AcquisitionError) as raised:
                acquire(url, commit, self.root / "invalid")
            self.assertIn(raised.exception.code, ("invalid_url", "invalid_commit"))

    def test_diff_manifests_reports_added_removed_modified(self) -> None:
        before = {"a.py": "1", "b.py": "2", "c.py": "3"}
        after = {"a.py": "1", "b.py": "9", "d.py": "4"}
        changes = diff_manifests(before, after)
        self.assertEqual(changes["added"], ["d.py"])
        self.assertEqual(changes["removed"], ["c.py"])
        self.assertEqual(changes["modified"], ["b.py"])

    def test_cleanup_removes_the_workspace(self) -> None:
        workspace = self.root / "workspace"
        acquire(self.url, self.commit, workspace)
        remove_tree(workspace)
        self.assertFalse(workspace.exists())

    def test_validate_spec_rejects_a_branch_name(self) -> None:
        with self.assertRaises(AcquisitionError):
            validate_spec(self.url, "main")


if __name__ == "__main__":
    unittest.main()
