"""
Productivity tools for agents

Available tools (loaded when dependencies are present):
- search_web, read_webpage: Web search / extract (tavily-python, requests)
- create_file: Create files (python-docx, openpyxl, reportlab, etc.)
- execute_code_sandbox: Run Python in E2B sandbox (e2b-code-interpreter)
- read_file: Read PDF/DOCX/XLSX etc. (PyPDF2, python-docx, openpyxl)
- create_video: Create MP4 from slides

If a submodule fails to import (e.g. missing e2b-code-interpreter), only that tool
is omitted; others remain available.
"""

__all__ = [
    "search_web",
    "read_webpage",
    "create_file",
    "execute_code_sandbox",
    "read_file",
    "create_video"
]

# Optional imports: load each submodule so one missing dep doesn't kill all productivity tools
search_web = None
read_webpage = None
create_file = None
execute_code_sandbox = None
read_file = None
create_video = None

try:
    from .search import search_web as _sw, read_webpage as _rw
    search_web = _sw
    read_webpage = _rw
except ImportError as e:
    import warnings
    warnings.warn(f"livebench.tools.productivity: search not loaded: {e}")

try:
    from .file_creation import create_file as _cf
    create_file = _cf
except ImportError as e:
    import warnings
    warnings.warn(f"livebench.tools.productivity: create_file not loaded: {e}")

try:
    from .code_execution_sandbox import execute_code as execute_code_sandbox
except ImportError as e:
    import warnings
    warnings.warn(f"livebench.tools.productivity: execute_code_sandbox not loaded (install e2b-code-interpreter): {e}")

try:
    from .file_reading import read_file as _rf
    read_file = _rf
except ImportError as e:
    import warnings
    warnings.warn(f"livebench.tools.productivity: read_file not loaded: {e}")

try:
    from .video_creation import create_video as _cv
    create_video = _cv
except ImportError as e:
    import warnings
    warnings.warn(f"livebench.tools.productivity: create_video not loaded: {e}")
