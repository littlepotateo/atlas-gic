"""Load KEY=VALUE env files into the process environment at CLI start.

Search order (first existing file of each kind is read, all are optional):
  1. $ATLAS_ENV_FILE, if set (an explicit path; a missing file is an error the CLI reports)
  2. ./.env in the current directory
  3. ~/.config/atlas/.env

Values already set in the process environment always win, so an exported variable overrides any
file. Nothing is printed: only the NAMES loaded are returned. Keys still come only from the
environment; a file is just a convenient way to fill it, and it should live outside git.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ENV_FILE_VAR = "ATLAS_ENV_FILE"
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


class EnvFileError(ValueError):
    """An env file named by ATLAS_ENV_FILE is missing or unreadable."""


def parse_env_text(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines. Blank lines and lines starting with '#' are skipped; a value in
    matching single or double quotes is unquoted; an inline ' #' comment is dropped from
    unquoted values. Lines that are not assignments are ignored."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        m = _LINE.match(raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if value[:1] in ("'", '"'):
            close = value.find(value[0], 1)
            value = value[1:close] if close != -1 else value[1:]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        out[key] = value
    return out


def candidate_paths(environ=os.environ, home: Path | None = None, cwd: Path | None = None) -> list[Path]:
    home = home if home is not None else Path.home()
    cwd = cwd if cwd is not None else Path.cwd()
    paths: list[Path] = []
    explicit = environ.get(ENV_FILE_VAR, "").strip()
    if explicit:
        paths.append(Path(explicit).expanduser())
        return paths
    paths.append(cwd / ".env")
    paths.append(home / ".config" / "atlas" / ".env")
    return paths


def load_env_files(environ=None, home: Path | None = None, cwd: Path | None = None) -> list[str]:
    """Load the env files into `environ` (default: os.environ). Returns the variable NAMES that
    were set from a file. Raises EnvFileError only for an explicit ATLAS_ENV_FILE that cannot
    be read; a missing default file is silently skipped."""
    environ = os.environ if environ is None else environ
    loaded: list[str] = []
    explicit = bool(environ.get(ENV_FILE_VAR, "").strip())
    for path in candidate_paths(environ, home, cwd):
        if not path.is_file():
            if explicit:
                raise EnvFileError(f"{ENV_FILE_VAR} points to a file that does not exist: {path}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            if explicit:
                raise EnvFileError(f"cannot read {ENV_FILE_VAR} file {path}: {type(e).__name__}") from None
            continue
        for key, value in parse_env_text(text).items():
            if key not in environ or not str(environ.get(key, "")).strip():
                environ[key] = value
                loaded.append(key)
    return loaded
