"""
Path helpers for cross-platform file I/O.
On Windows, paths >= 260 chars need the \\?\ prefix for open/shutil to succeed.
"""
import os
import sys
from typing import Optional


def path_for_io(path: Optional[str]) -> Optional[str]:
    """
    Return a path suitable for open(), shutil.copy2(), etc.
    On Windows, if the absolute path length >= 260, returns the long form (\\\\?\\ + absolute path).
    Otherwise returns the path unchanged (or normalized).
    """
    if path is None or not isinstance(path, str) or not path.strip():
        return path
    if sys.platform != "win32":
        return os.path.normpath(path)
    # Already long form
    if path.strip().startswith("\\\\?\\"):
        return os.path.normpath(path)
    abs_path = os.path.normpath(os.path.abspath(path))
    if len(abs_path) >= 260:
        return "\\\\?\\" + abs_path
    return abs_path
