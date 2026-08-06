"""Command line interface.

Commands operate on the project in the current working directory, where the
configuration is discovered.
"""

from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from rtfc._changelog import ChangelogError, insert_version
from rtfc._config import Config, ConfigError, MetadataFieldConfig, SectionConfig, load_config
from rtfc._entry import Entry, EntryError, load_entries
from rtfc._format import Format, FormatError, get_format
from rtfc._render import JinjaRenderer, RenderError
from rtfc._validation import ValidationContext, ValidationError

__all__ = ("main",)


class _Args(argparse.Namespace):
    command: str
    # build:
    version: str = ""
    dry_run: bool = False
    # new:
    section: str | None = None
    meta: list[tuple[str, Any]] | None = None
    content: str | None = None


def _parse_value(raw: str) -> Any:
    """Parse ``raw`` as a TOML value, falling back to a plain string."""
    try:
        return tomllib.loads(f"value = {raw}")["value"]
    except tomllib.TOMLDecodeError:
        return raw


def _meta_field(value: str) -> tuple[str, Any]:
    """Parse a ``KEY=VALUE`` argument into a metadata item, used as an argparse type.

    The value is parsed as TOML, falling back to a plain string.
    """
    key, separator, raw = value.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError(f"{value!r} is not of the form KEY=VALUE")
    return key, _parse_value(raw)


def _build_parser(config: Config) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rtfc", description="Manage changelog entries and build changelogs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="Validate the configuration and all changelog entries.")

    build = subparsers.add_parser("build", help="Combine the changelog entries into the changelog.")
    build.add_argument("--version", required=True, help="Release version; entry files are deleted after building.")
    build.add_argument(
        "--dry-run", action="store_true", help="Print the version block instead of updating the changelog."
    )

    new = subparsers.add_parser("new", help="Create a changelog entry.", description="Create a changelog entry.")
    new.add_argument("-s", "--section", choices=list(config.sections) or None, help="Section id of the entry.")
    new.add_argument(
        "--meta", action="append", type=_meta_field, metavar="KEY=VALUE", help="Metadata field; can be repeated."
    )
    new.add_argument("--content", help="Entry content; defaults to a placeholder, opened in $EDITOR when set.")

    return parser


def _docs_parser() -> argparse.ArgumentParser:
    """Build the parser from a default configuration, for the sphinx-argparse documentation.

    Running the actual command line interface requires a valid configuration.
    ``construct()`` bypasses validation, so the documented ``--section``
    choices are the default sections.
    """
    return _build_parser(Config.construct(changelog=Path("changelog.rst"), sections=['depends on configuration.']))


def _load(config: Config) -> tuple[Format, list[Entry]]:
    fmt = get_format(config.format)
    entries = load_entries(config.directory, sections=config.sections, metadata_validator=config.metadata_validator())
    return fmt, entries


def _check(config: Config) -> int:
    """Handle the ``check`` command: validate the configuration and all entries."""
    fmt, entries = _load(config)
    JinjaRenderer(config=config, fmt=fmt)  # Validates the entry template.
    print(f"OK: {len(entries)} valid entries")
    return 0


def _build(args: _Args, config: Config) -> int:
    """Handle the ``build`` command: combine the entries into the changelog."""
    fmt, entries = _load(config)
    if not entries:
        print("No changelog entries found", file=sys.stderr)
        return 1
    renderer = JinjaRenderer(config=config, fmt=fmt)
    header = fmt.version_header(args.version, datetime.date.today())
    block = renderer.render_block(entries, header=header)
    if args.dry_run:
        print(block)
        return 0

    changelog = config.changelog.read_text(encoding="utf-8")
    config.changelog.write_text(insert_version(changelog, block, fmt=fmt), encoding="utf-8")
    for entry in entries:
        entry.path.unlink()
    print(f"Updated {config.changelog}")
    return 0


def _prompt_section(sections: dict[str, SectionConfig]) -> str | None:
    """Prompt for the entry section; an empty answer means no section."""
    ids = ", ".join(sections)
    while True:
        raw = input(f"Section ({ids}) [none]: ").strip()
        if not raw:
            return None
        if raw in sections:
            return raw
        print(f"Unknown section {raw!r}")


def _prompt_metadata(fields: dict[str, MetadataFieldConfig], metadata: dict[str, Any]) -> None:
    """Prompt for the metadata fields of the configured schema not already provided.

    An empty answer skips the field, leaving its schema default to apply;
    invalid values are prompted for again.
    """
    for name, field in fields.items():
        if name in metadata:
            continue
        if field.required:
            hint = "required"
        elif field.default is not None:
            hint = f"default: {field.default!r}"
        else:
            hint = "optional"
        while True:
            raw = input(f"{name} ({field.type}, {hint}): ").strip()
            if not raw:
                if field.required:
                    print(f"{name!r} is required")
                    continue
                break
            # For string fields the raw input is the value; anything else goes
            # through TOML parsing (so e.g. arrays can be entered as `["a", "b"]`):
            value = raw if field.type == "string" else _parse_value(raw)
            try:
                field._validator().validate(value, ValidationContext(path=(name,)))
            except ValidationError as exc:
                print(exc)
                continue
            metadata[name] = value
            break


def _new(args: _Args, config: Config) -> int:
    """Handle the ``new`` command: create a changelog entry.

    When run from a terminal, prompts for the values not provided as command
    line arguments, before opening ``$EDITOR`` on the created entry.
    """
    if args.section is not None and args.section not in config.sections:
        expected = ", ".join(map(repr, config.sections))
        print(f"Unknown section {args.section!r} (expected one of: {expected})", file=sys.stderr)
        return 1

    metadata = dict(args.meta or [])
    if sys.stdin.isatty():
        if args.section is None and config.sections:
            args.section = _prompt_section(config.sections)
        _prompt_metadata(config.metadata, metadata)

    entry = Entry.create(
        config.directory,
        section=args.section,
        metadata=metadata,
        content=args.content if args.content is not None else "Describe the change.",
    )
    entry.write()
    print(f"Created {entry.path}")

    editor = os.getenv("EDITOR")
    if args.content is None and editor:
        subprocess.run([editor, str(entry.path)], check=False)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the rtfc command line interface.

    A valid configuration is required for any invocation: it is loaded first,
    as the parser is built from it (e.g. the ``--section`` choices).
    """
    try:
        config = load_config(Path.cwd())
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    args = _build_parser(config).parse_args(argv, namespace=_Args())
    try:
        if args.command == "check":
            return _check(config)
        if args.command == "build":
            return _build(args, config)
        return _new(args, config)
    except (ChangelogError, EntryError, FormatError, RenderError) as exc:
        print(exc, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Aborted", file=sys.stderr)
        return 1
