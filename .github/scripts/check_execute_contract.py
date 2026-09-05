#!/usr/bin/env python3
"""Check stable taskflow-execute invariants without pinning prose layout.

This file is BYTE-IDENTICAL in taskflow-claude, taskflow-codex and
taskflow-gemini. The invariants themselves are data, in the sibling
`contract.json`, because a few of them are legitimately harness-specific: on
Claude Code `native` isolation is the agent's own `isolation: worktree`, not a
hand-created git worktree, so asserting that phrase there would make CI enforce
something false. Keeping the code identical and the phrases in data means a
real difference is visible in a diff instead of hidden in three copies of a
script that have quietly drifted apart.

`contract.json` shape:

    {"required_phrases": {"<label>": "<phrase>", ...}}

A phrase is matched case-insensitively as a substring of
`skills/taskflow-execute/SKILL.md`. Add one only for an invariant that would be
a defect to lose, never to pin wording for its own sake.
"""

from __future__ import annotations

import argparse
import json
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


def load_required(root: Path) -> tuple[dict[str, str], list[str]]:
    """The invariant table from `contract.json`, beside this script.

    A missing or malformed file is an ERROR, never an empty table: a check that
    silently verifies nothing is worse than no check, because it reports green.
    """
    path = Path(__file__).resolve().parent / "contract.json"
    if not path.is_file():
        return {}, [f"missing contract file: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"invalid JSON in {path}: {exc}"]
    required = data.get("required_phrases")
    if not isinstance(required, dict) or not required:
        return {}, [f"`required_phrases` in {path} must be a non-empty object"]
    bad = [k for k, v in required.items() if not isinstance(v, str) or not v.strip()]
    if bad:
        return {}, [f"`required_phrases` entries must be non-empty strings: {sorted(bad)}"]
    return required, []


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

    required, load_errors = load_required(root)
    errors.extend(load_errors)
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
