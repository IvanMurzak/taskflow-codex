#!/usr/bin/env python3
"""Check stable taskflow-execute invariants without pinning prose layout."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_root", nargs="?", default=".")
    root = Path(parser.parse_args().plugin_root).resolve()
    errors = check(root)
    if errors:
        print("\n".join(f"- {error}" for error in errors))
        raise SystemExit(1)
    print(f"taskflow-execute contract check passed: {root}")


def check(root: Path) -> list[str]:
    path = root / "skills/taskflow-execute/SKILL.md"
    if not path.is_file():
        return [f"missing {path}"]
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return ["invalid or unclosed YAML frontmatter"]
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return [f"invalid YAML frontmatter: {exc}"]
    for key in ("name", "description"):
        if not isinstance(frontmatter.get(key), str) or not frontmatter[key].strip():
            errors.append(f"frontmatter `{key}` must be non-empty")

    required = {
        "merge default": "`--merge=on-green`",
        "path-only dispatch": "absolute path to the",
        "no task-body preload": "never load the task body",
        "parallel batch": "before waiting",
        "native engine": "`native` uses git worktrees",
        "root repository": "`repo: \".\"` means the root git repository",
        "sole board writer": "only you may edit it",
    }
    lowered = text.casefold()
    for label, phrase in required.items():
        if phrase.casefold() not in lowered:
            errors.append(f"missing {label} invariant: {phrase}")

    for reference in ("parallel-execution.md", "code-review.md", "submodules.md"):
        if not (root / "skills/taskflow-execute/references" / reference).is_file():
            errors.append(f"missing reference: {reference}")
    return errors


if __name__ == "__main__":
    main()
