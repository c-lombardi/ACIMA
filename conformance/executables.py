"""Resolve external executables from the environment, never from machine-specific paths.

A toolchain can be supplied by the process environment through ``PATH`` or by the
conventional ``<NAME>_ROOT`` variable (for example ``DOTNET_ROOT``).  If neither
source resolves it, the caller must stop or report the missing toolchain explicitly;
there is no fallback list of installation directories.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_executable(name: str) -> str | None:
    """Return the resolved executable path, or ``None`` when it is unavailable."""
    if not name:
        return None
    found = shutil.which(name)
    if found:
        return found
    root = os.environ.get(f"{name.upper()}_ROOT")
    if not root:
        return None
    base = Path(root)
    for candidate in (base / name, base / f"{name}.exe"):
        if candidate.is_file():
            return str(candidate)
    return None
