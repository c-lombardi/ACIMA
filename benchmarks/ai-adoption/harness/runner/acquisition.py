"""Repository acquisition and snapshot isolation.

The controller fetches a pinned commit itself, verifies the resulting checkout, keeps an unmodified
source snapshot, and gives the agent a disposable working copy. Repository content is never
executed during acquisition: no hooks, no submodules, no LFS smudge, no prompts.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .provenance import file_manifest, manifest_sha256

# Git is resolved explicitly: a Python interpreter may run with a PATH that does not contain the
# git installation (a sandbox, a service, a Windows/WSL split), and acquisition must not silently
# degrade to copying a directory. An explicit executable can be supplied by config or
# ACIMA_BENCH_GIT.
GIT_CANDIDATES = (
    "git",
    "/usr/bin/git",
    "/usr/local/bin/git",
    "/bin/git",
    "/ucrt64/bin/git",
    "/mingw64/bin/git",
    "/opt/homebrew/bin/git",
    "C:/Program Files/Git/cmd/git.exe",
)


def resolve_git(explicit: str | None = None) -> str:
    candidates: list[str | None] = [explicit, os.environ.get("ACIMA_BENCH_GIT")]
    candidates.extend(GIT_CANDIDATES)
    for candidate in candidates:
        if not candidate:
            continue
        if "/" in candidate or "\\" in candidate:
            if Path(candidate).is_file():
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    raise AcquisitionError(
        "git_missing",
        "git is not available; set ACIMA_BENCH_GIT or config.gitExecutable to a git executable",
    )

COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
URL_PATTERN = re.compile(r"^(https://[^\s]+|file://[^\s]+)$")
GIT_TIMEOUT_SECONDS = 300


class AcquisitionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class Acquisition:
    url: str
    commit: str
    verified_commit: str
    tree_sha256: str
    manifest: dict[str, str] = field(default_factory=dict)
    file_count: int = 0
    bytes: int = 0
    source: Path | None = None
    working: Path | None = None

    def identity(self) -> dict:
        return {
            "url": self.url,
            "commit": self.commit,
            "verifiedCommit": self.verified_commit,
            "treeSha256": self.tree_sha256,
            "fileCount": self.file_count,
            "bytes": self.bytes,
            "manifestSha256": manifest_sha256(self.manifest),
        }


def validate_spec(url: str, commit: str) -> None:
    if not URL_PATTERN.match(url or ""):
        raise AcquisitionError("invalid_url", f"unsupported repository URL: {url!r}")
    if not COMMIT_PATTERN.match(commit or ""):
        raise AcquisitionError(
            "invalid_commit", f"commit must be a full lowercase 40-character SHA, got {commit!r}"
        )


def _git_environment(workspace: Path) -> dict[str, str]:
    """A narrow environment: no interactive prompts, no inherited credentials, no LFS smudge."""
    home = workspace / "git-home"
    home.mkdir(parents=True, exist_ok=True)
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "SystemRoot": os.environ.get("SystemRoot", ""),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "echo",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
        "GIT_ALLOW_PROTOCOL": "https:file",
        "GCM_INTERACTIVE": "never",
    }
    return {key: value for key, value in environment.items() if value}


def _git(args: list[str], cwd: Path, workspace: Path, executable: str) -> str:
    command = [executable]
    # Hooks and fsmonitor can execute repository-controlled code. Both stay off.
    command += ["-c", "core.hooksPath=" + str(workspace / "no-hooks"),
                "-c", "core.fsmonitor=false",
                "-c", "submodule.recurse=false",
                "-c", "advice.detachedHead=false",
                # A pinned checkout must not fail because the host's global git config left long
                # paths off; the benchmark's git environment is isolated, so it sets this itself.
                "-c", "core.longpaths=true"]
    command += args
    (workspace / "no-hooks").mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            command, cwd=str(cwd), env=_git_environment(workspace),
            capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise AcquisitionError("git_missing", "git is not installed or not on PATH") from error
    except subprocess.TimeoutExpired as error:
        raise AcquisitionError("git_timeout", f"git exceeded {GIT_TIMEOUT_SECONDS}s") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise AcquisitionError("git_failed", detail[-1] if detail else f"exit {result.returncode}")
    return result.stdout.strip()


def acquire(url: str, commit: str, workspace: Path, *, keep_git_history: bool = True,
            git_executable: str | None = None) -> Acquisition:
    """Fetch one immutable commit into ``workspace/source`` and copy it to ``workspace/working``."""
    validate_spec(url, commit)
    executable = resolve_git(git_executable)
    workspace = Path(workspace).resolve()
    source = workspace / "source"
    working = workspace / "working"
    for path in (source, working):
        if path.exists():
            remove_tree(path)
    source.mkdir(parents=True, exist_ok=True)

    _git(["init", "--quiet"], source, workspace, executable)
    _git(["remote", "add", "origin", url], source, workspace, executable)
    try:
        # Fetch by SHA when the server allows it: no branch, no tags, no history beyond the commit.
        _git(["fetch", "--quiet", "--depth", "1", "origin", commit], source, workspace, executable)
    except AcquisitionError:
        # Servers that refuse a direct SHA fetch still resolve refs. Fetch, then require the exact
        # object locally before checking it out: the pin is the SHA, not the ref.
        _git(["fetch", "--quiet", "origin", "+refs/heads/*:refs/remotes/origin/*",
              "+refs/tags/*:refs/tags/*"], source, workspace, executable)
        try:
            _git(["cat-file", "-e", commit + "^{commit}"], source, workspace, executable)
        except AcquisitionError as error:
            raise AcquisitionError(
                "commit_not_found", f"commit {commit} is not present in the fetched repository"
            ) from error
        _git(["checkout", "--quiet", "--detach", commit], source, workspace, executable)
    else:
        _git(["checkout", "--quiet", "--detach", "FETCH_HEAD"], source, workspace, executable)

    verified = _git(["rev-parse", "HEAD"], source, workspace, executable)
    if verified != commit:
        raise AcquisitionError("identity_mismatch", f"checked out {verified}, expected {commit}")
    status = _git(["status", "--porcelain", "--untracked-files=all"], source, workspace, executable)
    if status:
        raise AcquisitionError("dirty_checkout", f"checkout is not clean: {status.splitlines()[0]}")
    tree = _git(["rev-parse", "HEAD^{tree}"], source, workspace, executable)

    manifest = file_manifest(source)
    total = sum((source / name).stat().st_size for name in manifest)
    acquisition = Acquisition(
        url=url, commit=commit, verified_commit=verified, tree_sha256=tree,
        manifest=manifest, file_count=len(manifest), bytes=total, source=source,
    )
    working.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, working, symlinks=True)
    if not keep_git_history:
        shutil.rmtree(working / ".git", ignore_errors=True)
    acquisition.working = working
    return acquisition


def verify(acquisition: Acquisition) -> bool:
    """The source snapshot must still match the manifest captured at acquisition."""
    if acquisition.source is None:
        return False
    return file_manifest(acquisition.source) == acquisition.manifest


def diff_manifests(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(name for name in set(before) & set(after) if before[name] != after[name])
    return {"added": added, "removed": removed, "modified": modified}


def _force_writable(function, path, _error) -> None:
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        function(path)
    except OSError:
        pass


def remove_tree(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    shutil.rmtree(path, onerror=_force_writable)
