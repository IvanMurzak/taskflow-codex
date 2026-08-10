#!/usr/bin/env python3
"""Check the taskflow-execute skill's documented structural contract."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


SKILL_RELATIVE_PATH = Path("skills/taskflow-execute/SKILL.md")
EXPECTED_ARGUMENTS = {
    "<slug>": ("the only folder there",),
    "--scope=": ("all",),
    "--parallel=": ("1",),
    "--engine=": ("auto",),
    "--pipeline=": ("none", "—", "-"),
    "--review=": ("off",),
    "--merge=": ("ask",),
    "--submodules=": ("auto",),
    "--solo=": ("empty",),
    "--on-fail=": ("continue",),
    "--dry-run": ("off",),
}
EXPECTED_LOADING_FLAGS = {"--parallel", "--review", "--submodules"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the taskflow-execute skill contract."
    )
    parser.add_argument(
        "plugin_root",
        nargs="?",
        default=".",
        help="Plugin root (default: current directory)",
    )
    return parser.parse_args()


def main() -> None:
    plugin_root = Path(parse_args().plugin_root).expanduser().resolve()
    errors = check_contract(plugin_root)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"taskflow-execute contract check passed: {plugin_root}")


def check_contract(plugin_root: Path) -> list[str]:
    errors: list[str] = []
    skill_path = plugin_root / SKILL_RELATIVE_PATH
    try:
        contents = skill_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"missing `{SKILL_RELATIVE_PATH.as_posix()}`"]
    except OSError as exc:
        return [f"unable to read `{SKILL_RELATIVE_PATH.as_posix()}`: {exc}"]

    frontmatter, body = parse_frontmatter(contents, errors)
    if frontmatter is not None:
        check_frontmatter(frontmatter, errors)
    check_body(body, errors)

    loading_rows = find_table_rows(body, "1", ("Condition", "Load"), errors)
    condition_flags = check_loading_table(plugin_root, loading_rows, errors)
    argument_rows = find_table_rows(
        body, "3", ("Argument", "Values", "Default", "Notes"), errors
    )
    check_arguments(argument_rows, condition_flags, errors)
    return errors


def parse_frontmatter(
    contents: str, errors: list[str]
) -> tuple[dict[str, Any] | None, str]:
    match = re.match(
        r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", contents, re.DOTALL
    )
    if match is None:
        errors.append(
            "`skills/taskflow-execute/SKILL.md` must start with closed YAML frontmatter"
        )
        return None, contents
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"taskflow-execute frontmatter is not valid YAML: {exc}")
        return None, contents[match.end() :]
    if not isinstance(frontmatter, dict):
        errors.append("taskflow-execute frontmatter must be a YAML object")
        return None, contents[match.end() :]
    return frontmatter, contents[match.end() :]


def check_frontmatter(frontmatter: dict[str, Any], errors: list[str]) -> None:
    for field in ("name", "description"):
        value = frontmatter.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"taskflow-execute frontmatter field `{field}` must be non-empty")
    for field in ("argument-hint", "allowed-tools"):
        if field in frontmatter:
            errors.append(f"taskflow-execute frontmatter must not contain `{field}`")
    for field in ("disable-model-invocation", "disable_model_invocation"):
        if field in frontmatter and frontmatter[field] is not False:
            errors.append(f"taskflow-execute frontmatter field `{field}` must be absent or false")


def check_body(body: str, errors: list[str]) -> None:
    if re.search(r"(?m)^[ \t]{0,3}(?:`{3,}|~{3,})[ \t]*!", body):
        errors.append("taskflow-execute body must not contain a fenced injected shell block")


def find_table_rows(
    body: str,
    section_number: str,
    expected_header: tuple[str, ...],
    errors: list[str],
) -> list[list[str]]:
    section_match = re.search(
        rf"(?ms)^## {re.escape(section_number)}\..*?(?=^## |\Z)", body
    )
    if section_match is None:
        errors.append(f"missing §{section_number} required table")
        return []

    lines = section_match.group().splitlines()
    for index, line in enumerate(lines):
        cells = parse_table_row(line)
        if cells != list(expected_header):
            continue
        if index + 1 >= len(lines) or not is_table_separator(lines[index + 1]):
            continue
        rows: list[list[str]] = []
        for row_line in lines[index + 2 :]:
            row = parse_table_row(row_line)
            if row is None:
                break
            rows.append(row)
        return rows

    errors.append(
        f"missing §{section_number} table with columns "
        + ", ".join(f"`{column}`" for column in expected_header)
    )
    return []


def parse_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def is_table_separator(line: str) -> bool:
    cells = parse_table_row(line)
    return cells is not None and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def check_loading_table(
    plugin_root: Path, rows: list[list[str]], errors: list[str]
) -> set[str]:
    conditions = "\n".join(row[0] for row in rows if len(row) >= 2)
    loads = "\n".join(row[1] for row in rows if len(row) >= 2)
    for reference in sorted(
        set(re.findall(r"references/([A-Za-z0-9_.-]+\.md)", loads))
    ):
        reference_path = plugin_root / "skills/taskflow-execute/references" / reference
        if not reference_path.is_file():
            errors.append(
                "loading-table reference is missing: "
                f"`{reference_path.relative_to(plugin_root).as_posix()}`"
            )
    flags = set(re.findall(r"--[A-Za-z0-9-]+", conditions))
    for flag in sorted(EXPECTED_LOADING_FLAGS - flags):
        errors.append(f"§1 loading table is missing condition flag `{flag}`")
    for flag in sorted(flags - EXPECTED_LOADING_FLAGS):
        errors.append(f"§1 loading table has unexpected condition flag `{flag}`")
    return flags


def argument_name(row: list[str]) -> str | None:
    if not row:
        return None
    match = re.match(r"`?((?:--[A-Za-z0-9-]+=?|<slug>))", row[0])
    if match is None:
        return None
    return match.group(1)


def check_arguments(
    rows: list[list[str]], condition_flags: set[str], errors: list[str]
) -> None:
    documented: dict[str, list[str]] = {}
    for row in rows:
        if len(row) != 4:
            errors.append("§3 arguments table has a row with an unexpected number of columns")
            continue
        name = argument_name(row)
        if name is None:
            errors.append(f"§3 arguments table has an unrecognized argument row `{row[0]}`")
            continue
        if name in documented:
            errors.append(f"§3 arguments table documents `{name}` more than once")
        documented[name] = row

    expected_names = set(EXPECTED_ARGUMENTS)
    found_names = set(documented)
    for name in sorted(expected_names - found_names):
        errors.append(f"§3 arguments table is missing `{name}`")
    for name in sorted(found_names - expected_names):
        errors.append(f"§3 arguments table has unexpected argument `{name}`")

    for name in sorted(expected_names & found_names):
        expected_defaults = EXPECTED_ARGUMENTS[name]
        if not any(
            default_matches(documented[name][2], candidate)
            for candidate in expected_defaults
        ):
            expected_text = " / ".join(f"`{value}`" for value in expected_defaults)
            errors.append(
                f"§3 argument `{name}` has default `{documented[name][2]}`; expected {expected_text}"
            )

    engine_row = documented.get("--engine=")
    if engine_row is not None and re.search(
        r"\bnative\b", engine_row[1], re.IGNORECASE
    ):
        errors.append("§3 argument `--engine=` must not offer `native`")

    for flag in sorted(condition_flags):
        argument = f"{flag}=" if f"{flag}=" in expected_names else flag
        if argument not in found_names:
            errors.append(
                f"§1 loading-table condition flag `{flag}` is missing from the §3 arguments table"
            )


def default_matches(documented_default: str, expected: str) -> bool:
    actual = documented_default.strip().casefold()
    if expected in {"-", "—"}:
        return actual == expected
    return re.search(
        rf"(?<![a-z0-9]){re.escape(expected.casefold())}(?![a-z0-9])", actual
    ) is not None


if __name__ == "__main__":
    main()
