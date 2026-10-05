#!/usr/bin/env python3
"""Install the skill into one selected directory without overwriting it."""

import argparse
from pathlib import Path
import shutil
import sys


def install(source, destination):
    source = source.resolve()
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError("Source directory has no SKILL.md")
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("SKILL.md", "requirements.txt", "agents", "references", "scripts", "examples"):
        entry = source / name
        if entry.is_dir():
            shutil.copytree(entry, destination / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(entry, destination / name)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path,
                        default=Path.home() / ".agents/skills/codex-thread-coordination",
                        help="Complete destination skill directory")
    args = parser.parse_args()
    destination = install(Path(__file__).resolve().parents[1], args.dest)
    print(f"Installed: {destination}")
    print("If the skill does not appear in Codex, restart it.")


if __name__ == "__main__":
    try:
        main()
    except OSError as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
